"""Settings Configuration

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
                spec_file = Path(__file__).parent.parent / "build" / "main.spec"
            match = search("name='ezControl (.+ )?v(.+)',", spec_file.read_text())
            if match is None:
                return "0.2"  # Default fallback version
            return match[2]
        except (FileNotFoundError, AttributeError):
            return "0.2"  # Default fallback version


DEV = True
# Application identity for UI
SW_APP_NAME = "Affilab.core"
# Pin version to repository tag (requested)
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

# Standard color palette
GRAPH_COLORS = {"a": "k", "b": (255, 0, 81), "c": (0, 174, 255), "d": (0, 230, 65)}

# Colorblind-friendly palette (Okabe-Ito)
# Designed to be distinguishable for all types of colorblindness
GRAPH_COLORS_COLORBLIND = {
    "a": (1, 115, 178),  # Blue
    "b": (222, 143, 5),  # Orange
    "c": (2, 158, 115),  # Green
    "d": (204, 120, 188),  # Magenta
}

# Current active palette (can be toggled by user)
# Using colorblind-friendly Okabe-Ito palette by default for accessibility
ACTIVE_GRAPH_COLORS = GRAPH_COLORS_COLORBLIND.copy()

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

# Prevent recursion error
GRAPH_REGION_UPDATE_GAP = 0.1  # 100 ms

# Fields
UNIT = "RU"  # measurement units

# ==========================================
# TRANSMITTANCE DISPLAY ORIENTATION
# ==========================================
# When True, invert transmittance for visualization so the SPR feature appears as a peak
# UI plots will display 100 - Transmittance(%) and analysis figures will display 1 - T
INVERT_TRANSMISSION_VISUAL = False

# ==========================================
# DETECTOR-SPECIFIC PARAMETERS (Use profiles instead!)
# ==========================================
# DEPRECATED: These are now loaded from detector profiles
# Use: profile = get_current_detector_profile()
MIN_WAVELENGTH = 560  # DEPRECATED: Use profile.spr_wavelength_min_nm (GitHub: 560-720nm ROI)
MAX_WAVELENGTH = 720  # DEPRECATED: Use profile.spr_wavelength_max_nm
POL_WAVELENGTH = 620  # index for auto polarization

# ==========================================
# WAVELENGTH CACHE POLICY
# ==========================================
# Controls for caching wavelength calibration arrays on disk
# - WAVELENGTH_CACHE_ENABLED: master on/off for using cached wavelengths
# - WAVELENGTH_CACHE_MAX_AGE_DAYS: maximum age for cache to be considered valid
# You can also invalidate via env var EZ_WL_CACHE_INVALIDATE=1 or by creating
# the flag file generated-files/calibration_data/invalidate_wavelength_cache.flag
WAVELENGTH_CACHE_ENABLED: bool = True
WAVELENGTH_CACHE_MAX_AGE_DAYS: float = 7.0  # tighten from 30 → 7 days by default

# ==========================================
# ADVANCED SETTINGS OVERRIDES - TIMING ARCHITECTURE
# ==========================================
# These values can be set via Advanced Settings dialog to override calibration defaults
# ALL timing calculations derive from these base parameters

# Base timing parameters (can be changed in Advanced Settings)
LED_ON_TIME_MS = 225.0  # LED ON duration - optimized (actual=250ms with 25ms overhead)
DETECTOR_WAIT_MS = 45.0  # Optimized LED stabilization time (was 60ms)
MAX_INTEGRATION_PER_SCAN_MS = 62.5  # USB4000 hardware limit for integration time per scan
NUM_SCANS = 3  # Number of scans per spectrum (HAL averages these)
SAFETY_BUFFER_MS = 10.0  # Safety margin for timing calculations

# Derived timing (DO NOT MODIFY - calculated from base parameters)
# DETECTOR_ON_TIME = LED_ON_TIME - DETECTOR_WAIT
# DETECTOR_WINDOW = DETECTOR_ON_TIME - SAFETY_BUFFER
# Formula: num_scans × integration_time ≤ DETECTOR_WINDOW
#          integration_time ≤ DETECTOR_WAIT_MS (per-scan cap)

# Legacy overrides (deprecated - use base parameters above)
DETECTOR_ON_TIME_MS = None  # DEPRECATED: Use LED_ON_TIME_MS and DETECTOR_WAIT_MS
LED_OFF_TIME_MS = None  # LED OFF duration override (None = use default 0ms)

# ==========================================
# OLD TIMING PARAMETERS - DELETED
# ==========================================
# All timing now controlled by LED_ON_TIME_MS, DETECTOR_WAIT_MS, NUM_SCANS, SAFETY_BUFFER_MS
# No more PRE_LED_DELAY_MS, POST_LED_DELAY_MS, or LED_DELAY
# See Advanced Settings section above for all timing parameters

# Optional: one-cycle LED verification at maximum brightness in live mode
# When True, each channel will run the first live acquisition at LED=255 and log a clear message.
# This helps visually confirm LED activation and avoids flat spectra during bring-up.
LED_FORCE_255_TEST_CYCLE: bool = False

# Overnight Mode - Slow acquisition for long-term stability monitoring
# When enabled, adds delay between channels for 1 data point per minute
OVERNIGHT_MODE: bool = False  # Enable/disable overnight mode
OVERNIGHT_DELAY_SECONDS: float = 15.0  # Delay between channels (15s × 4 = 60s per cycle)

# ==========================================
# TIMING CALCULATION FORMULAS
# ==========================================
# All timing derived from base parameters above:
#
# DETECTOR_ON_TIME = LED_ON_TIME_MS - DETECTOR_WAIT_MS
#                  = 225ms - 45ms = 180ms
#
# DETECTOR_WINDOW = DETECTOR_ON_TIME - SAFETY_BUFFER_MS
#                 = 180ms - 10ms = 170ms
#
# Integration time constraints:
#   - DETECTOR_WAIT_MS = 45ms (LED stabilization wait)
#   - MAX_INTEGRATION_PER_SCAN_MS = 62.5ms (USB4000 hardware limit)
#
# num_scans calculation in live data:
#   1. Cap integration_time to MAX_INTEGRATION_PER_SCAN_MS (62.5ms max per scan)
#   2. num_scans = floor(DETECTOR_WINDOW / integration_time)
#   3. Total acquisition = num_scans × integration_time ≤ 170ms
#
# Example: integration_time = 60ms
#   → num_scans = floor(170ms / 60ms) = 2 scans
#   → Total = 4 × 40ms = 160ms (within 170ms window)

# Reference Signal Averaging
DARK_NOISE_SCANS = 25  # Maximum dark noise scans
REF_SCANS = NUM_SCANS  # Reference scans = same as live data scans

# Legacy LED parameters
S_LED_INT = int(0.66 * 255)  # max s-polarized led intensity
S_LED_MIN = int(0.05 * 255)  # minimum LED intensity (5% of max = 13)
P_LED_MAX = 255  # max p-polarized led intensity
P_MAX_INCREASE = 1.33  # max brightness increase factor for P vs S
S_COUNT_MAX = 64000  # DEPRECATED: Use profile.max_intensity_counts (62,000 for Flame-T)
P_COUNT_THRESHOLD = 3000  # minimum p-polarized count for successful calibration (adjusted for real hardware sensitivity)
MIN_INTEGRATION = 5  # DEPRECATED: Use profile.min_integration_time_ms
CYCLE_TIME = 1.3  # cycle time for all 4 channels
MAX_INTEGRATION = (
    70  # DEPRECATED: Use profile.max_integration_time_ms (70ms for 3-scan budget)
)

# Percentage-based calibration (NEW APPROACH - Development Mode)
DEVELOPMENT_MODE = True  # When True, skip validation thresholds to allow testing/fixing
TARGET_WAVELENGTH_MIN = 580  # nm - start of target wavelength range for calibration
TARGET_WAVELENGTH_MAX = 610  # nm - end of target wavelength range for calibration
TARGET_INTENSITY_PERCENT = (
    50  # % - CALIBRATION target ~32,768 counts (conservative - leaves room for boost)
)
MIN_INTENSITY_PERCENT = 40  # % - minimum acceptable intensity during calibration
MAX_INTENSITY_PERCENT = 70  # % - maximum acceptable intensity during calibration (stay under 76% to allow boost)
DETECTOR_MAX_COUNTS = 65535  # Maximum detector counts (16-bit ADC)

# ============================================================================
# STEP 4: INTEGRATION TIME OPTIMIZATION (CONSTRAINED DUAL OPTIMIZATION)
# ============================================================================
# OPTIMIZED CALIBRATION SEQUENCE:
# Step 3: Find weakest LED → Rank all LEDs by brightness
# Step 4: Constrained dual optimization:
#   PRIMARY GOAL: Maximize weakest LED signal (60-80% @ LED=255)
#   CONSTRAINT 1: Strongest LED must not saturate (<95% @ predicted LED)
#   CONSTRAINT 2: Integration time ≤ 70ms (allows 3 scans: 70ms × 3 = 210ms budget)
# Step 5: Re-measure dark noise
# Step 6: Apply LED calibration from Step 4 validation
#
# TIMING BUDGET CONSTRAINTS:
# - Target: ~1Hz per channel (4 channels = ~1.2Hz system rate)
# - Per-channel budget: 210ms (integration + readout + processing)
# - Max integration: 70ms per scan (allows 3 scans minimum)
# - Total cycle: 4 channels × 210ms = 840ms ≈ 1.19Hz
#
# SIGNAL TARGETS (with P-mode headroom):
WEAKEST_TARGET_PERCENT = (
    70  # % - target for weakest LED at LED=255 (ideal: ~45,900 counts)
)
WEAKEST_MIN_PERCENT = 60  # % - minimum acceptable (realistic: ~39,321 counts)
WEAKEST_MAX_PERCENT = 80  # % - maximum (leaves headroom: ~52,428 counts)
STRONGEST_MAX_PERCENT = (
    95  # % - strongest LED must stay below this (prevent saturation)
)
STRONGEST_MIN_LED = (
    25  # Minimum LED intensity for strongest channel (ensures some headroom)
)

# ACCEPTANCE CRITERIA:
# - Weakest LED ≥ 60% is acceptable (even if others are at 80%)
# - Don't over-optimize if marginal gains
# - Prioritize leaving LED headroom for P-mode boost
MAX_READ_TIME = 200  # maximum total read time in milliseconds

# === TRANSMISSION BASELINE CORRECTION ===
TRANSMISSION_BASELINE_METHOD = "percentile"  # Options: 'percentile', 'polynomial', 'off_spr', 'none'
TRANSMISSION_BASELINE_PERCENTILE = 95.0  # Percentile for 'percentile' method (80-99 typical)
TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE = 2  # Polynomial degree for 'polynomial' method (1=linear, 2=quadratic)
TRANSMISSION_OFF_SPR_WAVELENGTH_RANGE = (570.0, 580.0)  # Wavelength range (nm) for 'off_spr' method (Phase Photonics: avoid <570nm noise)

# === CALIBRATION MODE ===
USE_ALTERNATIVE_CALIBRATION = False  # Use alternative calibration method (disabled)

CURVE_FIT_HEIGHT = 5  # height of transmission segment to take for width0
TRANS_SEG_H = 20  # height to define transmission segment
TRANS_SEG_H_REQ = 0.5  # factor for calibrated channel fitting height on both ends
AUTO_POLARIZE_ENABLE = False  # enable/disable auto-polarization during calibration

# ============================================================================
# 🎚️ SINGLE SOURCE OF SMOOTHING CONTROL
# ============================================================================
# Set FILTERING_ON to control ALL data smoothing in the system:
#   - False: Completely raw, unsmoothed data (for debugging/validation)
#   - True: Full smoothing pipeline (temporal + spectral + Kalman)
FILTERING_ON = (
    True  # ✨ MASTER SMOOTHING SWITCH - ENABLED to match old software (4-5 RU target)
)

# Temporal smoothing (only active if FILTERING_ON=True)
MED_FILT_WIN = (
    5  # ✨ OLD SOFTWARE: backward-looking mean window (np.nanmean, not median!)
)

# Transmittance spectrum denoising (only active if FILTERING_ON=True)
DENOISE_TRANSMITTANCE = FILTERING_ON  # Controlled by master switch
DENOISE_WINDOW = (
    11  # Window size for Savitzky-Golay filter (must be odd, ~3nm smoothing)
)
DENOISE_POLYORDER = 3  # Polynomial order for Savitzky-Golay filter (cubic)

# Dynamic Savitzky–Golay smoothing for uniform channel noise
# When enabled, the processor will automatically choose SG parameters so
# that the resulting spectrum has approximately the same smoothness
# (measured as the std of the 2nd derivative) across channels.
# Set target to None to auto-target the median smoothness from a quick scan.
DYNAMIC_SG_ENABLED = True  # Use dynamic SG instead of a fixed window/polyorder
# Recommended initial target range: 5e-4 .. 5e-3 (depends on scaling)
# Leave as None to auto-calibrate per spectrum (uses median of a small grid scan)
DYNAMIC_SG_TARGET_SMOOTHNESS = None  # e.g., 0.001 for slightly stronger smoothing

# Kalman filtering for optimal time-series noise reduction (only active if FILTERING_ON=True)
# Provides 2-3× better SNR than Savitzky-Golay alone for real-time peak tracking
KALMAN_FILTER_ENABLED = FILTERING_ON  # Controlled by master switch
KALMAN_PROCESS_NOISE = (
    0.01  # Process noise covariance (Q) - how much we trust the model
)
KALMAN_MEASUREMENT_NOISE = (
    0.1  # Measurement noise covariance (R) - how much we trust the data
)

# Adaptive peak detection (O3A Optimization - saves ~3-5ms/spectrum)
# Focuses search on expected SPR wavelength range for faster, more robust peak finding
# Phase 1 optimization: Widened from 630-650nm to 600-800nm for better generality
ADAPTIVE_PEAK_DETECTION = True  # Enable adaptive peak detection within expected range
# Live tests target the ~605 nm band; tighten expected search band to reduce mis-tracking.
# Adjust as needed per chip/profile.
SPR_PEAK_EXPECTED_MIN = 580.0  # nm - minimum expected SPR peak wavelength
SPR_PEAK_EXPECTED_MAX = 660.0  # nm - maximum expected SPR peak wavelength

# ============================================================================
# ENHANCED PEAK TRACKING (4-Stage Pipeline for <2 RU Stability)
# ============================================================================

# Peak tracking method selection
# - 'numerical_derivative': Numerical gradient + zero-crossing (ORIGINAL from old software - shape-proof!)
# - 'consensus': Centroid + Parabolic combination - 2-3ms, <2 RU (REJECTED - buggy)
# - 'enhanced': 4-stage pipeline (FFT + Polynomial + Derivative + Kalman) - 15ms, <1 RU (REJECTED - binary signal)
# - 'centroid': Weighted centroid method - 1-2ms, <2 RU (FASTER, simpler)
# - 'parabolic': Simple parabolic interpolation - 0.5ms, 3-5 RU (fallback)
PEAK_TRACKING_METHOD = "numerical_derivative"  # Retained for fallback; centroid path returns early when enabled

# Enable enhanced peak tracking with FFT → Polynomial → Derivative pipeline
# ⚠️ DISABLED - Using old software's numerical_derivative method instead
# The old software achieves 4-5 RU raw noise with Fourier DST/IDCT derivative + 5-point temporal filter
# Enhanced pipeline was an attempt to improve, but old software method is proven
ENHANCED_PEAK_TRACKING = False  # Using numerical_derivative fallback (centroid takes precedence when enabled)

# Width-bias correction (fast, physics-aware centroid + asymmetry correction)
# When enabled, live peak estimation will use a wide-window centroid with right-side
# decay and correct it using an asymmetry feature measured from left/right half-depth edges.
WIDTH_BIAS_CORRECTION_ENABLED = (
    True  # Enable physics-aware centroid + width/asymmetry correction as primary path
)
WIDTH_BIAS_K = 0.5  # Slope for asymmetry correction (tune via simulator)
CENTROID_WINDOW_NM = 100.0  # Wide centroid window for stability
RIGHT_DECAY_GAMMA = 0.02  # Right-side exponential downweighting (nm^-1)
EDGE_DEPTH_FRACTION = 0.5  # Fraction of dip depth for left/right edge (e.g., 50%)

# Fourier Regularization Parameter for numerical_derivative method
# Controls noise reduction in Fourier DST/IDCT derivative calculation
# Formula: weights = φ / (1 + α·φ²·(1 + φ²)) where φ = π/n·k
# Higher α = stronger noise suppression, smoother derivative
# Lower α = less suppression, more responsive to high-frequency features
# Default: 2000 (from old software - achieves 4-5 RU noise)
# Current system: 1 RU noise at α=2000
# Optimized: 3430 (via optimize_fourier_alpha.py with synthetic data)
# Test range: 500-10,000 (use optimize_fourier_alpha.py)
FOURIER_ALPHA = 3430  # Regularization parameter for Fourier derivative (optimized)

# Stage 1: FFT Preprocessing Parameters (only used if ENHANCED_PEAK_TRACKING=True)
FFT_CUTOFF_FREQUENCY = (
    0.20  # INCREASED from 0.15 - less aggressive smoothing, more responsive
)
FFT_NOISE_REDUCTION = True  # Enable FFT-based high-frequency noise removal

# Stage 2: Polynomial Fitting Parameters (only used if ENHANCED_PEAK_TRACKING=True)
POLYNOMIAL_DEGREE = 4  # REDUCED from 6 - simpler fit, less overfitting, faster response
POLYNOMIAL_FIT_RANGE = (
    600,
    675,
)  # Full SPR dip range - covers entire resonance feature

# Stage 3: Derivative Peak Finding (only used if ENHANCED_PEAK_TRACKING=True)
# (Uses analytical derivative of polynomial - no additional parameters needed)

# Stage 4: Temporal Smoothing Parameters (only used if ENHANCED_PEAK_TRACKING=True)
# CRITICAL: Old software achieved 4-5 RU by applying temporal filtering to sensorgram
# This is NOT "artificial" - it's REQUIRED for matching old software performance
TEMPORAL_SMOOTHING_ENABLED = (
    True  # ENABLED - Achieves 4-5 RU target (old software used this)
)
TEMPORAL_SMOOTHING_METHOD = "kalman"  # Kalman filter (optimal for real-time tracking)

# =============================================================================
# SESSION QUALITY MONITORING (FWHM-Based QC System)
# =============================================================================
# When enabled, the system will track FWHM (Full Width at Half Maximum) of the SPR
# peak throughout each recording session and provide:
#   - Real-time RGB LED status feedback (Green/Yellow/Red quality indicator)
#   - Per-channel FWHM history tracking (only within 580-630nm valid range)
#   - End-of-session QC report with statistics and historical comparison
#   - Session-based tracking (resets each recording, not cumulative)
#
# Quality Thresholds (user-specified):
#   - <30nm:   Excellent (Green LED)
#   - 30-60nm: Good     (Yellow LED)
#   - ≥60nm:   Poor     (Red LED)
#
# Wavelength Validation:
#   - Only peaks within 580-630nm are tracked for QC purposes
#   - Out-of-range peaks are ignored but logged for debugging
#
# Feature Status: DISABLED for controlled rollout pending user testing
ENABLE_SESSION_QUALITY_MONITORING: bool = False  # Master switch for FWHM QC system

# Quality thresholds for FWHM-based grading (nm)
FWHM_EXCELLENT_THRESHOLD_NM: float = 30.0  # Green:  FWHM < 30nm
FWHM_GOOD_THRESHOLD_NM: float = 60.0  # Yellow: 30nm ≤ FWHM < 60nm
# Red:    FWHM ≥ 60nm

# Wavelength range for QC validation (only peaks within this range are tracked)
QC_WAVELENGTH_MIN_NM: float = 580.0  # Minimum wavelength for QC tracking
QC_WAVELENGTH_MAX_NM: float = 630.0  # Maximum wavelength for QC tracking

# Degradation detection threshold (nm/min)
QC_DEGRADATION_ALERT_THRESHOLD: float = 0.5  # Alert if FWHM increases by >0.5nm/min

# Session history persistence (stored in device directory)
QC_MAX_SESSION_HISTORY: int = 50  # Keep last 50 sessions for baseline comparison

# =============================================================================
# CONSENSUS PEAK TRACKING (Phase 1 - v0.2.0)
# =============================================================================
# Combines centroid + parabolic methods for robust peak detection
# Invariant to peak shape and intensity variations

# Spectral smoothing (Savitzky-Golay filter)
CONSENSUS_SAVGOL_WINDOW = 7  # Window size (odd number, 5-11 recommended)
CONSENSUS_SAVGOL_POLYORDER = 3  # Polynomial order (2-3 recommended)

# Centroid method parameters
CONSENSUS_TARGET_PIXELS = 20  # Target pixels for adaptive thresholding (15-25)
CONSENSUS_SEARCH_RANGE = (600, 720)  # SPR wavelength range (nm)

# Outlier detection
CONSENSUS_OUTLIER_THRESHOLD = 3.0  # MAD multiplier (2.0-4.0, higher = more lenient)
CONSENSUS_HISTORY_SIZE = 10  # Number of recent peaks for outlier detection

# Method weighting (Phase 1: fixed 60/40, Phase 3: adaptive)
CONSENSUS_CENTROID_WEIGHT = 0.60  # Centroid weight (0.5-0.7 recommended)
CONSENSUS_PARABOLIC_WEIGHT = 0.40  # Parabolic weight (1 - centroid_weight)

# =============================================================================
# ACQUISITION SPEED OPTIMIZATION
# =============================================================================

# Integration time and scan averaging for optimal noise vs speed balance
# ✨ MATCHING OLD SOFTWARE EXACTLY: 2 scans × 100ms = 200ms per spectrum
# Old software: 2 scans × 100ms = 200ms/channel × 4 = 800ms + 300ms overhead = 1.1s
# Old LED values: (82, 231, 41, 45) for channels (a, b, c, d)
#
# Strategy: 200ms budget per channel (matching old software)
# At 100ms integration: 2 scans fit in budget → better SNR (√2 improvement)
# At 130ms integration: only 1 scan fits → worse SNR despite more photons
INTEGRATION_TIME_MS = 100.0  # ✨ 100ms allows 2 scans within 200ms budget
# Default placeholder; live/global now uses calculate_dynamic_scans based on 200ms budget
NUM_SCANS_PER_ACQUISITION = 2
# Total acquisition time = 100ms × 2 = 200ms per channel (matches old software exactly)
TEMPORAL_SMOOTHING_METHOD = "kalman"  # "kalman" or "moving_average"
TEMPORAL_WINDOW_SIZE = 5  # Moving average window (if not using Kalman)
KALMAN_MEASUREMENT_NOISE = 1.0  # R parameter: trust measurements more (faster tracking)
KALMAN_PROCESS_NOISE = 0.5  # Q parameter: allow more change (reduce lag)

# ============================================================================
# GUI RENDERING PERFORMANCE (G1, G4 Optimizations)
# ============================================================================

# G1: Antialiasing - trades rendering quality for speed
ENABLE_ANTIALIASING_LIVE_MODE = (
    False  # Disable for 20% faster GUI rendering (2-3ms saved)
)
ENABLE_ANTIALIASING_STATIC = True  # Keep for publication-quality screenshots

# G4: GUI Update Throttling - reduce update frequency for slower machines
GUI_UPDATE_EVERY_N_CYCLES = 1  # 1=every cycle (default), 2=every other, 3=every 3rd

# ============================================================================

# ============================================================================
# LIVE MODE SMART BOOST (20-40% increase to offset P-pol dampening)
# ============================================================================
# Strategy:
# 1. Step 6 LED intensities are FIXED and never change (baseline from S-pol calibration)
# 2. Integration time can be boosted 20-40% to offset P-pol signal dampening
# 3. Smart constraints enforce safety:
#    - Stay below saturation: ~90% detector max (59,000 counts for 65535 max)
#    - Stay within time budget: integration × scans ≤ 200ms per spectrum
# 4. Boost is intelligent: reduces if signal would saturate, respects 200ms budget
LIVE_MODE_MAX_INTEGRATION_MS = (
    200.0  # Maximum integration time per spectrum (ms) - hard budget limit
)
LIVE_MODE_TARGET_INTENSITY_PERCENT = (
    90  # % - target 90% detector max (allows headroom for P-pol fluctuations)
)
LIVE_MODE_SATURATION_THRESHOLD_PERCENT = (
    92  # % - if signal exceeds this, reduce boost to prevent saturation
)
LIVE_MODE_MIN_BOOST_FACTOR = 1.0  # Never reduce integration time below calibrated value
LIVE_MODE_MAX_BOOST_FACTOR = (
    1.4  # Maximum boost: 1.4× = 40% increase (conservative, safe)
)

# Display delay for multi-point processing stabilization
# First N seconds of data are collected but not displayed to allow temporal filters,
# Kalman filters, and multi-point peak tracking algorithms to reach steady state
LIVE_MODE_DISPLAY_DELAY_SECONDS = (
    10.0  # Hide sensorgram for first 10 seconds after live start
)

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

# ==========================================
# CALIBRATION QC GATING
# ==========================================
# When True, QC validation can short-circuit full calibration if it passes.
# When False, QC is bypassed and the system will run the full calibration flow.
# You can toggle this at runtime and restart calibration.
FORCE_FULL_CALIBRATION: bool = True  # Suspend QC and run full calibration

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

CONSOLE_LOG_LEVEL = logging.INFO  # WARNING = production (fast, clean console)
# INFO = development (more details)
# DEBUG = troubleshooting (verbose)

# === Performance Profiling Settings ===
PROFILING_ENABLED = False  # Enable performance profiling
PROFILING_REPORT_INTERVAL = 30  # Seconds between profiling reports (if enabled)

# =============================================================================

# Device types and timezone
DEVICES = ["PicoP4SPR", "PicoEZSPR"]  # Supported device types
import datetime

# Robust timezone: prefer datetime.timezone.utc; fallback if needed
try:
    tz_utc = datetime.timezone.utc
except Exception:
    # Very old Python fallback (unlikely)
    tz_utc = None

if tz_utc is not None:
    TIME_ZONE = datetime.datetime.now(tz_utc).astimezone().tzinfo
else:
    # Fallback: local timezone
    TIME_ZONE = datetime.datetime.now().astimezone().tzinfo

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
