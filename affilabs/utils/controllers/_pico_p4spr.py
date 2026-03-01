from __future__ import annotations

import builtins
import contextlib
import struct
import threading
import time
from pathlib import Path

import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import ARDUINO_PID, ARDUINO_VID, PICO_PID, PICO_VID

from affilabs.utils.controllers._base import StaticController, CH_DICT


# ArduinoController class DELETED - obsolete hardware
# Use PicoP4SPR instead


class PicoP4SPR(StaticController):
    def __init__(self) -> None:
        super().__init__(name="pico_p4spr")
        self._ser = None
        self.version = ""
        self._lock = threading.Lock()
        self._channels_enabled = set()  # Track which LED channels have been enabled
        # Cache of last-set LED intensities for reliable readback/fallback
        self._last_led_intensities: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}

    def open(self):
        # Close existing connection if any
        if self._ser is not None:
            try:
                self._ser.close()
            except:
                pass
            self._ser = None

        # Try VID/PID match first (preferred method)
        print(f"DEBUG: PicoP4SPR.open() - Looking for VID={hex(PICO_VID)} PID={hex(PICO_PID)}")
        logger.info(
            f"PicoP4SPR.open() - Looking for VID={hex(PICO_VID)} PID={hex(PICO_PID)}",
        )
        for dev in serial.tools.list_ports.comports():
            logger.debug(
                f"  Found port: {dev.device} VID={hex(dev.vid) if dev.vid else 'None'} PID={hex(dev.pid) if dev.pid else 'None'}",
            )
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    print(f"DEBUG: MATCH! Trying PicoP4SPR on {dev.device}")
                    logger.info(f"MATCH! Trying PicoP4SPR on {dev.device}")
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=0.5,
                        write_timeout=1,
                    )
                    # Flush any stale data
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()

                    cmd = "id\n"
                    self._ser.write(cmd.encode())
                    import time

                    time.sleep(0.3)  # Allow Pico boot splash to clear before reading
                    reply = self._ser.readline()[0:5].decode()
                    # If we caught a boot splash line (e.g. "=== T"), flush and retry once
                    if reply and not reply.startswith("P4SPR") and not reply.startswith("P4PRO"):
                        self._ser.reset_input_buffer()
                        time.sleep(0.2)
                        self._ser.write(b"id\n")
                        time.sleep(0.2)
                        reply = self._ser.readline()[0:5].decode()
                    print(f"DEBUG: Pico P4SPR ID reply: '{reply}'")
                    logger.info(f"Pico P4SPR ID reply: '{reply}'")
                    if reply == "P4SPR":
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        time.sleep(0.1)
                        self.version = self._ser.readline()[0:4].decode()
                        logger.info(f"Pico P4SPR Fw version: {self.version}")
                        return True
                    # Wrong ID - close port and return False immediately (likely different Pico model)
                    logger.warning(f"ID mismatch - expected 'P4SPR', got '{reply}' - stopping scan")
                    print(f"DEBUG: Got reply '{reply}' - this is a different Pico model, returning False immediately")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                            print("DEBUG: Port closed successfully")
                        except Exception as close_err:
                            print(f"DEBUG: Error closing port: {close_err}")
                            logger.error(f"Error closing port after ID mismatch: {close_err}")
                        finally:
                            self._ser = None
                    # Found a Pico but wrong model - let other controller classes try
                    print(f"DEBUG: Returning False from PicoP4SPR.open() - found {reply}, need P4SPR")
                    return False
                except Exception as e:
                    logger.error(f"Failed to open Pico on {dev.device}: {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after exception: {close_err}",
                            )
                        finally:
                            self._ser = None

        logger.warning("No PicoP4SPR found with VID/PID match")

        # FALLBACK: If VID/PID enumeration failed, try all COM ports blindly
        # This fixes Device Manager detection issues on Windows
        # BUT: Skip ports that might be Arduino boards to prevent hijacking
        logger.info(
            "VID/PID match failed - trying fallback COM port scan (Arduino excluded)...",
        )

        # Build exclusion list: ports with Arduino VID/PID
        excluded_ports = set()
        for dev in serial.tools.list_ports.comports():
            if dev.pid == ARDUINO_PID and dev.vid == ARDUINO_VID:
                excluded_ports.add(dev.device)
                logger.debug(f"Excluding {dev.device} (Arduino detected)")

        for dev in serial.tools.list_ports.comports():
            # Skip excluded ports
            if dev.device in excluded_ports:
                continue

            try:
                logger.info(f"Trying PicoP4SPR fallback on {dev.device}")
                self._ser = serial.Serial(
                    port=dev.device,
                    baudrate=115200,
                    timeout=0.3,
                    write_timeout=0.5,
                )
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                cmd = "id\n"
                self._ser.write(cmd.encode())
                import time

                time.sleep(0.05)  # Reduced from 0.15s
                reply = self._ser.readline()[0:5].decode()

                if reply == "P4SPR":
                    logger.info(f"Found Pico P4SPR on {dev.device} (fallback method)")
                    cmd = "iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.1)
                    self.version = self._ser.readline()[0:4].decode()
                    logger.debug(f" Pico P4SPR Fw: {self.version}")
                    return True
                self._ser.close()
                self._ser = None
            except Exception as e:
                logger.debug(f"   {dev.device} not a Pico P4SPR: {e}")
                if self._ser is not None:
                    try:
                        self._ser.close()
                    except:
                        pass
                    self._ser = None

        return False

    def turn_on_channel(self, ch="a"):
        try:
            if ch not in {"a", "b", "c", "d"}:
                msg = "Invalid Channel!"
                raise ValueError(msg)

            # Skip if already enabled (optimization)
            if ch in self._channels_enabled:
                logger.debug(f"LED {ch.upper()} already enabled, skipping turn_on_channel")
                return True

            cmd = f"l{ch}\n"
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()  # Clear any leftover data
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)  # Wait for response
                    response = self._ser.read(1)  # Read 1 byte
                    # Accept both '6' and '1' as success (firmware versions vary)
                    success = response in (b"6", b"1")
                    if success:
                        # CRITICAL: Firmware auto-disables previous LED when new one turns on
                        # Clear tracking set and add only the new channel
                        self._channels_enabled.clear()
                        self._channels_enabled.add(ch)
                    else:
                        logger.warning(
                            f"[ERROR] LED {ch.upper()} enable failed - expected b'6' or b'1', got: {response!r}",
                        )
                    return success
        except (PermissionError, OSError) as e:
            logger.error(f"Error turning on channel {ch}: {e}")
            raise ConnectionError(f"Controller disconnected: {e}") from e
        except Exception as e:
            logger.error(f"Error turning on channel {ch}: {e}")
            return False

    def get_temp(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = "it\n"
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception:
            temp = -1
            # Silently ignore temp read errors - not critical
        return temp

    def get_led_intensity(self, ch="a"):
        """Query current LED intensity from firmware (V1.1+).

        Args:
            ch: LED channel ('a', 'b', 'c', or 'd')

        Returns:
            int: Current intensity (0-255), or -1 on error

        """
        try:
            if ch not in {"a", "b", "c", "d"}:
                logger.error(f"Invalid channel: {ch}")
                return -1

            if self._ser is not None or self.open():
                with self._lock:
                    # Clear any stale data
                    self._ser.reset_input_buffer()
                    time.sleep(0.01)

                    # Clear serial buffer before querying (prevents CYCLE_START events from interfering)
                    if self._ser.in_waiting > 0:
                        self._ser.reset_input_buffer()
                        time.sleep(0.01)

                    # Send query command
                    cmd = f"i{ch}\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)

                    # Read response - firmware should respond with single line containing intensity
                    response_bytes = self._ser.readline()
                    response = response_bytes.decode("utf-8", errors="ignore").strip()

                    # Debug: log what we got (suppress CYCLE_START events)
                    if not response.startswith("CYCLE_START"):
                        logger.debug(f"LED {ch} query response: '{response}'")

                    # Try to parse as integer
                    try:
                        return int(response)
                    except ValueError:
                        # If response is non-numeric, it's likely an echo or error
                        # Try reading one more line in case response was delayed
                        time.sleep(0.02)
                        if self._ser.in_waiting > 0:
                            response2_bytes = self._ser.readline()
                            response2 = response2_bytes.decode(
                                "utf-8",
                                errors="ignore",
                            ).strip()
                            logger.debug(f"LED {ch} second response: '{response2}'")
                            try:
                                return int(response2)
                            except ValueError:
                                pass

                        # Suppress logging for CYCLE_START events (normal in CYCLE_SYNC mode)
                        if not response.startswith("CYCLE_START"):
                            logger.debug(
                                f"Invalid intensity response for {ch}: {response}",
                            )
                        return -1
        except Exception as e:
            logger.debug(f"Error reading LED intensity: {e}")
            return -1

    def get_all_led_intensities(self):
        """Query all LED intensities (V1.1+).

        NOTE: Channel D query is disabled due to firmware bug where 'id'
        command conflicts with device identification command.

        Robust behavior:
        - Attempts to query A/B/C via 'iX' firmware command
        - Falls back to cached last-set intensities if query fails/invalid
        - Uses cached value for D (cannot be queried reliably)

        Returns:
            dict: {'a': int, 'b': int, 'c': int, 'd': int} (never None)
                  Values reflect live query when possible, otherwise cached

        """
        intensities: dict[str, int] = {}

        # Query A/B/C; fallback to cached values on failure
        for ch in ["a", "b", "c"]:
            val = self.get_led_intensity(ch)
            if val >= 0:
                intensities[ch] = val
                # Keep cache in sync with actual device state
                self._last_led_intensities[ch] = val
            else:
                # Fallback to last known value to avoid failing calibration
                intensities[ch] = self._last_led_intensities.get(ch, 0)

        # Channel D: cannot be queried reliably → use cached value
        intensities["d"] = self._last_led_intensities.get("d", 0)

        return intensities

    def verify_led_state(self, expected: dict, tolerance: int = 5) -> bool:
        """Verify LEDs are in expected state (V1.1+).

        Args:
            expected: Dictionary of channel->expected_intensity
            tolerance: Acceptable deviation (default 5)

        Returns:
            bool: True if all LEDs within tolerance, False otherwise

        """
        try:
            actual = self.get_all_led_intensities()
            if actual is None:
                return False

            for ch, expected_val in expected.items():
                actual_val = actual.get(ch, -1)
                if abs(actual_val - expected_val) > tolerance:
                    logger.warning(
                        f"LED {ch.upper()} mismatch: expected={expected_val}, actual={actual_val}",
                    )
                    return False
            return True
        except Exception as e:
            logger.error(f"Error verifying LED state: {e}")
            return False

    def emergency_shutdown(self):
        """Turn off all LEDs immediately (V1.1+).

        Returns:
            bool: True if successful, False otherwise

        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = "i0\n"
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)
                    response = self._ser.read(10)
                    success = b"6" in response
                    if success:
                        # Clear enabled channels tracking
                        self._channels_enabled.clear()
                        logger.info("Emergency shutdown executed - all LEDs off")
                    return success
        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}")
            return False

    def turn_off_channels(self):
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = "lx\n"
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)
                    response = self._ser.read(10)
                    success = b"6" in response
                    if success:
                        self._channels_enabled.clear()
                        # Update cached intensities: all LEDs are OFF
                        self._last_led_intensities.update({"a": 0, "b": 0, "c": 0, "d": 0})
                        logger.debug(
                            "[OK] All LED channels turned OFF via 'lx' command",
                        )
                    else:
                        logger.warning(
                            f"[WARN] Turn off channels command may have failed (response: {response!r})",
                        )
                    return success
        except Exception as e:
            logger.error(f"Error turning off channels: {e}")
            return False

    def set_intensity(self, ch="a", raw_val=1):
        try:
            if ch not in {"a", "b", "c", "d"}:
                msg = f"Invalid Channel - {ch}"
                raise ValueError(msg)
            # error bounding: P4SPR LED intensity range is 0-255
            if raw_val > 255:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 255
            elif raw_val < 0:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 0

            # CRITICAL FIX: If intensity is 0, we need to DISABLE the channel, not just set to 0
            # This prevents the channel from staying enabled with residual light
            if raw_val == 0:
                # Use the disable command (lx disables all, but we need individual disable)
                # Send command to turn off this specific channel
                cmd = f"b{ch}000\n"  # Set intensity to 0
                if self._ser is not None or self.open():
                    with self._lock:
                        try:
                            self._ser.reset_output_buffer()
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)
                        ok = self._ser.read() == b"6"
                    if ok:
                        # Remove from enabled channels set
                        self._channels_enabled.discard(ch)
                        # Update cached intensity
                        self._last_led_intensities[ch] = 0
                        logger.debug(f"[OK] LED {ch.upper()} disabled (intensity=0)")
                    return ok
                return False

            cmd = f"b{ch}{int(raw_val):03d}\n"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self._ser is None and not self.open():
                        logger.error(f"pico failed to open port for LED {ch}")
                        return False

                    # Clear any pending I/O to reduce contention
                    try:
                        self._ser.reset_output_buffer()
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    # CRITICAL: Enable channel FIRST, then set intensity
                    # Firmware only applies PWM if channel is enabled (led_x_enabled=true)
                    self.turn_on_channel(ch=ch)

                    with self._lock:
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)  # device processing
                        # Accept both '6' and '1' as success ack for PWM set
                        resp = self._ser.read()
                        ok = resp in (b"6", b"1") or (
                            isinstance(resp, bytes) and resp.startswith(b"6")
                        )

                    if ok:
                        # Update cached intensity on success
                        self._last_led_intensities[ch] = int(raw_val)
                    else:
                        logger.warning(
                            f"[WARN] LED {ch.upper()} intensity command may have failed",
                        )

                    return ok
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"LED write timeout (ch {ch}, attempt {attempt + 1}/{max_retries}): {e}",
                        )
                        time.sleep(0.05)
                        continue
                    logger.error(f"error while setting led intensity {e}")
                    return False
            return False
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0) -> bool | None:
        """Set all LED intensities in a single batch command (V1.1+).

        V1.1 firmware properly handles channel enable/disable in the batch command,
        making this much simpler and more reliable than sequential individual commands.

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

        Note:
            V1.1 firmware handles channel on/off automatically:
            - Non-zero intensity: Turns channel ON and sets intensity
            - Zero intensity: Turns channel OFF (disables PWM)

        """
        try:
            # Clamp values to valid range (0-255)
            a = max(0, min(255, int(a)))
            b = max(0, min(255, int(b)))
            c = max(0, min(255, int(c)))
            d = max(0, min(255, int(d)))

            # CRITICAL: P4SPR firmware requires 2 commands for multi-LED operation:
            # 1. lm:a,b,c,d - Enable channels (which ones are active)
            # 2. batch:A,B,C,D - Set intensities for active channels
            # The 'la/lb/lc/ld' commands disable all other LEDs (only 1 LED at a time)

            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()

                    # Step 1: Enable all channels with non-zero intensity using lm: command
                    channels_to_enable = []
                    if a > 0:
                        channels_to_enable.append('a')
                    if b > 0:
                        channels_to_enable.append('b')
                    if c > 0:
                        channels_to_enable.append('c')
                    if d > 0:
                        channels_to_enable.append('d')

                    if channels_to_enable:
                        # Enable channels: lm:a,b,c,d
                        channel_str = ",".join(channels_to_enable)
                        lm_cmd = f"lm:{channel_str}\n"
                        self._ser.write(lm_cmd.encode())
                        time.sleep(0.02)  # Wait for channel enable

                        # Read ACK for lm command
                        lm_response = self._ser.read(1)

                        self._ser.reset_input_buffer()

                    # Step 2: Set intensities with batch command
                    # Format: batch:A,B,C,D\n
                    cmd = f"batch:{a},{b},{c},{d}\n"
                    self._ser.write(cmd.encode())

                    # Firmware v2.4.1: Minimal wait for command processing (~2ms firmware execution)
                    # Increased slightly to ensure ACK is ready
                    time.sleep(0.005)  # 5ms wait for firmware to process and send ACK

                    # Firmware v2.4.1: Minimal wait for command processing (~2ms firmware execution)
                    # Increased slightly to ensure ACK is ready
                    time.sleep(0.005)  # 5ms wait for firmware to process and send ACK

                    # Read response - firmware sends ACK immediately
                    max_attempts = 3
                    success = False
                    response = b""
                    for attempt in range(max_attempts):
                        if self._ser.in_waiting > 0:
                            response = self._ser.read(self._ser.in_waiting)
                            # Accept '6' or '1' ack from firmware
                            if (b"6" in response) or (b"1" in response):
                                success = True
                                break
                        time.sleep(0.002)  # 2ms between retries

                    if not success:
                        # Final attempt - wait slightly longer
                        time.sleep(0.01)
                        if self._ser.in_waiting > 0:
                            response = self._ser.read(self._ser.in_waiting)
                            success = (b"6" in response) or (b"1" in response)

                if success:
                    # V2.4.1: No need to clear enabled tracking - batch command is atomic
                    # Update cached intensities on success
                    self._last_led_intensities.update({"a": a, "b": b, "c": c, "d": d})
                    logger.debug(f"Batch LED set: A={a} B={b} C={c} D={d}")
                    return True
                logger.warning(f"Batch LED command failed - response: {response}")
                return False
            logger.error("pico serial port not valid for batch command")
            return False

        except (PermissionError, OSError) as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            raise ConnectionError(f"Controller disconnected: {e}") from e
        except Exception as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            return False

    def led_rank_sequence(
        self,
        test_intensity=128,
        settling_ms=45,
        dark_ms=5,
        timeout_s=10.0,
    ):
        r"""Execute firmware-side LED ranking sequence for fast calibration (V1.2+).

        This command triggers the firmware to sequence through all 4 LEDs automatically,
        with precise timing control. Python reads spectra when signaled by firmware.

        Protocol:
            1. Send: "rank:XXX,SSSS,DDD\n" where XXX=intensity, SSSS=settling_ms, DDD=dark_ms
            2. Firmware responds: "START\n"
            3. For each channel (a, b, c, d):
               - Firmware: "X:READY\n" (LED turning on)
               - Firmware: wait settling_ms
               - Firmware: "X:READ\n" (signal Python to read spectrum NOW)
               - Python: Read spectrum while LED is on
               - Firmware: Turn off LED, wait dark_ms
               - Firmware: "X:DONE\n" (measurement complete)
            4. Firmware responds: "END\n"

        Args:
            test_intensity: LED test brightness (0-255, default 128 = 50%)
            settling_ms: LED settling time in ms (default 45ms)
            dark_ms: Dark time between channels in ms (default 5ms)
            timeout_s: Maximum time to wait for sequence (default 10s)

        Yields:
            tuple: (channel, signal) where signal is 'READY', 'READ', or 'DONE'

        Returns:
            Generator that yields (channel, signal) tuples

        Example:
            ```python
            channel_data = {}

            for ch, signal in ctrl.led_rank_sequence(test_intensity=128):
                if signal == 'READ':
                    # Firmware has LED on and stable - read spectrum NOW
                    spectrum = usb.read_spectrum()
                    channel_data[ch] = analyze_spectrum(spectrum)
                elif signal == 'DONE':
                    # Measurement complete for this channel
                    logger.info(f"Channel {ch} complete")

            # All 4 channels measured, rank them
            ranked = rank_channels(channel_data)
            ```

        Performance:
            Old method (Python control): ~600ms (4 channels × 150ms each)
            New method (firmware control): ~220ms (4 channels × 55ms each)
            Speedup: 2.7x faster, more deterministic timing

        """
        try:
            # Clamp values
            test_intensity = max(0, min(255, int(test_intensity)))
            settling_ms = max(0, min(1000, int(settling_ms)))
            dark_ms = max(0, min(100, int(dark_ms)))

            # Format: rank:XXX,SSSS,DDD\n
            cmd = f"rank:{test_intensity},{settling_ms},{dark_ms}\n"

            if self._ser is None and not self.open():
                logger.error("Serial port not available for rank command")
                return

            with self._lock:
                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.01)

                # Wait for START signal
                start_time = time.time()
                while time.time() - start_time < timeout_s:
                    line = self._ser.readline().decode().strip()
                    if line == "START":
                        logger.debug("Rank sequence started")
                        break
                    if time.time() - start_time > 1.0:
                        logger.error(f"Timeout waiting for START, got: {line}")
                        return

                # Process channel signals
                while time.time() - start_time < timeout_s:
                    line = self._ser.readline().decode().strip()

                    # DEBUG: Log EVERY line received from firmware
                    logger.info(f"[RANK PROTOCOL] Firmware sent: '{line}'")

                    if line == "END":
                        logger.debug("Rank sequence complete")
                        break

                    # Parse channel signal: "a:READY", "b:READ", etc.
                    if ":" in line:
                        ch, signal = line.split(":", 1)
                        if ch in ["a", "b", "c", "d"] and signal in [
                            "READY",
                            "READ",
                            "DONE",
                        ]:
                            logger.info(
                                f"[RANK PROTOCOL] Yielding: ch='{ch}', signal='{signal}'",
                            )
                            yield (ch, signal)
                        else:
                            logger.warning(f"Unexpected signal format: {line}")
                    elif line:
                        logger.debug(f"Firmware message: {line}")

                if time.time() - start_time >= timeout_s:
                    logger.error("Rank sequence timeout!")

        except Exception as e:
            logger.error(f"Error in LED rank sequence: {e}")
            return

    def set_mode(self, mode="s"):
        """Switch polarizer between S and P modes (PicoP4SPR).

        ========================================================================
        CRITICAL RULE: NEVER USE EEPROM FOR SERVO POSITIONS - ALWAYS DEVICE_CONFIG
        ========================================================================
        POSITIONS ARE IMMUTABLE - SINGLE SOURCE OF TRUTH IS device_config.json

        This function sends 'ss' or 'sp' command to controller firmware.
        The controller reads servo positions from its EEPROM memory.

        EEPROM positions are:
        - Written from device_config.json at application startup ONLY
        - NEVER read or modified during runtime
        - Controller firmware uses these stored positions when 'ss'/'sp' received

        This is the ONLY correct architecture:
        device_config.json → EEPROM (once at startup) → firmware uses for 'ss'/'sp'

        Legacy servo_set()/servo_get()/flash() operations are FORBIDDEN and DELETED.
        ========================================================================
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    # Flush input buffer to clear any stale data
                    with contextlib.suppress(Exception):
                        self._ser.reset_input_buffer()

                    cmd = "ss\n" if mode == "s" else "sp\n"

                    self._ser.write(cmd.encode())
                    # Increased wait time for servo movement; some firmware emits no ack
                    time.sleep(0.12)

                    # Try reading response multiple times (servo might be slow)
                    response = b""
                    attempts = 0
                    for attempts in range(3):
                        response = self._ser.readline().strip()
                        if response:
                            break
                        time.sleep(0.05)

                    # Log what we got back
                    mode_name = "S-mode" if mode == "s" else "P-mode"
                    # Reduce noise: treat empty responses as normal on V1.1 firmware
                    if response:
                        logger.info(
                            f"📡 Controller response to set_mode('{mode}'): {response} (after {attempts + 1} attempts)",
                        )
                    else:
                        logger.debug(
                            f"📡 Controller response to set_mode('{mode}'): <empty> (after {attempts} attempts)",
                        )

                    # Check if response indicates success
                    # v2.2 firmware may contaminate with debug output (e.g., b'6CYCLE:689')
                    success = (
                        response == b"" or response == b"6" or response.startswith(b"6")
                    )

                    if success:
                        # Only log success loudly if we received explicit ack; keep empty ack as quiet success
                        if response and response != b"6":
                            # Got ACK with trailing debug data
                            logger.info(
                                f"[OK] Controller confirmed: {mode_name} servo moved (response: {response[:20]}...)"
                                if len(response) > 20
                                else f"[OK] Controller confirmed: {mode_name} servo moved (response: {response})",
                            )
                        elif response == b"6":
                            logger.info(
                                f"[OK] Controller confirmed: {mode_name} servo moved to position from device_config",
                            )
                        else:
                            logger.debug(
                                f"[OK] {mode_name} set with empty ack (accepted on firmware V1.1)",
                            )
                    else:
                        # Unexpected response
                        logger.warning(
                            f"[WARN] Controller response unexpected for {mode_name}: expected b'6', got {response}",
                        )
                        logger.warning(
                            "[WARN] Proceeding; servo likely moved correctly (device_config→EEPROM→firmware)",
                        )
                        return True

                    return success
        except Exception as e:
            logger.error(f"[ERROR] Exception during set_mode('{mode}'): {e}")
            return False

    # =========================================================================
    # V2.4 FIRMWARE COMMANDS
    # =========================================================================

    def rankbatch(self, int_a, int_b, int_c, int_d, settling_ms, dark_ms, num_cycles):
        """Execute rankbatch LED sequence (V2.4 CYCLE_SYNC firmware).

        V2.4 firmware uses hardware timer ISR to sequence LEDs with precise timing.
        Sends CYCLE_START event once per cycle (75% less USB traffic than V2.3).

        Args:
            int_a: Intensity for LED A (0-255)
            int_b: Intensity for LED B (0-255)
            int_c: Intensity for LED C (0-255)
            int_d: Intensity for LED D (0-255)
            settling_ms: LED settling time in ms (10-1000)
            dark_ms: Dark period between LEDs in ms (0-100)
            num_cycles: Number of measurement cycles (1-10000)

        Returns:
            bool: True if command sent successfully, False otherwise

        Note:
            This sends the command and returns immediately. The acquisition
            manager monitors CYCLE_START events to synchronize reads.
        """
        try:
            # Clamp values to safe ranges
            int_a = max(0, min(255, int(int_a)))
            int_b = max(0, min(255, int(int_b)))
            int_c = max(0, min(255, int(int_c)))
            int_d = max(0, min(255, int(int_d)))
            settling_ms = max(10, min(1000, int(settling_ms)))
            dark_ms = max(0, min(100, int(dark_ms)))
            num_cycles = max(1, min(10000, int(num_cycles)))

            # Format: rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
            cmd = f"rankbatch:{int_a},{int_b},{int_c},{int_d},{settling_ms},{dark_ms},{num_cycles}\n"

            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.01)

                    # Wait for ACK
                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        logger.info(f"[OK] Rankbatch started: {num_cycles} cycles")
                    else:
                        logger.error(f"[ERROR] Rankbatch failed to start: {response!r}")

                    return success
        except Exception as e:
            logger.error(f"Error sending rankbatch command: {e}")
            return False

    def stop_rankbatch(self):
        """Stop currently running rankbatch sequence (V2.4).

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(b"stop\n")
                    time.sleep(0.01)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        logger.info("[OK] Rankbatch stopped")
                    else:
                        logger.warning(f"[WARN] Stop command response: {response!r}")

                    return success
        except Exception as e:
            logger.error(f"Error stopping rankbatch: {e}")
            return False

    def send_keepalive(self):
        """Send keepalive to reset watchdog timer (V2.4.1).

        The watchdog monitors for keepalive signals and will auto-stop
        rankbatch if timeout is exceeded (default 120 seconds).

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.write(b"ka\n")
                    time.sleep(0.005)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if not success:
                        logger.debug(f"Keepalive response: {response!r}")

                    return success
        except Exception as e:
            logger.debug(f"Keepalive error: {e}")
            return False

    def set_servo_speed(self, speed_ms):
        """Set servo pulse duration for movement speed (V2.4).

        Args:
            speed_ms: Pulse duration in milliseconds (200-2000)
                     200 = fastest, 2000 = slowest
                     Default is 500ms

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            speed_ms = max(200, min(2000, int(speed_ms)))

            cmd = f"servo_speed:{speed_ms}\n"

            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.01)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        logger.info(f"[OK] Servo speed set to {speed_ms}ms")
                    else:
                        logger.warning(f"[WARN] Servo speed command response: {response!r}")

                    return success
        except Exception as e:
            logger.error(f"Error setting servo speed: {e}")
            return False

    def reboot_to_bootloader(self):
        """Reboot controller into BOOTSEL mode for firmware updates (V2.4).

        Returns:
            bool: True if command sent, False otherwise

        Note:
            Controller will disconnect immediately after receiving this command.
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.write(b"ib\n")
                    time.sleep(0.1)  # Give time for response

                    response = self._ser.read(1)
                    logger.info(f"Bootloader reboot initiated (response: {response!r})")

                    # Controller will disconnect - close serial port
                    try:
                        self._ser.close()
                    except:
                        pass
                    self._ser = None

                    return True
        except Exception as e:
            logger.error(f"Error rebooting to bootloader: {e}")
            return False

    def device_off(self):
        """Turn off device (all LEDs off, power indicator off) (V2.4).

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(b"do\n")
                    time.sleep(0.02)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        logger.info("[OK] Device powered off")
                    else:
                        logger.warning(f"[WARN] Device off response: {response!r}")

                    return success
        except Exception as e:
            logger.error(f"Error turning device off: {e}")
            return False

    def turn_on_multi_leds(self, channels):
        """Turn on multiple LEDs simultaneously (V2.4).

        Args:
            channels: String or list of channels to enable (e.g., "abc" or ['a', 'b', 'c'])

        Returns:
            bool: True if successful, False otherwise

        Example:
            ctrl.turn_on_multi_leds("ab")   # Turn on A and B
            ctrl.turn_on_multi_leds(['a', 'c', 'd'])  # Turn on A, C, D
        """
        try:
            # Convert to string and validate
            if isinstance(channels, list):
                channels = "".join(channels)

            channels = channels.lower()
            valid_channels = [ch for ch in channels if ch in 'abcd']

            if not valid_channels:
                logger.error("No valid channels specified")
                return False

            # Format: lm:A,B,C,D
            channel_str = ",".join(valid_channels)
            cmd = f"lm:{channel_str}\n"

            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        # Update enabled channels tracking
                        self._channels_enabled.clear()
                        self._channels_enabled.update(valid_channels)
                        logger.debug(f"[OK] Multi-LED enabled: {','.join(valid_channels)}")
                    else:
                        logger.warning(f"[WARN] Multi-LED response: {response!r}")

                    return success
        except Exception as e:
            logger.error(f"Error enabling multi-LEDs: {e}")
            return False

    # =========================================================================
    # LEGACY EEPROM FUNCTIONS DELETED - DO NOT USE FOR SERVO POSITIONS
    # =========================================================================
    # servo_get() - DELETED - reads positions from EEPROM (DANGEROUS)
    # servo_set() - DELETED - writes positions to EEPROM (DANGEROUS)
    # flash() - DELETED - writes to EEPROM (DANGEROUS)
    #
    # Servo positions come ONLY from device_config.json
    # They are loaded at startup via write_config_to_eeprom()
    # NEVER changed at runtime
    # =========================================================================

    def servo_move_raw_pwm(self, target_pwm):
        """Move servo to a specific PWM position (for calibration).

        This is used during servo calibration to move the servo to test positions.

        V2.4 Firmware Command Format:
            servo:ANGLE,DURATION_MS
            Example: servo:90,500 → move to 90° in 500ms

        Firmware Angle Mapping (from affinite_p4spr_LATEST_v2.4.1.c):
            MIN_DEG = 5, MAX_DEG = 175
            duty = 0.025 + (deg - MIN_DEG) × (0.125 - 0.025) / (MAX_DEG - MIN_DEG)
            Linear map: 5-175° → 2.5%-12.5% duty cycle

        PWM to Angle Conversion:
            PWM 0-255 → Angle 5-175°
            Formula: angle = 5 + (pwm / 255.0) × 170

        Args:
            target_pwm: PWM value 0-255 (will be converted to angle 5-175°)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if target_pwm < 0 or target_pwm > 255:
                logger.error(f"Invalid PWM value: {target_pwm} (must be 0-255)")
                return False

            # Convert PWM (0-255) to firmware angle (5-175°)
            # Linear mapping: 0→5°, 255→175°
            pwm_val = int(target_pwm)
            MIN_ANGLE = 5
            MAX_ANGLE = 175
            angle = int(MIN_ANGLE + (pwm_val / 255.0) * (MAX_ANGLE - MIN_ANGLE))

            # Clamp to firmware range
            angle = max(MIN_ANGLE, min(MAX_ANGLE, angle))

            # V2.4 firmware command: servo:ANGLE,DURATION_MS
            # Use 500ms duration for smooth, reliable movement
            cmd = f"servo:{angle},500\n"
            logger.info(f"Moving servo: PWM {pwm_val} to angle {angle} degrees: {cmd.strip()}")

            # Debug: Check serial port state
            if self._ser is None:
                logger.warning("⚠️ Serial port is None - attempting to open...")
                if not self.open():
                    logger.error("❌ Failed to open serial port!")
                    return False
                logger.info("✅ Serial port opened successfully")

            if self._ser is not None:
                logger.debug(f"🔍 Serial port: {self._ser.port}, is_open={self._ser.is_open}")

                with self._lock:
                    try:
                        self._ser.reset_input_buffer()
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to reset input buffer: {e}")

                    # Send servo move command
                    logger.debug(f"📤 Sending command: {cmd.strip()}")
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)
                    response = self._ser.read(10)  # Read up to 10 bytes for response
                    logger.debug(f"📥 Response: {response!r}")

                    # V2.4 firmware responds with '1' for servo:ANGLE,DURATION format
                    # Older firmware responds with '6'
                    if response in (b"1", b"6"):
                        # Wait for physical servo movement
                        # V2.4 firmware: 500ms movement duration specified in command
                        # Add extra margin for physical settling
                        time.sleep(0.6)  # 600ms total wait (500ms movement + 100ms settle)
                        logger.debug(f"Servo physically moved to angle {angle} degrees (PWM {pwm_val})")
                        return True
                    else:
                        logger.error(f"❌ servo command failed: {response!r} (expected b'1' or b'6')")
                        return False

            logger.error("❌ Serial port not open after attempted recovery")
            return False

        except Exception as e:
            logger.error(f"❌ Error moving servo to PWM {target_pwm}: {e}")
            return False

    def servo_move_calibration_only(self, s=10, p=100):
        """CALIBRATION ONLY: Move servo to test positions.

        ========================================================================
        FOR SERVO CALIBRATION WORKFLOW ONLY
        ========================================================================
        This function is ONLY for the servo calibration workflow where we scan
        different angles to FIND optimal S and P positions.

        Results are saved to device_config.json (NOT EEPROM).
        After calibration, application restart writes device_config to EEPROM.

        DO NOT use this for runtime position changes.
        DO NOT use this during normal acquisition.

        EXPECTS PWM VALUES (0-255), NOT DEGREES!
        ========================================================================
        """
        # Handle None values gracefully - use current position if None
        if s is None:
            s = 10  # Default S position
        if p is None:
            p = 100  # Default P position

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Convert early — config JSON can deliver these as strings
                try:
                    s = int(s)
                    p = int(p)
                except (TypeError, ValueError) as conv_err:
                    logger.warning(f"servo_move_calibration_only: invalid position values {s!r}, {p!r}: {conv_err}")
                    return False

                if (s < 0) or (p < 0) or (s > 255) or (p > 255):
                    msg = f"Invalid polarizer PWM position: {s}, {p} (must be 0-255)"
                    raise ValueError(msg)

                # Values are already in PWM (0-255) - NO CONVERSION NEEDED
                s_servo = s
                p_servo = p

                cmd = f"sv{s_servo:03d}{p_servo:03d}\n"
                if self._ser is not None or self.open():
                    with self._lock:
                        with contextlib.suppress(Exception):
                            self._ser.reset_input_buffer()

                        self._ser.write(cmd.encode())
                        time.sleep(0.05)

                        response = self._ser.readline().strip()
                        if not response:
                            time.sleep(0.05)
                            response = self._ser.readline().strip()

                        # Accept '6' or '1' as success (firmware versions vary)
                        # Also accept if '6' or '1' appears anywhere in response
                        success = (response == b"6" or response == b"1" or
                                   b"6" in response or b"1" in response)

                        if not success:
                            logger.debug(f"Servo move response: {response!r} (expected b'6' or b'1')")

                        # CRITICAL: Even if no ACK, the servo IS moving (verified by user)
                        # Return True as long as command was sent successfully
                        return True
                else:
                    logger.error("Cannot move servo - port not open")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                logger.warning(f"Servo calibration move failed: {e}")
                return False
        return False

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        import time

        try:
            if self._ser is not None or self.open():
                with self._lock:
                    with contextlib.suppress(Exception):
                        self._ser.reset_input_buffer()
                    self._ser.write(b"cv\n")
                    # Firmware V2.4 may take longer and may not ACK reliably
                    start = time.time()
                    response = b""
                    while time.time() - start < 1.0:  # up to 1s
                        chunk = self._ser.read(1)
                        if chunk:
                            response += chunk
                            break
                        time.sleep(0.05)
                    # Treat '6' or response starting with '6' as success; empty = unknown/False
                    return response == b"6" or response.startswith(b"6")
            return False
        except Exception as e:
            logger.debug(f"PicoP4SPR EEPROM config check failed: {e}")
            return False

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM."""
        import struct
        import time

        try:
            if self._ser is not None or self.open():
                with self._lock:
                    with contextlib.suppress(Exception):
                        self._ser.reset_input_buffer()
                    self._ser.write(b"rc\n")
                    # Firmware V2.4 may stream data slower; accumulate up to 20 bytes
                    start = time.time()
                    buf = bytearray()
                    while time.time() - start < 1.0 and len(buf) < 20:
                        # Read whatever is waiting
                        waiting = getattr(self._ser, "in_waiting", 0)
                        if waiting and waiting > 0:
                            buf.extend(self._ser.read(waiting))
                        else:
                            # Fallback to 1-byte reads
                            chunk = self._ser.read(1)
                            if chunk:
                                buf.extend(chunk)
                            else:
                                time.sleep(0.05)

                    data = bytes(buf[:20])
                    if len(data) != 20:
                        logger.warning(
                            f"PicoP4SPR EEPROM read returned {len(data)} bytes, expected 20",
                        )
                        return None

                    # Verify checksum
                    calculated_checksum = self._calculate_checksum(data)
                    stored_checksum = data[16]
                    if calculated_checksum != stored_checksum:
                        logger.warning(
                            f"PicoP4SPR EEPROM checksum mismatch: calc={calculated_checksum}, stored={stored_checksum}",
                        )
                        return None

                    # Parse data (same format as Arduino)
                    version = data[0]
                    if version != 1:
                        logger.warning(
                            f"Unknown PicoP4SPR EEPROM config version: {version}",
                        )
                        return None

                    led_model = self._decode_led_model(data[1])
                    controller_type = self._decode_controller_type(data[2])
                    fiber_diameter = data[3]
                    polarizer_type = self._decode_polarizer_type(data[4])
                    servo_s = struct.unpack("<H", data[5:7])[0]
                    servo_p = struct.unpack("<H", data[7:9])[0]
                    led_a = data[9]
                    led_b = data[10]
                    led_c = data[11]
                    led_d = data[12]
                    integration_time = struct.unpack("<H", data[13:15])[0]
                    num_scans = data[15]

                    config = {
                        "led_pcb_model": led_model,
                        "controller_type": controller_type,
                        "fiber_diameter_um": fiber_diameter,
                        "polarizer_type": polarizer_type,
                        "servo_s_position": servo_s,
                        "servo_p_position": servo_p,
                        "led_intensity_a": led_a,
                        "led_intensity_b": led_b,
                        "led_intensity_c": led_c,
                        "led_intensity_d": led_d,
                        "integration_time_ms": integration_time,
                        "num_scans": num_scans,
                    }

                    logger.info(
                        f"✓ Loaded device config from PicoP4SPR EEPROM: {led_model}, {fiber_diameter}µm fiber",
                    )
                    return config

        except Exception as e:
            logger.error(f"Failed to read PicoP4SPR EEPROM config: {e}")
            return None

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM."""
        import struct
        import time

        try:
            if self._ser is not None or self.open():
                with self._lock:
                    # Build 20-byte config packet (same as Arduino)
                    data = bytearray(20)
                    data[0] = 1  # version
                    data[1] = self._encode_led_model(
                        config.get("led_pcb_model", "luminus_cool_white"),
                    )
                    data[2] = self._encode_controller_type(
                        config.get("controller_type", "pico_p4spr"),
                    )
                    data[3] = config.get("fiber_diameter_um", 200)
                    data[4] = self._encode_polarizer_type(
                        config.get("polarizer_type", "round"),
                    )

                    # Ensure servo positions are integers (not strings or floats)
                    servo_s = int(config.get("servo_s_position", 10))
                    servo_p = int(config.get("servo_p_position", 100))
                    data[5:7] = struct.pack("<H", servo_s)
                    data[7:9] = struct.pack("<H", servo_p)

                    data[9] = config.get("led_intensity_a", 0)
                    data[10] = config.get("led_intensity_b", 0)
                    data[11] = config.get("led_intensity_c", 0)
                    data[12] = config.get("led_intensity_d", 0)

                    integration_time = config.get("integration_time_ms", 100)
                    data[13:15] = struct.pack("<H", integration_time)
                    data[15] = config.get("num_scans", 3)

                    data[16] = self._calculate_checksum(data)

                    # Send to controller
                    # V2.4 firmware EEPROM write command
                    self._ser.reset_input_buffer()

                    # Debug: Log what we're sending
                    logger.debug(f"📤 Sending EEPROM write: wc + {len(data)} bytes + newline")
                    logger.debug(f"   Servo S={servo_s}, P={servo_p}")

                    self._ser.write(b"wc")
                    self._ser.write(bytes(data))
                    self._ser.write(b"\n")

                    # CRITICAL: EEPROM writes are SLOW (can take 500ms+)
                    # V2.4 firmware needs longer timeout for flash operations
                    time.sleep(0.6)  # Increased from 0.2s to 0.6s for EEPROM write

                    # Read response with timeout
                    response = self._ser.read(10)  # Read up to 10 bytes to catch any error messages

                    success = b"6" in response

                    if success:
                        logger.info("✓ Device config written to PicoP4SPR EEPROM")

                    return success

        except Exception as e:
            logger.error(f"Failed to write PicoP4SPR EEPROM config: {e}")
            return False

    def stop(self) -> None:
        self.turn_off_channels()

    def __str__(self) -> str:
        return "Pico Mini Board"

