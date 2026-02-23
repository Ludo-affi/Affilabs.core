from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path
from typing import Final

import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import PICO_PID, PICO_VID

from affilabs.utils.controllers._base import FlowController, CH_DICT
from affilabs.utils.controllers._valve_mixin import ValveCycleMixin


# ============================================================================
# PicoP4PRO - Standalone P4PRO Controller (4 LEDs + Servo + KNX Valves)
# ============================================================================

class PicoP4PRO(ValveCycleMixin, FlowController):
    """P4PRO controller with 4-LED control, servo polarizer, and KNX valve control.

    Hardware Features:
    - 4 LED channels (A, B, C, D) with batch intensity control
    - Servo polarizer (PWM 0-255, uses 'sv' RAM-only command for fast calibration)
    - 6-port valves (2 channels) with cycle tracking and safety timeout
    - 3-way valves (2 channels) with state monitoring

    Firmware: P4PRO V2.1+
    Command Protocol: Uses 'sv' for servo (not 'servo:' to avoid EEPROM writes)
    """

    def __init__(self) -> None:
        super().__init__(name="pico_p4pro")
        self._ser = None
        self._servo_s_pos = None  # Loaded from device_config
        self._servo_p_pos = None  # Loaded from device_config
        self.version = ""
        self.firmware_id = "P4PRO"

        # NOTE: _load_valve_cycles() called in open() after serial port is established
        self._init_valve_tracking()

    def valid(self):
        return (self._ser is not None and self._ser.is_open) or self.open()

    def open(self) -> bool:
        """Open P4PRO controller by scanning for P4PRO firmware ID."""
        print("DEBUG: PicoP4PRO.open() - Looking for VID=0x2e8a PID=0xa")
        logger.info("PicoP4PRO.open() - Looking for VID=0x2e8a PID=0xa")

        # Try VID/PID match first
        print("DEBUG: PicoP4PRO - About to enumerate comports()")
        ports = list(serial.tools.list_ports.comports())
        print(f"DEBUG: PicoP4PRO - Found {len(ports)} ports")
        for dev in ports:
            print(f"DEBUG: PicoP4PRO - Checking port {dev.device}, VID={hex(dev.vid) if dev.vid else None}, PID={hex(dev.pid) if dev.pid else None}")
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                print(f"DEBUG: MATCH! Trying PicoP4PRO on {dev.device}")
                logger.info(f"MATCH! Trying PicoP4PRO on {dev.device}")
                try:
                    print(f"DEBUG: PicoP4PRO - Attempting to open serial port {dev.device}...")
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=0.05,  # 50ms timeout - firmware may need up to 50ms for response
                        write_timeout=1,
                    )
                    print(f"DEBUG: PicoP4PRO - Serial port {dev.device} opened successfully")
                    # Improve reliability on Windows CDC by toggling DTR/RTS
                    try:
                        self._ser.dtr = True
                        self._ser.rts = True
                    except Exception:
                        pass
                    # Clear buffers before identification
                    try:
                        self._ser.reset_input_buffer()
                        self._ser.reset_output_buffer()
                    except Exception:
                        pass
                    cmd = "id\n"
                    print("DEBUG: PicoP4PRO - Sending 'id' command...")
                    self._ser.write(cmd.encode())
                    import time
                    time.sleep(0.10)
                    reply = self._ser.readline().decode().strip()
                    print(f"DEBUG: PicoP4PRO - Got ID reply: '{reply}'")

                    if reply == "P4PRO" or "P4PRO" in reply or reply == "p4proplus" or "p4proplus" in reply:
                        print("DEBUG: PicoP4PRO - ID match! This is a P4PRO/P4PROPLUS!")
                        self.firmware_id = reply
                        # Clear any leftover data before version query
                        try:
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        time.sleep(0.10)  # Wait for version response
                        version_raw = self._ser.readline().decode().strip()
                        self.version = version_raw[0:4] if len(version_raw) >= 4 else version_raw
                        logger.info(f"✅ Found Pico P4PRO firmware: {reply} (version {self.version})")
                        # Load valve cycles now that serial port is established
                        self._load_valve_cycles()
                        print("DEBUG: PicoP4PRO - Returning True (success!)")
                        return True
                    else:
                        print(f"DEBUG: PicoP4PRO - ID mismatch, expected 'P4PRO', got '{reply}'")
                        logger.warning(f"ID mismatch - expected 'P4PRO', got '{reply}'")
                        try:
                            self._ser.close()
                        except Exception:
                            pass
                        self._ser = None
                except Exception as e:
                    print(f"DEBUG: PicoP4PRO - EXCEPTION while trying {dev.device}: {e}")
                    logger.error(f"Error connecting to {dev.device}: {e}")
                    if self._ser:
                        try:
                            self._ser.close()
                        except Exception:
                            pass
                        self._ser = None

        print("DEBUG: PicoP4PRO - No VID/PID match found")
        logger.warning("No PicoP4PRO found with VID/PID match")
        # FALLBACK: Try all COM ports if VID/PID match failed
        logger.info("🔧 PicoP4PRO VID/PID match failed - trying all COM ports...")
        for dev in serial.tools.list_ports.comports():
            try:
                logger.debug(f"   Trying {dev.device}...")
                self._ser = serial.Serial(
                    port=dev.device,
                    baudrate=115200,
                    timeout=0.5,
                    write_timeout=1,
                )
                # Improve reliability: toggle DTR/RTS and flush buffers
                with contextlib.suppress(Exception):
                    self._ser.dtr = True
                    self._ser.rts = True
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()

                # Identify firmware
                cmd = "id\n"
                self._ser.write(cmd.encode())
                import time
                time.sleep(0.15)
                reply = self._ser.readline().decode().strip()

                if reply == "P4PRO" or "P4PRO" in reply:
                    self.firmware_id = reply
                    # Clear any leftover data before version query
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass
                    cmd = "iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.10)
                    version_raw = self._ser.readline().decode().strip()
                    self.version = version_raw[0:4] if len(version_raw) >= 4 else version_raw
                    logger.info(
                        f"[OK] Found Pico P4PRO on {dev.device} (firmware: {reply}, fallback method)",
                    )
                    # Load valve cycles now that serial port is established
                    self._load_valve_cycles()
                    return True
                # Not P4PRO - close and continue scan
                self._ser.close()
                self._ser = None
            except Exception as e:
                logger.debug(f"   {dev.device} not a Pico P4PRO: {e}")
                if self._ser is not None:
                    with contextlib.suppress(Exception):
                        self._ser.close()
                    self._ser = None

        return False

    def close(self) -> None:
        """Close serial connection to P4PRO."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                logger.error(f"Error closing P4PRO serial port: {e}")
            finally:
                self._ser = None

    # ========================================================================
    # LED Control (4 channels: A, B, C, D)
    # ========================================================================

    def enable_multi_led(self, a: bool = True, b: bool = True, c: bool = True, d: bool = True) -> bool:
        """Enable multiple LEDs using lm:ABCD command.

        CRITICAL: P4PRO firmware requires lm:ABCD command (letters, not numbers!)
        before LEDs respond to intensity commands (la:X, lb:X, etc.).

        Args:
            a, b, c, d: Which channels to enable (True) or disable (False)

        Returns:
            True if command sent successfully
        """
        try:
            if self._ser is not None or self.open():
                # Build channel string: enabled channels use letter, disabled use nothing
                # e.g., all enabled = "ABCD", only A and C = "AC"
                channels = ""
                if a: channels += "A"
                if b: channels += "B"
                if c: channels += "C"
                if d: channels += "D"

                cmd = f"lm:{channels}\n"
                logger.debug(f"P4PRO LED enable: Sending {cmd.strip()!r}")
                self._ser.write(cmd.encode())
                time.sleep(0.05)
                resp = self._ser.read(10)

                # Check for success response
                logger.debug(f"P4PRO LED enable response: {resp!r}")
                if resp != b'1':
                    logger.warning(f"LED enable command {cmd.strip()!r} returned: {resp!r} (expected b'1')")
                    return False
                logger.info(f"P4PRO LEDs enabled: {channels}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error enabling multi-LED: {e}")
            return False

    def turn_on_channel(self, ch: str) -> bool:
        """Enable single LED channel for P4PRO using lm: command.

        Turns on ONE LED channel while turning off all others.
        This is critical for sequential LED acquisition (live data).

        Args:
            ch: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            True if command succeeded
        """
        try:
            if self._ser is not None or self.open():
                # P4PRO firmware: lm:X command enables ONLY channel X
                # This automatically disables other channels
                ch_upper = ch.upper()
                cmd = f"lm:{ch_upper}\n"
                self._ser.write(cmd.encode())

                # Small delay for firmware to process and respond
                time.sleep(0.01)  # 10ms - firmware responds in <5ms

                # Read response - firmware responds with b'\x01' (byte 1) or b'1' (ASCII)
                # Use readline to get complete response
                resp = self._ser.readline().strip()

                # Check if response contains '1', 0x01, or 'b' (success indicators)
                if b'1' in resp or b'\x01' in resp or b'b' in resp:
                    return True

                # Empty response or unexpected response
                logger.warning(f"turn_on_channel({ch}) returned: {resp!r} (expected b'1', b'\\x01', or b'b')")
                return False
            return False
        except Exception as e:
            logger.error(f"Error turning on channel {ch}: {e}")
            return False

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels by setting all intensities to 0."""
        try:
            if self._ser is not None or self.open():
                # P4PRO: Set all LED intensities to 0 to turn off
                # Using sequential la:0 commands (lx command doesn't work reliably)
                for ch in ['a', 'b', 'c', 'd']:
                    cmd = f"l{ch}:0\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.005)  # Small delay between commands

                # Read responses
                time.sleep(0.01)
                if self._ser.in_waiting > 0:
                    self._ser.read(self._ser.in_waiting)  # Clear buffer

                return True
            return False
        except Exception as e:
            logger.error(f"Error turning off channels: {e}")
            return False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        """Set LED intensity for a single channel (0-255).

        NOTE: P4PRO firmware may not send acknowledgment responses for LED commands.
        Return True optimistically after sending command.
        """
        try:
            if raw_val < 0 or raw_val > 255:
                logger.error(f"Invalid intensity: {raw_val} (must be 0-255)")
                return False

            cmd = f"i{ch}{raw_val:03d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                # P4PRO firmware may not send acknowledgment - don't wait for response
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting intensity for channel {ch}: {e}")
            return False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        """Set all 4 LED intensities.

        P4PRO v2.2+: Uses atomic leds: command when all LEDs have same brightness (OEM calibration),
        or sequential la:X commands for different brightness levels.

        Atomic mode (same brightness): All LEDs turn on simultaneously
        Sequential mode (different): LEDs turn on one-by-one (~40ms total)

        NOTE: P4PRO firmware brightness control is non-linear. High values (50-255) appear
        similar, only very low values (~10) appear noticeably dimmer.

        Args:
            a, b, c, d: Intensities 0-255 for each channel

        Returns:
            True if command succeeded, False otherwise
        """
        try:
            # Clamp values to valid range
            a = max(0, min(255, int(a)))
            b = max(0, min(255, int(b)))
            c = max(0, min(255, int(c)))
            d = max(0, min(255, int(d)))

            if self._ser is not None or self.open():
                # Check if all non-zero values are equal (OEM calibration case)
                non_zero_values = [v for v in [a, b, c, d] if v > 0]
                all_same = len(set(non_zero_values)) <= 1 and len(non_zero_values) > 0

                if all_same and a == b == c == d and a > 0:
                    # All 4 LEDs same brightness - use atomic command for simultaneous turn-on
                    cmd = f"leds:A:{a},B:{b},C:{c},D:{d}\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.01)
                    resp = self._ser.readline().strip()

                    if resp != b'1':
                        logger.warning(f"leds atomic command failed: {resp!r}")
                        return False

                    logger.debug(f"P4PRO LED batch set (atomic): A={a} B={b} C={c} D={d}")
                else:
                    # Different brightness or partial LEDs - use sequential commands
                    for ch, val in [('a', a), ('b', b), ('c', c), ('d', d)]:
                        if val > 0:
                            cmd = f"l{ch}:{val}\n"
                            self._ser.write(cmd.encode())
                            time.sleep(0.01)
                            resp = self._ser.readline().strip()
                            if resp not in (b'1', b'\x01', b'b'):
                                logger.warning(f"l{ch}:{val} command failed: {resp!r}")

                    logger.debug(f"P4PRO LED batch set (sequential): A={a} B={b} C={c} D={d}")

                return True
            return False
        except Exception as e:
            logger.error(f"Error setting batch intensities: {e}")
            return False

    # ========================================================================
    # Servo Polarizer Control
    # ========================================================================

    def servo_move_raw_pwm(self, target_pwm):
        """Move servo using servo:ANGLE,DURATION format (RAM-only, no flash write).

        P4PRO firmware v2.0 supports servo:ANGLE,DURATION command that moves
        the servo directly without writing to EEPROM/flash.

        Args:
            target_pwm: PWM value 0-255 (converted to degrees 5-175)

        Returns:
            bool: True if successful
        """
        import time
        try:
            # Convert early — callers may pass string values from JSON config
            try:
                target_pwm = int(target_pwm)
            except (TypeError, ValueError) as conv_err:
                logger.error(f"servo_move_raw_pwm: invalid target_pwm {target_pwm!r}: {conv_err}")
                return False

            if target_pwm < 0 or target_pwm > 255:
                logger.error(f"Invalid PWM value: {target_pwm} (must be 0-255)")
                return False

            # Convert PWM (0-255) to degrees (5-175)
            degrees = int(5 + (target_pwm * 170 / 255))
            degrees = max(5, min(175, degrees))

            # P4PRO firmware v2.1: servo:ANGLE,DURATION format (no flash write)
            # CRITICAL: Firmware requires 500ms duration minimum for reliable response
            duration_ms = 500  # Minimum duration for stable operation
            cmd = f"servo:{degrees},{duration_ms}\n"

            if self._ser is not None or self.open():
                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.7)  # Wait for servo movement + response (500ms + 200ms margin)
                response = self._ser.readline().strip()  # Use readline for complete response

                # P4PRO v2.1 responds with b'\x01', b'1', b'B', b'b', or blank b'' (all valid)
                # Blank response means servo moved but firmware didn't acknowledge - this is normal
                if len(response) == 0 or b"\x01" in response or b"1" in response or b"B" in response or b"b" in response:
                    if len(response) == 0:
                        logger.debug(f"[P4PRO-SERVO] Move to {degrees}° (no response - servo moved)")
                    return True
                else:
                    logger.error(f"[P4PRO-SERVO] Move to {degrees}° failed: unexpected response={response!r}")
                    return False
            return False
        except Exception as e:
            logger.error(f"Error moving servo: {e}")
            return False
        except Exception as e:
            logger.error(f"Error moving servo: {e}")
            return False

    def servo_move_calibration_only(self, s=10, p=100):
        """Move servo for calibration purposes without writing to flash.

        This method is called by the calibration system. It uses the RAM-only
        servo:ANGLE,DURATION command (P4PRO firmware v2.1+).

        Args:
            s: S-mode target position (0-255 PWM, ignored - uses p for both)
            p: P-mode target position (0-255 PWM, calibration uses this)

        Returns:
            bool: True if movement successful
        """
        # Calibration system passes PWM values (0-255)
        # Use servo_move_raw_pwm() which handles the v2.1 command
        return self.servo_move_raw_pwm(target_pwm=p)

    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode (S or P) using device config PWM values directly.

        Uses servo:ANGLE,DURATION command (RAM-only, no EEPROM access).
        Device config PWM values are the source of truth.

        Args:
            mode: 'S' or 'P' (case insensitive)

        Returns:
            bool: True if successful
        """
        try:
            mode = mode.upper()
            if mode not in ('S', 'P'):
                logger.error(f"Invalid mode: {mode} (must be 'S' or 'P')")
                return False

            # Use stored PWM values from device config (set via set_servo_positions)
            if not hasattr(self, '_servo_s_pos') or not hasattr(self, '_servo_p_pos'):
                logger.error("Servo positions not loaded - call set_servo_positions() first")
                return False

            target_pwm = self._servo_s_pos if mode == 'S' else self._servo_p_pos

            logger.info(f"🔄 Setting P4PRO polarizer to {mode}-mode (PWM={target_pwm})")

            # Use direct PWM move (no EEPROM access)
            success = self.servo_move_raw_pwm(target_pwm)

            if success:
                logger.info(f"✅ Polarizer set to {mode}-mode")
                return True
            else:
                logger.error(f"[P4PRO-SERVO] Failed to set {mode}-mode")
                return False

        except Exception as e:
            logger.error(f"Error setting polarizer mode: {e}")
            return False

    def set_servo_positions(self, s: int, p: int):
        """Store servo S and P PWM positions for direct RAM-only moves.

        Device config values are stored in memory and used directly via
        servo:ANGLE,DURATION commands. No EEPROM/flash writes.

        Args:
            s: S-mode PWM position (0-255)
            p: P-mode PWM position (0-255)

        Returns:
            bool: True if positions stored successfully
        """
        try:
            # Validate PWM positions
            if not (0 <= s <= 255) or not (0 <= p <= 255):
                logger.error(f"Invalid servo PWM positions: S={s}, P={p} (must be 0-255)")
                return False

            # Store positions in memory (no flash write)
            self._servo_s_pos = s
            self._servo_p_pos = p
            logger.info(f"📍 Servo positions stored: S={s} PWM, P={p} PWM (device config source)")
            return True

        except Exception as e:
            logger.error(f"Error storing servo positions: {e}")
            return False

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to P4PRO controller EEPROM.

        P4PRO firmware v2.2 uses 'sv' command to store servo S/P positions in flash.
        This enables 'ss' and 'sp' commands to move to the stored positions.

        Args:
            config: Dict with keys like:
                - servo_s_position: PWM value 0-255 for S-mode
                - servo_p_position: PWM value 0-255 for P-mode

        Returns:
            True if EEPROM write successful, False otherwise
        """
        try:
            # Extract servo positions (in PWM units 0-255)
            s_pwm = config.get("servo_s_position", 10)
            p_pwm = config.get("servo_p_position", 100)

            # P4PROPLUS firmware stores PWM values (0-255) directly in EEPROM
            # DO NOT convert to degrees - firmware expects PWM values
            logger.info(f"📝 Writing servo config to P4PRO EEPROM: S={s_pwm} PWM, P={p_pwm} PWM (storing PWM values directly)")

            # Use existing set_servo_positions method which sends 'sv' command
            # For P4PROPLUS, this stores PWM values directly
            success = self.set_servo_positions(s=s_pwm, p=p_pwm)

            if success:
                logger.info("✅ P4PRO EEPROM config written successfully")
            else:
                logger.error("❌ P4PRO EEPROM config write FAILED")

            return success

        except Exception as e:
            logger.error(f"Error writing config to P4PRO EEPROM: {e}")
            return False

    # ========================================================================
    # KNX Valve Control (6-port and 3-way valves)
    # ========================================================================

    def _cancel_valve_timer(self, ch):
        """Cancel existing safety timer for valve channel."""
        with self._valve_six_lock:
            if self._valve_six_timers[ch] is not None:
                self._valve_six_timers[ch].cancel()
                self._valve_six_timers[ch] = None

    def _auto_shutoff_valve(self, ch):
        """Auto-shutoff callback for 6-port valve safety timeout."""
        logger.warning(f"⚠️ SAFETY TIMEOUT: 6-port valve {ch} auto-shutoff after {self.VALVE_SAFETY_TIMEOUT_SECONDS}s")
        try:
            if self._ser is not None or self.open():
                cmd = f"v6{ch}0\n"
                self._ser.write(cmd.encode())
                self._ser.read()
                self._valve_six_state[ch] = 0
                logger.info(f"✓ KC{ch} 6-port valve auto-closed (LOAD position)")
        except Exception as e:
            logger.error(f"Error during auto-shutoff for valve {ch}: {e}")
        finally:
            with self._valve_six_lock:
                self._valve_six_timers[ch] = None

    def knx_six(self, state, ch, timeout_seconds=None):
        """Control individual 6-port valve with optional safety timeout.

        Args:
            ch: Channel (1 or 2)
            state: 0=load, 1=inject
            timeout_seconds: Optional safety timeout (None = no timeout)
        """
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                # Accept b"1", b"\x01", b"b", or b"" (empty) as success
                success = response in (b"1", b"\x01", b"b", b"")

                # Track commanded state (what we TOLD the valve to do)
                old_state = self._valve_six_state.get(ch)
                if old_state is not None and old_state != state:
                    self._valve_six_cycles_session[ch] += 1
                    self._valve_six_cycles_lifetime[ch] += 1
                    self._save_valve_cycles()
                    logger.debug(f"6-port valve {ch}: session cycle {self._valve_six_cycles_session[ch]}, lifetime {self._valve_six_cycles_lifetime[ch]} ({old_state}→{state})")
                self._valve_six_state[ch] = state

                if not success:
                    logger.warning(f"KC{ch} 6-port valve command sent but firmware verification FAILED (response={response!r}) - expected b'1', b'\\x01', b'b', or b''")

                # Safety timer management (runs regardless of response verification)
                if state == 1:  # INJECT
                    if timeout_seconds is not None and timeout_seconds > 0:
                        with self._valve_six_lock:
                            if self._valve_six_timers[ch] is not None:
                                self._valve_six_timers[ch].cancel()
                            self._valve_six_timers[ch] = threading.Timer(
                                timeout_seconds,
                                self._auto_shutoff_valve,
                                args=[ch]
                            )
                            self._valve_six_timers[ch].daemon = True
                            self._valve_six_timers[ch].start()
                        logger.info(f"✓ KC{ch} 6-port valve → INJECT (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]}) [Timeout: {timeout_seconds}s]")
                    else:
                        self._cancel_valve_timer(ch)
                        logger.info(f"✓ KC{ch} 6-port valve → INJECT (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]})")
                else:  # LOAD
                    self._cancel_valve_timer(ch)
                    logger.info(f"✓ KC{ch} 6-port valve → LOAD (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling 6-port valve {ch}: {e}")
            return False

    def knx_six_both(self, state, timeout_seconds=None):
        """Control both 6-port valves simultaneously."""
        try:
            # Firmware uses channel '3' for both valves: v631=ON, v630=OFF
            cmd = f"v63{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                # Accept b"1", b"\x01", b"b", or b"" (empty) as success
                success = response in (b"1", b"\x01", b"b", b"")

                # Track commanded state for both channels
                for ch in [1, 2]:
                    old_state = self._valve_six_state.get(ch)
                    if old_state is not None and old_state != state:
                        self._valve_six_cycles_session[ch] += 1
                        self._valve_six_cycles_lifetime[ch] += 1
                        self._save_valve_cycles()
                        logger.debug(f"Valve 6-port CH{ch} cycles - session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]}")
                    self._valve_six_state[ch] = state

                if not success:
                    logger.warning(f"BOTH 6-port valves command sent but firmware verification FAILED (response={response!r}) - expected b'1', b'\\x01', b'b', or b''")

                # Handle timeout timers for both channels
                for ch in [1, 2]:
                    if state == 1 and timeout_seconds:
                        with self._valve_six_lock:
                            if self._valve_six_timers[ch] is not None:
                                self._valve_six_timers[ch].cancel()
                            self._valve_six_timers[ch] = threading.Timer(
                                timeout_seconds,
                                self._auto_shutoff_valve,
                                args=[ch]
                            )
                            self._valve_six_timers[ch].daemon = True
                            self._valve_six_timers[ch].start()
                    else:
                        self._cancel_valve_timer(ch)

                mode = "INJECT" if state == 1 else "LOAD"
                logger.info(f"✓ Both 6-port valves → {mode} (cycles: V1={self._valve_six_cycles_lifetime[1]}, V2={self._valve_six_cycles_lifetime[2]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling both 6-port valves: {e}")
            return False

    def knx_three(self, state, ch):
        """Control individual 3-way valve.

        Args:
            ch: Channel (1 or 2)
            state: 0=waste, 1=load
        """
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"

                # Track commanded state
                old_state = self._valve_three_state.get(ch)
                if old_state is not None and old_state != state:
                    self._valve_three_cycles_session[ch] += 1
                    self._valve_three_cycles_lifetime[ch] += 1
                    self._save_valve_cycles()
                    logger.debug(f"3-way valve {ch}: session cycle {self._valve_three_cycles_session[ch]}, lifetime {self._valve_three_cycles_lifetime[ch]} ({old_state}→{state})")
                self._valve_three_state[ch] = state

                if not success:
                    logger.warning(f"KC{ch} 3-way valve command sent but firmware verification FAILED (response={response})")
                else:
                    mode = "LOAD" if state == 1 else "WASTE"
                    logger.info(f"✓ KC{ch} 3-way valve → {mode} (session: {self._valve_three_cycles_session[ch]}, lifetime: {self._valve_three_cycles_lifetime[ch]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling 3-way valve {ch}: {e}")
            return False

    def knx_three_both(self, state):
        """Control both 3-way valves simultaneously."""
        try:
            # Firmware uses channel '3' for both valves: v331=ON, v330=OFF (NOT v3B!)
            cmd = f"v33{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"

                # Track commanded state for both valves
                for ch in [1, 2]:
                    old_state = self._valve_three_state.get(ch)
                    if old_state is not None and old_state != state:
                        self._valve_three_cycles_session[ch] += 1
                        self._valve_three_cycles_lifetime[ch] += 1
                        logger.debug(f"3-way valve {ch}: session cycle {self._valve_three_cycles_session[ch]}, lifetime {self._valve_three_cycles_lifetime[ch]} ({old_state}→{state})")
                    self._valve_three_state[ch] = state

                if not success:
                    logger.warning(f"BOTH 3-way valves command sent but firmware verification FAILED (response={response})")
                else:
                    self._save_valve_cycles()
                    mode = "LOAD" if state == 1 else "WASTE"
                    logger.info(f"✓ Both 3-way valves → {mode} (session: V1={self._valve_three_cycles_session[1]}, V2={self._valve_three_cycles_session[2]} | lifetime: V1={self._valve_three_cycles_lifetime[1]}, V2={self._valve_three_cycles_lifetime[2]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling both 3-way valves: {e}")
            return False

    def knx_six_state(self, ch):
        """Get current state of 6-port valve (0=load, 1=inject, None=unknown)."""
        return self._valve_six_state.get(ch)

    def knx_three_state(self, ch):
        """Get current state of 3-way valve (0=waste, 1=load, None=unknown)."""
        return self._valve_three_state.get(ch)

    def get_valve_cycles(self):
        """Get valve cycle counts (session + lifetime) for health monitoring."""
        return {
            "six_port_session": dict(self._valve_six_cycles_session),
            "three_way_session": dict(self._valve_three_cycles_session),
            "six_port_lifetime": dict(self._valve_six_cycles_lifetime),
            "three_way_lifetime": dict(self._valve_three_cycles_lifetime),
            "total_six_session": sum(self._valve_six_cycles_session.values()),
            "total_three_session": sum(self._valve_three_cycles_session.values()),
            "total_six_lifetime": sum(self._valve_six_cycles_lifetime.values()),
            "total_three_lifetime": sum(self._valve_three_cycles_lifetime.values()),
        }

    # ========================================================================
    # Internal Peristaltic Pump Control (P4PROPLUS V2.3+)
    # ========================================================================

    def has_internal_pumps(self) -> bool:
        """Check if this P4PRO has internal peristaltic pumps.

        P4PROPLUS (V2.3+) has integrated peristaltic pumps that can substitute
        for external AffiPump in many operations.

        Standard P4PRO (V2.1-V2.2) has valves only and requires external AffiPump.

        Returns:
            True if firmware version >= V2.3 (P4PROPLUS with internal pumps)
        """
        # Check firmware ID first
        if hasattr(self, 'firmware_id') and self.firmware_id:
            if 'p4proplus' in self.firmware_id.lower():
                logger.debug(f"P4PROPLUS detected via firmware ID: {self.firmware_id}")
                return True

        # Fall back to version check
        if not self.version:
            return False

        try:
            # Extract version number (V2.3 -> 2.3)
            version_str = self.version.replace('V', '').replace('v', '')
            version_float = float(version_str)

            # P4PROPLUS is V2.3+
            has_pumps = version_float >= 2.3

            if has_pumps:
                logger.debug(f"P4PROPLUS detected: {self.version} has internal peristaltic pumps")
            else:
                logger.debug(f"Standard P4PRO: {self.version} has valves only (needs external AffiPump)")

            return has_pumps

        except (ValueError, AttributeError) as e:
            logger.warning(f"Version parse error: {e}")
            return False

    def get_pump_capabilities(self) -> dict:
        """Get capability flags for P4PROPLUS internal pumps.

        Returns dict with capability flags for UI logic (greying out incompatible operations).
        Empty dict if no internal pumps available.
        """
        if not self.has_internal_pumps():
            return {}

        return {
            # Hardware type
            "type": "peristaltic",

            # Core capabilities
            "bidirectional": False,  # Forward flow only, no aspiration
            "has_homing": False,  # No position initialization
            "has_position_tracking": False,  # CRITICAL: No feedback loop!
            "supports_partial_loop": False,  # Needs aspiration (bidirectional)

            # Flow rate specs (user-facing, in uL/min)
            "max_flow_rate_ul_min": 300,
            "min_flow_rate_ul_min": 1,
            "supports_flow_rate_change": True,  # Can change on-the-fly

            # Calibration factor for uL/min to RPM conversion
            "ul_per_revolution": 3.0,  # Must be calibrated per installation

            # Firmware RPM limits
            "min_rpm": 5,
            "max_rpm": 300,

            # Reliability compensations
            "recommended_prime_cycles": 10,  # vs 6 for syringe pumps
            "requires_visual_verification": True,
            "suction_reliability_warning": (
                "Peristaltic pumps may fail to pick up sample at START of run.\n"
                "You MUST visually verify liquid in tubing during priming.\n"
                "Watch for air bubbles - they indicate suction failure."
            )
        }

    def _ul_min_to_rpm(self, rate_ul_min: float) -> int:
        """Convert flow rate from uL/min to RPM for peristaltic pump.

        Based on peristaltic pump tubing specifications.
        This conversion factor MUST be calibrated per installation.

        Args:
            rate_ul_min: Flow rate in uL/min

        Returns:
            RPM value (5-300 range, clamped to firmware limits)
        """
        caps = self.get_pump_capabilities()
        ul_per_rev = caps.get("ul_per_revolution", 3.0)

        # Convert uL/min to revolutions/min
        rpm = rate_ul_min / ul_per_rev

        # Clamp to firmware limits (5-300 RPM)
        min_rpm = caps.get("min_rpm", 5)
        max_rpm = caps.get("max_rpm", 300)
        rpm = max(min_rpm, min(max_rpm, int(rpm)))

        return rpm

    def pump_start(self, rate_ul_min: float, ch: int = 1) -> bool:
        """Start internal peristaltic pump at specified RPM.

        CRITICAL: P4PROPLUS firmware expects RPM (rotations per minute)!

        Command format: pr{ch}{rpm:04d}\n
        Examples:
            pr10050\n = Pump 1 at 50 RPM
            pr20100\n = Pump 2 at 100 RPM
            pr30075\n = Both pumps at 75 RPM

        Args:
            rate_ul_min: RPM value (parameter name kept for compatibility, but now expects RPM)
            ch: Pump channel (1, 2, or 3 for both)

        Returns:
            True if command sent successfully
        """
        if not self.has_internal_pumps():
            logger.error("No internal pumps available (P4PROPLUS V2.3+ required)")
            return False

        # Treat input as RPM directly (no conversion)
        rpm = int(round(rate_ul_min))

        # Validate RPM range (5-300 RPM per firmware limits)
        if rpm < 5 or rpm > 300:
            logger.error(f"RPM {rpm} out of range [5-300]")
            return False

        # Format command: pr{ch}{rpm:04d}\n
        # Firmware parses command[3:6] directly as rate (no offset subtraction)
        cmd = f"pr{ch}{rpm:04d}\n"

        logger.info(f"Internal pump {ch} start: {rpm} RPM -> {cmd.strip()}")

        try:
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                # CRITICAL: Firmware needs time to process pump commands
                # Without delay, rapid commands interfere and pump won't stop/change speed
                import time
                time.sleep(0.15)  # 150ms delay for firmware processing

                # P4PROPLUS firmware doesn't send response for pump commands
                # (unlike valve commands which send b"6")
                # Pump movement confirmed working even with empty response
                try:
                    response = self._ser.read(1)  # Try to read any response
                    if response:
                        logger.debug(f"Pump {ch} response: {response!r}")
                except Exception:
                    pass  # No response is OK for pump commands

                logger.debug(f"Pump {ch} started successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error starting pump {ch}: {e}")
            return False

    def pump_stop(self, ch: int = 1) -> bool:
        """Stop internal peristaltic pump.

        Command format: ps{ch}\n
        Examples:
            ps1\n = Stop pump 1
            ps2\n = Stop pump 2
            ps3\n = Stop both pumps

        Args:
            ch: Pump channel (1, 2, or 3 for both)

        Returns:
            True if command sent successfully and firmware responded with success (b"6")
        """
        if not self.has_internal_pumps():
            logger.error("No internal pumps available (P4PROPLUS V2.3+ required)")
            return False

        cmd = f"ps{ch}\n"

        logger.info(f"Internal pump {ch} stop: {cmd.strip()}")

        try:
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                # CRITICAL: Firmware needs time to process pump commands
                # Without delay, rapid commands interfere and pump won't stop/change speed
                import time
                time.sleep(0.15)  # 150ms delay for firmware processing

                # P4PROPLUS firmware doesn't send response for pump commands
                # (unlike valve commands which send b"6")
                # Pump movement confirmed working even with empty response
                try:
                    response = self._ser.read(1)  # Try to read any response
                    if response:
                        logger.debug(f"Pump {ch} response: {response!r}")
                except Exception:
                    pass  # No response is OK for pump commands

                logger.debug(f"Pump {ch} stopped successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping pump {ch}: {e}")
            return False

    def inject_internal_pump(self, volume_ul: float, flow_rate_ul_min: float, ch: int = 1) -> bool:
        """Perform simple injection using internal peristaltic pump.

        Since peristaltic pumps are unidirectional (forward flow only),
        this is a simple inject operation without aspiration/load phase.

        Args:
            volume_ul: Volume to inject in microliters
            flow_rate_ul_min: Flow rate in uL/min (1-300)
            ch: Pump channel (1, 2, or 3 for both)

        Returns:
            True if injection completed successfully

        Example:
            # Inject 100 uL at 150 uL/min using pump 1
            ctrl.inject_internal_pump(volume_ul=100, flow_rate_ul_min=150, ch=1)
        """
        if not self.has_internal_pumps():
            logger.error("No internal pumps available (P4PROPLUS V2.3+ required)")
            return False

        if volume_ul <= 0:
            logger.error(f"Invalid volume: {volume_ul} uL (must be > 0)")
            return False

        # Calculate injection duration
        duration_sec = (volume_ul / flow_rate_ul_min) * 60.0

        logger.info(f"Internal pump inject: {volume_ul} uL at {flow_rate_ul_min} uL/min (ch {ch})")
        logger.info(f"  Duration: {duration_sec:.2f} seconds")

        try:
            # Start pump
            if not self.pump_start(rate_ul_min=flow_rate_ul_min, ch=ch):
                logger.error("Failed to start pump for injection")
                return False

            # Wait for injection to complete
            import time
            time.sleep(duration_sec)

            # Stop pump
            if not self.pump_stop(ch=ch):
                logger.warning("Failed to stop pump after injection (pump may still be running!)")
                return False

            logger.info(f"Injection complete: {volume_ul} uL delivered")
            return True

        except Exception as e:
            logger.error(f"Error during injection: {e}")
            # Try to stop pump on error
            try:
                self.pump_stop(ch=ch)
            except Exception:
                pass
            return False

    def stop_kinetic(self) -> None:
        """Stop all kinetic operations (pumps and valves)."""
        try:
            cmds = ["ps3\n", "v330\n", "v630\n"]
            if self._ser is not None or self.open():
                for cmd in cmds:
                    self._ser.write(cmd.encode())
                    self._ser.read()
                logger.info("P4PRO kinetics stopped")
        except Exception as e:
            logger.error(f"Error stopping kinetics: {e}")

    def get_temp(self):
        """Get controller temperature."""
        try:
            if self._ser is not None or self.open():
                cmd = "it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                return float(temp)
        except Exception as e:
            logger.debug(f"Temperature not readable: {e}")
        return -1.0

    def __str__(self) -> str:
        return "Pico P4PRO Controller"
