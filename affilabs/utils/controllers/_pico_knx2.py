from __future__ import annotations

import time

import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import PICO_PID, PICO_VID

from affilabs.utils.controllers._base import FlowController


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
                print("DEBUG knx_three: Command sent successfully")
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
                print("DEBUG knx_six: Command sent successfully")
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

