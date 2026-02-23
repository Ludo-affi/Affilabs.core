"""live_binding_stats.py — Pure-computation module for real-time binding quality signals.

All functions are stateless and take numpy arrays + scalar times.
No Qt, no hardware, no side effects.

Units
-----
- Internal: wavelength in nm (as stored in buffer_mgr.cycle_data[ch].spr)
- User-facing: RU  (355 RU = 1 nm)

Semi-qualitative thresholds (all in RU)
---------------------------------------
Binding response (anchor at t+20s, compared to pre-baseline mean):
    Strong   >= 50 RU
    Moderate >= 15 RU
    Weak     >= 3  RU
    None     <  3  RU

Slope signal (first 15s, linear fit, RU/min):
    Rising   >= +2 RU/min
    Flat     -2 to +2 RU/min
    Falling  <= -2 RU/min

Regeneration (post-baseline vs pre-baseline of same channel):
    Recovered  abs(delta) <= 10 RU
    High       delta > +10 RU   (incomplete regen)
    Low        delta < -10 RU   (over-regenerated)

Immobilisation ΔSPR (baseline-to-baseline):
    Dense    >= 2000 RU
    Good     >= 500  RU
    Low      >= 50   RU
    Minimal  <  50   RU
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Unit conversion ────────────────────────────────────────────────────────────
NM_TO_RU: float = 355.0


def nm_to_ru(nm: float) -> float:
    return nm * NM_TO_RU


# ── Core computation helpers ───────────────────────────────────────────────────

def _slice_window(
    time_arr: np.ndarray,
    spr_arr: np.ndarray,
    t_start: float,
    t_end: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return time/spr slices within [t_start, t_end]. Both arrays same length."""
    mask = (time_arr >= t_start) & (time_arr <= t_end)
    return time_arr[mask], spr_arr[mask]


def compute_pre_baseline(
    time_arr: np.ndarray,
    spr_arr: np.ndarray,
    injection_time: float,
    window_sec: float = 30.0,
) -> Optional[float]:
    """Mean SPR (nm) over the 30 s window immediately before injection.

    Returns None if fewer than 3 data points exist in the window.
    """
    t0 = injection_time - window_sec
    t, s = _slice_window(time_arr, spr_arr, t0, injection_time)
    if len(s) < 3:
        logger.debug(
            f"pre_baseline: only {len(s)} pts in [{t0:.1f}, {injection_time:.1f}]s — skipped"
        )
        return None
    return float(np.mean(s))


def compute_anchor(
    time_arr: np.ndarray,
    spr_arr: np.ndarray,
    injection_time: float,
    anchor_offset_sec: float = 20.0,
    avg_window_sec: float = 5.0,
) -> Optional[float]:
    """Mean SPR (nm) in a short window centred on injection_time + anchor_offset_sec.

    Used as the response position reference after signal has stabilised.
    Returns None if fewer than 2 points.
    """
    t_centre = injection_time + anchor_offset_sec
    t_start = t_centre - avg_window_sec / 2
    t_end = t_centre + avg_window_sec / 2
    _, s = _slice_window(time_arr, spr_arr, t_start, t_end)
    if len(s) < 2:
        return None
    return float(np.mean(s))


def compute_slope(
    time_arr: np.ndarray,
    spr_arr: np.ndarray,
    injection_time: float,
    slope_window_sec: float = 15.0,
) -> Optional[float]:
    """Linear slope (nm/s) of SPR vs time over first slope_window_sec after injection.

    Returns None if fewer than 3 points.  Convert to RU/min externally.
    """
    t0 = injection_time
    t1 = injection_time + slope_window_sec
    t, s = _slice_window(time_arr, spr_arr, t0, t1)
    if len(s) < 3:
        return None
    # polyfit degree 1: slope in nm/s
    coeffs = np.polyfit(t - t[0], s, 1)
    return float(coeffs[0])  # nm/s


def compute_post_baseline(
    time_arr: np.ndarray,
    spr_arr: np.ndarray,
    cycle_end_time: float,
    window_sec: float = 30.0,
) -> Optional[float]:
    """Mean SPR (nm) over the last 30 s of the cycle (post-wash baseline).

    Returns None if fewer than 3 points.
    """
    t0 = cycle_end_time - window_sec
    t, s = _slice_window(time_arr, spr_arr, t0, cycle_end_time)
    if len(s) < 3:
        return None
    return float(np.mean(s))


