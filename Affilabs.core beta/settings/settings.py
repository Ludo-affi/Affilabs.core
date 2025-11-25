import json
import os
import sys
from pathlib import Path
from re import search


def get_version() -> str:
    """Get the current version of this software."""
    try:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            # When frozen (compiled to .exe), read from bundled VERSION file
            version_file = Path(sys._MEIPASS) / "VERSION"  # noqa: SLF001
        else:
            # When running from source, read from VERSION file in project root
            version_file = Path(__file__).parent.parent / "VERSION"

        version = version_file.read_text().strip()
        return version
    except FileNotFoundError:
        # Fallback: try to parse main.spec if VERSION file doesn't exist
        try:
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                spec_file = Path(sys._MEIPASS) / "main.spec"  # noqa: SLF001
            else:
                spec_file = Path(__file__).parent.parent / "main.spec"
            match = search("name='ezControl (.+ )?v(.+)',", spec_file.read_text())
            if match is None:
                return "4.0"  # Default fallback version
            return match[2]
        except (FileNotFoundError, AttributeError):
            return "4.0"  # Default fallback version


DEV = False  # Set to True to enable OEM/factory features (optical calibration button, etc.)
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
GRAPH_COLORS = {"a": "k", "b": (255, 0, 81), "c": (0, 174, 255), "d": (0, 100, 0)}

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

# Cycle marker style: "cursors" or "lines"
CYCLE_MARKER_STYLE = "cursors"  # Can be changed to "lines" for vertical line markers

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

# LED Timing Configuration (in milliseconds)
# PRE_LED_DELAY_MS: Settling time after LED turn-on before measurement
# POST_LED_DELAY_MS: Dark time after LED turn-off before channel switch (for afterglow decay)
PRE_LED_DELAY_MS = 45  # LED stabilization delay before measurement (default 45ms, configurable 0-200ms)
POST_LED_DELAY_MS = 5  # Additional dark time after LED off (default 5ms, configurable 0-100ms)

# Legacy support (kept for backward compatibility with old code)
LED_DELAY = PRE_LED_DELAY_MS / 1000.0  # Convert to seconds for legacy code
LED_POST_DELAY = POST_LED_DELAY_MS / 1000.0  # Convert to seconds for legacy code

USE_DYNAMIC_LED_DELAY = False  # DISABLED: afterglow correction now uses model subtraction instead
LED_DELAY_TARGET_RESIDUAL = 2.0  # percent residual allowed when computing dynamic LED delay

# === AUTOMATIC AFTERGLOW CORRECTION STRATEGY ===
# Three-tier system based on total acquisition delay (PRE + POST):
#
# 1. FAST MODE: Total delay < 50ms (e.g., 25ms pre + 5ms post = 30ms total)
#    - Afterglow correction: ENABLED (high-speed feature)
#    - Rationale: Afterglow is 0.5-0.9% of signal at 25ms, needs correction
#    - Benefit: 24% noise reduction, enables 2x faster acquisition
#
# 2. NORMAL MODE: 50ms ≤ Total delay ≤ 100ms (e.g., 45ms pre + 5ms post = 50ms)
#    - Afterglow correction: ENABLED (default calibrated state)
#    - Rationale: Afterglow is 0.3-0.5% of signal at 50ms, correction recommended
#    - Benefit: Better stability for standard operation
#
# 3. SLOW MODE: Total delay > 100ms
#    - Afterglow correction: DISABLED (afterglow negligible)
#    - Rationale: Afterglow < 0.2% of signal, below noise floor
#    - Benefit: Saves computation, avoids over-correction
#
# The system automatically determines mode based on LED_DELAY + LED_POST_DELAY
AFTERGLOW_FAST_THRESHOLD_MS = 50.0   # Below this: high-speed mode (correction enabled)
AFTERGLOW_SLOW_THRESHOLD_MS = 100.0  # Above this: slow mode (correction disabled)
AFTERGLOW_AUTO_MODE = True  # Automatic mode selection (recommended, set False to force enable/disable)
USE_DYNAMIC_POST_DELAY = False  # DISABLED: afterglow correction now uses model subtraction instead
S_LED_INT = 255  # max s-polarized led intensity
S_LED_MIN = 20  # minimum intensity for checking saturation
P_LED_MAX = 255  # max p-polarized led intensity
P_MAX_INCREASE = 1.33  # max brightness increase factor for P vs S
S_COUNT_MAX = 49152  # DEPRECATED: Now queried from detector HAL via usb.target_counts (75% of detector max)
P_COUNT_THRESHOLD = 300  # DEPRECATED: Replaced by dynamic 30% of target_counts in verify_calibration()
MIN_INTEGRATION = 10  # minimum detector integration time in milliseconds - start low and increase as needed
INTEGRATION_STEP = 5  # integration time step in milliseconds
MAX_INTEGRATION = 100  # maximum detector integration time in milliseconds
MAX_READ_TIME = 200  # maximum total read time in milliseconds
MAX_NUM_SCANS = 25

