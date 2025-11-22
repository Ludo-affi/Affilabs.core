"""USB4000 Spectrometer Driver - SINGLE CONNECTION METHOD ONLY

This is the ONLY way to connect to the USB4000/FLAME-T spectrometer.
Uses pyseabreeze backend (pure Python, works on this system).

Requirements:
- pyusb Python package installed
- seabreeze Python package installed
"""

from utils.logger import logger

# Defer all seabreeze imports until open() is called to avoid blocking on import


class USB4000:
    """USB4000/FLAME-T Spectrometer using pyseabreeze backend.

    This is the ONLY connection method. No fallbacks, no alternatives.
    """

    def __init__(self, parent=None):
        """Initialize USB4000 driver."""
        self._device = None
        self.opened = False
        self.serial_number = None
        self.spec = None
        self.use_seabreeze = True  # Always True - single connection method
        self._wavelengths = None
        self._integration_time = 0.1

        # Detector specifications (set during open())
        self._max_counts = 65535  # 16-bit ADC default for USB4000
        self._num_pixels = 3648  # USB4000 default

    def open(self):
        """Connect to spectrometer - SINGLE METHOD ONLY."""
        try:
            logger.info("Connecting to USB4000...")

            # Import seabreeze only when actually opening (deferred to avoid blocking on import)
            try:
                import seabreeze
                seabreeze.use('pyseabreeze')
                from seabreeze.spectrometers import Spectrometer, list_devices
                logger.info("USB4000: Using pyseabreeze backend (pure Python, works with WinUSB)")
            except ImportError as e:
                logger.error(f"SeaBreeze not available: {e}")
                logger.error("Install with: pip install seabreeze pyusb")
                return False

            # Discover devices (NEW software method) with timeout
            logger.debug("Scanning for Ocean Optics devices (5s timeout)...")

            # Use threading with timeout to prevent indefinite blocking
            import threading
            devices = []
            exception = [None]

            def scan_devices():
                try:
                    nonlocal devices
                    devices = list_devices()
                except Exception as e:
                    exception[0] = e

            scan_thread = threading.Thread(target=scan_devices, daemon=True)
            scan_thread.start()
            scan_thread.join(timeout=5.0)

            if scan_thread.is_alive():
                logger.warning("USB device scan timed out after 5 seconds - no spectrometer connected")
                return False

            if exception[0]:
                logger.error(f"USB device scan failed: {exception[0]}")
                return False

            logger.debug(f"SeaBreeze found {len(devices)} device(s)")

            if not devices:
                logger.warning("No USB4000 devices found")
                return False

            # Get first device serial number
            device_info = devices[0]
            target_serial = device_info.serial_number
            logger.info(f"Connecting to device serial: {target_serial}")

            # Connect using SeaBreeze (NEW software method)
            logger.debug(f"SeaBreeze: Creating spectrometer for serial {target_serial}")

            try:
                self._device = Spectrometer.from_serial_number(target_serial)
            except Exception as e:
                if "already opened" in str(e).lower():
                    # Device is stuck open - try to close all and reopen
                    logger.warning("Device already opened - attempting cleanup and retry...")
                    try:
                        # Close all open spectrometers
                        from seabreeze.spectrometers import list_devices, Spectrometer
                        for dev in list_devices():
                            try:
                                spec = Spectrometer(dev)
                                spec.close()
                                logger.debug(f"Closed stuck spectrometer: {dev.serial_number}")
                            except:
                                pass

                        # Short delay for cleanup
                        import time
                        time.sleep(0.5)

                        # Retry connection
                        logger.info("Retrying connection after cleanup...")
                        self._device = Spectrometer.from_serial_number(target_serial)
                        logger.info("✅ Successfully connected after cleanup")
                    except Exception as retry_error:
                        logger.error(f"Cleanup and retry failed: {retry_error}")
                        raise
                else:
                    raise

            # Set connection state
            self.opened = True
            self.serial_number = target_serial
            self.spec = self._device

            # Initialize wavelengths
            try:
                self._wavelengths = self._device.wavelengths()
                self._num_pixels = len(self._wavelengths)
                logger.debug(f"Wavelength range: {self._wavelengths[0]:.1f} - {self._wavelengths[-1]:.1f} nm")
                logger.debug(f"Number of pixels: {self._num_pixels}")
            except Exception as e:
                logger.warning(f"Could not read wavelengths: {e}")

            # Query detector specifications
            try:
                # Try to get max_intensity from device (some detectors provide this)
                max_intensity = getattr(self._device, "max_intensity", None)
                if max_intensity is not None:
                    self._max_counts = int(max_intensity)
                    logger.info(f"Detector max counts from device: {self._max_counts}")
                else:
                    # Default: USB4000/Flame-T use 16-bit ADC
                    # But Flame-T saturates at ~62000, not 65535
                    # Keep conservative default
                    self._max_counts = 65535
                    logger.info(f"Detector max counts (default 16-bit): {self._max_counts}")
            except Exception as e:
                logger.warning(f"Could not determine max counts: {e}")
                self._max_counts = 65535

            # Log detector capabilities
            try:
                min_int_us = self._device.minimum_integration_time_micros
                min_max_limits = self._device.integration_time_micros_limits
                logger.info(
                    f"Detector integration time limits: "
                    f"{min_max_limits[0]/1000:.2f}ms - {min_max_limits[1]/1000:.2f}ms"
                )
            except Exception as e:
                logger.warning(f"Could not read detector capabilities: {e}")

            logger.info(f"USB4000 connected: {self.serial_number}")
            return True

        except Exception as e:
            logger.error(f"USB4000 connection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def close(self):
        """Close connection."""
        try:
            if self._device:
                self._device.close()
        except Exception as e:
            logger.warning(f"Error closing USB4000: {e}")
        finally:
            self.opened = False
            self._device = None
            self.spec = None

    def __del__(self):
        """Destructor to ensure spectrometer is closed."""
        try:
            if hasattr(self, '_device') and self._device is not None:
                self.close()
        except:
            pass

    def set_integration(self, time_ms):
        """Set integration time.

        Args:
            time_ms: Integration time in milliseconds (matches settings.py)
        """
        if not self._device or not self.opened:
            return False
        try:
            # Convert milliseconds to microseconds for SeaBreeze API
            time_us = int(time_ms * 1000)

            # Set the integration time (this is a setter only, returns None)
            self._device.integration_time_micros(time_us)

            # Store in seconds for internal use
            self._integration_time = time_ms / 1000.0
            return True
        except Exception as e:
            logger.error(f"set_integration error: {e}")
            # Check if device was disconnected (errno 19)
            if "[Errno 19]" in str(e) or "No such device" in str(e):
                logger.error("🔌 Spectrometer disconnected during operation")
                self.opened = False
                self._device = None
                raise ConnectionError("Spectrometer disconnected") from e
            return False

    def read_intensity(self):
        """Read intensities."""
        if not self._device or not self.opened:
            return None
        try:
            import numpy as np
            return np.array(self._device.intensities())
        except Exception as e:
            logger.error(f"read_intensity error: {e}")
            # Check if device was disconnected (errno 19)
            if "[Errno 19]" in str(e) or "No such device" in str(e):
                logger.error("🔌 Spectrometer disconnected during operation")
                self.opened = False
                self._device = None
                raise ConnectionError("Spectrometer disconnected") from e
            return None

    @property
    def wavelengths(self):
        """Get wavelengths."""
        if self._wavelengths is not None:
            return self._wavelengths
        if self._device:
            try:
                self._wavelengths = self._device.wavelengths()
                return self._wavelengths
            except Exception as e:
                logger.debug(f"Could not read wavelengths: {e}")
        return None

    @property
    def min_integration(self):
        """Get min integration time."""
        if self._device:
            try:
                # SeaBreeze returns in microseconds, convert to seconds
                return self._device.minimum_integration_time_micros / 1_000_000
            except Exception as e:
                logger.debug(f"Could not read min integration time: {e}")
        return 0.001

    def read_wavelength(self):
        """Get wavelengths array."""
        return self.wavelengths

    @property
    def max_counts(self):
        """Get maximum detector counts (ADC saturation level).

        Returns:
            int: Maximum counts (e.g., 65535 for 16-bit, 62000 for Flame-T)
        """
        return self._max_counts

    @property
    def num_pixels(self):
        """Get number of detector pixels/wavelength points.

        Returns:
            int: Number of pixels (e.g., 3648 for USB4000/Flame-T, 2048 for Phase Photonics)
        """
        return self._num_pixels

    @property
    def target_counts(self):
        """Get recommended target counts for calibration (75% of max).

        Returns:
            int: Target counts for S-mode calibration
        """
        return int(0.75 * self._max_counts)
