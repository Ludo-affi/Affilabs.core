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
SW_APP_NAME = "ezControl"
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

# Standard color palette
GRAPH_COLORS = {"a": "k", "b": (255, 0, 81), "c": (0, 174, 255), "d": (0, 230, 65)}

# Colorblind-friendly palette (Okabe-Ito)
# Designed to be distinguishable for all types of colorblindness
GRAPH_COLORS_COLORBLIND = {
    "a": (1, 115, 178),    # Blue
    "b": (222, 143, 5),    # Orange
    "c": (2, 158, 115),    # Green
    "d": (204, 120, 188),  # Magenta
}

# Current active palette (can be toggled by user)
ACTIVE_GRAPH_COLORS = GRAPH_COLORS.copy()

ARDUINO_VID = 0x2341
ARDUINO_PID = 0x8036

ADAFRUIT_VID = 0x239A

PICO_PID = 0x000A
PICO_VID = 0x2E8A

CP210X_VID = 0x10C4
CP210X_PID = 0xEA60
BAUD_RATE = 115200
QSPR_BAUD_RATE = 460800

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
LED_DELAY = 0.050  # led-stabilization delay (50ms - default, adjustable in Advanced Settings)
USE_DYNAMIC_LED_DELAY = False  # DISABLED: afterglow correction now uses model subtraction instead
LED_DELAY_TARGET_RESIDUAL = 2.0  # percent residual allowed when computing dynamic LED delay
LED_POST_DELAY = 0.005  # additional dark time after LED off before switching channel (s)
USE_DYNAMIC_POST_DELAY = False  # DISABLED: afterglow correction now uses model subtraction instead
S_LED_INT = 255  # max s-polarized led intensity
S_LED_MIN = 20  # minimum intensity for checking saturation
P_LED_MAX = 255  # max p-polarized led intensity
P_MAX_INCREASE = 1.33  # max brightness increase factor for P vs S
S_COUNT_MAX = 49152  # target signal level: 75% of 16-bit detector max (65535) - optimized for SPR
P_COUNT_THRESHOLD = 300  # minimum p-polarized count for successful calibration
MIN_INTEGRATION = 10  # minimum detector integration time in milliseconds - start low and increase as needed
INTEGRATION_STEP = 5  # integration time step in milliseconds
MAX_INTEGRATION = 100  # maximum detector integration time in milliseconds
MAX_READ_TIME = 200  # maximum total read time in milliseconds
MAX_NUM_SCANS = 25
CURVE_FIT_HEIGHT = 5  # height of transmission segment to take for width0
TRANS_SEG_H = 20  # height to define transmission segment
TRANS_SEG_H_REQ = 0.5  # factor for calibrated channel fitting height on both ends
AUTO_POLARIZE_ENABLE = False  # enable/disable auto-polarization during calibration
FILTERING_ON = True  # enabled/disable filtering
MED_FILT_WIN = 3  # default median filter window size
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
