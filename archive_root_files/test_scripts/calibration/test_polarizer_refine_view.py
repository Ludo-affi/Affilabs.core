"""Live view for Polarizer Calibration Steps 3 and 4

- Step 3: Refine S position (coarse/fine/ultra-fine) and plot intensity vs angle
- Step 4: Evaluate P candidates at S±90 and plot intensity vs angle

This uses existing hardware managers and plots results live similar to test_calibration_live_view.
"""

import sys
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Add project src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from core.hardware_manager import HardwareManager

from utils.logger import logger


class PolarizerRefineLive(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Polarizer Calibration Live - Steps 3 & 4")
        self.resize(1200, 800)

        self.hardware_mgr = None
        self.usb = None
        self.ctrl = None
        self._ready = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Controls
        ctrl_group = QGroupBox("Controls")
        ctrl_layout = QHBoxLayout(ctrl_group)
        self.connect_btn = QPushButton("Connect Hardware")
        self.connect_btn.clicked.connect(self._connect_hardware)
        ctrl_layout.addWidget(self.connect_btn)

        self.run_step3_btn = QPushButton("Run Step 3 (Refine S)")
        self.run_step3_btn.setEnabled(False)
        self.run_step3_btn.clicked.connect(self._run_step3)
        ctrl_layout.addWidget(self.run_step3_btn)

        self.run_step4_btn = QPushButton("Run Step 4 (Evaluate P)")
        self.run_step4_btn.setEnabled(False)
        self.run_step4_btn.clicked.connect(self._run_step4)
        ctrl_layout.addWidget(self.run_step4_btn)

        self.status_label = QLabel("Disconnected")
        ctrl_layout.addWidget(self.status_label)

        layout.addWidget(ctrl_group)

        # Plots
        self.plot_step3 = pg.PlotWidget(title="Step 3: S-mode Intensity vs Angle")
        self.plot_step3.setLabel("left", "Intensity", units="counts")
        self.plot_step3.setLabel("bottom", "Angle", units="deg")
        self.plot_step3.showGrid(x=True, y=True, alpha=0.3)
        self.plot_step3.setBackground("w")
        self.curve_step3 = self.plot_step3.plot(pen=pg.mkPen(color="g", width=2))
        layout.addWidget(self.plot_step3)

        self.plot_step4 = pg.PlotWidget(
            title="Step 4: P-mode Intensity vs Angle (S±90 candidates)",
        )
        self.plot_step4.setLabel("left", "Intensity", units="counts")
        self.plot_step4.setLabel("bottom", "Angle", units="deg")
        self.plot_step4.showGrid(x=True, y=True, alpha=0.3)
        self.plot_step4.setBackground("w")
        self.curve_step4 = self.plot_step4.plot(pen=pg.mkPen(color="m", width=2))
        layout.addWidget(self.plot_step4)

        self._angles3 = []
        self._intens3 = []
        self._angles4 = []
        self._intens4 = []

    def _connect_hardware(self):
        try:
            self.status_label.setText("Connecting...")
            self.hardware_mgr = HardwareManager()

            def on_connected(info):
                self.ctrl = self.hardware_mgr.ctrl
                self.usb = self.hardware_mgr.usb
                if not self.ctrl or not self.usb:
                    self.status_label.setText(
                        "Error: Missing controller or spectrometer",
                    )
                    return
                self._ready = True
                self.status_label.setText("Connected")
                self.run_step3_btn.setEnabled(True)
                self.run_step4_btn.setEnabled(True)

            def on_progress(msg):
                logger.info(msg)

            def on_error(msg):
                self.status_label.setText(f"Error: {msg}")

            self.hardware_mgr.connection_progress.connect(on_progress)
            self.hardware_mgr.hardware_connected.connect(on_connected)
            self.hardware_mgr.error_occurred.connect(on_error)
            self.hardware_mgr.scan_and_connect()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _measure_at_angle(self, angle_deg: int, mode: str) -> float:
        try:
            # Move and settle
            self.ctrl.set_mode(mode)
            self.ctrl.servo_set(int(angle_deg), int(angle_deg))
            import time as _t

            _t.sleep(0.3)
            # Read spectrum and compute mean across ROI buckets
            spectrum = self.usb.read_intensity()
            if spectrum is None:
                return 0.0
            # Use mean intensity as proxy
            return float(np.mean(spectrum))
        except Exception:
            return 0.0

    def _run_step3(self):
        if not self._ready:
            return
        self._angles3.clear()
        self._intens3.clear()
        # Coarse candidates around mid-range
        candidates = [20, 50, 80, 110, 140, 170]
        self.ctrl.set_mode("s")
        for ang in candidates:
            inten = self._measure_at_angle(ang, "s")
            self._angles3.append(ang)
            self._intens3.append(inten)
            self.curve_step3.setData(self._angles3, self._intens3)
            QApplication.processEvents()
        # Pick best S and refine around it
        if self._intens3:
            best_idx = int(np.argmax(self._intens3))
            best_s = self._angles3[best_idx]
            refine = [
                max(0, best_s - 14),
                best_s,
                min(180, best_s + 14),
                max(0, best_s - 7),
                min(180, best_s + 7),
                max(0, best_s - 3),
                min(180, best_s + 3),
            ]
            for ang in refine:
                inten = self._measure_at_angle(ang, "s")
                self._angles3.append(ang)
                self._intens3.append(inten)
                self.curve_step3.setData(self._angles3, self._intens3)
                QApplication.processEvents()

    def _run_step4(self):
        if not self._ready:
            return
        self._angles4.clear()
        self._intens4.clear()
        # Estimate S from step3 data if available
        if self._intens3:
            best_idx = int(np.argmax(self._intens3))
            s_est = self._angles3[best_idx]
        else:
            s_est = 90
        # Evaluate P candidates at S±90 and small vicinity
        candidates = [max(0, s_est - 90), min(180, s_est + 90)]
        self.ctrl.set_mode("p")
        for base in candidates:
            for delta in [-3, 0, 3]:
                ang = max(0, min(180, base + delta))
                inten = self._measure_at_angle(ang, "p")
                self._angles4.append(ang)
                self._intens4.append(inten)
                self.curve_step4.setData(self._angles4, self._intens4)
                QApplication.processEvents()


def main():
    app = QApplication(sys.argv)
    w = PolarizerRefineLive()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
