from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from platform import system
from shutil import copy
from typing import Any, Final

import numpy
import serial
import serial.tools.list_ports

from settings import BAUD_RATE, CP210X_PID, CP210X_VID, PICO_PID, PICO_VID
from utils.logger import logger

# ===== IMPROVED TYPES AND CONSTANTS =====


class ChannelID(Enum):
    """LED channel identifiers with their numeric values."""

    A = 1
    B = 2
    C = 3
    D = 4


@dataclass
class DeviceInfo:
    """Device information structure."""

    name: str
    firmware_version: str
    hardware_version: str = ""


class ControllerError(Exception):
    """Base exception for controller-related errors."""


class SerialCommunicationError(ControllerError):
    """Exception raised for serial communication failures."""


if system() == "Windows":
    try:
        from os import listdrives
    except ImportError:
        # listdrives doesn't exist in newer Python versions
        # We'll create a fallback function if needed
        def listdrives():
            import os
            import string

            drives = []
            for letter in string.ascii_uppercase:
                if os.path.exists(f"{letter}:\\"):
                    drives.append(f"{letter}:\\")
            return drives


CH_DICT = {"a": 1, "b": 2, "c": 3, "d": 4}


class ControllerBase:
    """Base class for hardware controllers with improved serial communication."""

    def __init__(self, name: str):
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()
        self.name = name

    def open(self) -> bool:
        return False

    def valid(self) -> bool:
        """Return True if serial port is open or can be opened.

        Subclasses may override open(); this helper avoids writes to a closed
        or stale handle which can raise PermissionError on Windows after a
        disconnect.
        """
        try:
            return (
                self._ser is not None and getattr(self._ser, "is_open", False)
            ) or self.open()
        except Exception:
            return False

    @contextmanager
    def _safe_serial_context(self):
        """Context manager for safe serial operations with proper locking and error handling."""
        if self._ser is None:
            raise SerialCommunicationError("Serial port not open")

        with self._lock:
            try:
                yield self._ser
            except serial.SerialException as e:
                logger.error(f"Serial communication error: {e}")
                self._ser = None
                raise SerialCommunicationError(f"Serial operation failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in serial operation: {e}")
                raise ControllerError(f"Serial operation failed: {e}")

    def safe_write(self, data: str | bytes) -> bool:
        """Safely write data to serial port with proper error handling."""
        try:
            with self._safe_serial_context() as ser:
                if isinstance(data, str):
                    data = data.encode()
                ser.write(data)
                return True
        except (SerialCommunicationError, ControllerError):
            return False

    def safe_read(self, size: int = 1) -> bytes:
        """Safely read data from serial port with proper error handling."""
        try:
            with self._safe_serial_context() as ser:
                return ser.read(size)
        except (SerialCommunicationError, ControllerError):
            return b""

    def safe_readline(self) -> str:
        """Safely read a line from serial port with proper error handling."""
        try:
            with self._safe_serial_context() as ser:
                return ser.readline().decode().strip()
        except (SerialCommunicationError, ControllerError):
            return ""

    def safe_reset_input_buffer(self) -> None:
        """Safely reset serial input buffer with proper error handling."""
        try:
            with self._safe_serial_context() as ser:
                ser.reset_input_buffer()
        except (SerialCommunicationError, ControllerError):
            pass

    def get_info(self) -> Any:
        return None

    def turn_on_channel(self, ch: str = "a") -> Any:
        return None

    def turn_off_channels(self) -> Any:
        return None

    def set_mode(self, mode: str = "s") -> Any:
        return None

    def stop(self) -> Any:
        return None

    def close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                logger.warning(f"Error closing serial port: {e}")
            finally:
                self._ser = None


