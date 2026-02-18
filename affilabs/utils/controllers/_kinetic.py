from __future__ import annotations

import json
import threading
import time
from json import JSONDecodeError

import numpy as np
import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import BAUD_RATE, CP210X_PID, CP210X_VID

from affilabs.utils.controllers._base import FlowController, CH_DICT


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

