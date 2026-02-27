"""TraceDrawer exporter — builds per-cycle .txt files from Edits tab data.

Workflow:
  1. User tweaks graphs in the Edits tab (alignment, ref subtraction, etc.)
  2. User opens TraceDrawer export dialog
  3. Dialog receives cycle list + raw data already in memory
  4. User picks cycles, adjusts time windows / baseline / ref
  5. Export produces a .zip with one .txt per cycle

TraceDrawer .txt format (per file):
  - Tab-delimited
  - Column 1 : Time (s), zeroed at injection start
  - Column 2+: one column per included channel (Ch A, Ch B …)
  - Values are baseline-subtracted Δ resonance (nm)
  - Interpolated to a regular time grid
"""

from __future__ import annotations

import ast
import io
import math
import re
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from affilabs.utils.logger import logger


# ═══════════════════════════════════════════════════════════════════════
#  Trace builder — works on in-memory raw_data_rows (list[dict])
# ═══════════════════════════════════════════════════════════════════════

def build_trace(
    raw_data_rows: list[dict[str, Any]],
    channel: str,
    cycle: dict[str, Any],
    alignment: dict[str, Any] | None = None,
    ref_channel: str | None = None,
    pre_inject_s: float = 30.0,
    assoc_s: float = 300.0,
    dissoc_s: float = 300.0,
    baseline_window_s: float = 10.0,
) -> dict[str, Any] | None:
    """Build a single baseline-subtracted, time-zeroed trace for *channel*
    within *cycle*, using the Edits-tab raw data rows.

    Returns
    -------
    dict
        ``time`` : np.ndarray (t = 0 at injection)
        ``value``: np.ndarray (Δ nm, baseline-subtracted)
        ``label``: str  (concentration label for column header)
        ``conc`` : float | None
        ``cycle_dict``: original cycle dict (for zip metadata)
    Or *None* if insufficient data.
    """
    inject_time = _find_injection_time(cycle, channel)
    if inject_time is None:
        # Fallback: use cycle start
        inject_time = _resolve_start(cycle)
    if inject_time is None:
        logger.warning(f"TraceDrawer: cannot determine injection/start time for cycle {cycle.get('cycle_num', '?')}")
        return None

    abs_start = inject_time - pre_inject_s
    abs_end = inject_time + assoc_s + dissoc_s

    # Alignment shift
    shift = 0.0
    if alignment:
        shift = alignment.get("shift", 0.0)

    # --- Extract channel data in window ---
    times: list[float] = []
    vals: list[float] = []
    ch_lower = channel.lower()

    for row in raw_data_rows:
        t = row.get("time", row.get("elapsed", 0.0))
        if t < abs_start or t > abs_end:
            continue
        rch = str(row.get("channel", "")).lower()
        if rch == ch_lower:
            times.append(t)
            vals.append(float(row.get("value", 0.0)))

    if len(times) < 5:
        logger.warning(f"TraceDrawer: only {len(times)} pts for cycle {cycle.get('cycle_num', '?')} ch {channel}")
        return None

    time_arr = np.array(times, dtype=float)
    val_arr = np.array(vals, dtype=float)
    order = np.argsort(time_arr)
    time_arr = time_arr[order]
    val_arr = val_arr[order]

    # --- Reference subtraction ---
    if ref_channel and ref_channel.lower() != ch_lower:
        ref_t, ref_v = _extract_channel(raw_data_rows, ref_channel, abs_start, abs_end)
        if len(ref_t) >= 2:
            interp_ref = np.interp(time_arr, ref_t, ref_v)
            val_arr = val_arr - interp_ref

    # --- Zero time at injection + alignment shift ---
    time_arr = time_arr - inject_time + shift

    # --- Baseline subtraction ---
    bl_mask = (time_arr >= -baseline_window_s) & (time_arr < 0)
    if bl_mask.sum() > 0:
        baseline = np.nanmean(val_arr[bl_mask])
        val_arr = val_arr - baseline

    conc = _get_concentration(cycle, channel)
    label = _format_label(cycle, channel, conc)

    return {
        "time": time_arr,
        "value": val_arr,
        "label": label,
        "conc": conc,
        "cycle_dict": cycle,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Interpolation
# ═══════════════════════════════════════════════════════════════════════

def interpolate_traces(
    traces: list[dict[str, Any]],
    step_s: float = 0.5,
) -> tuple[np.ndarray, list[np.ndarray], list[str]]:
    """Interpolate traces onto a common regular time grid.

    Returns ``(common_time, values_list, labels)``.
    """
    if not traces:
        return np.array([]), [], []

    t_min = min(float(tr["time"][0]) for tr in traces)
    t_max = max(float(tr["time"][-1]) for tr in traces)
    common = np.arange(t_min, t_max + step_s / 2, step_s)

    values: list[np.ndarray] = []
    labels: list[str] = []
    for tr in traces:
        iv = np.interp(common, tr["time"], tr["value"], left=np.nan, right=np.nan)
        values.append(iv)
        labels.append(tr["label"])
    return common, values, labels


# ═══════════════════════════════════════════════════════════════════════
#  Single-file .txt writer
# ═══════════════════════════════════════════════════════════════════════

def write_single_txt(
    common_time: np.ndarray,
    values_list: list[np.ndarray],
    labels: list[str],
    precision: int = 4,
) -> str:
    """Build tab-delimited text for one .txt file (one cycle, may have multiple channels)."""
    # De-duplicate labels
    used: dict[str, int] = {}
    final_labels: list[str] = []
    for lbl in labels:
        if lbl in used:
            used[lbl] += 1
            final_labels.append(f"{lbl} ({used[lbl]})")
        else:
            used[lbl] = 1
            final_labels.append(lbl)

    lines: list[str] = []
    lines.append("\t".join(["Time"] + final_labels))
    for i, t in enumerate(common_time):
        parts = [f"{t:.{precision}f}"]
        for vals in values_list:
            v = vals[i]
            parts.append("" if np.isnan(v) else f"{v:.{precision}f}")
        lines.append("\t".join(parts))
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════════
#  ZIP packager — one .txt per cycle
# ═══════════════════════════════════════════════════════════════════════

def build_zip(
    per_cycle_traces: list[list[dict[str, Any]]],
    step_s: float = 0.5,
    precision: int = 4,
) -> bytes:
    """Build in-memory .zip with one .txt per cycle.

    *per_cycle_traces* is a list of lists: outer = cycle, inner = per-channel
    traces for that cycle.

    Each .txt is named ``<Type>_<Conc>_C<num>.txt``.
    Returns raw zip bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for traces in per_cycle_traces:
            if not traces:
                continue
            common, values, labels = interpolate_traces(traces, step_s=step_s)
            if len(common) == 0:
                continue
            txt = write_single_txt(common, values, labels, precision=precision)
            fname = _safe_filename(traces[0])
            zf.writestr(fname, txt)

    return buf.getvalue()


def export_zip(
    per_cycle_traces: list[list[dict[str, Any]]],
    output_path: Path,
    step_s: float = 0.5,
    precision: int = 4,
) -> None:
    """Write the zip to *output_path*."""
    data = build_zip(per_cycle_traces, step_s=step_s, precision=precision)
    output_path.write_bytes(data)
    n_cycles = sum(1 for t in per_cycle_traces if t)
    logger.info(f"TraceDrawer export: {output_path} ({n_cycles} cycles)")


# ═══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _extract_channel(
    raw_data_rows: list[dict],
    channel: str,
    t_start: float,
    t_end: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Pull sorted (time, value) arrays for a channel in a time window."""
    ch = channel.lower()
    ts: list[float] = []
    vs: list[float] = []
    for row in raw_data_rows:
        t = row.get("time", row.get("elapsed", 0.0))
        if t < t_start or t > t_end:
            continue
        if str(row.get("channel", "")).lower() == ch:
            ts.append(t)
            vs.append(float(row.get("value", 0.0)))
    if not ts:
        return np.array([]), np.array([])
    ta = np.array(ts)
    va = np.array(vs)
    order = np.argsort(ta)
    return ta[order], va[order]


def _resolve_start(cycle: dict) -> float | None:
    for key in ("start_time_sensorgram", "sensorgram_time", "start_time",
                "time", "elapsed_time", "elapsed"):
        v = cycle.get(key)
        if v is not None:
            try:
                f = float(v)
                if not math.isnan(f):
                    return f
            except (TypeError, ValueError):
                pass
    return None


def _find_injection_time(cycle: dict, channel: str) -> float | None:
    """Per-channel injection time from cycle dict."""
    itbc = cycle.get("injection_time_by_channel")
    if isinstance(itbc, str):
        try:
            itbc = ast.literal_eval(itbc)
        except (ValueError, SyntaxError):
            itbc = None
    if isinstance(itbc, dict):
        for k in (channel.lower(), channel.upper()):
            if k in itbc:
                try:
                    return float(itbc[k])
                except (TypeError, ValueError):
                    pass
    return _resolve_start(cycle)


def _get_concentration(cycle: dict, channel: str) -> float | None:
    concs = cycle.get("concentrations")
    if isinstance(concs, str):
        try:
            concs = ast.literal_eval(concs)
        except (ValueError, SyntaxError):
            concs = None
    if isinstance(concs, dict):
        for k in (channel.upper(), channel.lower()):
            if k in concs and concs[k] is not None:
                try:
                    return float(concs[k])
                except (TypeError, ValueError):
                    pass
    cv = cycle.get("concentration_value")
    if cv is not None and not (isinstance(cv, float) and math.isnan(cv)):
        try:
            return float(cv)
        except (TypeError, ValueError):
            pass
    return None


def _format_label(cycle: dict, channel: str, conc: float | None) -> str:
    units = cycle.get("concentration_units", "nM")
    if units is None or (isinstance(units, float) and math.isnan(units)):
        units = cycle.get("units", "nM")
    if units is None or (isinstance(units, float) and math.isnan(units)):
        units = "nM"
    if conc is not None:
        cs = f"{int(conc)}" if conc == int(conc) else f"{conc}"
        return f"{cs} {units}"
    return f"C{cycle.get('cycle_num', '?')}_{channel.upper()}"


def _safe_filename(trace: dict) -> str:
    cd = trace.get("cycle_dict", {})
    ctype = str(cd.get("type", "Cycle")).replace(" ", "_")
    cnum = cd.get("cycle_num", "?")
    conc = trace.get("conc")
    units = cd.get("concentration_units", "nM")
    if units is None or (isinstance(units, float) and math.isnan(units)):
        units = "nM"
    if conc is not None:
        cs = f"{int(conc)}" if conc == int(conc) else f"{conc}"
        name = f"{ctype}_{cs}{units}_C{cnum}"
    else:
        name = f"{ctype}_C{cnum}"
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip(". ")[:80]
    return f"{safe}.txt"
