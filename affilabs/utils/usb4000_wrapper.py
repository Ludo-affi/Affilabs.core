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

        # Patch seabreeze USBTransport.list_devices to skip phantom Windows USB entries.
        # On Windows, replugging creates a phantom device entry (same VID/PID, wrong driver)
        # that seabreeze crashes on instead of skipping. We pre-filter: only yield handles
        # whose underlying pyusb device responds to set_configuration() (real device).
        try:
            from seabreeze.pyseabreeze.transport import USBTransport

            _original_usb_list = USBTransport.list_devices.__func__

            @classmethod  # type: ignore[misc]
            def _patched_usb_list(cls, **kwargs):
                for handle in _original_usb_list(cls, **kwargs):
                    try:
                        handle.pyusb_device.set_configuration()
                        yield handle
                    except Exception:
                        logger.debug(
                            f"Skipping phantom USB device (set_configuration failed): "
                            f"VID={hex(handle.pyusb_device.idVendor)} "
                            f"PID={hex(handle.pyusb_device.idProduct)}"
                        )

            USBTransport.list_devices = _patched_usb_list
            logger.info("[OK] SeaBreeze phantom-device filter installed")
        except Exception as patch_err:
            logger.debug(f"SeaBreeze phantom patch skipped: {patch_err}")

    else:
        logger.debug(
            "libusb backend not available (this is OK for non-Ocean Optics detectors)",
        )

except Exception as e:
    # Non-fatal: software should work with other detector types
    logger.debug(f"libusb initialization skipped: {e}")

_usb_device_lock = threading.RLock()


def reset_usb_spectrometers():
    """Software reset of USB spectrometers (power cycle without physical disconnect).

    This function attempts to reset Ocean Optics USB spectrometers that are in a
    stuck state. Useful when the device shows "already opened" or won't reconnect
    after an unexpected disconnect.

    Returns:
        bool: True if reset was attempted, False if no devices found or error
    """
    try:
        import usb.core
        import usb.util
        import time

        logger.debug("USB spectrometer software reset...")

        # Ocean Optics USB4000 VID/PID
        OCEAN_OPTICS_VID = 0x2457  # Ocean Optics vendor ID

        # Try to get the backend we configured
        backend = None
        try:
            from affilabs.utils.libusb_init import get_libusb_backend
            backend = get_libusb_backend()
        except Exception:
            pass

        # Find all Ocean Optics devices
        devices = usb.core.find(
            find_all=True,
            idVendor=OCEAN_OPTICS_VID,
            backend=backend
        )

        device_list = list(devices)
        if not device_list:
            logger.warning("No Ocean Optics USB devices found for reset")
            return False

        logger.debug(f"Found {len(device_list)} Ocean Optics device(s)")

        reset_count = 0
        for dev in device_list:
            try:
                # Get device info with timeout to prevent hanging
                device_info = f"Device VID=0x{dev.idVendor:04x} PID=0x{dev.idProduct:04x}"
                try:
                    # Use a short timeout for getting device strings
                    def get_device_info():
                        nonlocal device_info
                        try:
                            serial = usb.util.get_string(dev, dev.iSerialNumber)
                            product = usb.util.get_string(dev, dev.iProduct)
                            device_info = f"{product} (S/N: {serial})"
                        except Exception:
                            pass

                    info_thread = threading.Thread(target=get_device_info, daemon=True)
                    info_thread.start()
                    info_thread.join(timeout=1.0)  # 1 second timeout
                except Exception:
                    pass

                logger.debug(f"  Resetting: {device_info}")

                # Perform USB reset (equivalent to unplug/replug)
                dev.reset()
                reset_count += 1
                logger.debug("  Reset successful")

            except usb.core.USBError as e:
                # Permission errors are common on Windows - not critical
                if e.errno == 13:  # Permission denied
                    logger.warning("  ⚠️  Reset skipped (permission denied - device may be in use)")
                else:
                    logger.warning(f"  ⚠️  Reset failed: {e}")
            except Exception as e:
                logger.warning(f"  ⚠️  Reset failed: {e}")

        if reset_count > 0:
            logger.debug(f"Reset {reset_count} device(s) - waiting for re-enumeration...")
            time.sleep(2.0)  # Give USB stack time to re-enumerate devices
            logger.debug("USB reset complete")
            return True
        else:
            logger.warning("No devices were successfully reset")
            return False

    except ImportError:
        logger.warning("PyUSB not available - cannot perform USB reset")
        logger.info("Install with: pip install pyusb")
        return False
    except Exception as e:
        logger.error(f"USB reset failed: {e}")
        return False