class KineticController(ControllerBase):
    def __init__(self):
        super().__init__(name="KNX2")
        self._lock = threading.Lock()
        self.version = "1.0"

    def open(self) -> bool:
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found a KNX2 board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(
                        port=dev.device, baudrate=BAUD_RATE, timeout=3
                    )
                    info = self.get_info()
                    if info is not None:
                        if info["fw ver"].startswith("KNX2"):
                            if info["fw ver"].startswith("KNX2 V1.1"):
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
        return False

    def _send_command(
        self, cmd: str, parse_json: bool = False, reply: bool = True
    ) -> Any:
        """Send command with improved error handling and type safety."""
        if not self.valid():
            logger.warning(
                f"Attempted to send command '{cmd}' to disconnected {self.name}"
            )
            return None

        logger.debug(f"{self.name}: Sending command - '{cmd}'")

        if not self.safe_write(f"{cmd}\n"):
            logger.error(f"Failed to write command '{cmd}' to {self.name}")
            return None

        if not reply:
            return True

        response = self.safe_readline()
        if not response:
            logger.warning(f"No response received for command '{cmd}' from {self.name}")
            return None

        if parse_json:
            try:
                return json.loads(response)
            except JSONDecodeError as e:
                logger.error(
                    f"Failed to parse JSON response for '{cmd}': {response} - {e}"
                )
                return None

        return response

    def get_status(self):
        return self._send_command(cmd="get_status", parse_json=True)

    def get_info(self):
        return self._send_command(cmd="get_info", parse_json=True)

    def get_parameters(self):
        return self._send_command(cmd="get_parameters", parse_json=True)

    def read_wavelength(self, channel):
        data = self._send_command(cmd=f"read{channel}")
        if data:
            return numpy.asarray([int(v) for v in data.split(",")])

    def read_intensity(self):
        data = self._send_command(cmd="intensity")
        if data:
            return numpy.asarray([int(v) for v in data.split(",")])

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

    def stop_kinetic(self):
        self._send_command("knx_stop_all")

    def shutdown(self):
        self._send_command("shutdown")
        self.close()

    def __str__(self):
        return "KNX2 Board"


