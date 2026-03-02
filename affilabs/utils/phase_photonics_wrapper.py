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
try:
    from ftd2xx import listDevices
except (ImportError, OSError):
    listDevices = None
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

    # Hardware averaging limit — this detector supports max 15 onboard scans
    MAX_HARDWARE_AVERAGING = 15

    # PhasePhotonics timing characteristics
    # SOFTWARE AVERAGING (hardware averaging ignores integration time!)
    # Total acquisition time = Integration time × TIMING_MULTIPLIER
    # This includes integration + USB readout overhead per scan
    TIMING_MULTIPLIER = 1.93

    # NOTE: Hardware averaging (usb_set_averaging) is BROKEN - it ignores integration time!
    # The detector does multiple scans but at wrong integration time (~1ms instead of configured)
    # Therefore we MUST use software averaging (Python loop) instead

    # LEGACY: Software averaging timing (DEPRECATED - kept for reference)
    # Total acquisition time = Integration time × TIMING_MULTIPLIER
    # This was used when doing software averaging (looping in Python)
    TIMING_MULTIPLIER_LEGACY = 1.93

    # External wavelength calibration overrides
    # Use these when EEPROM calibration is incorrect or missing
    # Format: {"serial_number": [c0, c1, c2, c3]}
    CALIBRATION_OVERRIDES = {
        "ST00007": [
            5.559280e2,      # c0 = 555.9280
            2.190425e-1,     # c1 = 0.2190425
            -1.658049e-5,    # c2 = -1.658049e-05
            -7.303322e-9,    # c3 = -7.303322e-09
        ],
        "ST00011": [
            5.303916e2,      # c0 = 530.3916
            2.204814e-1,     # c1 = 0.2204814
            -4.007498e-6,    # c2 = -4.007498e-06
            -9.861940e-9,    # c3 = -9.861940e-09
        ],
        "ST00012": [
            5.637917e2,      # c0 = 563.7917
            2.089449e-1,     # c1 = 0.2089449
            -2.302712e-6,    # c2 = -2.302712e-06
            -1.650914e-8,    # c3 = -1.650914e-08
        ],
        "ST00014": [
            5.016961e2,      # c0 = 501.6961
            2.385570e-1,     # c1 = 0.2385570
            -3.840143e-5,    # c2 = -3.840143e-05
            7.718971e-9,     # c3 = 7.718971e-09
        ],
    }

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
        self._max_counts = 8191  # 13-bit ADC (measured saturation ~8K)
        self._num_pixels = SENSOR_DATA_LEN  # 1848 for PhasePhotonics (ISOLATED)

        # Optimal scan configuration
        self._num_scans = 1  # Will be set by calculate_optimal_scans()
        self._time_budget_ms = None  # Available time per measurement

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
            from affilabs.utils.resource_path import get_affilabs_resource

            dll_path = get_affilabs_resource("utils/Sensor64bit.dll")
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

    def set_averaging(self, num_scans: int = 1) -> bool:
        """Set hardware scan averaging (internal accumulation in detector).

        CRITICAL FOR FAST ACQUISITION! The detector averages scans internally
        before USB transfer. This is ~44% faster than manual averaging:

        Manual averaging (8 scans):  8 × 44ms = 352ms
        Hardware averaging (8 scans): 8 × 22ms + 22ms = 198ms

        Args:
            num_scans: Number of scans to average internally (1-15, default: 1)
                      Typical values: 8 for good SNR, 1 for maximum speed

        Returns:
            bool: True if successful, False otherwise

        Example:
            >>> detector.set_averaging(8)  # Average 8 scans internally
            >>> spectrum = detector.read_intensity()  # Returns averaged result

        Note:
            - Set to 1 for single-scan acquisition (no averaging)
            - Set to 8 for typical SPR measurements (good SNR)
            - Maximum value: 15 (hardware limit)

        """
        if self.spec is None:
            logger.error("Cannot set averaging: spectrometer not connected")
            return False

        if not (1 <= num_scans <= self.MAX_HARDWARE_AVERAGING):
            logger.error(f"Invalid num_scans: {num_scans} (must be 1-{self.MAX_HARDWARE_AVERAGING})")
            return False

        try:
            logger.info(f"Setting hardware averaging to {num_scans} scans...")
            r = self.api.usb_set_averaging(self.spec, num_scans)

            if r == 0:
                logger.info(f"✓ Hardware averaging set to {num_scans} scans")

                # Update trigger timeout to account for averaging
                # Total acquisition time = integration × num_scans
                integration_ms = self._integration_time * 1000
                total_time_ms = integration_ms * num_scans
                trig_tmo_ms = int(total_time_ms * 1.5)  # 1.5x safety margin

                r_tmo = self.api.usb_set_trig_tmo(self.spec, trig_tmo_ms)
                if r_tmo != 0:
                    logger.warning(f"Failed to set trigger timeout for averaging: {r_tmo}")

                return True

            logger.error(f"Failed to set averaging, error code: {r}")
            return False

        except Exception as e:
            logger.error(f"Failed to set averaging: {e}")
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
        """Read wavelength calibration from detector EEPROM or external override.

        Priority:
        1. CALIBRATION_OVERRIDES dictionary (if serial number present)
        2. EEPROM calibration data

        Returns:
            numpy.ndarray: Wavelength array in nanometers (1848 elements), or None if failed

        """
        if self.spec is not None or self.open():
            try:
                # Check for external calibration override first
                if self.serial_number in self.CALIBRATION_OVERRIDES:
                    coeffs = np.array(self.CALIBRATION_OVERRIDES[self.serial_number])
                    logger.info(
                        f"Using external calibration override for {self.serial_number} "
                        f"(c0={coeffs[0]:.2f}, c1={coeffs[1]:.6e}, c2={coeffs[2]:.6e}, c3={coeffs[3]:.6e})"
                    )
                else:
                    # Read from EEPROM
                    bytes_read, config = self.api.usb_read_config(self.spec, 0)
                    if bytes_read != self.CONFIG_SIZE:
                        logger.error(f"Failed to read EEPROM config: expected {self.CONFIG_SIZE} bytes, got {bytes_read}")
                        return None

                    # Extract calibration coefficients from config data
                    coeffs = frombuffer(
                        config.data,
                        ">f8",  # Big-endian float64
                        self.CALIBRATION_DEGREE,
                        self.CALIBRATION_OFFSET,
                    )

                    # Check if device is calibrated
                    if all(isnan(coeffs)):
                        msg = f"PhasePhotonics {self.serial_number} has not been calibrated in EEPROM"
                        logger.error(msg)
                        raise RuntimeError(msg)

                    logger.debug(
                        f"Using EEPROM calibration for {self.serial_number} "
                        f"(c0={coeffs[0]:.2f}, c1={coeffs[1]:.6e}, c2={coeffs[2]:.6e}, c3={coeffs[3]:.6e})"
                    )

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

    def read_intensity_batch(self, num_scans: int = 8, data_type=np.uint16):
        """Read and average multiple scans with optimized USB pipelining.

        This method minimizes USB command overhead by reading scans in a tight
        loop without extra delays. Significantly faster than calling
        read_intensity() multiple times.

        Typical performance:
        - read_intensity() × 8:  ~350ms (43.8ms per scan)
        - read_intensity_batch(8): ~250ms (31.3ms per scan) ← 28% faster!

        Args:
            num_scans: Number of scans to acquire and average (default: 8)
            data_type: numpy dtype for returned array (default: np.uint16)

        Returns:
            numpy.ndarray: Averaged intensity array (1848 elements), or None if failed

        Example:
            >>> # Fast 8-scan average (~250ms instead of 350ms)
            >>> averaged_spectrum = detector.read_intensity_batch(8)

        """
        if self.spec is None and not self.open():
            logger.error("Cannot read batch: spectrometer not connected")
            return None

        try:
            import time

            t_start = time.perf_counter()

            # Pre-allocate array for scans
            scans = np.empty((num_scans, SENSOR_DATA_LEN), dtype=data_type)

            # Tight loop - minimize overhead between reads
            for i in range(num_scans):
                ret_code, pixel_data = self.api.usb_read_pixels(self.spec, data_type)

                if ret_code != 0:
                    logger.error(f"Batch read failed on scan {i+1}/{num_scans}, error: {ret_code}")
                    return None

                scans[i] = pixel_data

            # Average all scans
            averaged = np.mean(scans, axis=0)

            t_elapsed = (time.perf_counter() - t_start) * 1000

            logger.info(
                f"Batch read: {num_scans} scans in {t_elapsed:.1f}ms "
                f"({t_elapsed/num_scans:.1f}ms per scan)"
            )

            return averaged.astype(data_type)

        except Exception as e:
            logger.exception(f"Batch read failed: {e}")
            return None

    def calculate_optimal_scans(self, integration_ms: float, time_budget_ms: float) -> int:
        """Calculate optimal number of scans for given integration time and budget.

        Uses SOFTWARE AVERAGING timing: Total Time = Integration Time × 1.93 × num_scans
        (Hardware averaging is broken - ignores integration time!)

        Args:
            integration_ms: Integration time per scan in milliseconds
            time_budget_ms: Available time budget in milliseconds

        Returns:
            int: Optimal number of scans (minimum 1)

        Example:
            >>> # For 190ms budget with 22ms integration
            >>> detector.calculate_optimal_scans(22, 190)  # Returns 4
            >>> # For 7.91ms integration, 170ms budget
            >>> detector.calculate_optimal_scans(7.91, 170)  # Returns 11

        """
        # Software averaging: Total Time = num_scans × (integration_time × TIMING_MULTIPLIER)
        time_per_scan = integration_ms * self.TIMING_MULTIPLIER
        num_scans = int(time_budget_ms / time_per_scan)

        # Ensure at least 1 scan
        num_scans = max(1, num_scans)

        # Log the calculation
        total_time = num_scans * time_per_scan
        snr_gain = num_scans ** 0.5

        logger.info(
            f"Optimal scans: {num_scans} × {time_per_scan:.1f}ms = {total_time:.1f}ms "
            f"(SNR: {snr_gain:.2f}x, budget: {time_budget_ms:.0f}ms)"
        )

        return num_scans

    def set_optimal_scans(self, integration_ms: float, time_budget_ms: float) -> int:
        """Set optimal number of scans and store configuration.

        Args:
            integration_ms: Integration time in milliseconds
            time_budget_ms: Available time budget in milliseconds

        Returns:
            int: Number of scans configured

        """
        self._num_scans = self.calculate_optimal_scans(integration_ms, time_budget_ms)
        self._time_budget_ms = time_budget_ms

        logger.info(
            f"PhasePhotonics configured: {integration_ms}ms integration, "
            f"{self._num_scans} scans, {time_budget_ms}ms budget"
        )

        return self._num_scans

    def get_num_scans(self) -> int:
        """Get configured number of scans.

        Returns:
            int: Number of scans (default: 1)

        """
        return self._num_scans

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
                # Measure actual acquisition time with high-resolution timer
                import time

                t_start = time.perf_counter()

                ret_code, pixel_data = self.api.usb_read_pixels(self.spec, data_type)

                t_elapsed = (time.perf_counter() - t_start) * 1000  # Convert to ms

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
