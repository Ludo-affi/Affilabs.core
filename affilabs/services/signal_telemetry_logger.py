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


def _get_telemetry_dir() -> Path:
    docs = Path.home() / "Documents"
    telemetry = docs / "Affilabs Data" / "telemetry"
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
    """Per-channel rolling buffers for p2p and slope computation."""

    def __init__(self) -> None:
        self._wavelengths: Deque[float] = deque(maxlen=_P2P_WINDOW)
        self._slope_pts: Deque[tuple[float, float]] = deque()  # (t, wl) — time-bounded

    def push(self, elapsed_s: float, wavelength: float) -> None:
        self._wavelengths.append(wavelength)
        self._slope_pts.append((elapsed_s, wavelength))
        # Prune slope window to last _SLOPE_WINDOW seconds
        cutoff = elapsed_s - _SLOPE_WINDOW
        while self._slope_pts and self._slope_pts[0][0] < cutoff:
            self._slope_pts.popleft()

    @property
    def p2p(self) -> float | None:
        if len(self._wavelengths) < 2:
            return None
        return max(self._wavelengths) - min(self._wavelengths)

    @property
    def slope(self) -> float | None:
        return _compute_slope(list(self._slope_pts))


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
    ) -> None:
        """Record one frame. Called from spectrum_helpers.py per processed frame.

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

            # --- Cycle context (best-effort; never raise) ---
            cycle_type  = ""
            cycle_elapsed_frac: float | None = None
            try:
                mw = getattr(app, "main_window", app)  # mixin pattern
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
                    iq_level_str = sensor_iq.iq_level.value if hasattr(sensor_iq.iq_level, "value") else str(sensor_iq.iq_level)
            except Exception:
                pass

            row: dict = {
                "session_id":           self._session_id,
                "timestamp_utc":        datetime.utcnow().isoformat(timespec="milliseconds"),
                "elapsed_s":            round(elapsed_s, 3),
                "channel":              ch,
                "cycle_type":           cycle_type,
                "cycle_elapsed_frac":   round(cycle_elapsed_frac, 4) if cycle_elapsed_frac is not None else "",
                "dip_position_nm":      round(wavelength, 4),
                "raw_intensity":        round(float(intensity), 1) if intensity is not None else "",
                "fwhm_nm":              _fmt(iq_metrics.get("fwhm"), 3),
                "dip_depth":            _fmt(iq_metrics.get("dip_depth"), 4),
                "p2p_5frame_nm":        _fmt(rolling.p2p, 5),
                "slope_5s_nm_per_s":    _fmt(rolling.slope, 6),
                "iq_level":             iq_level_str,
                # Phase 2+ — filled by classifier offline; null at runtime
                "classifier_top1":      "",
                "classifier_conf1":     "",
                "classifier_top2":      "",
                "classifier_conf2":     "",
                "manual_label":         "",
            }

            with self._write_lock:
                writer = self._csv_writers.get(ch)
                if writer is None:
                    return
                writer.writerow(row)
                self._row_count += 1
                # Flush periodically for recoverability without hurting throughput
                if self._row_count % _FLUSH_EVERY == 0:
                    self._csv_files[ch].flush()

                # Disk-space guard — check every 1000 rows
                if self._row_count % 1000 == 0 and not _has_enough_disk(self._telemetry_dir):
                    self._enabled = False

        except Exception:
            pass  # telemetry must never crash the acquisition thread


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_COLUMNS = [
    "session_id",
    "timestamp_utc",
    "elapsed_s",
    "channel",
    "cycle_type",
    "cycle_elapsed_frac",
    "dip_position_nm",
    "raw_intensity",
    "fwhm_nm",
    "dip_depth",
    "p2p_5frame_nm",
    "slope_5s_nm_per_s",
    "iq_level",
    "classifier_top1",
    "classifier_conf1",
    "classifier_top2",
    "classifier_conf2",
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
