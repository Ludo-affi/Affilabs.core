#!/usr/bin/env python3
"""
AffiLabs — Compression Trainer (user-facing)
=============================================

Simple guided UI that walks a first-time user through sensor chip
compression.  Device / sensor agnostic — auto-calibrates to *their*
specific system.

Flow
----
1. **Capture NO CHIP** — no sensor chip, flow cell closed.
2. **Capture CHIP + WATER** — sensor chip placed, water flowing, no compression.
3. **Compress** — turn the knob slowly.  A big gauge shows:
       yellow = keep going  |  GREEN = sweet spot  |  red = back off.

Detection method
----------------
We track the **mid/low band ratio** (self-normalizing spectral shape
metric).  It drops as SPR coupling improves, stabilises at the sweet
spot, and climbs back if over-compressed.  The *trend* is universal
across systems — the two baseline captures provide the system-specific
scale.

The target range is estimated as:

    target = ratio_chip_water - sweet_spot_drop

where ``sweet_spot_drop`` is typically ~ 0.07 below the chip+water ratio
(i.e. the ratio must drop from the uncompressed state).

Usage
-----
    python standalone_tools/compression_trainer_ui.py
"""
from __future__ import annotations

import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

FONT = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif"

# Colours
COL_BG        = "#F2F2F7"
COL_CARD      = "#FFFFFF"
COL_TEXT      = "#1D1D1F"
COL_SUBTLE    = "#8E8E93"
COL_BLUE      = "#007AFF"
COL_PURPLE    = "#5856D6"
COL_GREEN     = "#34C759"
COL_ORANGE    = "#FF9500"
COL_RED       = "#FF3B30"
COL_BORDER    = "#E5E5EA"
COL_STEP_DONE = COL_GREEN
COL_STEP_CUR  = COL_PURPLE
COL_STEP_TODO = "#D1D1D6"


@dataclass
class TrainerConfig:
    """All tuneable parameters in one place."""

    # Hardware (same as labeller defaults — Pico P4SPR + USB4000)
    integration_time_ms: int = 5
    controller_vid: int = 0x2E8A
    controller_pid: int = 0x000A
    controller_baud: int = 115200
    led_brightness: int = 25
    channel_labels: tuple[str, ...] = ("a", "b", "c", "d")

    # Band definitions (nm)
    band_low: tuple[float, float] = (560.0, 600.0)
    band_mid: tuple[float, float] = (600.0, 650.0)
    band_high: tuple[float, float] = (650.0, 695.0)

    # Sweet-spot — normalised range (chip+water baseline = 1.0)
    sweet_spot_low: float = 0.94        # bottom of green zone (94% of baseline)
    sweet_spot_high: float = 0.96       # top of green zone (96% of baseline)

    # Capture averaging — average N frames for stability
    capture_avg_frames: int = 10

    # Trend detection — rolling derivative window
    trend_window: int = 30

    # Evolution buffer
    evo_buffer_size: int = 500


# Persistence
_SCRIPT_DIR = Path(__file__).resolve().parent
CAL_FILE = _SCRIPT_DIR / "compression_trainer_cal.npz"


# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE LINK
# ═══════════════════════════════════════════════════════════════════════════════


class HardwareLink:
    def __init__(self, cfg: TrainerConfig) -> None:
        self.cfg = cfg
        self.spec = None
        self.serial_conn = None
        self.wavelengths: np.ndarray | None = None

    def connect(self) -> tuple[bool, str]:
        cfg = self.cfg
        try:
            try:
                import os
                sys.path.insert(0, os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..")
                ))
                from affilabs.utils.libusb_init import get_libusb_backend
                _be = get_libusb_backend()
                if _be:
                    import usb.core
                    _orig = usb.core.find

                    def _pf(*a, **k):
                        if "backend" not in k:
                            k["backend"] = _be
                        return _orig(*a, **k)

                    usb.core.find = _pf
            except Exception:
                pass

            import seabreeze
            seabreeze.use("pyseabreeze")
            from seabreeze.spectrometers import Spectrometer, list_devices

            devs = list_devices()
            if not devs:
                return False, "No spectrometer found"
            self.spec = Spectrometer(devs[0])
            self.spec.integration_time_micros(cfg.integration_time_ms * 1000)
            self.wavelengths = self.spec.wavelengths()
        except Exception as e:
            return False, f"Spectrometer: {e}"

        try:
            import serial
            import serial.tools.list_ports

            for p in serial.tools.list_ports.comports():
                if p.vid == cfg.controller_vid and p.pid == cfg.controller_pid:
                    self.serial_conn = serial.Serial(
                        p.device, cfg.controller_baud, timeout=1,
                    )
                    time.sleep(0.3)
                    return True, f"Connected ({p.device})"
            return False, "Controller not found"
        except Exception as e:
            return False, f"Serial: {e}"

    def _cmd(self, c: str) -> None:
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(c.encode())
            time.sleep(0.02)

    def leds_on(self) -> None:
        labels = ",".join(self.cfg.channel_labels)
        b = self.cfg.led_brightness
        n = len(self.cfg.channel_labels)
        self._cmd(f"lm:{labels}\n")
        self._cmd(f"batch:{','.join([str(b)] * n)}\n")

    def leds_off(self) -> None:
        n = len(self.cfg.channel_labels)
        self._cmd(f"batch:{','.join(['0'] * n)}\n")

    def read(self) -> np.ndarray | None:
        return self.spec.intensities() if self.spec else None

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
# HARDWARE MANAGER ADAPTER (for launch from main app)
# ═══════════════════════════════════════════════════════════════════════════════


