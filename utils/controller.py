import json
import threading
import time
from json import JSONDecodeError
from pathlib import Path
from platform import system
from shutil import copy
from typing import Final
from contextlib import suppress

import numpy
import serial
import serial.tools.list_ports

from settings import ARDUINO_VID, ARDUINO_PID, CP210X_PID, CP210X_VID, BAUD_RATE, ADAFRUIT_VID, \
    PICO_VID, PICO_PID
from utils.logger import logger

if system() == "Windows":
    try:
        from os import listdrives
    except ImportError:
        # listdrives doesn't exist in newer Python versions
        # We'll create a fallback function if needed
        def listdrives():
            import string
            import os
            drives = []
            for letter in string.ascii_uppercase:
                if os.path.exists(f"{letter}:\\"):
                    drives.append(f"{letter}:\\")
            return drives

CH_DICT = {'a': 1, 'b': 2, 'c': 3, 'd': 4}


class ControllerBase:

    def __init__(self, name):
        self._ser = None
        self.name = name

    def open(self):
        pass

    def valid(self):
        """Return True if serial port is open or can be opened.

        Subclasses may override open(); this helper avoids writes to a closed
        or stale handle which can raise PermissionError on Windows after a
        disconnect.
        """
        try:
            return (self._ser is not None and getattr(self._ser, "is_open", False)) or self.open()
        except Exception:
            return False

    def get_info(self):
        pass

    def turn_on_channel(self, ch='a'):
        pass

    def turn_off_channels(self):
        pass

    def set_mode(self, mode='s'):
        pass

    def stop(self):
        pass

    def close(self):
        if self._ser is not None:
            self._ser.close()
            self._ser = None


class KineticController(ControllerBase):

    def __init__(self):
        super().__init__(name='KNX2')
        self._lock = threading.Lock()
        self.version = '1.0'

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found a KNX2 board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(port=dev.device, baudrate=BAUD_RATE, timeout=3)
                    info = self.get_info()
                    if info is not None:
                        if info['fw ver'].startswith('KNX2'):
                            if info['fw ver'].startswith('KNX2 V1.1'):
                                self.version = '1.1'
                            return True
                        # EZSPR detection disabled (obsolete hardware, use PicoEZSPR instead)
                        # elif info['fw ver'].startswith('EZSPR'):
                        #     self.name = "EZSPR"
                        #     if info['fw ver'].startswith('EZSPR V1.1'):
                        #         self.version = '1.1'
                        #     return True
                        elif info['fw ver'].startswith('KNX1'):
                            self.name = "KNX"
                            self.version = '1.1'
                            return True
                        else:
                            logger.debug('dev is not KNX2')
                            self._ser.close()
                            return False
                    else:
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
                                logger.error(f"Failed to parse to JSON of {cmd} - {buf}")
                                return None
                        else:
                            data = buf.splitlines()
                            return data[0] if data else buf
            except Exception as e:
                logger.error(f"Failed to send command to {self.name} - {e}")
                self._ser = None

    def get_status(self):
        return self._send_command(cmd='get_status', parse_json=True)

    def get_info(self):
        return self._send_command(cmd='get_info', parse_json=True)

    def get_parameters(self):
        return self._send_command(cmd='get_parameters', parse_json=True)

    def read_wavelength(self, channel):
        data = self._send_command(cmd=f"read{channel}")
        if data:
            return numpy.asarray([int(v) for v in data.split(',')])

    def read_intensity(self):
        data = self._send_command(cmd='intensity')
        if data:
            return numpy.asarray([int(v) for v in data.split(',')])

    def stop(self):
        return self._send_command(cmd="stop")

    def turn_on_channel(self, ch='a'):
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def turn_off_channels(self):
        return self._send_command('led_off')

    # Equivalent to the Arduino function to turn on a channel LED at a given intensity
    def set_intensity(self, ch='a', raw_val=255):
        val = int((raw_val / 255) * 31) + 1
        self._send_command(f"led_intensity({CH_DICT[ch]},{val})")
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def set_integration(self, int_ms):
        return self._send_command(f"set_integration({int_ms})")

    def set_mode(self, mode='s'):
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
        self._send_command(f"knx_stop_all")

    def shutdown(self):
        self._send_command('shutdown')
        self.close()

    def __str__(self):
        return "KNX2 Board"


