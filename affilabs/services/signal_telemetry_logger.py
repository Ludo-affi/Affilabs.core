"""Signal Telemetry Logger — Phase 1 of SIGNAL_EVENT_CLASSIFIER_FRS.

Silent per-frame feature logger. No UI. No user-visible output.
Writes one CSV per acquisition session to ~/Documents/Affilabs Data/telemetry/.

Design: singleton, thread-safe, buffered bulk-write (flush every N rows or on stop).
Called from spectrum_helpers.py once per processed frame.

See docs/features/SIGNAL_EVENT_CLASSIFIER_FRS.md for full specification.
"""

from __future__ import annotations

import csv
import os
import shutil
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Deque

if TYPE_CHECKING:
    pass  # avoid circular imports — 'app' is accessed via attribute access only

_FLUSH_EVERY = 30          # rows
_MIN_FREE_GB  = 0.5        # guard: skip if disk < 500 MB free
_MAX_SESSION_ROWS = 500_000  # hard cap per session (≈8 h at 1 Hz × 4 channels)

# Rolling window sizes for derived features
_P2P_WINDOW    = 5    # frames for peak-to-peak
_SLOPE_WINDOW  = 5.0  # seconds for slope (linear regression)
_OPTICAL_WINDOW = 10  # frames for pre/post triage buffer (5 pre + 5 post)


def _get_telemetry_dir() -> Path:
    from affilabs.utils.resource_path import get_writable_data_path
    telemetry = get_writable_data_path("data/telemetry")
    telemetry.mkdir(parents=True, exist_ok=True)
    return telemetry


def _has_enough_disk(path: Path) -> bool:
    try:
        usage = shutil.disk_usage(path)
        return usage.free / 1e9 >= _MIN_FREE_GB
    except OSError:
        return False


def _compute_slope(pts: list[tuple[float, float]]) -> float | None:
    """Linear regression slope (nm/s) over a list of (t, wavelength) pairs."""
    if len(pts) < 2:
        return None
    n = len(pts)
    sum_t  = sum(p[0] for p in pts)
    sum_w  = sum(p[1] for p in pts)
    sum_tt = sum(p[0] ** 2 for p in pts)
    sum_tw = sum(p[0] * p[1] for p in pts)
    denom = n * sum_tt - sum_t ** 2
    if abs(denom) < 1e-12:
        return None
    return (n * sum_tw - sum_t * sum_w) / denom


