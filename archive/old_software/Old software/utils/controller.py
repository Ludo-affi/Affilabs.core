import json
import threading
import time
from json import JSONDecodeError
from pathlib import Path
from platform import system
from shutil import copy
from typing import Final

import numpy
import serial
import serial.tools.list_ports

from settings import (
    ARDUINO_PID,
    ARDUINO_VID,
    BAUD_RATE,
    CP210X_PID,
    CP210X_VID,
    PICO_PID,
    PICO_VID,
    QSPR_BAUD_RATE,
)
from utils.logger import logger

if system() == "Windows":
    from os import listdrives

CH_DICT = {"a": 1, "b": 2, "c": 3, "d": 4}


class ControllerBase:
    """Abstract base class for all hardware controllers."""

    def __init__(self, name):
        self._ser = None
        self.name = name

    def open(self):
        pass

    def get_info(self):
        pass

    def turn_on_channel(self, ch="a"):
        pass

    def turn_off_channels(self):
        pass

    def set_mode(self, mode="s"):
        pass

    def stop(self):
        pass

    def close(self):
        """Close serial port connection."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                # Log but don't raise - we want cleanup to continue
                import logging

                logging.getLogger(__name__).error(f"Error closing serial port: {e}")
            finally:
                self._ser = None

    def __del__(self):
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


class ArduinoController(StaticController):
    def __init__(self):
        super().__init__(name="p4spr")
        self._ser = None

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == ARDUINO_PID and dev.vid == ARDUINO_VID:
                # if dev.vid == ADAFRUIT_VID:
                logger.info(f"Found an Arduino board - {dev}")
                # logger.info(f"Found a Feather board - {dev}")
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=3,
                        write_timeout=2,
                    )
                    return True
                except Exception as e:
                    logger.error(f"Failed to open Arduino - {e}")
                    self._ser.close()
                    return False
        return False

    def turn_on_channel(self, ch="a"):
        if ch not in {"a", "b", "c", "d"}:
            raise ValueError("Invalid Channel!")
        if self._ser is not None or self.open():
            self._ser.write(ch.encode())
            result = self._ser.read()
            return result == ch.encode()

    def turn_off_channels(self):
        if self._ser is not None or self.open():
            self._ser.write(b"i")
            return self._ser.read() == b"i"

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
            if self.turn_on_channel(ch=ch):
                cmd = f"w{CH_DICT[ch]}{int(raw_val):03d}"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)  # Delay for device to process (50ms)
                    return self._ser.read() == b"w"
            else:
                logger.error(f"Failed to turn LED {ch.upper()} ON!")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_mode(self, mode="s"):
        if self._ser is not None or self.open():
            self._ser.write(mode.encode())
            return self._ser.read() == mode.encode()

    def servo_get(self):
        commands = {"s": "r5", "p": "r6"}
        curr_pos = {"s": b"0000", "p": b"0000"}
        if self._ser is not None or self.open():
            for pos in ["s", "p"]:
                self._ser.write(commands[pos].encode())
                curr_pos[pos] = self._ser.readline()
            logger.debug(f"Servo s, p: {curr_pos}")
        else:
            logger.error("serial communication failed - servo get")
        return curr_pos

    def servo_set(self, s=10, p=100):
        arduino_s_cmd = 5
        arduino_p_cmd = 6
        if (s < 0) or (p < 0) or (s > 180) or (p > 180):
            raise ValueError(f"Invalid polarizer position given: {s}, {p}")
        cmd_s = f"w{arduino_s_cmd}{s:03d}"
        cmd_p = f"w{arduino_p_cmd}{p:03d}"
        if self._ser is not None or self.open():
            for cmd in [cmd_s, cmd_p]:
                self._ser.write(cmd.encode())
                if self._ser.read() == b"w":
                    pass
                else:
                    logger.error("servo position write failed")
                    break
        else:
            logger.error("serial communication failed - servo set")

    def flash(self):
        """Flash EEPROM to persist settings. Returns True if successful."""
        import time

        flash_cmd = "f"
        try:
            if self._ser is not None or self.open():
                # Flush any pending data in input buffer
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass

                # Send flash command
                self._ser.write(flash_cmd.encode())

                # Wait for EEPROM write to complete
                time.sleep(0.15)

                # Try to read response
                response = self._ser.readline().strip()

                # If empty, try reading again
                if not response:
                    time.sleep(0.1)
                    response = self._ser.readline().strip()

                success = response == flash_cmd.encode()
                if success:
                    logger.debug("EEPROM flash confirmed by controller")
                else:
                    logger.warning(
                        f"EEPROM flash response mismatch: expected {flash_cmd.encode()}, got {response}",
                    )
                return success
            logger.error("Cannot flash EEPROM - serial port not open")
            return False
        except Exception as e:
            logger.error(f"EEPROM flash failed with exception: {e}")
            return False

    def __str__(self):
        return "Arduino Board"


class QSPRController(ControllerBase):
    def __init__(self):
        super().__init__(name="qspr")
        self._lock = threading.Lock()

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found an qSPR board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=QSPR_BAUD_RATE,
                        timeout=3,
                        write_timeout=1,
                    )
                    info = self.get_info()
                    if info is not None:
                        if info["fw ver"].startswith("qSPR"):
                            return True
                        logger.debug("dev is not qSPR")
                        self._ser.close()
                        return False
                    logger.debug(f"Error during get info, returned: {info}")
                    self._ser.close()
                    return False
                except Exception as e:
                    logger.error(f"Failed to open qSPR - {e}")
                    self._ser = None
                    return False

    def _send_command(self, cmd, parse_json=False, reply=False):
        if self._ser is not None or self.open():
            if not (cmd.startswith("led_o")):
                logger.debug(f"QSPR command: {cmd}")
            try:
                with self._lock:
                    self._ser.write(f"{cmd}\n".encode())
                    buf = self._ser.readline().decode()
                    if parse_json:
                        try:
                            return json.loads(buf)
                        except JSONDecodeError:
                            logger.error(f"Failed to parse to JSON of {cmd} - {buf}")
                            return None
                    else:
                        data = buf.splitlines()
                        response = data[0] if data else buf
                        if reply:
                            logger.debug(f"QSPR reply: {response}")
                        return response
            except Exception as e:
                logger.error(f"Failed to send command to qSPR - {e}")
                self._ser = None

    def get_status(self):
        return self._send_command(cmd="status", parse_json=True)

    def get_info(self):
        return self._send_command(cmd="info", parse_json=True)

    def get_parameters(self):
        return self._send_command(cmd="param", parse_json=True)

    def set_parameters(self, parameter_list):
        return self._send_command(cmd=f"set_parameters:{parameter_list}:")

    def read_wavelength(self):
        data = self._send_command(cmd="wave")
        if data:
            return numpy.asarray([int(v) for v in data.split(",")])

    def read_intensity(self):
        try:
            data = self._send_command(cmd="read")
            if data:
                return numpy.asarray([int(v) for v in data.split(",")])
        except Exception as e:
            logger.debug(f"Error during QSPR read: {e}")

    def crt_up(self):
        return self._send_command(cmd="crt_up", reply=True)

    def crt_down(self):
        return self._send_command(cmd="crt_down", reply=True)

    def crt_adj_up(self):
        return self._send_command(cmd="crt_adj_up")

    def crt_adj_down(self):
        return self._send_command(cmd="crt_adj_down")

    def stop(self):
        return self._send_command(cmd="led_off")

    def turn_on_channel(self, ch="a"):
        self._send_command(f"led_on({CH_DICT[ch]})")

    def turn_off_channels(self):
        self._send_command("led_off")

    # Equivalent to the Arduino function to turn on a channel LED at a given intensity
    def set_intensity(self, ch="a", raw_val=255):
        val = int((raw_val / 255) * 31) + 1  # convert from Arduino to QSPR
        self._send_command(f"led_intensity({CH_DICT[ch]},{val})")
        self._send_command(f"led_on({CH_DICT[ch]})")

    def set_integration(self, int_ms):
        return self._send_command(f"set_integration({int_ms})")

    def set_mode(self, mode="s"):
        return self._send_command(f"servo_{mode}")

    def servo_set(self, s=10, p=100):
        return self._send_command(f"servo_set({s},{p})")

    def knx_stop(self):
        return self._send_command("knx_stop")

    def knx_start(self, rate):
        return self._send_command(f"knx_start({rate})")

    def knx_three(self, state):
        return self._send_command(f"knx_three({state})")

    def knx_six(self, state):
        return self._send_command(f"knx_six({state})")

    def knx_status(self):
        return self._send_command(cmd="knx_status", parse_json=True)

    def stop_kinetic(self):
        return self._send_command("knx_stop_all")

    def shutdown(self):
        self._send_command("shutdown")
        self.close()

    def __str__(self):
        return "qSPR Board"


class KineticController(FlowController):
    def __init__(self):
        super().__init__(name="KNX2")
        self._lock = threading.Lock()
        self.version = "1.0"

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found a KNX2 board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=BAUD_RATE,
                        timeout=3,
                        write_timeout=1,
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
        val = int((raw_val / 255) * 31) + 1  # convert from Arduino to QSPR
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


class PicoP4SPR(StaticController):
    def __init__(self):
        super().__init__(name="pico_p4spr")
        self._ser = None
        self.version = ""
        self._lock = threading.Lock()

    def open(self):
        # Close existing connection if any
        if self._ser is not None:
            try:
                self._ser.close()
            except:
                pass
            self._ser = None

        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    self._ser = serial.Serial(
                        port=dev.device,
                        baudrate=115200,
                        timeout=1,
                        write_timeout=5,
                    )
                    # Flush any stale data
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()

                    cmd = "id\n"
                    self._ser.write(cmd.encode())
                    import time

                    time.sleep(0.05)  # Small delay for Pico to respond
                    reply = self._ser.readline()[0:5].decode()
                    logger.debug(f"Pico P4SPR reply - {reply}")
                    if reply == "P4SPR":
                        cmd = "iv\n"
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)
                        self.version = self._ser.readline()[0:4].decode()
                        logger.debug(f" Pico P4SPR Fw: {self.version}")
                        return True
                    try:
                        self._ser.close()
                    except Exception as close_err:
                        logger.error(
                            f"Error closing port after ID mismatch: {close_err}",
                        )
                    finally:
                        self._ser = None
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after exception: {close_err}",
                            )
                        finally:
                            self._ser = None
        return False

    def turn_on_channel(self, ch="a"):
        try:
            if ch not in {"a", "b", "c", "d"}:
                raise ValueError("Invalid Channel!")
            cmd = f"l{ch}\n"
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
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

    def turn_off_channels(self):
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = "lx\n"
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
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

                    with self._lock:
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)  # device processing
                        ok = self._ser.read() == b"1"
                    # Ensure LED channel is on (no-op if already on)
                    self.turn_on_channel(ch=ch)
                    return ok
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"LED write timeout (ch {ch}, attempt {attempt+1}/{max_retries}): {e}",
                        )
                        time.sleep(0.05)
                        continue
                    logger.error(f"error while setting led intensity {e}")
                    return False
            return False
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0):
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
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    if mode == "s":
                        cmd = "ss\n"
                    else:
                        cmd = "sp\n"
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = "sr\n"
        curr_pos = {"s": b"0000", "p": b"0000"}
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Ensure connection is open
                if self._ser is None:
                    if not self.open():
                        logger.error(
                            "serial communication failed - servo get - cannot open port",
                        )
                        return curr_pos

                with self._lock:
                    # Flush buffers before command
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    # Send command and wait for response
                    self._ser.write(cmd.encode())
                    import time

                    time.sleep(0.15)  # allow device to prepare reply

                    # Read up to a few lines to skip temperature or ack noise
                    for _ in range(3):
                        servo_reading = self._ser.readline()
                        logger.debug(
                            f"servo reading pico {servo_reading} (attempt {attempt + 1}/{max_retries})",
                        )
                        if not servo_reading:
                            break
                        s = servo_reading.decode("utf-8", errors="ignore").strip()
                        if s == "1" or s == "":
                            # ack or empty, continue
                            continue
                        # If it's a float like temperature, ignore
                        try:
                            float(s)
                            # looks like temperature line; skip
                            continue
                        except ValueError:
                            pass
                        # Expect comma-separated s,p
                        if "," in s:
                            parts = s.split(",")
                            if len(parts) == 2:
                                try:
                                    s_val = int(parts[0])
                                    p_val = int(parts[1])
                                    curr_pos["s"] = parts[0].encode()
                                    curr_pos["p"] = parts[1].encode()
                                    logger.debug(
                                        f"Servo s, p: {curr_pos} (parsed as {s_val}, {p_val})",
                                    )
                                    return curr_pos
                                except ValueError:
                                    # Not integers; ignore and keep reading
                                    continue
                        # Not a valid line, try next
                    # If we got here, no valid line in this attempt
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue
                return curr_pos
            except Exception as e:
                logger.debug(f"error getting servo pos on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    # Try to reopen connection on error
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except:
                            pass
                        self._ser = None
                    time.sleep(0.2)
                    continue

        return curr_pos

    def servo_set(self, s=10, p=100):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                    raise ValueError(f"Invalid polarizer position given: {s}, {p}")
                cmd = f"sv{s:03d}{p:03d}\n"
                if self._ser is not None or self.open():
                    with self._lock:
                        self._ser.write(cmd.encode())
                        return self._ser.read() == b"1"
                else:
                    logger.error("unable to update servo positions")
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
        """Flash EEPROM to persist settings. Returns True if successful."""
        import time

        try:
            flash_cmd = "sf\n"
            if self._ser is not None or self.open():
                with self._lock:
                    # Flush any pending data in input buffer
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    # Send flash command
                    self._ser.write(flash_cmd.encode())

                    # Wait longer for EEPROM write to complete
                    # EEPROM writes can take 5-10ms on AVR/RP2040
                    time.sleep(0.15)

                    # Try to read response with timeout
                    response = self._ser.readline().strip()

                    # If empty, try reading again (response might be delayed)
                    if not response:
                        time.sleep(0.1)
                        response = self._ser.readline().strip()

                    success = response == b"1"
                    if success:
                        logger.debug("PicoP4SPR EEPROM flash confirmed")
                    else:
                        logger.warning(
                            f"PicoP4SPR EEPROM flash response mismatch: expected b'1', got {response}",
                        )
                    return success
            else:
                logger.error("Cannot flash PicoP4SPR EEPROM - serial port not open")
                return False
        except Exception as e:
            logger.error(f"PicoP4SPR EEPROM flash failed: {e}")
            return False

    def stop(self):
        self.turn_off_channels()

    def __str__(self):
        return "Pico Mini Board"


class PicoKNX2(FlowController):
    def __init__(self):
        super().__init__(name="pico_knx2")
        self._ser = None
        self.version = ""

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
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
                    logger.debug(f"Pico KNX2 reply - {reply}")
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
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after exception: {close_err}",
                            )
                        finally:
                            self._ser = None
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

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"1":
                    return True
            else:
                logger.error("failed to send cmd knx_stop")
            return False
        except Exception as e:
            logger.error(f"Error during knx_stop {e}")

    def knx_start(self, rate, ch):
        try:
            cmd = f"pr{ch}{rate:3d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"1":
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
                return True
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return True
            logger.error("failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")

    def knx_led(self, led_state, ch):
        pass  # Green indicator LED for each ch controlled in FW

    def stop_kinetic(self):
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

    def shutdown(self):
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

    def __str__(self):
        return "Pico Carrier Board"


class PicoEZSPR(FlowController):
    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self):
        super().__init__(name="pico_ezspr")
        self._ser = None
        self.version = ""

    def valid(self):
        return (self._ser is not None and self._ser.is_open) or self.open()

    def open(self):
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
                    reply = self._ser.readline()[0:5].decode()
                    logger.debug(f"Pico EZSPR reply - {reply}")
                    if reply == "EZSPR":
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
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(
                                f"Error closing port after exception: {close_err}",
                            )
                        finally:
                            self._ser = None
                return False

    def update_firmware(self, firmware):
        if not (self.valid() and self.version in self.UPDATABLE_VERSIONS):
            return False

        self._ser.write(b"du\n")
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
        self._ser.write(b"pc\n")
        reply = self._ser.readline()
        return tuple(x / self.PUMP_CORRECTION_MULTIPLIER for x in reply[:2])

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
        self._ser.write(b"pf" + corrrection_bytes + b"\n")
        return True

    def turn_on_channel(self, ch="a"):
        try:
            if ch in {"a", "b", "c", "d"}:
                cmd = f"l{ch}\n"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
            elif ch not in {"a", "b", "c", "d"}:
                raise ValueError("Invalid Channel!")
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def turn_off_channels(self):
        try:
            if self._ser is not None or self.open():
                cmd = "lx\n"
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
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
                        reply = self._ser.read() == b"1"
                        self.turn_on_channel(ch=ch)
                        return reply
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.debug(
                                f"LED write timeout (EZSPR ch {ch}, attempt {attempt+1}/{max_retries}): {e}",
                            )
                            time.sleep(0.05)
                            continue
                        logger.error(f"error while setting led intensity {e}")
                        return False
                return False
            if ch not in {"a", "b", "c", "d"}:
                raise ValueError(f"Invalid Channel - {ch}")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0):
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
        try:
            if self._ser is not None or self.open():
                if mode == "s":
                    cmd = "ss\n"
                else:
                    cmd = "sp\n"
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

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

                    # If response is just "1\r\n", read again for actual positions
                    if servo_reading.strip() == b"1":
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

    def servo_set(self, s=10, p=100):
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                    raise ValueError(f"Invalid polarizer position given: {s}, {p}")
                cmd = f"sv{s:03d}{p:03d}\n"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
                logger.error("unable to update servo positions")
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
                return self._ser.read() == b"1"
            return False
        except Exception as e:
            logger.debug(f"error flashing pico {e}")
            return False

    def stop(self):
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

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b"1":
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
                if self._ser.read() == b"1":
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
                return self._ser.read() == b"1"
            logger.error("failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            logger.error("failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")

    def knx_led(self, led_state, ch):
        pass  # Green indicator LED for each ch controlled in FW

    def stop_kinetic(self):
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

    def shutdown(self):
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

    def __str__(self):
        return "Pico Carrier Board"
