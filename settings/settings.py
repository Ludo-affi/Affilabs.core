import json
import os
import sys
from pathlib import Path
from re import search


def get_version() -> str:
    """Get the current version of this software."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        spec_file = Path(sys._MEIPASS) / "main.spec"  # noqa: SLF001
    else:
        spec_file = Path("main.spec")
    match = search("name='ezControl (.+ )?v(.+)',", spec_file.read_text())
    if match is None:
        msg = "Could not find version in spec file."
        raise RuntimeError(msg)
    return match[2]


DEV = True
SW_VERSION = f"Version {get_version()}"
TARGET = "win"

if TARGET == "win":
    ROOT_DIR = f"{os.getcwd()}\\generated-files"
    os.makedirs(ROOT_DIR, exist_ok=True)

elif TARGET == "mac":
    ROOT_DIR = "generated-files"
    os.makedirs(ROOT_DIR, exist_ok=True)

CH_LIST = ["a", "b", "c", "d"]
EZ_CH_LIST = ["a", "b"]
UNIT_LIST = {"nm": 1, "RU": 355}
GRAPH_COLORS = {"a": "k", "b": (255, 0, 81), "c": (0, 174, 255), "d": (0, 230, 65)}

ARDUINO_VID = 0x2341
ARDUINO_PID = 0x8036

ADAFRUIT_VID = 0x239A

PICO_PID = 0x000A
PICO_VID = 0x2E8A

CP210X_VID = 0x10C4
CP210X_PID = 0xEA60
BAUD_RATE = 115200

# Prevent recursion error
GRAPH_REGION_UPDATE_GAP = 0.1  # 100 ms

# Fields
UNIT = "RU"  # measurement units
MIN_WAVELENGTH = 560  # minimum wavelength for data
MAX_WAVELENGTH = 720  # maximum wavelength for data
POL_WAVELENGTH = 620  # index for auto polarization
DARK_NOISE_SCANS = 30  # number of scans to average in dark noise measurement
REF_SCANS = 20  # number of scans to average in reference measurement
CYCLE_TIME = 1.3  # cycle time for all 4 channels
LED_DELAY = 0.1  # led-stabilization delay
S_LED_INT = int(0.66 * 255)  # max s-polarized led intensity
S_LED_MIN = 20  # minimum intensity for checking saturation
P_LED_MAX = 255  # max p-polarized led intensity
P_MAX_INCREASE = 1.33  # max brightness increase factor for P vs S
S_COUNT_MAX = 64000  # maximum value for peak intensity in counts
P_COUNT_THRESHOLD = 10000  # minimum p-polarized count for successful calibration
MIN_INTEGRATION = 5  # minimum detector integration time in ms
MAX_INTEGRATION = 100  # maximum detector integration time in ms
MAX_READ_TIME = 200  # maximum total read time in milliseconds
CURVE_FIT_HEIGHT = 5  # height of transmission segment to take for width0
TRANS_SEG_H = 20  # height to define transmission segment
TRANS_SEG_H_REQ = 0.5  # factor for calibrated channel fitting height on both ends
AUTO_POLARIZE_ENABLE = False  # enable/disable auto-polarization during calibration
FILTERING_ON = True  # enabled/disable filtering
MED_FILT_WIN = 5  # default median filter window size
DEBUG = False  # enable/disable debug mode
SHOW_PLOT = False  # enable/disable test plotting for grab data
SHOW_AUTOSEGMENT = False  # enable/disable test plotting for auto-segmentation
RECORDING_INTERVAL = 15  # frequency to save data when recording
SENSOR_AVG = 10  # number of kinetic sensor readings to average
SENSOR_POLL_INTERVAL = 10  # seconds to wait between sensor readings
FLUSH_RATE = 220  # rate in uL/min for flushing channels
DEMO = False  # enable/disable demo mode
STATIC_PLOT = False  # enable/disable static portion of plots
POP_OUT_SPEC = False  # pop out spectroscopy into separate window for debugging

# Device types and timezone
DEVICES = ["PicoP4SPR", "PicoEZSPR"]  # Supported device types
import datetime
try:
    # Python 3.11+ has datetime.UTC
    TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
except AttributeError:
    # Python 3.10 and earlier - use timezone.utc
    import datetime
    TIME_ZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

DEFAULT_CONFIG = {
    "unit": UNIT,
    "min_wavelength": MIN_WAVELENGTH,
    "max_wavelength": MAX_WAVELENGTH,
    "integration_time": MIN_INTEGRATION,
    "channel_cycle_time": CYCLE_TIME,
}

CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as jp:
        json.dump(DEFAULT_CONFIG, jp, indent=2)

try:
    from local_settings import *
except ImportError:
    pass