class HardwareMgrAdapter:
    """Wraps the app's hardware_mgr to match the HardwareLink interface.

    Used when the Compression Assistant is launched from the main app
    (hardware already connected).  Does NOT disconnect on cleanup — the
    caller owns the hardware.
    """

    def __init__(self, hardware_mgr) -> None:
        self._mgr = hardware_mgr
        self.spec = hardware_mgr.usb          # OceanSpectrometerAdapter
        self.serial_conn = getattr(hardware_mgr, "ctrl", None)
        self.wavelengths: np.ndarray | None = None
        self._prev_integration_ms: int | None = None  # to restore on disconnect

        if self.spec:
            try:
                self.wavelengths = self.spec.read_wavelength()
            except Exception:
                pass
            # Set integration time to match trainer config (5 ms)
            # The main app may have a different value — save it to restore later
            cfg = TrainerConfig()
            try:
                self._prev_integration_ms = getattr(self.spec, "_last_integration_ms", None)
                self.spec.set_integration(cfg.integration_time_ms)
            except Exception:
                pass

    # ── HardwareLink-compatible interface ─────────────────────────────────

    def connect(self) -> tuple[bool, str]:
        """Already connected — just validate."""
        if self.spec is None:
            return False, "No spectrometer in hardware_mgr"
        if self.serial_conn is None:
            return False, "No controller in hardware_mgr"
        if self.wavelengths is None:
            try:
                self.wavelengths = self.spec.read_wavelength()
            except Exception as e:
                return False, f"Cannot read wavelengths: {e}"
        return True, "Using app hardware"

    def _cmd(self, c: str) -> None:
        ctrl = self.serial_conn
        if ctrl is None:
            return
        if hasattr(ctrl, "_ser") and ctrl._ser and ctrl._ser.is_open:
            ctrl._ser.write(c.encode())
            time.sleep(0.02)
        elif hasattr(ctrl, "_serial") and ctrl._serial and ctrl._serial.is_open:
            ctrl._serial.write(c.encode())
            time.sleep(0.02)
        elif hasattr(ctrl, "send_command"):
            ctrl.send_command(c.rstrip("\n"))

    def leds_on(self) -> None:
        cfg = TrainerConfig()
        labels = ",".join(cfg.channel_labels)
        b = cfg.led_brightness
        n = len(cfg.channel_labels)
        self._cmd(f"lm:{labels}\n")
        self._cmd(f"batch:{','.join([str(b)] * n)}\n")

    def leds_off(self) -> None:
        cfg = TrainerConfig()
        n = len(cfg.channel_labels)
        self._cmd(f"batch:{','.join(['0'] * n)}\n")

    def read(self) -> np.ndarray | None:
        if self.spec:
            try:
                return self.spec.read_intensity()
            except Exception:
                return None
        return None

    def disconnect(self) -> None:
        """Restore integration time — we don't own the hardware."""
        if self._prev_integration_ms is not None and self.spec:
            try:
                self.spec.set_integration(self._prev_integration_ms)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# BAND-RATIO COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════


def compute_band_ratio(
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    band_a: tuple[float, float],
    band_b: tuple[float, float],
) -> float:
    """Mean(band_a) / Mean(band_b).  Returns 1.0 on error."""
    ma = (wavelengths >= band_a[0]) & (wavelengths <= band_a[1])
    mb = (wavelengths >= band_b[0]) & (wavelengths <= band_b[1])
    a = np.mean(spectrum[ma]) if np.any(ma) else 1.0
    b = np.mean(spectrum[mb]) if np.any(mb) else 1.0
    return float(a / b) if b > 0 else 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# ACQUISITION WORKER
# ═══════════════════════════════════════════════════════════════════════════════


class AcqWorker(QThread):
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
                d = self.hw.read()
                if d is not None:
                    self.spectrum_ready.emit(d)
            except Exception as e:
                self.error.emit(str(e))
                time.sleep(1)
            time.sleep(0.01)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING STAGES
# ═══════════════════════════════════════════════════════════════════════════════

STAGE_CONNECT    = 0
STAGE_NO_CHIP    = 1
STAGE_CHIP_WATER = 2
STAGE_COMPRESS   = 3
STAGE_QC_LEAK_CHECK = 4
STAGE_DONE       = 5

STEP_LABELS = ["No Chip", "Chip + Water", "Compress"]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════════


class StepProgressBar(QWidget):
    """Horizontal 3-step indicator:  (1) -- (2) -- (3)  with labels."""

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        self._labels = labels
        self._current = 0
        self._completed: set[int] = set()
        self.setFixedHeight(72)

    def set_step(self, step_idx: int) -> None:
        self._current = step_idx
        self._completed = set(range(step_idx))
        self.update()

    def mark_all_done(self) -> None:
        self._completed = set(range(len(self._labels)))
        self._current = len(self._labels)
        self.update()

    def paintEvent(self, event) -> None:
        from PySide6.QtCore import QPointF, QRectF

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self._labels)
        w = self.width()
        circle_r = 18
        y_center = 26
        margin_x = 60
        span = w - 2 * margin_x

        xs = [margin_x + i * span / max(n - 1, 1) for i in range(n)]

        # Connecting lines
        for i in range(n - 1):
            col = QColor(COL_STEP_DONE) if i < self._current else QColor(COL_STEP_TODO)
            p.setPen(QPen(col, 3))
            p.drawLine(QPointF(xs[i] + circle_r, y_center),
                       QPointF(xs[i + 1] - circle_r, y_center))

        # Circles + labels
        for i in range(n):
            cx = xs[i]

            if i in self._completed:
                fill = QColor(COL_STEP_DONE)
                text_col = QColor(COL_TEXT)
            elif i == self._current:
                fill = QColor(COL_STEP_CUR)
                text_col = QColor(COL_TEXT)
            else:
                fill = QColor(COL_STEP_TODO)
                text_col = QColor(COL_SUBTLE)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawEllipse(QPointF(cx, y_center), circle_r, circle_r)

            # Number / checkmark
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            rect = QRectF(cx - circle_r, y_center - circle_r,
                          circle_r * 2, circle_r * 2)
            if i in self._completed:
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "\u2713")
            else:
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))

            # Label
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(text_col)
            p.drawText(QRectF(cx - 50, y_center + circle_r + 4, 100, 20),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       self._labels[i])

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSION GAUGE WIDGET
# ═══════════════════════════════════════════════════════════════════════════════


