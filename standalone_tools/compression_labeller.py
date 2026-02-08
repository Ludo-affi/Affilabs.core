#!/usr/bin/env python3
"""
AffiLabs — Compression Signal Labeller v3.1
============================================

**Device / sensor agnostic** live spectrum viewer with transmission mode
and real-time metric evolution.

All hardware-specific values (VID/PID, baud rate, LED brightness,
integration time, serial protocol) live in ``HardwareConfig``.
All analysis parameters (ROI, thresholds, scoring weights) live in
``AnalysisConfig``.  Both are plain dataclasses — override for any
spectrometer + controller combination.

Features
--------
* **Reference capture** — click 📷 to store the current (no-chip) spectrum
  as the baseline.  Saved to ``compression_ref.npy`` and auto-loaded on
  restart.
* **Transmission display** — when a reference exists the plot shows
  T = raw / reference (0–1 scale) instead of raw counts.
* **Rolling metric evolution** — three mini time-series below the main
  spectrum track dip wavelength, dip depth and FWHM over the last N
  readings so you can *watch* compression change in real time.
* **Edge-artifact guard** — dips in the first/last N pixels of the ROI
  are suppressed (boundary artefacts, not real resonance).

Usage
-----
    python compression_labeller.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DATACLASSES  (override for different hardware / sensors)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class HardwareConfig:
    """Device-specific hardware parameters.

    Override any field to adapt for a different spectrometer, controller,
    or LED topology.  The defaults match the Pico P4SPR + Ocean Optics
    USB4000 combination, but nothing is assumed by the rest of the code.
    """

    # ── Spectrometer ──────────────────────────────────────────────────────
    integration_time_ms: int = 5            # ms — set per spectrometer

    # ── Controller auto-detection (USB VID/PID) ───────────────────────────
    controller_vid: int | None = 0x2E8A     # None → skip auto-detect
    controller_pid: int | None = 0x000A     # None → skip auto-detect
    controller_port: str | None = None      # Explicit COM port overrides VID/PID
    controller_baud: int = 115200

    # ── LED configuration ─────────────────────────────────────────────────
    led_brightness: int = 25                # 0-255 (25 ≈ 10 %)
    num_led_channels: int = 4
    channel_labels: tuple[str, ...] = ("a", "b", "c", "d")

    def led_on_commands(self, brightness: int | None = None) -> list[str]:
        """Build serial commands to activate all LED channels.

        Override this method (or subclass) for controllers that use a
        different serial protocol.
        """
        b = max(0, min(255, brightness if brightness is not None else self.led_brightness))
        labels = ",".join(self.channel_labels)
        vals = ",".join([str(b)] * self.num_led_channels)
        return [f"lm:{labels}\n", f"batch:{vals}\n"]

    def led_off_commands(self) -> list[str]:
        """Build serial commands to deactivate all LEDs."""
        zeros = ",".join(["0"] * self.num_led_channels)
        return [f"batch:{zeros}\n"]


@dataclass
class AnalysisConfig:
    """Spectrum analysis parameters — adjust per sensor type.

    Every magic number that used to be a module-level constant now lives
    here so it can be overridden without editing source code.
    """

    # ── Region of interest for dip search ─────────────────────────────────
    roi_wl_min: float = 550.0               # nm — start of search window
    roi_wl_max: float = 700.0               # nm — end of search window

    # ── Dip detection thresholds ──────────────────────────────────────────
    min_dip_depth: float = 0.02             # fractional depth to count as a dip
    min_dip_snr: float = 2.0                # minimum SNR to count as a dip

    # ── Edge-artifact guard ───────────────────────────────────────────────
    edge_guard_pixels: int = 3              # ignore dips in first / last N px

    # ── Baseline / noise estimation ───────────────────────────────────────
    baseline_top_fraction: float = 0.30     # use top 30 % of signal for baseline
    noise_estimation_pixels: int = 20       # first N pixels of ROI for noise σ

    # ── Quality scoring ───────────────────────────────────────────────────
    depth_full_marks: float = 0.30          # depth at which score maxes out
    snr_full_marks: float = 20.0            # SNR at which score maxes out
    fwhm_ideal_nm: float = 30.0             # ideal FWHM centre
    fwhm_range: tuple[float, float] = (5.0, 80.0)   # valid FWHM band
    fwhm_tolerance_nm: float = 50.0         # how far from ideal before zero
    dip_wl_valid_range: tuple[float, float] = (560.0, 690.0)

    # ── Transmission computation ──────────────────────────────────────────
    reference_floor_counts: float = 10.0    # floor for div-by-zero guard


# ═══════════════════════════════════════════════════════════════════════════════
# UI / PERSISTENCE CONSTANTS  (not device-specific)
# ═══════════════════════════════════════════════════════════════════════════════

FONT_SYSTEM = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif"

# Plot styling
LIVE_CURVE_COLOR = "#007AFF"     # raw spectrum (blue)
TRANS_CURVE_COLOR = "#34C759"    # transmission spectrum (green)
EVO_COLOR_MID_LOW = "#FF3B30"     # mid/low ratio (main training metric)
EVO_COLOR_MID_HIGH = "#007AFF"    # mid/high ratio
EVO_COLOR_DIP_WL = "#AF52DE"      # dip wavelength

# Compression labels
COMPRESSION_LABELS = [
    "no_chip",
    "chip_no_compression",
    "too_little_compression",
    "good_compression",
    "too_much_compression",
    "over_compressed",
    "leak_detected",
]

# Persistence paths (next to this script)
_SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = _SCRIPT_DIR / "compression_training_data.json"
REF_FILE = _SCRIPT_DIR / "compression_ref.npy"

# Rolling evolution buffer
EVOLUTION_BUFFER_SIZE = 300


# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE LINK  (device-agnostic via HardwareConfig)
# ═══════════════════════════════════════════════════════════════════════════════


class HardwareLink:
    """Thin wrapper around seabreeze + serial for live spectrum acquisition.

    All device-specific values come from ``HardwareConfig`` — nothing is
    hardcoded.  Pass a custom config for a different spectrometer or
    controller::

        cfg = HardwareConfig(
            integration_time_ms=10,
            controller_vid=0x1234,
            controller_pid=0x5678,
            controller_baud=9600,
            led_brightness=50,
        )
        hw = HardwareLink(cfg)
    """

    def __init__(self, config: HardwareConfig | None = None) -> None:
        self.config = config or HardwareConfig()
        self.spec = None
        self.serial_conn = None
        self.wavelengths: np.ndarray | None = None

    # ── connection ────────────────────────────────────────────────────────

    def connect(self) -> tuple[bool, str]:
        """Connect spectrometer + controller."""
        cfg = self.config

        # ── Spectrometer (seabreeze) ──────────────────────────────────────
        try:
            # libusb backend init (Windows needs explicit DLL path)
            try:
                import sys, os
                sys.path.insert(0, os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..")
                ))
                from affilabs.utils.libusb_init import get_libusb_backend
                _backend = get_libusb_backend()
                if _backend:
                    import usb.core
                    _orig_find = usb.core.find
                    def _patched_find(*a, **kw):
                        if "backend" not in kw:
                            kw["backend"] = _backend
                        return _orig_find(*a, **kw)
                    usb.core.find = _patched_find
            except Exception:
                pass  # libusb init is best-effort

            # Must select backend BEFORE importing spectrometers
            import seabreeze
            seabreeze.use("pyseabreeze")
            from seabreeze.spectrometers import Spectrometer, list_devices

            devices = list_devices()
            if not devices:
                return False, "No spectrometer found"
            self.spec = Spectrometer(devices[0])
            self.spec.integration_time_micros(cfg.integration_time_ms * 1000)
            self.wavelengths = self.spec.wavelengths()
        except Exception as exc:
            return False, f"Spectrometer error: {exc}"

        # ── Controller (serial) ───────────────────────────────────────────
        try:
            import serial
            import serial.tools.list_ports

            # Explicit port takes priority
            if cfg.controller_port:
                self.serial_conn = serial.Serial(
                    cfg.controller_port, cfg.controller_baud, timeout=1,
                )
                time.sleep(0.3)
                return True, f"Connected ({cfg.controller_port})"

            # Auto-detect by VID/PID
            if cfg.controller_vid is not None and cfg.controller_pid is not None:
                for p in serial.tools.list_ports.comports():
                    if p.vid == cfg.controller_vid and p.pid == cfg.controller_pid:
                        self.serial_conn = serial.Serial(
                            p.device, cfg.controller_baud, timeout=1,
                        )
                        time.sleep(0.3)
                        return True, f"Connected ({p.device})"
                return False, (
                    f"Controller not found "
                    f"(VID {cfg.controller_vid:#06X} / "
                    f"PID {cfg.controller_pid:#06X})"
                )

            return False, "No controller_port or VID/PID configured"
        except Exception as exc:
            return False, f"Serial error: {exc}"

    def _cmd(self, cmd: str) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(cmd.encode())
            time.sleep(0.02)

    # ── LED control (protocol from HardwareConfig) ────────────────────────

    def leds_on(self, brightness: int | None = None) -> None:
        """Turn on all LED channels using config-defined protocol."""
        for cmd in self.config.led_on_commands(brightness):
            self._cmd(cmd)

    def leds_off(self) -> None:
        """Turn off all LEDs using config-defined protocol."""
        for cmd in self.config.led_off_commands():
            self._cmd(cmd)

    # ── acquisition ───────────────────────────────────────────────────────

    def read_live(self) -> np.ndarray | None:
        if self.spec is None:
            return None
        return self.spec.intensities()

    # ── cleanup ───────────────────────────────────────────────────────────

    def disconnect(self) -> None:
        try:
            self.leds_off()
        except Exception:
            pass
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        if self.spec:
            try:
                self.spec.close()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS  (all thresholds from AnalysisConfig)
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_spectrum(
    wavelengths: np.ndarray,
    signal: np.ndarray,
    config: AnalysisConfig | None = None,
) -> dict:
    """Analyse a 1-D signal (raw counts OR transmission) within the ROI.

    Works identically for raw and transmission — the relative metrics
    (dip_depth, FWHM, SNR) are scale-invariant.

    All thresholds and scoring parameters come from ``config``.
    """
    cfg = config or AnalysisConfig()

    roi_mask = (wavelengths >= cfg.roi_wl_min) & (wavelengths <= cfg.roi_wl_max)
    wl_roi = wavelengths[roi_mask]
    sig_roi = signal[roi_mask]

    if len(sig_roi) < 10:
        return {"has_dip": False, "mean_intensity": 0}

    mean_val = float(np.mean(sig_roi))

    # Baseline = mean of top N % brightest pixels in ROI
    cutoff_idx = int(len(sig_roi) * (1.0 - cfg.baseline_top_fraction))
    sorted_vals = np.sort(sig_roi)
    top_slice = sorted_vals[cutoff_idx:]
    baseline = float(np.mean(top_slice)) if len(top_slice) else mean_val

    # Noise — σ of the first N pixels in the ROI
    n_noise = min(cfg.noise_estimation_pixels, len(sig_roi))
    noise_std = float(np.std(sig_roi[:n_noise])) if n_noise >= 2 else 1e-9

    # Find dip (minimum)
    min_idx = int(np.argmin(sig_roi))
    min_val = float(sig_roi[min_idx])
    dip_wl = float(wl_roi[min_idx])

    # ── Edge-artifact guard ───────────────────────────────────────────
    guard = cfg.edge_guard_pixels
    if min_idx < guard or min_idx > len(sig_roi) - guard - 1:
        return {
            "has_dip": False,
            "mean_intensity": mean_val,
            "baseline_mean": baseline,
            "dip_wavelength": None,
            "dip_depth": 0,
            "dip_fwhm": None,
            "snr": 0,
            "quality_score": 0,
        }

    depth = (baseline - min_val) / baseline if baseline > 0 else 0

    # SNR
    snr = (baseline - min_val) / noise_std if noise_std > 1e-9 else 0

    # FWHM
    half_height = (baseline + min_val) / 2
    fwhm = None
    try:
        left = np.where(sig_roi[:min_idx] > half_height)[0]
        right = np.where(sig_roi[min_idx:] > half_height)[0]
        if len(left) and len(right):
            wl_left = float(wl_roi[left[-1]])
            wl_right = float(wl_roi[min_idx + right[0]])
            fwhm = wl_right - wl_left
    except Exception:
        pass

    has_dip = depth > cfg.min_dip_depth and snr > cfg.min_dip_snr

    # ── Quality score (0-100) — all weights from config ───────────────
    score = 0.0
    if has_dip:
        # Depth component (30 pts)
        depth_s = min(depth / cfg.depth_full_marks, 1.0) * 30

        # SNR component (30 pts)
        snr_s = min(snr / cfg.snr_full_marks, 1.0) * 30

        # FWHM component (20 pts)
        fwhm_s = 0.0
        fwhm_lo, fwhm_hi = cfg.fwhm_range
        if fwhm and fwhm_lo < fwhm < fwhm_hi:
            fwhm_s = (1 - abs(fwhm - cfg.fwhm_ideal_nm) / cfg.fwhm_tolerance_nm) * 20

        # Wavelength validity (20 pts)
        wl_lo, wl_hi = cfg.dip_wl_valid_range
        wl_score = 20.0 if wl_lo < dip_wl < wl_hi else 0.0

        score = depth_s + snr_s + fwhm_s + wl_score

    # ── Band-ratio metrics (self-normalizing, always available) ───────
    bl, bm, bh = cfg.band_low, cfg.band_mid, cfg.band_high
    mask_low = (wavelengths >= bl[0]) & (wavelengths <= bl[1])
    mask_mid = (wavelengths >= bm[0]) & (wavelengths <= bm[1])
    mask_high = (wavelengths >= bh[0]) & (wavelengths <= bh[1])

    i_low = float(np.mean(signal[mask_low])) if np.any(mask_low) else 1.0
    i_mid = float(np.mean(signal[mask_mid])) if np.any(mask_mid) else 1.0
    i_high = float(np.mean(signal[mask_high])) if np.any(mask_high) else 1.0

    mid_low_ratio = i_mid / i_low if i_low > 0 else 1.0
    mid_high_ratio = i_mid / i_high if i_high > 0 else 1.0

    return {
        "has_dip": has_dip,
        "mean_intensity": mean_val,
        "baseline_mean": baseline,
        "min_intensity": min_val,
        "dip_wavelength": dip_wl if has_dip else None,
        "dip_depth": depth,
        "dip_fwhm": fwhm,
        "snr": snr,
        "quality_score": max(0, min(100, score)),
        # Band ratios (always valid, no reference needed)
        "mid_low_ratio": mid_low_ratio,
        "mid_high_ratio": mid_high_ratio,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def save_reference(spectrum: np.ndarray, path: Path = REF_FILE) -> None:
    """Persist the no-chip reference spectrum to disk."""
    np.save(path, spectrum)


def load_reference(path: Path = REF_FILE) -> np.ndarray | None:
    """Load previously saved reference, or return None."""
    if path.exists():
        return np.load(path)
    return None


def compute_transmission(
    raw: np.ndarray,
    reference: np.ndarray,
    floor: float = 10.0,
) -> np.ndarray:
    """T = raw / reference, clamped to avoid div-by-zero artefacts.

    ``floor`` is the minimum reference value — pixels below this are
    floored to prevent noise blow-up.  Configurable via
    ``AnalysisConfig.reference_floor_counts``.
    """
    ref_safe = np.where(reference > floor, reference, floor)
    return raw / ref_safe


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STORE  (JSON persistence)
# ═══════════════════════════════════════════════════════════════════════════════


def load_dataset(path: Path = DATA_FILE) -> list[dict]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_dataset(dataset: list[dict], path: Path = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, default=str)


def add_snapshot(
    dataset: list[dict],
    label: str,
    note: str,
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    analysis: dict,
    transmission: np.ndarray | None = None,
) -> dict:
    entry = {
        "id": len(dataset) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "note": note,
        "wavelengths": wavelengths.tolist(),
        "intensity": spectrum.tolist(),
        "analysis": {
            k: v for k, v in analysis.items() if not isinstance(v, np.ndarray)
        },
    }
    if transmission is not None:
        entry["transmission"] = transmission.tolist()
    dataset.append(entry)
    save_dataset(dataset)
    return entry


# ═══════════════════════════════════════════════════════════════════════════════
# ACQUISITION WORKER
# ═══════════════════════════════════════════════════════════════════════════════


class AcquisitionWorker(QThread):
    """Reads raw spectra in a background thread at ~100 Hz."""

    spectrum_ready = Signal(np.ndarray)
    error = Signal(str)

    def __init__(self, hw: HardwareLink) -> None:
        super().__init__()
        self.hw = hw
        self._running = True

    def stop(self) -> None:
        self._running = False
        self.wait(2000)

    def run(self) -> None:
        while self._running:
            try:
                data = self.hw.read_live()
                if data is not None:
                    self.spectrum_ready.emit(data)
            except Exception as e:
                self.error.emit(str(e))
                time.sleep(1)
            time.sleep(0.01)  # ~100 Hz max refresh


# ═══════════════════════════════════════════════════════════════════════════════
# GUI — LIVE PLOT WIDGET
# ═══════════════════════════════════════════════════════════════════════════════


class LivePlotWidget(QWidget):
    """Live spectrum plot — shows raw OR transmission with analysis overlay."""

    def __init__(self, analysis_cfg: AnalysisConfig, parent=None) -> None:
        super().__init__(parent)
        self._acfg = analysis_cfg
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Wavelength", units="nm")
        self.plot_widget.setLabel("left", "Intensity", units="counts")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setMouseEnabled(x=True, y=True)
        layout.addWidget(self.plot_widget)

        # Main live curve
        self.curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen(LIVE_CURVE_COLOR, width=2), name="Live",
        )

        # Vertical dip marker
        self.dip_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen("#FF3B30", width=2, style=Qt.PenStyle.DashLine),
            movable=False,
        )
        self.dip_line.setVisible(False)
        self.plot_widget.addItem(self.dip_line)

        # FWHM region shading
        self.fwhm_region = pg.LinearRegionItem(
            values=[0, 0], movable=False,
            brush=pg.mkBrush(255, 59, 48, 30),
        )
        self.fwhm_region.setVisible(False)
        self.fwhm_region.setZValue(-5)
        self.plot_widget.addItem(self.fwhm_region)

        # ROI shading (analysis window — from config, not hardcoded)
        self.roi_region = pg.LinearRegionItem(
            values=[analysis_cfg.roi_wl_min, analysis_cfg.roi_wl_max],
            movable=False,
            brush=pg.mkBrush(0, 122, 255, 15),
        )
        self.roi_region.setZValue(-10)
        self.plot_widget.addItem(self.roi_region)

        # Dip label
        self.dip_text = pg.TextItem("", color="#FF3B30", anchor=(0, 1))
        self.dip_text.setFont(
            pg.QtGui.QFont("Segoe UI", 10, pg.QtGui.QFont.Weight.Bold)
        )
        self.plot_widget.addItem(self.dip_text)
        self.dip_text.setVisible(False)

        # Mode label (Raw / Transmission) — top-right corner
        self.mode_text = pg.TextItem(
            "RAW", color="#86868B", anchor=(1, 0),
        )
        self.mode_text.setFont(
            pg.QtGui.QFont("Segoe UI", 11, pg.QtGui.QFont.Weight.Bold)
        )
        self.plot_widget.addItem(self.mode_text)
        self.mode_text.setPos(analysis_cfg.roi_wl_max, 0)

    def set_transmission_mode(self, enabled: bool) -> None:
        """Switch between raw and transmission display."""
        if enabled:
            self.curve.setPen(pg.mkPen(TRANS_CURVE_COLOR, width=2))
            self.plot_widget.setLabel("left", "Transmission")
            self.mode_text.setText("TRANSMISSION")
            self.mode_text.setColor("#34C759")
        else:
            self.curve.setPen(pg.mkPen(LIVE_CURVE_COLOR, width=2))
            self.plot_widget.setLabel("left", "Intensity", units="counts")
            self.mode_text.setText("RAW")
            self.mode_text.setColor("#86868B")

    def update_data(
        self,
        wavelengths: np.ndarray,
        signal: np.ndarray,
        analysis: dict | None = None,
    ) -> None:
        wl = wavelengths[:len(signal)]
        self.curve.setData(wl, signal)

        # Pin mode label at the top-right of the ROI (fixed data coords)
        roi_max = self._acfg.roi_wl_max
        sig_max = float(np.max(signal)) if len(signal) else 1.0
        self.mode_text.setPos(roi_max, sig_max)

        if analysis and analysis.get("has_dip") and analysis.get("dip_wavelength"):
            dip_wl = analysis["dip_wavelength"]
            self.dip_line.setValue(dip_wl)
            self.dip_line.setVisible(True)

            fwhm = analysis.get("dip_fwhm")
            if fwhm and fwhm > 0:
                half = fwhm / 2
                self.fwhm_region.setRegion([dip_wl - half, dip_wl + half])
                self.fwhm_region.setVisible(True)
            else:
                self.fwhm_region.setVisible(False)

            depth = analysis.get("dip_depth", 0)
            snr = analysis.get("snr", 0)
            score = analysis.get("quality_score", 0)
            self.dip_text.setText(
                f"Dip: {dip_wl:.1f} nm  |  Depth: {depth:.3f}  |  "
                f"SNR: {snr:.1f}  |  Score: {score:.0f}"
            )
            self.dip_text.setPos(dip_wl + 5, analysis.get("min_intensity", 0))
            self.dip_text.setVisible(True)
        else:
            self.dip_line.setVisible(False)
            self.fwhm_region.setVisible(False)
            self.dip_text.setVisible(False)


# ═══════════════════════════════════════════════════════════════════════════════
# GUI — METRIC EVOLUTION WIDGET (rolling time-series)
# ═══════════════════════════════════════════════════════════════════════════════


class MetricEvolutionWidget(QWidget):
    """Three stacked mini-plots showing the key compression metrics
    evolving over time — lets the user *see* compression changing live.

    Tracks:
        1. **mid/low ratio** — the main compression indicator.
           Drops from ~1.0 (no chip) toward ~0.80 (good compression).
           If it climbs back up, you've over-compressed.
        2. **mid/high ratio** — direction indicator.
           Drops when dip is centered; rises when dip shifts red.
        3. **Dip wavelength** — red-shifts with compression.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._buffers: dict[str, deque] = {
            "mid_low":  deque(maxlen=EVOLUTION_BUFFER_SIZE),
            "mid_high": deque(maxlen=EVOLUTION_BUFFER_SIZE),
            "dip_wl":   deque(maxlen=EVOLUTION_BUFFER_SIZE),
        }

        # ── mid/low ratio (PRIMARY training metric) ───────────────────────
        self.pw_ml = pg.PlotWidget()
        self.pw_ml.setLabel("left", "mid/low")
        self.pw_ml.setFixedHeight(110)
        self.pw_ml.showGrid(y=True, alpha=0.2)
        self.pw_ml.hideAxis("bottom")
        # Target zone shading: ~0.78 – 0.82 = good compression
        self.target_region = pg.LinearRegionItem(
            values=[0.78, 0.82], orientation="horizontal",
            movable=False, brush=pg.mkBrush(52, 199, 89, 35),
        )
        self.target_region.setZValue(-10)
        self.pw_ml.addItem(self.target_region)
        self.curve_ml = self.pw_ml.plot(
            [], [], pen=pg.mkPen(EVO_COLOR_MID_LOW, width=2),
        )
        layout.addWidget(self.pw_ml)

        # ── mid/high ratio ────────────────────────────────────────────────
        self.pw_mh = pg.PlotWidget()
        self.pw_mh.setLabel("left", "mid/high")
        self.pw_mh.setFixedHeight(100)
        self.pw_mh.showGrid(y=True, alpha=0.2)
        self.pw_mh.hideAxis("bottom")
        self.curve_mh = self.pw_mh.plot(
            [], [], pen=pg.mkPen(EVO_COLOR_MID_HIGH, width=2),
        )
        layout.addWidget(self.pw_mh)

        # ── Dip wavelength ────────────────────────────────────────────────
        self.pw_dip = pg.PlotWidget()
        self.pw_dip.setLabel("left", "Dip (nm)")
        self.pw_dip.setLabel("bottom", "Sample #")
        self.pw_dip.setFixedHeight(100)
        self.pw_dip.showGrid(y=True, alpha=0.2)
        self.curve_dip = self.pw_dip.plot(
            [], [], pen=pg.mkPen(EVO_COLOR_DIP_WL, width=2),
        )
        layout.addWidget(self.pw_dip)

        # Link x-axes for synchronized scrolling
        self.pw_mh.setXLink(self.pw_ml)
        self.pw_dip.setXLink(self.pw_ml)

    def push(self, analysis: dict) -> None:
        """Append one reading to the rolling buffers and update plots."""
        ml = analysis.get("mid_low_ratio", np.nan)
        mh = analysis.get("mid_high_ratio", np.nan)
        dip_wl = analysis.get("dip_wavelength")

        self._buffers["mid_low"].append(ml)
        self._buffers["mid_high"].append(mh)
        self._buffers["dip_wl"].append(dip_wl if dip_wl else np.nan)

        x = np.arange(len(self._buffers["mid_low"]))

        self.curve_ml.setData(x, np.array(self._buffers["mid_low"], dtype=float))
        self.curve_mh.setData(x, np.array(self._buffers["mid_high"], dtype=float))
        self.curve_dip.setData(x, np.array(self._buffers["dip_wl"], dtype=float))

    def clear(self) -> None:
        """Reset all buffers."""
        for buf in self._buffers.values():
            buf.clear()
        self.curve_ml.setData([], [])
        self.curve_mh.setData([], [])
        self.curve_dip.setData([], [])


