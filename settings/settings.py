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
        spec_file = Path("build/main.spec")
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
# ✨ Phase 2 Optimization: Reduced to 4 scans to match live acquisition (50ms × 4 = 200ms)
DARK_NOISE_SCANS = 4  # number of scans to average in dark noise measurement (was 30)
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
FILTERING_ON = False  # DISABLED for development - see raw unfiltered data
MED_FILT_WIN = 5  # default median filter window size (when filtering is enabled)

# Transmittance spectrum denoising (NEW - for improved peak tracking)
DENOISE_TRANSMITTANCE = True  # Enable Savitzky-Golay denoising on transmittance spectrum
DENOISE_WINDOW = 11  # Window size for Savitzky-Golay filter (must be odd, ~3nm smoothing)
DENOISE_POLYORDER = 3  # Polynomial order for Savitzky-Golay filter (cubic)

# Kalman filtering for optimal time-series noise reduction (OPTIONAL - adds ~0.5ms/spectrum)
# Provides 2-3× better SNR than Savitzky-Golay alone for real-time peak tracking
KALMAN_FILTER_ENABLED = True  # Enable Kalman filter after Savitzky-Golay denoising
KALMAN_PROCESS_NOISE = 0.01  # Process noise covariance (Q) - how much we trust the model
KALMAN_MEASUREMENT_NOISE = 0.1  # Measurement noise covariance (R) - how much we trust the data

# Adaptive peak detection (O3A Optimization - saves ~3-5ms/spectrum)
# Focuses search on expected SPR wavelength range for faster, more robust peak finding
# Phase 1 optimization: Widened from 630-650nm to 600-800nm for better generality
ADAPTIVE_PEAK_DETECTION = True  # Enable adaptive peak detection within expected range
SPR_PEAK_EXPECTED_MIN = 600.0  # nm - minimum expected SPR peak wavelength (Phase 1: widened)
SPR_PEAK_EXPECTED_MAX = 800.0  # nm - maximum expected SPR peak wavelength (Phase 1: widened)

# ============================================================================
# ENHANCED PEAK TRACKING (4-Stage Pipeline for <2 RU Stability)
# ============================================================================

# Peak tracking method selection
# - 'enhanced': 4-stage pipeline (FFT + Polynomial + Derivative + Kalman) - 15ms, <1 RU
# - 'centroid': Weighted centroid method - 1-2ms, <2 RU (FASTER, simpler)
# - 'parabolic': Simple parabolic interpolation - 0.5ms, 3-5 RU (fallback)
PEAK_TRACKING_METHOD = 'centroid'  # ✨ TESTING: Centroid method (5-10× faster than enhanced)

# Enable enhanced peak tracking with FFT → Polynomial → Derivative pipeline
# ⚠️ CURRENTLY DISABLED - Using simple direct minimum for better time resolution
# The enhanced pipeline can introduce lag and mask real SPR binding events
# Only enable if you need noise reduction MORE than time resolution
ENHANCED_PEAK_TRACKING = True  # ENABLED: Using FFT + Polynomial (Stages 1-3 only, NO temporal smoothing)

# Stage 1: FFT Preprocessing Parameters (only used if ENHANCED_PEAK_TRACKING=True)
FFT_CUTOFF_FREQUENCY = 0.20  # INCREASED from 0.15 - less aggressive smoothing, more responsive
FFT_NOISE_REDUCTION = True   # Enable FFT-based high-frequency noise removal

# Stage 2: Polynomial Fitting Parameters (only used if ENHANCED_PEAK_TRACKING=True)
POLYNOMIAL_DEGREE = 4           # REDUCED from 6 - simpler fit, less overfitting, faster response
POLYNOMIAL_FIT_RANGE = (600, 675)  # Full SPR dip range - covers entire resonance feature

# Stage 3: Derivative Peak Finding (only used if ENHANCED_PEAK_TRACKING=True)
# (Uses analytical derivative of polynomial - no additional parameters needed)

# Stage 4: Temporal Smoothing Parameters (only used if ENHANCED_PEAK_TRACKING=True)
TEMPORAL_SMOOTHING_ENABLED = False     # DISABLED - Artificial smoothing masks real SPR signal changes
#   ⚠️ DO NOT ENABLE unless you want to sacrifice time resolution for noise reduction
#   SPR needs to track REAL binding events, not smooth them away!

