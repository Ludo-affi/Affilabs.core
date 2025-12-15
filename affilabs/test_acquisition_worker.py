"""Minimal test for acquisition worker thread - NO UI, NO Qt widgets.

This isolates the acquisition logic to test if it can run without crashes.
"""

import sys

import numpy as np
from PySide6.QtCore import QCoreApplication, QTimer


# Mock hardware classes
class MockController:
    def set_intensity(self, ch, raw_val):
        pass

    def set_mode(self, mode):
        print(f"Mock: Set mode to {mode}")


class MockSpectrometer:
    def set_integration(self, time_ms):
        print(f"Mock: Set integration to {time_ms}ms")

    def read_intensity(self):
        # Return realistic spectrum data
        return np.random.randint(20000, 50000, 2048)


def main():
    print("=" * 60)
    print("MINIMAL ACQUISITION WORKER TEST")
    print("=" * 60)

    # Create Qt application (NO GUI)
    app = QCoreApplication(sys.argv)

    # Import managers AFTER Qt app exists
    from core.data_acquisition_manager import DataAcquisitionManager
    from core.event_bus import EventBus
    from core.hardware_manager import HardwareManager

    print("\n1. Creating event bus...")
    event_bus = EventBus(debug_mode=False)

    print("2. Creating hardware manager with mock devices...")
    hw_mgr = HardwareManager()
    hw_mgr.ctrl = MockController()
    hw_mgr.usb = MockSpectrometer()

    print("3. Creating data acquisition manager...")
    data_mgr = DataAcquisitionManager(hardware_mgr=hw_mgr)

    print("4. Injecting fake calibration data...")
    data_mgr.calibrated = True
    data_mgr.integration_time = 40
    data_mgr.num_scans = 5
    data_mgr.leds_calibrated = {"a": 255, "b": 150, "c": 150, "d": 255}
    data_mgr.wave_data = np.linspace(400, 900, 2048)
    data_mgr.ref_sig = {
        "a": np.ones(2048) * 40000,
        "b": np.ones(2048) * 40000,
        "c": np.ones(2048) * 40000,
        "d": np.ones(2048) * 40000,
    }
    data_mgr.dark_noise = np.zeros(2048)
    data_mgr.fourier_weights = {
        "a": np.ones(2048 - 1),
        "b": np.ones(2048 - 1),
        "c": np.ones(2048 - 1),
        "d": np.ones(2048 - 1),
    }

    print("5. Connecting to spectrum_acquired signal...")
    spectrum_count = {"count": 0}

    def on_spectrum(data):
        spectrum_count["count"] += 1
        if spectrum_count["count"] <= 5:
            print(
                f"   ✓ Spectrum {spectrum_count['count']}: channel={data['channel']}, wavelength={data.get('wavelength', 'N/A'):.2f}nm",
            )
        elif spectrum_count["count"] == 20:
            print("   ✓ Received 20 spectra - TEST PASSED!")
            data_mgr.stop_acquisition()
            QTimer.singleShot(500, app.quit)

    data_mgr.spectrum_acquired.connect(on_spectrum)

    print("\n6. Starting acquisition worker thread...")
    data_mgr.start_acquisition()

    print("\n7. Running event loop for 10 seconds...")
    print("   (Watching for Qt threading errors or crashes...)\n")

    # Auto-stop after 10 seconds if not enough spectra
    def timeout():
        if spectrum_count["count"] < 20:
            print(
                f"\n   [WARN] Timeout: Only received {spectrum_count['count']} spectra",
            )
            print("   (Expected at least 20)")
        data_mgr.stop_acquisition()
        QTimer.singleShot(500, app.quit)

    QTimer.singleShot(10000, timeout)

    # Run Qt event loop
    exit_code = app.exec()

    print("\n" + "=" * 60)
    print(f"RESULT: Received {spectrum_count['count']} spectra")
    if spectrum_count["count"] >= 20:
        print("STATUS: [OK] SUCCESS - Acquisition worker runs without crashes!")
    elif spectrum_count["count"] > 0:
        print("STATUS: [WARN] PARTIAL - Worker started but may have issues")
    else:
        print("STATUS: [ERROR] FAILED - No spectra received")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
