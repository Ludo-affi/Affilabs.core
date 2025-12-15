"""USB4000 Spectrometer Driver - GOLDEN reference (pyseabreeze-only).

Single, reliable connection path using pyseabreeze backend.
This version mirrors the working reference in `archive/2025-12-01-cleanup/usb4000_wrapper_GOLDEN.py`.

Note: This wrapper is detector-agnostic. The libusb initialization is optional
and only applies to Ocean Optics spectrometers using pyseabreeze.
"""

from __future__ import annotations

import contextlib
import threading

from affilabs.utils.logger import logger

# OPTIONAL: Initialize libusb for Ocean Optics spectrometers on Windows
# This is not required for all detector types and won't prevent startup if it fails
try:
    from affilabs.utils.libusb_init import get_libusb_backend

    _libusb_backend = get_libusb_backend()

    if _libusb_backend:
        # Monkey-patch usb.core to use our explicit backend
        # This helps Ocean Optics devices connect on Windows
        import usb.core

        _original_find = usb.core.find

        def _patched_find(*args, **kwargs):
            if "backend" not in kwargs:
                kwargs["backend"] = _libusb_backend
            return _original_find(*args, **kwargs)

        usb.core.find = _patched_find
        logger.info("[OK] libusb backend configured for Ocean Optics spectrometers")
    else:
        logger.debug(
            "libusb backend not available (this is OK for non-Ocean Optics detectors)",
        )

except Exception as e:
    # Non-fatal: software should work with other detector types
    logger.debug(f"libusb initialization skipped: {e}")

_usb_device_lock = threading.RLock()


