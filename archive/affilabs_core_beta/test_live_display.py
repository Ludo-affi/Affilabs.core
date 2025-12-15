"""Minimal test: Acquisition worker → Queue → Main thread → Live graph display
Proves the data pipeline works without calibration complexity.
"""

import queue
import sys
import threading
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Mock hardware that generates fake SPR data
class MockHardware:
    def __init__(self):
        self.wavelengths = np.linspace(450, 850, 2048)
        self.time_offset = 0

    def get_spectrum(self, channel):
        """Generate realistic SPR dip that shifts over time"""
        # SPR dip parameters (shifts to simulate real-time binding)
        dip_center = 650 + 5 * np.sin(self.time_offset * 0.5)  # Oscillating dip
        dip_width = 30
        dip_depth = 0.6

        # Generate baseline + SPR dip
        baseline = 1.0 + 0.05 * np.random.randn(len(self.wavelengths))
        dip = dip_depth * np.exp(
            -((self.wavelengths - dip_center) ** 2) / (2 * dip_width**2),
        )
        spectrum = baseline - dip

        self.time_offset += 0.1
        return spectrum


# Worker thread: Acquires spectra and puts in queue
class AcquisitionWorker(QObject):
    def __init__(self, data_queue):
        super().__init__()
        self.data_queue = data_queue
        self.hardware = MockHardware()
        self.running = False
        self.stop_flag = threading.Event()

    def run(self):
        """Worker thread main loop"""
        self.running = True
        count = 0
        print("🚀 Worker thread started")

        while self.running and not self.stop_flag.is_set():
            try:
                # Simulate acquisition time
                time.sleep(0.1)

                # Get spectrum from mock hardware
                spectrum = self.hardware.get_spectrum("a")
                wavelengths = self.hardware.wavelengths

                # Put in queue (thread-safe)
                data = {
                    "type": "spectrum",
                    "channel": "a",
                    "wavelengths": wavelengths,
                    "intensity": spectrum,
                    "timestamp": time.time(),
                    "count": count,
                }
                self.data_queue.put_nowait(data)
                count += 1

                if count % 10 == 0:
                    print(f"✅ Worker: Generated {count} spectra")

            except Exception as e:
                print(f"❌ Worker error: {e}")
                import traceback

                traceback.print_exc()
                break

        print(f"🛑 Worker thread stopped after {count} spectra")

    def stop(self):
        """Stop the worker"""
        print("Stopping worker...")
        self.running = False
        self.stop_flag.set()


# Main window with live graph
class LiveDisplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live SPR Display Test")
        self.resize(1000, 600)

        # Data queue for thread-safe communication
        self.data_queue = queue.Queue()

        # Setup UI
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Control buttons
        self.start_btn = QPushButton("Start Acquisition")
        self.start_btn.clicked.connect(self.start_acquisition)
        self.stop_btn = QPushButton("Stop Acquisition")
        self.stop_btn.clicked.connect(self.stop_acquisition)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        # PyQtGraph plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.setLabel("left", "Intensity", units="AU")
        self.plot_widget.setLabel("bottom", "Wavelength", units="nm")
        self.plot_widget.setTitle("Channel A - Live SPR Spectrum")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self.plot_widget)

        # Plot curve
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color="b", width=2))

        # Worker thread
        self.worker = None
        self.worker_thread = None

        # Timer to process queue (runs in main thread)
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)

        # Stats
        self.spectrum_count = 0
        self.start_time = None

        print("✅ LiveDisplayWindow initialized")

    def start_acquisition(self):
        """Start acquisition worker thread"""
        print("\n🎬 Starting acquisition...")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.spectrum_count = 0
        self.start_time = time.time()

        # Create worker
        self.worker = AcquisitionWorker(self.data_queue)

        # Start worker thread
        self.worker_thread = threading.Thread(
            target=self.worker.run,
            daemon=True,
            name="AcqWorker",
        )
        self.worker_thread.start()

        # Start queue processing timer (main thread)
        self.queue_timer.start(10)  # Process every 10ms

        print("✅ Acquisition started - worker thread running")

    def stop_acquisition(self):
        """Stop acquisition worker thread"""
        print("\n🛑 Stopping acquisition...")

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Stop worker
        if self.worker:
            self.worker.stop()

        # Wait for thread
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        # Stop queue timer
        self.queue_timer.stop()

        # Process remaining queue items
        while not self.data_queue.empty():
            self.process_queue()

        elapsed = time.time() - self.start_time if self.start_time else 0
        print(
            f"✅ Acquisition stopped - {self.spectrum_count} spectra in {elapsed:.1f}s ({self.spectrum_count/elapsed:.1f} Hz)",
        )

    def process_queue(self):
        """Process data queue in main thread (Qt-safe)"""
        try:
            # Process all available items (up to 100 per call)
            for _ in range(100):
                if self.data_queue.empty():
                    break

                data = self.data_queue.get_nowait()

                if data["type"] == "spectrum":
                    # Update graph (Qt operations safe in main thread)
                    self.curve.setData(data["wavelengths"], data["intensity"])

                    self.spectrum_count += 1

                    # Update title with stats
                    elapsed = time.time() - self.start_time if self.start_time else 1
                    fps = self.spectrum_count / elapsed
                    self.plot_widget.setTitle(
                        f"Channel A - Live SPR Spectrum | {self.spectrum_count} spectra | {fps:.1f} Hz",
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


# Main entry point
def main():
    print("=" * 70)
    print("Live SPR Display Test")
    print("Tests: Worker thread → Queue → Main thread → PyQtGraph display")
    print("=" * 70)

    app = QApplication(sys.argv)

    window = LiveDisplayWindow()
    window.show()

    print("\n✅ Application ready")
    print("   Click 'Start Acquisition' to begin")
    print("   Watch the live SPR spectrum update")
    print("   Click 'Stop Acquisition' to end\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
