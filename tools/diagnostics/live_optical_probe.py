"""Live Optical Probe — real-time spectrum viewer for fiber alignment & servo tuning.

Shows live spectrum plot + peak counts while you physically adjust the fiber,
move the servo, and toggle LEDs. No calibration required.

Usage:
    .venv/Scripts/python.exe tools/diagnostics/live_optical_probe.py

Controls:
    LED buttons     — toggle individual channels A/B/C/D or ALL
    Intensity slider — 1–255 (applies to all active LEDs)
    Integration slider — 4.5–60 ms
    Servo slider    — 0–255 PWM (moves in real-time as you drag)
    S / P buttons   — jump to saved S/P positions from device_config.json
    Sweep button    — run a full 0→255 sweep and overlay the peak-count profile
    Freeze          — pause live update (spectrum stays on screen)
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QGroupBox, QPushButton, QSlider, QLabel, QSizePolicy,
    QProgressBar,
)
import pyqtgraph as pg


# ── Hardware ──────────────────────────────────────────────────────────────────

def _connect_hardware():
    from affilabs.utils.controller import PicoP4SPR, PicoP4PRO, PicoEZSPR
    from affilabs.utils.hal.controller_hal import create_controller_hal
    from affilabs.utils.usb4000_wrapper import USB4000

    ctrl_hal = None
    for name, Cls in [("PicoP4SPR", PicoP4SPR), ("PicoP4PRO", PicoP4PRO), ("PicoEZSPR", PicoEZSPR)]:
        try:
            c = Cls()
            if c.open():
                ctrl_hal = create_controller_hal(c, None)
                print(f"  ✓ Controller: {name}")
                break
        except Exception:
            pass

    usb = USB4000()
    if not usb.open():
        raise RuntimeError("Detector open() failed")
    serial = getattr(usb, "serial_number", "?")
    print(f"  ✓ Spectrometer: {serial}")
    return ctrl_hal, usb, serial


def _load_servo_positions(serial: str) -> dict | None:
    import json
    p = ROOT / "affilabs" / "config" / "devices" / serial / "device_config.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    hw = d.get("hardware", d)
    s = hw.get("servo_s_position") or d.get("servo_s_position")
    p2 = hw.get("servo_p_position") or d.get("servo_p_position")
    if s and p2:
        return {"s": int(s), "p": int(p2)}
    return None


def _raw_ctrl(ctrl_hal):
    return ctrl_hal._ctrl if hasattr(ctrl_hal, "_ctrl") else ctrl_hal


def _move_servo(ctrl_hal, pwm: int):
    pwm = max(0, min(255, int(pwm)))
    deg = int(5 + (pwm / 255.0) * 170.0)
    deg = max(5, min(175, deg))
    rc = _raw_ctrl(ctrl_hal)
    rc._ser.write(f"sv{deg:03d}{deg:03d}\n".encode())
    time.sleep(0.05)
    rc._ser.readline()
    rc._ser.write(b"sp\n")
    time.sleep(0.05)
    rc._ser.readline()


def _set_leds(ctrl_hal, channels: list[str], intensity: int):
    rc = _raw_ctrl(ctrl_hal)
    if channels:
        ch_str = ",".join(c.upper() for c in channels)
        try:
            rc._ser.write(f"lm:{ch_str}\n".encode())
            time.sleep(0.03)
            rc._ser.read(20)
        except Exception:
            pass
    else:
        try:
            rc._ser.write(b"lm:\n")
            time.sleep(0.03)
        except Exception:
            pass
    kwargs = {c: (intensity if c in channels else 0) for c in ["a", "b", "c", "d"]}
    ctrl_hal.set_batch_intensities(**kwargs)


# ── Acquisition worker ────────────────────────────────────────────────────────

class _AcqWorker(QObject):
    """Background thread: continuously reads spectra and emits result."""
    new_spectrum = Signal(object, object)   # wavelengths, counts arrays
    sweep_done   = Signal(object, object)   # pwm_array, peak_array

    def __init__(self, ctrl_hal, usb):
        super().__init__()
        self._ctrl = ctrl_hal
        self._usb  = usb
        self._running  = False
        self._frozen   = False
        self._int_ms   = 10.0
        self._thread   = None
        self._sweep_req = False
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set_integration(self, ms: float):
        with self._lock:
            self._int_ms = float(ms)
            self._usb.set_integration(self._int_ms)
            time.sleep(0.05)

    def set_frozen(self, v: bool):
        self._frozen = v

    def request_sweep(self):
        self._sweep_req = True

    def _loop(self):
        self._usb.set_integration(self._int_ms)
        time.sleep(0.1)
        wl = None
        try:
            wl = np.array(self._usb.read_wavelength())
        except Exception:
            wl = np.arange(2048)

        while self._running:
            if self._sweep_req:
                self._sweep_req = False
                self._do_sweep(wl)
                continue

            if self._frozen:
                time.sleep(0.05)
                continue

            try:
                with self._lock:
                    ms = self._int_ms
                counts = np.array(self._usb.read_intensity(), dtype=float)
                self.new_spectrum.emit(wl, counts)
            except Exception:
                pass
            time.sleep(max(0.01, ms / 1000.0))

    def _do_sweep(self, wl):
        pwms, peaks = [], []
        for pwm in range(0, 256, 8):
            _move_servo(self._ctrl, pwm)
            time.sleep(0.3)
            try:
                counts = np.array(self._usb.read_intensity(), dtype=float)
                peaks.append(float(np.mean(np.sort(counts)[-20:])))
            except Exception:
                peaks.append(0.0)
            pwms.append(pwm)
        self.sweep_done.emit(np.array(pwms), np.array(peaks))


# ── Main window ───────────────────────────────────────────────────────────────

class LiveProbe(QMainWindow):

    _servo_move_signal = Signal(int)   # thread-safe servo move from slider

    def __init__(self, ctrl_hal, usb, serial: str, positions: dict | None):
        super().__init__()
        self._ctrl = ctrl_hal
        self._usb  = usb
        self._serial = serial
        self._positions = positions or {}
        self._active_leds: list[str] = []
        self._intensity = 100
        self._servo_pwm = 128
        self._frozen = False

        self.setWindowTitle(f"Live Optical Probe — {serial}")
        self.resize(1100, 620)

        self._build_ui()
        self._setup_worker()

        # Servo moves happen on a timer to debounce slider drags
        self._servo_timer = QTimer(self)
        self._servo_timer.setSingleShot(True)
        self._servo_timer.timeout.connect(self._do_servo_move)
        self._pending_servo_pwm: int | None = None

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Left: plots ───────────────────────────────────────────────────────
        plots_col = QVBoxLayout()
        plots_col.setSpacing(6)

        # Spectrum plot
        pg.setConfigOptions(antialias=True)
        self._spectrum_plot = pg.PlotWidget(title="Live Spectrum")
        self._spectrum_plot.setLabel("left", "Counts")
        self._spectrum_plot.setLabel("bottom", "Wavelength (nm)")
        self._spectrum_plot.setBackground("#1C1C1E")
        self._spectrum_plot.showGrid(x=True, y=True, alpha=0.2)
        self._spectrum_curve = self._spectrum_plot.plot(pen=pg.mkPen("#30D158", width=1.5))
        # SPR region marker 560–720 nm
        spr_region = pg.LinearRegionItem([560, 720], movable=False,
                                          brush=pg.mkBrush(255, 200, 0, 25))
        self._spectrum_plot.addItem(spr_region)
        self._spectrum_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plots_col.addWidget(self._spectrum_plot, 3)

        # Peak bar + label
        peak_row = QHBoxLayout()
        peak_lbl = QLabel("Peak:")
        peak_lbl.setFixedWidth(36)
        self._peak_bar = QProgressBar()
        self._peak_bar.setRange(0, 65535)
        self._peak_bar.setTextVisible(False)
        self._peak_bar.setFixedHeight(16)
        self._peak_bar.setStyleSheet(
            "QProgressBar::chunk { background: #30D158; } QProgressBar { border: none; background: #2C2C2E; border-radius: 4px; }"
        )
        self._peak_label = QLabel("0")
        self._peak_label.setFixedWidth(70)
        self._peak_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bold = QFont(); bold.setBold(True); bold.setPointSize(11)
        self._peak_label.setFont(bold)
        peak_row.addWidget(peak_lbl)
        peak_row.addWidget(self._peak_bar, 1)
        peak_row.addWidget(self._peak_label)
        plots_col.addLayout(peak_row)

        # Sweep profile plot (hidden until sweep runs)
        self._sweep_plot = pg.PlotWidget(title="Servo Sweep — peak counts vs PWM")
        self._sweep_plot.setLabel("left", "Peak counts (top-20 avg)")
        self._sweep_plot.setLabel("bottom", "Servo PWM")
        self._sweep_plot.setBackground("#1C1C1E")
        self._sweep_plot.showGrid(x=True, y=True, alpha=0.2)
        self._sweep_curve  = self._sweep_plot.plot(pen=pg.mkPen("#FF9F0A", width=2),
                                                    symbol="o", symbolSize=5,
                                                    symbolBrush="#FF9F0A")
        self._sweep_s_line = pg.InfiniteLine(angle=90, movable=False,
                                              pen=pg.mkPen("#0A84FF", width=1.5, style=Qt.PenStyle.DashLine))
        self._sweep_p_line = pg.InfiniteLine(angle=90, movable=False,
                                              pen=pg.mkPen("#FF453A", width=1.5, style=Qt.PenStyle.DashLine))
        self._sweep_plot.addItem(self._sweep_s_line)
        self._sweep_plot.addItem(self._sweep_p_line)
        self._sweep_plot.hide()
        self._sweep_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plots_col.addWidget(self._sweep_plot, 2)

        root.addLayout(plots_col, 1)

        # ── Right: controls ───────────────────────────────────────────────────
        ctrl_col = QVBoxLayout()
        ctrl_col.setSpacing(10)
        ctrl_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- LED group ---
        led_grp = QGroupBox("LEDs")
        led_layout = QVBoxLayout(led_grp)
        led_layout.setSpacing(4)

        ch_row = QHBoxLayout()
        self._led_btns: dict[str, QPushButton] = {}
        for ch in ["A", "B", "C", "D"]:
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setFixedSize(40, 32)
            btn.clicked.connect(lambda checked, c=ch.lower(): self._on_led_toggle(c))
            self._led_btns[ch.lower()] = btn
            ch_row.addWidget(btn)
        led_layout.addLayout(ch_row)

        all_row = QHBoxLayout()
        btn_all = QPushButton("ALL ON")
        btn_all.setFixedHeight(28)
        btn_all.clicked.connect(self._on_all_on)
        btn_off = QPushButton("ALL OFF")
        btn_off.setFixedHeight(28)
        btn_off.clicked.connect(self._on_all_off)
        all_row.addWidget(btn_all)
        all_row.addWidget(btn_off)
        led_layout.addLayout(all_row)

        # Intensity
        int_row = QHBoxLayout()
        int_row.addWidget(QLabel("Intensity"))
        self._int_slider = QSlider(Qt.Orientation.Horizontal)
        self._int_slider.setRange(1, 255)
        self._int_slider.setValue(100)
        self._int_slider.valueChanged.connect(self._on_intensity_changed)
        int_row.addWidget(self._int_slider, 1)
        self._int_val_lbl = QLabel("100")
        self._int_val_lbl.setFixedWidth(30)
        int_row.addWidget(self._int_val_lbl)
        led_layout.addLayout(int_row)

        ctrl_col.addWidget(led_grp)

        # --- Integration time ---
        integ_grp = QGroupBox("Integration time")
        integ_layout = QHBoxLayout(integ_grp)
        self._integ_slider = QSlider(Qt.Orientation.Horizontal)
        self._integ_slider.setRange(45, 600)   # × 0.1 ms → 4.5–60 ms
        self._integ_slider.setValue(100)
        self._integ_slider.valueChanged.connect(self._on_integ_changed)
        integ_layout.addWidget(self._integ_slider, 1)
        self._integ_lbl = QLabel("10.0 ms")
        self._integ_lbl.setFixedWidth(56)
        integ_layout.addWidget(self._integ_lbl)
        ctrl_col.addWidget(integ_grp)

        # --- Servo group ---
        servo_grp = QGroupBox("Servo polarizer")
        servo_layout = QVBoxLayout(servo_grp)
        servo_layout.setSpacing(4)

        # S / P jump buttons
        sp_row = QHBoxLayout()
        self._btn_s = QPushButton(f"→ S  ({self._positions.get('s', '?')} PWM)")
        self._btn_p = QPushButton(f"→ P  ({self._positions.get('p', '?')} PWM)")
        self._btn_s.setFixedHeight(30)
        self._btn_p.setFixedHeight(30)
        self._btn_s.setEnabled(bool(self._positions))
        self._btn_p.setEnabled(bool(self._positions))
        self._btn_s.clicked.connect(lambda: self._jump_servo(self._positions["s"]))
        self._btn_p.clicked.connect(lambda: self._jump_servo(self._positions["p"]))
        sp_row.addWidget(self._btn_s)
        sp_row.addWidget(self._btn_p)
        servo_layout.addLayout(sp_row)

        # PWM slider
        pwm_row = QHBoxLayout()
        pwm_row.addWidget(QLabel("PWM"))
        self._servo_slider = QSlider(Qt.Orientation.Horizontal)
        self._servo_slider.setRange(0, 255)
        self._servo_slider.setValue(128)
        self._servo_slider.valueChanged.connect(self._on_servo_slider)
        pwm_row.addWidget(self._servo_slider, 1)
        self._servo_lbl = QLabel("128")
        self._servo_lbl.setFixedWidth(30)
        pwm_row.addWidget(self._servo_lbl)
        servo_layout.addLayout(pwm_row)

        # Sweep
        self._btn_sweep = QPushButton("Run Sweep (0→255)")
        self._btn_sweep.setFixedHeight(30)
        self._btn_sweep.clicked.connect(self._on_sweep)
        servo_layout.addWidget(self._btn_sweep)

        ctrl_col.addWidget(servo_grp)

        # --- Freeze / status ---
        misc_grp = QGroupBox("View")
        misc_layout = QVBoxLayout(misc_grp)
        self._btn_freeze = QPushButton("⏸  Freeze")
        self._btn_freeze.setCheckable(True)
        self._btn_freeze.setFixedHeight(30)
        self._btn_freeze.toggled.connect(self._on_freeze)
        misc_layout.addWidget(self._btn_freeze)

        self._status_lbl = QLabel("Connecting…")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        misc_layout.addWidget(self._status_lbl)
        ctrl_col.addWidget(misc_grp)

        ctrl_col.addStretch()
        ctrl_frame = QWidget()
        ctrl_frame.setFixedWidth(220)
        ctrl_frame.setLayout(ctrl_col)
        root.addWidget(ctrl_frame)

        # Style
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1C1C1E; color: #F5F5F7; }
            QGroupBox { border: 1px solid #3A3A3C; border-radius: 8px; margin-top: 8px;
                        font-weight: 600; font-size: 12px; padding: 6px 4px 4px 4px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; top: -1px; }
            QPushButton { background: #2C2C2E; border: 1px solid #3A3A3C;
                          border-radius: 6px; padding: 2px 6px; }
            QPushButton:hover { background: #3A3A3C; }
            QPushButton:checked { background: #0A84FF; border-color: #0A84FF; }
            QSlider::groove:horizontal { height: 4px; background: #3A3A3C; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0;
                                         background: #F5F5F7; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #0A84FF; border-radius: 2px; }
            QLabel { font-size: 12px; }
        """)

    # ── Worker setup ──────────────────────────────────────────────────────────

    def _setup_worker(self):
        self._worker = _AcqWorker(self._ctrl, self._usb)
        self._worker.new_spectrum.connect(self._on_spectrum)
        self._worker.sweep_done.connect(self._on_sweep_done)
        self._worker.start()
        self._status_lbl.setText(f"Live  |  {self._serial}")

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_spectrum(self, wl, counts):
        self._spectrum_curve.setData(wl, counts)
        peak = float(counts.max())
        self._peak_bar.setValue(min(65535, int(peak)))
        pct = peak / 65535 * 100
        color = "#30D158" if pct > 10 else ("#FF9F0A" if pct > 3 else "#FF453A")
        self._peak_label.setText(f"{peak:,.0f}")
        self._peak_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_sweep_done(self, pwms, peaks):
        self._sweep_curve.setData(pwms, peaks)
        if self._positions.get("s") is not None:
            self._sweep_s_line.setValue(self._positions["s"])
        if self._positions.get("p") is not None:
            self._sweep_p_line.setValue(self._positions["p"])
        self._sweep_plot.show()
        self._btn_sweep.setEnabled(True)
        self._btn_sweep.setText("Run Sweep (0→255)")
        self._status_lbl.setText(f"Sweep done  |  {self._serial}")
        # Re-enable live
        self._worker.set_frozen(self._frozen)

    def _on_led_toggle(self, ch: str):
        if ch in self._active_leds:
            self._active_leds.remove(ch)
        else:
            self._active_leds.append(ch)
        self._apply_leds()

    def _on_all_on(self):
        self._active_leds = ["a", "b", "c", "d"]
        for btn in self._led_btns.values():
            btn.setChecked(True)
        self._apply_leds()

    def _on_all_off(self):
        self._active_leds = []
        for btn in self._led_btns.values():
            btn.setChecked(False)
        self._apply_leds()

    def _apply_leds(self):
        for ch, btn in self._led_btns.items():
            btn.setChecked(ch in self._active_leds)
        threading.Thread(target=_set_leds, args=(self._ctrl, self._active_leds, self._intensity),
                         daemon=True).start()

    def _on_intensity_changed(self, val: int):
        self._intensity = val
        self._int_val_lbl.setText(str(val))
        if self._active_leds:
            threading.Thread(target=_set_leds, args=(self._ctrl, self._active_leds, val),
                             daemon=True).start()

    def _on_integ_changed(self, val: int):
        ms = val / 10.0
        self._integ_lbl.setText(f"{ms:.1f} ms")
        threading.Thread(target=self._worker.set_integration, args=(ms,), daemon=True).start()

    def _on_servo_slider(self, val: int):
        self._servo_lbl.setText(str(val))
        self._pending_servo_pwm = val
        self._servo_timer.start(80)   # debounce 80 ms

    def _do_servo_move(self):
        if self._pending_servo_pwm is not None:
            pwm = self._pending_servo_pwm
            threading.Thread(target=_move_servo, args=(self._ctrl, pwm), daemon=True).start()

    def _jump_servo(self, pwm: int):
        self._servo_slider.setValue(pwm)   # triggers _on_servo_slider

    def _on_freeze(self, checked: bool):
        self._frozen = checked
        self._worker.set_frozen(checked)
        self._btn_freeze.setText("▶  Resume" if checked else "⏸  Freeze")

    def _on_sweep(self):
        self._btn_sweep.setEnabled(False)
        self._btn_sweep.setText("Sweeping…")
        self._worker.set_frozen(True)   # pause live during sweep
        self._worker.request_sweep()
        self._status_lbl.setText("Running sweep…")

    def closeEvent(self, event):
        self._worker.stop()
        _set_leds(self._ctrl, [], 0)
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Live Optical Probe")
    print("=" * 40)
    print("Connecting hardware...")
    try:
        ctrl_hal, usb, serial = _connect_hardware()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    positions = _load_servo_positions(serial)
    if positions:
        print(f"  Saved positions: S={positions['s']} PWM, P={positions['p']} PWM")
    else:
        print("  No saved servo positions (run oem_calibrate first, or use slider to explore)")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Live Optical Probe")

    win = LiveProbe(ctrl_hal, usb, serial, positions)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