class PicoP4SPR(ControllerBase):

    def __init__(self):
        super().__init__(name='pico_p4spr')
        self._ser = None
        self.version = ''

    def open(self):
        for dev in serial.tools.list_ports.comports():
            # Log candidate ports
            try:
                logger.debug(
                    f"Checking port {dev.device} {getattr(dev, 'vid', None)}:{getattr(dev, 'pid', None)} - {dev.description} - {getattr(dev, 'hwid', '')}"
                )
            except Exception:
                logger.debug(f"Checking port {dev.device} - {dev.description}")

            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                # Prefer the CDC interface (MI_00) when present
                try:
                    hwid = getattr(dev, "hwid", "")
                    # If an interface marker is present (MI_XX) and it's not MI_00, skip it
                    if "MI_" in hwid and "MI_00" not in hwid:
                        logger.debug(f"Skipping non-CDC interface on {dev.device} (hwid={hwid})")
                        continue
                except Exception:
                    pass
                try:
                    # Open with a slightly longer timeout for first handshake
                    self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=3, write_timeout=2)

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
                    else:
                        logger.debug("Pico present but did not return expected ID; closing port")
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

    def turn_on_channel(self, ch='a'):
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError("Invalid Channel!")
            cmd = f"l{ch}\n"
            if self.valid():
                try:
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b'1'
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
            with suppress(Exception):
                self._ser.reset_input_buffer()
            self._ser.write(b"it\n")
            for _ in range(3):
                line = self._ser.readline()
                s = line.decode(errors="ignore").strip()
                if not s:
                    # Skip empty lines
                    continue
                try:
                    # Limit precision to avoid long strings like '23.45678'
                    val = float(s)
                    return val
                except ValueError:
                    # Non-empty but not a float; log once and break
                    logger.debug(f"temp value not readable '{s}'")
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
            cmd = f"lx\n"
            try:
                self._ser.write(cmd.encode())
                return self._ser.read() == b'1'
            except PermissionError:
                # Device likely disconnected; avoid noisy logs
                return False
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def set_intensity(self, ch='a', raw_val=1):
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
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
                self._ser.write(cmd.encode())
                reply = self._ser.read() == b'1'
                self.turn_on_channel(ch=ch)
                return reply
            else:
                logger.error(f"pico failed to turn LED {ch} ON")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_mode(self, mode='s'):
        try:
            if self.valid():
                if mode == 's':
                    cmd = f"ss\n"
                else:
                    cmd = f"sp\n"
                try:
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b'1'
                except PermissionError:
                    return False
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = f"sr\n"
        curr_pos = {'s': b'000', 'p': b'000'}
        try:
            if self.valid():
                # Flush any leftover bytes (e.g., from previous commands) to avoid misreads
                with suppress(Exception):
                    self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())

                # Read up to a few lines until we find a line like b"ddd,ddd\n"
                line = b""
                for _ in range(3):
                    line = self._ser.readline()
                    logger.debug(f"servo reading pico {line}")
                    if len(line) >= 7 and line[0:3].isdigit() and line[3:4] == b"," and line[4:7].isdigit():
                        break
                # Parse if valid
                if len(line) >= 7 and line[0:3].isdigit() and line[3:4] == b"," and line[4:7].isdigit():
                    curr_pos['s'] = line[0:3]
                    curr_pos['p'] = line[4:7]
                    logger.debug(f"Servo s, p: {curr_pos}")
                else:
                    logger.error(f"Unexpected servo reply: {line!r}")
            else:
                logger.error("serial communication failed - servo get")
        except Exception as e:
            logger.debug(f"error getting servo pos {e}")
        return curr_pos

    def servo_set(self, s=10, p=100):
        try:
            if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                raise ValueError(f"Invalid polarizer position given: {s}, {p}")
            else:
                cmd = f"sv{s:03d}{p:03d}\n"
                if self.valid():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b'1'
                else:
                    logger.error("unable to update servo positions")
                    return False
        except Exception as e:
            logger.debug(f"error setting servo position {e}")
            return False

    def flash(self):
        try:
            flash_cmd = 'sf\n'
            if self.valid():
                try:
                    self._ser.write(flash_cmd.encode())
                    return self._ser.read() == b'1'
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


