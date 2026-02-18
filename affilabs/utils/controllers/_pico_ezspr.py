from __future__ import annotations

import builtins
import contextlib
import threading
import time
from pathlib import Path
from platform import system
from shutil import copy
from typing import Final

import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import PICO_PID, PICO_VID

from affilabs.utils.controllers._base import FlowController, CH_DICT
from affilabs.utils.controllers._valve_mixin import ValveCycleMixin

if system() == "Windows":
    import string


class PicoEZSPR(ValveCycleMixin, FlowController):
    """EZSPR/AFFINITE controller with 2 LEDs, pump control, and valve control.

    This class handles EZSPR and AFFINITE firmware variants only.
    P4PRO hardware uses the separate PicoP4PRO class.

    Hardware Features:
    - 2 LED channels (A, B) - no batch command support
    - Internal pump with flow rate control
    - 6-port valves (2 channels) with cycle tracking and safety timeout
    - 3-way valves (2 channels) with state monitoring

    Firmware: EZSPR V1.3+, AFFINITE V1.4+
    """

    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self) -> None:
        super().__init__(name="pico_ezspr")
        self._ser = None
        self.version = ""
        self.firmware_id = ""  # Track firmware ID (EZSPR or AFFINITE only)

        self._init_valve_tracking()
        self._load_valve_cycles()

    def valid(self):
        return (self._ser is not None and self._ser.is_open) or self.open()

    def open(self) -> bool:
        """Open Pico EZSPR controller - accepts EZSPR or AFFINITE firmware only.

        NOTE: P4PRO firmware is NOT handled by this class - use PicoP4PRO instead.
        """
        # Try VID/PID match first (preferred method)
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=5,
                        write_timeout=5,
                    )
                    cmd = "id\n"
                    self._ser.write(cmd.encode())
                    reply = self._ser.readline().decode().strip()
                    logger.debug(f"Pico EZSPR reply - {reply}")
                    # Accept EZSPR or AFFINITE firmware only (NOT P4PRO)
                    if reply in ("EZSPR", "AFFINITE") or "AFFINITE" in reply:
                        self.firmware_id = reply  # Store for command format selection
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        self.version = self._ser.readline()[0:4].decode()
                        logger.info(f"✅ Found Pico EZSPR/AFFINITE firmware: {reply} (version {self.version})")
                        return True
                    elif "P4PRO" in reply:
                        logger.debug("P4PRO firmware detected - skipping (use PicoP4PRO class)")
                    try:
                        self._ser.close()
                    except Exception as close_err:
                        logger.error(
                            f"Error closing port after ID mismatch: {close_err}",
                        )
                    finally:
                        self._ser = None
                except Exception as e:
                    logger.error(f"Failed to open Pico via VID/PID - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after exception: {close_err}",
                            )
                        finally:
                            self._ser = None

        # FALLBACK: Try all COM ports if VID/PID match failed
        logger.info("🔧 Pico EZSPR VID/PID match failed - trying all COM ports...")
        for dev in serial.tools.list_ports.comports():
            try:
                logger.debug(f"   Trying {dev.device}...")
                self._ser = serial.Serial(
                    port=dev.device,
                    baudrate=115200,
                    timeout=1,
                    write_timeout=2,
                )
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                cmd = "id\n"
                self._ser.write(cmd.encode())
                import time

                time.sleep(0.15)
                reply = self._ser.readline().decode().strip()

                # Accept EZSPR or AFFINITE firmware only (NOT P4PRO)
                if reply in ("EZSPR", "AFFINITE") or "AFFINITE" in reply:
                    self.firmware_id = reply  # Store for command format selection
                    logger.info(
                        f"[OK] Found Pico EZSPR/AFFINITE on {dev.device} (firmware: {reply}, fallback method)",
                    )
                    cmd = "iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.1)
                    self.version = self._ser.readline()[0:4].decode()
                    return True
                elif "P4PRO" in reply:
                    logger.debug("P4PRO firmware detected - skipping (use PicoP4PRO class)")
                    self._ser.close()
                    self._ser = None
                    continue
                self._ser.close()
                self._ser = None
            except Exception as e:
                logger.debug(f"   {dev.device} not a Pico EZSPR: {e}")
                if self._ser is not None:
                    with contextlib.suppress(builtins.BaseException):
                        self._ser.close()
                    self._ser = None

        return False

    def update_firmware(self, firmware) -> bool:
        if not (self.valid() and self.version in self.UPDATABLE_VERSIONS):
            return False

        self._ser.write(b"du\n")
        self.close()

        now = time.monotonic_ns()
        timeout = now + 5_000_000_000
        while now <= timeout:
            try:
                # Python 3.9-compatible drive enumeration
                drives = [
                    f"{letter}:/"
                    for letter in string.ascii_uppercase
                    if Path(f"{letter}:/").exists()
                ]
                pico_drive = next(
                    d for d in drives if (Path(d) / "INFO_UF2.TXT").exists()
                )
                break
            except StopIteration:
                time.sleep(0)
                now = time.monotonic_ns()
        else:
            return False

        copy(firmware, pico_drive)

        now = time.monotonic_ns()
        timeout = now + 5_000_000_000
        while now <= timeout:
            if self.open():
                return True
            time.sleep(0)
            now = time.monotonic_ns()

        return False

    def get_pump_corrections(self):
        if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
            return None
        self._ser.write(b"pc\n")
        reply = self._ser.readline()
        return tuple(x / self.PUMP_CORRECTION_MULTIPLIER for x in reply[:2])

    def set_pump_corrections(self, pump_1_correction, pump_2_correction) -> bool:
        if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
            return False
        corrections = pump_1_correction, pump_2_correction
        try:
            corrrection_bytes = bytes(
                round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections
            )
        except ValueError:
            return False
        self._ser.write(b"pf" + corrrection_bytes + b"\n")
        return True

    def turn_on_channel(self, ch="a"):
        try:
            if ch in {"a", "b", "c", "d"}:
                cmd = f"l{ch}\n"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"6"
            elif ch not in {"a", "b", "c", "d"}:
                msg = "Invalid Channel!"
                raise ValueError(msg)
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def turn_off_channels(self) -> bool | None:
        """Turn off all LED channels.

        Uses lx command which is universally supported by all firmware versions.
        For more reliable zero intensity, use set_batch_intensities(0,0,0,0) instead.
        """
        try:
            if self._ser is not None or self.open():
                # Use lx command - universally supported across firmware versions
                cmd = "lx\n"
                self._ser.write(cmd.encode())
                time.sleep(0.02)
                logger.debug("  All LED channels turned OFF via lx command")
                return True
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def set_intensity(self, ch="a", raw_val=1):
        try:
            if ch in {"a", "b", "c", "d"}:
                # error bounding: P4SPR LED intensity range is 0-255
                if raw_val > 255:
                    logger.debug(f"Invalid Intensity value - {raw_val}")
                    raw_val = 255
                elif raw_val < 0:
                    logger.debug(f"Invalid Intensity value - {raw_val}")
                    raw_val = 0

                cmd = f"b{ch}{int(raw_val):03d}\n"
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if self._ser is None and not self.open():
                            logger.error(f"pico failed to open port for LED {ch}")
                            return False
                        try:
                            self._ser.reset_output_buffer()
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)
                        reply = self._ser.read() == b"6"
                        self.turn_on_channel(ch=ch)
                        return reply
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.debug(
                                f"LED write timeout (EZSPR ch {ch}, attempt {attempt + 1}/{max_retries}): {e}",
                            )
                            time.sleep(0.05)
                            continue
                        logger.error(f"error while setting led intensity {e}")
                        return False
                return False
            if ch not in {"a", "b", "c", "d"}:
                msg = f"Invalid Channel - {ch}"
                raise ValueError(msg)
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0) -> bool | None:
        """Set all LED intensities in a single batch command.

        This method uses the Pico's batch command format to set all 4 LED
        intensities simultaneously, providing ~15x speedup over sequential
        individual commands.

        Args:
            a: Intensity for LED A (0-255)
            b: Intensity for LED B (0-255)
            c: Intensity for LED C (0-255)
            d: Intensity for LED D (0-255)

        Returns:
            bool: True if command succeeded, False otherwise

        Example:
            # Turn on LED A at full brightness, others off
            controller.set_batch_intensities(a=255, b=0, c=0, d=0)

            # Set custom pattern
            controller.set_batch_intensities(a=128, b=64, c=192, d=255)

        Performance:
            Sequential commands: ~12ms for 4 LEDs
            Batch command: ~0.8ms for 4 LEDs
            Speedup: 15x faster

        """
        try:
            # Clamp values to valid range (0-255)
            a = max(0, min(255, int(a)))
            b = max(0, min(255, int(b)))
            c = max(0, min(255, int(c)))
            d = max(0, min(255, int(d)))

            # CRITICAL: Enable LED channels before setting intensity (EZSPR)
            # The Pico firmware requires channels to be turned ON before they respond to intensity commands
            for ch, intensity in [("a", a), ("b", b), ("c", c), ("d", d)]:
                if intensity > 0:  # Only enable channels that will be used
                    self.turn_on_channel(ch=ch)

            # Format: batch:A,B,C,D\n
            cmd = f"batch:{a},{b},{c},{d}\n"

            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                time.sleep(0.02)  # Small delay for processing
                # Batch command executes successfully even with minimal response
                logger.debug(f"Batch LED command sent: {cmd.strip()}")
                return True
            logger.error("pico serial port not valid for batch command")
            return False

        except Exception as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            return False

    def set_mode(self, mode="s"):
        """Set polarizer mode for P4PRO using servo:ANGLE,DURATION format.

        P4PRO firmware v2.0 uses servo:ANGLE,DURATION instead of ss/sp commands.
        Requires servo positions to be loaded via set_servo_positions() first.
        """
        import time

        try:
            if self._ser is not None or self.open():
                # Check if servo positions are loaded
                if self._servo_s_pos is None or self._servo_p_pos is None:
                    logger.error("❌ Servo positions not loaded - cannot set polarizer mode")
                    logger.error("   Call set_servo_positions(s, p) before set_mode()")
                    return False

                # Select target angle based on mode
                target_angle = self._servo_s_pos if mode == "s" else self._servo_p_pos
                duration_ms = 150  # Fast servo movement duration (was 500ms)

                # P4PRO uses servo:ANGLE,DURATION format
                cmd = f"servo:{target_angle},{duration_ms}\n"
                logger.info(f"🔄 Setting P4PRO polarizer to {mode.upper()}-mode (angle {target_angle}°)")

                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.05)

                response = self._ser.read(10)

                # P4PRO v2.0 responds with b'\x01\r\n' or b'1\r\n'
                if len(response) > 0 and (b"\x01" in response or b"1" in response or b"6" in response):
                    logger.info(f"✅ Polarizer set to {mode.upper()}-mode")
                    # Wait for servo to physically move (reduced from 0.7s)
                    time.sleep(0.25)
                    return True
                else:
                    logger.error(f"❌ Failed to set mode: unexpected response {response!r}")
                    return False

        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def set_servo_positions(self, s: int, p: int):
        """Load servo S and P positions (degrees) for use by set_mode().

        Args:
            s: S-mode angle in degrees (5-175)
            p: P-mode angle in degrees (5-175)
        """
        self._servo_s_pos = s
        self._servo_p_pos = p
        logger.info(f"📌 Servo positions loaded: S={s}°, P={p}°")

    def servo_get(self):
        cmd = "sr\n"
        curr_pos = {"s": b"0000", "p": b"0000"}
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if self._ser is not None or self.open():
                    import time

                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.15)  # Increased wait time for Pico to respond

                    servo_reading = self._ser.readline()
                    logger.debug(
                        f"servo reading pico {servo_reading} (attempt {attempt + 1}/{max_retries})",
                    )

                    # If response is just "6\r\n" (ACK), read again for actual positions
                    if servo_reading.strip() == b"6":
                        time.sleep(0.05)
                        servo_reading = self._ser.readline()
                        logger.debug(
                            f"servo reading pico (second read) {servo_reading}",
                        )

                    # Parse comma-separated format: "s,p\r\n"
                    try:
                        response_str = servo_reading.decode("utf-8").strip()
                        if not response_str:
                            logger.warning(
                                f"Empty servo response on attempt {attempt + 1} - servo may not be initialized",
                            )
                            if attempt < max_retries - 1:
                                time.sleep(0.2)
                                continue
                            return curr_pos

                        if "," in response_str:
                            parts = response_str.split(",")
                            if len(parts) == 2:
                                # Validate that parts contain numeric values
                                try:
                                    s_val = int(parts[0])
                                    p_val = int(parts[1])
                                    curr_pos["s"] = parts[0].encode()
                                    curr_pos["p"] = parts[1].encode()
                                    logger.debug(
                                        f"Servo s, p: {curr_pos} (parsed as {s_val}, {p_val})",
                                    )
                                    return curr_pos  # Success - return immediately
                                except ValueError as ve:
                                    logger.warning(
                                        f"Non-numeric servo values: {parts} - {ve}",
                                    )
                                    if attempt < max_retries - 1:
                                        time.sleep(0.2)
                                        continue
                            else:
                                logger.warning(
                                    f"Invalid servo response format (expected 2 parts): {servo_reading}",
                                )
                                if attempt < max_retries - 1:
                                    time.sleep(0.2)
                                    continue
                        else:
                            logger.warning(
                                f"Invalid servo response (no comma): {servo_reading}",
                            )
                            if attempt < max_retries - 1:
                                time.sleep(0.2)
                                continue
                    except Exception as parse_error:
                        logger.warning(
                            f"Error parsing servo response {servo_reading}: {parse_error}",
                        )
                        if attempt < max_retries - 1:
                            time.sleep(0.2)
                            continue
                else:
                    logger.error("serial communication failed - servo get")
                    if attempt < max_retries - 1:
                        time.sleep(0.2)
                        continue
            except Exception as e:
                logger.debug(f"error getting servo pos on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue

        return curr_pos

    def servo_move_raw_pwm(self, target_pwm):
        """Move servo to a specific PWM position (for calibration).

        Uses sv command for FAST calibration moves (no EEPROM writes).
        The servo:ANGLE,DURATION command writes to flash (~5s delay) - NOT suitable for calibration!

        Args:
            target_pwm: PWM value 0-255

        Returns:
            bool: True if successful, False otherwise
        """
        import time

        try:
            if target_pwm < 0 or target_pwm > 255:
                logger.error(f"Invalid PWM value: {target_pwm} (must be 0-255)")
                return False

            # P4PRO/EZSPR firmware uses sv command for RAM-only moves (no flash write)
            # Format: sv{s:03d}{p:03d}\n where both s and p are the same for calibration sweep
            # PWM range: 0-255
            pwm_val = int(target_pwm)

            # Use sv command (RAM only, no EEPROM write, <100ms response)
            cmd = f"sv{pwm_val:03d}{pwm_val:03d}\n"
            logger.debug(f"🔧 SERVO CALIB: {cmd.strip()} (PWM {target_pwm})")

            if self._ser is not None or self.open():
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass

                # Send servo command
                self._ser.write(cmd.encode())
                time.sleep(0.05)  # Wait for firmware to process

                # Read response - sv command responds quickly with b'6'
                response = self._ser.read(1)

                if response == b"6":
                    logger.debug(f"✅ Servo PWM {target_pwm} set (fast sv command)")
                    time.sleep(0.1)  # Minimal servo movement delay
                    return True
                else:
                    logger.warning(f"⚠️ Unexpected servo response: {response!r}")
                    time.sleep(0.1)
                    return True  # Continue anyway - servo likely moved

            logger.error("❌ Serial port not open")
            return False

            logger.error("❌ Serial port not open")
            return False

        except Exception as e:
            logger.error(f"❌ EXCEPTION in servo_move_raw_pwm: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def servo_set(self, s=10, p=100):
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                    msg = f"Invalid polarizer position given: {s}, {p}"
                    raise ValueError(msg)

                # All Pico-based firmware (EZSPR, P4PRO, AFFINITE) use sv format
                # Format: sv{s:03d}{p:03d}\n where values are 0-255 PWM or 0-180 degrees
                cmd = f"sv{s:03d}{p:03d}\n"
                logger.info(f"🔧 Sending servo command to {self.firmware_id}: {cmd.strip()} (s={s}, p={p})")

                if self._ser is not None or self.open():
                    # Clear input buffer before sending command
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    self._ser.write(cmd.encode())
                    time.sleep(0.05)  # Give firmware time to process

                    # Read response - firmware sends ACK ('6')
                    response = self._ser.read(1)
                    logger.debug(f"Servo response: {response!r}")

                    success = response == b"6"
                    if success:
                        logger.info(f"✅ Servo positions set successfully: s={s}, p={p}")
                    else:
                        logger.warning(f"⚠️ Unexpected servo response: {response!r} (expected b'6')")

                    return success
                logger.error("unable to update servo positions - port not open")
                return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Servo write timeout (attempt {attempt + 1}/{max_retries}), retrying...",
                    )
                    continue
                logger.warning(f"Servo write failed after {max_retries} attempts: {e}")
                return False
        return False

    def flash(self):
        try:
            flash_cmd = "sf\n"
            if self._ser is not None or self.open():
                self._ser.write(flash_cmd.encode())
                return self._ser.read() == b"6"
            return False
        except Exception as e:
            logger.debug(f"error flashing pico {e}")
            return False

    def stop(self) -> None:
        self.turn_off_channels()

    def get_status(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                cmd = "it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception as e:
            logger.debug(f"temp value not readable {e}")
        return temp

    def knx_status(self, ch):
        status = {"flow": 0, "temp": 0, "6P": 0, "3W": 0}
        try:
            cmd = f"ks{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                data = self._ser.readline().decode()[0:-2]
                data = data.split(",")
                if len(data) > 3:
                    status["flow"] = float(data[0])
                    status["temp"] = float(data[1])
                    status["3W"] = float(data[2])
                    status["6P"] = float(data[3])
            else:
                logger.error("failed to send cmd knx_status")
            return status
        except Exception as e:
            logger.error(f"Error during knx_status {e}")

    def knx_stop(self, ch) -> bool | None:
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"6":
                    return True
            else:
                logger.error("failed to send cmd knx_stop")
            return False
        except Exception as e:
            logger.error(f"Error during knx_stop {e}")

    def knx_start(self, rate, ch):
        try:
            if (c := self.get_pump_corrections()) is not None:
                if str(ch) == "1":
                    rate *= c[0]
                elif str(ch) == "2":
                    rate *= c[1]
                elif str(ch) == "3" and c[0] == c[1]:
                    rate *= c[0]
                elif str(ch) == "3":
                    self._ser.write(f"pr1{round(rate * c[0]):3d}\n".encode())
                    self._ser.write(f"pr2{round(rate * c[1]):3d}\n".encode())
                    return self._ser.read(2) == b"11"
            cmd = f"pr{ch}{round(rate):3d}\n"
            if self.valid():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"6":
                    return True
            else:
                logger.error("failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")

    def knx_three(self, state, ch):
        """Control individual 3-way valve.

        Args:
            state: 0=waste, 1=load
            ch: Channel (1 or 2)

        Returns:
            bool: True if successful
        """
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"  # P4PRO firmware returns '1' for success

                # Track commanded state (what we TOLD the valve to do)
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
                    state_name = "LOAD" if state == 1 else "WASTE"
                    logger.info(f"✓ KC{ch} 3-way valve → {state_name} (session: {self._valve_three_cycles_session[ch]}, lifetime: {self._valve_three_cycles_lifetime[ch]})")

                return success
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")
            return False

    def _cancel_valve_timer(self, ch):
        """Cancel existing safety timer for valve channel."""
        with self._valve_six_lock:
            if self._valve_six_timers[ch] is not None:
                self._valve_six_timers[ch].cancel()
                self._valve_six_timers[ch] = None
                logger.debug(f"Cancelled safety timer for 6-port valve {ch}")

    def _auto_shutoff_valve(self, ch):
        """Auto-shutoff callback for 6-port valve safety timeout."""
        logger.warning(f"⚠️ SAFETY TIMEOUT: 6-port valve {ch} auto-shutoff after {self.VALVE_SAFETY_TIMEOUT_SECONDS}s")
        try:
            if self._ser is not None or self.open():
                cmd = f"v6{ch}0\n"  # Force to LOAD position (state=0)
                self._ser.write(cmd.encode())
                self._ser.read()
                self._valve_six_state[ch] = 0
                logger.info(f"✓ KC{ch} 6-port valve auto-closed (LOAD position)")
        except Exception as e:
            logger.error(f"Error during auto-shutoff for valve {ch}: {e}")
        finally:
            with self._valve_six_lock:
                self._valve_six_timers[ch] = None

    def _start_valve_safety_timer(self, ch):
        """Start 5-minute safety timer for valve channel."""
        with self._valve_six_lock:
            # Cancel any existing timer
            if self._valve_six_timers[ch] is not None:
                self._valve_six_timers[ch].cancel()
            # Start new timer
            self._valve_six_timers[ch] = threading.Timer(
                self.VALVE_SAFETY_TIMEOUT_SECONDS,
                self._auto_shutoff_valve,
                args=[ch]
            )
            self._valve_six_timers[ch].daemon = True
            self._valve_six_timers[ch].start()
            logger.debug(f"Started {self.VALVE_SAFETY_TIMEOUT_SECONDS}s safety timer for 6-port valve {ch}")

    def knx_six(self, state, ch, timeout_seconds=None):
        """Control individual 6-port valve with optional timeout.

        Args:
            ch: Channel (1 or 2)
            state: 0=load, 1=inject
            timeout_seconds: Optional timeout in seconds for safety fallback.
                           - If None (default): NO automatic timeout - valve stays open
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations
                           - Pass explicitly for manual valve control without calculated contact time
        """
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"  # P4PRO firmware returns '1' for success

                if success:
                    # Track state change and cycle count
                    old_state = self._valve_six_state.get(ch)
                    if old_state is not None and old_state != state:
                        self._valve_six_cycles_session[ch] += 1
                        self._valve_six_cycles_lifetime[ch] += 1
                        self._save_valve_cycles()
                        logger.debug(f"6-port valve {ch}: session cycle {self._valve_six_cycles_session[ch]}, lifetime {self._valve_six_cycles_lifetime[ch]} ({old_state}→{state})")
                    self._valve_six_state[ch] = state

                    # Safety timer management
                    if state == 1:  # Valve turned ON (INJECT position)
                        if timeout_seconds is not None and timeout_seconds > 0:
                            # Safety timeout specified (for manual/unknown operations)
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
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]}) [Safety timeout: {timeout_seconds}s]")
                        else:
                            # No timeout - programmatic operation with calculated contact time
                            self._cancel_valve_timer(ch)
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]})")
                    else:  # Valve turned OFF (LOAD position)
                        self._cancel_valve_timer(ch)
                        logger.info(f"✓ KC{ch} 6-port valve → LOAD (session: {self._valve_six_cycles_session[ch]}, lifetime: {self._valve_six_cycles_lifetime[ch]})")

                return success
            logger.error("failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")
            return False

    def knx_six_both(self, state, timeout_seconds=None):
        """Set both 6-port valves simultaneously to same state with optional timeout.

        Args:
            state: 0=load, 1=inject
            timeout_seconds: Optional timeout in seconds for safety fallback.
                           - If None (default): NO automatic timeout - valves stay open
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations
                           - Pass explicitly for manual valve control without calculated contact time

        Returns:
            True if both valves acknowledged, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                # Send both commands back-to-back
                self._ser.write(f"v61{state:1d}\n".encode())
                resp1 = self._ser.read()
                logger.info(f"DEBUG knx_six_both: v61{state} sent, response: {resp1}")
                self._ser.write(f"v62{state:1d}\n".encode())
                resp2 = self._ser.read()
                logger.info(f"DEBUG knx_six_both: v62{state} sent, response: {resp2}")
                success = resp1 == b"1" and resp2 == b"1"

                if not success:
                    logger.warning(f"⚠️ 6-port valve command partial failure: v61 resp={resp1}, v62 resp={resp2}")

                if success:
                    # Track state changes and cycles for both valves
                    for ch in [1, 2]:
                        old_state = self._valve_six_state.get(ch)
                        if old_state is not None and old_state != state:
                            self._valve_six_cycles_session[ch] += 1
                            self._valve_six_cycles_lifetime[ch] += 1
                            logger.debug(f"6-port valve {ch}: session cycle {self._valve_six_cycles_session[ch]}, lifetime {self._valve_six_cycles_lifetime[ch]} ({old_state}→{state})")
                        self._valve_six_state[ch] = state

                    # Safety timer management for both valves
                    if state == 1:  # Valves turned ON (INJECT position)
                        if timeout_seconds is not None and timeout_seconds > 0:
                            # Safety timeout specified (for manual/unknown operations)
                            for ch in [1, 2]:
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
                            self._save_valve_cycles()
                            logger.info(f"✓ 6-port valves both set to INJECT (session: V1={self._valve_six_cycles_session[1]}, V2={self._valve_six_cycles_session[2]} | lifetime: V1={self._valve_six_cycles_lifetime[1]}, V2={self._valve_six_cycles_lifetime[2]}) [Safety timeout: {timeout_seconds}s]")
                        else:
                            # No timeout - programmatic operation with calculated contact time
                            for ch in [1, 2]:
                                self._cancel_valve_timer(ch)
                            self._save_valve_cycles()
                            logger.info(f"✓ 6-port valves both set to INJECT (session: V1={self._valve_six_cycles_session[1]}, V2={self._valve_six_cycles_session[2]} | lifetime: V1={self._valve_six_cycles_lifetime[1]}, V2={self._valve_six_cycles_lifetime[2]})")
                    else:  # Valves turned OFF (LOAD position)
                        for ch in [1, 2]:
                            self._cancel_valve_timer(ch)
                        self._save_valve_cycles()
                        logger.info(f"✓ 6-port valves both set to LOAD (session: V1={self._valve_six_cycles_session[1]}, V2={self._valve_six_cycles_session[2]} | lifetime: V1={self._valve_six_cycles_lifetime[1]}, V2={self._valve_six_cycles_lifetime[2]})")

                return success
            logger.error("knx_six_both failed: serial port not available (self._ser is None)")
            return False
        except Exception as e:
            logger.error(f"knx_six_both EXCEPTION: {e}", exc_info=True)
            return False

    def knx_three_both(self, state):
        """Set both 3-way valves simultaneously to same state.

        Args:
            state: 0=waste, 1=load

        Returns:
            True if both valves acknowledged, False otherwise
        """
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
                    logger.warning(f"BOTH 3-way valves command sent but firmware verification FAILED (resp1={resp1}, resp2={resp2})")
                else:
                    self._save_valve_cycles()
                    logger.info(f"✓ 3-way valves both set to {'LOAD' if state == 1 else 'WASTE'} (session: V1={self._valve_three_cycles_session[1]}, V2={self._valve_three_cycles_session[2]} | lifetime: V1={self._valve_three_cycles_lifetime[1]}, V2={self._valve_three_cycles_lifetime[2]})")

                return success
            logger.error("failed to send cmd knx_three_both")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three_both {e}")
            return False

    def knx_led(self, led_state, ch) -> None:
        pass  # Green indicator LED for each ch controlled in FW

    def knx_six_state(self, ch):
        """Get current state of 6-port valve.

        Args:
            ch: Valve channel (1 or 2)

        Returns:
            0 (load), 1 (inject), or None if unknown
        """
        return self._valve_six_state.get(ch)

    def knx_three_state(self, ch):
        """Get current state of 3-way valve.

        Args:
            ch: Valve channel (1 or 2)

        Returns:
            0 (waste), 1 (load), or None if unknown
        """
        return self._valve_three_state.get(ch)

    def get_valve_cycles(self):
        """Get valve cycle counts (session + lifetime) for health monitoring.

        Returns:
            dict with cycle counts for all valves
        """
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

    def stop_kinetic(self) -> None:
        try:
            cmds = ["ps3\n", "v330\n", "v630\n"]
            if self._ser is not None or self.open():
                er = False
                for cmd in cmds:
                    self._ser.write(cmd.encode())
                    if self._ser.read() != b"1":
                        er = True
                if er:
                    logger.error("pico failed to confirm kinetics off")
            else:
                logger.error("pico failed to turn kinetics off")
        except Exception as e:
            logger.error(f"error while shutting down kinetics {e}")

    def shutdown(self) -> None:
        try:
            cmd = "do\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() != b"1":
                    logger.error("pico failed to confirm device off")
            else:
                logger.error("pico failed to turn device off")
        except Exception as e:
            logger.error(f"error while shutting down device {e}")

    def get_info(self):
        return self.name

    def get_temp(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                cmd = "it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception as e:
            temp = -1
            logger.debug(f"temp value not readable {e}")
        return temp

    def __str__(self) -> str:
        return "Pico Carrier Board"

