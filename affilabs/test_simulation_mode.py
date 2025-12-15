"""Simulation Test Mode
====================
Tests the complete data acquisition and recording pipeline with simulated spectra.

This script:
1. Generates realistic fake spectral data (4 channels + wavelengths)
2. Injects it into the data acquisition manager
3. Tests the complete pipeline: acquisition → processing → recording → UI
4. Runs for configurable duration to stress-test the system

Usage:
------
python test_simulation_mode.py [duration_seconds]

Default: 30 seconds
"""

import sys
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from loggers import logger
from main_simplified import AffilabsApplication


class SimulationMode:
    """Simulates spectral data and injects into live system."""

    def __init__(self, app: AffilabsApplication, duration_seconds: int = 30):
        """Initialize simulation mode.

        Args:
            app: AffilabsApplication instance
            duration_seconds: How long to run simulation

        """
        self.app = app
        self.duration_seconds = duration_seconds
        self.start_time = None
        self.spectrum_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._send_simulated_spectrum)

    def start(self):
        """Start simulation mode."""
        logger.info("=" * 80)
        logger.info("🎬 SIMULATION MODE STARTED")
        logger.info(f"   Duration: {self.duration_seconds} seconds")
        logger.info("   Rate: 10 spectra/second")
        logger.info("=" * 80)

        self.start_time = time.time()

        # Inject fake calibration data
        self.app._debug_bypass_calibration()
        logger.info("[OK] Fake calibration injected")

        # Wait a moment for calibration to settle
        QTimer.singleShot(500, self._start_acquisition)

    def _start_acquisition(self):
        """Start the acquisition process."""
        try:
            # Trigger Start button
            logger.info("🚀 Triggering Start button...")
            self.app._on_start_button_clicked()

            # Start sending simulated spectra
            logger.info("📡 Starting spectrum simulation...")
            self.timer.start(100)  # 10 Hz (100ms interval)

            # Schedule stop after duration
            QTimer.singleShot(self.duration_seconds * 1000, self._stop_simulation)

        except Exception as e:
            logger.exception(f"[ERROR] Failed to start simulation: {e}")
            QApplication.quit()

    def _send_simulated_spectrum(self):
        """Generate and send one simulated spectrum."""
        try:
            elapsed = time.time() - self.start_time

            # Generate realistic fake spectrum data
            spectrum = self._generate_fake_spectrum()

            # Inject directly into data manager's processing
            if self.app.data_mgr and hasattr(self.app.data_mgr, "spectrum_acquired"):
                self.app.data_mgr.spectrum_acquired.emit(spectrum)
                self.spectrum_count += 1

                if self.spectrum_count % 50 == 0:  # Log every 5 seconds
                    logger.info(
                        f"📊 Sent {self.spectrum_count} spectra (elapsed: {elapsed:.1f}s)",
                    )

        except Exception as e:
            logger.exception(f"[ERROR] Error sending simulated spectrum: {e}")
            self._stop_simulation()

    def _generate_fake_spectrum(self):
        """Generate realistic fake spectral data.

        Returns:
            dict: Spectrum data matching real hardware format

        """
        # Use realistic wavelength range (Ocean Optics USB4000: ~200-1100nm)
        n_pixels = 3648
        wavelengths = np.linspace(200, 1100, n_pixels)

        # Simulate 4-channel SPR response
        # Channel A-D: Different peak positions and amplitudes
        time_offset = time.time() - self.start_time

        # Base noise level
        noise = np.random.normal(0, 50, n_pixels)

        # Channel A: Strong peak at 650nm (typical SPR)
        peak_a = 15000 * np.exp(-((wavelengths - 650) ** 2) / (2 * 20**2))
        channel_a = peak_a + noise + 1000

        # Channel B: Moderate peak at 660nm
        peak_b = 12000 * np.exp(-((wavelengths - 660) ** 2) / (2 * 22**2))
        channel_b = peak_b + noise + 800

        # Channel C: Weak peak at 655nm
        peak_c = 10000 * np.exp(-((wavelengths - 655) ** 2) / (2 * 18**2))
        channel_c = peak_c + noise + 900

        # Channel D: Strong peak at 670nm
        peak_d = 14000 * np.exp(-((wavelengths - 670) ** 2) / (2 * 25**2))
        channel_d = peak_d + noise + 1100

        # Add slight drift over time (simulate real binding event)
        drift = 0.1 * time_offset  # Slow drift
        channel_a += drift * 100
        channel_b += drift * 80
        channel_c += drift * 90
        channel_d += drift * 110

        return {
            "wavelengths": wavelengths.astype(np.float32),
            "channel_a": channel_a.astype(np.float32),
            "channel_b": channel_b.astype(np.float32),
            "channel_c": channel_c.astype(np.float32),
            "channel_d": channel_d.astype(np.float32),
            "timestamp": time.time(),
            "integration_time": 40.0,
            "simulated": True,
        }

    def _stop_simulation(self):
        """Stop simulation and report results."""
        self.timer.stop()

        elapsed = time.time() - self.start_time

        logger.info("=" * 80)
        logger.info("🎬 SIMULATION MODE COMPLETE")
        logger.info(f"   Duration: {elapsed:.2f} seconds")
        logger.info(f"   Spectra sent: {self.spectrum_count}")
        logger.info(f"   Average rate: {self.spectrum_count / elapsed:.1f} spectra/sec")
        logger.info("=" * 80)

        # Stop acquisition and recording
        try:
            if self.app.data_mgr and self.app.data_mgr._acquiring:
                self.app.data_mgr.stop_acquisition()
                logger.info("[OK] Acquisition stopped")

            if self.app.recording_mgr and hasattr(
                self.app.recording_mgr,
                "stop_recording",
            ):
                self.app.recording_mgr.stop_recording()
                logger.info("[OK] Recording stopped")
        except Exception as e:
            logger.exception(f"[WARN] Error during cleanup: {e}")

        # Show results dialog
        from affilabs.widgets.message import show_message

        show_message(
            f"Simulation Complete!\n\n"
            f"[OK] Duration: {elapsed:.1f}s\n"
            f"[OK] Spectra sent: {self.spectrum_count}\n"
            f"[OK] Rate: {self.spectrum_count / elapsed:.1f}/sec\n\n"
            f"Check logs for any errors during pipeline processing.",
            msg_type="Info",
            title="Simulation Test Results",
        )

        logger.info("💡 You can now close the application or run another test")


def main():
    """Main entry point for simulation test."""
    # Parse duration from command line
    duration = 30  # default
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default {duration}s")

    logger.info("=" * 80)
    logger.info("🧪 STARTING SIMULATION TEST MODE")
    logger.info("=" * 80)

    # Create Qt application
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)

    # Create main application
    app = AffilabsApplication()

    # Create and start simulation
    simulation = SimulationMode(app, duration_seconds=duration)
    QTimer.singleShot(1000, simulation.start)  # Start after UI loads

    # Run application
    logger.info("🚀 Starting Qt event loop...")
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
