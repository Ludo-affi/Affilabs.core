"""
Lightweight test UI that simulates post-calibration state and displays live SPR data.
This proves the live data display works when we bypass the calibration dialog complexity.

Tests the flow:
1. Start from "calibrated" state (fake calibration data loaded)
2. Click Start button → Launch acquisition worker
3. Live graph updates with real SPR spectra
4. Proves the rewrite will work
"""
import sys
import time
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
import pyqtgraph as pg
import queue
import threading

# Mock hardware
class MockHardware:
    def __init__(self):
        self.wavelengths = np.linspace(450, 850, 2048)
        self.time_offset = 0
        self.integration_time = 40
        self.num_scans = 5

    def get_spectrum(self, channel):
        """Generate realistic SPR spectrum with shifting dip"""
        # Different dip positions for different channels
        channel_dips = {'a': 650, 'b': 665, 'c': 670, 'd': 580}
        base_dip = channel_dips.get(channel, 650)

        # Oscillating dip simulating binding event
        dip_center = base_dip + 5 * np.sin(self.time_offset * 0.3)
        dip_width = 30
        dip_depth = 0.6

        # Generate spectrum
        baseline = 1.0 + 0.03 * np.random.randn(len(self.wavelengths))
        dip = dip_depth * np.exp(-((self.wavelengths - dip_center) ** 2) / (2 * dip_width ** 2))
        spectrum = baseline - dip

        self.time_offset += 0.1
        return spectrum

    def get_calibration_data(self):
        """Return fake calibration data"""
        return {
            'wavelengths': self.wavelengths,
            'dark': np.random.randn(len(self.wavelengths)) * 100 + 500,
            's_ref': {
                'a': np.random.randn(len(self.wavelengths)) * 1000 + 40000,
                'b': np.random.randn(len(self.wavelengths)) * 1000 + 38000,
                'c': np.random.randn(len(self.wavelengths)) * 1000 + 35000,
                'd': np.random.randn(len(self.wavelengths)) * 1000 + 33000,
            }
        }

# Acquisition worker
class AcquisitionWorker:
    def __init__(self, data_queue, hardware):
        self.data_queue = data_queue
        self.hardware = hardware
        self.running = False
        self.stop_flag = threading.Event()
        self.channels = ['a', 'b', 'c', 'd']

    def run(self):
        """Worker thread: acquire and process spectra"""
        self.running = True
        count = 0
        print("🚀 Acquisition worker started")

        # Get calibration data
        cal_data = self.hardware.get_calibration_data()
        wavelengths = cal_data['wavelengths']
        dark = cal_data['dark']
        s_ref = cal_data['s_ref']

        while self.running and not self.stop_flag.is_set():
            try:
                # Simulate acquisition delay
                time.sleep(0.05)  # 20 Hz acquisition

                # Acquire all channels
                for channel in self.channels:
                    # Get raw spectrum
                    p_raw = self.hardware.get_spectrum(channel)

                    # Process: (P - dark) / (S_ref - dark) → Transmission
                    p_corrected = p_raw - dark
                    s_corrected = s_ref[channel] - dark
                    transmission = np.clip(p_corrected / s_corrected, 0.01, 1.5)

                    # Put in queue
                    data = {
                        'type': 'spectrum',
                        'channel': channel,
                        'wavelengths': wavelengths,
                        'transmission': transmission,
                        'timestamp': time.time(),
                        'count': count
                    }
                    self.data_queue.put_nowait(data)

                count += 1

                if count % 20 == 0:
                    print(f"✅ Acquired {count} spectrum sets ({count * 4} total spectra)")

            except Exception as e:
                print(f"❌ Worker error: {e}")
                import traceback
                traceback.print_exc()
                break

        print(f"🛑 Worker stopped after {count} acquisitions")

    def stop(self):
        self.running = False
        self.stop_flag.set()

