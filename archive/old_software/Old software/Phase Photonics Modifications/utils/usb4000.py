from pathlib import Path
from time import sleep

from ftd2xx import listDevices
import numpy as np
from numpy import all, arange, asarray, frombuffer, isnan
from numpy.polynomial import Polynomial

from utils.common import get_config
from utils.logger import logger

from .SpectrometerAPI import SENSOR_DATA_LEN, SpectrometerAPI


class USB4000:
    """USB4000 device driver"""

    CONFIG_SIZE = 4096
    CALIBRATION_OFFSET = 3072
    CALIBRATION_DEGREE = 4

    def __init__(self, app):
        super(USB4000, self).__init__()
        self.api = SpectrometerAPI(Path(__file__).parent / "Sensor.dll")
        self.app = app
        self.spec = None
        self.opened = False
        self.devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
        self.min_integration = 0
        self.max_integration = 5_000_000
        self.serial_number = None

    def get_device_list(self):
        try:
            logger.debug("trying to open spec list")
            self.devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
        except Exception as e:
            logger.debug(f"Error getting device list {e}")

    def open(self):
        try:
            # get_dev = threading.Thread(target=self.get_device_list)
            # get_dev.start()
            # time.sleep(1)
            # get_dev.join(0.1)
            # if get_dev.is_alive():
            #     raise ConnectionError
            logger.debug(f"spectrometers available: {self.devs}")
            self.devs = [s.decode() for s in listDevices() if s.startswith(b"ST")]
            if True:  # len(self.devs) > 0:
                self.serial_number = self.devs[0]
                if self.serial_number == "ST00005":
                    self.api = SpectrometerAPI(
                        Path(__file__).parent / "SensorT_x64.dll",
                    )
                self.spec = self.api.usb_initialize(self.devs[0])
                self.set_integration(
                    max(get_config()["integration_time"], self.min_integration),
                )
                self.opened = True
                return True
            else:
                return False
        except Exception as e:
            logger.exception(f"Failed to connect to spectrometer - {e}")
            self.app.raise_error.emit("spec")

    # Added method to set integration time
    def set_integration(self, integration):
        if integration < self.min_integration or integration > self.max_integration:
            return False
        try:
            r = self.api.usb_set_interval(self.spec, int(integration * 1000))
            sleep(0.3)
            return bool(r)
        except Exception as e:
            logger.error(f"Failed to set integration time - {e}")
            self.app.raise_error.emit("spec")

    def read_wavelength(self):
        if self.spec is not None or self.open():
            try:
                bytes_read, config = self.api.usb_read_config(self.spec, 0)
                if bytes_read == self.CONFIG_SIZE:
                    coeffs = frombuffer(
                        config.data,
                        ">f8",
                        self.CALIBRATION_DEGREE,
                        self.CALIBRATION_OFFSET,
                    )
                    if all(isnan(coeffs)):
                        msg = "Spectrometer has not been calibrated."
                        raise RuntimeError(msg)  # noqa: TRY301
                    calibration_curve = Polynomial(coeffs)
                    return calibration_curve(arange(SENSOR_DATA_LEN))
            except Exception as e:
                logger.error(f"Failed to read wavelength data from spectrometer - {e}")
                self.app.raise_error.emit("spec")
        return None

    def read_intensity(self, data_type=np.float64):
        if self.spec is not None or self.open():
            try:
                return self.api.usb_read_pixels(self.spec, data_type)[1]
            except Exception as e:
                logger.error(f"Failed to read intensity data from spectrometer - {e}")
                self.app.raise_error.emit("spec")
        return None

    def close(self):
        if self.spec is not None:
            self.api.usb_deinit(self.spec)
            self.spec = None