# ═══════════════════════════════════════════════════════════════════════════════
# GUI — ANALYSIS PANEL
# ═══════════════════════════════════════════════════════════════════════════════


class AnalysisPanel(QWidget):
    """Shows live analysis metrics for the current spectrum."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        title = QLabel("📊 Live Analysis")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; font-family: {FONT_SYSTEM};"
        )
        layout.addWidget(title)

        # Mode indicator
        self.mode_label = QLabel("Mode: RAW")
        self.mode_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #86868B; "
            f"font-family: {FONT_SYSTEM};"
        )
        layout.addWidget(self.mode_label)

        # Metric rows
        self._labels: dict[str, QLabel] = {}
        metrics = [
            ("mid_low_ratio", "Mid/Low Ratio"),
            ("mid_high_ratio", "Mid/High Ratio"),
            ("dip_wavelength", "Dip Position (nm)"),
            ("dip_depth", "Dip Depth"),
            ("dip_fwhm", "FWHM (nm)"),
            ("snr", "SNR"),
            ("quality_score", "Quality Score"),
        ]
        for key, label_text in metrics:
            row = QHBoxLayout()
            name_lbl = QLabel(label_text)
            name_lbl.setStyleSheet(
                f"font-size: 12px; color: #86868B; font-family: {FONT_SYSTEM};"
            )
            name_lbl.setFixedWidth(140)
            row.addWidget(name_lbl)

            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 700; font-family: {FONT_SYSTEM};"
            )
            row.addWidget(val_lbl)
            row.addStretch()
            layout.addLayout(row)
            self._labels[key] = val_lbl

        # Quality indicator bar
        self.quality_bar = QLabel("")
        self.quality_bar.setFixedHeight(8)
        self.quality_bar.setStyleSheet(
            "background: #E5E5EA; border-radius: 4px;"
        )
        layout.addWidget(self.quality_bar)

        # Status text
        self.status_text = QLabel("Waiting for data...")
        self.status_text.setStyleSheet(
            f"font-size: 13px; font-weight: 600; font-family: {FONT_SYSTEM};"
        )
        self.status_text.setWordWrap(True)
        layout.addWidget(self.status_text)

        layout.addStretch()

    def set_mode(self, transmission: bool) -> None:
        """Update the mode indicator label."""
        if transmission:
            self.mode_label.setText("Mode: TRANSMISSION")
            self.mode_label.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: #34C759; "
                f"font-family: {FONT_SYSTEM};"
            )
        else:
            self.mode_label.setText("Mode: RAW")
            self.mode_label.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: #86868B; "
                f"font-family: {FONT_SYSTEM};"
            )

    def update_analysis(self, a: dict) -> None:
        # Band ratios (always available, the key training metrics)
        ml = a.get("mid_low_ratio", 1.0)
        mh = a.get("mid_high_ratio", 1.0)
        self._labels["mid_low_ratio"].setText(f"{ml:.3f}")
        self._labels["mid_high_ratio"].setText(f"{mh:.3f}")

        # Color mid/low by zone
        if ml < 0.83:
            ml_color = "#34C759"  # green = good compression zone
        elif ml < 0.90:
            ml_color = "#FF9500"  # orange = getting there
        else:
            ml_color = "#8E8E93"  # gray = no/little compression
        self._labels["mid_low_ratio"].setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {ml_color}; "
            f"font-family: {FONT_SYSTEM};"
        )

        dip_wl = a.get("dip_wavelength")
        self._labels["dip_wavelength"].setText(
            f"{dip_wl:.1f}" if dip_wl else "--"
        )

        depth = a.get("dip_depth")
        self._labels["dip_depth"].setText(
            f"{depth:.4f}" if depth else "--"
        )

        fwhm = a.get("dip_fwhm")
        self._labels["dip_fwhm"].setText(f"{fwhm:.1f}" if fwhm else "--")

        snr = a.get("snr", 0)
        self._labels["snr"].setText(f"{snr:.1f}")

        score = a.get("quality_score", 0)
        self._labels["quality_score"].setText(f"{score:.0f} / 100")

        # Color coding
        if score >= 70:
            color = "#34C759"
            status = "✅ Good compression — clean resonance dip"
        elif score >= 40:
            color = "#FF9500"
            status = "⚠️ Marginal — dip visible but needs improvement"
        elif a.get("has_dip"):
            color = "#FF3B30"
            status = "❌ Poor — dip present but too weak/broad"
        else:
            color = "#8E8E93"
            status = "🔍 No resonance dip detected"

        self._labels["quality_score"].setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {color}; "
            f"font-family: {FONT_SYSTEM};"
        )
        self.quality_bar.setStyleSheet(
            f"background: {color}; border-radius: 4px;"
        )
        self.status_text.setText(status)
        self.status_text.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {color}; "
            f"font-family: {FONT_SYSTEM};"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GUI — LABELLING PANEL
# ═══════════════════════════════════════════════════════════════════════════════


class LabellingPanel(QWidget):
    """Buttons for labelling + notes + snapshot log."""

    snapshot_requested = Signal(str, str)  # (label, note)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Title
        title = QLabel("🏷️ Label & Snapshot")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; font-family: {FONT_SYSTEM};"
        )
        layout.addWidget(title)

        # Label selector
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Label:"))
        self.label_combo = QComboBox()
        self.label_combo.addItems(COMPRESSION_LABELS)
        self.label_combo.setCurrentText("good_compression")
        self.label_combo.setStyleSheet(
            f"font-size: 12px; font-family: {FONT_SYSTEM}; padding: 4px;"
        )
        label_row.addWidget(self.label_combo, 1)
        layout.addLayout(label_row)

        # Custom note
        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Note:"))
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional description...")
        self.note_input.setStyleSheet(
            f"font-size: 12px; font-family: {FONT_SYSTEM}; padding: 4px;"
        )
        note_row.addWidget(self.note_input, 1)
        layout.addLayout(note_row)

        # ── Quick-label buttons ───────────────────────────────────────────
        btn_group = QGroupBox("Quick Label (click = snapshot + label)")
        btn_group.setStyleSheet(
            f"QGroupBox {{ font-size: 11px; font-weight: 600; "
            f"font-family: {FONT_SYSTEM}; }}"
        )
        btn_layout = QGridLayout()
        btn_layout.setSpacing(4)

        quick_labels = [
            ("🚫 No Chip", "no_chip", "#8E8E93"),
            ("📦 Chip, No Compression", "chip_no_compression", "#5856D6"),
            ("⬇️ Too Little", "too_little_compression", "#FF9500"),
            ("✅ Good Compression", "good_compression", "#34C759"),
            ("⬆️ Too Much", "too_much_compression", "#FF3B30"),
            ("💀 Over-Compressed", "over_compressed", "#AF52DE"),
            ("💧 Leak", "leak_detected", "#00C7BE"),
        ]

        for i, (text, label, color) in enumerate(quick_labels):
            btn = QPushButton(text)
            btn.setFixedHeight(36)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color}; color: white; border: none;"
                f"  border-radius: 6px; padding: 4px 8px;"
                f"  font-size: 12px; font-weight: 600;"
                f"  font-family: {FONT_SYSTEM};"
                f"}}"
                f"QPushButton:hover {{ opacity: 0.9; }}"
                f"QPushButton:pressed {{ opacity: 0.7; }}"
            )
            btn.clicked.connect(
                lambda checked, l=label: self._quick_snapshot(l)
            )
            row, col = divmod(i, 2)
            btn_layout.addWidget(btn, row, col)

        # Manual snapshot button
        snap_btn = QPushButton("📸 Snapshot (use combo label)")
        snap_btn.setFixedHeight(36)
        snap_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #007AFF; color: white; border: none;"
            f"  border-radius: 6px; padding: 4px 8px;"
            f"  font-size: 12px; font-weight: 600;"
            f"  font-family: {FONT_SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #0066DD; }}"
        )
        snap_btn.clicked.connect(self._manual_snapshot)
        btn_layout.addWidget(snap_btn, len(quick_labels) // 2 + 1, 0, 1, 2)

        btn_group.setLayout(btn_layout)
        layout.addWidget(btn_group)

        # ── Snapshot log ──────────────────────────────────────────────────
        log_label = QLabel("📋 Snapshot Log")
        log_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; font-family: {FONT_SYSTEM};"
        )
        layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        self.log.setStyleSheet(
            "font-size: 11px; font-family: 'Consolas', 'Courier New', monospace;"
            "background: #1D1D1F; color: #F5F5F7; border-radius: 6px; padding: 6px;"
        )
        layout.addWidget(self.log)

        # ── Dataset stats ─────────────────────────────────────────────────
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            f"font-size: 11px; color: #86868B; font-family: {FONT_SYSTEM};"
        )
        layout.addWidget(self.stats_label)

        layout.addStretch()

    def _quick_snapshot(self, label: str) -> None:
        note = self.note_input.text().strip()
        self.snapshot_requested.emit(label, note)
        self.note_input.clear()

    def _manual_snapshot(self) -> None:
        label = self.label_combo.currentText()
        note = self.note_input.text().strip()
        self.snapshot_requested.emit(label, note)
        self.note_input.clear()

    def add_log_entry(self, entry: dict) -> None:
        ts = entry["timestamp"][:19].replace("T", " ")
        label = entry["label"]
        note = entry.get("note", "")
        eid = entry["id"]

        a = entry.get("analysis", {})
        score = a.get("quality_score", 0)
        snr = a.get("snr", 0)
        dip = a.get("dip_wavelength", "—")
        depth = a.get("dip_depth", 0)
        note_str = f"  [{note}]" if note else ""
        has_trans = "transmission" in entry

        self.log.append(
            f"#{eid} [{ts}]  {label}  |  "
            f"Score:{score:.0f}  SNR:{snr:.1f}  "
            f"Dip:{dip}  Depth:{depth:.3f}"
            f"{'  [T]' if has_trans else ''}{note_str}"
        )

    def update_stats(self, dataset: list[dict]) -> None:
        if not dataset:
            self.stats_label.setText("No snapshots yet")
            return
        counts: dict[str, int] = {}
        for d in dataset:
            lbl = d["label"]
            counts[lbl] = counts.get(lbl, 0) + 1
        parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
        self.stats_label.setText(
            f"Total: {len(dataset)} snapshots  |  " + "  ".join(parts)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════


class CompressionLabellerWindow(QMainWindow):
    """Main window — live spectrum + transmission + real-time evolution.

    Accepts ``HardwareConfig`` and ``AnalysisConfig`` so every device-
    specific value is injectable from the outside::

        hw_cfg = HardwareConfig(controller_port="COM7", led_brightness=50)
        an_cfg = AnalysisConfig(roi_wl_min=500, roi_wl_max=750)
        window = CompressionLabellerWindow(hw_cfg, an_cfg)
    """

    def __init__(
        self,
        hw_config: HardwareConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("AffiLabs — Compression Signal Labeller")
        self.setGeometry(80, 80, 1500, 900)
        self.setStyleSheet("background: #F8F9FA;")

        self._hw_cfg = hw_config or HardwareConfig()
        self._an_cfg = analysis_config or AnalysisConfig()

        self.hw = HardwareLink(self._hw_cfg)
        self.dataset = load_dataset()
        self.worker: AcquisitionWorker | None = None
        self._latest_raw: np.ndarray | None = None
        self._latest_analysis: dict = {}

        # Reference spectrum (no-chip baseline) — auto-load from disk
        self._reference: np.ndarray | None = load_reference()

        self._build_ui()
        self._apply_reference_mode()
        self._connect_hw()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Top status bar ────────────────────────────────────────────────
        status_row = QHBoxLayout()

        self.status_label = QLabel("⏳ Connecting to hardware...")
        self.status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: #FF9500; "
            f"font-family: {FONT_SYSTEM};"
        )
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        # Reference capture button
        self.ref_btn = QPushButton("📷 Capture Reference")
        self.ref_btn.setFixedHeight(28)
        self.ref_btn.setToolTip(
            "Capture current spectrum as no-chip reference for transmission mode"
        )
        self.ref_btn.setStyleSheet(
            f"QPushButton {{ background: #5856D6; color: white; border: none;"
            f"border-radius: 6px; padding: 2px 12px; font-size: 11px;"
            f"font-weight: 600; font-family: {FONT_SYSTEM}; }}"
            f"QPushButton:hover {{ background: #4B49B0; }}"
        )
        self.ref_btn.clicked.connect(self._capture_reference)
        status_row.addWidget(self.ref_btn)

        # Clear reference button
        self.clear_ref_btn = QPushButton("✖ Clear Ref")
        self.clear_ref_btn.setFixedHeight(28)
        self.clear_ref_btn.setStyleSheet(
            f"QPushButton {{ background: #8E8E93; color: white; border: none;"
            f"border-radius: 6px; padding: 2px 12px; font-size: 11px;"
            f"font-weight: 600; font-family: {FONT_SYSTEM}; }}"
            f"QPushButton:hover {{ background: #636366; }}"
        )
        self.clear_ref_btn.clicked.connect(self._clear_reference)
        status_row.addWidget(self.clear_ref_btn)

        # Reconnect button
        self.reconnect_btn = QPushButton("🔄 Reconnect")
        self.reconnect_btn.setFixedHeight(28)
        self.reconnect_btn.setStyleSheet(
            f"QPushButton {{ background: #007AFF; color: white; border: none;"
            f"border-radius: 6px; padding: 2px 12px; font-size: 11px;"
            f"font-weight: 600; font-family: {FONT_SYSTEM}; }}"
            f"QPushButton:hover {{ background: #0066DD; }}"
        )
        self.reconnect_btn.clicked.connect(self._connect_hw)
        status_row.addWidget(self.reconnect_btn)

        main_layout.addLayout(status_row)

        # ── Horizontal splitter: left (plots) | right (panels) ────────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: spectrum + evolution plots
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Main spectrum plot (receives AnalysisConfig for ROI display)
        self.live_plot = LivePlotWidget(self._an_cfg)
        left_layout.addWidget(self.live_plot, stretch=3)

        # Evolution header
        evo_label = QLabel("📈 Metric Evolution (real-time)")
        evo_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: #86868B; "
            f"font-family: {FONT_SYSTEM}; margin-top: 4px;"
        )
        left_layout.addWidget(evo_label)

        # Evolution plots (dip position, depth, FWHM over time)
        self.evolution = MetricEvolutionWidget()
        left_layout.addWidget(self.evolution, stretch=2)

        h_splitter.addWidget(left_widget)

        # Right side: analysis + labelling in scroll area
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self.analysis_panel = AnalysisPanel()
        right_layout.addWidget(self.analysis_panel)

        self.labelling_panel = LabellingPanel()
        self.labelling_panel.snapshot_requested.connect(self._take_snapshot)
        self.labelling_panel.update_stats(self.dataset)
        right_layout.addWidget(self.labelling_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right_panel)
        scroll.setMinimumWidth(380)

        h_splitter.addWidget(scroll)
        h_splitter.setStretchFactor(0, 3)
        h_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(h_splitter)

    # ── Reference management ─────────────────────────────────────────────

    def _capture_reference(self) -> None:
        """Store the current raw spectrum as the no-chip reference."""
        if self._latest_raw is None:
            QMessageBox.warning(
                self, "No Data",
                "No live spectrum available yet. Wait for data to appear "
                "before capturing a reference.",
            )
            return

        self._reference = self._latest_raw.copy()
        save_reference(self._reference)
        self._apply_reference_mode()
        self.evolution.clear()
        self.status_label.setText(
            "📷 Reference captured — switched to TRANSMISSION mode"
        )
        self.status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: #5856D6; "
            f"font-family: {FONT_SYSTEM};"
        )

    def _clear_reference(self) -> None:
        """Remove the reference and switch back to raw display."""
        self._reference = None
        if REF_FILE.exists():
            REF_FILE.unlink()
        self._apply_reference_mode()
        self.evolution.clear()
        self.status_label.setText("Reference cleared — switched to RAW mode")

    def _apply_reference_mode(self) -> None:
        """Sync all UI components to the current reference state."""
        has_ref = self._reference is not None
        self.live_plot.set_transmission_mode(has_ref)
        self.analysis_panel.set_mode(has_ref)
        self.clear_ref_btn.setVisible(has_ref)
        self.ref_btn.setText(
            "📷 Re-capture Reference" if has_ref else "📷 Capture Reference"
        )

    # ── Hardware connection ───────────────────────────────────────────────

    def _connect_hw(self) -> None:
        self.status_label.setText("⏳ Connecting...")
        self.status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: #FF9500; "
            f"font-family: {FONT_SYSTEM};"
        )
        QApplication.processEvents()

        ok, msg = self.hw.connect()
        if ok:
            ref_info = " (Transmission)" if self._reference is not None else " (Raw)"
            self.status_label.setText(f"✅ {msg}{ref_info}")
            self.status_label.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: #34C759; "
                f"font-family: {FONT_SYSTEM};"
            )
            self.hw.leds_on()
            self._start_acquisition()
        else:
            self.status_label.setText(f"❌ {msg}")
            self.status_label.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: #FF3B30; "
                f"font-family: {FONT_SYSTEM};"
            )

    def _start_acquisition(self) -> None:
        if self.worker:
            self.worker.stop()

        self.worker = AcquisitionWorker(self.hw)
        self.worker.spectrum_ready.connect(self._on_spectrum)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_spectrum(self, raw: np.ndarray) -> None:
        """Handle new live spectrum — compute transmission if reference exists."""
        self._latest_raw = raw
        wl = self.hw.wavelengths
        if wl is None:
            return

        # Decide what to display and analyze
        if self._reference is not None:
            display = compute_transmission(
                raw, self._reference,
                floor=self._an_cfg.reference_floor_counts,
            )
        else:
            display = raw

        analysis = analyze_spectrum(wl[:len(display)], display, self._an_cfg)
        self._latest_analysis = analysis

        # Update all UI components
        self.live_plot.update_data(wl, display, analysis)
        self.analysis_panel.update_analysis(analysis)
        self.evolution.push(analysis)

    def _on_error(self, msg: str) -> None:
        self.status_label.setText(f"⚠️ {msg}")

    # ── Snapshot ──────────────────────────────────────────────────────────

    def _take_snapshot(self, label: str, note: str) -> None:
        if self._latest_raw is None or self.hw.wavelengths is None:
            QMessageBox.warning(
                self, "No Data",
                "No live spectra available yet. Wait for data to appear.",
            )
            return

        # Store transmission alongside raw if reference exists
        trans = None
        if self._reference is not None:
            trans = compute_transmission(
                self._latest_raw, self._reference,
                floor=self._an_cfg.reference_floor_counts,
            )

        entry = add_snapshot(
            dataset=self.dataset,
            label=label,
            note=note,
            wavelengths=self.hw.wavelengths,
            spectrum=self._latest_raw,
            analysis=self._latest_analysis,
            transmission=trans,
        )

        self.labelling_panel.add_log_entry(entry)
        self.labelling_panel.update_stats(self.dataset)

        self.status_label.setText(
            f"📸 Snapshot #{entry['id']} saved: {label}"
        )

    # ── Cleanup ───────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self.worker:
            self.worker.stop()
        self.hw.disconnect()
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Launch the labeller with default configs.

    For a different device, create custom configs::

        hw = HardwareConfig(
            integration_time_ms=10,
            controller_vid=0x1234,
            controller_pid=0x5678,
            led_brightness=50,
            num_led_channels=6,
            channel_labels=("1", "2", "3", "4", "5", "6"),
        )
        an = AnalysisConfig(roi_wl_min=500, roi_wl_max=800)
        window = CompressionLabellerWindow(hw, an)
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Default configs — override here or via subclass for different hardware
    hw_cfg = HardwareConfig()
    an_cfg = AnalysisConfig()

    window = CompressionLabellerWindow(hw_cfg, an_cfg)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