# === SESSION QUALITY MONITORING (FWHM-Based QC System) ===
# Quality thresholds for FWHM-based grading (nm)
FWHM_EXCELLENT_THRESHOLD_NM = 30.0   # Green:  FWHM < 30nm
FWHM_GOOD_THRESHOLD_NM = 60.0        # Yellow: 30nm ≤ FWHM < 60nm
                                      # Red:    FWHM ≥ 60nm

# === CALIBRATION METHOD SELECTION ===
# Two calibration methods available:
# 1. STANDARD (Default): Global integration time, variable LED intensity per channel
#    - Optimizes integration time globally for all channels
#    - Then calibrates LED intensity per channel to reach target signal
#    - Best for general use, well-tested and stable
#
# 2. ALTERNATIVE: Global LED intensity (255), variable integration time per channel
#    - Sets all LEDs to maximum intensity (255)
#    - Calibrates integration time per channel to reach target signal
#    - Benefits: Better frequency, excellent SNR, more LED consistency at max current
#    - Trade-offs: Variable integration time per channel, may hit timing budget on weak channels
#
# IMPORTANT: Keep ALTERNATIVE method DISABLED until thoroughly tested
USE_ALTERNATIVE_CALIBRATION = False  # Set to True to use Global LED Intensity method (EXPERIMENTAL)

CURVE_FIT_HEIGHT = 5  # height of transmission segment to take for width0
TRANS_SEG_H = 20  # height to define transmission segment
TRANS_SEG_H_REQ = 0.5  # factor for calibrated channel fitting height on both ends
AUTO_POLARIZE_ENABLE = False  # enable/disable auto-polarization during calibration
FILTERING_ON = True  # enabled/disable filtering
MED_FILT_WIN = 3  # default median filter window size

# === Display Smoothing Settings ===
ENABLE_INTERPOLATED_DISPLAY = True  # Emit preview points during batch processing for smooth visualization
BATCH_SIZE = 12  # Number of raw spectra to buffer before vectorized processing (balances quality vs latency)
                 # Batch size 12 provides ~300ms processing window for advanced filtering
                 # Recommended values:
                 # - 8: Fast mode (~200ms window), good for monitoring
                 # - 12: Quality mode (~300ms window), Savitzky-Golay filtering (RECOMMENDED)
                 # - 16: Research mode (~400ms window), maximum quality

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

# === Performance Profiling Settings ===
PROFILING_ENABLED = False  # Enable performance profiling
PROFILING_REPORT_INTERVAL = 30  # Seconds between profiling reports (if enabled)

# === Timezone Settings ===
import datetime
try:
    TIME_ZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
except AttributeError:
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
    import tempfile
    from pathlib import Path
    config_path = Path(CONFIG_FILE)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write using temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=config_path.parent,
            delete=False,
            suffix='.tmp'
        ) as tmp_file:
            json.dump(DEFAULT_CONFIG, tmp_file, indent=2)
            tmp_path = Path(tmp_file.name)

        tmp_path.replace(config_path)
    except Exception as e:
        print(f"Failed to create default config: {e}")
        raise

try:
    from local_settings import *
except ImportError:
    pass