class USB4000:
    def __init__(self, parent=None) -> None:
        self._device = None
        self.opened = False
        self.serial_number = None
        self.spec = None
        self._wavelengths = None
        self._integration_time = 0.1
        self._max_counts = 65535
        self._num_pixels = 3648

    def open(self) -> bool | None:
        try:
            if self.opened and self._device is not None:
                try:
                    _ = self._device.integration_time_micros(0)
                    logger.info("USB4000 already connected and responding")
                    return True
                except Exception as e:
                    logger.warning(
                        f"Existing connection invalid: {e} - reconnecting...",
                    )
                    self.opened = False
                    self._device = None

            logger.info("Connecting to USB4000...")

            try:
                import seabreeze

                seabreeze.use("pyseabreeze")
                from seabreeze.spectrometers import Spectrometer, list_devices

                logger.info(
                    "USB4000: Using pyseabreeze backend (pure Python, WinUSB-compatible)",
                )
            except ImportError as e:
                logger.error(f"SeaBreeze not available: {e}")
                logger.error("Install with: pip install seabreeze pyusb")
                return False

            # On Windows with libusb, force close any stale connections
            # This prevents "already opened" errors after app restart or ghost processes
            try:
                devices_to_cleanup = list_devices()
                if devices_to_cleanup:
                    # Try to close each device up to 2 times (some devices need multiple attempts)
                    for attempt in range(2):
                        for dev in devices_to_cleanup:
                            try:
                                test_spec = Spectrometer(dev)
                                test_spec.close()
                            except Exception as e:
                                # If device says "already opened", try to close it anyway
                                if "already opened" in str(e).lower():
                                    try:
                                        # Sometimes the error IS the handle we need to close
                                        test_spec.close()
                                    except Exception:
                                        pass
                                # Device already closed or not accessible

                        if attempt == 0:
                            import time

                            time.sleep(0.2)  # Wait between attempts

                    import time

                    time.sleep(0.3)  # Give USB stack time to release handles
            except Exception:
                pass

            # Use HardwareManager timeouts if available
            try:
                from affilabs.core.hardware_manager import (
                    CONNECTION_TIMEOUT,
                    HARDWARE_DEBUG,
                )
            except Exception:
                try:
                    from core.hardware_manager import CONNECTION_TIMEOUT, HARDWARE_DEBUG
                except Exception:
                    HARDWARE_DEBUG = False
                    CONNECTION_TIMEOUT = 8.0

            if HARDWARE_DEBUG:
                logger.debug(
                    f"Scanning for Ocean Optics devices ({CONNECTION_TIMEOUT}s timeout)...",
                )

            devices = []
            exception = [None]

            def scan_devices() -> None:
                try:
                    nonlocal devices
                    devices = list_devices()
                except Exception as e:
                    exception[0] = e

            scan_thread = threading.Thread(target=scan_devices, daemon=True)
            scan_thread.start()
            scan_thread.join(timeout=CONNECTION_TIMEOUT)

            if scan_thread.is_alive():
                logger.warning(
                    f"USB device scan timed out after {CONNECTION_TIMEOUT}s - no spectrometer",
                )
                return False

            if exception[0]:
                logger.error(f"USB device scan failed: {exception[0]}")
                return False

            logger.info(f"SeaBreeze found {len(devices)} device(s)")
            for idx, dev in enumerate(devices):
                with contextlib.suppress(Exception):
                    logger.info(
                        f"  Device[{idx}] serial={getattr(dev, 'serial_number', 'N/A')} model={getattr(dev, 'model', 'N/A')}",
                    )

            if not devices:
                logger.warning("No USB4000 devices found")
                return False

            dev0 = devices[0]
            target_serial = getattr(dev0, "serial_number", None)
            logger.info(f"Connecting to device serial: {target_serial}")

            connection_exception = [None]

            def connect_device() -> None:
                try:
                    nonlocal connection_exception
                    self._device = Spectrometer.from_serial_number(target_serial)
                except Exception as e:
                    connection_exception[0] = e

            cth = threading.Thread(target=connect_device, daemon=True)
            cth.start()
            cth.join(timeout=CONNECTION_TIMEOUT)

            if cth.is_alive():
                logger.error(
                    f"Spectrometer connection timed out after {CONNECTION_TIMEOUT}s",
                )
                return False

            if connection_exception[0] is not None:
                e = connection_exception[0]
                if "already opened" in str(e).lower():
                    logger.warning("Device already opened - attempting reuse...")
                    try:
                        for dev in list_devices():
                            if getattr(dev, "serial_number", None) == target_serial:
                                try:
                                    self._device = Spectrometer(dev)
                                    logger.info(
                                        "Successfully reused existing open connection",
                                    )
                                    break
                                except Exception:
                                    pass
                        if self._device is None:
                            logger.warning(
                                "Reuse failed - closing any stuck connections...",
                            )
                            for dev in list_devices():
                                try:
                                    spec = Spectrometer(dev)
                                    spec.close()
                                except Exception:
                                    pass
                            import time

                            time.sleep(0.5)
                            self._device = Spectrometer.from_serial_number(
                                target_serial,
                            )
                            logger.info("Successfully connected after cleanup")
                    except Exception as retry_error:
                        logger.error(f"Cleanup and retry failed: {retry_error}")
                        return False
                else:
                    logger.error(f"Connection failed via from_serial_number: {e}")
                    logger.info(
                        "Attempting direct Spectrometer(devices[0]) fallback...",
                    )
                    try:
                        fallback_exception = [None]

                        def fallback_connect() -> None:
                            try:
                                nonlocal fallback_exception
                                self._device = Spectrometer(dev0)
                            except Exception as fe:
                                fallback_exception[0] = fe

                        fb = threading.Thread(target=fallback_connect, daemon=True)
                        fb.start()
                        fb.join(timeout=CONNECTION_TIMEOUT)
                        if fb.is_alive():
                            logger.error(
                                f"Fallback connection timed out after {CONNECTION_TIMEOUT}s",
                            )
                            return False
                        if fallback_exception[0] is not None:
                            logger.error(
                                f"Fallback connection failed: {fallback_exception[0]}",
                            )
                            return False
                        target_serial = target_serial or getattr(
                            dev0,
                            "serial_number",
                            None,
                        )
                        logger.info("Fallback Spectrometer(devices[0]) connected")
                    except Exception as fe_outer:
                        logger.error(
                            f"Direct instantiation fallback failed: {fe_outer}",
                        )
                        return False

            self.opened = True
            self.serial_number = target_serial
            self.spec = self._device

            try:
                self._wavelengths = self._device.wavelengths()
                self._num_pixels = len(self._wavelengths)
            except Exception as e:
                logger.warning(f"Could not read wavelengths: {e}")

            try:
                max_intensity = getattr(self._device, "max_intensity", None)
                if max_intensity is not None:
                    self._max_counts = int(max_intensity)
                else:
                    self._max_counts = 65535
            except Exception:
                self._max_counts = 65535

            return True

        except Exception as e:
            logger.error(f"USB4000 connection failed: {e}")
            try:
                import traceback

                logger.error(traceback.format_exc())
            except Exception:
                pass
            return False

    def close(self) -> None:
        try:
            if self._device:
                with _usb_device_lock:
                    self._device.close()
                logger.debug("USB4000 device closed")
        except Exception as e:
            logger.warning(f"Error closing USB4000: {e}")
        finally:
            self.opened = False
            self._device = None
            self.spec = None

    def __del__(self) -> None:
        try:
            if hasattr(self, "_device") and self._device is not None:
                self.close()
        except Exception:
            pass

    def set_integration(self, time_ms) -> bool | None:
        if not self._device or not self.opened:
            return False
        try:
            time_us = int(time_ms * 1000)
            with _usb_device_lock:
                self._device.integration_time_micros(time_us)
            self._integration_time = time_ms / 1000.0
            return True
        except Exception as e:
            logger.error(f"set_integration error: {e}")
            if "[Errno 19]" in str(e) or "No such device" in str(e):
                logger.error("Spectrometer disconnected during operation")
                self.opened = False
                self._device = None
                msg = "Spectrometer disconnected"
                raise ConnectionError(msg) from e
            return False

    def read_intensity(self):
        """Read single spectrum (legacy method)."""
        if not self._device or not self.opened:
            return None
        try:
            import numpy as np

            with _usb_device_lock:
                return np.array(self._device.intensities())
        except Exception as e:
            logger.error(f"read_intensity error: {e}")
            if "[Errno 19]" in str(e) or "No such device" in str(e):
                logger.error("Spectrometer disconnected during operation")
                self.opened = False
                self._device = None
                msg = "Spectrometer disconnected"
                raise ConnectionError(msg) from e
            return None

    def intensities(self, num_scans=1):
        """Read spectrum with optional averaging (adapter-compatible method).

        Args:
            num_scans: Number of scans to average (default=1)

        Returns:
            numpy array of intensities, or None if error

        """
        if not self._device or not self.opened:
            return None
        try:
            import numpy as np

            with _usb_device_lock:
                if num_scans == 1:
                    # Single scan - direct read
                    return np.array(self._device.intensities())
                # Multiple scans - average them
                scans = []
                for _ in range(num_scans):
                    scans.append(self._device.intensities())
                return np.mean(scans, axis=0)
        except Exception as e:
            logger.error(f"intensities error: {e}")
            if "[Errno 19]" in str(e) or "No such device" in str(e):
                logger.error("Spectrometer disconnected during operation")
                self.opened = False
                self._device = None
                msg = "Spectrometer disconnected"
                raise ConnectionError(msg) from e
            return None

    @property
    def wavelengths(self):
        if self._wavelengths is not None:
            return self._wavelengths
        if self._device:
            try:
                with _usb_device_lock:
                    self._wavelengths = self._device.wavelengths()
                return self._wavelengths
            except Exception as e:
                logger.debug(f"Could not read wavelengths: {e}")
        return None

    @property
    def min_integration(self):
        if self._device:
            try:
                with _usb_device_lock:
                    return self._device.minimum_integration_time_micros / 1_000_000
            except Exception as e:
                logger.debug(f"Could not read min integration time: {e}")
        return 0.001

    @property
    def integration_time(self):
        return self._integration_time

    def get_integration_ms(self):
        return float(self._integration_time * 1000.0)

    def read_wavelength(self):
        return self.wavelengths

    @property
    def max_counts(self):
        return self._max_counts

    @property
    def num_pixels(self):
        return self._num_pixels

    @property
    def target_counts(self):
        return int(0.70 * self._max_counts)
