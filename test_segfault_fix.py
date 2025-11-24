"""
Test to reproduce and fix the segfault crash
This simulates the exact sequence: Qt window -> calibration -> worker thread startup
"""
import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')

import time
import threading
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QDialog, QLabel
from PySide6.QtCore import QTimer, Signal, QObject

print("="*70)
print("SEGFAULT REPRODUCTION TEST")
print("="*70)

# Import real managers
from core.hardware_manager import HardwareManager
from core.data_acquisition_manager import DataAcquisitionManager

class FakeCalibrationDialog(QDialog):
    """Simulate calibration dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fake Calibration")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Calibration dialog"))
        self.setLayout(layout)

class TestWindow(QMainWindow):
    """Minimal window to simulate the real app"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Segfault Test")
        self.setGeometry(100, 100, 400, 200)
        
        # Create simple UI
        central = QWidget()
        layout = QVBoxLayout()
        
        self.status_label = QPushButton("Click to start test")
        self.status_label.clicked.connect(self.run_test)
        layout.addWidget(self.status_label)
        
        central.setLayout(layout)
        self.setCentralWidget(central)
        
    def run_test(self):
        self.status_label.setText("Test running...")
        QTimer.singleShot(100, self.start_acquisition_test)
        
    def start_acquisition_test(self):
        print("\n[TEST] Starting acquisition simulation...")
        
        # This is what happens in the real app
        print("[1] Creating hardware manager...")
        self.hardware_mgr = HardwareManager()
        
        print("[2] Scanning hardware...")
        self.scan_complete = threading.Event()
        
        def on_connected(status):
            print(f"[3] Hardware connected: {status.get('spectrometer_serial')}")
            self.scan_complete.set()
            
        self.hardware_mgr.hardware_connected.connect(on_connected)
        self.hardware_mgr.scan_and_connect()
        
        # Wait for scan with event processing
        def check_scan():
            if self.scan_complete.is_set():
                self.after_scan()
            else:
                QTimer.singleShot(100, check_scan)
                
        QTimer.singleShot(100, check_scan)
        
    def after_scan(self):
        print("[4] Creating data acquisition manager...")
        self.data_mgr = DataAcquisitionManager(self.hardware_mgr)
        
        print("[4b] Setting up spectrum_acquired signal...")
        # This is what the real app does - connects signal
        def on_spectrum_acquired(data):
            print(f"    [SIGNAL] Got spectrum: channel={data.get('channel')}, wave={data.get('wavelength')}")
            
        self.data_mgr.spectrum_acquired.connect(on_spectrum_acquired)
        
        print("[5] Injecting fake calibration...")
        import numpy as np
        self.data_mgr.wave_data = list(range(200, 1100))
        self.data_mgr.leds_calibrated = {'a': 255, 'b': 255, 'c': 255, 'd': 255}
        self.data_mgr.integration_time = 40
        self.data_mgr.num_scans = 5
        fake_spectrum = np.ones(900) * 30000
        self.data_mgr.ref_sig = {'a': fake_spectrum, 'b': fake_spectrum, 
                                   'c': fake_spectrum, 'd': fake_spectrum}
        self.data_mgr.dark_sig = {'a': np.zeros(900), 'b': np.zeros(900), 
                                    'c': np.zeros(900), 'd': np.zeros(900)}
        
        print("[6] Starting acquisition worker...")
        print("    This is where the segfault happens in the real app!")
        print()
        
        # Show a fake calibration dialog
        print("[6b] Showing calibration dialog...")
        self.cal_dialog = FakeCalibrationDialog(self)
        self.cal_dialog.show()
        
        try:
            self.data_mgr.start_acquisition()
            self.status_label.setText("✓ Acquisition started! Watching for crash...")
            
            # Close dialog 100ms after acquisition starts (like real app)
            print("[6c] Scheduling dialog close in 100ms...")
            def close_dialog():
                print("[7] Closing calibration dialog...")
                if self.cal_dialog:
                    self.cal_dialog.close()
                    self.cal_dialog = None
                    print("[7] Dialog closed - waiting for segfault...")
                    
            QTimer.singleShot(100, close_dialog)
            
            # Monitor for 5 seconds
            self.check_count = [0]
            def check_alive():
                self.check_count[0] += 1
                if self.check_count[0] < 50:  # 5 seconds
                    self.status_label.setText(f"✓ Still alive after {self.check_count[0]/10:.1f}s...")
                    QTimer.singleShot(100, check_alive)
                else:
                    self.status_label.setText("TEST PASSED - NO CRASH!")
                    print("\n" + "="*70)
                    print("TEST PASSED - NO SEGFAULT DETECTED")
                    print("="*70)
                    self.data_mgr.stop_acquisition()
                    
            QTimer.singleShot(100, check_alive)
            
        except Exception as e:
            print(f"[ERROR] Exception during start: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"❌ Exception: {e}")

# Create Qt app
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

print("\n[SETUP] Creating test window...")
window = TestWindow()
window.show()

print("[SETUP] Window shown - click button to start test")
print("="*70)

sys.exit(app.exec())
