from __future__ import annotations

"""PhasePhotonics Spectrometer Driver - PRODUCTION IMPLEMENTATION.

This driver interfaces with PhasePhotonics detectors using SensorT.dll.
COMPLETELY ISOLATED from USB4000 - uses separate API module with correct
pixel count (1848) to prevent any risk of mixing detector types.

Compatible interface with USB4000 wrapper for drop-in replacement via
detector_factory.create_detector().
"""

from pathlib import Path

import numpy as np
from ftd2xx import listDevices
from numpy import all, arange, frombuffer, isnan
from numpy.polynomial import Polynomial

from affilabs.utils.logger import logger

# CRITICAL: Import PhasePhotonics-specific API (NOT SpectrometerAPI)
# This ensures SENSOR_DATA_LEN = 1848 (not 3700)
from affilabs.utils.phase_photonics_api import SENSOR_DATA_LEN, PhasePhotonicsAPI


class PhasePhotonics:
    """PhasePhotonics Spectrometer Driver.

    DETECTOR ISOLATION:
    - Uses phase_photonics_api.PhasePhotonicsAPI (1848 pixels)
    - USB4000 uses SpectrometerAPI (3700 pixels)
    - Zero risk of array size mixing

    Compatible interface with USB4000 wrapper for drop-in replacement via
    detector_factory.create_detector().
    """

    # PhasePhotonics calibration constants
    CONFIG_SIZE = 4096
    CALIBRATION_OFFSET = 3072
    CALIBRATION_DEGREE = 4

    def __init__(self, parent=None) -> None:
        """Initialize PhasePhotonics driver.

        Args:
            parent: Application instance for error callbacks

        """
        super().__init__()

        # PhasePhotonics-specific API (isolated from USB4000)
        self.api = None  # Will be set in open() based on device serial
        self.parent = parent
        self.spec = None
        self.opened = False
        self.devs = []
        self.min_integration = 0  # microseconds
        self.max_integration = 5_000_000  # 5 seconds in microseconds
        self.serial_number = None

        # Detector specifications - PhasePhotonics specific
        self._wavelengths = None
        self._integration_time = 0.1  # seconds
        self._max_counts = 4095  # 12-bit ADC (confirmed by OEM specs)
        self._num_pixels = SENSOR_DATA_LEN  # 1848 for PhasePhotonics (ISOLATED)

        logger.info(
            f"PhasePhotonics driver initialized (pixel count: {self._num_pixels})",
        )

    def get_device_list(self) -> None:
        """Scan for connected PhasePhotonics devices.

        PhasePhotonics devices have serial numbers starting with "ST".
        """
        try:
            logger.debug("Scanning for PhasePhotonics spectrometers...")
            # ftd2xx enumerates FTDI USB devices
            all_devices = listDevices()

            if all_devices is None:
                logger.warning(
                    "ftd2xx.listDevices() returned None - D2XX drivers may not be installed or device not connected"
                )
                self.devs = []
                return

            # Filter for PhasePhotonics devices (serial starts with "ST")
            self.devs = [s.decode() for s in all_devices if s.startswith(b"ST")]
            logger.info(
                f"Found {len(self.devs)} PhasePhotonics device(s): {self.devs}",
            )
        except Exception as e:
            logger.error(f"Error getting device list: {e}", exc_info=True)
            self.devs = []

    def open(self) -> bool | None:
        """Connect to PhasePhotonics spectrometer.

        Returns:
            bool: True if connection successful, False otherwise

        """
        try:
            # Scan for devices
            self.get_device_list()

            if len(self.devs) == 0:
                logger.warning("No PhasePhotonics spectrometers found")
                return False

            # Use first available device
            self.serial_number = self.devs[0]
            logger.info(f"Connecting to PhasePhotonics {self.serial_number}...")

            # Use OEM-recommended DLL (Sensor64bit.dll) for optimal performance
            # Provides 120+ FPS and 8-10ms pixel reading times
            dll_path = Path(__file__).parent / "Sensor64bit.dll"
            logger.debug("Using Sensor64bit.dll (OEM recommended for high performance)")

            if not dll_path.exists():
                logger.error(f"PhasePhotonics DLL not found: {dll_path}")
                return False

            # Initialize PhasePhotonics-specific API (ISOLATED from USB4000)
            self.api = PhasePhotonicsAPI(str(dll_path))

            # Connect to device
            self.spec = self.api.usb_initialize(self.devs[0])

            if not self.spec:
                logger.error("Failed to initialize PhasePhotonics spectrometer")
                return False

            # Set default integration time (100ms)
            default_integration_ms = 100
            self.set_integration(default_integration_ms)

            self.opened = True
            logger.info(
                f"✓ PhasePhotonics {self.serial_number} connected (1848 pixels)",
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to connect to PhasePhotonics spectrometer: {e}")
            if self.parent and hasattr(self.parent, "raise_error"):
                self.parent.raise_error.emit("spec")
            return False

    def close(self) -> None:
        """Disconnect from spectrometer."""
        if self.spec is not None:
            try:
                self.api.usb_deinit(self.spec)
                logger.info("PhasePhotonics spectrometer disconnected")
            except Exception as e:
                logger.error(f"Error closing PhasePhotonics spectrometer: {e}")
            finally:
                self.spec = None
                self.opened = False

    def set_integration(self, integration_ms) -> bool | None:
        """Set integration time in milliseconds.

        Args:
            integration_ms: Integration time in milliseconds (float or int)

        Returns:
            bool: True if successful, False otherwise

        """
        integration_us = int(integration_ms * 1000)  # Convert to microseconds

        if (
            integration_us < self.min_integration
            or integration_us > self.max_integration
        ):
            logger.warning(f"Integration time {integration_ms}ms out of range")
            return False

        try:
            r = self.api.usb_set_interval(self.spec, integration_us)
            # Note: No post-set delay needed (confirmed by OEM)
            self._integration_time = integration_ms / 1000.0  # Store in seconds

            if r == 0:
                # CRITICAL: Set trigger timeout to match integration time (LabVIEW does this!)
                # This is what enables fast acquisition!
                trig_tmo_ms = max(
                    20,
                    int(integration_ms * 3),
                )  # 3x integration or 20ms minimum
                r_tmo = self.api.usb_set_trig_tmo(self.spec, trig_tmo_ms)
                if r_tmo != 0:
                    logger.warning(
                        f"Failed to set trigger timeout, error code: {r_tmo}",
                    )

                return True
            logger.error(f"Failed to set integration time, error code: {r}")
            return False
        except Exception as e:
            logger.error(f"Failed to set integration time: {e}")
            if self.parent and hasattr(self.parent, "raise_error"):
                self.parent.raise_error.emit("spec")
            return False

    def get_trigger_timeout(self):
        """Get current trigger timeout from sensor.

        Returns:
            int: Current trigger timeout in milliseconds, or -1 if failed

        """
        if self.spec is None:
            logger.error("Cannot get trigger timeout: spectrometer not connected")
            return -1

        try:
            timeout_ms = self.api.get_trigger_timeout(self.spec)
            logger.debug(f"Current trigger timeout: {timeout_ms}ms")
            return timeout_ms
        except Exception as e:
            logger.error(f"Failed to get trigger timeout: {e}")
            return -1

    def set_trigger_timeout(self, timeout_ms) -> bool | None:
        """Set trigger timeout for USB reads.

        The trigger timeout controls how long the DLL waits for data during reads.
        For fast integration times (e.g., 10ms), reducing this can speed up acquisition.
        Recommended: 2-3x integration time.

        Args:
            timeout_ms: Timeout in milliseconds (int)

        Returns:
            bool: True if successful, False otherwise

        """
        if self.spec is None:
            logger.error("Cannot set trigger timeout: spectrometer not connected")
            return False

        try:
            logger.info(f"Setting trigger timeout to {timeout_ms}ms...")
            r = self.api.set_trigger_timeout(self.spec, timeout_ms)
            if r == 0:
                logger.info(f"✓ Trigger timeout set to {timeout_ms}ms")
                return True
            logger.error(f"Failed to set trigger timeout, error code: {r}")
            return False
        except Exception as e:
            logger.error(f"Failed to set trigger timeout: {e}")
            return False

    def read_wavelength(self):
        """Read wavelength calibration from detector EEPROM.

        Returns:
            numpy.ndarray: Wavelength array in nanometers (1848 elements), or None if failed

        """
        if self.spec is not None or self.open():
            try:
                bytes_read, config = self.api.usb_read_config(self.spec, 0)
                if bytes_read == self.CONFIG_SIZE:
                    # Extract calibration coefficients from config data
                    coeffs = frombuffer(
                        config.data,
                        ">f8",  # Big-endian float64
                        self.CALIBRATION_DEGREE,
                        self.CALIBRATION_OFFSET,
                    )

                    # Check if device is calibrated
                    if all(isnan(coeffs)):
                        msg = "PhasePhotonics spectrometer has not been calibrated"
                        logger.error(msg)
                        raise RuntimeError(msg)

                    # Compute wavelength array using calibration polynomial
                    calibration_curve = Polynomial(coeffs)
                    wavelengths = calibration_curve(arange(SENSOR_DATA_LEN))

                    # CRITICAL VALIDATION: Ensure array size
                    if len(wavelengths) != SENSOR_DATA_LEN:
                        msg = (
                            f"PhasePhotonics wavelength array mismatch: "
                            f"expected {SENSOR_DATA_LEN}, got {len(wavelengths)}"
                        )
                        raise ValueError(
                            msg,
                        )

                    logger.debug(
                        f"PhasePhotonics wavelength calibration: "
                        f"{wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm "
                        f"({len(wavelengths)} pixels)",
                    )
                    return wavelengths

            except Exception as e:
                logger.error(
                    f"Failed to read PhasePhotonics wavelength calibration: {e}",
                )
                if self.parent and hasattr(self.parent, "raise_error"):
                    self.parent.raise_error.emit("spec")
        return None

    def read_intensity(self, data_type=np.uint16):
        """Read raw intensity spectrum from PhasePhotonics detector.

        Args:
            data_type: numpy dtype for returned array
                      - np.uint16: Native detector format (OEM default, most efficient)
                      - np.float32: Good balance
                      - np.float64: Maximum precision

        Returns:
            numpy.ndarray: Intensity array (1848 elements), or None if failed

        """
        if self.spec is not None or self.open():
            try:
                # Measure actual acquisition time
                import time

                t_start = time.time()

                ret_code, pixel_data = self.api.usb_read_pixels(self.spec, data_type)

                t_elapsed = (time.time() - t_start) * 1000  # Convert to ms

                if ret_code == 0:  # Success
                    # CRITICAL VALIDATION: Verify array size
                    if len(pixel_data) != SENSOR_DATA_LEN:
                        msg = (
                            f"PhasePhotonics returned {len(pixel_data)} pixels, "
                            f"expected {SENSOR_DATA_LEN}. Detector type mismatch!"
                        )
                        raise ValueError(
                            msg,
                        )

                    # Log timing info (only first few calls to avoid spam)
                    if not hasattr(self, "_read_count"):
                        self._read_count = 0
                    self._read_count += 1

                    if self._read_count <= 5 or self._read_count % 20 == 0:
                        logger.debug(
                            f"PhasePhotonics read #{self._read_count}: {t_elapsed:.1f}ms (integration={self._integration_time * 1000:.1f}ms)",
                        )

                    return pixel_data
                logger.warning(
                    f"PhasePhotonics usb_read_pixels error code: {ret_code} (took {t_elapsed:.1f}ms)",
                )
                return None

            except Exception as e:
                logger.error(f"Failed to read PhasePhotonics intensity data: {e}")
                if self.parent and hasattr(self.parent, "raise_error"):
                    self.parent.raise_error.emit("spec")
        return None

    def wavelengths(self):
        """Get wavelength array (cached).

        Returns:
            numpy.ndarray: Wavelength array in nanometers (1848 elements)

        """
        if self._wavelengths is None:
            self._wavelengths = self.read_wavelength()
        return self._wavelengths

    @property
    def max_counts(self):
        """Maximum detector counts (ADC saturation level)."""
        return self._max_counts

    @property
    def num_pixels(self):
        """Number of detector pixels (1848 for PhasePhotonics)."""
        return self._num_pixels

    @property
    def target_counts(self):
        """Recommended target counts for calibration (70% of max)."""
        return int(0.70 * self._max_counts)

    def __str__(self) -> str:
        return f"PhasePhotonics Spectrometer (serial: {self.serial_number}, pixels: {self._num_pixels})"

    def __repr__(self) -> str:
        return f"<PhasePhotonics(opened={self.opened}, serial={self.serial_number}, pixels={self._num_pixels})>"