class USB4000:
    def __init__(self, parent=None) -> None:
        self._device = None
        self._device_handle = None  # Strong reference to prevent GC
        self._usb_device = None  # Keep device descriptor alive
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

            logger.debug("Connecting to USB4000...")

            try:
                import seabreeze

                seabreeze.use("pyseabreeze")
                from seabreeze.spectrometers import Spectrometer, list_devices

                logger.debug("USB4000: pyseabreeze backend")
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

            logger.debug(f"SeaBreeze found {len(devices)} device(s)")
            for idx, dev in enumerate(devices):
                with contextlib.suppress(Exception):
                    logger.debug(
                        f"  Device[{idx}] serial={getattr(dev, 'serial_number', 'N/A')} model={getattr(dev, 'model', 'N/A')}",
                    )

            if not devices:
                logger.warning("No USB4000 devices found")
                return False

            dev0 = devices[0]
            target_serial = getattr(dev0, "serial_number", None)
            logger.debug(f"Connecting to device serial: {target_serial}")

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
                        # If device still reports 'already opened', attempt direct instantiation once more
                        try:
                            if "already opened" in str(retry_error).lower():
                                logger.warning(
                                    "Device reports 'already opened' after cleanup - attempting direct Spectrometer(dev0) attach",
                                )
                                self._device = Spectrometer(dev0)
                                logger.info("Successfully attached to existing open device")
                            else:
                                return False
                        except Exception as final_attach_err:
                            logger.error(f"Final attach failed: {final_attach_err}")
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

            # Keep strong reference to prevent garbage collection
            # Seabreeze uses weak references internally which can cause
            # "weakly-referenced object no longer exists" errors
            self._device_handle = self._device
            self._usb_device = dev0  # Keep device descriptor alive

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

    def close(self, silent: bool = False) -> None:
        """Close the USB4000 device connection.

        Args:
            silent: If True, suppress logging (used during Python shutdown)
        """
        try:
            if self._device:
                with _usb_device_lock:
                    self._device.close()
                if not silent:
                    try:
                        logger.debug("USB4000 device closed")
                    except (NameError, TypeError):
                        pass  # Logger unavailable during shutdown
        except Exception as e:
            if not silent:
                try:
                    logger.warning(f"Error closing USB4000: {e}")
                except (NameError, TypeError):
                    pass  # Logger unavailable during shutdown
        finally:
            self.opened = False
            self._device = None
            self._device_handle = None  # Clear strong reference
            self._usb_device = None  # Clear device descriptor
            self.spec = None

    def __del__(self) -> None:
        try:
            if hasattr(self, "_device") and self._device is not None:
                self.close(silent=True)  # Silent during shutdown to avoid logging errors
        except Exception:
            pass

    def set_integration(self, time_ms) -> bool | None:
        if not self._device or not self.opened:
            logger.error(f"set_integration FAILED: device={self._device is not None}, opened={self.opened}")
            return False
        try:
            # FLOOR: Enforce 4.5ms minimum for stable USB communication
            # Ocean Optics USB4000/Flame-T hardware limit is 3.5ms, but requires
            # safety margin. Testing shows 3.8ms still causes timeouts in iteration 2.
            # 4.5ms provides 1ms safety margin for reliable operation.
            time_ms = max(4.5, time_ms)

            time_us = int(time_ms * 1000)  # SeaBreeze API requires microseconds
            with _usb_device_lock:
                self._device.integration_time_micros(time_us)
            self._integration_time = time_ms / 1000.0  # Store in seconds

            # CRITICAL: Add settling delay after integration time change
            # Python 3.12 is faster and may trigger USB timeouts if we read too quickly
            # after changing integration time. Give device time to reconfigure.
            import time
            time.sleep(0.15)  # 150ms settling delay

            return True
        except Exception as e:
            logger.error(f"set_integration error for {time_ms:.1f}ms ({time_us}us, {time_ms/1000:.4f}s): {e}")
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
        # FLOOR: Return 3.5ms minimum for Ocean Optics USB stability
        # CRITICAL: USB4000/Flame-T require 3.5ms minimum for stable USB communication
        # Below 3.5ms causes USB timeout errors (Errno 10060)
        if self._device:
            try:
                with _usb_device_lock:
                    hw_min = self._device.minimum_integration_time_micros / 1_000_000
                    return max(0.0035, hw_min)  # Enforce 3.5ms floor (was 3ms - too low!)
            except Exception as e:
                logger.debug(f"Could not read min integration time: {e}")
        return 0.0035  # 3.5ms default floor (CRITICAL for USB stability)

    @property
    def min_integration_ms(self):
        """Minimum integration time in milliseconds (3.5ms floor for Ocean Optics USB stability)."""
        return self.min_integration * 1000.0

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
    def dark_current(self):
        """Typical dark current baseline in counts (USB4000)."""
        return 3000  # USB4000 typical dark current

    @property
    def num_pixels(self):
        return self._num_pixels

    @property
    def target_counts(self):
        return int(0.70 * self._max_counts)