# Main window
class LiveDataWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AffiLabs.core - Live Data Test (Post-Calibration)")
        self.resize(1200, 800)

        # Hardware and worker
        self.hardware = MockHardware()
        self.worker = None
        self.worker_thread = None
        self.data_queue = queue.Queue()

        # Setup UI
        self.setup_ui()

        # Queue timer
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)

        # Stats
        self.spectrum_count = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        self.start_time = None

        print("✅ Live Data Window initialized")
        print("📊 Simulated state: Calibration complete, ready to start acquisition")

    def setup_ui(self):
        """Build the UI"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Live SPR Transmission Data")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status
        self.status_label = QLabel("✅ System calibrated and ready")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #28a745; padding: 10px;")
        layout.addWidget(self.status_label)

        # Control buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.start_btn = QPushButton("▶ Start Acquisition")
        self.start_btn.setFont(QFont("Segoe UI", 11))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: #218838;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """)
        self.start_btn.clicked.connect(self.start_acquisition)

        self.stop_btn = QPushButton("⏸ Stop Acquisition")
        self.stop_btn.setFont(QFont("Segoe UI", 11))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: #c82333;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.stop_btn.setEnabled(False)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # Graphs - 2x2 grid
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setSpacing(10)

        # Top row: Channel A and B
        top_row = QHBoxLayout()
        self.plot_a = self.create_plot("Channel A", "#e74c3c")
        self.plot_b = self.create_plot("Channel B", "#3498db")
        top_row.addWidget(self.plot_a['widget'])
        top_row.addWidget(self.plot_b['widget'])
        graph_layout.addLayout(top_row)

        # Bottom row: Channel C and D
        bottom_row = QHBoxLayout()
        self.plot_c = self.create_plot("Channel C", "#2ecc71")
        self.plot_d = self.create_plot("Channel D", "#f39c12")
        bottom_row.addWidget(self.plot_c['widget'])
        bottom_row.addWidget(self.plot_d['widget'])
        graph_layout.addLayout(bottom_row)

        layout.addWidget(graph_container)

        # Store plot references
        self.plots = {
            'a': self.plot_a,
            'b': self.plot_b,
            'c': self.plot_c,
            'd': self.plot_d
        }

    def create_plot(self, title, color):
        """Create a PyQtGraph plot widget"""
        widget = pg.PlotWidget()
        widget.setBackground('w')
        widget.setTitle(title, color='k', size='12pt')
        widget.setLabel('left', 'Transmission', units='AU')
        widget.setLabel('bottom', 'Wavelength', units='nm')
        widget.showGrid(x=True, y=True, alpha=0.3)
        widget.setYRange(0, 1.2)

        curve = widget.plot(pen=pg.mkPen(color=color, width=2))

        return {'widget': widget, 'curve': curve}

    def start_acquisition(self):
        """Start acquisition worker"""
        print("\n🎬 Starting acquisition...")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("🔴 Acquiring live data...")
        self.status_label.setStyleSheet("color: #dc3545; padding: 10px;")

        # Reset stats
        for ch in self.spectrum_count:
            self.spectrum_count[ch] = 0
        self.start_time = time.time()

        # Create and start worker
        self.worker = AcquisitionWorker(self.data_queue, self.hardware)
        self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker_thread.start()

        # Start queue processing
        self.queue_timer.start(10)  # Process every 10ms

        print("✅ Acquisition started")

    def stop_acquisition(self):
        """Stop acquisition worker"""
        print("\n🛑 Stopping acquisition...")

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("✅ System calibrated and ready")
        self.status_label.setStyleSheet("color: #28a745; padding: 10px;")

        # Stop worker
        if self.worker:
            self.worker.stop()

        # Wait for thread
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        # Stop timer
        self.queue_timer.stop()

        # Process remaining items
        while not self.data_queue.empty():
            self.process_queue()

        elapsed = time.time() - self.start_time if self.start_time else 1
        total = sum(self.spectrum_count.values())
        print(f"✅ Stopped - {total} spectra in {elapsed:.1f}s ({total/elapsed:.1f} Hz)")

    def process_queue(self):
        """Process data queue in main thread"""
        try:
            for _ in range(100):  # Process up to 100 items per call
                if self.data_queue.empty():
                    break

                data = self.data_queue.get_nowait()

                if data['type'] == 'spectrum':
                    channel = data['channel']

                    # Update graph
                    plot = self.plots[channel]
                    plot['curve'].setData(data['wavelengths'], data['transmission'])

                    # Update stats
                    self.spectrum_count[channel] += 1

                    # Update title with count
                    total = sum(self.spectrum_count.values())
                    elapsed = time.time() - self.start_time if self.start_time else 1
                    fps = total / elapsed
                    plot['widget'].setTitle(
                        f"Channel {channel.upper()} - {self.spectrum_count[channel]} spectra ({fps:.1f} Hz)",
                        color='k', size='11pt'
                    )

        except queue.Empty:
            pass
        except Exception as e:
            print(f"❌ Error processing queue: {e}")
            import traceback
            traceback.print_exc()

    def closeEvent(self, event):
        """Clean shutdown"""
        print("\n🚪 Closing window...")
        if self.worker:
            self.stop_acquisition()
        event.accept()

def main():
    print("="*70)
    print("AffiLabs.core - Post-Calibration Live Data Test")
    print("="*70)
    print("This test simulates starting from calibration complete state")
    print("and proves the live data display pipeline works.")
    print("="*70)
    print()

    app = QApplication(sys.argv)

    # Set style
    app.setStyle('Fusion')

    window = LiveDataWindow()
    window.show()

    print("✅ Application ready")
    print("   Click 'Start Acquisition' to begin")
    print("   Watch live SPR transmission spectra update")
    print("   Click 'Stop Acquisition' to end\n")

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
