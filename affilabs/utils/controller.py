from __future__ import annotations

import builtins
import contextlib
import json
import threading
import time
from json import JSONDecodeError
from pathlib import Path
from platform import system
from shutil import copy
from typing import Final

import numpy as np
import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import (
    ARDUINO_PID,
    ARDUINO_VID,
    BAUD_RATE,
    CP210X_PID,
    CP210X_VID,
    PICO_PID,
    PICO_VID,
)

if system() == "Windows":
    import string

CH_DICT = {"a": 1, "b": 2, "c": 3, "d": 4}


class ControllerBase:
    """Abstract base class for all hardware controllers."""

    def __init__(self, name) -> None:
        self._ser = None
        self.name = name

    def open(self) -> None:
        pass

    def get_info(self) -> None:
        pass

    def turn_on_channel(self, ch="a") -> None:
        pass

    def turn_off_channels(self) -> None:
        pass

    def set_mode(self, mode="s") -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        """Close serial port connection."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                # Log but don't raise - we want cleanup to continue
                logger.exception(f"Error closing serial port: {e}")
            finally:
                self._ser = None

    # EEPROM Configuration Methods
    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        return False  # Override in subclass

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM.

        Returns dict with keys:
            led_pcb_model: 'luminus_cool_white' or 'osram_warm_white'
            controller_type: 'arduino', 'pico_p4spr', 'pico_ezspr'
            fiber_diameter_um: 100 or 200
            polarizer_type: 'barrel' or 'round'
            servo_s_position: 0-180
            servo_p_position: 0-180
            led_intensity_a: 0-255
            led_intensity_b: 0-255
            led_intensity_c: 0-255
            led_intensity_d: 0-255
            integration_time_ms: int
            num_scans: int

        Returns None if no valid config or firmware doesn't support.
        """
        return None  # Override in subclass

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM.

        Args:
            config: Dict with same keys as read_config_from_eeprom()

        Returns:
            True if successful, False otherwise

        """
        return False  # Override in subclass

    @staticmethod
    def _encode_led_model(model: str) -> int:
        """Convert LED model name to byte value."""
        mapping = {
            "luminus_cool_white": 0,
            "osram_warm_white": 1,
        }
        return mapping.get(model.lower(), 255)

    @staticmethod
    def _decode_led_model(value: int) -> str:
        """Convert byte value to LED model name."""
        mapping = {0: "luminus_cool_white", 1: "osram_warm_white"}
        return mapping.get(value)

    @staticmethod
    def _encode_controller_type(controller_type: str) -> int:
        """Convert controller type to byte value."""
        mapping = {
            "arduino": 0,
            "pico_p4spr": 1,
            "pico_ezspr": 2,
        }
        return mapping.get(controller_type.lower(), 255)

    @staticmethod
    def _decode_controller_type(value: int) -> str:
        """Convert byte value to controller type."""
        mapping = {0: "arduino", 1: "pico_p4spr", 2: "pico_ezspr"}
        return mapping.get(value)

    @staticmethod
    def _encode_polarizer_type(polarizer: str) -> int:
        """Convert polarizer type to byte value."""
        mapping = {"barrel": 0, "round": 1}
        return mapping.get(polarizer.lower(), 255)

    @staticmethod
    def _decode_polarizer_type(value: int) -> str:
        """Convert byte value to polarizer type."""
        mapping = {0: "barrel", 1: "round"}
        return mapping.get(value)

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """Calculate XOR checksum of first 16 bytes."""
        checksum = 0
        for byte in data[0:16]:
            checksum ^= byte
        return checksum

    def __del__(self) -> None:
        """Destructor to ensure serial port is closed."""
        try:
            if hasattr(self, "_ser") and self._ser is not None:
                self.close()
        except:
            pass


class StaticController(ControllerBase):
    """Base class for static-mode controllers (P4SPR family).

    Static controllers have detector/spectroscopy capabilities but no pumps or valves.
    They operate by having liquid statically incubate on the sensor surface.

    Hardware: ArduinoController (Gen 1), PicoP4SPR (Gen 2)
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Static controllers do not support flow mode."""
        return False


class FlowController(ControllerBase):
    """Base class for flow-mode controllers (P4PRO, KNX, ezSPR families).

    Flow controllers support liquid handling via pumps and valves for continuous
    flow-based SPR measurements.

    Hardware configurations:
    - P4PRO: P4SPR detector + KNX valves + external AffiPump
    - KNX: Standalone pump/valve unit (no detector)
    - ezSPR/P4PROPlus: P4SPR detector + integrated KNX pumps/valves
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Flow controllers support flow mode."""
        return True


# ArduinoController class DELETED - obsolete hardware
# Use PicoP4SPR instead


class KineticController(FlowController):
    def __init__(self) -> None:
        super().__init__(name="KNX2")
        self._lock = threading.Lock()
        self.version = "1.0"

    def open(self) -> bool | None:
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found a KNX2 board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=BAUD_RATE,
                        timeout=3,
                        write_timeout=1,
                        dsrdtr=True,
                        rtscts=False,
                    )
                    info = self.get_info()
                    if info is not None:
                        if info["fw ver"].startswith("KNX2"):
                            if info["fw ver"].startswith("KNX2 V1.1"):
                                self.version = "1.1"
                            return True
                        if info["fw ver"].startswith("EZSPR"):
                            self.name = "EZSPR"
                            if info["fw ver"].startswith("EZSPR V1.1"):
                                self.version = "1.1"
                            return True
                        if info["fw ver"].startswith("KNX1"):
                            self.name = "KNX"
                            self.version = "1.1"
                            return True
                        logger.debug("dev is not KNX2")
                        self._ser.close()
                        return False
                    logger.debug(f"Error during get info, returned: {info}")
                    self._ser.close()
                    return False
                except Exception as e:
                    logger.error(f"Failed to open KNX2 - {e}")
                    self._ser = None
                    return False
        return None

    def _send_command(self, cmd, parse_json=False, reply=True):
        if self._ser is not None or self.open():
            logger.debug(f"KNX2: Sending command - `{cmd}`")
            try:
                with self._lock:
                    self._ser.write(f"{cmd}\n".encode())
                    if reply:
                        buf = self._ser.readline().decode()
                        if parse_json:
                            try:
                                return json.loads(buf)
                            except JSONDecodeError:
                                logger.error(
                                    f"Failed to parse to JSON of {cmd} - {buf}",
                                )
                                return None
                        else:
                            data = buf.splitlines()
                            return data[0] if data else buf
            except Exception as e:
                logger.error(f"Failed to send command to {self.name} - {e}")
                self._ser = None
        return None

    def get_status(self):
        return self._send_command(cmd="get_status", parse_json=True)

    def get_info(self):
        return self._send_command(cmd="get_info", parse_json=True)

    def get_parameters(self):
        return self._send_command(cmd="get_parameters", parse_json=True)

    def read_wavelength(self, channel):
        data = self._send_command(cmd=f"read{channel}")
        if data:
            return np.asarray([int(v) for v in data.split(",")])
        return None

    def read_intensity(self):
        data = self._send_command(cmd="intensity")
        if data:
            return np.asarray([int(v) for v in data.split(",")])
        return None

    def stop(self):
        return self._send_command(cmd="stop")

    def turn_on_channel(self, ch="a"):
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def turn_off_channels(self):
        return self._send_command("led_off")

    # Equivalent to the Arduino function to turn on a channel LED at a given intensity
    def set_intensity(self, ch="a", raw_val=255):
        val = int((raw_val / 255) * 31) + 1
        self._send_command(f"led_intensity({CH_DICT[ch]},{val})")
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def set_integration(self, int_ms):
        return self._send_command(f"set_integration({int_ms})")

    def set_mode(self, mode="s"):
        return self._send_command(f"servo_{mode}")

    def servo_set(self, s=10, p=100):
        return self._send_command(f"servo_set({s},{p})")

    def knx_stop(self, ch):
        return self._send_command(f"knx_stop_{ch}")

    def knx_start(self, rate, ch):
        return self._send_command(f"knx_start_{rate}_{ch}")

    def knx_three(self, state, ch):
        return self._send_command(f"knx_three_{state}_{ch}")

    def knx_six(self, state, ch):
        return self._send_command(f"knx_six_{state}_{ch}")

    def knx_led(self, led_state, ch):
        return self._send_command(f"knx_led_{led_state}_{ch}")

    def knx_status(self, ch):
        return self._send_command(cmd=f"knx_status_{ch}", parse_json=True)

    def stop_kinetic(self) -> None:
        self._send_command("knx_stop_all")

    def shutdown(self) -> None:
        self._send_command("shutdown")
        self.close()

    def __str__(self) -> str:
        return "KNX2 Board"


class PicoP4SPR(StaticController):
    def __init__(self) -> None:
        super().__init__(name="pico_p4spr")
        self._ser = None
        self.version = ""
        self._lock = threading.Lock()
        self._channels_enabled = set()  # Track which LED channels have been enabled
        # Cache of last-set LED intensities for reliable readback/fallback
        self._last_led_intensities: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}

    def open(self) -> bool:
        # Close existing connection if any
        if self._ser is not None:
            with contextlib.suppress(builtins.BaseException):
                self._ser.close()
            self._ser = None

        # Reset channel tracking on new connection
        self._channels_enabled = set()

        # Try VID/PID match first (preferred method - auto-detects correct COM port)
        logger.info(
            f"PicoP4SPR.open() - Looking for VID={hex(PICO_VID)} PID={hex(PICO_PID)}",
        )
        port_list = list(serial.tools.list_ports.comports())
        logger.debug(f"Found {len(port_list)} COM ports")
        for dev in port_list:
            logger.debug(
                f"  Port {dev.device}: VID={hex(dev.vid) if dev.vid else 'None'} PID={hex(dev.pid) if dev.pid else 'None'}",
            )
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    logger.info(f"MATCH! Trying PicoP4SPR on {dev.device}")
                    # Increase timeouts to improve reliability on Windows
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=1.0,
                        write_timeout=1,
                        dsrdtr=True,
                        rtscts=False,
                    )
                    # CRITICAL: Explicitly set DTR/RTS after opening (Pico USB CDC requirement)
                    self._ser.dtr = True
                    self._ser.rts = True
                    import time

                    time.sleep(0.1)  # 100ms settle time after DTR/RTS

                    # Flush any stale data
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()

                    cmd = "id\n"
                    self._ser.write(cmd.encode())

                    time.sleep(0.5)  # 500ms delay matching PowerShell test
                    raw_reply = self._ser.readline()
                    reply = (
                        raw_reply[0:5].decode()
                        if len(raw_reply) >= 5
                        else raw_reply.decode()
                    )
                    logger.info(f"Pico P4SPR ID reply: '{reply}'")
                    if reply == "P4SPR":
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        time.sleep(0.20)
                        self.version = self._ser.readline()[0:4].decode()
                        logger.info(f"Pico P4SPR Fw version: {self.version}")
                        return True
                    logger.warning(f"ID mismatch - expected 'P4SPR', got '{reply}'")
                    try:
                        self._ser.close()
                    except Exception as close_err:
                        logger.error(
                            f"Error closing port after ID mismatch: {close_err}",
                        )
                    finally:
                        self._ser = None
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
                # Slightly higher timeout to handle slower Pico responses
                self._ser = serial.Serial(
                    port=dev.device,
                    baudrate=115200,
                    timeout=0.5,
                    write_timeout=0.5,
                    dsrdtr=True,
                    rtscts=False,
                )
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                cmd = "id\n"
                self._ser.write(cmd.encode())
                import time

                time.sleep(0.15)  # Allow more time for firmware to print
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
                    with contextlib.suppress(builtins.BaseException):
                        self._ser.close()
                    self._ser = None

        return False

    def turn_on_channel(self, ch="a"):
        try:
            if ch not in {"a", "b", "c", "d"}:
                msg = "Invalid Channel!"
                raise ValueError(msg)

            # Skip if already enabled (optimization)
            if ch in self._channels_enabled:
                return True

            cmd = f"l{ch}\n"
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()  # Clear any leftover data
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)  # Wait for response
                    response = self._ser.read(1)  # Read 1 byte (firmware sends '1')
                    success = response == b"6"
                    if success:
                        # CRITICAL: Firmware auto-disables previous LED when new one turns on
                        # Clear tracking set and add only the new channel
                        self._channels_enabled.clear()
                        self._channels_enabled.add(ch)
                        logger.debug(
                            f"[OK] LED {ch.upper()} enabled via 'l{ch}' command",
                        )
                    else:
                        logger.warning(
                            f"[ERROR] LED {ch.upper()} enable failed - no '1' response (got: {response})",
                        )
                    return success
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
                        logger.debug(
                            f"[OK] LED {ch.upper()} intensity set to {raw_val} (ack={resp!r})",
                        )
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

            # Format: batch:A,B,C,D\n
            # V2.4.1 firmware: batch command handles PWM enable/disable automatically
            cmd = f"batch:{a},{b},{c},{d}\n"

            if self._ser is not None or self.open():
                with self._lock:
                    # V2.4.1: Send batch command directly (no pre-enable needed)
                    # The firmware batch handler calls led_brightness() which sets PWM registers
                    # and enables/disables channels automatically based on intensity values
                    self._ser.reset_input_buffer()
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
                    logger.debug(
                        f"Batch LED command successful: A={a}, B={b}, C={c}, D={d}",
                    )
                    return True
                logger.warning(f"Batch LED command failed - response: {response}")
                return False
            logger.error("pico serial port not valid for batch command")
            return False

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
        Firmware sends PWM pulse for 500ms (default), then waits 100ms.

        Args:
            target_pwm: PWM value 0-255

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if target_pwm < 0 or target_pwm > 255:
                logger.error(f"Invalid PWM value: {target_pwm} (must be 0-255)")
                return False

            # Set both S and P to the same value (we're just testing one position)
            pwm_val = int(target_pwm)

            # Send sv command to set the position values
            cmd = f"sv{pwm_val:03d}{pwm_val:03d}\n"
            logger.info(f"🔧 Moving servo to PWM {pwm_val}: {cmd.strip()}")

            if self._ser is not None or self.open():
                with self._lock:
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    # Step 1: Set the position values
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)
                    response = self._ser.read(1)

                    if response != b"6":
                        logger.error(f"❌ sv command failed: {response!r}")
                        return False

                    logger.debug(f"✅ Position set to PWM {pwm_val}")

                    # Step 2: Move to that position using ss (S-mode)
                    # Firmware will send PWM pulse for ~500ms then turn off
                    self._ser.write(b"ss\n")
                    time.sleep(0.05)
                    response = self._ser.read(1)

                    if response == b"6":
                        # Wait for physical servo movement
                        # Firmware: 500ms pulse + 100ms settle = 600ms total
                        # Add extra margin for physical movement
                        time.sleep(0.7)  # 700ms total wait
                        logger.info(f"✅ Servo physically moved to PWM {pwm_val}")
                        return True
                    else:
                        logger.error(f"❌ ss command failed: {response!r}")
                        return False

            logger.error("❌ Serial port not open")
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
                if (s < 0) or (p < 0) or (s > 255) or (p > 255):
                    msg = f"Invalid polarizer PWM position: {s}, {p} (must be 0-255)"
                    raise ValueError(msg)

                # Values are already in PWM (0-255) - NO CONVERSION NEEDED
                s_servo = int(s)
                p_servo = int(p)

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

                        return response == b"6"
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
                    self._ser.reset_input_buffer()
                    self._ser.write(b"cv\n")
                    time.sleep(0.1)
                    response = self._ser.read(1)
                    return response == b"6"
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
                    self._ser.reset_input_buffer()
                    self._ser.write(b"rc\n")
                    time.sleep(0.15)

                    # Read 20 bytes
                    data = self._ser.read(20)
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

                    servo_s = config.get("servo_s_position", 10)
                    servo_p = config.get("servo_p_position", 100)
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
                    self._ser.reset_input_buffer()
                    self._ser.write(b"wc")
                    self._ser.write(bytes(data))
                    self._ser.write(b"\n")

                    time.sleep(0.2)

                    response = self._ser.read(1)
                    success = response == b"6"

                    if success:
                        logger.info("✓ Device config written to PicoP4SPR EEPROM")
                    else:
                        logger.warning(
                            f"PicoP4SPR EEPROM write failed, response: {response}",
                        )

                    return success

        except Exception as e:
            logger.error(f"Failed to write PicoP4SPR EEPROM config: {e}")
            return False

    def stop(self) -> None:
        self.turn_off_channels()

    def __str__(self) -> str:
        return "Pico Mini Board"


class PicoKNX2(FlowController):
    def __init__(self) -> None:
        super().__init__(name="pico_knx2")
        self._ser = None
        self.version = ""

    def open(self) -> bool:
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                # Try up to 3 times to connect to this device
                for attempt in range(3):
                    try:
                        self._ser = serial.Serial(
                            port=dev.device,
                            baudrate=115200,
                            timeout=1,
                            write_timeout=3,
                        )
                        cmd = "id\n"
                        self._ser.write(cmd.encode())
                        reply = self._ser.readline()[0:4].decode()
                        logger.debug(
                            f"Pico KNX2 reply - {reply} (attempt {attempt + 1}/3)",
                        )
                        if reply == "KNX2":
                            cmd = "iv\n"
                            self._ser.write(cmd.encode())
                            self.version = self._ser.readline()[0:4].decode()
                            return True
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after ID mismatch: {close_err}",
                            )
                        finally:
                            self._ser = None
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(0.2)
                    except Exception as e:
                        logger.error(
                            f"Failed to open Pico KNX2 (attempt {attempt + 1}/3) - {e}",
                        )
                        if self._ser is not None:
                            try:
                                self._ser.close()
                            except Exception as close_err:
                                logger.error(
                                    f"Error closing port after exception: {close_err}",
                                )
                            finally:
                                self._ser = None
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(0.2)
        return False

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

    def knx_start(self, rate, ch) -> bool | None:
        try:
            cmd = f"pr{ch}{rate:3d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"6":
                    return True
            else:
                logger.error("failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")

    def knx_three(self, state, ch) -> bool | None:
        try:
            cmd = f"v3{ch}{state:1d}\n"
            print(f"DEBUG knx_three: Sending command: {cmd.strip()!r} (ch={ch}, state={state})")
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                print(f"DEBUG knx_three: Command sent successfully")
                return True
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch) -> bool | None:
        try:
            cmd = f"v6{ch}{state:1d}\n"
            print(f"DEBUG knx_six: Sending command: {cmd.strip()!r} (ch={ch}, state={state})")
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                print(f"DEBUG knx_six: Command sent successfully")
                return True
            logger.error("failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")

    def knx_led(self, led_state, ch) -> None:
        pass  # Green indicator LED for each ch controlled in FW

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

    def __str__(self) -> str:
        return "Pico Carrier Board"


class PicoEZSPR(FlowController):
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
    VALVE_SAFETY_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes safety timeout

    def __init__(self) -> None:
        super().__init__(name="pico_ezspr")
        self._ser = None
        self.version = ""
        self.firmware_id = ""  # Track firmware ID (EZSPR or AFFINITE only)

        # Valve cycle tracking and state monitoring
        self._valve_six_cycles = {1: 0, 2: 0}  # Total cycles per 6-port valve
        self._valve_three_cycles = {1: 0, 2: 0}  # Total cycles per 3-way valve
        self._valve_six_state = {1: None, 2: None}  # Current state (0=load, 1=inject)
        self._valve_three_state = {1: None, 2: None}  # Current state (0=waste, 1=load)

        # 6-port valve safety timeout tracking
        self._valve_six_timers = {1: None, 2: None}  # Active timers for auto-shutoff
        self._valve_six_lock = threading.Lock()  # Thread-safe timer management

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

                # Accept multiple firmware IDs: EZSPR, P4PRO, AFFINITE
                if reply in ("EZSPR", "P4PRO", "AFFINITE") or "AFFINITE" in reply or "P4PRO" in reply:
                    self.firmware_id = reply  # Store for command format selection
                    logger.info(
                        f"[OK] Found Pico EZSPR/P4PRO on {dev.device} (firmware: {reply}, fallback method)",
                    )
                    cmd = "iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.1)
                    self.version = self._ser.readline()[0:4].decode()
                    return True
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
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                return response == b"1"  # P4PRO firmware returns '1' for success
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

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
                        self._valve_six_cycles[ch] += 1
                        logger.debug(f"6-port valve {ch}: cycle {self._valve_six_cycles[ch]} ({old_state}→{state})")
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
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (cycle {self._valve_six_cycles[ch]}) [Safety timeout: {timeout_seconds}s]")
                        else:
                            # No timeout - programmatic operation with calculated contact time
                            self._cancel_valve_timer(ch)
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (cycle {self._valve_six_cycles[ch]})")
                    else:  # Valve turned OFF (LOAD position)
                        self._cancel_valve_timer(ch)
                        logger.info(f"✓ KC{ch} 6-port valve → LOAD (cycle {self._valve_six_cycles[ch]})")

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
                self._ser.write(f"v62{state:1d}\n".encode())
                resp2 = self._ser.read()
                success = resp1 == b"1" and resp2 == b"1"

                if success:
                    # Track state changes and cycles for both valves
                    for ch in [1, 2]:
                        old_state = self._valve_six_state.get(ch)
                        if old_state is not None and old_state != state:
                            self._valve_six_cycles[ch] += 1
                            logger.debug(f"6-port valve {ch}: cycle {self._valve_six_cycles[ch]} ({old_state}→{state})")
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
                            logger.info(f"✓ 6-port valves both set to INJECT (cycles: V1={self._valve_six_cycles[1]}, V2={self._valve_six_cycles[2]}) [Safety timeout: {timeout_seconds}s]")
                        else:
                            # No timeout - programmatic operation with calculated contact time
                            for ch in [1, 2]:
                                self._cancel_valve_timer(ch)
                            logger.info(f"✓ 6-port valves both set to INJECT (cycles: V1={self._valve_six_cycles[1]}, V2={self._valve_six_cycles[2]})")
                    else:  # Valves turned OFF (LOAD position)
                        for ch in [1, 2]:
                            self._cancel_valve_timer(ch)
                        logger.info(f"✓ 6-port valves both set to LOAD (cycles: V1={self._valve_six_cycles[1]}, V2={self._valve_six_cycles[2]})")

                return success
            logger.error("failed to send cmd knx_six_both")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six_both {e}")
            return False

    def knx_three_both(self, state):
        """Set both 3-way valves simultaneously to same state.

        Args:
            state: 0=waste, 1=load

        Returns:
            True if both valves acknowledged, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                # Send both commands back-to-back
                self._ser.write(f"v31{state:1d}\n".encode())
                resp1 = self._ser.read()
                self._ser.write(f"v32{state:1d}\n".encode())
                resp2 = self._ser.read()
                success = resp1 == b"1" and resp2 == b"1"

                if success:
                    # Track state changes and cycles for both valves
                    for ch in [1, 2]:
                        old_state = self._valve_three_state.get(ch)
                        if old_state is not None and old_state != state:
                            self._valve_three_cycles[ch] += 1
                            logger.debug(f"3-way valve {ch}: cycle {self._valve_three_cycles[ch]} ({old_state}→{state})")
                        self._valve_three_state[ch] = state
                    logger.info(f"✓ 3-way valves both set to {'LOAD' if state == 1 else 'WASTE'} (cycles: V1={self._valve_three_cycles[1]}, V2={self._valve_three_cycles[2]})")

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
        """Get valve cycle counts for health monitoring.

        Returns:
            dict with cycle counts for all valves
        """
        return {
            "six_port": dict(self._valve_six_cycles),
            "three_way": dict(self._valve_three_cycles),
            "total_six": sum(self._valve_six_cycles.values()),
            "total_three": sum(self._valve_three_cycles.values()),
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


# ============================================================================
# PicoP4PRO - Standalone P4PRO Controller (4 LEDs + Servo + KNX Valves)
# ============================================================================

class PicoP4PRO(FlowController):
    """P4PRO controller with 4-LED control, servo polarizer, and KNX valve control.

    Hardware Features:
    - 4 LED channels (A, B, C, D) with batch intensity control
    - Servo polarizer (PWM 0-255, uses 'sv' RAM-only command for fast calibration)
    - 6-port valves (2 channels) with cycle tracking and safety timeout
    - 3-way valves (2 channels) with state monitoring

    Firmware: P4PRO V2.1+
    Command Protocol: Uses 'sv' for servo (not 'servo:' to avoid EEPROM writes)
    """

    VALVE_SAFETY_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes safety timeout

    def __init__(self) -> None:
        super().__init__(name="pico_p4pro")
        self._ser = None
        self._servo_s_pos = None  # Loaded from device_config
        self._servo_p_pos = None  # Loaded from device_config
        self.version = ""
        self.firmware_id = "P4PRO"

        # Valve cycle tracking and state monitoring
        self._valve_six_cycles = {1: 0, 2: 0}
        self._valve_three_cycles = {1: 0, 2: 0}
        self._valve_six_state = {1: None, 2: None}
        self._valve_three_state = {1: None, 2: None}

        # 6-port valve safety timeout tracking
        self._valve_six_timers = {1: None, 2: None}
        self._valve_six_lock = threading.Lock()

    def valid(self):
        return (self._ser is not None and self._ser.is_open) or self.open()

    def open(self) -> bool:
        """Open P4PRO controller by scanning for P4PRO firmware ID."""
        logger.info("PicoP4PRO.open() - Looking for VID=0x2e8a PID=0xa")

        # Try VID/PID match first
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                logger.info(f"MATCH! Trying PicoP4PRO on {dev.device}")
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=1,  # 1 second timeout for fast servo/LED response
                        write_timeout=1,
                    )
                    cmd = "id\n"
                    self._ser.write(cmd.encode())
                    reply = self._ser.readline().decode().strip()

                    if reply == "P4PRO" or "P4PRO" in reply:
                        self.firmware_id = reply
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        self.version = self._ser.readline()[0:4].decode()
                        logger.info(f"✅ Found Pico P4PRO firmware: {reply} (version {self.version})")
                        return True
                    else:
                        logger.warning(f"ID mismatch - expected 'P4PRO', got '{reply}'")
                        try:
                            self._ser.close()
                        except Exception:
                            pass
                        self._ser = None
                except Exception as e:
                    logger.error(f"Error connecting to {dev.device}: {e}")
                    if self._ser:
                        try:
                            self._ser.close()
                        except Exception:
                            pass
                        self._ser = None

        logger.warning("No PicoP4PRO found with VID/PID match")
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
        """Enable LED channel.

        NOTE: For P4PRO, use enable_multi_led() instead for proper LED activation.
        This method exists for HAL compatibility but may not work reliably alone.
        """
        return True  # P4PRO prefers enable_multi_led()

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels using lx command."""
        try:
            if self._ser is not None or self.open():
                cmd = "lx\n"
                self._ser.write(cmd.encode())
                time.sleep(0.01)
                resp = self._ser.read(10)
                return resp == b'1'
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
                    resp = self._ser.read(10)

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
                            resp = self._ser.read(10)
                            if resp != b'1':
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
                time.sleep(0.6)  # Wait for servo movement + response (500ms + margin)
                response = self._ser.read(10)

                # P4PRO v2.1 responds with b'\x01\r\n' or b'1\r\n'
                if len(response) > 0 and (b"\x01" in response or b"1" in response):
                    return True
                else:
                    logger.error(f"[P4PRO-SERVO] Move to {degrees}° failed: response={response!r}")
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
        """Set polarizer mode (S or P) using ss/sp firmware commands.

        P4PRO firmware v2.0 uses 'ss' and 'sp' commands to move to stored positions.
        The servo positions must be pre-programmed to flash using the flash command.

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

            # P4PRO firmware uses 'ss' for S-mode, 'sp' for P-mode
            cmd = "ss\n" if mode == 'S' else "sp\n"

            if self._ser is not None or self.open():
                logger.info(f"🔄 Setting P4PRO polarizer to {mode}-mode")
                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.05)
                response = self._ser.read(10)

                # P4PRO responds with b'1' for successful servo move
                if response == b"1" or b"1" in response:
                    logger.info(f"✅ Polarizer set to {mode}-mode")
                    time.sleep(0.5)  # Wait for physical servo movement
                    return True
                else:
                    logger.error(f"[P4PRO-SERVO] Failed to set {mode}-mode: response={response!r}")
                    return False
            return False

        except Exception as e:
            logger.error(f"Error setting polarizer mode: {e}")
            return False

    def set_servo_positions(self, s: int, p: int):
        """Program servo S and P positions to P4PRO firmware flash memory.

        Uses 'sv' command to write positions to EEPROM. These positions are then
        used by 'ss' and 'sp' commands to move the polarizer.

        Args:
            s: S-mode position in degrees (5-175)
            p: P-mode position in degrees (5-175)

        Returns:
            bool: True if flash write successful
        """
        try:
            # Validate positions
            if not (5 <= s <= 175) or not (5 <= p <= 175):
                logger.error(f"Invalid servo positions: S={s}, P={p} (must be 5-175)")
                return False

            # Check if positions already match (avoid unnecessary flash writes and servo movement)
            if hasattr(self, '_servo_s_pos') and hasattr(self, '_servo_p_pos'):
                if self._servo_s_pos == s and self._servo_p_pos == p:
                    logger.debug(f"Servo positions unchanged (S={s}°, P={p}°), skipping flash write")
                    return True

            # P4PRO firmware 'sv' command writes to flash: sv{s:03d}{p:03d}\n
            cmd = f"sv{s:03d}{p:03d}\n"

            if self._ser is not None or self.open():
                logger.info(f"💾 Programming P4PRO servo positions to flash: S={s}°, P={p}°")
                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.1)  # Flash write takes longer
                response = self._ser.read(10)

                if response == b"1" or b"1" in response:
                    self._servo_s_pos = s
                    self._servo_p_pos = p
                    logger.info(f"✅ Servo positions programmed to P4PRO flash")
                    return True
                else:
                    logger.error(f"[P4PRO-FLASH] Failed to program servo positions: response={response!r}")
                    return False
            return False

        except Exception as e:
            logger.error(f"Error programming servo positions: {e}")
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

            # Convert PWM (0-255) to degrees (5-175) for P4PRO sv command
            s_deg = int(5 + (s_pwm * 170 / 255))
            p_deg = int(5 + (p_pwm * 170 / 255))
            s_deg = max(5, min(175, s_deg))
            p_deg = max(5, min(175, p_deg))

            logger.info(f"📝 Writing servo config to P4PRO EEPROM: S={s_pwm} PWM ({s_deg}°), P={p_pwm} PWM ({p_deg}°)")

            # Use existing set_servo_positions method which sends 'sv' command
            success = self.set_servo_positions(s=s_deg, p=p_deg)

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
                success = response == b"1"

                if success:
                    # Track state and cycles
                    old_state = self._valve_six_state.get(ch)
                    if old_state is not None and old_state != state:
                        self._valve_six_cycles[ch] += 1
                    self._valve_six_state[ch] = state

                    # Safety timer management
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
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (cycle {self._valve_six_cycles[ch]}) [Timeout: {timeout_seconds}s]")
                        else:
                            self._cancel_valve_timer(ch)
                            logger.info(f"✓ KC{ch} 6-port valve → INJECT (cycle {self._valve_six_cycles[ch]})")
                    else:  # LOAD
                        self._cancel_valve_timer(ch)
                        logger.info(f"✓ KC{ch} 6-port valve → LOAD (cycle {self._valve_six_cycles[ch]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling 6-port valve {ch}: {e}")
            return False

    def knx_six_both(self, state, timeout_seconds=None):
        """Control both 6-port valves simultaneously."""
        try:
            cmd = f"v6B{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"

                if success:
                    for ch in [1, 2]:
                        old_state = self._valve_six_state.get(ch)
                        if old_state is not None and old_state != state:
                            self._valve_six_cycles[ch] += 1
                        self._valve_six_state[ch] = state

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
                    logger.info(f"✓ Both 6-port valves → {mode} (cycles: V1={self._valve_six_cycles[1]}, V2={self._valve_six_cycles[2]})")

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

                if success:
                    old_state = self._valve_three_state.get(ch)
                    if old_state is not None and old_state != state:
                        self._valve_three_cycles[ch] += 1
                    self._valve_three_state[ch] = state
                    mode = "LOAD" if state == 1 else "WASTE"
                    logger.info(f"✓ KC{ch} 3-way valve → {mode} (cycle {self._valve_three_cycles[ch]})")

                return success
            return False
        except Exception as e:
            logger.error(f"Error controlling 3-way valve {ch}: {e}")
            return False

    def knx_three_both(self, state):
        """Control both 3-way valves simultaneously."""
        try:
            cmd = f"v3B{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                response = self._ser.read()
                success = response == b"1"

                if success:
                    for ch in [1, 2]:
                        old_state = self._valve_three_state.get(ch)
                        if old_state is not None and old_state != state:
                            self._valve_three_cycles[ch] += 1
                        self._valve_three_state[ch] = state
                    mode = "LOAD" if state == 1 else "WASTE"
                    logger.info(f"✓ Both 3-way valves → {mode} (cycles: V1={self._valve_three_cycles[1]}, V2={self._valve_three_cycles[2]})")

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
        """Get valve cycle counts for health monitoring."""
        return {
            "six_port": dict(self._valve_six_cycles),
            "three_way": dict(self._valve_three_cycles),
            "total_six": sum(self._valve_six_cycles.values()),
            "total_three": sum(self._valve_three_cycles.values()),
        }

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
