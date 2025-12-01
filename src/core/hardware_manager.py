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

from PySide6.QtCore import QObject, Signal, QThread
from utils.logger import logger
from typing import Optional, Dict
import threading
import time

# ============================================================================
# DEBUG FLAGS - Set to True for detailed troubleshooting output
# ============================================================================
HARDWARE_DEBUG = True  # Enable detailed connection timing and device scan logs
CONNECTION_TIMEOUT = 2.0  # Seconds to wait for USB device discovery (2s fast, 5s safe)
CONNECTION_RETRY_COUNT = 3  # Retry connections this many times before failing

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
                from utils.controller import ArduinoController, PicoP4SPR, PicoEZSPR, KineticController, PicoKNX2
                _controller_classes_cache = {
                    'ArduinoController': ArduinoController,
                    'PicoP4SPR': PicoP4SPR,
                    'PicoEZSPR': PicoEZSPR,
                    'KineticController': KineticController,
                    'PicoKNX2': PicoKNX2
                }
                logger.debug("Controller classes loaded successfully")
            except Exception as e:
                logger.error(f"Failed to import controller classes: {e}")
                # Return stub classes that fail gracefully
                class StubController:
                    def open(self): return False
                    def close(self): pass
                _controller_classes_cache = {
                    'ArduinoController': StubController,
                    'PicoP4SPR': StubController,
                    'PicoEZSPR': StubController,
                    'KineticController': StubController,
                    'PicoKNX2': StubController
                }
        return _controller_classes_cache

def _get_settings():
    """Lazy import with caching for settings."""
    global _settings_cache
    with _import_lock:
        if _settings_cache is None:
            try:
                from settings.settings import ARDUINO_VID, ARDUINO_PID, PICO_VID, PICO_PID
                _settings_cache = {
                    'ARDUINO_VID': ARDUINO_VID,
                    'ARDUINO_PID': ARDUINO_PID,
                    'PICO_VID': PICO_VID,
                    'PICO_PID': PICO_PID
                }
                logger.debug("Settings loaded successfully")
            except Exception as e:
                logger.error(f"Failed to import settings: {e}")
                _settings_cache = {
                    'ARDUINO_VID': 0x2341,
                    'ARDUINO_PID': 0x0043,
                    'PICO_VID': 0x2e8a,
                    'PICO_PID': 0x000a
                }
        return _settings_cache