# PicoKNX2 DISABLED - Legacy hardware, use PicoEZSPR instead
# class PicoKNX2(ControllerBase):
#
#     def __init__(self):
#         super().__init__(name='pico_knx2')
#         self._ser = None
#         self.version = ''
#
#     def open(self):
#         for dev in serial.tools.list_ports.comports():
#             if dev.pid == PICO_PID and dev.vid == PICO_VID:
#                 try:
#                     self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=1)
#                     cmd = f"id\n"
#                     self._ser.write(cmd.encode())
#                     reply = self._ser.readline()[0:4].decode()
#                     logger.debug(f"Pico KNX2 reply - {reply}")
#                     if reply == 'KNX2':
#                         cmd = f"iv\n"
#                         self._ser.write(cmd.encode())
#                         self.version = self._ser.readline()[0:4].decode()
#                         return True
#                     else:
#                         self._ser.close()
#                 except Exception as e:
#                     logger.error(f"Failed to open Pico - {e}")
#                     if self._ser is not None:
#                         self._ser.close()
#         return False
#
#     def get_status(self):
#         try:
#             if not self.valid():
#                 return -1
#             with suppress(Exception):
#                 self._ser.reset_input_buffer()
#             self._ser.write(b"it\n")
#             for _ in range(3):
#                 line = self._ser.readline()
#                 s = line.decode(errors="ignore").strip()
#                 if not s:
#                     continue
#                 try:
#                     return float(s)
#                 except ValueError:
#                     logger.debug(f"temp value not readable '{s}'")
#                     break
#             return -1
#         except PermissionError:
#             return -1
#         except Exception:
#             return -1
#
#     def knx_status(self, ch):
#         status = {'flow': 0, 'temp': 0, '6P': 0, '3W': 0}
#         try:
#             cmd = f"ks{ch}\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 data = self._ser.readline().decode()[0:-2]
#                 data = data.split(',')
#                 if len(data) > 3:
#                     status['flow'] = float(data[0])
#                     status['temp'] = float(data[1])
#                     status['3W'] = float(data[2])
#                     status['6P'] = float(data[3])
#             else:
#                 logger.error(f"failed to send cmd knx_status")
#             return status
#         except Exception as e:
#             logger.error(f"Error during knx_status {e}")
#
#     def knx_stop(self, ch):
#         try:
#             cmd = f"ps{ch}\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 if self._ser.read() == b'1':
#                     return True
#             else:
#                 logger.error(f"failed to send cmd knx_stop")
#             return False
#         except Exception as e:
#             logger.error(f"Error during knx_stop {e}")
#
#     def knx_start(self, rate, ch):
#         try:
#             cmd = f"pr{ch}{rate:3d}\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 if self._ser.read() == b'1':
#                     return True
#             else:
#                 logger.error(f"failed to send cmd knx_start")
#             return False
#         except Exception as e:
#             logger.error(f"Error during knx_start {e}")
#
#     def knx_three(self, state, ch):
#         try:
#             cmd = f"v3{ch}{state:1d}\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 return True
#             else:
#                 logger.error(f"failed to send cmd knx_three")
#             return False
#         except Exception as e:
#             logger.error(f"Error during knx_three {e}")
#
#     def knx_six(self, state, ch):
#         try:
#             cmd = f"v6{ch}{state:1d}\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 return True
#             else:
#                 logger.error(f"failed to send cmd knx_six")
#             return False
#         except Exception as e:
#             logger.error(f"Error during knx_six {e}")
#
#     def knx_led(self, led_state, ch):
#         pass  # Green indicator LED for each ch controlled in FW
#
#     def stop_kinetic(self):
#         try:
#             cmds = ["ps3\n", "v330\n", "v630\n"]
#             if self._ser is not None or self.open():
#                 er = False
#                 for cmd in cmds:
#                     self._ser.write(cmd.encode())
#                     if not (self._ser.read() == b'1'):
#                         er = True
#                 if er:
#                     logger.error(f"pico failed to confirm kinetics off")
#             else:
#                 logger.error(f"pico failed to turn kinetics off")
#         except Exception as e:
#             logger.error(f"error while shutting down kinetics {e}")
#
#     def shutdown(self):
#         try:
#             cmd = "do\n"
#             if self._ser is not None or self.open():
#                 self._ser.write(cmd.encode())
#                 if not (self._ser.read() == b'1'):
#                     logger.error(f"pico failed to confirm device off")
#             else:
#                 logger.error(f"pico failed to turn device off")
#         except Exception as e:
#             logger.error(f"error while shutting down device {e}")
#
#     def get_info(self):
#         return self.name
#
#     def __str__(self):
#         return "Pico Carrier Board"


