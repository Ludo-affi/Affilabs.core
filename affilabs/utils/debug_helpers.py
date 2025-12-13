"""Debug helpers for testing and development.

This module contains debug/testing utilities that bypass normal
hardware and calibration flows for UI testing and development.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MockController:
    """Mock controller for testing without hardware."""

    def set_intensity(self, ch, raw_val) -> None:
        """Mock LED intensity setting."""

    def set_mode(self, mode) -> None:
        """Mock mode switching."""


class MockSpectrometer:
    """Mock spectrometer for testing without hardware."""

    def set_integration(self, time_ms) -> None:
        """Mock integration time setting."""

    def read_intensity(self):
        """Return fake spectrum data."""
        return np.random.randint(20000, 50000, 2048)


def create_fake_calibration_data() -> dict[str, Any]:
    """Create minimal fake calibration data for debug/testing.

    Returns:
        Dictionary with fake calibration parameters matching real structure

    """
    return {
        "calibrated": True,
        "integration_time": 40,
        "num_scans": 5,
        "leds_calibrated": {"a": 255, "b": 150, "c": 150, "d": 255},
        "wave_data": np.linspace(400, 900, 2048),
        "ref_sig": {
            "a": np.ones(2048) * 40000,
            "b": np.ones(2048) * 40000,
            "c": np.ones(2048) * 40000,
            "d": np.ones(2048) * 40000,
        },
        "dark_noise": np.zeros(2048),
        "fourier_weights": {
            "a": np.ones(2048 - 1),  # Derivative has n-1 points
            "b": np.ones(2048 - 1),
            "c": np.ones(2048 - 1),
            "d": np.ones(2048 - 1),
        },
    }


def inject_fake_calibration(data_mgr) -> None:
    """Inject fake calibration data into data manager.

    Args:
        data_mgr: DataAcquisitionManager instance to populate

    """
    fake_data = create_fake_calibration_data()

    data_mgr.calibrated = fake_data["calibrated"]
    data_mgr.integration_time = fake_data["integration_time"]
    data_mgr.num_scans = fake_data["num_scans"]
    data_mgr.leds_calibrated = fake_data["leds_calibrated"]
    data_mgr.wave_data = fake_data["wave_data"]
    data_mgr.ref_sig = fake_data["ref_sig"]
    data_mgr.dark_noise = fake_data["dark_noise"]
    data_mgr.fourier_weights = fake_data["fourier_weights"]

    logger.info("[OK] Fake calibration data injected into data manager")


def save_fake_calibration_to_config(device_config) -> None:
    """Save fake calibration to device config.

    Args:
        device_config: DeviceConfiguration instance

    """
    if not device_config:
        logger.warning("No device config available - skipping save")
        return

    try:
        device_config.set_led_intensities(255, 150, 150, 255)
        device_config.set_calibration_settings(40, 5)
        device_config.save()
        logger.info("💾 Fake calibration saved to device config")
    except Exception as e:
        logger.warning(f"Failed to save fake calibration to device config: {e}")


def create_mock_hardware(hardware_mgr) -> None:
    """Create mock hardware objects for testing without real hardware.

    Args:
        hardware_mgr: HardwareManager instance to populate

    """
    if not hardware_mgr.ctrl or not hardware_mgr.usb:
        logger.info("🧪 Creating mock hardware objects")
        hardware_mgr.ctrl = MockController()
        hardware_mgr.usb = MockSpectrometer()
        logger.info("[OK] Mock hardware created")