def compute_delta_spr_ru(
    pre_baseline_nm: Optional[float],
    post_baseline_nm: Optional[float],
) -> Optional[float]:
    """Baseline-to-baseline ΔSPR in RU (positive = blue shift = binding removed).

    SPR convention: binding *decreases* wavelength (blue shift).
    ΔSPR = (pre - post) × 355   → positive when baseline returns high after wash
           = 0 for perfect regeneration (pre ≈ post)

    For immobilisation: the key number is (post_immob - pre_immob) × 355,
    which will be negative (chip loaded → baseline drops).  Callers should take
    abs() for display.
    """
    if pre_baseline_nm is None or post_baseline_nm is None:
        return None
    return nm_to_ru(pre_baseline_nm - post_baseline_nm)


# ── Classification ─────────────────────────────────────────────────────────────

# Color tokens (match existing app palette)
_GREEN  = "#34C759"
_BLUE   = "#007AFF"
_AMBER  = "#FF9500"
_RED    = "#FF3B30"
_MUTED  = "#86868B"


def classify_binding(
    pre_baseline_nm: Optional[float],
    current_spr_nm: Optional[float],
) -> Tuple[str, str]:
    """Label + color for binding response at current time.

    ΔSPR = (pre - current) × 355  (positive = blue shift = binding event).
    """
    if pre_baseline_nm is None or current_spr_nm is None:
        return "—", _MUTED

    delta_ru = nm_to_ru(pre_baseline_nm - current_spr_nm)

    if delta_ru >= 50:
        return f"+{delta_ru:.0f} RU  Strong", _GREEN
    if delta_ru >= 15:
        return f"+{delta_ru:.0f} RU  Moderate", _BLUE
    if delta_ru >= 3:
        return f"+{delta_ru:.0f} RU  Weak", _AMBER
    if delta_ru > 0:
        return f"+{delta_ru:.0f} RU  None", _MUTED
    # Negative delta = wavelength went up = not a binding event
    return f"{delta_ru:.0f} RU", _MUTED


def classify_slope(slope_nm_per_s: Optional[float]) -> Tuple[str, str]:
    """Label + color for slope direction.

    slope_nm_per_s: from compute_slope().  Convert to RU/min for display.
    """
    if slope_nm_per_s is None:
        return "—", _MUTED

    # nm/s × 355 RU/nm × 60 s/min = RU/min
    slope_ru_per_min = slope_nm_per_s * NM_TO_RU * 60.0

    if slope_ru_per_min >= 2.0:
        return f"↑ {slope_ru_per_min:+.0f} RU/min", _GREEN
    if slope_ru_per_min <= -2.0:
        return f"↓ {slope_ru_per_min:+.0f} RU/min", _RED
    return f"→ {slope_ru_per_min:+.0f} RU/min", _MUTED


def classify_regen(
    pre_baseline_nm: Optional[float],
    post_baseline_nm: Optional[float],
) -> Tuple[str, str]:
    """Label + color for regeneration quality (post-wash baseline vs pre-inject baseline).

    Δ = (post - pre) × 355
    Positive Δ → baseline went up after wash → over-regenerated or artefact.
    Negative Δ → incomplete regeneration (analyte still on surface).
    """
    if pre_baseline_nm is None or post_baseline_nm is None:
        return "—", _MUTED

    delta_ru = nm_to_ru(post_baseline_nm - pre_baseline_nm)

    if abs(delta_ru) <= 10:
        return f"Recovered ({delta_ru:+.0f} RU)", _GREEN
    if delta_ru > 10:
        return f"High ({delta_ru:+.0f} RU)", _AMBER
    return f"Incomplete ({delta_ru:+.0f} RU)", _RED


def classify_immob(delta_spr_ru: Optional[float]) -> Tuple[str, str]:
    """Label + color for immobilisation surface density.

    delta_spr_ru should be abs(ΔSPR) so always positive.
    """
    if delta_spr_ru is None:
        return "—", _MUTED

    d = abs(delta_spr_ru)
    if d >= 2000:
        return f"{d:.0f} RU  Dense", _BLUE
    if d >= 500:
        return f"{d:.0f} RU  Good", _GREEN
    if d >= 50:
        return f"{d:.0f} RU  Low", _AMBER
    return f"{d:.0f} RU  Minimal", _RED