class PicoEZSPR(ControllerBase):

    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self):
        super().__init__(name='pico_ezspr')
        self._ser = None
        self.version = ''

    def valid(self):
        return self._ser is not None and self._ser.is_open or self.open()

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=5)
                    cmd = f"id\n"
                    self._ser.write(cmd.encode())
                    reply = self._ser.readline()[0:5].decode()
                    logger.debug(f"Pico EZSPR reply - {reply}")
                    if reply == 'EZSPR':
                        cmd = f"iv\n"
                        self._ser.write(cmd.encode())
                        self.version = self._ser.readline()[0:4].decode()
                        return True
                    else:
                        self._ser.close()
                except Exception as e:
                    logger.error(f"Failed to open Pico - {e}")
                    if self._ser is not None:
                        self._ser.close()
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
                pico_drive = next(d for d in listdrives() if (Path(d) / "INFO_UF2.TXT").exists())
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
            corrrection_bytes = bytes(round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections)
        except ValueError:
            return False
        self._ser.write(b"pf" + corrrection_bytes + b"\n")
        return True

    def turn_on_channel(self, ch='a'):
        try:
            if ch in {"a", "b", "c", "d"}:
                cmd = f"l{ch}\n"
                if self.valid():
                    try:
                        self._ser.write(cmd.encode())
                        return self._ser.read() == b"1"
                    except PermissionError:
                        return False
            elif ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError("Invalid Channel!")
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def turn_off_channels(self):
        try:
            if not self.valid():
                return False
            cmd = f"lx\n"
            try:
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            except PermissionError:
                return False
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def set_intensity(self, ch='a', raw_val=1):
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
                    self._ser.write(cmd.encode())
                    reply = self._ser.read() == b"1"
                    self.turn_on_channel(ch=ch)
                    return reply
                else:
                    logger.error(f"pico failed to turn LED {ch} ON")
            elif ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError(f"Invalid Channel - {ch}")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_mode(self, mode='s'):
        try:
            if self.valid():
                if mode == 's':
                    cmd = f"ss\n"
                else:
                    cmd = f"sp\n"
                try:
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
                except PermissionError:
                    return False
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = f"sr\n"
        curr_pos = {'s': b'0000', 'p': b'0000'}
        try:
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                servo_reading = self._ser.readline()
                logger.debug(f"servo reading pico {servo_reading}")
                curr_pos['s'] = servo_reading[0:3]
                curr_pos['p'] = servo_reading[4:7]
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
            else:
                cmd = f"sv{s:03d}{p:03d}\n"
                if self.valid():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b'1'
                else:
                    logger.error("unable to update servo positions")
                    return False
        except Exception as e:
            logger.debug(f"error setting servo position {e}")
            return False

    def flash(self):
        try:
            flash_cmd = 'sf\n'
            if self.valid():
                try:
                    self._ser.write(flash_cmd.encode())
                    return self._ser.read() == b'1'
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
            with suppress(Exception):
                self._ser.reset_input_buffer()
            self._ser.write(b"it\n")
            for _ in range(3):
                line = self._ser.readline()
                s = line.decode(errors="ignore").strip()
                if not s:
                    continue
                try:
                    return float(s)
                except ValueError:
                    logger.debug(f"temp value not readable '{s}'")
                    break
            return -1
        except PermissionError:
            return -1
        except Exception:
            return -1

    def knx_status(self, ch):
        status = {'flow': 0, 'temp': 0, '6P': 0, '3W': 0}
        try:
            cmd = f"ks{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                data = self._ser.readline().decode()[0:-2]
                data = data.split(',')
                if len(data) > 3:
                    status['flow'] = float(data[0])
                    status['temp'] = float(data[1])
                    status['3W'] = float(data[2])
                    status['6P'] = float(data[3])
            else:
                logger.error(f"failed to send cmd knx_status")
            return status
        except Exception as e:
            logger.error(f"Error during knx_status {e}")

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_stop")
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
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")

    def knx_three(self, state, ch):
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            else:
                logger.error(f"failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            else:
                logger.error(f"failed to send cmd knx_six")
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
                    if not (self._ser.read() == b'1'):
                        er = True
                if er:
                    logger.error(f"pico failed to confirm kinetics off")
            else:
                logger.error(f"pico failed to turn kinetics off")
        except Exception as e:
            logger.error(f"error while shutting down kinetics {e}")

    def shutdown(self):
        try:
            cmd = "do\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if not (self._ser.read() == b'1'):
                    logger.error(f"pico failed to confirm device off")
            else:
                logger.error(f"pico failed to turn device off")
        except Exception as e:
            logger.error(f"error while shutting down device {e}")

    def get_info(self):
        return self.name

    def get_temp(self):
        try:
            if not self.valid():
                return -1
            with suppress(Exception):
                self._ser.reset_input_buffer()
            self._ser.write(b"it\n")
            for _ in range(3):
                line = self._ser.readline()
                s = line.decode(errors="ignore").strip()
                if not s:
                    continue
                try:
                    return float(s)
                except ValueError:
                    logger.debug(f"temp value not readable '{s}'")
                    break
            return -1
        except PermissionError:
            return -1
        except Exception:
            return -1

    def __str__(self):
        return "Pico Carrier Board"

