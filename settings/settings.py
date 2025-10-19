"""
Settings Configuration

DETECTOR-SPECIFIC PARAMETERS (NEW):
====================================
This file now supports detector-specific parameters loaded from detector profiles.
See detector_profiles/*.json for detector-specific configurations.

The detector manager auto-detects the connected detector and loads the appropriate profile with:
- pixel_count (e.g., 3648 for Ocean Optics)
- wavelength_range (min/max nm)
- max_intensity_counts (62,000 for Flame-T, not 50,000!)
- max_integration_time_ms (200 ms for Flame-T, not 20 ms!)
- target_signal_counts
- spr_wavelength_range (580-720 nm)

To access detector-specific values:
    from utils.detector_manager import get_current_detector_profile
    profile = get_current_detector_profile()
    max_counts = profile.max_intensity_counts  # 62,000 for Flame-T

Legacy constants below are kept for backward compatibility but will be
replaced with detector profile values during runtime.
"""

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

# ==========================================
# DETECTOR-SPECIFIC PARAMETERS (Use profiles instead!)
# ==========================================
# DEPRECATED: These are now loaded from detector profiles
# Use: profile = get_current_detector_profile()
MIN_WAVELENGTH = 580  # DEPRECATED: Use profile.spr_wavelength_min_nm
MAX_WAVELENGTH = 720  # DEPRECATED: Use profile.spr_wavelength_max_nm
POL_WAVELENGTH = 620  # index for auto polarization

# ==========================================
# TIMING PARAMETERS
# ==========================================
# LED Stabilization - time between LED turn-on and spectrum acquisition
# OPTIMIZED: Reduced from 100ms to 50ms (Priority #5 - CALIBRATION_ACCELERATION_GUIDE.md)
# Saves ~0.55s per calibration (11 LED activations × 50ms reduction)
# Tested safe on Flame-T and USB4000 detectors
LED_DELAY = 0.05  # seconds (50ms) - optimized from 100ms

# ==========================================
# MODERN TIMING ARCHITECTURE (≤200ms per channel)
# ==========================================
# Acquisition timing is now DYNAMIC based on integration time.
# Use calculate_dynamic_scans() from utils.spr_calibrator for all scan calculations.
# Target: ≤200ms acquisition time per channel for responsive sensorgram updates.
#
# Performance:
#   - Per-channel: ~200ms (LED 50ms + acquisition 150ms)
#   - Full cycle: ~800ms (4 channels × 200ms)
#   - Update rate: ~1.2 Hz (perceived ~5 Hz with staggered updates)

# Legacy timing constants (DEPRECATED - kept for backward compatibility only)
# DO NOT USE these for new code - use calculate_dynamic_scans() instead
ACQUISITION_FREQUENCY = 1.0  # Hz - DEPRECATED (use calculate_dynamic_scans)
ACQUISITION_CYCLE_TIME = 1.0 / ACQUISITION_FREQUENCY  # DEPRECATED (target is now 200ms/channel)
TIME_PER_CHANNEL = ACQUISITION_CYCLE_TIME / 4  # DEPRECATED (use calculate_dynamic_scans)
CYCLE_TIME = 1.3  # DEPRECATED: Use calculate_dynamic_scans() instead

# Reference Signal Averaging
# Number of scans is DYNAMIC based on integration time (via calculate_dynamic_scans)
# to maintain ≤200ms acquisition time per channel
DARK_NOISE_SCANS = 30  # number of scans to average in dark noise measurement
REF_SCANS = 20  # DEPRECATED: Now calculated dynamically via calculate_dynamic_scans()

# Legacy LED parameters
S_LED_INT = int(0.66 * 255)  # max s-polarized led intensity
S_LED_MIN = int(0.05 * 255)  # minimum LED intensity (5% of max = 13)
P_LED_MAX = 255  # max p-polarized led intensity
P_MAX_INCREASE = 1.33  # max brightness increase factor for P vs S
S_COUNT_MAX = 64000  # DEPRECATED: Use profile.max_intensity_counts (62,000 for Flame-T)
P_COUNT_THRESHOLD = 3000  # minimum p-polarized count for successful calibration (adjusted for real hardware sensitivity)
MIN_INTEGRATION = 5  # DEPRECATED: Use profile.min_integration_time_ms
MAX_INTEGRATION = 100  # DEPRECATED: Use profile.max_integration_time_ms (200 ms for Flame-T!)

# Percentage-based calibration (NEW APPROACH - Development Mode)
DEVELOPMENT_MODE = True  # When True, skip validation thresholds to allow testing/fixing
TARGET_WAVELENGTH_MIN = 580  # nm - start of target wavelength range for calibration
TARGET_WAVELENGTH_MAX = 610  # nm - end of target wavelength range for calibration
TARGET_INTENSITY_PERCENT = 50  # % - target intensity as percentage of detector max (REDUCED from 80% to prevent P-mode saturation)
MIN_INTENSITY_PERCENT = 30  # % - minimum acceptable intensity (reduced from 60% to match new target)
MAX_INTENSITY_PERCENT = 60  # % - maximum acceptable intensity (reduced from 90% to prevent saturation)
DETECTOR_MAX_COUNTS = 65535  # Maximum detector counts (16-bit ADC)

# Step 4 constrained dual optimization targets (S-MODE CALIBRATION ONLY)
# P-mode integration time is calculated later using LIVE_MODE_INTEGRATION_FACTOR
WEAKEST_TARGET_PERCENT = 70  # % - target for weakest LED at LED=255 (maximize SNR for calibration)
WEAKEST_MIN_PERCENT = 60  # % - minimum acceptable for weakest LED during calibration
WEAKEST_MAX_PERCENT = 80  # % - maximum acceptable for weakest LED during calibration
STRONGEST_MAX_PERCENT = 95  # % - saturation threshold for strongest LED at LED≥25 (ensures calibration can succeed)
STRONGEST_MIN_LED = 25  # Minimum practical LED intensity (10% of 255) for strongest LED validation
MAX_READ_TIME = 200  # maximum total read time in milliseconds
CURVE_FIT_HEIGHT = 5  # height of transmission segment to take for width0
TRANS_SEG_H = 20  # height to define transmission segment
TRANS_SEG_H_REQ = 0.5  # factor for calibrated channel fitting height on both ends
AUTO_POLARIZE_ENABLE = False  # enable/disable auto-polarization during calibration
FILTERING_ON = True  # enabled/disable filtering
MED_FILT_WIN = 5  # default median filter window size

# Transmittance spectrum denoising (NEW - for improved peak tracking)
DENOISE_TRANSMITTANCE = True  # Enable Savitzky-Golay denoising on transmittance spectrum
DENOISE_WINDOW = 11  # Window size for Savitzky-Golay filter (must be odd, ~3nm smoothing)
DENOISE_POLYORDER = 3  # Polynomial order for Savitzky-Golay filter (cubic)

# Live mode integration time adjustment (to prevent saturation)
LIVE_MODE_INTEGRATION_FACTOR = 0.5  # Use 50% of calibrated integration time for live measurements

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
    from datetime import timezone
    TIME_ZONE = datetime.datetime.now(timezone.utc).astimezone().tzinfo

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