class PicoP4SPR(ControllerBase):
    def __init__(self):
        super().__init__(name="pico_p4spr")
        self._ser = None
        self.version = ""

    def open(self):
        for dev in serial.tools.list_ports.comports():
            # Log candidate ports
            try:
                logger.debug(
                    f"Checking port {dev.device} {getattr(dev, 'vid', None)}:{getattr(dev, 'pid', None)} - {dev.description} - {getattr(dev, 'hwid', '')}",
                )
            except Exception:
                logger.debug(f"Checking port {dev.device} - {dev.description}")

            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                # Prefer the CDC interface (MI_00) when present
                try:
                    hwid = getattr(dev, "hwid", "")
                    # If an interface marker is present (MI_XX) and it's not MI_00, skip it
                    if "MI_" in hwid and "MI_00" not in hwid:
                        logger.debug(
                            f"Skipping non-CDC interface on {dev.device} (hwid={hwid})"
                        )
                        continue
                except Exception:
                    pass
                try:
                    # Open with a slightly longer timeout for first handshake
                    self._ser = serial.Serial(
                        port=dev.device, baudrate=115200, timeout=3, write_timeout=2
                    )

                    # Many CDC firmwares only respond when DTR is asserted; assert DTR
                    with suppress(Exception):
                        # brief toggle to signal host ready
                        self._ser.dtr = False
                        time.sleep(0.02)
                        self._ser.dtr = True
                        # keep RTS low unless required
                        self._ser.rts = False

                    # Give the device a moment and clear buffers
                    time.sleep(0.15)
                    with suppress(Exception):
                        self._ser.reset_input_buffer()
                        self._ser.reset_output_buffer()

                    # Try ID up to 5 times
                    ok = False
                    for _ in range(5):
                        # Some firmwares expect CRLF
                        self._ser.write(b"id\r\n")
                        time.sleep(0.15)
                        # Prefer read-until-newline, but fall back to reading whatever is buffered
                        line = self._ser.readline()
                        if not line:
                            with suppress(Exception):
                                waiting = self._ser.in_waiting
                                if waiting:
                                    line = self._ser.read(waiting)
                        reply = line.decode(errors="ignore").strip()
                        logger.debug(f"Pico P4SPR reply - {reply}")
                        if "P4SPR" in reply:
                            ok = True
                            break
                        time.sleep(0.2)

                    if ok:
                        self._ser.write(b"iv\r\n")
                        time.sleep(0.1)
                        v_raw = self._ser.readline()
                        v = v_raw.decode(errors="ignore").strip()
                        self.version = v[0:4] if v else ""
                        return True
                    logger.debug(
                        "Pico present but did not return expected ID; closing port"
                    )
                    self._ser.close()
                    self._ser = None
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception:
                            pass
                        self._ser = None
        return False

    def turn_on_channel(self, ch="a"):
        try:
            if ch not in {"a", "b", "c", "d"}:
                raise ValueError("Invalid Channel!")
            cmd = f"l{ch}\n"
            if self.valid():
                try:
                    if not self.safe_write(cmd):
                        return False
                    return self.safe_read() == b"1"
                except PermissionError:
                    # Device likely disconnected; avoid noisy logs
                    return False
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def get_temp(self):
        """Read controller temperature.

        Tolerates blank/newline-only replies by retrying briefly and returns -1
        without logging in that benign case to reduce log noise.
        """
        try:
            if not self.valid():
                return -1
            # Clear any stale bytes to avoid parsing leftovers
            self.safe_reset_input_buffer()
            if not self.safe_write(b"it\n"):
                return -1
            for _ in range(3):
                line_str = self.safe_readline()
                if not line_str:
                    # Skip empty lines
                    continue
                try:
                    # Limit precision to avoid long strings like '23.45678'
                    val = float(line_str)
                    return val
                except ValueError:
                    # Non-empty but not a float; log once and break
                    logger.debug(f"temp value not readable '{line_str}'")
                    break
            return -1
        except PermissionError:
            return -1
        except Exception:
            return -1

    def turn_off_channels(self):
        try:
            if not self.valid():
                return False
            cmd = "lx\n"
            try:
                if not self.safe_write(cmd):
                    return False
                return self.safe_read() == b"1"
            except PermissionError:
                # Device likely disconnected; avoid noisy logs
                return False
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def set_intensity(self, ch="a", raw_val=1):
        try:
            if ch not in {"a", "b", "c", "d"}:
                raise ValueError(f"Invalid Channel - {ch}")
            # error bounding: P4SPR LED intensity range is 0-255
            if raw_val > 255:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 255
            elif raw_val < 0:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 0

            cmd = f"b{ch}{int(raw_val):03d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error(f"pico failed to write LED command for channel {ch}")
                    return False
                reply = self.safe_read() == b"1"
                self.turn_on_channel(ch=ch)
                return reply
            logger.error(f"pico failed to turn LED {ch} ON")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0):
        """Set all LED intensities in a single batch command.

        This method uses the Pico's batch command format to set all 4 LED
        intensities simultaneously, providing ~15x speedup over sequential
        individual commands (discovered via pico_batch_command_diagnostic.py).

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

            # Format: batch:A,B,C,D\n
            cmd = f"batch:{a},{b},{c},{d}\n"

            if self.valid():
                if not self.safe_write(cmd):
                    logger.error(f"pico failed to write batch LED command")
                    return False

                # The Pico's batch command may not send explicit acknowledgment
                # or may send just a carriage return. Based on diagnostic testing,
                # the command executes successfully even with minimal/no response.
                # We consider the write success as command success.
                return True
            else:
                logger.error("pico serial port not valid for batch command")
                return False

        except Exception as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            return False

    def set_mode(self, mode="s"):
        try:
            if self.valid():
                if mode == "s":
                    cmd = "ss\n"
                else:
                    cmd = "sp\n"
                try:
                    if not self.safe_write(cmd):
                        return False
                    return self.safe_read() == b"1"
                except PermissionError:
                    return False
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = "sr\n"
        curr_pos = {"s": b"000", "p": b"000"}
        try:
            if self.valid():
                # Flush any leftover bytes (e.g., from previous commands) to avoid misreads
                self.safe_reset_input_buffer()
                if not self.safe_write(cmd):
                    logger.error("Failed to write servo get command")
                    return curr_pos

                # Read up to a few lines until we find a line like "ddd,ddd"
                line_str = ""
                for _ in range(3):
                    line_str = self.safe_readline()
                    logger.debug(f"servo reading pico {line_str}")
                    if (
                        len(line_str) >= 7
                        and line_str[0:3].isdigit()
                        and line_str[3:4] == ","
                        and line_str[4:7].isdigit()
                    ):
                        break
                # Parse if valid
                if (
                    len(line_str) >= 7
                    and line_str[0:3].isdigit()
                    and line_str[3:4] == ","
                    and line_str[4:7].isdigit()
                ):
                    curr_pos["s"] = line_str[0:3].encode()
                    curr_pos["p"] = line_str[4:7].encode()
                    logger.debug(f"Servo s, p: {curr_pos}")
                else:
                    logger.error(f"Unexpected servo reply: {line_str!r}")
            else:
                logger.error("serial communication failed - servo get")
        except Exception as e:
            logger.debug(f"error getting servo pos {e}")
        return curr_pos

    def servo_set(self, s=10, p=100):
        try:
            if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                raise ValueError(f"Invalid polarizer position given: {s}, {p}")
            cmd = f"sv{s:03d}{p:03d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    return False
                return self.safe_read() == b"1"
            logger.error("unable to update servo positions")
            return False
        except Exception as e:
            logger.debug(f"error setting servo position {e}")
            return False

    def flash(self):
        try:
            flash_cmd = "sf\n"
            if self.valid():
                try:
                    if not self.safe_write(flash_cmd):
                        return False
                    return self.safe_read() == b"1"
                except PermissionError:
                    return False
            else:
                return False
        except Exception as e:
            logger.debug(f"error flashing pico {e}")
            return False

    def stop(self):
        self.turn_off_channels()

    def __str__(self):
        return "Pico Mini Board"


class PicoEZSPR(ControllerBase):
    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self):
        super().__init__(name="pico_ezspr")
        self._ser = None
        self.version = ""

    def valid(self) -> bool:
        if self._ser is not None and self._ser.is_open:
            return True
        return bool(self.open())

    def open(self) -> bool:
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    self._ser = serial.Serial(
                        port=dev.device, baudrate=115200, timeout=5
                    )
                    cmd = "id\n"
                    self._ser.write(cmd.encode())
                    reply = self._ser.readline()[0:5].decode()
                    logger.debug(f"Pico EZSPR reply - {reply}")
                    if reply == "EZSPR":
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        self.version = self._ser.readline()[0:4].decode()
                        return True
                    self._ser.close()
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        self._ser.close()
        return False

    def update_firmware(self, firmware):
        if not (self.valid() and self.version in self.UPDATABLE_VERSIONS):
            return False

        if not self.safe_write(b"du\n"):
            return False
        self.close()

        now = time.monotonic_ns()
        timeout = now + 5_000_000_000
        while now <= timeout:
            try:
                pico_drive = next(
                    d for d in listdrives() if (Path(d) / "INFO_UF2.TXT").exists()
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
        if not self.safe_write(b"pc\n"):
            return None
        reply = self.safe_readline()
        if reply:
            try:
                reply_bytes = reply.encode()[:2]
                return tuple(x / self.PUMP_CORRECTION_MULTIPLIER for x in reply_bytes)
            except Exception:
                return None
        return None

    def set_pump_corrections(self, pump_1_correction, pump_2_correction):
        if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
            return False
        corrections = pump_1_correction, pump_2_correction
        try:
            corrrection_bytes = bytes(
                round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections
            )
        except ValueError:
            return False
        return self.safe_write(b"pf" + corrrection_bytes + b"\n")

    def turn_on_channel(self, ch="a"):
        try:
            if ch in {"a", "b", "c", "d"}:
                cmd = f"l{ch}\n"
                if self.valid():
                    try:
                        if not self.safe_write(cmd):
                            return False
                        return self.safe_read() == b"1"
                    except PermissionError:
                        return False
            elif ch not in {"a", "b", "c", "d"}:
                raise ValueError("Invalid Channel!")
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def turn_off_channels(self):
        try:
            if not self.valid():
                return False
            cmd = "lx\n"
            try:
                if not self.safe_write(cmd):
                    return False
                return self.safe_read() == b"1"
            except PermissionError:
                return False
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
                if self.valid():
                    if not self.safe_write(cmd):
                        return False
                    reply = self.safe_read() == b"1"
                    self.turn_on_channel(ch=ch)
                    return reply
                logger.error(f"pico failed to turn LED {ch} ON")
            elif ch not in {"a", "b", "c", "d"}:
                raise ValueError(f"Invalid Channel - {ch}")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_mode(self, mode="s"):
        try:
            if self.valid():
                if mode == "s":
                    cmd = "ss\n"
                else:
                    cmd = "sp\n"
                try:
                    if not self.safe_write(cmd):
                        return False
                    return self.safe_read() == b"1"
                except PermissionError:
                    return False
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = "sr\n"
        curr_pos = {"s": b"0000", "p": b"0000"}
        try:
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("Failed to write servo get command")
                    return curr_pos
                servo_reading = self.safe_readline()
                logger.debug(f"servo reading pico {servo_reading}")
                if len(servo_reading) >= 7:
                    curr_pos["s"] = servo_reading[0:3].encode()
                    curr_pos["p"] = servo_reading[4:7].encode()
                logger.debug(f"Servo s, p: {curr_pos}")
            else:
                logger.error("serial communication failed - servo get")
        except Exception as e:
            logger.debug(f"error getting servo pos {e}")
        return curr_pos

    def servo_set(self, s=10, p=100):
        try:
            if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                raise ValueError(f"Invalid polarizer position given: {s}, {p}")
            cmd = f"sv{s:03d}{p:03d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    return False
                return self.safe_read() == b"1"
            logger.error("unable to update servo positions")
            return False
        except Exception as e:
            logger.debug(f"error setting servo position {e}")
            return False

    def flash(self):
        try:
            flash_cmd = "sf\n"
            if self.valid():
                try:
                    if not self.safe_write(flash_cmd):
                        return False
                    return self.safe_read() == b"1"
                except PermissionError:
                    return False
            else:
                return False
        except Exception as e:
            logger.debug(f"error flashing pico {e}")
            return False

    def stop(self):
        self.turn_off_channels()

    def get_status(self):
        try:
            if not self.valid():
                return -1
            self.safe_reset_input_buffer()
            if not self.safe_write(b"it\n"):
                return -1
            for _ in range(3):
                line_str = self.safe_readline()
                if not line_str:
                    continue
                try:
                    return float(line_str)
                except ValueError:
                    logger.debug(f"temp value not readable '{line_str}'")
                    break
            return -1
        except PermissionError:
            return -1
        except Exception:
            return -1

    def knx_status(self, ch):
        status: dict[str, float] = {"flow": 0.0, "temp": 0.0, "6P": 0.0, "3W": 0.0}
        try:
            cmd = f"ks{ch}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("failed to send cmd knx_status")
                    return status
                data_str = self.safe_readline()
                if data_str:
                    data = data_str.rstrip("\r\n").split(",")
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
            return status

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("failed to send cmd knx_stop")
                    return False
                return self.safe_read() == b"1"
            logger.error("failed to send cmd knx_stop")
            return False
        except Exception as e:
            logger.error(f"Error during knx_stop {e}")
            return False

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
                    if not self.safe_write(f"pr1{round(rate * c[0]):3d}\n"):
                        return False
                    if not self.safe_write(f"pr2{round(rate * c[1]):3d}\n"):
                        return False
                    return self.safe_read(2) == b"11"
            cmd = f"pr{ch}{round(rate):3d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("failed to send cmd knx_start")
                    return False
                return self.safe_read() == b"1"
            logger.error("failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")
            return False

    def knx_three(self, state, ch):
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("failed to send cmd knx_three")
                    return False
                return self.safe_read() == b"1"
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")
            return False

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("failed to send cmd knx_six")
                    return False
                return self.safe_read() == b"1"
            logger.error("failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")
            return False

    def knx_led(self, led_state, ch):
        pass  # Green indicator LED for each ch controlled in FW

    def stop_kinetic(self):
        try:
            cmds = ["ps3\n", "v330\n", "v630\n"]
            if self.valid():
                er = False
                for cmd in cmds:
                    if not self.safe_write(cmd) or not (self.safe_read() == b"1"):
                        er = True
                if er:
                    logger.error("pico failed to confirm kinetics off")
            else:
                logger.error("pico failed to turn kinetics off")
        except Exception as e:
            logger.error(f"error while shutting down kinetics {e}")

    def shutdown(self):
        try:
            cmd = "do\n"
            if self.valid():
                if not self.safe_write(cmd):
                    logger.error("pico failed to turn device off")
                elif not (self.safe_read() == b"1"):
                    logger.error("pico failed to confirm device off")
            else:
                logger.error("pico failed to turn device off")
        except Exception as e:
            logger.error(f"error while shutting down device {e}")

    def get_info(self):
        return self.name

    def get_temp(self):
        try:
            if not self.valid():
                return -1
            self.safe_reset_input_buffer()
            if not self.safe_write(b"it\n"):
                return -1
            for _ in range(3):
                line_str = self.safe_readline()
                if not line_str:
                    continue
                try:
                    return float(line_str)
                except ValueError:
                    logger.debug(f"temp value not readable '{line_str}'")
                    break
            return -1
        except PermissionError:
            return -1
        except Exception:
            return -1

    def __str__(self):
        return "Pico Carrier Board"


# ----------------------
# Convenience factory API
# ----------------------
def get_controller():
    """Return the first available controller instance.

    Tries PicoP4SPR, PicoEZSPR, then KNX2. Returns a connected instance
    or None if nothing is available.
    """
    try_order = (PicoP4SPR, PicoEZSPR, KineticController)
    for cls in try_order:
        try:
            c = cls()
            if c.open():
                logger.info(f"Connected to controller: {c}")
                return c
        except Exception as e:
            logger.debug(f"Controller {cls.__name__} not available: {e}")
            continue
    logger.error("No controller detected. Connect device and try again.")
    return None