class CompressionGauge(QWidget):
    """Big vertical gauge — maps mid/low ratio to a colour-coded bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(160)
        self.setMinimumHeight(340)

        self._ratio_chip = 0.87
        self._ratio_target = 0.80
        self._ratio_current = 0.87
        self._half_width = 0.02
        self._zone = "waiting"
        self._has_been_below = False  # hysteresis: True once ratio drops below sweet zone

    def set_calibration(
        self, ratio_chip: float, sweet_lo: float, sweet_hi: float,
    ) -> None:
        self._ratio_chip = ratio_chip
        self._ratio_target = (sweet_lo + sweet_hi) / 2
        self._half_width = (sweet_hi - sweet_lo) / 2
        self._has_been_below = False
        self.update()

    def set_value(self, ratio: float) -> None:
        self._ratio_current = ratio
        sweet_lo = self._ratio_target - self._half_width
        sweet_hi = self._ratio_target + self._half_width

        if ratio < sweet_lo:
            # Below sweet spot — user went too far
            self._has_been_below = True
            self._zone = "backoff"
        elif ratio <= sweet_hi:
            # Inside the sweet zone — clear the flag (user loosened correctly)
            self._has_been_below = False
            self._zone = "sweet"
        else:
            # Above sweet_hi
            if self._has_been_below:
                # Over-compression: signal wrapped back up past sweet spot.
                # User must LOOSEN, not tighten.
                self._zone = "backoff"
            else:
                # Normal approach — keep tightening
                self._zone = "tighten"

        self.update()

    @property
    def zone(self) -> str:
        return self._zone

    def paintEvent(self, event) -> None:
        from PySide6.QtCore import QPointF, QRectF

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_top = 30
        margin_bot = 30
        bar_w = 52
        bar_x = w // 2 - bar_w // 2 + 10
        bar_h = h - margin_top - margin_bot

        r_top = 1.02
        r_bot = self._ratio_target - 0.06

        def ratio_to_y(r: float) -> float:
            frac = (r_top - r) / (r_top - r_bot) if r_top != r_bot else 0.5
            return margin_top + frac * bar_h

        sweet_hi = self._ratio_target + self._half_width
        sweet_lo = self._ratio_target - self._half_width

        # Background card
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COL_CARD))
        p.drawRoundedRect(QRectF(0, 0, w, h), 16, 16)

        # Yellow zone
        y_top = margin_top
        y_sweet_hi = ratio_to_y(sweet_hi)
        p.setBrush(QColor(255, 204, 0, 80))
        p.drawRoundedRect(QRectF(bar_x, y_top, bar_w, y_sweet_hi - y_top), 6, 6)

        # Green zone
        y_sweet_lo = ratio_to_y(sweet_lo)
        p.setBrush(QColor(52, 199, 89, 120))
        p.drawRect(QRectF(bar_x, y_sweet_hi, bar_w, y_sweet_lo - y_sweet_hi))

        # Red zone
        y_bot = margin_top + bar_h
        p.setBrush(QColor(255, 59, 48, 80))
        p.drawRoundedRect(QRectF(bar_x, y_sweet_lo, bar_w, y_bot - y_sweet_lo), 6, 6)

        # Outer border
        p.setPen(QPen(QColor(COL_BORDER), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, margin_top, bar_w, bar_h), 6, 6)

        # Zone labels
        font_sm = QFont("Segoe UI", 8)
        p.setFont(font_sm)

        p.setPen(QColor(COL_ORANGE))
        p.drawText(QRectF(bar_x + bar_w + 8, y_top, 80, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Loose")

        p.setPen(QColor(COL_GREEN))
        y_mid_sweet = (y_sweet_hi + y_sweet_lo) / 2
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(bar_x + bar_w + 8, y_mid_sweet - 10, 80, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "SWEET SPOT")

        p.setFont(font_sm)
        p.setPen(QColor(COL_RED))
        p.drawText(QRectF(bar_x + bar_w + 8, y_bot - 18, 80, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Over-tight")

        # Current position marker (triangle)
        y_cur = ratio_to_y(self._ratio_current)
        y_cur = max(margin_top, min(margin_top + bar_h, y_cur))

        if self._zone == "sweet":
            mc = QColor(COL_GREEN)
        elif self._zone == "tighten":
            mc = QColor(COL_ORANGE)
        elif self._zone == "backoff":
            mc = QColor(COL_RED)
        else:
            mc = QColor(COL_SUBTLE)

        tri = QPolygonF([
            QPointF(bar_x - 2, y_cur),
            QPointF(bar_x - 20, y_cur - 11),
            QPointF(bar_x - 20, y_cur + 11),
        ])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mc)
        p.drawPolygon(tri)

        # Value label
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(mc)
        p.drawText(QRectF(0, y_cur - 10, bar_x - 24, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._ratio_current:.3f}")

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# CARD HELPER
# ═══════════════════════════════════════════════════════════════════════════════


def _card(child_layout: QVBoxLayout | QHBoxLayout) -> QFrame:
    """Wrap a layout in a white rounded card with subtle shadow."""
    card = QFrame()
    card.setLayout(child_layout)
    card.setStyleSheet(
        f"QFrame {{ background: {COL_CARD}; border-radius: 14px; }}"
    )
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 25))
    card.setGraphicsEffect(shadow)
    return card


# ═══════════════════════════════════════════════════════════════════════════════
# PUMP FLUSH WORKER (for active leak check with P4PRO + AffiPump)
# ═══════════════════════════════════════════════════════════════════════════════


class _PumpFlushWorker(QThread):
    """Runs a gentle pump flush in the background during leak check.

    Opens 6-port valves to INJECT, runs a slow dispense cycle to push
    liquid through the channels while the main thread monitors spectral
    intensity for leaks.
    """

    flush_error = Signal(str)

    def __init__(self, pump) -> None:
        super().__init__()
        self._pump = pump
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._flush())
        except Exception as e:
            self.flush_error.emit(str(e))
        finally:
            loop.close()

    async def _flush(self) -> None:
        """Run a single gentle aspirate-dispense cycle for leak testing."""
        import asyncio

        pump = self._pump
        if pump is None:
            return

        try:
            # Get raw controller for valve operations
            hw_mgr = getattr(pump, '_hardware_manager', None) or getattr(pump, 'hardware_manager', None)
            raw_ctrl = None
            if hw_mgr:
                raw_ctrl = getattr(hw_mgr, '_ctrl_raw', None)

            # Open 6-port valves to INJECT for flow-through
            if raw_ctrl:
                try:
                    raw_ctrl.knx_six_both(state=1)
                    await asyncio.sleep(0.3)
                    raw_ctrl.knx_three_both(state=1)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass  # Valve control is best-effort

            # Gentle dispense — slow rate pushes liquid through channels
            # while spectrum is monitored for intensity drops (leaks)
            volume_ul = 1000.0
            aspirate_speed_ul_s = 24000.0 / 60.0  # 400 µL/s — fast aspirate (matches run buffer)
            dispense_speed_ul_s = 12000.0 / 60.0   # 200 µL/s — moderate dispense

            # Aspirate first
            pump._pump.pump.aspirate_both(volume_ul, aspirate_speed_ul_s)
            p1, p2, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, pump._pump.pump.wait_until_both_ready, 60.0,
            )
            if not self._running:
                return

            await asyncio.sleep(0.5)

            # Dispense through channels
            pump._pump.pump.dispense_both(volume_ul, dispense_speed_ul_s)
            p1, p2, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, pump._pump.pump.wait_until_both_ready, 60.0,
            )

            # Close valves after flush
            if raw_ctrl:
                try:
                    raw_ctrl.knx_three_both(state=0)
                    await asyncio.sleep(0.1)
                    raw_ctrl.knx_six_both(state=0)
                except Exception:
                    pass

        except Exception as e:
            self.flush_error.emit(f"Flush failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TRAINER WINDOW
# ═══════════════════════════════════════════════════════════════════════════════


class CompressionTrainerWindow(QMainWindow):
    def __init__(
        self,
        cfg: TrainerConfig | None = None,
        hardware_mgr=None,
        start_stage: int | None = None,
        pre_baseline: dict | None = None,
        pump=None,
    ) -> None:
        super().__init__()
        self.cfg = cfg or TrainerConfig()
        self.setWindowTitle("AffiLabs  \u2014  Compression Assistant")
        self.setGeometry(180, 80, 1060, 720)
        self.setStyleSheet(f"background: {COL_BG};")

        # Use pre-connected hardware if provided, else standalone link
        if hardware_mgr is not None:
            self.hw = HardwareMgrAdapter(hardware_mgr)
            self._hw_owned = False
        else:
            self.hw = HardwareLink(self.cfg)
            self._hw_owned = True

        self.worker: AcqWorker | None = None
        self._latest_raw: np.ndarray | None = None
        self._avg_buf: list[np.ndarray] = []

        # Calibration baselines
        self._no_chip_ratio: float | None = None
        self._no_chip_spectrum: np.ndarray | None = None  # Reference spectrum for transmission
        self._chip_water_ratio: float | None = None
        self._target_ratio: float | None = None
        self._cal_loaded = False

        # Evolution buffer
        self._evo_buf: deque[float] = deque(maxlen=self.cfg.evo_buffer_size)

        # QC leak check
        self._qc_monitoring = False
        self._qc_passed = False
        self._qc_ref_intensity: float | None = None
        self._qc_sample_count = 0
        self._qc_intensity_samples: deque[float] = deque(maxlen=600)  # Last 600 samples
        self._qc_threshold_line: pg.InfiniteLine | None = None

        # Pump reference for active leak checking (P4PRO + AffiPump)
        self._pump = pump
        self._pump_flush_worker: QThread | None = None

        # Load pre-captured baseline data (e.g. S-pol capture from P4PRO flow)
        if pre_baseline:
            self._no_chip_ratio = pre_baseline.get("no_chip_ratio")
            self._no_chip_spectrum = pre_baseline.get("no_chip_spectrum")

        # When launched from main app, hardware is already connected —
        # skip STAGE_CONNECT and go to the requested stage
        if hardware_mgr is not None:
            self._stage = start_stage if start_stage is not None else STAGE_NO_CHIP
        else:
            self._stage = STAGE_CONNECT

        self._build_ui()
        self._load_calibration()
        self._connect_hw()

    # ══════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 12)
        root.setSpacing(10)

        # ── Header ───────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Compression Assistant")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {COL_TEXT}; "
            f"font-family: {FONT}; background: transparent;"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self.status = QLabel("Connecting...")
        self.status.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COL_ORANGE}; "
            f"font-family: {FONT}; background: transparent;"
        )
        hdr.addWidget(self.status)
        root.addLayout(hdr)

        # ── Step progress bar ────────────────────────────────────────────
        self.step_bar = StepProgressBar(STEP_LABELS)
        self.step_bar.setStyleSheet("background: transparent;")
        root.addWidget(self.step_bar)

        # ── Content area ─────────────────────────────────────────────────
        content = QHBoxLayout()
        content.setSpacing(16)

        # LEFT column
        left = QVBoxLayout()
        left.setSpacing(12)

        # Instruction card
        instr_inner = QVBoxLayout()
        instr_inner.setContentsMargins(20, 16, 20, 16)
        instr_inner.setSpacing(8)

        self.step_badge = QLabel("")
        self.step_badge.setFixedHeight(24)
        self.step_badge.setFixedWidth(86)
        self.step_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: white; "
            f"background: {COL_PURPLE}; border-radius: 12px; "
            f"padding: 2px 12px; font-family: {FONT};"
        )
        instr_inner.addWidget(self.step_badge)

        self.instruction = QLabel("")
        self.instruction.setWordWrap(True)
        self.instruction.setStyleSheet(
            f"font-size: 16px; font-weight: 400; color: {COL_TEXT}; "
            f"font-family: {FONT}; background: transparent;"
        )
        self.instruction.setMinimumHeight(70)
        instr_inner.addWidget(self.instruction)

        self.instr_card = _card(instr_inner)
        left.addWidget(self.instr_card)

        # Action button
        self.action_btn = QPushButton("")
        self.action_btn.setFixedHeight(50)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet(self._btn_style(COL_BLUE))
        self.action_btn.clicked.connect(self._on_action)
        left.addWidget(self.action_btn)

        # Skip button (visible only during leak check stage)
        self.skip_btn = QPushButton("Skip Leak Check")
        self.skip_btn.setFixedHeight(40)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(
            f"QPushButton {{ background: #F2F2F7; color: {COL_SUBTLE}; "
            f"border: 1.5px solid {COL_SUBTLE}; border-radius: 8px; "
            f"padding: 4px 16px; font-size: 13px; font-weight: 600; "
            f"font-family: {FONT}; }}"
            f"QPushButton:hover {{ background: #E8E8ED; }}"
        )
        self.skip_btn.clicked.connect(self._skip_leak_check)
        self.skip_btn.hide()  # Hidden by default
        left.addWidget(self.skip_btn)

        # Big feedback label
        self.feedback = QLabel("")
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback.setMinimumHeight(60)
        self.feedback.setStyleSheet(
            f"font-size: 40px; font-weight: 800; color: {COL_SUBTLE}; "
            f"font-family: {FONT}; background: transparent;"
        )
        left.addWidget(self.feedback)

        # Live spectrum preview (visible during capture stages)
        self.live_plot = pg.PlotWidget()
        self.live_plot.setLabel("left", "Intensity")
        self.live_plot.setLabel("bottom", "Wavelength (nm)")
        self.live_plot.showGrid(x=True, y=True, alpha=0.15)
        self.live_plot.setFixedHeight(160)
        self.live_plot.setBackground("#FAFAFA")
        self.live_curve = self.live_plot.plot(
            [], [], pen=pg.mkPen("#5856D6", width=1.5),
        )
        left.addWidget(self.live_plot)

        # Evolution plot (visible during compress stage)
        self.evo_plot = pg.PlotWidget()
        self.evo_plot.setLabel("left", "mid / low ratio")
        self.evo_plot.setLabel("bottom", "Samples")
        self.evo_plot.showGrid(x=True, y=True, alpha=0.15)
        self.evo_plot.setFixedHeight(160)
        self.evo_plot.setBackground("#FAFAFA")
        self.evo_curve = self.evo_plot.plot(
            [], [], pen=pg.mkPen(COL_RED, width=2),
        )
        self.evo_target_region: pg.LinearRegionItem | None = None
        left.addWidget(self.evo_plot)

        left.addStretch()
        content.addLayout(left, stretch=3)

        # RIGHT column — gauge
        right = QVBoxLayout()
        right.setSpacing(8)

        gauge_label = QLabel("Compression")
        gauge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gauge_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {COL_SUBTLE}; "
            f"font-family: {FONT}; background: transparent;"
        )
        right.addWidget(gauge_label)
        self.gauge_label = gauge_label

        self.gauge = CompressionGauge()
        right.addWidget(self.gauge, stretch=1)
        right.addStretch()

        content.addLayout(right, stretch=1)
        root.addLayout(content, stretch=1)

        # ── Footer ───────────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.addStretch()

        self.retake_btn = QPushButton("\u21bb  Retake Step 2")
        self.retake_btn.setFixedHeight(36)
        self.retake_btn.setFixedWidth(170)
        self.retake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retake_btn.setStyleSheet(
            f"QPushButton {{ background: #F2F2F7; color: {COL_ORANGE}; "
            f"border: 1.5px solid {COL_ORANGE}; border-radius: 8px; "
            f"padding: 4px 16px; font-size: 13px; font-weight: 600; "
            f"font-family: {FONT}; }}"
            f"QPushButton:hover {{ background: #FFF3E0; }}"
        )
        self.retake_btn.clicked.connect(self._retake_compression)
        footer.addWidget(self.retake_btn)

        self.recal_btn = QPushButton("\u21bb  Start Over")
        self.recal_btn.setFixedHeight(36)
        self.recal_btn.setFixedWidth(160)
        self.recal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recal_btn.setStyleSheet(
            f"QPushButton {{ background: #F2F2F7; color: {COL_RED}; "
            f"border: 1.5px solid {COL_RED}; border-radius: 8px; "
            f"padding: 4px 16px; font-size: 13px; font-weight: 600; "
            f"font-family: {FONT}; }}"
            f"QPushButton:hover {{ background: #FFE5E5; }}"
        )
        self.recal_btn.clicked.connect(self._reset_calibration)
        footer.addWidget(self.recal_btn)
        root.addLayout(footer)

        self._update_stage_ui()

    # ── Button style helper ──────────────────────────────────────────────

    @staticmethod
    def _btn_style(bg: str, hover: str | None = None) -> str:
        hv = hover or bg
        return (
            f"QPushButton {{ background: {bg}; color: white; border: none; "
            f"border-radius: 12px; font-size: 15px; font-weight: 700; "
            f"font-family: {FONT}; }}"
            f"QPushButton:hover {{ background: {hv}; }}"
            f"QPushButton:disabled {{ background: #C7C7CC; }}"
        )

    # ══════════════════════════════════════════════════════════════════════
    # STAGE TRANSITIONS
    # ══════════════════════════════════════════════════════════════════════

    def _set_stage(self, stage: int) -> None:
        self._stage = stage
        self._update_stage_ui()

    def _update_stage_ui(self) -> None:
        s = self._stage

        # Show/hide plots based on stage
        is_compress = s == STAGE_COMPRESS
        is_qc = s in (STAGE_QC_LEAK_CHECK, STAGE_DONE)
        self.live_plot.setVisible(not is_compress and not is_qc)
        self.evo_plot.setVisible(is_compress or is_qc)
        self.gauge.setVisible(is_compress)
        self.gauge_label.setVisible(is_compress)
        
        # Update live plot label based on stage
        if s == STAGE_CHIP_WATER:
            self.live_plot.setLabel("left", "Transmission")
        else:
            self.live_plot.setLabel("left", "Intensity")

        if s == STAGE_CONNECT:
            self.step_bar.set_step(0)
            self.step_badge.setText("SETUP")
            self._set_badge_color(COL_ORANGE)
            self.instruction.setText(
                "Connecting to hardware...\n"
                "Make sure the spectrometer and controller are plugged in."
            )
            self.action_btn.setText("Retry connection")
            self.action_btn.setStyleSheet(self._btn_style(COL_ORANGE))
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.feedback.setText("")

        elif s == STAGE_NO_CHIP:
            self.step_bar.set_step(0)
            self.step_badge.setText("STEP 1 / 3")
            self._set_badge_color(COL_PURPLE)
            self.instruction.setText(
                "Place a new sensor into the prism.\n"
                "Keep it dry \u2014 no water.\n"
                "Close the lid. You should see all 4 LEDs on.\n\n"
                "When ready, click the button below."
            )
            self.action_btn.setText("Capture  DRY SENSOR  baseline")
            self.action_btn.setStyleSheet(self._btn_style(COL_PURPLE, "#4B49B0"))
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.feedback.setText("")

        elif s == STAGE_CHIP_WATER:
            self.step_bar.set_step(1)
            self.step_badge.setText("STEP 2 / 3")
            self._set_badge_color(COL_PURPLE)
            self.instruction.setText(
                "Place the sensor chip into the flow cell.\n"
                "Compress \u2014 turn the knob right until you feel resistance.\n"
                "Add water.\n"
                "Loosen \u2014 turn the knob all the way left.\n\n"
                "When ready, click the button below."
            )
            self.action_btn.setText("Capture  CHIP + WATER  baseline")
            self.action_btn.setStyleSheet(self._btn_style(COL_PURPLE, "#4B49B0"))
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.feedback.setText("")

        elif s == STAGE_COMPRESS:
            self.step_bar.set_step(2)
            self.step_badge.setText("STEP 3 / 3")
            self._set_badge_color(COL_GREEN)
            self.instruction.setText(
                "Assisted compression \u2014 live signal feedback.\n\n"
                "Slowly turn the knob right (tighten).\n"
                "The gauge and plot show your compression in real time.\n"
                "Stop when you reach the green zone."
            )
            self.action_btn.setText("Done \u2014 lock compression")
            self.action_btn.setStyleSheet(self._btn_style(COL_GREEN, "#2DB84E"))
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.feedback.setText("TIGHTEN SLOWLY")
            self.feedback.setStyleSheet(
                f"font-size: 40px; font-weight: 800; color: {COL_ORANGE}; "
                f"font-family: {FONT}; background: transparent;"
            )

        elif s == STAGE_QC_LEAK_CHECK:
            self.step_bar.set_step(2)
            self.step_badge.setText("STEP 3 / 3")
            self._set_badge_color(COL_ORANGE)
            has_pump = self._pump is not None
            if self._qc_monitoring:
                if has_pump:
                    self.instruction.setText(
                        "Flushing liquid through channels via pump...\n\n"
                        "Monitoring for leaks under flow.\n"
                        "(Checking signal stability over next 30 seconds)"
                    )
                else:
                    self.instruction.setText(
                        "Injecting liquid into all 4 channels...\n\n"
                        "Monitoring for leaks.\n"
                        "(Checking signal stability over next 30 seconds)"
                    )
                self.action_btn.setText("Cancel")
                self.action_btn.setStyleSheet(self._btn_style(COL_ORANGE))
                self.action_btn.setEnabled(True)
                self.skip_btn.hide()  # Hide skip button during monitoring
                self.feedback.setText("Monitoring...")
                self.feedback.setStyleSheet(
                    f"font-size: 40px; font-weight: 800; color: {COL_ORANGE}; "
                    f"font-family: {FONT}; background: transparent;"
                )
            else:
                if has_pump:
                    self.instruction.setText(
                        "Ready to check for leaks.\n\n"
                        "The pump will flush liquid through the channels\n"
                        "while monitoring signal intensity for 30 seconds."
                    )
                else:
                    self.instruction.setText(
                        "Inject liquid into all 4 channels.\n\n"
                        "This will check for leaks by monitoring\n"
                        "signal intensity for 30 seconds."
                    )
                self.action_btn.setText("Start Leak Check")
                self.action_btn.setStyleSheet(self._btn_style(COL_ORANGE, "#D4860D"))
                self.action_btn.setEnabled(True)
                self.skip_btn.show()  # Show skip button when leak check not started
                self.feedback.setText("")

        elif s == STAGE_DONE:
            self.step_bar.mark_all_done()
            self.step_badge.setText("COMPLETE")
            self._set_badge_color(COL_GREEN)
            self.instruction.setText(
                "Compression locked!\n\n"
                "The sensor is properly installed.\n"
                "You may now begin your experiment."
            )
            self.action_btn.setText("Close")
            self.action_btn.setStyleSheet(self._btn_style(COL_GREEN))
            self.action_btn.setEnabled(True)
            self.skip_btn.hide()
            self.feedback.setText("\u2713  DONE")
            self.feedback.setStyleSheet(
                f"font-size: 40px; font-weight: 800; color: {COL_GREEN}; "
                f"font-family: {FONT}; background: transparent;"
            )

    def _set_badge_color(self, col: str) -> None:
        self.step_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: white; "
            f"background: {col}; border-radius: 12px; "
            f"padding: 2px 12px; font-family: {FONT};"
        )

    # ══════════════════════════════════════════════════════════════════════
    # ACTION BUTTON
    # ══════════════════════════════════════════════════════════════════════

    def _on_action(self) -> None:
        if self._stage == STAGE_CONNECT:
            self._connect_hw()
        elif self._stage == STAGE_NO_CHIP:
            self._capture_no_chip()
        elif self._stage == STAGE_CHIP_WATER:
            self._capture_chip_water()
        elif self._stage == STAGE_COMPRESS:
            self._set_stage(STAGE_QC_LEAK_CHECK)
        elif self._stage == STAGE_QC_LEAK_CHECK:
            if self._qc_monitoring:
                # Monitoring in progress, do nothing (cancel button would go here if needed)
                return
            elif self._qc_passed:
                # QC passed, proceed to done
                self._set_stage(STAGE_DONE)
            else:
                # QC failed or not started, restart the check
                self._start_qc_monitoring()
        elif self._stage == STAGE_DONE:
            self.close()

    def _skip_leak_check(self) -> None:
        """Skip the QC leak check and proceed directly to completion."""
        self._set_stage(STAGE_DONE)

    # ══════════════════════════════════════════════════════════════════════
    # HARDWARE
    # ══════════════════════════════════════════════════════════════════════

    def _connect_hw(self) -> None:
        self.status.setText("Connecting...")
        self.status.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COL_ORANGE}; "
            f"font-family: {FONT}; background: transparent;"
        )
        QApplication.processEvents()

        ok, msg = self.hw.connect()
        if ok:
            self.status.setText(f"\u25cf  {msg}")
            self.status.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {COL_GREEN}; "
                f"font-family: {FONT}; background: transparent;"
            )
            self.hw.leds_on()
            self._start_acquisition()

            # If a specific start_stage was set (e.g. from P4PRO flow), honour it
            if self._stage not in (STAGE_CONNECT,):
                # Stage was already set by __init__ — just refresh UI
                self._update_stage_ui()
            elif self._cal_loaded:
                self._set_stage(STAGE_COMPRESS)
            else:
                self._set_stage(STAGE_NO_CHIP)
        else:
            self.status.setText(f"\u2715  {msg}")
            self.status.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {COL_RED}; "
                f"font-family: {FONT}; background: transparent;"
            )

    def _start_acquisition(self) -> None:
        if self.worker:
            self.worker.stop()
        self.worker = AcqWorker(self.hw)
        self.worker.spectrum_ready.connect(self._on_spectrum)
        self.worker.error.connect(
            lambda m: self.status.setText(f"Error: {m}")
        )
        self.worker.start()

    # ══════════════════════════════════════════════════════════════════════
    # BASELINE CAPTURES  (averaged over N frames)
    # ══════════════════════════════════════════════════════════════════════

    def _averaged_ratio(self) -> float:
        """Return mid/low ratio averaged over buffered frames."""
        if not self._avg_buf or self.hw.wavelengths is None:
            return self._current_mid_low()
        avg = np.mean(self._avg_buf, axis=0)
        return compute_band_ratio(
            self.hw.wavelengths, avg,
            self.cfg.band_mid, self.cfg.band_low,
        )

    def _capture_no_chip(self) -> None:
        if self._latest_raw is None or self.hw.wavelengths is None:
            QMessageBox.warning(self, "No Data",
                                "No spectrum available yet. Wait a moment.")
            return

        self._no_chip_ratio = self._averaged_ratio()
        # Store the averaged spectrum for transmission display in step 2
        if self._avg_buf:
            self._no_chip_spectrum = np.mean(self._avg_buf, axis=0)
        self.status.setText(
            f"\u25cf  Dry sensor captured  (mid/low = {self._no_chip_ratio:.3f})"
        )
        self._avg_buf.clear()
        self._set_stage(STAGE_CHIP_WATER)

    def _capture_chip_water(self) -> None:
        if self._latest_raw is None or self.hw.wavelengths is None:
            QMessageBox.warning(self, "No Data",
                                "No spectrum available yet. Wait a moment.")
            return

        self._chip_water_ratio = self._averaged_ratio()
        # Sweet spot in normalised space (baseline = 1.0)
        self._target_ratio = (self.cfg.sweet_spot_low + self.cfg.sweet_spot_high) / 2
        self._avg_buf.clear()

        self._save_calibration()

        self.gauge.set_calibration(
            ratio_chip=1.0,          # baseline IS 1.0 in normalised space
            sweet_lo=self.cfg.sweet_spot_low,
            sweet_hi=self.cfg.sweet_spot_high,
        )

        # Target region on evolution plot
        if self.evo_target_region:
            self.evo_plot.removeItem(self.evo_target_region)
        self.evo_target_region = pg.LinearRegionItem(
            values=[self.cfg.sweet_spot_low, self.cfg.sweet_spot_high],
            orientation="horizontal", movable=False,
            brush=pg.mkBrush(52, 199, 89, 40),
        )
        self.evo_target_region.setZValue(-10)
        self.evo_plot.addItem(self.evo_target_region)

        self._evo_buf.clear()
        self.status.setText(
            f"\u25cf  Chip+water captured  (baseline = 1.000, "
            f"sweet spot = {self.cfg.sweet_spot_low:.0%}\u2013{self.cfg.sweet_spot_high:.0%})"
        )
        self._set_stage(STAGE_COMPRESS)

    # ══════════════════════════════════════════════════════════════════════
    # CALIBRATION PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════

    def _save_calibration(self) -> None:
        np.savez(
            CAL_FILE,
            no_chip_ratio=self._no_chip_ratio or 0,
            chip_water_ratio=self._chip_water_ratio or 0,
            target_ratio=self._target_ratio or 0,
        )

    def _load_calibration(self) -> None:
        if CAL_FILE.exists():
            try:
                d = np.load(CAL_FILE)
                self._no_chip_ratio = float(d["no_chip_ratio"])
                self._chip_water_ratio = float(d["chip_water_ratio"])
                self._target_ratio = float(d["target_ratio"])
                if self._chip_water_ratio > 0 and self._target_ratio > 0:
                    self._cal_loaded = True
                    self.gauge.set_calibration(
                        ratio_chip=1.0,          # baseline IS 1.0 in normalised space
                        sweet_lo=self.cfg.sweet_spot_low,
                        sweet_hi=self.cfg.sweet_spot_high,
                    )
                    self.evo_target_region = pg.LinearRegionItem(
                        values=[self.cfg.sweet_spot_low,
                                self.cfg.sweet_spot_high],
                        orientation="horizontal", movable=False,
                        brush=pg.mkBrush(52, 199, 89, 40),
                    )
                    self.evo_target_region.setZValue(-10)
                    self.evo_plot.addItem(self.evo_target_region)
            except Exception:
                self._cal_loaded = False

    def _retake_compression(self) -> None:
        """Retake step 2 (chip+water baseline): keep step 1, redo chip+water capture."""
        if self._no_chip_ratio is None:
            # No baseline yet — fall back to full reset
            self._reset_calibration()
            return
        self._chip_water_ratio = None
        self._target_ratio = None
        self._cal_loaded = False
        self._evo_buf.clear()
        self._avg_buf.clear()
        if self.evo_target_region:
            self.evo_plot.removeItem(self.evo_target_region)
            self.evo_target_region = None
        self._set_stage(STAGE_CHIP_WATER)
        self.status.setText(
            f"Restarting step 2 \u2014 keeping step 1 baseline (dry sensor, mid/low = {self._no_chip_ratio:.3f})"
        )

    def _reset_calibration(self) -> None:
        self._no_chip_ratio = None
        self._no_chip_spectrum = None
        self._chip_water_ratio = None
        self._target_ratio = None
        self._cal_loaded = False
        self._evo_buf.clear()
        self._avg_buf.clear()
        if CAL_FILE.exists():
            CAL_FILE.unlink()
        if self.evo_target_region:
            self.evo_plot.removeItem(self.evo_target_region)
            self.evo_target_region = None
        self._set_stage(STAGE_NO_CHIP)
        self.status.setText("Calibration reset \u2014 recapture baselines")

    def _start_qc_monitoring(self) -> None:
        """Start QC leak check: monitor intensity for 30 seconds.

        If a pump is available (P4PRO + AffiPump), runs a gentle flush
        through the channels while monitoring — tests under real flow
        conditions.
        """
        self._qc_monitoring = True
        self._qc_ref_intensity = None
        self._qc_sample_count = 0
        self._qc_intensity_samples.clear()

        # Set up evo plot for QC intensity monitoring
        self._evo_buf.clear()
        self.evo_curve.setData([], [])
        self.evo_plot.setLabel("left", "Relative Intensity")
        self.evo_plot.setLabel("bottom", "Samples")

        # Remove compression target region, add 90% threshold line
        if self.evo_target_region:
            self.evo_plot.removeItem(self.evo_target_region)
            self.evo_target_region = None
        self._qc_threshold_line = pg.InfiniteLine(
            pos=0.90, angle=0, pen=pg.mkPen(COL_RED, width=2, style=Qt.PenStyle.DashLine),
            label="90% threshold", labelOpts={"color": COL_RED, "position": 0.1},
        )
        self.evo_plot.addItem(self._qc_threshold_line)

        # If pump available, start a gentle flush in the background
        if self._pump is not None:
            self._start_pump_flush()

        self._update_stage_ui()
        if self._pump is not None:
            self.status.setText("QC monitoring started. Pump flushing channels...")
        else:
            self.status.setText("QC monitoring started. Inject liquid into all 4 channels.")

    # ── Pump flush for active leak check (P4PRO + AffiPump) ──────────────

    def _start_pump_flush(self) -> None:
        """Run a gentle pump flush while monitoring for leaks.

        Opens 6-port valves to INJECT, runs a slow dispense (one cycle)
        to push liquid through the channels.  The spectral intensity is
        monitored by ``_on_spectrum`` while this runs.
        """
        self._pump_flush_worker = _PumpFlushWorker(self._pump)
        self._pump_flush_worker.flush_error.connect(
            lambda msg: self.status.setText(f"\u26a0 Flush error: {msg}")
        )
        self._pump_flush_worker.start()

    def _stop_pump_flush(self) -> None:
        """Stop the pump flush worker if running."""
        if self._pump_flush_worker and self._pump_flush_worker.isRunning():
            self._pump_flush_worker.stop()
            self._pump_flush_worker.wait(5000)
            self._pump_flush_worker = None

    def _check_qc_result(self) -> None:
        """After 10 sec monitoring, check if leak detected (>10% drop)."""
        if len(self._qc_intensity_samples) < 10:
            return  # Not enough samples yet

        # Compare first 30% vs last 30% of samples
        n = len(self._qc_intensity_samples)
        baseline_idx = n // 3
        current_idx = (2 * n) // 3

        if baseline_idx == 0 or current_idx <= baseline_idx:
            return

        baseline = np.mean(list(self._qc_intensity_samples)[:baseline_idx])
        current = np.mean(list(self._qc_intensity_samples)[current_idx:])

        if baseline > 0:
            pct_drop = (baseline - current) / baseline * 100
            if pct_drop > 10:
                # Leak detected
                self._qc_passed = False
                self.feedback.setText("\u26a0  LEAK DETECTED")
                self.feedback.setStyleSheet(
                    f"font-size: 40px; font-weight: 800; color: {COL_RED}; "
                    f"font-family: {FONT}; background: transparent;"
                )
                self.action_btn.setText("Retry Leak Check")
                self.action_btn.setEnabled(True)
                self.instruction.setText(
                    f"\u26a0  LEAK DETECTED!\n\n"
                    f"Signal dropped {pct_drop:.1f}% during injection.\n"
                    f"Check for loose connections or seal issues."
                )
                self._qc_monitoring = False
                self._stop_pump_flush()
                self._cleanup_qc_plot()
                self.status.setText(f"Leak detected: {pct_drop:.1f}% signal drop")
            else:
                # Pass QC
                self._qc_passed = True
                self.feedback.setText("\u2713  No Leak")
                self.feedback.setStyleSheet(
                    f"font-size: 40px; font-weight: 800; color: {COL_GREEN}; "
                    f"font-family: {FONT}; background: transparent;"
                )
                self.action_btn.setText("Proceed to Experiment")
                self.action_btn.setEnabled(True)
                self.instruction.setText(
                    "\u2713  No leak detected!\n\n"
                    "The system is ready.\n"
                    "Click below to proceed to your experiment."
                )
                self._qc_monitoring = False
                self._stop_pump_flush()
                self._cleanup_qc_plot()
                self.status.setText("QC passed: no significant leak")

    def _cleanup_qc_plot(self) -> None:
        """Remove QC threshold line and restore evo plot labels."""
        if self._qc_threshold_line:
            self.evo_plot.removeItem(self._qc_threshold_line)
            self._qc_threshold_line = None
        self.evo_plot.setLabel("left", "mid / low ratio")
        self.evo_plot.setLabel("bottom", "Samples")

    def _current_mid_low(self) -> float:
        if self._latest_raw is None or self.hw.wavelengths is None:
            return 1.0
        return compute_band_ratio(
            self.hw.wavelengths, self._latest_raw,
            self.cfg.band_mid, self.cfg.band_low,
        )

    def _on_spectrum(self, raw: np.ndarray) -> None:
        self._latest_raw = raw

        # Fill averaging buffer
        self._avg_buf.append(raw.copy())
        if len(self._avg_buf) > self.cfg.capture_avg_frames:
            self._avg_buf.pop(0)

        if self.hw.wavelengths is None:
            return

        wl = self.hw.wavelengths

        # During capture stages: show live spectrum preview
        if self._stage in (STAGE_NO_CHIP, STAGE_CHIP_WATER, STAGE_CONNECT):
            mask = (wl >= 540) & (wl <= 720)
            
            # During step 2 (chip+water), show transmission if reference available
            if self._stage == STAGE_CHIP_WATER and self._no_chip_spectrum is not None:
                # Transmission = raw / reference (avoid division by zero)
                with np.errstate(divide='ignore', invalid='ignore'):
                    transmission = raw / self._no_chip_spectrum
                    transmission = np.nan_to_num(transmission, nan=1.0, posinf=1.0, neginf=1.0)
                self.live_curve.setData(wl[mask], transmission[mask])
            else:
                # Step 1: show raw spectrum
                self.live_curve.setData(wl[mask], raw[mask])
            return

        # During QC leak check: monitor intensity
        if self._stage == STAGE_QC_LEAK_CHECK and self._qc_monitoring:
            # Compute total intensity (sum across all wavelengths)
            total_intensity = np.sum(raw)
            self._qc_intensity_samples.append(total_intensity)
            self._qc_sample_count += 1

            # Show intensity evolution on evo plot
            x = np.arange(len(self._qc_intensity_samples))
            y = np.array(self._qc_intensity_samples, dtype=float)
            if len(y) > 0:
                y_norm = y / y[0]  # Normalise to first sample = 1.0
            else:
                y_norm = y
            self.evo_curve.setData(x, y_norm)
            
            # After ~600 samples (assuming ~20Hz acquisition = 30 seconds), check result
            if self._qc_sample_count >= 600:
                self._check_qc_result()
            return

        # During compress stage: live guidance
        if self._stage != STAGE_COMPRESS:
            return
        if self._target_ratio is None or self._chip_water_ratio is None:
            return

        raw_ratio = self._current_mid_low()
        # Normalise: chip+water baseline = 1.0
        ratio = raw_ratio / self._chip_water_ratio
        self.gauge.set_value(ratio)

        self._evo_buf.append(ratio)
        x = np.arange(len(self._evo_buf))
        self.evo_curve.setData(x, np.array(self._evo_buf, dtype=float))

        zone = self.gauge.zone
        if zone == "tighten":
            self.feedback.setText("TIGHTEN")
            self.feedback.setStyleSheet(
                f"font-size: 40px; font-weight: 800; color: {COL_ORANGE}; "
                f"font-family: {FONT}; background: transparent;"
            )
        elif zone == "sweet":
            self.feedback.setText("\u25cf  SWEET SPOT  \u25cf")
            self.feedback.setStyleSheet(
                f"font-size: 40px; font-weight: 800; color: {COL_GREEN}; "
                f"font-family: {FONT}; background: transparent;"
            )
        elif zone == "backoff":
            self.feedback.setText("\u26a0  LOOSEN UP!")
            self.feedback.setStyleSheet(
                f"font-size: 40px; font-weight: 800; color: {COL_RED}; "
                f"font-family: {FONT}; background: transparent;"
            )

    # ══════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ══════════════════════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:
        self._stop_pump_flush()
        if self.worker:
            self.worker.stop()
        if self._hw_owned:
            self.hw.disconnect()
        super().closeEvent(event)

    # ══════════════════════════════════════════════════════════════════════
    # MODAL LAUNCH (from main app)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def launch_modal(
        parent,
        hardware_mgr,
        start_stage: int | None = None,
        pre_baseline: dict | None = None,
        pump=None,
    ) -> None:
        """Launch the Compression Assistant as a modal window.

        Called from the startup calibration dialog.  The servo must already
        be in P-pol before calling this.

        Args:
            parent: Parent widget (for centering)
            hardware_mgr: The app's HardwareManager (already connected)
            start_stage: Stage to start at (e.g. STAGE_CHIP_WATER to skip Step 1)
            pre_baseline: Pre-captured baseline data dict with keys:
                - 'no_chip_ratio': float — mid/low ratio from Step 1 capture
                - 'no_chip_spectrum': np.ndarray | None — reference spectrum
            pump: Pump reference for active leak checking (AffiPump / P4PRO+)
        """
        from PySide6.QtCore import QEventLoop

        trainer = CompressionTrainerWindow(
            hardware_mgr=hardware_mgr,
            start_stage=start_stage,
            pre_baseline=pre_baseline,
            pump=pump,
        )
        trainer.setWindowModality(Qt.WindowModality.ApplicationModal)
        trainer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        if parent:
            pg = parent.geometry()
            tw, th = trainer.width(), trainer.height()
            trainer.move(
                pg.x() + (pg.width() - tw) // 2,
                pg.y() + (pg.height() - th) // 2,
            )

        trainer.show()

        # Block until closed
        loop = QEventLoop()
        trainer.destroyed.connect(loop.quit)
        loop.exec()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = CompressionTrainerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