# =============================================================================
# ACQUISITION SPEED OPTIMIZATION
# =============================================================================

# Integration time and scan averaging for optimal noise vs speed balance
# ✨ PHASE 5 AGGRESSIVE: Targeting 1.1s cycle time to match old software
# 
# SPEED PRESETS:
# - ULTRA FAST: 30ms × 3 scans = 90ms/channel × 4 = 360ms + overhead = ~1.0s total ⚡⚡⚡
# - AGGRESSIVE: 35ms × 3 scans = 105ms/channel × 4 = 420ms + overhead = ~1.1s total ⚡⚡
# - BALANCED:   40ms × 4 scans = 160ms/channel × 4 = 640ms + overhead = ~1.2s total ⚡
# - SAFE:       50ms × 4 scans = 200ms/channel × 4 = 800ms + overhead = ~1.4s total
#
# Current target: Match old software at 1.1s/cycle
INTEGRATION_TIME_MS = 35.0      # ✨ AGGRESSIVE: 35ms (was 40ms, was 50ms baseline)
NUM_SCANS_PER_ACQUISITION = 3   # ✨ AGGRESSIVE: 3 scans (was 4) - reduces noise averaging but gains speed
# Total acquisition time = 35ms × 3 = 105ms per channel (4 channels = 420ms base + ~680ms overhead = 1.1s)
TEMPORAL_SMOOTHING_METHOD = "kalman"   # "kalman" or "moving_average"
TEMPORAL_WINDOW_SIZE = 5               # Moving average window (if not using Kalman)
KALMAN_MEASUREMENT_NOISE = 1.0         # R parameter: trust measurements more (faster tracking)
KALMAN_PROCESS_NOISE = 0.5             # Q parameter: allow more change (reduce lag)

# ============================================================================
# GUI RENDERING PERFORMANCE (G1, G4 Optimizations)
# ============================================================================

# G1: Antialiasing - trades rendering quality for speed
ENABLE_ANTIALIASING_LIVE_MODE = False  # Disable for 20% faster GUI rendering (2-3ms saved)
ENABLE_ANTIALIASING_STATIC = True      # Keep for publication-quality screenshots

# G4: GUI Update Throttling - reduce update frequency for slower machines
GUI_UPDATE_EVERY_N_CYCLES = 1  # 1=every cycle (default), 2=every other, 3=every 3rd

# ============================================================================

# Live mode integration time BOOST (maximize signal while staying under 200ms)
# Strategy: Calibration uses conservative 50% target to avoid saturation during optimization
# Live mode can boost signal closer to 80% since we're only measuring, not iterating
# ⚠️ REDUCED from 75% to 60% to prevent saturation in bright channels (C, D)
LIVE_MODE_MAX_INTEGRATION_MS = 200.0  # Maximum integration time for live mode (ms)
LIVE_MODE_TARGET_INTENSITY_PERCENT = 60  # % - target 60% of detector max (was 75%, reduced to prevent saturation)
LIVE_MODE_MIN_BOOST_FACTOR = 1.0  # Never reduce integration time below calibrated value
LIVE_MODE_MAX_BOOST_FACTOR = 2.5  # Maximum boost allowed (up to 2.5× calibrated time)

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

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
# Control logging verbosity for performance optimization
# Console logging can add 1-2ms overhead per cycle with DEBUG level
# 
# Levels (increasing verbosity):
# - ERROR: Only critical errors (fastest, minimal output)
# - WARNING: Warnings and errors (recommended for production)
# - INFO: General information + warnings + errors (moderate output)
# - DEBUG: Detailed debugging info (slowest, verbose output)
#
# File logging always uses DEBUG level (full details for troubleshooting)
# Console logging uses CONSOLE_LOG_LEVEL (reduced for performance)

import logging
CONSOLE_LOG_LEVEL = logging.WARNING  # WARNING = production (fast, clean console)
                                      # INFO = development (more details)
                                      # DEBUG = troubleshooting (verbose)

# =============================================================================

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
