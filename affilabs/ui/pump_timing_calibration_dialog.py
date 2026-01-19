"""Dialog for automated pump timing calibration.

Runs automated test injections to synchronize pump arrival times at the detector
by calculating and applying correction factors for KC1 and KC2 pumps.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QDialogButtonBox,
    QMessageBox,
)

if TYPE_CHECKING:
    from affilabs.utils.controller import Controller

from affilabs.utils.logger import logger


class CalibrationWorker(QThread):
    """Background thread for running timing calibration tests."""
    
    progress_updated = Signal(int)  # Progress percentage
    log_updated = Signal(str)  # Log message
    test_completed = Signal(str, dict)  # Test name, results dict
    calibration_finished = Signal(bool, dict)  # Success, results
    
    def __init__(self, controller: Controller):
        super().__init__()
        self.controller = controller
        self._should_stop = False
    
    def stop(self):
        """Request calibration to stop."""
        self._should_stop = True
    
    def run(self):
        """Run the calibration procedure."""
        try:
            self.log_updated.emit("🔄 Starting pump timing calibration...\n")
            
            # Import detector adapter
            from affilabs.utils.ocean_spectrometer_adapter import OceanSpectrometerAdapter
            
            # Initialize detector
            self.log_updated.emit("📡 Opening detector...")
            detector = OceanSpectrometerAdapter()
            if not detector.open():
                self.log_updated.emit("❌ ERROR: Could not open detector\n")
                self.calibration_finished.emit(False, {})
                return
            
            self.log_updated.emit("✓ Detector opened\n")
            detector.set_integration(100)
            
            # Test parameters
            test_rpm = 50
            purge_duration = 120  # 2 minutes in seconds
            contact_time = 10  # seconds
            baseline_wait = 120  # 2 minutes
            
            results = {}
            
            # === KC1 TEST ===
            if self._should_stop:
                detector.close()
                self.calibration_finished.emit(False, {})
                return
                
            self.progress_updated.emit(10)
            self.log_updated.emit("\n" + "="*60 + "\n")
            self.log_updated.emit("🔵 KC1 (Pump 1) Timing Test\n")
            self.log_updated.emit("="*60 + "\n")
            
            # Pre-purge
            self.log_updated.emit(f"\n🧹 Pre-test purge at 250 RPM for {purge_duration}s...")
            self.controller.knx_six_both(state=0)
            time.sleep(1)
            self.controller.pump_start(rate_ul_min=250, ch=1)
            
            for i in range(purge_duration):
                if self._should_stop:
                    self.controller.pump_stop(ch=1)
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                time.sleep(1)
                if i % 10 == 0:
                    self.log_updated.emit(".")
            
            self.controller.pump_stop(ch=1)
            self.log_updated.emit(" Done!\n")
            self.progress_updated.emit(20)
            
            # Baseline measurement
            self.log_updated.emit(f"\n📊 Measuring baseline for {baseline_wait}s...\n")
            time.sleep(baseline_wait)
            baseline = np.mean([detector.read_intensity() for _ in range(10)])
            threshold = baseline * 1.05
            self.log_updated.emit(f"✓ Baseline: {baseline:.1f}, Threshold: {threshold:.1f}\n")
            self.progress_updated.emit(30)
            
            # Start pump and wait for loop fill
            self.log_updated.emit(f"\n💧 Starting pump at {test_rpm} RPM (15s loop fill)...\n")
            self.controller.pump_start(rate_ul_min=test_rpm, ch=1)
            time.sleep(15)
            
            # Open valves to inject
            self.log_updated.emit(f"🚪 Opening valves for {contact_time}s injection...\n")
            self.controller.knx_six_both(state=1)
            time.sleep(contact_time)
            
            # Close valves
            self.log_updated.emit("🚪 Closing valves...\n")
            self.controller.knx_six_both(state=0)
            self.controller.pump_stop(ch=1)
            self.progress_updated.emit(40)
            
            # Monitor for arrival on all 4 channels
            self.log_updated.emit("\n🔍 Monitoring all 4 channels for sample arrival...\n")
            arrivals = {'A': None, 'B': None, 'C': None, 'D': None}
            start_time = time.time()
            consecutive_hits = {ch: 0 for ch in arrivals}
            
            while time.time() - start_time < 600:  # 10 minute timeout
                if self._should_stop:
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                    
                readings = detector.read_intensity()
                elapsed = time.time() - start_time
                
                for i, ch in enumerate(['A', 'B', 'C', 'D']):
                    if arrivals[ch] is None:
                        if readings[i] > threshold:
                            consecutive_hits[ch] += 1
                            if consecutive_hits[ch] >= 10:
                                arrivals[ch] = elapsed
                                self.log_updated.emit(f"✓ Channel {ch} arrival at {elapsed:.1f}s\n")
                        else:
                            consecutive_hits[ch] = 0
                
                if all(v is not None for v in arrivals.values()):
                    break
                    
                time.sleep(0.1)
            
            results['kc1'] = arrivals
            self.log_updated.emit(f"\n✓ KC1 test complete: {arrivals}\n")
            self.test_completed.emit("KC1", arrivals)
            self.progress_updated.emit(50)
            
            # === FINAL PURGE ===
            self.log_updated.emit(f"\n🧹 Final purge at 250 RPM for {purge_duration}s with valves open...")
            self.controller.knx_six_both(state=1)
            self.controller.pump_start(rate_ul_min=250, ch=1)
            
            for i in range(purge_duration):
                if self._should_stop:
                    self.controller.pump_stop(ch=1)
                    self.controller.knx_six_both(state=0)
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                time.sleep(1)
                if i % 10 == 0:
                    self.log_updated.emit(".")
            
            self.controller.pump_stop(ch=1)
            self.controller.knx_six_both(state=0)
            self.log_updated.emit(" Done!\n")
            self.progress_updated.emit(60)
            
            # === KC2 TEST ===
            if self._should_stop:
                detector.close()
                self.calibration_finished.emit(False, {})
                return
                
            self.log_updated.emit("\n" + "="*60 + "\n")
            self.log_updated.emit("🔴 KC2 (Pump 2) Timing Test\n")
            self.log_updated.emit("="*60 + "\n")
            
            # Pre-purge
            self.log_updated.emit(f"\n🧹 Pre-test purge at 250 RPM for {purge_duration}s...")
            self.controller.knx_six_both(state=0)
            time.sleep(1)
            self.controller.pump_start(rate_ul_min=250, ch=2)
            
            for i in range(purge_duration):
                if self._should_stop:
                    self.controller.pump_stop(ch=2)
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                time.sleep(1)
                if i % 10 == 0:
                    self.log_updated.emit(".")
            
            self.controller.pump_stop(ch=2)
            self.log_updated.emit(" Done!\n")
            self.progress_updated.emit(70)
            
            # Baseline measurement
            self.log_updated.emit(f"\n📊 Measuring baseline for {baseline_wait}s...\n")
            time.sleep(baseline_wait)
            baseline = np.mean([detector.read_intensity() for _ in range(10)])
            threshold = baseline * 1.05
            self.log_updated.emit(f"✓ Baseline: {baseline:.1f}, Threshold: {threshold:.1f}\n")
            self.progress_updated.emit(80)
            
            # Start pump and wait for loop fill
            self.log_updated.emit(f"\n💧 Starting pump at {test_rpm} RPM (15s loop fill)...\n")
            self.controller.pump_start(rate_ul_min=test_rpm, ch=2)
            time.sleep(15)
            
            # Open valves to inject
            self.log_updated.emit(f"🚪 Opening valves for {contact_time}s injection...\n")
            self.controller.knx_six_both(state=1)
            time.sleep(contact_time)
            
            # Close valves
            self.log_updated.emit("🚪 Closing valves...\n")
            self.controller.knx_six_both(state=0)
            self.controller.pump_stop(ch=2)
            self.progress_updated.emit(90)
            
            # Monitor for arrival on all 4 channels
            self.log_updated.emit("\n🔍 Monitoring all 4 channels for sample arrival...\n")
            arrivals = {'A': None, 'B': None, 'C': None, 'D': None}
            start_time = time.time()
            consecutive_hits = {ch: 0 for ch in arrivals}
            
            while time.time() - start_time < 600:  # 10 minute timeout
                if self._should_stop:
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                    
                readings = detector.read_intensity()
                elapsed = time.time() - start_time
                
                for i, ch in enumerate(['A', 'B', 'C', 'D']):
                    if arrivals[ch] is None:
                        if readings[i] > threshold:
                            consecutive_hits[ch] += 1
                            if consecutive_hits[ch] >= 10:
                                arrivals[ch] = elapsed
                                self.log_updated.emit(f"✓ Channel {ch} arrival at {elapsed:.1f}s\n")
                        else:
                            consecutive_hits[ch] = 0
                
                if all(v is not None for v in arrivals.values()):
                    break
                    
                time.sleep(0.1)
            
            results['kc2'] = arrivals
            self.log_updated.emit(f"\n✓ KC2 test complete: {arrivals}\n")
            self.test_completed.emit("KC2", arrivals)
            
            # Final purge
            self.log_updated.emit(f"\n🧹 Final purge at 250 RPM for {purge_duration}s with valves open...")
            self.controller.knx_six_both(state=1)
            self.controller.pump_start(rate_ul_min=250, ch=2)
            
            for i in range(purge_duration):
                if self._should_stop:
                    self.controller.pump_stop(ch=2)
                    self.controller.knx_six_both(state=0)
                    detector.close()
                    self.calibration_finished.emit(False, {})
                    return
                time.sleep(1)
                if i % 10 == 0:
                    self.log_updated.emit(".")
            
            self.controller.pump_stop(ch=2)
            self.controller.knx_six_both(state=0)
            self.log_updated.emit(" Done!\n")
            
            # Cleanup
            detector.close()
            self.log_updated.emit("\n✅ Calibration complete!\n")
            
            # Calculate corrections if both tests succeeded
            if 'kc1' in results and 'kc2' in results:
                self.log_updated.emit("\n📊 Calculating timing corrections...\n")
                # Use first detected channel arrival time from each test
                kc1_times = [t for t in results['kc1'].values() if t is not None]
                kc2_times = [t for t in results['kc2'].values() if t is not None]
                
                if kc1_times and kc2_times:
                    kc1_avg = np.mean(kc1_times)
                    kc2_avg = np.mean(kc2_times)
                    self.log_updated.emit(f"KC1 average arrival: {kc1_avg:.1f}s\n")
                    self.log_updated.emit(f"KC2 average arrival: {kc2_avg:.1f}s\n")
                    
                    # Calculate correction factors
                    if kc1_avg > kc2_avg:
                        # KC1 is slower, needs to speed up
                        kc1_correction = 1.0
                        kc2_correction = kc2_avg / kc1_avg
                    else:
                        # KC2 is slower, needs to speed up
                        kc1_correction = kc1_avg / kc2_avg
                        kc2_correction = 1.0
                    
                    results['corrections'] = {
                        'kc1': kc1_correction,
                        'kc2': kc2_correction
                    }
                    
                    self.log_updated.emit(f"\n✨ Suggested correction factors:\n")
                    self.log_updated.emit(f"   KC1: {kc1_correction:.3f}\n")
                    self.log_updated.emit(f"   KC2: {kc2_correction:.3f}\n")
            
            self.progress_updated.emit(100)
            self.calibration_finished.emit(True, results)
            
        except Exception as e:
            logger.exception(f"Calibration error: {e}")
            self.log_updated.emit(f"\n❌ ERROR: {e}\n")
            self.calibration_finished.emit(False, {})


class PumpTimingCalibrationDialog(QDialog):
    """Dialog for running automated pump timing calibration."""
    
    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.worker = None
        self.results = {}
        
        self.setWindowTitle("Pump Timing Calibration")
        self.setMinimumSize(700, 600)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("⏱ Automated Pump Timing Calibration")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #1D1D1F; padding: 8px;"
        )
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "This calibration will automatically test both pumps and calculate\n"
            "correction factors to synchronize their arrival times at the detector.\n\n"
            "⚠ Ensure sample vial is filled with calibration solution before starting."
        )
        desc.setStyleSheet("color: #86868B; padding: 4px;")
        layout.addWidget(desc)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "  border: 1px solid rgba(0, 0, 0, 0.12);"
            "  border-radius: 6px;"
            "  text-align: center;"
            "  background: white;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "    stop:0 #5856D6, stop:1 #007AFF);"
            "  border-radius: 5px;"
            "}"
        )
        layout.addWidget(self.progress_bar)
        
        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "QTextEdit {"
            "  background: #F5F5F7;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 8px;"
            "  font-family: 'SF Mono', 'Consolas', monospace;"
            "  font-size: 12px;"
            "}"
        )
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.start_btn = QPushButton("▶ Start Calibration")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(
            "QPushButton {"
            "  background: #34C759;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  padding: 0px 24px;"
            "}"
            "QPushButton:hover { background: #28A745; }"
            "QPushButton:pressed { background: #1E7E34; }"
            "QPushButton:disabled { background: #D1D1D6; }"
        )
        self.start_btn.clicked.connect(self._start_calibration)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  padding: 0px 24px;"
            "}"
            "QPushButton:hover { background: #D32F2F; }"
            "QPushButton:pressed { background: #B71C1C; }"
            "QPushButton:disabled { background: #D1D1D6; }"
        )
        self.stop_btn.clicked.connect(self._stop_calibration)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #007AFF;"
            "  border: 1.5px solid #007AFF;"
            "  border-radius: 8px;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  padding: 0px 24px;"
            "}"
            "QPushButton:hover { background: rgba(0, 122, 255, 0.08); }"
            "QPushButton:pressed { background: rgba(0, 122, 255, 0.15); }"
        )
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _start_calibration(self):
        """Start the calibration process."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # Create and start worker thread
        self.worker = CalibrationWorker(self.controller)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.log_updated.connect(self._append_log)
        self.worker.test_completed.connect(self._on_test_completed)
        self.worker.calibration_finished.connect(self._on_calibration_finished)
        self.worker.start()
    
    def _stop_calibration(self):
        """Stop the calibration process."""
        if self.worker and self.worker.isRunning():
            self._append_log("\n⏹ Stopping calibration...\n")
            self.worker.stop()
            self.worker.wait()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
    
    def _append_log(self, message: str):
        """Append message to log output."""
        self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)
        self.log_text.insertPlainText(message)
        self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)
    
    def _on_test_completed(self, test_name: str, arrivals: dict):
        """Handle individual test completion."""
        logger.info(f"{test_name} test completed: {arrivals}")
    
    def _on_calibration_finished(self, success: bool, results: dict):
        """Handle calibration completion."""
        self.results = results
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        
        if success and 'corrections' in results:
            # Ask if user wants to apply corrections
            reply = QMessageBox.question(
                self,
                "Apply Corrections?",
                f"Calibration complete!\n\n"
                f"Suggested correction factors:\n"
                f"  KC1: {results['corrections']['kc1']:.3f}\n"
                f"  KC2: {results['corrections']['kc2']:.3f}\n\n"
                f"Apply these corrections to the pumps?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                kc1 = results['corrections']['kc1']
                kc2 = results['corrections']['kc2']
                
                if self.controller.set_pump_corrections(kc1, kc2):
                    self._append_log(f"\n✅ Corrections applied successfully!\n")
                    QMessageBox.information(
                        self,
                        "Success",
                        "Pump timing corrections have been applied!"
                    )
                    self.accept()
                else:
                    self._append_log(f"\n❌ Failed to apply corrections\n")
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to apply corrections to controller."
                    )
        elif not success:
            QMessageBox.warning(
                self,
                "Calibration Failed",
                "Calibration did not complete successfully.\nCheck the log for details."
            )
    
    def closeEvent(self, event):
        """Handle dialog close."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Calibration Running",
                "Calibration is still running. Stop and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