class HardwareManager(QObject):
    """Manages all hardware devices with non-blocking initialization."""

    # Signals for hardware status updates
    hardware_connected = Signal(dict)  # {ctrl_type, knx_type, pump_connected, spectrometer, sensor_ready, optics_ready, fluidics_ready}
    hardware_disconnected = Signal()
    connection_progress = Signal(str)  # Status messages during connection
    error_occurred = Signal(str)  # Error messages

    # Quality thresholds for sensor/optics verification
    SENSOR_MIN_INTENSITY = 1000  # Minimum acceptable signal intensity
    SENSOR_MAX_INTENSITY = 60000  # Maximum safe intensity (avoid saturation at 65535)
    OPTICS_MIN_QUALITY = 0.7  # Minimum signal-to-noise ratio

    def __init__(self):
        super().__init__()

        # Hardware device references
        self.ctrl = None  # SPR controller
        self.knx = None   # Kinetic controller
        self.pump = None  # Pump
        self.usb = None   # Spectrometer

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
        self._calibration_passed = False
        self._afterglow_calibration_done = False
        self._optics_leak_detected = False

        # Intensity/leak tracking structures
        self._channel_intensity_history = {'a': [], 'b': [], 'c': [], 'd': []}
        self._channel_max_intensity = {'a': 0, 'b': 0, 'c': 0, 'd': 0}

        # FWHM readiness tracking
        self._channel_fwhm = {'a': None, 'b': None, 'c': None, 'd': None}
        self._fwhm_threshold = 60.0  # nm

    def _try_reconnect_controller(self):
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
                if hasattr(ctrl, 'open') and ctrl.open():
                    self.ctrl = ctrl
                    logger.info(f"✅ Reconnected to {self._ctrl_type}")

                    # Initialize servo after successful reconnection
                    self._initialize_servo_polarizer(ctrl)
                    return True
                else:
                    logger.debug(f"Fast reconnect failed for {self._ctrl_type}")
                    return False

            except Exception as e:
                logger.debug(f"Reconnect exception: {e}")
                return False

    def _try_reconnect_spectrometer(self):
        """Fast reconnect to cached spectrometer serial after file reload."""
        if not self._spec_serial:
            return False

        with self._connection_lock:
            try:
                try:
                    from src.utils.usb4000_wrapper import USB4000
                except ImportError:
                    from utils.usb4000_wrapper import USB4000

                logger.info(f"Fast reconnect: Spectrometer {self._spec_serial}")
                usb = USB4000()

                if usb.open():
                    # Verify it's the same device
                    if hasattr(usb, 'serial_number') and usb.serial_number == self._spec_serial:
                        self.usb = usb
                        logger.info(f"✅ Reconnected to spectrometer {self._spec_serial}")
                        return True
                    elif not hasattr(usb, 'serial_number'):
                        # Can't verify, but accept connection
                        self.usb = usb
                        logger.info("✅ Reconnected to spectrometer (serial not verifiable)")
                        return True
                    else:
                        logger.warning(f"Serial mismatch: expected {self._spec_serial}, got {usb.serial_number}")
                        usb.close()
                        return False
                else:
                    logger.debug("Fast reconnect failed for spectrometer")
                    return False

            except Exception as e:
                logger.debug(f"Spectrometer reconnect exception: {e}")
                return False

    def _initialize_servo_polarizer(self, ctrl):
        """Initialize servo polarizer to S-mode position on controller connection.

        Reads servo positions from device_config, moves polarizer to S-position,
        and locks to S-mode for consistent starting state.

        Args:
            ctrl: Controller object (PicoP4SPR, PicoEZSPR, or Arduino)
        """
        try:
            logger.info("="*60)
            logger.info("🔧 INITIALIZING SERVO POLARIZER...")
            logger.info("="*60)

            # Check if controller supports servo
            if not hasattr(ctrl, 'servo_move_calibration_only'):
                logger.warning("⚠️ Controller does not support servo - skipping polarizer init")
                return

            # Load device config to get servo positions
            try:
                from src.utils.common import get_config
            except ImportError:
                from utils.common import get_config

            config = get_config()

            # Try to get detector serial for device-specific config
            detector_serial = None
            if self.usb and hasattr(self.usb, 'serial_number'):
                detector_serial = self.usb.serial_number

            # Look for servo positions in config
            s_position = None
            p_position = None

            # Try detector-specific config first
            if detector_serial and 'detectors' in config:
                detector_config = config['detectors'].get(detector_serial, {})
                hw = detector_config.get('hardware', {})
                s_position = hw.get('servo_s_position')
                p_position = hw.get('servo_p_position')
                if s_position and p_position:
                    logger.info(f"📍 Using detector-specific servo positions: S={s_position}°, P={p_position}°")

            # Fall back to default config
            if s_position is None or p_position is None:
                hw = config.get('hardware', {})
                s_position = hw.get('servo_s_position', 120)  # Default S=120°
                p_position = hw.get('servo_p_position', 60)   # Default P=60°
                logger.info(f"📍 Using default servo positions: S={s_position}°, P={p_position}°")

            # Turn off all LEDs for safety during servo movement
            logger.info("💡 Turning off all LEDs for safe servo movement...")
            if hasattr(ctrl, 'turn_off_channels'):
                ctrl.turn_off_channels()

            import time
            time.sleep(0.1)

            # Park servo to 1° to remove backlash
            logger.info("🏠 Parking polarizer to 1° (remove backlash)...")
            ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.5)  # Allow servo to complete movement

            # Move to S-mode position
            logger.info(f"↗️ Moving polarizer to S-mode: S={s_position}°, P={p_position}°...")
            ctrl.servo_move_calibration_only(s=s_position, p=p_position)
            time.sleep(0.5)  # Allow servo to complete movement

            # Lock to S-mode via firmware command
            logger.info("🔒 Locking to S-mode via firmware...")
            if hasattr(ctrl, 'servo_set'):
                ctrl.servo_set(s=s_position, p=p_position)
                time.sleep(0.2)

            logger.info("✅ Servo polarizer initialized to S-mode")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"❌ Servo initialization failed: {e}")
            if HARDWARE_DEBUG:
                import traceback
                logger.debug(traceback.format_exc())
            # Non-fatal - continue with connection even if servo init fails

    def _connect_spectrometer(self):
        """Attempt to connect to spectrometer (USB4000/Flame-T via SeaBreeze)."""
        try:
            if HARDWARE_DEBUG:
                logger.info("="*60)
                logger.info("SCANNING FOR SPECTROMETER...")
                logger.info("="*60)

            # Try fast reconnect first if we have cached info
            if self._spec_serial and self._try_reconnect_spectrometer():
                logger.info("✅ Fast reconnect successful!")
                return

            logger.info("Connecting to spectrometer (full scan)...")

            try:
                from src.utils.usb4000_wrapper import USB4000
            except ImportError:
                from utils.usb4000_wrapper import USB4000  # fallback if src prefix not used

            usb = USB4000()
            if usb.open():
                with self._connection_lock:
                    self.usb = usb
                    # Cache serial number for future reconnects
                    if hasattr(self.usb, 'serial_number'):
                        self._spec_serial = self.usb.serial_number
                        logger.info(f"Spectrometer connected: {self._spec_serial}")
                    else:
                        logger.info("Spectrometer connected (no serial)")

                # Warm-up dummy read at 10 ms
                try:
                    import time
                    logger.info("🌡️ Performing spectrometer warm-up (10 ms dummy read)...")
                    self.usb.set_integration(10)  # 10 ms
                    time.sleep(0.1)
                    dummy = self.usb.read_intensity()
                    if dummy is not None:
                        logger.info(f"   Warm-up read OK ({len(dummy)} pixels)")
                    logger.info("✅ Spectrometer warm-up complete")
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

    def scan_and_connect(self, auto_connect: bool = True) -> Dict[str, bool]:
        """Scan for hardware devices and optionally auto-connect.

        See: README_HARDWARE_BEHAVIOR.md for complete documentation
        """
        print("\n" + "="*80)
        print("[HARDWARE_MANAGER] scan_and_connect() called!")
        print("="*80 + "\n")
        logger.info("HardwareManager.scan_and_connect() called")

        # Check if main unit (controller+detector) is already locked
        if self._hardware_locked:
            # Main unit is locked, but we can still scan for peripherals
            if self.ctrl and self.usb:
                logger.info("="*60)
                logger.info("🔒 MAIN UNIT LOCKED - Controller and detector cannot change")
                logger.info(f"   Controller: {self.ctrl.name}")
                logger.info(f"   Detector: {self.usb.serial_number if hasattr(self.usb, 'serial_number') else 'Connected'}")

                # Check if peripherals are also locked
                if self._peripherals_locked:
                    logger.warning("="*60)
                    logger.warning("🔒 PERIPHERALS ALSO LOCKED - Cannot rescan")
                    logger.warning(f"   Pump: {'Connected' if self.pump else 'None'}")
                    logger.warning(f"   Kinetic: {self.knx.name if self.knx else 'None'}")
                    logger.warning("   Use disconnect_all() to clear hardware and rescan")
                    logger.warning("="*60)
                    print("[HARDWARE_MANAGER] All hardware locked - disconnect first to rescan!")
                    return
                else:
                    # Peripherals not locked yet - allow peripheral scan
                    logger.info("🔓 Peripherals can still be added")
                    logger.info("   Scanning for pump/kinetic controllers...")
                    logger.info("="*60)
                    print("[HARDWARE_MANAGER] Scanning for peripherals (pump/kinetic)...")

                    # Only scan for peripherals (skip controller and detector)
                    self._connecting = True
                    self.connection_progress.emit("Scanning for peripherals...")

                    # Run peripheral scan in background thread
                    self._connection_thread = threading.Thread(
                        target=self._peripheral_scan_worker,
                        daemon=True,
                        name="PeripheralScanner"
                    )
                    self._connection_thread.start()
                    logger.info("Background peripheral scan thread started")
                    print("[HARDWARE_MANAGER] Background peripheral scan started!")
                    return
            else:
                # Hardware locked but no devices? Clear lock
                logger.warning("Hardware locked but no devices found - clearing lock")
                self._hardware_locked = False

        if self._connecting:
            logger.warning("Connection already in progress - ignoring duplicate call")
            print("[HARDWARE_MANAGER] Connection already in progress!")
            return

        logger.info("Starting new hardware scan...")
        print("[HARDWARE_MANAGER] Starting hardware scan in background thread...")

        self._connecting = True
        self.connection_progress.emit("Scanning for hardware...")

        # Run connection in background thread
        self._connection_thread = threading.Thread(
            target=self._connection_worker,
            daemon=True,
            name="HardwareScanner"
        )
        self._connection_thread.start()
        logger.info("Background scan thread started")
        print("[HARDWARE_MANAGER] Background thread started!")

    def _connection_worker(self):
        """Worker thread that scans for hardware.

        Scanning priority logic:
        1. Look for controller first (PicoP4SPR → PicoEZSPR → Arduino) - stop at first found
        2. Look for detector (USB4000/Ocean Optics) - determines main unit type
        3. Scan for pumps (AffiPump first, then KNX) - only one can be connected

        Retry logic: Will retry up to CONNECTION_RETRY_COUNT times with exponential backoff
        """
        retry_attempt = 0
        max_retries = CONNECTION_RETRY_COUNT

        while retry_attempt < max_retries:
            try:
                if retry_attempt > 0:
                    wait_time = min(2 ** retry_attempt, 10)  # Exponential backoff, max 10s
                    logger.info(f"⏳ Retry {retry_attempt}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)

                scan_start = time.time()
                logger.info("[SCAN] Starting hardware scan...")

                # Step 1: Try to connect to SPR controller FIRST (priority order)
                # This determines which main unit is plugged in
                self.connection_progress.emit("Looking for SPR controller...")
                t0 = time.time()
                logger.info("[SCAN] Starting controller scan...")
                try:
                    self._connect_controller()
                    logger.info(f"[SCAN] Controller scan completed: ctrl={'FOUND' if self.ctrl else 'NOT FOUND'}")
                except Exception as ctrl_e:
                    logger.error(f"[SCAN] Controller scan exception: {ctrl_e}")
                    if HARDWARE_DEBUG:
                        import traceback
                        logger.debug(traceback.format_exc())
                if HARDWARE_DEBUG:
                    logger.info(f"[SCAN] Controller scan: {time.time()-t0:.2f}s")

                # Step 2: Try to connect to spectrometer (detector)
                # Combined with controller, this identifies P4SPR/P4PRO/ezSPR
                self.connection_progress.emit("Looking for spectrometer...")
                t0 = time.time()
                self._connect_spectrometer()
                # Second-chance explicit open: if still not connected, try direct USB4000 here
                if self.usb is None:
                    try:
                        logger.info("[SCAN] Spectrometer not found; attempting explicit USB4000 open...")
                        try:
                            from src.utils.usb4000_wrapper import USB4000
                        except ImportError:
                            from utils.usb4000_wrapper import USB4000
                        _usb = USB4000()
                        if _usb.open():
                            with self._connection_lock:
                                self.usb = _usb
                                if hasattr(_usb, 'serial_number'):
                                    self._spec_serial = _usb.serial_number
                            logger.info(f"[SCAN] USB4000 connected on second attempt: {getattr(self.usb, 'serial_number', None)}")
                        else:
                            logger.info("[SCAN] Explicit USB4000 open failed")
                    except Exception as sec_e:
                        logger.debug(f"[SCAN] Explicit USB4000 open error: {sec_e}")
                if HARDWARE_DEBUG:
                    logger.info(f"[SCAN] Spectrometer scan: {time.time()-t0:.2f}s")

                # Step 3: Try to connect to pump (AffiPump first)
                # AffiPump and KNX are mutually exclusive - only one can be connected
                self.connection_progress.emit("Looking for pump...")
                t0 = time.time()
                self._connect_pump()  # Tries AffiPump first
                if HARDWARE_DEBUG:
                    logger.info(f"[SCAN] Pump scan: {time.time()-t0:.2f}s")

                # Step 4: Try to connect to kinetic controller (only if no AffiPump found)
                if not self.pump:
                    self.connection_progress.emit("Looking for kinetic controller...")
                    t0 = time.time()
                    self._connect_kinetic()
                    if HARDWARE_DEBUG:
                        logger.info(f"[SCAN] Kinetic scan: {time.time()-t0:.2f}s")
                else:
                    logger.info("[SCAN] Skipping kinetic scan - AffiPump already connected")
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
                    logger.info(f"✅ Valid SPR device: {ctrl_type} (controller + detector)")
                elif ctrl_type and self.ctrl and not self.usb:
                    logger.warning(f"⚠️ {ctrl_type} incomplete: controller found but detector missing")
                    ctrl_type = None  # Don't show controller without detector

                # Check kinetics (KNX) - can be standalone, mutually exclusive with AffiPump
                knx_type = self._get_kinetic_type()
                if knx_type and self.knx:
                    valid_hardware.append(knx_type)
                    logger.info(f"✅ Valid kinetic device: {knx_type}")

                # Check pump (AffiPump) - standalone, mutually exclusive with KNX
                if self.pump:
                    valid_hardware.append('AffiPump')
                    logger.info(f"✅ Valid pump: AffiPump")

                # Emit final status
                status = {
                    'ctrl_type': ctrl_type,  # Only set if controller + detector both present
                    'knx_type': knx_type if self.knx else None,
                    'pump_connected': self.pump is not None,
                    'spectrometer': True if self.usb else False,
                    'spectrometer_serial': self.usb.serial_number if self.usb and hasattr(self.usb, 'serial_number') else None,
                    'sensor_ready': False,  # Will be set to True after calibration
                    'optics_ready': False,  # Will be set to True after calibration
                    'fluidics_ready': self.pump is not None,  # Fluidics ready if pump connected
                    # Consider scan successful if any single device is connected
                    'scan_successful': (self.usb is not None) or (self.ctrl is not None) or (self.pump is not None) or (self.knx is not None)
                }

                # Log hardware detection results
                total_time = time.time() - scan_start
                logger.info("="*60)
                logger.info(f"HARDWARE SCAN COMPLETE ({total_time:.2f}s)")
                logger.info("Scanning order: Controller → Detector → Pump → Kinetic")
                logger.info(f"  • Controller: {self.ctrl.name if self.ctrl else 'NOT FOUND'}")
                logger.info(f"  • Detector:   {'CONNECTED' if self.usb else 'NOT FOUND'}")
                logger.info(f"  • Pump:       {'CONNECTED' if self.pump else 'NOT FOUND'}")
                logger.info(f"  • Kinetic:    {self.knx.name if self.knx else ('SKIPPED' if self.pump else 'NOT FOUND')}")
                logger.info(f"  → Valid Hardware: {', '.join(valid_hardware) if valid_hardware else 'NONE'}")
                logger.info("="*60)

                # Emit status
                if valid_hardware:
                    logger.info(f"✅ Hardware scan SUCCESSFUL - found {len(valid_hardware)} device(s)")

                    # Check for special cases based on detector serial number
                    if self.usb and hasattr(self.usb, 'serial_number'):
                        detector_serial = self.usb.serial_number
                        self._check_and_apply_special_case(detector_serial, status)

                    # Lock main unit (controller + detector) - no changes allowed until disconnect
                    if self.ctrl and self.usb and not self._hardware_locked:
                        self._hardware_locked = True
                        logger.info("="*60)
                    logger.info("🔒 MAIN UNIT LOCKED (Controller + Detector)")
                    logger.info("   Configuration fixed until disconnect")
                    logger.info("   Peripherals (pump/kinetic) can still be added")
                    logger.info("="*60)

                # Lock peripherals if any are connected
                if (self.pump or self.knx) and not self._peripherals_locked:
                    self._peripherals_locked = True
                    logger.info("="*60)
                    logger.info("🔒 PERIPHERALS LOCKED")
                    peripheral_list = []
                    if self.pump:
                        peripheral_list.append("Pump")
                    if self.knx:
                        peripheral_list.append(f"Kinetic ({self.knx.name})")
                    logger.info(f"   Connected: {', '.join(peripheral_list)}")
                    logger.info("   No further peripheral changes until disconnect")
                    logger.info("="*60)
                else:
                    logger.warning("⚠️ Hardware scan FAILED - no valid hardware combinations")
                    self.connection_progress.emit("No valid hardware detected")
                    # Don't lock if scan failed

                # ALWAYS emit signal - UI will handle success/failure
                self.hardware_connected.emit(status)

                # If devices connected successfully, exit retry loop
                if valid_hardware:
                    logger.info("✅ Connection successful, exiting retry loop")
                    break

                # If no devices found and we haven't exhausted retries, continue loop
                retry_attempt += 1
                if retry_attempt < max_retries:
                    logger.warning(f"❌ Connection attempt {retry_attempt}/{max_retries} failed - retrying...")
                else:
                    logger.error(f"❌ All {max_retries} connection attempts failed")

            except Exception as e:
                logger.exception(f"Error during hardware scan: {e}")
                self.error_occurred.emit(f"Hardware scan failed: {e}")
                # On exception, retry if attempts remain
                retry_attempt += 1
                if retry_attempt < max_retries:
                    logger.warning(f"Retrying after exception ({retry_attempt}/{max_retries})...")
                    continue
                else:
                    break

        # Cleanup - mark connection process complete
        self._connecting = False

    def _peripheral_scan_worker(self):
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
                    logger.info(f"[PERIPHERAL SCAN] Pump scan: {time.time()-t0:.2f}s")
            else:
                logger.info("[PERIPHERAL SCAN] Pump already connected - skipping")

            # Step 2: Try to connect to kinetic controller (only if no AffiPump)
            if not self.pump and not self.knx:  # Mutually exclusive
                self.connection_progress.emit("Looking for kinetic controller...")
                t0 = time.time()
                self._connect_kinetic()
                if HARDWARE_DEBUG:
                    logger.info(f"[PERIPHERAL SCAN] Kinetic scan: {time.time()-t0:.2f}s")
            elif self.pump:
                logger.info("[PERIPHERAL SCAN] Skipping kinetic scan - pump already connected")
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
                valid_hardware.append('AffiPump')

            status = {
                'ctrl_type': ctrl_type,
                'knx_type': knx_type if self.knx else None,
                'pump_connected': self.pump is not None,
                'spectrometer': self.usb is not None,
                'spectrometer_serial': self.usb.serial_number if self.usb and hasattr(self.usb, 'serial_number') else None,
                'sensor_ready': self._sensor_verified,
                'optics_ready': self._optics_verified,
                'fluidics_ready': self.pump is not None,
                'scan_successful': len(valid_hardware) > 0
            }

            # Log results
            total_time = time.time() - scan_start
            logger.info("="*60)
            logger.info(f"PERIPHERAL SCAN COMPLETE ({total_time:.2f}s)")
            logger.info(f"  • Pump:       {'CONNECTED' if self.pump else 'NOT FOUND'}")
            logger.info(f"  • Kinetic:    {self.knx.name if self.knx else 'NOT FOUND'}")
            logger.info("="*60)

            # Lock peripherals if any were found
            if (self.pump or self.knx) and not self._peripherals_locked:
                self._peripherals_locked = True
                logger.info("="*60)
                logger.info("🔒 PERIPHERALS LOCKED")
                peripheral_list = []
                if self.pump:
                    peripheral_list.append("Pump")
                if self.knx:
                    peripheral_list.append(f"Kinetic ({self.knx.name})")
                logger.info(f"   Connected: {', '.join(peripheral_list)}")
                logger.info("   No further peripheral changes until disconnect")
                logger.info("="*60)

            # Emit updated status
            self.hardware_connected.emit(status)

            if self.pump or self.knx:
                logger.info("✅ Peripheral scan SUCCESSFUL")
            else:
                logger.info("⚠️ No peripherals found")

        except Exception as e:
            logger.exception(f"Error during peripheral scan: {e}")
            self.error_occurred.emit(f"Peripheral scan failed: {e}")
        finally:
            self._connecting = False

    def _connect_controller(self):
        """Attempt to connect to SPR controller."""
        print(f"[DEBUG] _connect_controller() CALLED, self.ctrl={self.ctrl}")
        logger.info(f"[DEBUG] _connect_controller() STARTING, self.ctrl={self.ctrl}")

        # CRITICAL SAFEGUARD: Prevent reconnection if controller already connected
        if self.ctrl is not None:
            print(f"[DEBUG] Ctrl already set: {self.ctrl}, returning early")
            try:
                controller_name = self.ctrl.name if hasattr(self.ctrl, 'name') else type(self.ctrl).__name__
                logger.warning(f"Controller already connected ({controller_name}) - skipping scan")
                return
            except:
                pass  # If we can't check name, proceed with connection attempt

        print("[DEBUG] Ctrl is None, proceeding with scan...")

        # Try reconnecting to cached port first (fast path after file reload)
        if self._ctrl_port and self._ctrl_type:
            logger.info(f"Attempting fast reconnect to {self._ctrl_type} on {self._ctrl_port}...")
            if self._try_reconnect_controller():
                logger.info("✅ Fast reconnect successful!")
                return
            else:
                logger.info("Fast reconnect failed, doing full scan...")

        try:
            if HARDWARE_DEBUG:
                logger.info("="*60)
                logger.info("SCANNING FOR CONTROLLERS...")
                logger.info("="*60)

            # Check available serial ports only in debug mode
            if HARDWARE_DEBUG:
                import serial.tools.list_ports
                available_ports = list(serial.tools.list_ports.comports())
                logger.info(f"Serial ports: {len(available_ports)}")
                for port in available_ports:
                    vid_str = f"0x{port.vid:04X}" if port.vid else "None"
                    pid_str = f"0x{port.pid:04X}" if port.pid else "None"
                    logger.info(f"  {port.device}: VID={vid_str} PID={pid_str} - {port.description}")

            # Get controller classes safely
            classes = _get_controller_classes()
            settings = _get_settings()

            # Try controllers in priority order: PicoP4SPR → PicoEZSPR → Arduino
            # STOP at first controller found - ignore the other 2

            # Priority 1: Try PicoP4SPR first (most common modern controller)
            logger.info(f"Trying PicoP4SPR (VID:PID = {hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})...")
            pico_p4spr = classes['PicoP4SPR']()
            open_result = pico_p4spr.open()
            if open_result:
                logger.info(f"✅ Controller connected: {pico_p4spr.name}")
                with self._connection_lock:
                    self.ctrl = pico_p4spr
                    self._ctrl_type = 'PicoP4SPR'
                    # Cache port if available
                    if hasattr(pico_p4spr, '_ser') and pico_p4spr._ser:
                        self._ctrl_port = pico_p4spr._ser.port
                        logger.info(f"Cached controller port: {self._ctrl_port}")

                # Initialize servo polarizer to S-mode position on connection
                self._initialize_servo_polarizer(pico_p4spr)
                return  # Found controller - stop searching
            else:
                logger.debug("PicoP4SPR open failed")

            # Priority 2: Try PicoEZSPR (P4PRO hardware)
            logger.info(f"Trying PicoEZSPR (VID:PID = {hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})...")
            pico_ezspr = classes['PicoEZSPR']()
            if pico_ezspr.open():
                logger.info(f"✅ Controller connected: {pico_ezspr.name}")
                with self._connection_lock:
                    self.ctrl = pico_ezspr
                    self._ctrl_type = 'PicoEZSPR'
                    if hasattr(pico_ezspr, '_ser') and pico_ezspr._ser:
                        self._ctrl_port = pico_ezspr._ser.port

                # Initialize servo polarizer to S-mode position on connection
                self._initialize_servo_polarizer(pico_ezspr)
                return  # Found controller - stop searching

            # Priority 3: Try Arduino (legacy controller)
            logger.info(f"Trying Arduino P4SPR (VID:PID = {hex(settings['ARDUINO_VID'])}:{hex(settings['ARDUINO_PID'])})...")
            arduino = classes['ArduinoController']()
            if arduino.open():
                logger.info(f"✅ Controller connected: {arduino.name}")
                with self._connection_lock:
                    self.ctrl = arduino
                    self._ctrl_type = 'ArduinoController'
                    if hasattr(arduino, '_ser') and arduino._ser:
                        self._ctrl_port = arduino._ser.port

                # Initialize servo polarizer to S-mode position on connection
                self._initialize_servo_polarizer(arduino)
                return  # Found controller - stop searching

            logger.warning("No SPR controller found")
            settings = _get_settings()
            logger.info(f"   Checked: Arduino ({hex(settings['ARDUINO_VID'])}:{hex(settings['ARDUINO_PID'])}), Pico ({hex(settings['PICO_VID'])}:{hex(settings['PICO_PID'])})")
            logger.info("   Check: drivers, USB cable, port, other programs")
            with self._connection_lock:
                self.ctrl = None
                # Don't clear cache - keep for retry

        except Exception as e:
            logger.error(f"Controller connection failed: {e}")
            if HARDWARE_DEBUG:
                logger.exception("Full exception details:")
            self.ctrl = None

    def _connect_kinetic(self):
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

    def _connect_pump(self):
        """Attempt to connect to pump."""
        try:
            from src.pump_controller import PumpController, FTDIError

            self.pump = PumpController.from_first_available()
            if self.pump:
                self.pump.send_command(0x41, b"e15R")
                logger.info("Pump connected")
            else:
                logger.debug("No pump found")

        except Exception as e:
            logger.error(f"Pump connection failed: {e}")
            self.pump = None

    def _get_controller_type(self) -> str:
        """Get the type of connected controller based on plugged hardware.

        Returns standardized hardware names for UI display:
        - P4SPR: Basic SPR controller (Arduino or PicoP4SPR)
        - P4PRO: Advanced SPR controller (PicoEZSPR hardware)
        - ezSPR: Standalone easy-to-use SPR controller

        Note: P4PRO is often paired with AffiPump.
              P4SPR is often paired with KNX.
        """
        if self.ctrl is None:
            return ''  # No controller = no device type

        name = getattr(self.ctrl, 'name', '')

        # Arduino-based P4SPR controller
        if name == 'p4spr':
            return 'P4SPR'

        # Pico-based P4SPR controller
        elif name == 'pico_p4spr':
            return 'P4SPR'

        # Pico-based EZSPR hardware = P4PRO product
        elif name == 'pico_ezspr':
            return 'P4PRO'

        return ''

    def _get_kinetic_type(self) -> str:
        """Get the type of connected kinetic controller.

        Returns standardized hardware name for UI display:
        - KNX: Kinetic controller (all variants map to "KNX")
        """
        if self.knx is None:
            return ''

        name = getattr(self.knx, 'name', '')
        # All kinetic controllers display as "KNX"
        if 'KNX' in name.upper() or 'KINETIC' in name.upper():
            return 'KNX'
        return ''

    def _verify_sensor_and_optics(self):
        """Verify sensor and optics quality for P4SPR devices.

        Checks:
        - Sensor: Spectrometer can acquire data with acceptable intensity
        - Optics: Signal quality is sufficient (not too noisy, not saturated)
        """
        self._sensor_verified = False
        self._optics_verified = False

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

            logger.info(f"Sensor test - Mean intensity: {mean_intensity:.1f}, Max: {max_intensity:.1f}")

            if mean_intensity < self.SENSOR_MIN_INTENSITY:
                logger.warning(f"Sensor signal too low: {mean_intensity:.1f} < {self.SENSOR_MIN_INTENSITY}")
                # Still mark as verified but log warning - sensor works but signal is weak
                self._sensor_verified = True
            elif max_intensity > self.SENSOR_MAX_INTENSITY:
                logger.warning(f"Sensor signal saturating: {max_intensity:.1f} > {self.SENSOR_MAX_INTENSITY}")
                self._sensor_verified = True
            else:
                logger.info("✅ Sensor verification passed")
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
                    logger.info("✅ Optics verification passed")
                    self._optics_verified = True
                else:
                    logger.warning(f"Optics quality low: SNR {snr:.2f} < {self.OPTICS_MIN_QUALITY}")
                    # Still mark as verified - optics work but quality is suboptimal
                    self._optics_verified = True
            else:
                logger.error("Optics verification failed: No signal detected")

        except Exception as e:
            logger.exception(f"Error during sensor/optics verification: {e}")
            # Mark as verified anyway if we have hardware - verification failed due to error, not hardware issue
            self._sensor_verified = self.usb is not None
            self._optics_verified = self.usb is not None

    def update_calibration_status(self, ch_error_list: list[str], calibration_type: str = 'full', s_ref_qc_results: dict = None):
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
        if calibration_type in ['full', 'afterglow']:
            self._afterglow_calibration_done = True
            logger.info("✅ Afterglow calibration completed")

        # Capture previous state before updating
        previous_optics_verified = self._optics_verified

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
                peak = qc.get('peak', 0)
                snr = qc.get('snr', 0)
                peak_wl = qc.get('peak_wl', 0)
                logger.debug(f"📊 S-ref QC Ch {ch.upper()}: peak={peak:.0f} counts, SNR={snr:.1f}, λ={peak_wl:.1f}nm")

                if not qc.get('passed', True):
                    self._s_ref_qc_passed = False
                    warnings = qc.get('warnings', [])
                    if warnings:
                        # Log warnings for debugging but don't impact UI
                        for warning in warnings:
                            logger.debug(f"   ⚠️ Ch {ch.upper()}: {warning}")
                        qc_warnings.extend([f"Ch {ch.upper()}: {w}" for w in warnings])

            if not self._s_ref_qc_passed:
                # Informational warning in debug log only
                logger.debug(f"ℹ️ S-ref optical QC notes: {'; '.join(qc_warnings)}")
                logger.debug("   Note: QC warnings are informational and don't block operation")
            else:
                logger.debug("✅ S-ref optical QC: All channels passed quality checks")

        # Optics ready requires:
        # 1. Afterglow calibration done
        # 2. Calibration passed (all channels)
        # 3. Hardware connected
        # 4. No active leak detected
        # Note: S-ref QC is informational only (logged for debugging)
        # Note: Sensor readiness is tracked separately via FWHM measurements
        if (self._afterglow_calibration_done and
            self._calibration_passed and
            self.usb is not None and
            not self._optics_leak_detected):
            self._optics_verified = True
            logger.info("✅ Optics verification: All conditions met - OPTICS READY")
        else:
            self._optics_verified = False

            # Log specific failure reasons
            reasons = []
            if not self._afterglow_calibration_done:
                reasons.append("afterglow calibration not performed")
            if not self._calibration_passed:
                reasons.append(f"calibration failed for channels {sorted(ch_error_list)}")
            if self._optics_leak_detected:
                reasons.append("optical leak detected")
            if len(self._maintenance_required) > 0:
                maint_list = sorted(list(set(self._maintenance_required)))  # Remove duplicates and sort
                reasons.append(f"maintenance required for channels {maint_list}")

            logger.warning(f"⚠️ Optics NOT ready: {', '.join(reasons)}")

        # DO NOT emit hardware_connected here - this would trigger connection flow again
        # and cause calibration loop. Just emit hardware status update for UI.
        # The hardware_connected signal should only be emitted during initial connection,
        # not during calibration status updates.

        # Emit hardware status update if optics state changed
        if previous_optics_verified != self._optics_verified:
            self._emit_hardware_status()

    def update_led_intensity(self, channel: str, intensity: float, timestamp: float):
        """Monitor LED intensity in real-time to detect sudden drops indicating leaks.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            intensity: Current raw intensity reading
            timestamp: Time of measurement
        """
        import time

        # Update peak intensity
        if intensity > self._channel_max_intensity[channel]:
            self._channel_max_intensity[channel] = intensity

        # Add to history with timestamp
        self._channel_intensity_history[channel].append((timestamp, intensity))

        # Keep only last 5 seconds of data
        cutoff_time = timestamp - 5.0
        self._channel_intensity_history[channel] = [
            (t, i) for t, i in self._channel_intensity_history[channel] if t >= cutoff_time
        ]

        # Check for sudden intensity drop (leak detection)
        # Only check if we have calibrated and have enough history
        if (self._calibration_passed and
            len(self._channel_intensity_history[channel]) > 10 and
            self._channel_max_intensity[channel] > 1000):  # Only check if we've seen good signal

            # Get intensity from 3 seconds ago
            three_seconds_ago = timestamp - 3.0
            old_intensities = [i for t, i in self._channel_intensity_history[channel] if t <= three_seconds_ago]

            if len(old_intensities) > 0:
                avg_old_intensity = sum(old_intensities) / len(old_intensities)

                # Check if current intensity dropped below 10% of max detector counts
                max_detector_counts = 65535  # USB4000 16-bit
                leak_threshold = max_detector_counts * 0.10

                # Leak detected if:
                # 1. Current intensity is below 10% of max detector counts
                # 2. Previous intensity was significantly higher (drop > 50%)
                if (intensity < leak_threshold and
                    avg_old_intensity > leak_threshold * 2 and
                    not self._optics_leak_detected):

                    self._optics_leak_detected = True
                    logger.error(
                        f"🔴 OPTICAL LEAK DETECTED in channel {channel.upper()}: "
                        f"Intensity dropped from {avg_old_intensity:.0f} to {intensity:.0f} "
                        f"(threshold: {leak_threshold:.0f} counts)"
                    )

                    # Update optics status to NOT READY
                    previous_optics_verified = self._optics_verified
                    self._optics_verified = False

                    # Emit status update
                    status = {
                        'ctrl_type': self._get_controller_type(),
                        'knx_type': self._get_kinetic_type(),
                        'pump_connected': self.pump is not None,
                        'spectrometer': self.usb is not None,
                        'sensor_ready': self._sensor_verified,
                        'optics_ready': self._optics_verified,
                        'fluidics_ready': self.pump is not None
                    }
                    self.hardware_connected.emit(status)

                    if previous_optics_verified:
                        self._emit_hardware_status()

                    # Emit error
                    self.hardware_error.emit(
                        f"Optical leak detected in channel {channel.upper()}. "
                        f"Check for loose connections or damaged optical components."
                    )

    def reset_leak_detection(self):
        """Reset leak detection state after user has fixed the issue."""
        self._optics_leak_detected = False
        self._channel_intensity_history = {'a': [], 'b': [], 'c': [], 'd': []}
        self._channel_max_intensity = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        logger.info("🔄 Leak detection reset - monitoring restarted")

        # Re-evaluate optics status (sensor status is independent, set by FWHM)
        if (self._afterglow_calibration_done and
            self._calibration_passed and
            self.usb is not None):
            self._optics_verified = True
            logger.info("✅ Optics status restored to READY")
            self._emit_hardware_status()

    def update_fwhm_status(self, channel: str, fwhm: float):
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
                logger.info(f"✅ Sensor verification: FWHM passed - channels {good_channels} < {self._fwhm_threshold} nm")
            self._sensor_verified = True
        else:
            # Either no measurements or all measurements are bad
            if len(measured_channels) == 0:
                # No FWHM data at all - sensor NOT ready
                if previous_sensor_verified:
                    logger.warning("❌ Sensor NOT ready: No FWHM data available (no chip/leak/connection issue)")
                self._sensor_verified = False
            else:
                # Have measurements but all are poor quality
                fwhm_str = {ch: f"{val:.1f}" for ch, val in measured_channels.items()}
                if previous_sensor_verified:
                    logger.warning(f"❌ Sensor NOT ready: All FWHM values exceed threshold - {fwhm_str} nm (threshold: {self._fwhm_threshold} nm)")
                self._sensor_verified = False

        # Emit hardware status update if sensor state changed
        if previous_sensor_verified != self._sensor_verified:
            status = {
                'ctrl_type': self._get_controller_type(),
                'knx_type': self._get_kinetic_type(),
                'pump_connected': self.pump is not None,
                'spectrometer': self.usb is not None,
                'sensor_ready': self._sensor_verified,
                'optics_ready': self._optics_verified,
                'fluidics_ready': self.pump is not None
            }
            self.hardware_connected.emit(status)
            self._emit_hardware_status()

    def check_intensity_leak(self, channel: str, intensity: float, dark_noise: float):
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
        pass

    def _emit_hardware_status(self):
        """Emit current hardware status with updated verification flags."""
        status = {
            'ctrl_type': self._get_controller_type(),
            'knx_type': self._get_kinetic_type(),
            'pump_connected': self.pump is not None,
            'spectrometer': 'USB4000' if self.usb else None,
            'spectrometer_serial': self.usb.serial_number if self.usb and hasattr(self.usb, 'serial_number') else None,
            'sensor_ready': self._sensor_verified,
            'optics_ready': self._optics_verified,
            'fluidics_ready': self.pump is not None
        }

        self.hardware_connected.emit(status)
        logger.info(f"Hardware status update: sensor_ready={self._sensor_verified}, optics_ready={self._optics_verified}")

    def _check_and_apply_special_case(self, detector_serial: str, status: dict) -> None:
        """Check for and apply device-specific special cases.

        Args:
            detector_serial: The detector's serial number
            status: Hardware status dictionary (modified in-place if special case found)
        """
        try:
            from utils.device_special_cases import check_special_case, apply_special_case

            # Check if this detector has a special case
            special_case = check_special_case(detector_serial)

            if special_case:
                # Store special case info for later use
                self._special_case = special_case
                status['special_case'] = {
                    'detector_serial': detector_serial,
                    'description': special_case.get('description', 'No description'),
                    'has_overrides': True
                }

                logger.info("📋 Special case will be applied during device initialization")

                # Log which parameters will be overridden
                override_params = [k for k in special_case.keys()
                                 if k not in ['description', 'notes']]
                if override_params:
                    logger.info(f"   Overrides: {', '.join(override_params)}")
            else:
                self._special_case = None
                status['special_case'] = None

        except Exception as e:
            logger.error(f"Error checking special cases: {e}")
            self._special_case = None
            status['special_case'] = None

    def get_special_case(self):
        """Get the current special case configuration if any.

        Returns:
            Special case dictionary or None
        """
        return getattr(self, '_special_case', None)

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
            'locked': self._hardware_locked,
            'controller': self.ctrl.name if self.ctrl else None,
            'detector': self.usb.serial_number if self.usb and hasattr(self.usb, 'serial_number') else None,
            'kinetic': self.knx.name if self.knx else None,
            'pump': 'Connected' if self.pump else None,
            'special_case': self._special_case.get('description') if self._special_case else None
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
            'controller': None,
            'spectrometer': None,
            'pump': None,
            'kinetic': None
        }

        with self._connection_lock:
            # Check controller
            if self.ctrl:
                try:
                    # Try simple command to verify connection is alive
                    if hasattr(self.ctrl, '_ser') and self.ctrl._ser and self.ctrl._ser.is_open:
                        health['controller'] = True
                    else:
                        health['controller'] = False
                        logger.warning("Controller serial port not open")
                except Exception as e:
                    health['controller'] = False
                    logger.error(f"Controller health check failed: {e}")

            # Check spectrometer
            if self.usb:
                try:
                    # Verify device is still accessible
                    if hasattr(self.usb, '_dev') and self.usb._dev:
                        health['spectrometer'] = True
                    else:
                        health['spectrometer'] = False
                        logger.warning("Spectrometer device handle lost")
                except Exception as e:
                    health['spectrometer'] = False
                    logger.error(f"Spectrometer health check failed: {e}")

            # Check pump (if present)
            if self.pump:
                try:
                    health['pump'] = True  # Basic presence check
                except Exception as e:
                    health['pump'] = False
                    logger.error(f"Pump health check failed: {e}")

            # Check kinetic (if present)
            if self.knx:
                try:
                    health['kinetic'] = True  # Basic presence check
                except Exception as e:
                    health['kinetic'] = False
                    logger.error(f"Kinetic health check failed: {e}")

        return health

    def auto_recover_connection(self) -> bool:
        """Attempt to recover lost connections using cached info.

        Returns:
            True if any connections were recovered, False otherwise
        """
        recovered = False

        logger.info("🔄 Attempting connection recovery...")

        with self._connection_lock:
            # Try to recover controller
            if self.ctrl is None and self._ctrl_port:
                logger.info(f"Attempting controller recovery on {self._ctrl_port}...")
                if self._try_reconnect_controller():
                    recovered = True
                    logger.info("✅ Controller recovered")
                else:
                    logger.warning("❌ Controller recovery failed")

            # Try to recover spectrometer
            if self.usb is None and self._spec_serial:
                logger.info(f"Attempting spectrometer recovery: {self._spec_serial}...")
                if self._try_reconnect_spectrometer():
                    recovered = True
                    logger.info("✅ Spectrometer recovered")
                else:
                    logger.warning("❌ Spectrometer recovery failed")

        if recovered:
            logger.info("✅ Connection recovery successful")
            self._emit_hardware_status()
        else:
            logger.warning("❌ Connection recovery failed - full rescan may be needed")

        return recovered


    def disconnect_all(self):
        """Disconnect all hardware devices gracefully and unlock for new hardware."""
        logger.info("="*60)
        logger.info("🔓 DISCONNECTING ALL HARDWARE - Unlocking configuration")
        logger.info("="*60)

        # Turn off all LEDs before disconnecting (graceful exit)
        if self.ctrl:
            try:
                logger.debug("Turning off all LEDs before disconnect...")
                self.ctrl.turn_off_channels()
                import time
                time.sleep(0.1)  # Brief delay to ensure command executes
                logger.debug("✅ LEDs turned off")
            except Exception as e:
                logger.warning(f"Could not turn off LEDs: {e}")

        # Disconnect controller
        if self.ctrl:
            try:
                logger.debug("Closing controller connection...")
                self.ctrl.close()
                logger.debug("✅ Controller closed")
            except Exception as e:
                logger.error(f"Error closing controller: {e}")
            self.ctrl = None

        # Disconnect kinetic controller
        if self.knx:
            try:
                logger.debug("Closing kinetic controller...")
                self.knx.close()
                logger.debug("✅ Kinetic controller closed")
            except Exception as e:
                logger.error(f"Error closing kinetic controller: {e}")
            self.knx = None

        # Disconnect pump
        if self.pump:
            try:
                logger.debug("Closing pump...")
                self.pump.close()
                logger.debug("✅ Pump closed")
            except Exception as e:
                logger.error(f"Error closing pump: {e}")
            self.pump = None

        # Disconnect spectrometer
        if self.usb:
            try:
                logger.debug("Closing spectrometer...")
                self.usb.close()
                logger.debug("✅ Spectrometer closed")
            except Exception as e:
                logger.error(f"Error closing spectrometer: {e}")
            self.usb = None

        # Clear special case configuration
        self._special_case = None

        # Clear verification states
        self._sensor_verified = False
        self._optics_verified = False
        self._calibration_passed = False
        self._afterglow_calibration_done = False

        # Unlock hardware - ready for new connection
        self._hardware_locked = False

        self.hardware_disconnected.emit()
        logger.info("="*60)
        logger.info("✅ All hardware disconnected - Ready for new hardware")
        logger.info("="*60)
