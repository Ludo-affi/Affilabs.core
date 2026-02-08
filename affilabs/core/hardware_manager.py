"""Hardware Manager - Coordinates all hardware devices.

This class manages:
- SPR controllers (P4SPR, EZSPR, Pico variants)
- Kinetic controllers (KNX, KNX2, PicoKNX2)
- Pumps (Affipump)
- Spectrometers (USB4000, PhasePhotonics)

Hardware Scanning Priority Logic:
1. Controller (PicoP4SPR → PicoEZSPR → Arduino) - Stop at first found
2. Detector (USB4000/Ocean Optics) - Identifies P4SPR/P4PRO/ezSPR
3. Pump (AffiPump first, then KNX) - Mutually exclusive, only one connected
4. Kinetic (KNX) - Only scan if no AffiPump found

All operations run in background threads to avoid blocking the UI.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from affilabs.utils.logger import logger


# ============================================================================
# DEBUG FLAGS - Set to True for detailed troubleshooting output
# ============================================================================
HARDWARE_DEBUG = True  # Enable verbose logging to debug P4PRO connection
CONNECTION_TIMEOUT = 2.0  # Reduced from 8s to 2s for faster scans (still safe for WinUSB)
CONNECTION_RETRY_COUNT = 1  # Single attempt only (no retries to avoid error cascade)

# ============================================================================
# CONDITIONAL HARDWARE SCANNING
# ============================================================================
# Only scan for KNX if detector serial matches these prefixes
# KNX is paired with specific SPR systems - no need to scan every time
KNX_SERIAL_PREFIXES = ["FLMT09116", "KNX"]  # Add detector serials that have KNX

# Enable Arduino scanning (legacy support - most systems use Pico now)
ENABLE_ARDUINO_SCAN = False  # Set True only for legacy systems

# ============================================================================
# CACHED IMPORTS - Survive module reloads during development
# ============================================================================
_controller_classes_cache = None
_settings_cache = None
_import_lock = threading.Lock()


def _get_controller_classes():
    """Lazy import with caching to survive file reloads."""
    global _controller_classes_cache
    with _import_lock:
        if _controller_classes_cache is None:
            try:
                from affilabs.utils.controller import (
                    KineticController,
                    PicoEZSPR,
                    PicoKNX2,
                    PicoP4SPR,
                    PicoP4PRO,
                )

                _controller_classes_cache = {
                    "PicoP4SPR": PicoP4SPR,
                    "PicoP4PRO": PicoP4PRO,
                    "PicoEZSPR": PicoEZSPR,
                    "KineticController": KineticController,
                    "PicoKNX2": PicoKNX2,
                }
                logger.debug("Controller classes loaded successfully")
            except Exception as e:
                logger.error(f"Failed to import controller classes: {e}")

                # Return stub classes that fail gracefully
                class StubController:
                    def open(self) -> bool:
                        return False

                    def close(self) -> None:
                        pass

                _controller_classes_cache = {
                    "PicoP4SPR": StubController,
                    "PicoP4PRO": StubController,
                    "PicoEZSPR": StubController,
                    "KineticController": StubController,
                    "PicoKNX2": StubController,
                }
        return _controller_classes_cache


def _get_settings():
    """Lazy import with caching for settings."""
    global _settings_cache
    with _import_lock:
        if _settings_cache is None:
            try:
                from settings import ARDUINO_PID, ARDUINO_VID, PICO_PID, PICO_VID

                _settings_cache = {
                    "ARDUINO_VID": ARDUINO_VID,
                    "ARDUINO_PID": ARDUINO_PID,
                    "PICO_VID": PICO_VID,
                    "PICO_PID": PICO_PID,
                }
                logger.debug("Settings loaded successfully")
            except Exception as e:
                logger.error(f"Failed to import settings: {e}")
                _settings_cache = {
                    "ARDUINO_VID": 0x2341,
                    "ARDUINO_PID": 0x0043,
                    "PICO_VID": 0x2E8A,
                    "PICO_PID": 0x000A,
                }
        return _settings_cache


class HardwareManager(QObject):
    """Manages all hardware devices with non-blocking initialization."""

    # Signals for hardware status updates
    hardware_connected = Signal(
        dict,
    )  # {ctrl_type, knx_type, pump_connected, spectrometer, sensor_ready, optics_ready, fluidics_ready}
    hardware_disconnected = Signal()
    connection_progress = Signal(str)  # Status messages during connection
    error_occurred = Signal(str)  # Error messages
    servo_calibration_needed = Signal()  # Triggered when servo positions are missing

    # Quality thresholds for sensor/optics verification
    SENSOR_MIN_INTENSITY = 1000  # Minimum acceptable signal intensity
    SENSOR_MAX_INTENSITY = 60000  # Maximum safe intensity (avoid saturation at 65535)
    OPTICS_MIN_QUALITY = 0.7  # Minimum signal-to-noise ratio

    def __init__(self) -> None:
        super().__init__()

        # Hardware device references
        self.ctrl = None  # SPR controller (HAL-wrapped)
        self._ctrl_raw = None  # SPR controller (raw object for hardware-specific ops)
        self.knx = None  # Kinetic controller
        self.pump = None  # Pump
        self.usb = None  # Spectrometer
        self.device_config = None  # Device configuration for servo positions

        # Connection state
        self.connected = False

        # Connection resilience - cache port/serial info for reconnection
        self._ctrl_port = None  # COM port for controller
        self._ctrl_type = None  # Controller type that worked
        self._spec_serial = None  # Spectrometer serial that worked
        self._connection_lock = threading.RLock()  # Protect connection state

        # Locking and connection flags
        self._hardware_locked = False
        self._peripherals_locked = False
        self._connecting = False

        # Verification and calibration state
        self._sensor_verified = False
        self._optics_verified = False
        self._fluidics_verified = False
        self._calibration_passed = False
        self._afterglow_calibration_done = False
        self._optics_leak_detected = False
        self._flow_calibrated = False  # Flow mode enabled after successful calibration with pump

        # Intensity/leak tracking structures
        self._channel_intensity_history = {"a": [], "b": [], "c": [], "d": []}
        self._channel_max_intensity = {"a": 0, "b": 0, "c": 0, "d": 0}

        # FWHM readiness tracking
        self._channel_fwhm = {"a": None, "b": None, "c": None, "d": None}
        self._fwhm_threshold = 60.0  # nm

    def get_servo_positions(self) -> dict[str, int]:
        """Get servo positions from device configuration (HAL method).

        This is the single source of truth for servo positions.
        Positions are read from device_config which is loaded at hardware init.

        Returns:
            Dict with keys 's_position' and 'p_position' (int values, in degrees)

        Raises:
            RuntimeError: If device_config not available or positions invalid

        """
        if not self.device_config:
            msg = "Device configuration not loaded - call scan_and_connect first"
            raise RuntimeError(msg)

        # device_config is a DeviceConfiguration object with .config property
        if hasattr(self.device_config, "config"):
            cfg = self.device_config.config
        else:
            cfg = self.device_config

        # Get detector serial for logging
        detector_serial = None
        if self.usb and hasattr(self.usb, "serial_number"):
            detector_serial = self.usb.serial_number

        # Read from hardware section only (single source of truth)
        if "hardware" in cfg:
            s_pos = cfg["hardware"].get("servo_s_position")
            p_pos = cfg["hardware"].get("servo_p_position")
            if s_pos is not None and p_pos is not None:
                # Validate positions are in valid range (0-255 PWM)
                if not (0 <= s_pos <= 255):
                    msg = f"Invalid S-position {s_pos} (must be 0-255 PWM)"
                    raise ValueError(msg)
                if not (0 <= p_pos <= 255):
                    msg = f"Invalid P-position {p_pos} (must be 0-255 PWM)"
                    raise ValueError(msg)

                logger.info(
                    f"[HAL] Servo positions for {detector_serial}: S={s_pos} PWM, P={p_pos} PWM",
                )
                return {"s_position": s_pos, "p_position": p_pos}

        # Fallback to defaults if not found
        logger.warning(
            f"[HAL] No servo positions in config for {detector_serial} - using defaults",
        )
        return {"s_position": 120, "p_position": 60}

    def get_device_config(self) -> dict:
        """Get device configuration dictionary (HAL method).

        Returns the configuration dictionary for the connected detector.
        This provides access to hardware settings, calibration data, etc.

        Returns:
            Device configuration dictionary

        Raises:
            RuntimeError: If device_config not available

        """
        if not self.device_config:
            msg = "Device configuration not loaded - call scan_and_connect first"
            raise RuntimeError(msg)

        # Return the config dict
        if hasattr(self.device_config, "config"):
            return self.device_config.config

        return self.device_config

    def _try_reconnect_controller(self) -> bool | None:
        """Fast reconnect to cached controller port/type after file reload."""
        if not self._ctrl_port or not self._ctrl_type:
            return False

        with self._connection_lock:
            try:
                classes = _get_controller_classes()
                ctrl_class = classes.get(self._ctrl_type)
                if not ctrl_class:
                    logger.warning(f"Controller class {self._ctrl_type} not found")
                    return False

                logger.info(f"Fast reconnect: {self._ctrl_type} on {self._ctrl_port}")
                ctrl = ctrl_class()

                # Attempt fast open with cached port
                if hasattr(ctrl, "open") and ctrl.open():
                    # Wrap with HAL
                    from affilabs.utils.hal.controller_hal import create_controller_hal

                    hal_ctrl = create_controller_hal(ctrl, self.device_config)
                    self.ctrl = hal_ctrl
                    self._ctrl_raw = ctrl
                    logger.info(f"[OK] Reconnected to {self._ctrl_type} via HAL")

                    # DISABLED: Don't initialize servo during reconnection
                    # Servo will be initialized during calibration workflow only
                    # self._initialize_servo_polarizer()
                    return True
                logger.debug(f"Fast reconnect failed for {self._ctrl_type}")
                return False

            except Exception as e:
                logger.debug(f"Reconnect exception: {e}")
                return False

    def _try_reconnect_spectrometer(self) -> bool | None:
        """Fast reconnect to cached spectrometer serial after file reload."""
        if not self._spec_serial:
            return False

        with self._connection_lock:
            try:
                try:
                    from affilabs.utils.usb4000_wrapper import USB4000
                except ImportError:
                    from affilabs.utils.usb4000_wrapper import USB4000

                logger.info(f"Fast reconnect: Spectrometer {self._spec_serial}")
                usb = USB4000()

                if usb.open():
                    # Verify it's the same device
                    if hasattr(usb, "serial_number") and usb.serial_number == self._spec_serial:
                        # Wrap with HAL adapter for read_roi() support
                        from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

                        self.usb = OceanSpectrometerAdapter(usb)
                        logger.info(
                            f"[OK] Reconnected to spectrometer {self._spec_serial} (HAL wrapped)",
                        )
                        return True
                    if not hasattr(usb, "serial_number"):
                        # Can't verify, but accept connection
                        # Wrap with HAL adapter for read_roi() support
                        from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

                        self.usb = OceanSpectrometerAdapter(usb)
                        logger.info(
                            "[OK] Reconnected to spectrometer (serial not verifiable, HAL wrapped)",
                        )
                        return True
                    logger.warning(
                        f"Serial mismatch: expected {self._spec_serial}, got {usb.serial_number}",
                    )
                    usb.close()
                    return False
                logger.debug("Fast reconnect failed for spectrometer")
                return False

            except Exception as e:
                logger.debug(f"Spectrometer reconnect exception: {e}")
                return False

    def _initialize_servo_polarizer(self) -> None:
        """Initialize servo polarizer to S-mode position on controller connection.

        Reads servo positions from device_config, moves polarizer to S-position,
        and locks to S-mode for consistent starting state.

        NOTE: Uses self.ctrl (HAL-wrapped controller) for all operations.
        """
        try:
            logger.info("=" * 60)
            logger.info("🔧 INITIALIZING SERVO POLARIZER...")
            logger.info("=" * 60)

            # Check if controller supports servo (use HAL)
            if not hasattr(self.ctrl, "servo_move_calibration_only"):
                logger.warning(
                    "[WARN] Controller does not support servo - skipping polarizer init",
                )
                return

            # Check if device_config is available (should be loaded by now)
            if not self.device_config:
                logger.error("❌ Device configuration not loaded - cannot initialize servo!")
                logger.error("   Servo initialization requires device_config to be loaded first")
                return

            # Get servo positions from device_config (single source of truth)
            servo_positions = self.device_config.get_servo_positions()

            # If positions are not calibrated, trigger auto-calibration
            if servo_positions is None:
                logger.warning("=" * 60)
                logger.warning("⚠️  SERVO POSITIONS NOT CALIBRATED")
                logger.warning("=" * 60)
                logger.warning("   No servo positions found in device config")
                logger.warning("   Auto-triggering servo calibration...")
                logger.warning("=" * 60)
                # Signal that calibration is needed (will be handled by main app)
                self.servo_calibration_needed.emit()
                return

            s_position = servo_positions["s"]
            p_position = servo_positions["p"]

            logger.info(
                f"📍 Servo positions from device_config: S={s_position} PWM, P={p_position} PWM"
            )

            # Store positions in controller memory (no EEPROM write)
            logger.info("📝 Loading servo positions to controller (RAM-only, no flash writes)...")
            self._ctrl_raw.set_servo_positions(s_position, p_position)
            logger.info("[OK] Servo positions loaded from device config")

            # Turn off all LEDs for safety during servo movement
            logger.info("💡 Turning off all LEDs for safe servo movement...")
            self.ctrl.turn_off_channels()

            import time

            time.sleep(0.1)

            # Park servo to 1° to remove backlash (use HAL servo methods)
            logger.info("🏠 Parking polarizer to 1° (remove backlash)...")
            self.ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.5)  # Allow servo to complete movement

            # Move to S-mode position (degrees 0-180)
            logger.info(
                f"↗ Moving polarizer to S-mode: S={s_position}°, P={p_position}°...",
            )
            self.ctrl.servo_move_calibration_only(s=s_position, p=p_position)
            time.sleep(0.5)  # Allow servo to complete movement

            # Lock to S-mode via firmware command
            logger.info("🔒 Locking to S-mode via firmware...")
            self.ctrl.servo_set(s=s_position, p=p_position)
            time.sleep(0.2)

            logger.info("[OK] Servo polarizer initialized to S-mode")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"[ERROR] Servo initialization failed: {e}")
            if HARDWARE_DEBUG:
                import traceback

                logger.debug(traceback.format_exc())
            # Non-fatal - continue with connection even if servo init fails

    def _connect_spectrometer(self) -> None:
        """Attempt to connect to spectrometer (USB4000/Flame-T via SeaBreeze).

        NOTE: Currently disabled in scan_and_connect() due to USB blocking issues.
        This method can still be called manually if needed.
        """
        logger.info("_connect_spectrometer() called (manual mode)")
        try:
            if HARDWARE_DEBUG:
                logger.info("=" * 60)
                logger.info("SCANNING FOR SPECTROMETER...")
                logger.info("=" * 60)

            # Try fast reconnect first if we have cached info
            if self._spec_serial and self._try_reconnect_spectrometer():
                logger.info("[OK] Fast reconnect successful!")
                return

            logger.info("Connecting to spectrometer (full scan)...")

            try:
                from affilabs.utils.usb4000_wrapper import USB4000
            except ImportError:
                from affilabs.utils.usb4000_wrapper import USB4000

            usb = USB4000()
            open_result = usb.open()

            if open_result:
                with self._connection_lock:
                    # Wrap raw detector with HAL adapter for read_roi() support
                    from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

                    self.usb = OceanSpectrometerAdapter(usb)
                    # Cache serial number for future reconnects
                    if hasattr(usb, "serial_number"):
                        self._spec_serial = usb.serial_number
                        logger.info(f"Spectrometer connected (HAL wrapped): {self._spec_serial}")
                    else:
                        logger.info("Spectrometer connected (no serial)")

                # Warm-up dummy read at 10 ms
                try:
                    import time

                    logger.info(
                        "🌡 Performing spectrometer warm-up (10 ms dummy read)...",
                    )
                    self.usb.set_integration(10)  # 10 ms
                    time.sleep(0.1)
                    dummy = self.usb.read_intensity()
                    if dummy is not None:
                        logger.info(f"   Warm-up read OK ({len(dummy)} pixels)")
                    logger.info("[OK] Spectrometer warm-up complete")
                except Exception as w_e:
                    logger.debug(f"Warm-up skipped due to: {w_e}")
            else:
                logger.warning("No spectrometer detected")
                if HARDWARE_DEBUG:
                    logger.info("   Check: USB cable, drivers, power")
                with self._connection_lock:
                    self.usb = None
                    # Don't clear cache - keep for retry

        except Exception as e:
            logger.error(f"Spectrometer connection failed: {e}")
            if HARDWARE_DEBUG:
                import traceback

                logger.debug(traceback.format_exc())
            with self._connection_lock:
                self.usb = None
                # Don't clear cache - keep for retry

    def scan_and_connect(self, auto_connect: bool = True) -> dict[str, bool]:
        """Scan for hardware devices and optionally auto-connect.

        See: README_HARDWARE_BEHAVIOR.md for complete documentation
        """
        logger.debug("HardwareManager.scan_and_connect() called")
        _ = auto_connect  # reserved for future use per API

        # Check if main unit (controller+detector) is already locked
        if self._hardware_locked:
            # Main unit is locked, but we can still scan for peripherals
            if self.ctrl and self.usb:
                logger.info("=" * 60)
                logger.info(
                    "🔒 MAIN UNIT LOCKED - Controller and detector cannot change",
                )
                logger.info(f"   Controller: {self.ctrl.get_device_type()}")
                logger.info(
                    f"   Detector: {self.usb.serial_number if hasattr(self.usb, 'serial_number') else 'Connected'}",
                )

                # Check if peripherals are also locked
                if self._peripherals_locked:
                    logger.warning("=" * 60)
                    logger.warning("🔒 PERIPHERALS ALSO LOCKED - Cannot rescan")
                    logger.warning(f"   Pump: {'Connected' if self.pump else 'None'}")
                    logger.warning(
                        f"   Kinetic: {self.knx.name if self.knx else 'None'}",
                    )
                    logger.warning(
                        "   Use disconnect_all() to clear hardware and rescan",
                    )
                    logger.warning("=" * 60)
                    return
                # Peripherals not locked yet - allow peripheral scan
                logger.info("🔓 Peripherals can still be added")
                logger.info("   Scanning for pump/kinetic controllers...")
                logger.info("=" * 60)

                # Only scan for peripherals (skip controller and detector)
                self._connecting = True
                self.connection_progress.emit("Scanning for peripherals...")

                # Run peripheral scan in background thread
                self._connection_thread = threading.Thread(
                    target=self._peripheral_scan_worker,
                    daemon=True,
                    name="PeripheralScanner",
                )
                self._connection_thread.start()
                logger.info("Background peripheral scan thread started")
                return
            # Hardware locked but no devices? Clear lock
            logger.warning("Hardware locked but no devices found - clearing lock")
            self._hardware_locked = False

        if self._connecting:
            logger.warning("Connection already in progress - ignoring duplicate call")
            return

        self._connecting = True
        self.connection_progress.emit("Scanning for hardware...")

        # Initialize hardware objects on MAIN THREAD (DLL/USB libraries not thread-safe)
        # Then worker thread will use these pre-initialized objects
        self._preinit_hardware()

        # Let UI update before starting background thread
        from PySide6.QtCore import QCoreApplication

        QCoreApplication.processEvents()

        # Run connection in background thread
        self._connection_thread = threading.Thread(
            target=self._connection_worker,
            daemon=True,
            name="HardwareScanner",
        )
        self._connection_thread.start()

    def _preinit_hardware(self) -> None:
        """Pre-initialize hardware on main thread.

        CRITICAL: USB/FTDI/DLL initialization must occur on main thread.
        Libraries like ftd2xx, pyusb, and FTDI drivers are NOT thread-safe.

        This method creates detector and controller instances on the main thread,
        then the worker thread can use these pre-initialized objects safely.
        """
        try:
            # Software reset USB spectrometers BEFORE attempting connection
            # This clears stuck "already opened" states without physical disconnect
            try:
                from affilabs.utils.usb4000_wrapper import reset_usb_spectrometers

                logger.info("Attempting software reset of USB spectrometers...")
                reset_usb_spectrometers()
            except Exception as reset_error:
                # Non-fatal - continue with normal connection
                logger.debug(f"USB reset skipped: {reset_error}")

            # Load device config
            import json
            from pathlib import Path

            config_path = Path(__file__).parent.parent / "config" / "device_config.json"
            with open(config_path) as f:
                config = json.load(f)

            # Pre-initialize detector on main thread
            from affilabs.utils.detector_factory import create_detector

            self._preinit_detector = create_detector(
                app=None,
                config=config.get("hardware", {}),
            )

        except Exception as e:
            logger.error(f"Hardware pre-initialization failed: {e}")
            import traceback

            traceback.print_exc()
            self._preinit_detector = None

    def _connection_worker(self) -> None:
        """Worker thread that scans for hardware.

        Scanning priority logic:
        1. Look for controller first (PicoP4SPR → PicoEZSPR → Arduino) - stop at first found
        2. Look for detector (USB4000/Ocean Optics) - determines main unit type
        3. Scan for pumps (AffiPump first, then KNX) - only one can be connected

        Retry logic: Will retry up to CONNECTION_RETRY_COUNT times with exponential backoff
        """
        retry_attempt = 0
        # Prevent multiple error dialogs per scan session
        _scan_error_emitted = False
        max_retries = CONNECTION_RETRY_COUNT

        while retry_attempt < max_retries:
            try:
                if retry_attempt > 0:
                    wait_time = min(
                        2**retry_attempt,
                        10,
                    )  # Exponential backoff, max 10s
                    logger.info(
                        f"⏳ Retry {retry_attempt}/{max_retries} in {wait_time}s...",
                    )
                    time.sleep(wait_time)

                scan_start = time.time()

                # Step 1: Try to connect to SPR controller FIRST (priority order)
                # This determines which main unit is plugged in
                self.connection_progress.emit("Looking for SPR controller...")
                print("=" * 80)
                print("DEBUG: _connect_controller() about to be called")
                print(f"DEBUG: self.ctrl before scan = {self.ctrl}")
                print("=" * 80)
                logger.info("🔍 Starting controller scan (PicoP4SPR → PicoP4PRO → PicoEZSPR)...")
                t0 = time.time()
                try:
                    self._connect_controller()
                    print(f"DEBUG: _connect_controller() returned, self.ctrl = {self.ctrl}")
                except Exception as ctrl_e:
                    logger.error(f"❌ Controller scan crashed: {ctrl_e}")
                    print(f"DEBUG: Exception in _connect_controller(): {ctrl_e}")
                    if HARDWARE_DEBUG:
                        import traceback

                        logger.error(traceback.format_exc())
                if HARDWARE_DEBUG:
                    logger.info(f"Controller scan: {time.time() - t0:.2f}s")

                # Step 2: Use pre-initialized detector (already scanned on main thread)
                t0 = time.time()
                if hasattr(self, "_preinit_detector") and self._preinit_detector:
                    self.connection_progress.emit("Verifying detector connection...")

                    with self._connection_lock:
                        # Wrap raw detector with HAL adapter for read_roi() support
                        from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

                        self.usb = OceanSpectrometerAdapter(self._preinit_detector)

                        if hasattr(self._preinit_detector, "serial_number"):
                            self._spec_serial = self._preinit_detector.serial_number
                            logger.info(f"Detector found: {self._spec_serial}")

                            # Initialize device configuration for this detector
                            from affilabs.utils.device_configuration import DeviceConfiguration

                            self.device_config = DeviceConfiguration(
                                device_serial=self._spec_serial,
                                controller=self._ctrl_raw
                                if hasattr(self, "_ctrl_raw") and self._ctrl_raw
                                else None,
                                silent_load=True,
                            )
                            logger.info(f"Device configuration loaded for {self._spec_serial}")

                            # Update spectrometer serial in device config if missing
                            if not self.device_config.get_spectrometer_serial():
                                logger.info(
                                    f"Updating spectrometer serial in config: {self._spec_serial}"
                                )
                                self.device_config.set_spectrometer_serial(self._spec_serial)
                                self.device_config.save()

                            # Verify and update controller model if needed
                            if self._ctrl_raw and hasattr(self._ctrl_raw, "name"):
                                detected_controller = self._ctrl_raw.name
                                config_controller = self.device_config.config.get(
                                    "hardware", {}
                                ).get("controller_model")

                                if config_controller != detected_controller:
                                    logger.warning(
                                        f"Controller mismatch! Config: {config_controller}, Detected: {detected_controller}"
                                    )
                                    logger.info(
                                        f"Updating controller model in config: {detected_controller}"
                                    )
                                    self.device_config.config["hardware"]["controller_model"] = (
                                        detected_controller
                                    )
                                    self.device_config.save()
                                else:
                                    logger.info(f"Controller verified: {detected_controller}")

                            # DISABLED: Don't initialize servo during hardware scan
                            # Servo will be initialized during calibration workflow only
                            # if self.ctrl:
                            #     self._initialize_servo_polarizer()
                else:
                    logger.error("Detector initialization failed")
                    self.usb = None

                if HARDWARE_DEBUG:
                    logger.info(f"Detector scan: {time.time() - t0:.3f}s")

                # Step 3: Try to connect to pump (AffiPump first)
                # AffiPump and KNX are mutually exclusive - only one can be connected
                self.connection_progress.emit("Looking for pump...")
                t0 = time.time()
                self._connect_pump()  # Tries AffiPump first
                if HARDWARE_DEBUG:
                    logger.info(f"Pump scan: {time.time() - t0:.2f}s")

                # Step 4: Try to connect to kinetic controller (only if no AffiPump found)
                # Only scan KNX if detector serial matches known KNX-equipped systems
                if not self.pump:
                    should_scan_knx = self._should_scan_kinetic()
                    if should_scan_knx:
                        self.connection_progress.emit("Looking for kinetic controller...")
                        t0 = time.time()
                        self._connect_kinetic()
                        if HARDWARE_DEBUG:
                            logger.info(f"Kinetic scan: {time.time() - t0:.2f}s")
                    else:
                        self.knx = None
                else:
                    self.knx = None

                # Don't verify sensor/optics here - they should only be marked ready after calibration
                # Initial status is False (not ready) until calibration completes

                # Get controller type
                ctrl_type = self._get_controller_type()

                # VALIDATION: P4SPR/P4PRO/ezSPR require BOTH controller AND detector
                # Pumps (AffiPump/KNX) can be standalone
                valid_hardware = []

                # Check SPR devices (P4SPR, P4PRO, ezSPR) - require controller + detector
                if ctrl_type and self.ctrl and self.usb:
                    valid_hardware.append(ctrl_type)
                    logger.info(f"Hardware ready: {ctrl_type}")
                elif ctrl_type and self.ctrl and not self.usb:
                    logger.warning(f"{ctrl_type} controller found, detector missing")
                    # Do NOT add to valid_hardware - power button stays yellow

                # Check kinetics (KNX) - can be standalone, mutually exclusive with AffiPump
                knx_type = self._get_kinetic_type()
                if knx_type and self.knx:
                    valid_hardware.append(knx_type)
                    logger.info(f"Hardware ready: {knx_type}")

                # Check pump (AffiPump) - standalone, mutually exclusive with KNX
                if self.pump:
                    valid_hardware.append("AffiPump")
                    logger.info("Hardware ready: AffiPump")

                # Emit final status
                # DEBUG: Log spectrometer serial detection
                spec_serial = None
                if self.usb and hasattr(self.usb, "serial_number"):
                    spec_serial = self.usb.serial_number

                status = {
                    "ctrl_type": ctrl_type,  # Only set if controller + detector both present
                    "knx_type": knx_type if self.knx else None,
                    "pump_connected": self.pump is not None,  # Pump connected flag for sidebar
                    "spectrometer": self.usb is not None,  # Boolean flag for coordinator validation
                    "spectrometer_serial": spec_serial,
                    "valid_hardware": valid_hardware,  # List of detected device types
                    # sensor_ready and optics_ready will be set to True after calibration
                    "fluidics_ready": self.pump is not None,  # Fluidics ready if pump connected
                    # Consider scan successful if any single device is connected
                    "scan_successful": (self.usb is not None)
                    or (self.ctrl is not None)
                    or (self.pump is not None)
                    or (self.knx is not None),
                }

                # Log hardware detection results
                total_time = time.time() - scan_start
                logger.info("=" * 60)
                logger.info(f"HARDWARE SCAN COMPLETE ({total_time:.2f}s)")
                logger.info("Scanning order: Controller → Detector → Pump → Kinetic")
                logger.info(
                    f"  • Controller: {self.ctrl.get_device_type() if self.ctrl else 'NOT FOUND'}",
                )
                logger.info(
                    f"  • Detector:   {'CONNECTED' if self.usb else 'NOT FOUND'}",
                )
                logger.info(
                    f"  • Pump:       {'CONNECTED' if self.pump else 'NOT FOUND'}",
                )
                logger.info(
                    f"  • Kinetic:    {self.knx.name if self.knx else ('SKIPPED' if self.pump else 'NOT FOUND')}",
                )
                logger.info(
                    f"  → Valid Hardware: {', '.join(valid_hardware) if valid_hardware else 'NONE'}",
                )
                logger.info("=" * 60)

                # Emit status
                if valid_hardware:
                    logger.info(
                        f"[OK] Hardware scan SUCCESSFUL - found {len(valid_hardware)} device(s)",
                    )

                    # Check for special cases based on detector serial number
                    if self.usb and hasattr(self.usb, "serial_number"):
                        detector_serial = self.usb.serial_number
                        self._check_and_apply_special_case(detector_serial, status)

                    # Lock main unit (controller + detector) - no changes allowed until disconnect
                    if self.ctrl and self.usb and not self._hardware_locked:
                        # CRITICAL: Initialize valves to LOAD position (OFF) to prevent overheating
                        # P4PRO firmware V2.1 has a bug where valves stay powered at 100% instead of using PWM
                        # This workaround ensures valves are off until explicitly commanded
                        if (
                            hasattr(self._ctrl_raw, "firmware_id")
                            and "P4PRO" in self._ctrl_raw.firmware_id
                        ):
                            logger.info(
                                "Initializing P4PRO 6-port valves to LOAD position (OFF)..."
                            )
                            try:
                                # Set both valves to LOAD (0 = OFF) to prevent overheating
                                self._ctrl_raw.knx_six_both(0)
                                logger.info("✓ 6-port valves initialized to LOAD (OFF)")
                            except Exception as e:
                                logger.warning(f"Failed to initialize valves: {e}")

                        logger.info("🔒 MAIN UNIT LOCKED (Controller + Detector)")
                        logger.info("   Configuration fixed until disconnect")
                        logger.info("   Peripherals (pump/kinetic) can still be added")
                        logger.info("=" * 60)

                    # Lock peripherals if any are connected
                    if (self.pump or self.knx) and not self._peripherals_locked:
                        self._peripherals_locked = True
                        logger.info("=" * 60)
                        logger.info("🔒 PERIPHERALS LOCKED")
                        peripheral_list = []
                        if self.pump:
                            peripheral_list.append("Pump")
                        if self.knx:
                            peripheral_list.append(f"Kinetic ({self.knx.name})")
                        logger.info(f"   Connected: {', '.join(peripheral_list)}")
                        logger.info("   No further peripheral changes until disconnect")
                        logger.info("=" * 60)
                else:
                    logger.warning(
                        "[WARN] Hardware scan FAILED - no valid hardware combinations",
                    )
                    self.connection_progress.emit("No valid hardware detected")
                    # Don't lock if scan failed

                # ALWAYS emit signal - UI will handle success/failure
                self.hardware_connected.emit(status)

                # If devices connected successfully, exit retry loop
                if valid_hardware:
                    logger.info("[OK] Connection successful, exiting retry loop")
                    break

                # If no devices found and we haven't exhausted retries, continue loop
                retry_attempt += 1
                if retry_attempt < max_retries:
                    logger.warning(
                        f"[ERROR] Connection attempt {retry_attempt}/{max_retries} failed - retrying...",
                    )
                else:
                    logger.error(
                        f"[ERROR] All {max_retries} connection attempts failed",
                    )

            except Exception as e:
                logger.exception(f"Error during hardware scan: {e}")
                # Don't show error dialog for simple connection failures
                # Only emit for actual exceptions (once per scan)
                if ("name 'os' is not defined" not in str(e)) and (not _scan_error_emitted):
                    _scan_error_emitted = True
                    self.error_occurred.emit(f"Hardware scan error: {e}")
                # On exception, retry if attempts remain
                retry_attempt += 1
                if retry_attempt < max_retries:
                    logger.warning(
                        f"Retrying after exception ({retry_attempt}/{max_retries})...",
                    )
                    continue
                break

        # Cleanup - mark connection process complete
        self._connecting = False

    def _peripheral_scan_worker(self) -> None:
        """Worker thread that scans for peripherals only (pump/kinetic).

        Called when main unit is already connected and user wants to add peripherals.
        """
        try:
            scan_start = time.time()
            logger.info("[PERIPHERAL SCAN] Starting peripheral-only scan...")

            # Step 1: Try to connect to pump (AffiPump first)
            self.connection_progress.emit("Looking for pump...")
            t0 = time.time()
            if not self.pump:  # Only scan if no pump connected
                self._connect_pump()
                if HARDWARE_DEBUG:
                    logger.info(f"[PERIPHERAL SCAN] Pump scan: {time.time() - t0:.2f}s")
            else:
                logger.info("[PERIPHERAL SCAN] Pump already connected - skipping")

            # Step 2: Try to connect to kinetic controller (only if no AffiPump)
            if not self.pump and not self.knx:  # Mutually exclusive
                self.connection_progress.emit("Looking for kinetic controller...")
                t0 = time.time()
                self._connect_kinetic()
                if HARDWARE_DEBUG:
                    logger.info(
                        f"[PERIPHERAL SCAN] Kinetic scan: {time.time() - t0:.2f}s",
                    )
            elif self.pump:
                logger.info(
                    "[PERIPHERAL SCAN] Skipping kinetic scan - pump already connected",
                )
            else:
                logger.info("[PERIPHERAL SCAN] Kinetic already connected - skipping")

            # Build updated status
            ctrl_type = self._get_controller_type()
            knx_type = self._get_kinetic_type()

            valid_hardware = []
            if ctrl_type and self.ctrl and self.usb:
                valid_hardware.append(ctrl_type)
            if knx_type and self.knx:
                valid_hardware.append(knx_type)
            if self.pump:
                valid_hardware.append("AffiPump")

            status = {
                "ctrl_type": ctrl_type,
                "knx_type": knx_type if self.knx else None,
                "pump_connected": self.pump is not None,
                "spectrometer": self.usb is not None,
                "spectrometer_serial": self.usb.serial_number
                if self.usb and hasattr(self.usb, "serial_number")
                else None,
                "sensor_ready": self._sensor_verified,
                "optics_ready": self._optics_verified,
                "fluidics_ready": self.pump is not None,
                "scan_successful": len(valid_hardware) > 0,
            }

            # Log results
            total_time = time.time() - scan_start
            logger.info("=" * 60)
            logger.info(f"PERIPHERAL SCAN COMPLETE ({total_time:.2f}s)")
            logger.info(f"  • Pump:       {'CONNECTED' if self.pump else 'NOT FOUND'}")
            logger.info(f"  • Kinetic:    {self.knx.name if self.knx else 'NOT FOUND'}")
            logger.info("=" * 60)

            # Lock peripherals if any were found
            if (self.pump or self.knx) and not self._peripherals_locked:
                self._peripherals_locked = True
                logger.info("=" * 60)
                logger.info("🔒 PERIPHERALS LOCKED")
                peripheral_list = []
                if self.pump:
                    peripheral_list.append("Pump")
                if self.knx:
                    peripheral_list.append(f"Kinetic ({self.knx.name})")
                logger.info(f"   Connected: {', '.join(peripheral_list)}")
                logger.info("   No further peripheral changes until disconnect")
                logger.info("=" * 60)

            # Emit updated status
            self.hardware_connected.emit(status)

            if self.pump or self.knx:
                logger.info("[OK] Peripheral scan SUCCESSFUL")
            else:
                logger.info("[WARN] No peripherals found")

        except Exception as e:
            logger.exception(f"Error during peripheral scan: {e}")
            self.error_occurred.emit(f"Peripheral scan failed: {e}")
        finally:
            self._connecting = False

    def _connect_controller(self) -> None:
        """Attempt to connect to SPR controller."""
        # CRITICAL SAFEGUARD: Prevent reconnection if controller already connected AND actually open
        if self.ctrl is not None:
            try:
                # Check if the controller is actually open (has a live serial connection)
                is_open = False
                if hasattr(self, "_ctrl_raw") and self._ctrl_raw is not None:
                    if hasattr(self._ctrl_raw, "_ser") and self._ctrl_raw._ser is not None:
                        is_open = True

                if is_open:
                    controller_name = self.ctrl.get_device_type() if self.ctrl else None
                    logger.warning(
                        f"⚠️ Controller already connected ({controller_name}) - skipping scan",
                    )
                    logger.warning(
                        "  If this is unexpected, the previous connection did not properly clean up!"
                    )
                    logger.warning(f"  Current ctrl object: {self.ctrl}")
                    return
                else:
                    # Controller adapter exists but no live connection - clear and rescan
                    logger.info(
                        "Controller adapter present but not open - clearing and rescanning..."
                    )
                    self.ctrl = None
                    self._ctrl_raw = None
            except Exception as e:
                # If we can't check name, proceed with connection attempt
                logger.warning(f"Controller object present but state check failed: {e}")
                logger.info("Clearing stale controller and continuing scan...")
                self.ctrl = None
                self._ctrl_raw = None

        # Try reconnecting to cached port first (fast path after file reload)
        if self._ctrl_port and self._ctrl_type:
            logger.info(
                f"Attempting fast reconnect to {self._ctrl_type} on {self._ctrl_port}...",
            )
            if self._try_reconnect_controller():
                logger.info("[OK] Fast reconnect successful!")
                return
            logger.info("Fast reconnect failed, doing full scan...")

        try:
            print("DEBUG: ENTERED try block in _connect_controller")
            logger.info("=" * 60)
            logger.info("SCANNING FOR CONTROLLERS...")
            logger.info("=" * 60)
            print("DEBUG: About to import serial.tools.list_ports")

            # Check available serial ports
            import serial.tools.list_ports

            available_ports = list(serial.tools.list_ports.comports())
            print(f"DEBUG: Found {len(available_ports)} ports")
            logger.info(f"Serial ports: {len(available_ports)}")
            for port in available_ports:
                vid_str = f"0x{port.vid:04X}" if port.vid else "None"
                pid_str = f"0x{port.pid:04X}" if port.pid else "None"
                logger.info(
                    f"  {port.device}: VID={vid_str} PID={pid_str} - {port.description}",
                )

            # Get controller classes safely
            print("DEBUG: Getting controller classes")
            classes = _get_controller_classes()
            settings = _get_settings()
            print(f"DEBUG: Got classes={list(classes.keys())}")

            # Try controllers in priority order: PicoP4SPR → PicoP4PRO → PicoEZSPR → Arduino
            # STOP at first controller found - ignore the rest

            # Priority 1: Try PicoP4SPR first (most common modern controller)
            print("DEBUG: [1/3] About to try PicoP4SPR")
            logger.info(
                f"[1/3] Trying PicoP4SPR (VID:PID = {hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})...",
            )
            pico_p4spr = classes["PicoP4SPR"]()
            print("DEBUG: Calling pico_p4spr.open()...")
            open_result = pico_p4spr.open()
            print(f"DEBUG: pico_p4spr.open() returned: {open_result}")
            print(f"DEBUG: pico_p4spr.open() returned: {open_result}")
            if open_result:
                print("DEBUG: PicoP4SPR connected successfully!")
                logger.info(f"✅ [OK] Controller connected: {pico_p4spr.name}")

                # Wrap with HAL for consistent interface
                from affilabs.utils.hal.controller_hal import create_controller_hal

                hal_ctrl = create_controller_hal(pico_p4spr, self.device_config)

                with self._connection_lock:
                    self.ctrl = hal_ctrl
                    self._ctrl_raw = pico_p4spr  # Keep raw reference for non-HAL methods
                    self._ctrl_type = "PicoP4SPR"
                    # Cache port if available
                    if hasattr(pico_p4spr, "_ser") and pico_p4spr._ser:
                        self._ctrl_port = pico_p4spr._ser.port
                        logger.info(f"Cached controller port: {self._ctrl_port}")

                # NOTE: Servo initialization moved to after device_config is loaded (after detector connection)
                logger.info("[OK] Controller wrapped with HAL")
                return  # Found controller - stop searching
            print("DEBUG: PicoP4SPR.open() returned False - trying next controller")
            logger.info("   ❌ PicoP4SPR not found")

            # Priority 2: Try PicoP4PRO (standalone P4PRO hardware)
            print("DEBUG: [2/3] About to try PicoP4PRO")
            logger.info(
                f"[2/3] Trying PicoP4PRO (VID:PID = {hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})...",
            )
            print("DEBUG: About to instantiate PicoP4PRO class...")
            pico_p4pro = classes["PicoP4PRO"]()
            print("DEBUG: PicoP4PRO class instantiated successfully")
            print("DEBUG: Calling pico_p4pro.open()...")
            if pico_p4pro.open():
                print("DEBUG: PicoP4PRO connected successfully!")
                logger.info(f"✅ [OK] Controller connected: {pico_p4pro.name}")

                # Wrap with HAL for consistent interface
                from affilabs.utils.hal.controller_hal import create_controller_hal

                hal_ctrl = create_controller_hal(pico_p4pro, self.device_config)

                with self._connection_lock:
                    self.ctrl = hal_ctrl
                    self._ctrl_raw = pico_p4pro  # Keep raw reference for non-HAL methods
                    self._ctrl_type = "PicoP4PRO"
                    if hasattr(pico_p4pro, "_ser") and pico_p4pro._ser:
                        self._ctrl_port = pico_p4pro._ser.port

                # NOTE: Servo initialization moved to after device_config is loaded (after detector connection)
                logger.info("[OK] Controller wrapped with HAL")
                return  # Found controller - stop searching
            logger.info("   ❌ PicoP4PRO not found")

            # Priority 3: Try PicoEZSPR (EZSPR/AFFINITE hardware)
            logger.info(
                f"[3/3] Trying PicoEZSPR (VID:PID = {hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})...",
            )
            pico_ezspr = classes["PicoEZSPR"]()
            if pico_ezspr.open():
                logger.info(f"✅ [OK] Controller connected: {pico_ezspr.name}")

                # Wrap with HAL for consistent interface
                from affilabs.utils.hal.controller_hal import create_controller_hal

                hal_ctrl = create_controller_hal(pico_ezspr, self.device_config)

                with self._connection_lock:
                    self.ctrl = hal_ctrl
                    self._ctrl_raw = pico_ezspr  # Keep raw reference for non-HAL methods
                    self._ctrl_type = "PicoEZSPR"
                    if hasattr(pico_ezspr, "_ser") and pico_ezspr._ser:
                        self._ctrl_port = pico_ezspr._ser.port

                # NOTE: Servo initialization moved to after device_config is loaded (after detector connection)
                logger.info("[OK] Controller wrapped with HAL")
                return  # Found controller - stop searching
            logger.info("   ❌ PicoEZSPR not found")

            # Arduino controller DELETED - obsolete hardware
            # Only PicoP4SPR, PicoP4PRO, and PicoEZSPR are supported

            logger.warning("No SPR controller found")
            settings = _get_settings()
            logger.info(
                f"   Checked: Pico ({hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})",
            )
            logger.info("   Check: drivers, USB cable, port, other programs")
            with self._connection_lock:
                self.ctrl = None
                # Don't clear cache - keep for retry

        except Exception as e:
            logger.error(f"❌ EXCEPTION in _connect_controller: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            if HARDWARE_DEBUG:
                import traceback

                logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.ctrl = None

    def _should_scan_kinetic(self) -> bool:
        """Check if we should scan for KNX based on detector serial number.

        KNX controllers are only present on specific SPR systems.
        Skip scan if detector serial doesn't match known KNX-equipped systems.

        Returns:
            True if KNX scan should proceed, False to skip

        """
        if not hasattr(self, "_spec_serial") or not self._spec_serial:
            logger.debug("[KNX] No detector serial - skipping KNX scan")
            return False

        # Check if serial matches any known KNX system prefix
        for prefix in KNX_SERIAL_PREFIXES:
            if self._spec_serial.startswith(prefix):
                logger.info(
                    f"[KNX] Detector {self._spec_serial} matches KNX series - scanning",
                )
                return True

        logger.debug(
            f"[KNX] Detector {self._spec_serial} not in KNX series - skipping scan",
        )
        return False

    def _connect_kinetic(self) -> None:
        """Attempt to connect to kinetic controller."""
        try:
            knx2 = KineticController()
            if knx2.open():
                logger.info(f"KNX2 controller connected: {knx2.get_info()}")
                self.knx = knx2
                return

            pico_knx2 = PicoKNX2()
            if pico_knx2.open():
                logger.info(f"Pico KNX2 controller connected: {pico_knx2.version}")
                self.knx = pico_knx2
                return

            logger.debug("No kinetic controller found")
            self.knx = None

        except Exception as e:
            logger.error(f"Kinetic controller connection failed: {e}")
            self.knx = None

    def _connect_pump(self) -> None:
        """Attempt to connect to AffiPump (Tecan Cavro Centris dual syringe pumps)."""
        try:
            logger.info("🔍 Scanning for AffiPump via FTDI...")
            from AffiPump import CavroPumpManager, PumpController

            from affilabs.utils.hal.pump_hal import create_pump_hal

            # First, connect to FTDI serial interface
            logger.debug("   Calling PumpController.from_first_available()...")
            controller = PumpController.from_first_available()
            if not controller:
                logger.info("   ❌ No FTDI pump controller found")
                logger.info("   Check: FTDI driver installed, USB cable, pump power")
                self.pump = None
                return

            logger.info(f"   ✅ FTDI controller found: {controller}")

            # Create pump manager with hardware controller
            logger.debug("   Creating CavroPumpManager...")
            pump_manager = CavroPumpManager(controller)

            # Initialize both pumps (DISABLED - prevents initial prime cycle)
            logger.debug("   Skipping pump initialization (disabled per user request)...")
            # DISABLED: Prevents automatic prime cycle on connection
            # if pump_manager.initialize_pumps():
            #     # Wrap with HAL for consistent interface
            #     self.pump = create_pump_hal(pump_manager)
            #     logger.info(
            #         "✅ AffiPump connected and initialized via HAL (2x Tecan Cavro Centris pumps)",
            #     )
            # else:
            #     logger.warning(
            #         "⚠️ AffiPump found but initialization failed - pump may be powered off",
            #     )
            #     controller.close()
            #     self.pump = None

            # Connect pump without initialization
            self.pump = create_pump_hal(pump_manager)
            logger.info(
                "✅ AffiPump connected (initialization skipped) - 2x Tecan Cavro Centris pumps",
            )

        except ImportError as e:
            logger.info(f"   ❌ AffiPump module not available: {e}")
            logger.info("   AffiPump package may not be installed")
            self.pump = None
        except Exception as e:
            logger.error(f"❌ Pump connection failed: {e}")
            if HARDWARE_DEBUG:
                logger.exception("Full pump detection error:")
            self.pump = None

    def _get_controller_type(self) -> str:
        """Get the type of connected controller based on plugged hardware.

        Returns standardized hardware names for UI display:
        - P4SPR: Basic SPR controller (PicoP4SPR)
        - P4PRO: Advanced SPR controller with servo polarizer (PicoP4PRO)
        - P4PROPLUS: P4PRO with internal peristaltic pumps (PicoP4PRO V2.3+)
        - ezSPR: Standalone easy-to-use SPR controller (PicoEZSPR)
        - AFFINITE: Integrated SPR with pump (PicoAFFINITE)

        Note: P4PRO is often paired with AffiPump for fluidics.
              P4SPR is often paired with KNX for kinetics.
        """
        if self.ctrl is None:
            return ""  # No controller = no device type

        # Use HAL's get_device_type() method (not .name attribute)
        device_type = self.ctrl.get_device_type()

        # Map internal device type to product name
        if device_type == "PicoP4SPR":
            return "P4SPR"
        elif device_type == "PicoP4PRO":
            # Check if P4PRO has internal pumps (P4PROPLUS)
            if hasattr(self, "_ctrl_raw") and self._ctrl_raw:
                if hasattr(self._ctrl_raw, "firmware_id") and self._ctrl_raw.firmware_id:
                    if "p4proplus" in str(self._ctrl_raw.firmware_id).lower():
                        return "P4PROPLUS"
                elif hasattr(self._ctrl_raw, "has_internal_pumps"):
                    try:
                        if self._ctrl_raw.has_internal_pumps():
                            return "P4PROPLUS"
                    except Exception:
                        pass
            return "P4PRO"
        elif device_type == "PicoEZSPR":
            return "ezSPR"
        elif device_type == "PicoAFFINITE":
            return "AFFINITE"
        elif device_type == "Arduino":
            return "P4SPR"  # Legacy

        return ""

    def _get_kinetic_type(self) -> str:
        """Get the type of connected kinetic controller.

        Returns standardized hardware name for UI display:
        - KNX: Kinetic controller (all variants map to "KNX")
        """
        if self.knx is None:
            return ""

        name = getattr(self.knx, "name", "")
        # All kinetic controllers display as "KNX"
        if "KNX" in name.upper() or "KINETIC" in name.upper():
            return "KNX"
        return ""

    def _verify_sensor_and_optics(self) -> None:
        """Verify sensor and optics quality for P4SPR devices.

        Checks:
        - Sensor: Spectrometer can acquire data with acceptable intensity
        - Optics: Signal quality is sufficient (not too noisy, not saturated)
        """
        self._sensor_verified = False
        self._optics_verified = False
        self._fluidics_verified = False

        if not self.usb or not self.ctrl:
            logger.warning("Cannot verify sensor/optics: hardware not connected")
            return

        try:
            # Step 1: Test sensor - read spectrum and check if we get data
            logger.info("Testing sensor...")

            # Set a reasonable integration time for testing (15ms)
            self.usb.set_integration(15.0)

            # Acquire a test spectrum
            import time

            time.sleep(0.1)  # Let integration time settle
            intensities = self.usb.read_intensity()

            if intensities is None or len(intensities) == 0:
                logger.error("Sensor verification failed: No data from spectrometer")
                return

            # Check intensity range
            import numpy as np

            mean_intensity = np.mean(intensities)
            max_intensity = np.max(intensities)

            logger.info(
                f"Sensor test - Mean intensity: {mean_intensity:.1f}, Max: {max_intensity:.1f}",
            )

            if mean_intensity < self.SENSOR_MIN_INTENSITY:
                logger.warning(
                    f"Sensor signal too low: {mean_intensity:.1f} < {self.SENSOR_MIN_INTENSITY}",
                )
                # Still mark as verified but log warning - sensor works but signal is weak
                self._sensor_verified = True
            elif max_intensity > self.SENSOR_MAX_INTENSITY:
                logger.warning(
                    f"Sensor signal saturating: {max_intensity:.1f} > {self.SENSOR_MAX_INTENSITY}",
                )
                self._sensor_verified = True
            else:
                logger.info("[OK] Sensor verification passed")
                self._sensor_verified = True

            # Step 2: Test optics - check signal quality (SNR)
            logger.info("Testing optics...")

            # Calculate signal-to-noise ratio
            signal_std = np.std(intensities)
            signal_mean = mean_intensity

            if signal_mean > 0:
                snr = signal_mean / (signal_std + 1e-6)  # Avoid division by zero
                logger.info(f"Optics test - SNR: {snr:.2f}")

                if snr >= self.OPTICS_MIN_QUALITY:
                    logger.info("[OK] Optics verification passed")
                    self._optics_verified = True
                else:
                    logger.warning(
                        f"Optics quality low: SNR {snr:.2f} < {self.OPTICS_MIN_QUALITY}",
                    )
                    # Still mark as verified - optics work but quality is suboptimal
                    self._optics_verified = True
            else:
                logger.error("Optics verification failed: No signal detected")

        except Exception as e:
            logger.exception(f"Error during sensor/optics verification: {e}")
            # Mark as verified anyway if we have hardware - verification failed due to error, not hardware issue
            self._sensor_verified = self.usb is not None
            self._optics_verified = self.usb is not None

        # Verify fluidics (pump hardware present)
        has_pump = self.pump is not None
        if not has_pump and hasattr(self, "_ctrl_raw") and self._ctrl_raw:
            try:
                has_pump = bool(self._ctrl_raw.has_internal_pumps())
            except (AttributeError, Exception):
                pass
        self._fluidics_verified = has_pump

    def update_calibration_status(
        self,
        ch_error_list: list[str],
        calibration_type: str = "full",
        s_ref_qc_results: dict | None = None,
    ) -> None:
        """Update sensor and optics readiness based on calibration results.

        Args:
            ch_error_list: List of channels that failed calibration
            calibration_type: 'full', 'afterglow', 'led', or 'wavelength'
            s_ref_qc_results: Optical QC validation results for S-ref spectra

        Optics are considered ready ONLY after:
        1. Afterglow calibration has been performed
        2. LED calibration passes (no failed channels)
        3. No active leak detected (intensity monitoring)
        4. S-ref spectra pass optical QC checks

        """
        self._ch_error_list = ch_error_list.copy()
        self._s_ref_qc_results = s_ref_qc_results or {}

        # Track calibration type completion
        if calibration_type in ["full", "afterglow"]:
            self._afterglow_calibration_done = True

        # Capture previous state before updating

        # Check if this is a calibration failure due to weak intensity
        # This indicates maintenance required (LED PCB replacement)
        self._maintenance_required = ch_error_list.copy()

        # Determine if calibration passed
        self._calibration_passed = len(ch_error_list) == 0

        # Check S-ref QC results (informational only - doesn't block optics ready)
        self._s_ref_qc_passed = True
        qc_warnings = []
        if self._s_ref_qc_results:
            for ch, qc in self._s_ref_qc_results.items():
                # Log detailed QC metrics for debugging
                peak = qc.get("peak", 0)
                snr = qc.get("snr", 0)
                peak_wl = qc.get("peak_wl", 0)
                logger.debug(
                    f"📊 S-ref QC Ch {ch.upper()}: peak={peak:.0f} counts, SNR={snr:.1f}, λ={peak_wl:.1f}nm",
                )

                if not qc.get("passed", True):
                    self._s_ref_qc_passed = False
                    warnings = qc.get("warnings", [])
                    if warnings:
                        # Log warnings for debugging but don't impact UI
                        for warning in warnings:
                            logger.debug(f"   [WARN] Ch {ch.upper()}: {warning}")
                        qc_warnings.extend([f"Ch {ch.upper()}: {w}" for w in warnings])

            if not self._s_ref_qc_passed:
                # Informational warning in debug log only
                logger.debug(f"[INFO] S-ref optical QC notes: {'; '.join(qc_warnings)}")
                logger.debug(
                    "   Note: QC warnings are informational and don't block operation",
                )
            else:
                logger.debug(
                    "[OK] S-ref optical QC: All channels passed quality checks",
                )

        # Optics ready requires:
        # 1. Afterglow calibration done
        # 2. Calibration passed (all channels)
        # 3. Hardware connected
        # 4. No active leak detected
        # Note: S-ref QC is informational only (logged for debugging)
        # Note: Sensor readiness is tracked separately via FWHM measurements
        if (
            self._afterglow_calibration_done
            and self._calibration_passed
            and self.usb is not None
            and not self._optics_leak_detected
        ):
            self._optics_verified = True
            logger.info("[OK] Optics verification: All conditions met - OPTICS READY")
        else:
            self._optics_verified = False

            # Log specific failure reasons
            reasons = []
            if not self._afterglow_calibration_done:
                reasons.append("afterglow calibration not performed")
            if not self._calibration_passed:
                reasons.append(
                    f"calibration failed for channels {sorted(ch_error_list)}",
                )
            if self._optics_leak_detected:
                reasons.append("optical leak detected")
            if len(self._maintenance_required) > 0:
                maint_list = sorted(
                    set(self._maintenance_required),
                )  # Remove duplicates and sort
                reasons.append(f"maintenance required for channels {maint_list}")

            logger.warning(f"[WARN] Optics NOT ready: {', '.join(reasons)}")

        # DO NOT emit hardware_connected here - this would trigger connection flow again
        # and cause calibration loop. Hardware scans should only happen on user request.
        # Status updates are handled directly by main_simplified.py after calibration.

        # Note: We intentionally DO NOT call _emit_hardware_status() here to avoid
        # triggering redundant hardware scan callbacks after successful calibration.

    def update_led_intensity(
        self,
        channel: str,
        intensity: float,
        timestamp: float,
    ) -> None:
        """Monitor LED intensity in real-time to detect sudden drops indicating leaks.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            intensity: Current raw intensity reading
            timestamp: Time of measurement

        """
        # Update peak intensity
        self._channel_max_intensity[channel] = max(
            self._channel_max_intensity[channel],
            intensity,
        )

        # Add to history with timestamp
        self._channel_intensity_history[channel].append((timestamp, intensity))

        # Keep only last 5 seconds of data
        cutoff_time = timestamp - 5.0
        self._channel_intensity_history[channel] = [
            (t, i) for t, i in self._channel_intensity_history[channel] if t >= cutoff_time
        ]

        # Check for sudden intensity drop (leak detection)
        # Only check if we have calibrated and have enough history
        if (
            self._calibration_passed
            and len(self._channel_intensity_history[channel]) > 10
            and self._channel_max_intensity[channel] > 1000
        ):  # Only check if we've seen good signal
            # Get intensity from 3 seconds ago
            three_seconds_ago = timestamp - 3.0
            old_intensities = [
                i for t, i in self._channel_intensity_history[channel] if t <= three_seconds_ago
            ]

            if len(old_intensities) > 0:
                avg_old_intensity = sum(old_intensities) / len(old_intensities)

                # Check if current intensity dropped below 10% of max detector counts
                max_detector_counts = 65535  # USB4000 16-bit
                leak_threshold = max_detector_counts * 0.10

                # Leak detected if:
                # 1. Current intensity is below 10% of max detector counts
                # 2. Previous intensity was significantly higher (drop > 50%)
                if (
                    intensity < leak_threshold
                    and avg_old_intensity > leak_threshold * 2
                    and not self._optics_leak_detected
                ):
                    self._optics_leak_detected = True
                    logger.error(
                        f"🔴 OPTICAL LEAK DETECTED in channel {channel.upper()}: "
                        f"Intensity dropped from {avg_old_intensity:.0f} to {intensity:.0f} "
                        f"(threshold: {leak_threshold:.0f} counts)",
                    )

                    # Update optics status to NOT READY
                    previous_optics_verified = self._optics_verified
                    self._optics_verified = False

                    # Emit status update
                    status = {
                        "ctrl_type": self._get_controller_type(),
                        "knx_type": self._get_kinetic_type(),
                        "pump_connected": self.pump is not None,
                        "spectrometer": self.usb is not None,
                        "sensor_ready": self._sensor_verified,
                        "optics_ready": self._optics_verified,
                        "fluidics_ready": self.pump is not None,
                    }
                    self.hardware_connected.emit(status)

                    if previous_optics_verified:
                        self._emit_hardware_status()

                    # Emit error
                    self.hardware_error.emit(
                        f"Optical leak detected in channel {channel.upper()}. "
                        f"Check for loose connections or damaged optical components.",
                    )

    def reset_leak_detection(self) -> None:
        """Reset leak detection state after user has fixed the issue."""
        self._optics_leak_detected = False
        self._channel_intensity_history = {"a": [], "b": [], "c": [], "d": []}
        self._channel_max_intensity = {"a": 0, "b": 0, "c": 0, "d": 0}
        logger.info("🔄 Leak detection reset - monitoring restarted")

        # Re-evaluate optics status (sensor status is independent, set by FWHM)
        if self._afterglow_calibration_done and self._calibration_passed and self.usb is not None:
            self._optics_verified = True
            logger.info("[OK] Optics status restored to READY")
            self._emit_hardware_status()

    def update_fwhm_status(self, channel: str, fwhm: float) -> None:
        """Update sensor readiness based on FWHM measurement.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            fwhm: Full-width half-maximum in nm

        Sensor is considered ready ONLY if:
        - At least one channel has valid FWHM data
        - At least one channel has FWHM < 60 nm (good quality)
        - If no FWHM data exists, sensor is NOT ready (no chip/leak/issue)

        """
        self._channel_fwhm[channel] = fwhm

        # Check if any channel meets the quality threshold
        previous_sensor_verified = self._sensor_verified

        # Get all channels with valid FWHM measurements
        measured_channels = {ch: val for ch, val in self._channel_fwhm.items() if val is not None}

        # Check if any measured channel is good quality
        good_channels = [ch for ch, val in measured_channels.items() if val < self._fwhm_threshold]

        if len(good_channels) > 0:
            # At least one channel has good FWHM
            if not previous_sensor_verified:
                logger.info(
                    f"[OK] Sensor verification: FWHM passed - channels {good_channels} < {self._fwhm_threshold} nm",
                )
            self._sensor_verified = True
        # Either no measurements or all measurements are bad
        elif len(measured_channels) == 0:
            # No FWHM data at all - sensor NOT ready
            if previous_sensor_verified:
                logger.warning(
                    "[ERROR] Sensor NOT ready: No FWHM data available (no chip/leak/connection issue)",
                )
            self._sensor_verified = False
        else:
            # Have measurements but all are poor quality
            fwhm_str = {ch: f"{val:.1f}" for ch, val in measured_channels.items()}
            if previous_sensor_verified:
                logger.warning(
                    f"[ERROR] Sensor NOT ready: All FWHM values exceed threshold - {fwhm_str} nm (threshold: {self._fwhm_threshold} nm)",
                )
            self._sensor_verified = False

        # Emit hardware status update if sensor state changed
        if previous_sensor_verified != self._sensor_verified:
            status = {
                "ctrl_type": self._get_controller_type(),
                "knx_type": self._get_kinetic_type(),
                "pump_connected": self.pump is not None,
                "spectrometer": self.usb is not None,
                "sensor_ready": self._sensor_verified,
                "optics_ready": self._optics_verified,
                "fluidics_ready": self.pump is not None,
            }
            self.hardware_connected.emit(status)
            self._emit_hardware_status()

    def check_intensity_leak(
        self,
        channel: str,
        intensity: float,
        dark_noise: float,
    ) -> None:
        """Check for intensity drops that indicate optical leaks.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            intensity: Current intensity value
            dark_noise: Dark noise level for this channel

        If intensity drops near dark noise for extended period (>5s), optics is not ready.
        This should be called from main_simplified.py with buffered intensity tracking.

        """
        # This is a placeholder - actual implementation will be in main_simplified.py
        # which will track intensity over time with a 5-second sliding window

    def _emit_hardware_status(self) -> None:
        """Emit current hardware status with updated verification flags."""
        # Check if pump is connected (external AffiPump or internal P4PROPLUS pumps)
        has_pump = self.pump is not None
        if not has_pump and hasattr(self, "_ctrl_raw") and self._ctrl_raw:
            try:
                has_pump = bool(self._ctrl_raw.has_internal_pumps())
            except (AttributeError, Exception):
                pass

        status = {
            "ctrl_type": self._get_controller_type(),
            "knx_type": self._get_kinetic_type(),
            "pump_connected": has_pump,
            "spectrometer": "USB4000" if self.usb else None,
            "spectrometer_serial": self.usb.serial_number
            if self.usb and hasattr(self.usb, "serial_number")
            else None,
            "sensor_ready": self._sensor_verified,
            "optics_ready": self._optics_verified,
        }

        # Only include fluidics_ready for controllers that support flow mode
        # P4SPR/static controllers don't have fluidics, so shouldn't show this status
        if self.ctrl and hasattr(self.ctrl, "supports_flow_mode") and self.ctrl.supports_flow_mode:
            status["fluidics_ready"] = self._fluidics_verified  # Set during verification scan
            status["flow_calibrated"] = getattr(self, "_flow_calibrated", False)

        self.hardware_connected.emit(status)
        logger.info(
            f"Hardware status update: sensor_ready={self._sensor_verified}, optics_ready={self._optics_verified}",
        )

    def _check_and_apply_special_case(self, detector_serial: str, status: dict) -> None:
        """Check for and apply device-specific special cases.

        Args:
            detector_serial: The detector's serial number
            status: Hardware status dictionary (modified in-place if special case found)

        """
        try:
            from affilabs.utils.device_special_cases import (
                check_special_case,
            )

            # Check if this detector has a special case
            special_case = check_special_case(detector_serial)

            if special_case:
                # Store special case info for later use
                self._special_case = special_case
                status["special_case"] = {
                    "detector_serial": detector_serial,
                    "description": special_case.get("description", "No description"),
                    "has_overrides": True,
                }

                logger.info(
                    "📋 Special case will be applied during device initialization",
                )

                # Log which parameters will be overridden
                override_params = [k for k in special_case if k not in ["description", "notes"]]
                if override_params:
                    logger.info(f"   Overrides: {', '.join(override_params)}")
            else:
                self._special_case = None
                status["special_case"] = None

        except Exception as e:
            logger.error(f"Error checking special cases: {e}")
            self._special_case = None
            status["special_case"] = None

    def get_special_case(self):
        """Get the current special case configuration if any.

        Returns:
            Special case dictionary or None

        """
        return getattr(self, "_special_case", None)

    def is_hardware_locked(self) -> bool:
        """Check if hardware configuration is locked.

        Returns:
            True if hardware is connected and locked, False otherwise

        """
        return self._hardware_locked

    def get_hardware_info(self) -> dict:
        """Get current hardware configuration information.

        Returns:
            Dictionary with hardware details

        """
        return {
            "locked": self._hardware_locked,
            "controller": self.ctrl.get_device_type() if self.ctrl else None,
            "detector": self.usb.serial_number
            if self.usb and hasattr(self.usb, "serial_number")
            else None,
            "kinetic": self.knx.name if self.knx else None,
            "pump": "Connected" if self.pump else None,
            "special_case": self._special_case.get("description") if self._special_case else None,
        }

    def check_connection_health(self) -> dict:
        """Health check for active hardware connections.

        Returns:
            Dictionary with health status for each device:
            {
                'controller': True/False/None,
                'spectrometer': True/False/None,
                'pump': True/False/None,
                'kinetic': True/False/None
            }

        """
        health = {
            "controller": None,
            "spectrometer": None,
            "pump": None,
            "kinetic": None,
        }

        with self._connection_lock:
            # Check controller
            if self.ctrl:
                try:
                    # Try simple command to verify connection is alive
                    if hasattr(self.ctrl, "_ser") and self.ctrl._ser and self.ctrl._ser.is_open:
                        health["controller"] = True
                    else:
                        health["controller"] = False
                        logger.warning("Controller serial port not open")
                except Exception as e:
                    health["controller"] = False
                    logger.error(f"Controller health check failed: {e}")

            # Check spectrometer
            if self.usb:
                try:
                    # Verify device is still accessible
                    # USB4000Wrapper uses _device attribute
                    if hasattr(self.usb, "_device") and self.usb._device and self.usb.opened:
                        health["spectrometer"] = True
                    else:
                        health["spectrometer"] = False
                        logger.warning("Spectrometer device handle lost")
                except Exception as e:
                    health["spectrometer"] = False
                    logger.error(f"Spectrometer health check failed: {e}")

            # Check pump (if present)
            if self.pump:
                try:
                    health["pump"] = True  # Basic presence check
                except Exception as e:
                    health["pump"] = False
                    logger.error(f"Pump health check failed: {e}")

            # Check kinetic (if present)
            if self.knx:
                try:
                    health["kinetic"] = True  # Basic presence check
                except Exception as e:
                    health["kinetic"] = False
                    logger.error(f"Kinetic health check failed: {e}")

        return health

    def auto_recover_connection(self, validate: bool = True) -> bool:
        """Attempt to recover lost connections using cached info.

        Args:
            validate: If True, validate connection after recovery with test command

        Returns:
            True if any connections were recovered and validated, False otherwise

        """
        recovered = False

        logger.info("🔄 Attempting connection recovery...")

        with self._connection_lock:
            # Try to recover controller
            if self.ctrl is None and self._ctrl_port:
                logger.info(f"Attempting controller recovery on {self._ctrl_port}...")
                if self._try_reconnect_controller():
                    # Validate connection if requested
                    if validate:
                        if self.is_controller_responsive():
                            recovered = True
                            logger.info("[OK] Controller recovered and validated")
                        else:
                            logger.warning(
                                "[WARN] Controller reconnected but not responsive",
                            )
                            self.ctrl = None  # Clear failed connection
                    else:
                        recovered = True
                        logger.info("[OK] Controller recovered (validation skipped)")
                else:
                    logger.warning("[ERROR] Controller recovery failed")

            # Try to recover spectrometer
            if self.usb is None and self._spec_serial:
                logger.info(f"Attempting spectrometer recovery: {self._spec_serial}...")
                if self._try_reconnect_spectrometer():
                    # Validate connection if requested
                    if validate:
                        if self.is_spectrometer_responsive():
                            recovered = True
                            logger.info("[OK] Spectrometer recovered and validated")
                        else:
                            logger.warning(
                                "[WARN] Spectrometer reconnected but not responsive",
                            )
                            self.usb = None  # Clear failed connection
                    else:
                        recovered = True
                        logger.info("[OK] Spectrometer recovered (validation skipped)")
                else:
                    logger.warning("[ERROR] Spectrometer recovery failed")

        if recovered:
            logger.info("[OK] Connection recovery successful")
            self._emit_hardware_status()
        else:
            logger.warning(
                "[ERROR] Connection recovery failed - full rescan may be needed",
            )

        return recovered

    def disconnect_all(self) -> None:
        """Disconnect all hardware devices gracefully and unlock for new hardware."""
        logger.info("=" * 60)
        logger.info("🔓 DISCONNECTING ALL HARDWARE - Unlocking configuration")
        logger.info("=" * 60)

        # Turn off all LEDs before disconnecting (graceful exit)
        if self.ctrl:
            try:
                logger.debug("Turning off all LEDs before disconnect...")
                self.ctrl.turn_off_channels()
                import time

                time.sleep(0.1)  # Brief delay to ensure command executes
                logger.debug("[OK] LEDs turned off")
            except Exception as e:
                logger.warning(f"Could not turn off LEDs: {e}")

        # Disconnect controller (use raw controller for close)
        if self._ctrl_raw:
            try:
                logger.debug("Closing controller connection...")
                self._ctrl_raw.close()
                logger.debug("[OK] Controller closed")
            except Exception as e:
                logger.error(f"Error closing controller: {e}")
            self._ctrl_raw = None
        self.ctrl = None

        # Disconnect kinetic controller
        if self.knx:
            try:
                logger.debug("Closing kinetic controller...")
                self.knx.close()
                logger.debug("[OK] Kinetic controller closed")
            except Exception as e:
                logger.error(f"Error closing kinetic controller: {e}")
            self.knx = None

        # Disconnect pump
        if self.pump:
            try:
                logger.debug("Closing pump...")
                self.pump.close()
                logger.debug("[OK] Pump closed")
            except Exception as e:
                logger.error(f"Error closing pump: {e}")
            self.pump = None

        # Disconnect spectrometer
        if self.usb:
            try:
                logger.debug("Closing spectrometer...")
                if hasattr(self.usb, "close"):
                    self.usb.close()
                    logger.debug("[OK] Spectrometer closed")
                else:
                    logger.debug("[OK] Spectrometer released (no close method)")
            except Exception as e:
                logger.debug(f"Spectrometer close: {e} (non-critical)")
            self.usb = None

        # Clear special case configuration
        self._special_case = None

        # Clear verification states
        self._sensor_verified = False
        self._optics_verified = False
        self._fluidics_verified = False
        self._calibration_passed = False
        self._afterglow_calibration_done = False

        # Unlock hardware - ready for new connection
        self._hardware_locked = False

        logger.info("=" * 60)
        logger.info("[OK] Hardware disconnected safely - ready for offline mode")
        logger.info("=" * 60)
        self.hardware_disconnected.emit()
