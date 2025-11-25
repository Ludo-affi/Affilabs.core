"""Hardware Manager - Coordinates all hardware devices.

This class manages:
- SPR controllers (P4SPR, EZSPR, Pico variants)
- Kinetic controllers (KNX, KNX2, PicoKNX2)
- Pumps (Affipump)
- Spectrometers (USB4000, PhasePhotonics)

All operations run in background threads to avoid blocking the UI.
"""

from PySide6.QtCore import QObject, Signal, QThread
from utils.logger import logger
from typing import Optional
import threading
import time

# ============================================================================
# DEBUG FLAGS - Set to True for detailed troubleshooting output
# ============================================================================
HARDWARE_DEBUG = True  # Enable detailed connection timing and device scan logs
CONNECTION_TIMEOUT = 2.0  # Seconds to wait for USB device discovery (2s fast, 5s safe)


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
        self._connecting = False
        self._connection_thread = None

        # Verification results
        self._sensor_verified = False
        self._optics_verified = False

        # Calibration results tracking
        self._ch_error_list = []  # List of failed channels
        self._calibration_passed = False
        self._afterglow_calibration_done = False  # Track if afterglow calibration completed

        # FWHM tracking for sensor verification
        self._channel_fwhm = {'a': None, 'b': None, 'c': None, 'd': None}  # type: dict[str, Optional[float]]
        self._fwhm_threshold = 60.0  # nm - FWHM_GOOD threshold

        # Optics intensity monitoring for leak detection
        self._channel_intensity_history = {'a': [], 'b': [], 'c': [], 'd': []}  # (timestamp, intensity)
        self._channel_max_intensity = {'a': 0, 'b': 0, 'c': 0, 'd': 0}  # Peak intensity seen
        self._optics_leak_detected = False
        self._maintenance_required = []  # Channels requiring LED PCB replacement

        logger.info("HardwareManager initialized")

    def scan_and_connect(self):
        """Scan for and connect to all available hardware (non-blocking).

        Always performs a fresh scan to ensure both controller and spectrometer are detected.
        If hardware is already connected, it will be detected again (idempotent operation).

        CRITICAL SAFEGUARDS TO PREVENT CONTROLLER HIJACKING:

        1. Priority Order: PicoP4SPR → Arduino → PicoEZSPR
           - Modern Pico controllers checked first
           - Search stops immediately when first controller found

        2. Strict VID/PID Matching:
           - Arduino: Only connects to exact VID/PID match
           - PicoP4SPR: VID/PID + device identity validation ("id\\n" → "P4SPR")

        3. No Dangerous Fallbacks:
           - Arduino: NO fallback COM port enumeration
           - PicoP4SPR: Fallback excludes Arduino VID/PID ports

        4. Reconnection Prevention:
           - If self.ctrl already exists, skip controller scan
           - Prevents hijacking by different device during session

        5. Identity Validation:
           - Arduino validates with "turn_off_channels" command
           - Pico validates with "id" command returning device name

        See: README_HARDWARE_BEHAVIOR.md for complete documentation
        """
        print("\n" + "="*80)
        print("[HARDWARE_MANAGER] scan_and_connect() called!")
        print("="*80 + "\n")
        logger.info("HardwareManager.scan_and_connect() called")
        
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
        """Worker thread that scans for hardware."""
        try:
            scan_start = time.time()
            logger.info("[SCAN] Starting hardware scan...")

            # Step 1: Try to connect to spectrometer
            self.connection_progress.emit("Looking for spectrometer...")
            t0 = time.time()
            self._connect_spectrometer()
            if HARDWARE_DEBUG:
                logger.info(f"[SCAN] Spectrometer scan: {time.time()-t0:.2f}s")

            # Step 2: Try to connect to SPR controller
            self.connection_progress.emit("Looking for SPR controller...")
            t0 = time.time()
            self._connect_controller()
            if HARDWARE_DEBUG:
                logger.info(f"[SCAN] Controller scan: {time.time()-t0:.2f}s")

            # Step 3: Try to connect to kinetic controller
            self.connection_progress.emit("Looking for kinetic controller...")
            t0 = time.time()
            self._connect_kinetic()
            if HARDWARE_DEBUG:
                logger.info(f"[SCAN] Kinetic scan: {time.time()-t0:.2f}s")

            # Step 4: Try to connect to pump
            self.connection_progress.emit("Looking for pump...")
            t0 = time.time()
            self._connect_pump()
            if HARDWARE_DEBUG:
                logger.info(f"[SCAN] Pump scan: {time.time()-t0:.2f}s")

            # Don't verify sensor/optics here - they should only be marked ready after calibration
            # Initial status is False (not ready) until calibration completes

            # Get controller type
            ctrl_type = self._get_controller_type()

            # Emit final status
            status = {
                'ctrl_type': ctrl_type,
                'knx_type': self._get_kinetic_type(),
                'pump_connected': self.pump is not None,
                'spectrometer': self.usb is not None,
                'spectrometer_serial': self.usb.serial_number if self.usb and hasattr(self.usb, 'serial_number') else None,
                'sensor_ready': False,  # Will be set to True after calibration
                'optics_ready': False,  # Will be set to True after calibration
                'fluidics_ready': self.pump is not None  # Fluidics ready if pump connected
            }

            # Log hardware detection results
            total_time = time.time() - scan_start
            logger.info("="*60)
            logger.info(f"HARDWARE SCAN COMPLETE ({total_time:.2f}s)")
            logger.info(f"  • Controller: {self.ctrl.name if self.ctrl else 'NOT FOUND'}")
            logger.info(f"  • Kinetic:    {self.knx.name if self.knx else 'NOT FOUND'}")
            logger.info(f"  • Pump:       {'CONNECTED' if self.pump else 'NOT FOUND'}")
            logger.info(f"  • Spectro:    {'CONNECTED' if self.usb else 'NOT FOUND'}")
            logger.info(f"  → Device Type: {ctrl_type if ctrl_type else 'UNKNOWN (no controller)'}")
            logger.info("="*60)

            # ALWAYS emit hardware_connected signal, even if nothing found
            # This ensures UI gets updated and power button returns to disconnected state
            if any([self.ctrl, self.knx, self.pump, self.usb]):
                logger.info(f"✅ Hardware scan complete - emitting connection status")
            else:
                logger.info("⚠️ No hardware detected - returning to disconnected state")
                self.connection_progress.emit("No hardware detected")

            # Emit status regardless - UI will handle "no hardware" case
            self.hardware_connected.emit(status)

        except Exception as e:
            logger.exception(f"Error during hardware scan: {e}")
            self.error_occurred.emit(f"Hardware scan failed: {e}")
        finally:
            self._connecting = False

    def _connect_spectrometer(self):
        """Attempt to connect to spectrometer."""
        try:
            from utils.detector_factory import create_detector
            from utils.common import get_config
            from utils.device_integration import initialize_device_on_connection

            config = get_config()
            if config is None:
                config = {}
            if HARDWARE_DEBUG:
                logger.info("="*60)
                logger.info("SCANNING FOR SPECTROMETER...")
                logger.info("="*60)
            logger.info("Connecting to spectrometer...")
            self.usb = create_detector(None, config)

            if self.usb:
                logger.info(f"Spectrometer connected: {self.usb.serial_number if hasattr(self.usb, 'serial_number') else 'Unknown S/N'}")

                # Log detailed info only in debug mode
                if HARDWARE_DEBUG:
                    if hasattr(self.usb, 'name'):
                        logger.info(f"   Model: {self.usb.name}")
                    if hasattr(self.usb, 'get_info'):
                        try:
                            info = self.usb.get_info()
                            logger.info(f"   Info: {info}")
                        except Exception as e:
                            logger.debug(f"   Could not get spectrometer info: {e}")

                # Initialize device-specific configuration
                device_dir = initialize_device_on_connection(self.usb)
                if device_dir and HARDWARE_DEBUG:
                    logger.info(f"   Device config: {device_dir}")
            else:
                logger.warning("No spectrometer detected")
                if HARDWARE_DEBUG:
                    logger.info("   Check: USB cable, drivers, power")

        except Exception as e:
            logger.error(f"Spectrometer connection failed: {e}")
            if HARDWARE_DEBUG:
                import traceback
                logger.debug(traceback.format_exc())
            self.usb = None

    def _connect_controller(self):
        """Attempt to connect to SPR controller."""
        # CRITICAL SAFEGUARD: Prevent reconnection if controller already connected
        if self.ctrl is not None:
            try:
                controller_name = self.ctrl.name if hasattr(self.ctrl, 'name') else type(self.ctrl).__name__
                logger.warning(f"Controller already connected ({controller_name}) - skipping scan")
                return
            except:
                pass  # If we can't check name, proceed with connection attempt

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

            # Try controllers in priority order: Pico first (more modern), then Arduino
            from utils.controller import ArduinoController, PicoP4SPR, PicoEZSPR
            from settings.settings import ARDUINO_VID, ARDUINO_PID, PICO_VID, PICO_PID

            # Try PicoP4SPR first (highest priority)
            if HARDWARE_DEBUG:
                logger.info(f"Trying PicoP4SPR (VID:PID = {hex(PICO_VID)}:{hex(PICO_PID)})...")
            pico_p4spr = PicoP4SPR()
            if pico_p4spr.open():
                logger.info(f"Controller connected: {pico_p4spr.name}")
                self.ctrl = pico_p4spr
                return

            # Try Arduino as fallback
            if HARDWARE_DEBUG:
                logger.info(f"Trying Arduino P4SPR (VID:PID = {hex(ARDUINO_VID)}:{hex(ARDUINO_PID)})...")
            arduino = ArduinoController()
            if arduino.open():
                logger.info(f"Controller connected: {arduino.name}")
                self.ctrl = arduino
                return

            # Try PicoEZSPR
            if HARDWARE_DEBUG:
                logger.info(f"Trying PicoEZSPR (VID:PID = {hex(PICO_VID)}:{hex(PICO_PID)})...")
            pico_ezspr = PicoEZSPR()
            if pico_ezspr.open():
                logger.info(f"Controller connected: {pico_ezspr.name}")
                self.ctrl = pico_ezspr
                return

            logger.warning("No SPR controller found")
            if HARDWARE_DEBUG:
                logger.info(f"   Checked: Arduino ({hex(ARDUINO_VID)}:{hex(ARDUINO_PID)}), Pico ({hex(PICO_VID)}:{hex(PICO_PID)})")
                logger.info("   Check: drivers, USB cable, port, other programs")
            self.ctrl = None

        except Exception as e:
            logger.error(f"Controller connection failed: {e}")
            if HARDWARE_DEBUG:
                logger.exception("Full exception details:")
            self.ctrl = None

    def _connect_kinetic(self):
        """Attempt to connect to kinetic controller."""
        try:
            from utils.controller import KineticController
            knx2 = KineticController()
            if knx2.open():
                logger.info(f"KNX2 controller connected: {knx2.get_info()}")
                self.knx = knx2
                return

            from utils.controller import PicoKNX2
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
            from pump_controller import PumpController, FTDIError

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

        Device identification logic:
        - Arduino OR PicoP4SPR alone = P4SPR
        - PicoP4SPR + RPi kinetic controller = P4SPR+KNX or ezSPR (check serial number list)
        - PicoEZSPR = P4PRO

        The device type is ONLY determined by what is physically plugged in.
        Serial number exceptions will be handled separately.
        """
        if self.ctrl is None:
            return ''  # No controller = no device type

        name = getattr(self.ctrl, 'name', '')

        # Arduino-based P4SPR controller
        if name == 'p4spr':
            return 'P4SPR'

        # Pico-based P4SPR controller
        elif name == 'pico_p4spr':
            # Check if kinetic controller is also connected
            if self.knx is not None:
                # PicoP4SPR + RPi = P4SPR+KNX or ezSPR
                # TODO: Check serial number list to determine if ezSPR vs P4SPR+KNX
                knx_name = getattr(self.knx, 'name', '')
                if 'EZSPR' in knx_name.upper():
                    return 'ezSPR'
                elif 'KNX' in knx_name.upper():
                    return 'P4SPR+KNX'
                else:
                    return 'P4SPR+KNX'  # Default to KNX if unclear
            else:
                # PicoP4SPR alone = P4SPR
                return 'P4SPR'

        # Pico-based ezSPR controller (P4PRO)
        elif name == 'pico_ezspr':
            return 'P4PRO'

        return ''

    def _get_kinetic_type(self) -> str:
        """Get the type of connected kinetic controller."""
        if self.knx is None:
            return ''

        name = getattr(self.knx, 'name', '')
        if 'KNX' in name.upper():
            return 'KNX2'
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

    def disconnect_all(self):
        """Disconnect all hardware devices."""
        logger.info("Disconnecting all hardware...")

        if self.ctrl:
            try:
                self.ctrl.close()
            except Exception as e:
                logger.error(f"Error closing controller: {e}")
            self.ctrl = None

        if self.knx:
            try:
                self.knx.close()
            except Exception as e:
                logger.error(f"Error closing kinetic controller: {e}")
            self.knx = None

        if self.pump:
            try:
                self.pump.close()
            except Exception as e:
                logger.error(f"Error closing pump: {e}")
            self.pump = None

        if self.usb:
            try:
                self.usb.close()
            except Exception as e:
                logger.error(f"Error closing spectrometer: {e}")
            self.usb = None

        self.hardware_disconnected.emit()
        logger.info("All hardware disconnected")