class _ChannelRollingState:
    """Per-channel rolling buffers for p2p, slope, delta_1frame, and optical triage."""

    def __init__(self) -> None:
        self._wavelengths: Deque[float] = deque(maxlen=_P2P_WINDOW)
        self._slope_pts: Deque[tuple[float, float]] = deque()  # (t, wl) — time-bounded
        self._last_wl: float | None = None
        # 10-frame optical buffer for pre/post event triage
        # Each entry: (wavelength_nm, transmittance_pct, fwhm_nm, raw_peak_counts)
        # None values allowed — classifier handles missing data gracefully
        self.optical_buffer: Deque[tuple[float | None, float | None, float | None, float | None]] = deque(maxlen=_OPTICAL_WINDOW)

    def push(self, elapsed_s: float, wavelength: float) -> None:
        self._last_wl = self._wavelengths[-1] if self._wavelengths else None
        self._wavelengths.append(wavelength)
        self._slope_pts.append((elapsed_s, wavelength))
        cutoff = elapsed_s - _SLOPE_WINDOW
        while self._slope_pts and self._slope_pts[0][0] < cutoff:
            self._slope_pts.popleft()

    def push_optical(
        self,
        wavelength: float | None,
        transmittance: float | None,
        fwhm: float | None,
        raw_peak: float | None,
    ) -> None:
        """Append one optical frame to the 10-point triage buffer."""
        self.optical_buffer.append((wavelength, transmittance, fwhm, raw_peak))

    def snapshot_pre(self) -> list[tuple]:
        """Return the last 5 optical frames as the pre-event snapshot."""
        buf = list(self.optical_buffer)
        return buf[-5:] if len(buf) >= 5 else buf

    @property
    def p2p(self) -> float | None:
        if len(self._wavelengths) < 2:
            return None
        return max(self._wavelengths) - min(self._wavelengths)

    @property
    def slope(self) -> float | None:
        return _compute_slope(list(self._slope_pts))

    @property
    def delta_1frame_ru(self) -> float | None:
        """Signed 1-frame wavelength change in RU (current − previous, × 355)."""
        if self._last_wl is None or not self._wavelengths:
            return None
        return (self._wavelengths[-1] - self._last_wl) * 355.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class SignalTelemetryLogger:
    """Singleton signal telemetry logger.

    Usage:
        # Start a session (called from _on_acquisition_started):
        SignalTelemetryLogger.get_instance().start_session(session_id)

        # Record a frame (called from spectrum_helpers.py):
        SignalTelemetryLogger.get_instance().record(
            app=app, channel=channel, elapsed_s=..., wavelength=...,
            intensity=..., iq_metrics=..., sensor_iq=...,
        )

        # Stop logger (called from _on_acquisition_stopped):
        SignalTelemetryLogger.get_instance().stop_session()
    """

    _instance: SignalTelemetryLogger | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SignalTelemetryLogger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._enabled: bool = False
        self._row_count: int = 0
        self._buffer: list[dict] = []
        self._write_lock = threading.Lock()
        self._csv_paths: dict[str, Path] = {}          # channel → file path
        self._csv_writers: dict[str, csv.DictWriter] = {}
        self._csv_files:   dict[str, object] = {}      # file handles
        self._rolling: dict[str, _ChannelRollingState] = {}  # channel → state
        self._telemetry_dir: Path | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, session_id: str) -> None:
        """Open telemetry files for a new acquisition session."""
        # Import lazily to avoid circular at module load time
        try:
            from settings import SIGNAL_TELEMETRY_ENABLED  # type: ignore[import]
            enabled = bool(SIGNAL_TELEMETRY_ENABLED)
        except (ImportError, AttributeError):
            enabled = False

        with self._write_lock:
            self._stop_session_locked()  # close any previous session gracefully
            self._session_id = session_id
            self._enabled = enabled
            self._row_count = 0
            self._rolling.clear()

            if not enabled:
                return

            self._telemetry_dir = _get_telemetry_dir()
            if not _has_enough_disk(self._telemetry_dir):
                self._enabled = False
                return

            # One CSV per channel so files stay under ~25 MB each
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            for ch in ("a", "b", "c", "d"):
                fname = f"signal_telemetry_{ts}_{session_id[:8]}_{ch}.csv"
                fpath = self._telemetry_dir / fname
                try:
                    fh = open(fpath, "w", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=_COLUMNS)
                    writer.writeheader()
                    self._csv_paths[ch]   = fpath
                    self._csv_writers[ch] = writer
                    self._csv_files[ch]   = fh
                    self._rolling[ch]     = _ChannelRollingState()
                except OSError:
                    pass  # disk error — disable rather than crash

    def stop_session(self) -> None:
        """Flush remaining rows and close files."""
        with self._write_lock:
            self._stop_session_locked()

    def get_optical_snapshot(self, channel: str) -> list[tuple]:
        """Return last 5 optical frames for a channel (pre-event snapshot).

        Safe to call from any thread — reads deque, no lock needed (GIL protects).
        Returns list of (wavelength_nm, transmittance_pct, fwhm_nm, raw_peak).
        Returns [] if fewer than 5 frames have been recorded.
        """
        ch = channel.lower()
        rolling = self._rolling.get(ch)
        if rolling is None:
            return []
        return rolling.snapshot_pre()

    def _stop_session_locked(self) -> None:
        """Close all open CSV files. Must be called with _write_lock held."""
        for fh in self._csv_files.values():
            try:
                fh.flush()
                fh.close()
            except OSError:
                pass
        self._csv_files.clear()
        self._csv_writers.clear()
        self._csv_paths.clear()
        self._session_id = None

    # ------------------------------------------------------------------
    # Per-frame recording
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        app: object,
        channel: str,
        elapsed_s: float,
        wavelength: float,
        intensity: float | None,
        iq_metrics: dict,
        sensor_iq: object | None,
        stage1_verdict: str = "",
        bubble_detected: bool = False,
        positive_front: bool = False,
        negative_front: bool = False,
        auto_label: str = "",
        is_control_channel: bool = False,
        control_slope_5s_ru: float | None = None,
        injection_index: int | None = None,
        cycle_sub_phase: str = "",
    ) -> None:
        """Record one frame per FRS §6.2 schema. Called from spectrum_helpers.py.

        This runs in the processing worker thread — keep it fast and never raise.
        """
        if not self._enabled or self._session_id is None:
            return
        if self._row_count >= _MAX_SESSION_ROWS:
            return

        try:
            ch = channel.lower()
            rolling = self._rolling.get(ch)
            if rolling is None:
                rolling = _ChannelRollingState()
                self._rolling[ch] = rolling

            rolling.push(elapsed_s, wavelength)
            rolling.push_optical(
                wavelength=wavelength,
                transmittance=iq_metrics.get("transmittance") if iq_metrics else None,
                fwhm=iq_metrics.get("fwhm") if iq_metrics else None,
                raw_peak=float(intensity) if intensity is not None else None,
            )

            # --- Cycle context (best-effort) ---
            cycle_type         = ""
            cycle_elapsed_frac: float | None = None
            try:
                mw    = getattr(app, "main_window", app)
                cycle = getattr(mw, "_current_cycle", None)
                if cycle is not None:
                    cycle_type = getattr(cycle, "type", "") or ""
                    dur = 0.0
                    try:
                        dur = float(cycle.get_duration_seconds())
                    except Exception:
                        pass
                    if dur > 0:
                        cycle_start = getattr(cycle, "_start_elapsed", None)
                        if cycle_start is not None:
                            elapsed_in_cycle = elapsed_s - float(cycle_start)
                            cycle_elapsed_frac = max(0.0, min(1.0, elapsed_in_cycle / dur))
            except Exception:
                pass

            # --- IQ level string ---
            iq_level_str = ""
            try:
                if sensor_iq is not None:
                    iq_level_str = (
                        sensor_iq.iq_level.value
                        if hasattr(sensor_iq.iq_level, "value")
                        else str(sensor_iq.iq_level)
                    )
            except Exception:
                pass

            # --- Derived RU values (nm × 355) ---
            dip_position_ru = round(wavelength * 355.0, 2)
            slope_nm        = rolling.slope          # nm/s or None
            slope_5s_ru     = _fmt(slope_nm * 355.0 if slope_nm is not None else None, 4)
            p2p_nm          = rolling.p2p            # nm or None
            p2p_5frame_ru   = _fmt(p2p_nm * 355.0 if p2p_nm is not None else None, 3)

            # delta_1frame: difference vs previous frame stored in rolling buffer
            delta_1frame_ru = _fmt(rolling.delta_1frame_ru, 3)

            # control slope diff
            slope_diff_ru: str | float = ""
            if slope_nm is not None and control_slope_5s_ru is not None:
                slope_diff_ru = _fmt(slope_nm * 355.0 - control_slope_5s_ru, 4)

            row: dict = {
                "session_id":           self._session_id,
                "timestamp_utc":        datetime.utcnow().isoformat(timespec="milliseconds"),
                "elapsed_s":            round(elapsed_s, 3),
                "channel":              ch.upper(),
                "is_control_channel":   int(is_control_channel),
                "cycle_type":           cycle_type,
                "cycle_sub_phase":      cycle_sub_phase,
                "cycle_elapsed_frac":   round(cycle_elapsed_frac, 4) if cycle_elapsed_frac is not None else "",
                "injection_index":      "" if injection_index is None else injection_index,
                "dip_position_ru":      dip_position_ru,
                "delta_1frame_ru":      delta_1frame_ru,
                "slope_5s_ru_per_s":    slope_5s_ru,
                "p2p_5frame_ru":        p2p_5frame_ru,
                "raw_intensity_ratio":  round(float(intensity), 4) if intensity is not None else "",
                "dip_depth":            _fmt(iq_metrics.get("dip_depth"), 4),
                "fwhm_nm":              _fmt(iq_metrics.get("fwhm"), 3),
                "control_slope_5s_ru":  _fmt(control_slope_5s_ru, 4),
                "slope_diff_ru":        slope_diff_ru,
                "iq_level":             iq_level_str,
                "stage1_verdict":       stage1_verdict,
                "bubble_detected":      int(bubble_detected),
                "positive_front":       int(positive_front),
                "negative_front":       int(negative_front),
                "auto_label":           auto_label,
                "manual_label":         "",
            }

            with self._write_lock:
                writer = self._csv_writers.get(ch)
                if writer is None:
                    return
                writer.writerow(row)
                self._row_count += 1
                if self._row_count % _FLUSH_EVERY == 0:
                    self._csv_files[ch].flush()
                if self._row_count % 1000 == 0 and not _has_enough_disk(self._telemetry_dir):
                    self._enabled = False

        except Exception:
            pass  # telemetry must never crash the acquisition thread


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_COLUMNS = [
    # Identity
    "session_id",
    "timestamp_utc",
    "elapsed_s",
    "channel",
    "is_control_channel",
    # Cycle context
    "cycle_type",
    "cycle_sub_phase",
    "cycle_elapsed_frac",
    "injection_index",
    # Signal features (RU)
    "dip_position_ru",
    "delta_1frame_ru",
    "slope_5s_ru_per_s",
    "p2p_5frame_ru",
    "raw_intensity_ratio",
    # Optical features
    "dip_depth",
    "fwhm_nm",
    # Control channel comparison
    "control_slope_5s_ru",
    "slope_diff_ru",
    # Quality
    "iq_level",
    # Classifier outputs
    "stage1_verdict",
    "bubble_detected",
    "positive_front",
    "negative_front",
    "auto_label",
    "manual_label",
]


def _fmt(value: object, ndigits: int) -> str | float:
    """Round a numeric value or return empty string for None."""
    if value is None:
        return ""
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return ""
