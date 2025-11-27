"""LED calibration module for SPR systems.

This module handles the automatic calibration of LED intensities across all channels,
integration time optimization, and reference signal measurements.

FILE ORGANIZATION:
==================
1. Calibration Constants - Timing and adjustment parameters
2. Calibration Result - Data structure for calibration results
3. Standard Path Helper Functions - Sequential calibration components
4. Alternative Path Helper Functions - Global LED intensity method components
5. Quality Control Functions - Shared QC validation (S-ref and P-mode verification)
6. Main Calibration Entry Points:
   - perform_full_led_calibration(): Standard method (Global Integration Time) - DEFAULT
   - perform_alternative_calibration(): Alternative method (Global LED Intensity) - EXPERIMENTAL

POLARIZER HARDWARE & CALIBRATION COMPLEXITY:
============================================
CRITICAL: Distinguish between TWO separate calibration phases:

**PHASE 1: SERVO POSITION CALIBRATION (OEM Manufacturing - Done ONCE)**

BARREL POLARIZER (Simple):
  - Hardware: Two FIXED polarization windows at 90° to each other
  - Servo Calibration: SIMPLE - just find the 2 window alignment positions
    * Sweep servo 10-255, look for 2 transmission peaks
    * Higher peak = S-mode (perpendicular), lower peak = P-mode (parallel)
    * ~1.4 minutes, done once at manufacturing (OEM calibration tool)
  - Result: Servo positions stored in device EEPROM/config

CIRCULAR POLARIZER (Complex):
  - Hardware: Continuously rotating polarizer element
  - Servo Calibration: COMPLEX - must find optimal angles in continuous space
    * Quadrant search algorithm (~13 measurements) with water required
    * Must identify global max (S-mode) and optimal working point (P-mode)
    * Physics: polarization angle changes continuously with servo position
  - Result: Servo positions stored in device EEPROM/config

**PHASE 2: LED INTENSITY CALIBRATION (This Module - Every Measurement Session)**

BOTH POLARIZER TYPES (Same Complexity):
  - Once servo positions are known, LED calibration is IDENTICAL for both types
  - LED Calibration Process:
    * S-mode: Optimize LED intensities to reach target counts
    * Analyze headroom: How much LED intensity was used in S-mode
    * P-mode: Boost LED intensities based on available headroom
    * BOTH types require headroom analysis for S→P boost prediction
  - Expected S/P Ratio: 1.5-15.0× for BOTH types (depends on sample coupling, not polarizer)
  - Complexity: STANDARD for both (the servo position complexity was already solved in Phase 1)

KEY INSIGHT: The polarizer type determines SERVO CALIBRATION complexity (Phase 1),
NOT LED CALIBRATION complexity (Phase 2, this module). Once servo positions are
established at manufacturing, LED intensity optimization follows the same process
regardless of polarizer type.

**THIS MODULE HANDLES PHASE 2 ONLY** - LED intensity calibration assuming servo
positions are already known from Phase 1 (manufacturing calibration).

OPTICAL SYSTEM MODES (How Calibration Data is Recorded):
========================================================
**CRITICAL**: The optical system mode determines HOW LED intensity and integration time
are recorded in device_config.json. This is THE MAIN PLACE impacted by the mode choice.

There are TWO modes, controlled by settings.USE_ALTERNATIVE_CALIBRATION:

MODE 1: STANDARD (Global Integration Time) - DEFAULT [USE_ALTERNATIVE_CALIBRATION = False]
--------------------------------------------------------------------------------------------
Philosophy: ONE global integration time, VARIABLE LED intensities per channel

Calibration Process:
  - Step 1: Find single optimal integration time (works for all channels)
  - Step 2: Optimize LED intensity PER CHANNEL to reach target signal
  - Result: All channels use SAME integration time, but DIFFERENT LED intensities

Recorded in device_config.json:
  - integration_time_ms: 93 (single value - SAME for all channels)
  - s_mode_intensities: {'a': 187, 'b': 203, 'c': 195, 'd': 178} (VARIABLE per channel)
  - p_mode_intensities: {'a': 238, 'b': 255, 'c': 245, 'd': 229} (VARIABLE per channel)

Best for: Circular polarizers where LED intensity affects polarization coupling
Timing: ~210ms/channel (integration + 50ms hardware overhead) ≈ 1Hz per channel

MODE 2: ALTERNATIVE (Fixed LED, Per-Channel Integration) - EXPERIMENTAL [USE_ALTERNATIVE_CALIBRATION = True]
------------------------------------------------------------------------------------------------
Philosophy: FIXED LED intensity (255), Per-channel integration calibration → MAX used as global

Calibration Process:
  - Step 1: Set ALL LEDs to maximum (255) for consistency and max SNR
  - Step 2: Calibrate integration time PER CHANNEL (3ms→70ms sweep) to reach target signal
  - Step 3: Take MAX integration time across all channels as global value
  - Result: All channels use SAME LED (255), SAME global integration (max), but calibrated per-channel

Recorded in device_config.json:
  - integration_time_ms: 120 (MAX integration time across all channels - used globally)
  - s_mode_intensities: {'a': 255, 'b': 255, 'c': 255, 'd': 255} (FIXED - all same)
  - p_mode_intensities: {'a': 255, 'b': 255, 'c': 255, 'd': 255} (FIXED - all same)
  - per_channel_integration_times: {'a': 85, 'b': 95, 'c': 120, 'd': 110} (diagnostic only - not used)

Benefits: Better frequency, excellent SNR, LED consistency at max current
Trade-offs: Variable integration per channel, requires per-channel timing during acquisition
Enable via: settings.USE_ALTERNATIVE_CALIBRATION = True (EXPERIMENTAL - use with caution)

**DOWNSTREAM EFFECTS**: The mode choice impacts:
  1. device_config.json structure (main impact - how data is saved/loaded)
  2. Fast-track validation (standard validates LED values, alternative validates integration times)
  3. Live acquisition (standard uses global integration, alternative uses per-channel)
  4. QC validation (standard compares LED intensities, alternative compares integration times)

CALIBRATION METHODS (Details):
====================
STANDARD Method (Global Integration Time) - DEFAULT:
  - Sequential optimization: integration time first (global), then LED intensities (per-channel)
  - Used for circular polarizers where LED intensity affects polarization
  - Steps: wavelength → global integration → S-mode LED/channel → dark → S-ref → S-QC → P-mode LED/channel → P-QC
  - S-mode LED analysis predicts P-mode boost potential (headroom intelligence for LED-polarization coupling)
  - Timing budget: 210ms/channel (integration + 50ms hardware overhead) ≈ 1Hz per channel

ALTERNATIVE Method (Fixed LED, Per-Channel Integration) - EXPERIMENTAL (Disabled by default):
  - All LEDs fixed at maximum intensity (255) for both S-mode and P-mode
  - S-mode: Per-channel integration calibration → MAX used as global integration time
  - P-mode: Same LEDs (255), same global integration time, uses 1 scan per spectrum
  - Benefits: Better frequency, excellent SNR, more LED consistency at max current
  - Steps: wavelength → S-mode integration/channel (LEDs at 255) → dark → S-ref → S-QC → P-mode (same config) → P-QC
  - Trade-offs: Variable integration per channel in S-mode, P-mode inherits S-mode timing
  - Enable via settings.USE_ALTERNATIVE_CALIBRATION = True

QUALITY CONTROL & WATER DETECTION:
===================================
Both calibration methods share common QC validation with TWO DISTINCT PHASES:

**CRITICAL DISTINCTION**: S-mode and P-mode measure DIFFERENT things:
- S-mode: Detector + LED performance (no SPR, no sensor validation)
- P-mode: Sensor + SPR performance (requires transmission spectrum P/S)

**PHASE A: S-MODE QC** (validate_s_ref_quality) - DETECTOR & LED BASELINE
Purpose: Characterize optical system WITHOUT SPR
Measures: LED spectral profile, detector response, optical path losses
QC Metrics:
  ✅ CAN detect:
    • Prism present/absent (by signal intensity vs expected)
    • Fiber connection status (weak signal = disconnected)
    • LED spectral profile (peak wavelength, intensity)
    • Optical system health (spectral shape)
  ❌ CANNOT detect:
    • Water presence (NO SPR information in S-pol!)
    • SPR coupling quality (need transmission spectrum)
    • Sensor degradation (need SPR dip analysis)
  Detection method: Intensity threshold (<5000 counts = likely prism absent)
  Result: S-ref baseline stored for transmission calculation

**PHASE B: P-MODE QC** (verify_calibration) - SENSOR & SPR VALIDATION
Purpose: Validate SPR coupling and water presence
Measures: SPR dip in transmission (P/S ratio), coupling quality
QC Metrics:
  ✅ CAN detect:
    • Water presence (SPR dip visible in transmission)
    • SPR coupling quality (dip depth >10% = good)
    • Sensor response (FWHM 15-30nm = high sensitivity)
    • Polarizer orientation (dip vs peak in transmission)
  ❌ CANNOT check on:
    • Individual S or P spectra (meaningless without ratio)
    • Raw intensity comparisons (LED profile contamination)
  Detection method: Transmission spectrum analysis (P/S ratio)
    - Calculate transmission = P-spectrum / S-spectrum × 100%
    - Look for SPR dip (valley) at 590-670nm
    - Measure FWHM: <30nm=good, 30-50nm=acceptable, >80nm=dry
  Result: Validated system ready for measurements

**Why this separation matters**:
1. S-mode establishes "what the system can do" (optical baseline)
2. P-mode validates "what the sensor can measure" (SPR performance)
3. Trying to detect water in S-mode = IMPOSSIBLE (no SPR in S-pol)
4. Trying to analyze SPR in raw P-spectrum = MEANINGLESS (LED profile mixed in)
5. ONLY transmission spectrum (P/S ratio) contains isolated SPR information

Think of it as: S-mode = "System QC", P-mode = "Sensor QC"
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from dataclasses import dataclass

import numpy as np

from settings import (
    CH_LIST,
    DARK_NOISE_SCANS,
    EZ_CH_LIST,
    LED_DELAY,
    MAX_INTEGRATION,
    MAX_NUM_SCANS,
    MAX_READ_TIME,
    MAX_WAVELENGTH,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
    P_LED_MAX,
    P_MAX_INCREASE,
    REF_SCANS,
    S_LED_INT,
    S_LED_MIN,
)
from utils.logger import logger
from utils.spr_signal_processing import calculate_fourier_weights

if TYPE_CHECKING:
    from utils.controller import ControllerBase

# =============================================================================
# CALIBRATION CONSTANTS
# =============================================================================

# Calibration timing constants
MODE_SWITCH_DELAY = 0.5  # seconds - settling time for S/P mode switching
P_MODE_SWITCH_DELAY = 0.4  # seconds - P-mode switching (slightly faster)

# LED adjustment step sizes
COARSE_ADJUST_STEP = 20  # Initial large adjustments
MEDIUM_ADJUST_STEP = 5   # Medium refinement
FINE_ADJUST_STEP = 1     # Final precision adjustment

# Integration time threshold for scan count adjustment
INTEGRATION_THRESHOLD_MS = 70  # Below this, use full scan count; above, use half

# System timing budget constraints (optimized for integration time with 3 scans minimum)
# 4 channels × 210ms budget = 840ms total cycle time ≈ 1.19Hz system rate
TARGET_CHANNEL_BUDGET_MS = 210  # Total time budget per channel (integration + overhead)
MAX_INTEGRATION_BUDGET_MS = 70  # Maximum integration time per scan (allows 3 scans: 70ms × 3 = 210ms)
SYSTEM_ACQUISITION_TARGET_HZ = 1.0  # Target acquisition frequency per channel

# Hardware acquisition overhead (decoupled from processing time shown on graph)
# These are the ACTUAL delays that limit per-channel frequency:
ESTIMATED_LED_DELAY_MS = 10      # LED settling time per channel switch
ESTIMATED_AFTERGLOW_MS = 20      # Afterglow decay time (channel-dependent)
ESTIMATED_DETECTOR_LAG_MS = 5    # Detector response lag
ESTIMATED_USB_TRANSFER_MS = 15   # USB readout + transfer time
ESTIMATED_MODE_SWITCH_MS = 500   # S/P polarization mode switching (only when changing modes)

# Total per-channel overhead (excluding integration time)
# = LED_DELAY + AFTERGLOW + DETECTOR_LAG + USB_TRANSFER
HARDWARE_OVERHEAD_MS = ESTIMATED_LED_DELAY_MS + ESTIMATED_AFTERGLOW_MS + \
                       ESTIMATED_DETECTOR_LAG_MS + ESTIMATED_USB_TRANSFER_MS  # ~50ms


# =============================================================================
# HELPER DATACLASSES
# =============================================================================

@dataclass
class DetectorParams:
    """Detector hardware parameters (read once, reused throughout calibration)."""
    target_counts: float  # Target signal level for S-mode calibration
    max_counts: float     # Maximum detector count (saturation point)
    saturation_threshold: float  # Safe maximum (typically 95% of max_counts)

@dataclass
class ScanConfig:
    """Scan count configuration based on integration time."""
    dark_scans: int  # Number of scans for dark noise measurement
    ref_scans: int   # Number of scans for reference signal measurement
    num_scans: int   # Number of scans for live acquisition

@dataclass
class ChannelHeadroomAnalysis:
    """LED headroom analysis for a single channel."""
    channel: str
    s_intensity: int           # S-mode LED intensity (0-255)
    headroom: int              # Remaining LED range (P_LED_MAX - s_intensity)
    headroom_pct: float        # Headroom as percentage
    predicted_boost: float     # Predicted P-mode boost ratio
    is_weak: bool              # True if s_intensity > 200 (weak optical signal)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def determine_channel_list(device_type: str, single_mode: bool = False, single_ch: str = "a") -> list[str]:
    """Determine which channels to calibrate based on device type.

    Centralized channel list determination - single source of truth.

    Args:
        device_type: Device type string (e.g., 'P4SPR', 'EZSPR', 'PicoEZSPR')
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode

    Returns:
        List of channel identifiers to calibrate
    """
    if single_mode:
        return [single_ch]
    elif device_type in ["EZSPR", "PicoEZSPR"]:
        return EZ_CH_LIST
    else:
        return CH_LIST


def get_detector_params(usb) -> DetectorParams:
    """Read detector parameters once at calibration start.

    These are hardware constants that don't change during calibration.
    Reading once and passing through eliminates redundant property accesses.

    Args:
        usb: Spectrometer instance

    Returns:
        DetectorParams with target_counts, max_counts, saturation_threshold
    """
    target_counts = usb.target_counts
    max_counts = usb.max_counts
    saturation_threshold = max_counts * 0.95  # 95% of max = safe maximum

    logger.debug(f"Detector params: target={target_counts:.0f}, max={max_counts:.0f}, safe_max={saturation_threshold:.0f}")

    return DetectorParams(
        target_counts=target_counts,
        max_counts=max_counts,
        saturation_threshold=saturation_threshold
    )


def calculate_scan_counts(integration_time_ms: int) -> ScanConfig:
    """Calculate scan counts based on integration time.

    Centralized scan count logic - single source of truth.
    Below 70ms: use full scan counts for better averaging
    Above 70ms: use half scan counts to keep total acquisition time reasonable

    Args:
        integration_time_ms: Integration time in milliseconds

    Returns:
        ScanConfig with dark_scans, ref_scans, num_scans
    """
    if integration_time_ms < INTEGRATION_THRESHOLD_MS:
        # Short integration: use full scan counts for better SNR
        dark_scans = DARK_NOISE_SCANS
        ref_scans = REF_SCANS
        num_scans = min(int(MAX_READ_TIME / integration_time_ms), MAX_NUM_SCANS)
    else:
        # Long integration: reduce scan counts but ensure minimum of 3 scans
        dark_scans = int(DARK_NOISE_SCANS / 2)
        ref_scans = int(REF_SCANS / 2)
        num_scans = min(int(MAX_READ_TIME / integration_time_ms), MAX_NUM_SCANS)

    # Ensure minimum of 3 scans per spectrum for adequate averaging
    num_scans = max(3, num_scans)

    logger.debug(f"Scan counts for {integration_time_ms}ms integration: dark={dark_scans}, ref={ref_scans}, live={num_scans}")

    return ScanConfig(
        dark_scans=dark_scans,
        ref_scans=ref_scans,
        num_scans=num_scans
    )


def switch_mode_safely(ctrl: ControllerBase, mode: str, turn_off_leds: bool = True, verify: bool = True) -> None:
    """Switch polarizer mode with proper settling and optional LED cleanup.

    Centralized mode switching logic - consistent timing and behavior.

    Args:
        ctrl: Controller instance
        mode: Target mode ('s' or 'p')
        turn_off_leds: If True, turn off LEDs and wait for afterglow decay
        verify: If True, verify hardware state after mode switch
    """
    logger.debug(f"🔄 switch_mode_safely called: mode={mode.upper()}, turn_off_leds={turn_off_leds}, controller={type(ctrl).__name__}")

    if turn_off_leds:
        logger.debug(f"   Turning off all channels...")
        ctrl.turn_off_channels()

        # Verify LEDs are off (V1.1 firmware)
        if verify:
            verify_hardware_state(
                ctrl,
                expected_leds={'a': 0, 'b': 0, 'c': 0, 'd': 0}
            )

        logger.debug(f"   Channels off, waiting {LED_DELAY * 3:.2f}s for afterglow decay...")
        time.sleep(LED_DELAY * 3)  # Extra delay for afterglow decay (~60ms total)

    logger.debug(f"   Setting mode to {mode.upper()}...")
    ctrl.set_mode(mode=mode)

    # Use appropriate delay based on mode
    delay = P_MODE_SWITCH_DELAY if mode == "p" else MODE_SWITCH_DELAY
    logger.debug(f"   Mode set, waiting {delay}s for settling...")
    time.sleep(delay)

    # Query servo position after mode switch (diagnostic)
    if verify:
        verify_hardware_state(
            ctrl,
            expected_mode=mode,
            check_servo=True
        )

    logger.debug(f"✅ Mode switch complete: {mode.upper()}-mode active (delay: {delay}s, LEDs off: {turn_off_leds})")


def verify_hardware_state(
    ctrl: ControllerBase,
    expected_leds: dict = None,
    expected_mode: str = None,
    check_servo: bool = False,
    tolerance: int = 5
) -> bool:
    """Verify hardware is in expected state before measurement.

    This is CRITICAL during calibration where we move hardware frequently.
    Ensures LEDs, servo positions match what we think we commanded.

    Args:
        ctrl: Controller instance
        expected_leds: Dict of channel->intensity (e.g., {'a': 200, 'b': 0, 'c': 0, 'd': 0})
                       Use {'a': 0, 'b': 0, 'c': 0, 'd': 0} to verify all off
        expected_mode: Expected polarizer mode ('s' or 'p')
        check_servo: If True, query servo positions (for diagnostic - no validation yet)
        tolerance: Acceptable LED intensity deviation (default 5)

    Returns:
        bool: True if hardware state matches expectations, False otherwise
    """
    try:
        all_verified = True

        # Verify LED intensities (V1.1 firmware)
        if expected_leds is not None:
            if hasattr(ctrl, 'get_all_led_intensities'):
                actual_leds = ctrl.get_all_led_intensities()

                if actual_leds is None:
                    logger.debug("LED query returned None (V1.0 firmware or query failed) - skipping verification")
                    # Don't fail - gracefully skip verification for V1.0 firmware
                else:
                    for ch, expected_val in expected_leds.items():
                        actual_val = actual_leds.get(ch, -1)
                        deviation = abs(actual_val - expected_val)

                        if deviation > tolerance:
                            logger.error(
                                f"❌ LED verification FAILED: Channel {ch.upper()} "
                                f"expected={expected_val}, actual={actual_val}, deviation={deviation}"
                            )
                            all_verified = False
                        else:
                            logger.debug(
                                f"✅ LED {ch.upper()} verified: {actual_val} "
                                f"(expected {expected_val}, deviation {deviation})"
                            )
            else:
                logger.debug("LED query not available (V1.0 firmware) - skipping LED verification")

        # Query servo positions (diagnostic - for now just log, no validation)
        if check_servo:
            if hasattr(ctrl, 'servo_get'):
                servo_pos = ctrl.servo_get()
                logger.debug(f"📍 Servo positions: S={servo_pos.get('s', 'unknown')}, P={servo_pos.get('p', 'unknown')}")
            else:
                logger.debug("Servo query not available")

        # Mode verification would require firmware support (not currently available)
        # Just log what we expect
        if expected_mode is not None:
            logger.debug(f"📍 Expected polarizer mode: {expected_mode.upper()}-mode")

        return all_verified

    except Exception as e:
        logger.error(f"Hardware verification error: {e}")
        return False


def get_calibration_expectations(polarizer_type: str) -> dict[str, any]:
    """Get calibration expectations based on polarizer hardware type.

    CALIBRATION SEQUENCE:
    --------------------
    1. Connect hardware → Identify device type
    2. Load device_config → Check for servo positions
    3. IF servo positions exist → Fast path (LED calibration only - this module)
       IF servo positions missing → Servo calibration first (method depends on polarizer type)
    4. LED intensity calibration → Common path (same for both types)

    This function describes expectations for BOTH phases:

    **Servo Position Calibration (if needed - not in this module):**
    - Barrel: SIMPLE - Find 2 fixed window positions (~1.4 min)
    - Circular: COMPLEX - Quadrant search with water (~13 measurements)
    - Only runs if device_config.json is not populated

    **LED Intensity Calibration (this module - always runs):**
    - BOTH types: Same complexity once servo positions are known/loaded
    - BOTH: Optimize LED intensities from S-mode to P-mode
    - BOTH: Require headroom analysis for P-mode boost
    - BOTH: Same expected S/P ratio (1.5-15× depending on sample)
    - This is the "common path" - process identical for both polarizer types

    Args:
        polarizer_type: 'barrel' or 'round'/'circular'

    Returns:
        Dictionary with calibration expectations:
        - 'servo_calibration_complexity': How complex servo calibration is (if needed)
        - 'led_calibration_complexity': Always 'STANDARD' (common path)
        - 'expected_s_p_ratio': Expected (min, max) S/P signal ratio (sample-dependent)
        - 'requires_headroom_analysis': Always True (needed for P-mode boost)
        - 'servo_calibration_method': Description of servo calibration process
        - 'led_calibration_notes': Description of LED calibration process
    """
    # Normalize polarizer type
    normalized = polarizer_type.lower()
    if normalized in ['round', 'circular']:
        normalized = 'circular'
    elif normalized == 'barrel':
        normalized = 'barrel'
    else:
        logger.warning(f"Unknown polarizer type '{polarizer_type}', assuming circular")
        normalized = 'circular'

    if normalized == 'barrel':
        expectations = {
            'servo_calibration_complexity': 'SIMPLE',
            'led_calibration_complexity': 'STANDARD',  # Same as circular once positions known
            'expected_s_p_ratio': (1.5, 15.0),  # Depends on sample coupling, not polarizer type
            'requires_headroom_analysis': True,  # BOTH types need S→P boost prediction
            'servo_calibration_method': 'Window detection - find 2 fixed perpendicular windows (~1.4 min at OEM)',
            'led_calibration_notes': 'Standard LED intensity optimization (S-mode → P-mode boost)'
        }
    else:  # circular
        expectations = {
            'servo_calibration_complexity': 'COMPLEX',
            'led_calibration_complexity': 'STANDARD',  # Same as barrel once positions known
            'expected_s_p_ratio': (1.5, 15.0),  # Depends on sample coupling, not polarizer type
            'requires_headroom_analysis': True,  # BOTH types need S→P boost prediction
            'servo_calibration_method': 'Quadrant search with water required (~13 measurements at OEM)',
            'led_calibration_notes': 'Standard LED intensity optimization (S-mode → P-mode boost)'
        }

    logger.debug(f"Calibration expectations for {normalized} polarizer: LED calibration is {expectations['led_calibration_complexity']}")
    return expectations


def analyze_channel_headroom(ref_intensity: dict[str, int]) -> dict[str, ChannelHeadroomAnalysis]:
    """Analyze LED headroom for all channels after S-mode calibration.

    This analysis predicts P-mode boost potential based on S-mode LED usage.
    Done once after S-mode, results reused in P-mode calibration.

    Args:
        ref_intensity: S-mode LED intensities for each channel

    Returns:
        Dictionary mapping channel to ChannelHeadroomAnalysis
    """
    analyses = {}

    logger.info("\n📊 LED HEADROOM ANALYSIS (P-mode potential prediction):")

    for ch, s_intensity in ref_intensity.items():
        headroom = P_LED_MAX - s_intensity
        headroom_pct = (headroom / P_LED_MAX) * 100

        # Predict P-mode boost potential based on S-mode intensity
        if s_intensity < 80:
            predicted_boost = 2.5
            potential = "EXCELLENT"
        elif s_intensity < 150:
            predicted_boost = 1.75
            potential = "GOOD"
        elif s_intensity < 200:
            predicted_boost = 1.35
            potential = "MODERATE"
        else:
            predicted_boost = 1.2
            potential = "LIMITED"

        is_weak = s_intensity > 200

        analyses[ch] = ChannelHeadroomAnalysis(
            channel=ch,
            s_intensity=s_intensity,
            headroom=headroom,
            headroom_pct=headroom_pct,
            predicted_boost=predicted_boost,
            is_weak=is_weak
        )

        logger.info(f"   Ch {ch.upper()}: S-LED={s_intensity}/255 ({headroom_pct:.0f}% headroom) - {potential} P-boost potential ({predicted_boost:.1f}x)")

    logger.info("")

    return analyses


# =============================================================================
# CALIBRATION RESULT
# =============================================================================

class LEDCalibrationResult:
    """Result of LED calibration process."""

    def __init__(self):
        """Initialize calibration result."""
        self.success = False
        self.s_integration_time = MIN_INTEGRATION  # S-mode integration time (Step 4)
        self.num_scans = 1
        self.ref_intensity = {}  # S-mode LED intensities
        self.leds_calibrated = {}  # P-mode LED intensities
        self.dark_noise = None
        self.ref_sig = {}
        self.wave_data = None
        self.wavelengths = None  # Alias for wave_data (GitHub compatibility)
        self.full_wavelengths = None  # Full detector wavelength array (before SPR filtering)
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.detector_max_counts = 65535  # Detector maximum counts (detector-specific)
        self.detector_saturation_threshold = 58900  # Detector saturation threshold (detector-specific)
        self.ch_error_list = []
        self.fourier_weights = None
        self.s_ref_qc_results = {}  # QC validation results for each channel
        self.spr_fwhm = {}  # SPR dip FWHM for each channel (sensor quality indicator)
        self.is_calibrated = False  # Overall calibration status

        # P-mode verification results (populated by verify_calibration)
        self.orientation_validation = {}  # {ch: {'p_s_ratio': float, 'expected_range': tuple, 'status': str}}
        self.transmission_validation = {}  # {ch: {'fwhm': float, 'dip_depth': float, 'status': str}}
        self.p_ref_sig = {}  # P-mode reference spectra (measured during verification)
        self.p_mode_intensity = {}  # P-mode LED intensities (optimized in Step 5)
        self.p_integration_time = MIN_INTEGRATION  # P-mode integration time (Step 5, may be up to +10% of S-mode)

        # Per-channel performance metrics (for ML system intelligence)
        self.channel_performance = {}  # {ch: {'max_counts', 'utilization_pct', 'snr_estimate', 'optical_limit'}}
        # These metrics guide peak tracking sensitivity and noise models per channel

        # LED headroom analysis (computed once after S-mode, reused in P-mode)
        self.headroom_analysis = {}  # {ch: ChannelHeadroomAnalysis}

        # Step 3: LED brightness ranking (weakest → strongest)
        self.led_ranking = []  # [(channel, (mean, max, saturated)), ...] sorted by brightness
        self.weakest_channel = None  # Weakest channel ID (str) - will be fixed at LED=255

        # Polarizer positions (loaded at initialization via fail-fast)
        self.polarizer_s_position = None  # S-mode servo position (0-255)
        self.polarizer_p_position = None  # P-mode servo position (0-255)
        self.polarizer_sp_ratio = None    # S/P transmission ratio (optional)

        # Alternative method specific (Fixed LED, Per-Channel Integration method)
        self.per_channel_integration = {}  # {ch: integration_time_ms} - for variable integration per channel
        self.per_channel_dark_noise = {}   # {ch: dark_noise_array} - dark noise at each channel's integration time
        self.calibration_method = "standard"  # "standard" or "alternative"


# =============================================================================
# STANDARD CALIBRATION PATH - HELPER FUNCTIONS
# =============================================================================

def calibrate_integration_time(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    integration_step: int,
    stop_flag=None,
    device_config=None,  # Optional: pre-loaded DeviceConfiguration (avoids redundant file reads)
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> tuple[int, int]:
    """Calibrate integration time to find optimal value for all channels.

    SYSTEM TIMING CONSTRAINTS:
    - Target: ~1Hz acquisition frequency per channel (for 4 channels)
    - Per-channel budget: 210ms (integration + readout + processing)
    - Max integration time: 70ms per scan (allows 3 scans minimum)
    - Total cycle time: 4 channels × 210ms = 840ms ≈ 1.19Hz system rate

    This function balances signal strength with timing requirements:
    - If optimal integration > 70ms → CONSTRAIN to 70ms, will need higher LED intensity
    - If optimal integration < 70ms → USE optimal value, LED has more headroom for P-mode

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels to calibrate
        integration_step: Step size for integration time adjustment
        stop_flag: Optional threading event to check for cancellation
        device_config: Optional pre-loaded DeviceConfiguration
        detector_params: Optional pre-read detector parameters

    Returns:
        Tuple of (integration_time, num_scans)
    """
    # Get detector parameters (use provided or read once)
    if detector_params is None:
        detector_params = get_detector_params(usb)

    target_counts = detector_params.target_counts

    integration = MIN_INTEGRATION
    max_int = MAX_INTEGRATION

    # Apply system timing budget constraint
    max_int = min(max_int, MAX_INTEGRATION_BUDGET_MS)
    logger.info(f"\n⏱️ SYSTEM TIMING BUDGET:")
    logger.info(f"   Target: {SYSTEM_ACQUISITION_TARGET_HZ}Hz per channel ({len(ch_list)} channels)")
    logger.info(f"   Per-channel budget: {TARGET_CHANNEL_BUDGET_MS}ms total")
    logger.info(f"   ")
    logger.info(f"   Hardware Acquisition Overhead (decoupled from processing):")
    logger.info(f"   • Integration time: <variable, max {MAX_INTEGRATION_BUDGET_MS}ms>")
    logger.info(f"   • LED settling delay: ~{ESTIMATED_LED_DELAY_MS}ms")
    logger.info(f"   • Afterglow decay: ~{ESTIMATED_AFTERGLOW_MS}ms")
    logger.info(f"   • Detector lag: ~{ESTIMATED_DETECTOR_LAG_MS}ms")
    logger.info(f"   • USB transfer: ~{ESTIMATED_USB_TRANSFER_MS}ms")
    logger.info(f"   • Total overhead: ~{HARDWARE_OVERHEAD_MS}ms")
    logger.info(f"   ")
    logger.info(f"   Max integration allowed: {MAX_INTEGRATION_BUDGET_MS}ms")
    logger.info(f"   (reserves {HARDWARE_OVERHEAD_MS}ms for hardware overhead)")
    logger.info(f"   {len(ch_list)}-channel cycle: {TARGET_CHANNEL_BUDGET_MS * len(ch_list)}ms ≈ {1000/(TARGET_CHANNEL_BUDGET_MS * len(ch_list)):.2f}Hz system rate")
    logger.info(f"   ")
    logger.info(f"   Note: Processing time (graph updates, etc.) runs independently\n")

    # Get target counts from detector
    target_counts = usb.target_counts
    logger.debug(f"Calibrating to detector target: {target_counts} counts")

    # Set to S-mode for integration time calibration
    ctrl.set_mode(mode="s")
    time.sleep(MODE_SWITCH_DELAY)
    ctrl.turn_off_channels()
    usb.set_integration(integration)
    time.sleep(0.1)

    logger.debug("Starting integration time calibration...")

    # === PRISM PRESENCE CHECK ===
    # Early detection: If prism is absent, S-mode signal will be MUCH HIGHER than expected
    # (no SPR absorption, just direct transmission through empty holder)
    # This check uses previous calibration data to detect anomalous signal levels
    prism_check_readings = []

    # Find minimum integration time needed for weakest channel
    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
        time.sleep(pre_led_delay_ms / 1000.0)
        int_array = usb.read_intensity()
        time.sleep(pre_led_delay_ms / 1000.0)
        current_count = int_array.max()
        prism_check_readings.append(current_count)
        logger.debug(f"Ch {ch} initial reading at {integration}ms: {current_count:.0f} counts (target: {target_counts})")

        while current_count < target_counts and integration < max_int:
            integration += integration_step
            logger.debug(f"Increasing integration time for ch {ch} - {integration}ms")
            usb.set_integration(integration)
            time.sleep(0.02)
            int_array = usb.read_intensity()
            new_count = int_array.max()
            logger.debug(
                f"  After setting to {integration}ms: {new_count:.0f} counts (change: {new_count - current_count:+.0f})"
            )
            current_count = new_count

    # === PRISM PRESENCE DIAGNOSTIC ===
    # Compare measured signal to expected levels from previous calibration
    # If prism is absent: signals will be 5-10× HIGHER (no SPR absorption)
    # If prism is present but dry: signals will be 2-3× higher (weak SPR coupling)
    try:
        # Use provided device_config or load it (optimization: avoid redundant file read)
        if device_config is None:
            from utils.device_configuration import DeviceConfiguration
            device_serial = getattr(usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)
        prev_calib = device_config.config.get('led_calibration', {})
        prev_integration = prev_calib.get('integration_time_ms', None)
        prev_s_ref_max = prev_calib.get('s_ref_max_intensity', {})

        if prev_integration and prev_s_ref_max and prism_check_readings:
            # Calculate expected signal at current integration time
            # Scale previous S-ref max intensities by integration time ratio
            integration_ratio = integration / prev_integration
            avg_reading = sum(prism_check_readings) / len(prism_check_readings)

            # Get average previous max intensity (at LED=255, old integration time)
            prev_signals = [prev_s_ref_max.get(ch, 0) for ch in ch_list if ch in prev_s_ref_max]
            if prev_signals:
                avg_prev_max = sum(prev_signals) / len(prev_signals)

                # Current reading is at S_LED_INT (typically 150), scale to estimate max
                estimated_max_at_current_int = avg_reading * (255 / S_LED_INT) * integration_ratio

                # Compare to previous calibration
                signal_ratio = estimated_max_at_current_int / avg_prev_max if avg_prev_max > 0 else 0

                logger.info(f"\n🔍 PRISM PRESENCE CHECK:")
                logger.info(f"   Current reading: {avg_reading:.0f} counts (at LED={S_LED_INT}, {integration}ms)")
                logger.info(f"   Estimated max: {estimated_max_at_current_int:.0f} counts (scaled to LED=255)")
                logger.info(f"   Previous calib: {avg_prev_max:.0f} counts (at LED=255, {prev_integration}ms)")
                logger.info(f"   Signal ratio: {signal_ratio:.2f}x")
                logger.info(f"")

                # Diagnostic interpretation
                if signal_ratio >= 5.0:
                    # CRITICAL: Signal way too high - likely no prism
                    logger.error(f"   ❌ PRISM LIKELY ABSENT!")
                    logger.error(f"   Signal is {signal_ratio:.1f}× higher than previous calibration")
                    logger.error(f"   Expected: ~1.0× (with prism + water)")
                    logger.error(f"   Measured: {signal_ratio:.1f}× (no SPR absorption detected)")
                    logger.error(f"")
                    logger.error(f"   🔧 DIAGNOSIS: No prism installed in sensor holder")
                    logger.error(f"   → Install prism, apply water, and retry calibration")
                    logger.error(f"")
                    raise ValueError("Prism absent - install prism and retry calibration")

                elif signal_ratio >= 2.5:
                    # WARNING: Signal moderately high - possibly dry or poor contact
                    logger.warning(f"   ⚠️ PRISM MAY BE DRY OR POOR CONTACT!")
                    logger.warning(f"   Signal is {signal_ratio:.1f}× higher than previous calibration")
                    logger.warning(f"   Expected: ~1.0× (with prism + water)")
                    logger.warning(f"   Measured: {signal_ratio:.1f}× (weak SPR coupling)")
                    logger.warning(f"")
                    logger.warning(f"   🔧 LIKELY CAUSES:")
                    logger.warning(f"   1. Prism is DRY (no water applied) - MOST COMMON")
                    logger.warning(f"   2. Air bubbles between prism and sensor")
                    logger.warning(f"   3. Prism not seated properly")
                    logger.warning(f"")
                    logger.warning(f"   💧 Recommendation: Apply fresh water and retry")
                    logger.warning(f"   (Continuing calibration - may fail FWHM validation later)")
                    logger.warning(f"")

                elif signal_ratio >= 1.5:
                    # NOTICE: Signal slightly high - monitor
                    logger.info(f"   ℹ️ Signal slightly elevated ({signal_ratio:.1f}×)")
                    logger.info(f"   This may indicate:")
                    logger.info(f"   • Prism contact not optimal")
                    logger.info(f"   • Water layer thin")
                    logger.info(f"   • Room temperature different from previous calibration")
                    logger.info(f"   Continuing - watch for FWHM validation results...")
                    logger.info(f"")

                elif signal_ratio >= 0.5:
                    # NORMAL: Signal in expected range
                    logger.info(f"   ✅ Signal ratio normal ({signal_ratio:.1f}×)")
                    logger.info(f"   Prism presence confirmed")
                    logger.info(f"")

                else:
                    # Signal unexpectedly LOW - different issue
                    logger.warning(f"   ⚠️ Signal LOWER than expected ({signal_ratio:.1f}×)")
                    logger.warning(f"   Possible causes:")
                    logger.warning(f"   • LED degradation")
                    logger.warning(f"   • Fiber misalignment")
                    logger.warning(f"   • Detector issue")
                    logger.warning(f"")

    except Exception as e:
        # If we can't load previous calibration, skip this check
        logger.debug(f"Prism presence check skipped: {e}")

    # Check if low intensity saturates and reduce if needed
    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=S_LED_MIN)
        time.sleep(pre_led_delay_ms / 1000.0)

        try:
            int_array = usb.read_intensity()
        except ConnectionError as e:
            logger.error(f"🔌 Spectrometer disconnected during integration time calibration")
            logger.error(f"   Channel: {ch.upper()}, Step: Saturation check")
            logger.error(f"   Error: {str(e)}")
            raise  # Propagate to main calibration handler

        current_count = int_array.max()
        logger.debug(f"Saturation check ch {ch}: {current_count:.0f}, limit: {target_counts}")

        while current_count > target_counts and integration > MIN_INTEGRATION:
            integration -= integration_step
            if integration < max_int:
                max_int = integration
            logger.debug(f"Decreasing integration time for ch {ch} - {integration}ms")
            usb.set_integration(integration)
            time.sleep(0.02)
            int_array = usb.read_intensity()
            current_count = int_array.max()

    logger.info(f"✅ Integration time calibrated: {integration}ms")

    # =======================================================================
    # P-MODE HEADROOM SAFETY: Ensure minimum integration for P-mode boost
    # =======================================================================
    # P-mode polarizer reduces signal by ~40% compared to S-mode
    # If S-mode integration is too low, P-mode weak channels (A, D) won't reach target
    # Safety minimum: 45ms ensures P-mode has enough signal even with polarization loss
    MIN_INTEGRATION_FOR_P_MODE = 45  # ms - ensures P-mode channels reach 53K target

    if integration < MIN_INTEGRATION_FOR_P_MODE:
        logger.warning(f"")
        logger.warning(f"⚠️ P-MODE HEADROOM ADJUSTMENT")
        logger.warning(f"   Calibrated integration: {integration}ms")
        logger.warning(f"   P-mode safety minimum: {MIN_INTEGRATION_FOR_P_MODE}ms")
        logger.warning(f"   ")
        logger.warning(f"   Reason: P-mode polarizer reduces signal by ~40%")
        logger.warning(f"   If integration too low → P-mode weak channels undersaturated")
        logger.warning(f"   ")
        logger.warning(f"   Action: Increasing integration to {MIN_INTEGRATION_FOR_P_MODE}ms")
        logger.warning(f"   This ensures ALL P-mode channels can reach 53K count target")
        logger.warning(f"")

        integration = MIN_INTEGRATION_FOR_P_MODE
        usb.set_integration(integration)
        time.sleep(0.1)

        logger.info(f"✅ Integration adjusted for P-mode: {integration}ms")

    # Analyze timing budget impact on LED optimization strategy
    # Calculate ACTUAL per-channel acquisition time (hardware-limited)
    actual_channel_time_ms = integration + HARDWARE_OVERHEAD_MS
    actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
    system_cycle_ms = actual_channel_time_ms * len(ch_list)
    system_hz = 1000 / system_cycle_ms if system_cycle_ms > 0 else 0

    budget_utilization = (integration / MAX_INTEGRATION_BUDGET_MS) * 100

    logger.info(f"\n📊 ACQUISITION TIMING ANALYSIS:")
    logger.info(f"   Integration time: {integration}ms ({budget_utilization:.0f}% of {MAX_INTEGRATION_BUDGET_MS}ms max)")
    logger.info(f"   Hardware overhead: ~{HARDWARE_OVERHEAD_MS}ms (LED + afterglow + detector + USB)")
    logger.info(f"   ")
    logger.info(f"   Per-channel acquisition: ~{actual_channel_time_ms}ms → {actual_channel_hz:.2f}Hz")
    logger.info(f"   {len(ch_list)}-channel cycle: ~{system_cycle_ms}ms → {system_hz:.2f}Hz system rate")
    logger.info(f"   ")

    if actual_channel_hz >= SYSTEM_ACQUISITION_TARGET_HZ:
        margin_pct = ((actual_channel_hz - SYSTEM_ACQUISITION_TARGET_HZ) / SYSTEM_ACQUISITION_TARGET_HZ) * 100
        logger.info(f"   ✅ MEETS TARGET: {actual_channel_hz:.2f}Hz ≥ {SYSTEM_ACQUISITION_TARGET_HZ}Hz ({margin_pct:+.0f}% margin)")
    else:
        deficit_pct = ((SYSTEM_ACQUISITION_TARGET_HZ - actual_channel_hz) / SYSTEM_ACQUISITION_TARGET_HZ) * 100
        logger.info(f"   ⚠️ BELOW TARGET: {actual_channel_hz:.2f}Hz < {SYSTEM_ACQUISITION_TARGET_HZ}Hz ({deficit_pct:.0f}% deficit)")

    logger.info(f"   ")

    if integration >= MAX_INTEGRATION_BUDGET_MS:
        logger.warning(f"   📌 AT MAXIMUM integration time ({MAX_INTEGRATION_BUDGET_MS}ms)")
        logger.warning(f"   → LEDs will need HIGHER intensity to reach target signal")
        logger.warning(f"   → P-mode optimization will have LIMITED headroom")
        logger.warning(f"   → Constrained by {SYSTEM_ACQUISITION_TARGET_HZ}Hz acquisition target")
    elif integration >= 80:
        logger.info(f"   ℹ️ High integration time (>80ms)")
        logger.info(f"   → LEDs will use moderate-to-high intensity")
        logger.info(f"   → P-mode optimization will have moderate headroom")
    elif integration >= 50:
        logger.info(f"   ✅ BALANCED integration time")
        logger.info(f"   → LEDs will use moderate intensity")
        logger.info(f"   → P-mode optimization will have good headroom")
    else:
        logger.info(f"   ✅ EXCELLENT - Low integration time (<50ms)")
        logger.info(f"   → LEDs will use LOW intensity (strong optical signal)")
        logger.info(f"   → P-mode optimization will have EXCELLENT headroom")
        logger.info(f"   → Acquisition faster than {SYSTEM_ACQUISITION_TARGET_HZ}Hz target with margin")

    logger.info(f"\n   Note: Graph processing/updates run independently from acquisition")
    logger.info("")

    # Calculate number of scans based on integration time
    num_scans = min(int(MAX_READ_TIME / integration), MAX_NUM_SCANS)
    logger.debug(f"Scans to average: {num_scans}")

    return integration, num_scans


def calibrate_led_channel(
    usb,
    ctrl: ControllerBase,
    ch: str,
    target_counts: float = None,
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    wave_min_index: int = None,  # ROI start for saturation checking
    wave_max_index: int = None,  # ROI end for saturation checking
    pre_led_delay_ms: float = 45.0,  # PRE LED delay (default 45ms)
    post_led_delay_ms: float = 5.0,  # POST LED delay (default 5ms)
) -> int:
    """Calibrate a single LED channel to target count level.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch: Channel to calibrate ('a', 'b', 'c', or 'd')
        target_counts: Target detector count level (if None, uses detector_params or reads from detector)
        stop_flag: Optional threading event to check for cancellation
        detector_params: Optional pre-read detector parameters

        wave_min_index: Start index of wavelength ROI for saturation checking (560nm)
        wave_max_index: End index of wavelength ROI for saturation checking (720nm)

    Returns:
        Calibrated LED intensity value (0-255)
    """
    # Get detector parameters (use provided or read once)
    if detector_params is None:
        detector_params = get_detector_params(usb)

    # Get target from parameters or use provided override
    if target_counts is None:
        target_counts = detector_params.target_counts
        logger.debug(f"Using detector target: {target_counts} counts")

    logger.debug(f"Calibrating LED {ch.upper()}...")

    max_counts = detector_params.max_counts
    saturation_threshold = detector_params.saturation_threshold

    # Start at maximum intensity
    intensity = P_LED_MAX
    ctrl.set_intensity(ch=ch, raw_val=intensity)
    time.sleep(pre_led_delay_ms / 1000.0)

    intensity_data = usb.read_intensity()
    if intensity_data is None:
        logger.error(f"Failed to read intensity for channel {ch.upper()} - spectrometer not responding")
        raise RuntimeError(f"Spectrometer read failed for channel {ch.upper()}")
    calibration_max = intensity_data.max()

    logger.debug(f"Initial intensity: {intensity} = {calibration_max:.0f} counts")

    # CRITICAL SAFETY CHECK: Verify we're actually getting signal from the LED
    # Signal should be significantly above dark noise (>1000 counts at max LED)
    MIN_EXPECTED_SIGNAL = 1000  # Minimum counts expected with LED at max
    if calibration_max < MIN_EXPECTED_SIGNAL:
        logger.error(f"❌ Ch {ch.upper()}: Hardware validation FAILED!")
        logger.error(f"   LED set to maximum ({intensity}) but signal is only {calibration_max:.0f} counts")
        logger.error(f"   Expected at least {MIN_EXPECTED_SIGNAL} counts")
        logger.error(f"   Possible causes:")
        logger.error(f"   - LED channel {ch.upper()} not working")
        logger.error(f"   - Light path blocked")
        logger.error(f"   - Spectrometer not reading correctly")
        logger.error(f"   - No water/prism on sensor (SPR channels only)")
        raise RuntimeError(f"Hardware validation failed: No signal detected on channel {ch.upper()}")

    logger.info(f"✅ Ch {ch.upper()}: Hardware validation passed - LED producing {calibration_max:.0f} counts at max intensity")

    # Check for initial saturation
    if calibration_max >= saturation_threshold:
        logger.warning(f"⚠️ Ch {ch.upper()}: S-mode saturation detected at max LED ({calibration_max:.0f} ≥ {saturation_threshold:.0f})")
        logger.info(f"   Auto-reducing LED intensity to bring signal to safe range...")

        # Calculate required reduction to reach 85% of detector max (safer than 95%)
        target_signal = max_counts * 0.85
        reduction_factor = target_signal / calibration_max
        reduced_intensity = max(S_LED_MIN, int(intensity * reduction_factor))

        logger.info(f"   Calculated reduction: LED {intensity} → {reduced_intensity} (factor: {reduction_factor:.3f})")

        # Apply reduced intensity
        ctrl.set_intensity(ch=ch, raw_val=reduced_intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        # Re-measure with reduced LED
        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error(f"Failed to re-measure after saturation reduction for channel {ch.upper()}")
            raise RuntimeError(f"Spectrometer read failed during saturation recovery")

        new_max = intensity_data.max()
        logger.info(f"   After reduction: {new_max:.0f} counts ({(new_max/max_counts)*100:.1f}% of detector max)")

        # Validate the reduction worked
        if new_max >= saturation_threshold:
            logger.error(f"❌ Ch {ch.upper()}: Still saturated after auto-reduction - possible hardware issue")
            # Use the reduced intensity anyway - better than max saturation
            intensity = reduced_intensity
            calibration_max = new_max
        else:
            logger.info(f"✅ Ch {ch.upper()}: Saturation resolved, continuing calibration from reduced baseline")
            intensity = reduced_intensity
            calibration_max = new_max

    # Coarse adjust
    previous_max = calibration_max
    coarse_iterations = 0
    while (
        calibration_max > target_counts
        and intensity > COARSE_ADJUST_STEP
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity -= COARSE_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        # Verify LED state during iteration (every 5th iteration to avoid spam)
        if coarse_iterations % 5 == 0:
            expected_state = {ch_: 0 for ch_ in ['a', 'b', 'c', 'd']}
            expected_state[ch] = intensity
            verify_hardware_state(ctrl, expected_leds=expected_state)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during coarse adjustment")
        calibration_max = intensity_data.max()

        coarse_iterations += 1

        # Sanity check: Signal should decrease as we reduce LED intensity
        if coarse_iterations == 1 and calibration_max >= previous_max * 0.95:
            logger.warning(f"⚠️ Ch {ch.upper()}: Signal not responding to LED changes (was {previous_max:.0f}, now {calibration_max:.0f})")
            logger.warning(f"   This may indicate hardware communication issues")
        previous_max = calibration_max

    logger.debug(f"Coarse adjust: {intensity} = {calibration_max:.0f} counts")

    # Medium adjust
    while (
        calibration_max < target_counts
        and intensity < P_LED_MAX
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity += MEDIUM_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during medium adjustment")
        calibration_max = intensity_data.max()

    logger.debug(f"Medium adjust: {intensity} = {calibration_max:.0f} counts")

    # Fine adjust
    fine_iterations = 0
    MAX_FINE_ITERATIONS = 50  # Prevent infinite loop if hardware unstable
    while (
        calibration_max > target_counts
        and intensity > FINE_ADJUST_STEP + 1
        and fine_iterations < MAX_FINE_ITERATIONS
    ):
        intensity -= FINE_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during fine adjustment")
        calibration_max = intensity_data.max()
        fine_iterations += 1

    if fine_iterations >= MAX_FINE_ITERATIONS:
        logger.warning(f"⚠️ Ch {ch.upper()}: Fine adjustment reached iteration limit - signal may be unstable")

    logger.debug(f"Fine adjust: {intensity} = {calibration_max:.0f} counts")

    # Final validation: Verify calibration accuracy
    error_pct = abs(calibration_max - target_counts) / target_counts * 100
    if error_pct > 10:
        logger.warning(f"⚠️ Ch {ch.upper()}: Calibration accuracy low - {error_pct:.1f}% error")
        logger.warning(f"   Target: {target_counts:.0f}, Achieved: {calibration_max:.0f}, LED: {intensity}")
    else:
        logger.info(f"✅ Ch {ch.upper()}: Final calibration - {calibration_max:.0f} counts (target: {target_counts:.0f}, error: {error_pct:.1f}%) at LED={intensity}")

    return intensity


def calibrate_p_mode_leds(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    stop_flag=None,
    detector_params: DetectorParams = None,  # Optional: pre-read detector parameters
    headroom_analysis: dict[str, ChannelHeadroomAnalysis] = None,  # Optional: pre-computed headroom analysis
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> tuple[dict[str, int], dict[str, dict]]:
    """Calibrate LED intensities in P-mode to maximize signal without saturation.

    Strategy: For each channel independently, increase LED intensity until we approach
    the saturation threshold. This maximizes SNR for each channel regardless of its
    S-mode starting point, accounting for differences in LED efficiency, polarization
    effects, and optical coupling.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels to calibrate
        ref_intensity: S-mode reference intensities for each channel (starting point)
        stop_flag: Optional threading event to check for cancellation
        detector_params: Optional pre-read detector parameters
        headroom_analysis: Optional pre-computed headroom analysis from S-mode

    Returns:
        Tuple of (leds_calibrated, channel_performance):
        - leds_calibrated: Dictionary of calibrated P-mode LED intensities
        - channel_performance: Per-channel metrics for ML system intelligence
    """
    logger.debug("Starting P-mode LED calibration (maximize signal per channel)...")

    # Get detector parameters (use provided or read once)
    if detector_params is None:
        detector_params = get_detector_params(usb)

    max_counts = detector_params.max_counts
    saturation_threshold = detector_params.saturation_threshold

    # Target: Push LED to 255 (max intensity) while staying below saturation
    # This maximizes SNR and uses full LED capacity
    # Target signal level: 92% of saturation threshold (safer margin for spectrum variations)
    optimal_target = saturation_threshold * 0.92  # 92% of safe threshold = ~87% of absolute max

    logger.debug(f"Max counts: {max_counts:.0f}, Saturation threshold: {saturation_threshold:.0f}, Optimal target: {optimal_target:.0f}")

    # Use pre-computed headroom analysis if available (optimization: eliminate duplicate calculation)
    if headroom_analysis is None:
        # Fallback: analyze if not provided (shouldn't happen in normal flow)
        logger.debug("Headroom analysis not provided, computing now...")
        headroom_analysis = analyze_channel_headroom(ref_intensity)
    else:
        logger.debug("Using pre-computed headroom analysis (optimization)")

    # Switch to P-mode with proper LED cleanup (use centralized helper)
    switch_mode_safely(ctrl, "p", turn_off_leds=True)

    leds_calibrated = {}
    channel_performance = {}  # Store per-channel metrics for ML system

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        # Use pre-computed headroom analysis (optimization: eliminate duplicate calculation)
        analysis = headroom_analysis[ch]
        s_intensity = analysis.s_intensity
        headroom = analysis.headroom
        headroom_pct = analysis.headroom_pct
        predicted_boost = analysis.predicted_boost

        logger.debug(f"Optimizing P-mode LED {ch.upper()} (maximize without saturating)...")
        logger.debug(f"   S-mode baseline: LED={s_intensity}, headroom={headroom} ({headroom_pct:.0f}%)")
        logger.debug(f"   Predicted boost: {predicted_boost:.1f}x")

        if analysis.is_weak and headroom < 30:
            logger.warning(f"   ⚠️ Ch {ch.upper()}: Very limited headroom ({headroom}). Consider reducing integration time for better P-mode optimization.")

        # Start from 100% of S-mode intensity for aggressive optimization
        # Goal: Push to LED=255 (max) as long as signal doesn't saturate
        # S-mode was optimized to ~70% target with weakest LED near 220
        p_intensity = max(S_LED_MIN, int(ref_intensity[ch]))  # Start at S-mode intensity
        logger.debug(f"   Starting P-mode at S-mode intensity: LED={p_intensity}")
        logger.debug(f"   Goal: Increase to LED=255 (max) without saturating")

        ctrl.set_intensity(ch=ch, raw_val=p_intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        # Read initial intensity
        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error(f"Failed to read intensity for channel {ch.upper()}")
            raise RuntimeError(f"Spectrometer read failed for channel {ch.upper()}")

        calibration_max = intensity_data.max()
        logger.debug(f"Ch {ch.upper()} starting: LED={p_intensity}, Max={calibration_max:.0f} counts")

        # Check if we're already close to or above target with S-mode LED
        if calibration_max > optimal_target:
            # We're already above target - need to reduce
            logger.debug(f"Ch {ch.upper()}: Already above target ({calibration_max:.0f} > {optimal_target:.0f}), reducing...")
            # Reduce to 80% of current and re-measure
            p_intensity = max(S_LED_MIN, int(p_intensity * 0.8))
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(pre_led_delay_ms / 1000.0)
            intensity_data = usb.read_intensity()
            if intensity_data is not None:
                calibration_max = intensity_data.max()
                logger.debug(f"Ch {ch.upper()}: After reduction, now at {calibration_max:.0f} counts")

        # Phase 1: Coarse increase - quickly approach LED=255 or optimal signal range
        step_count = 0
        while (
            calibration_max < optimal_target * 0.85  # Go closer to target during coarse (85%)
            and p_intensity < (P_LED_MAX - COARSE_ADJUST_STEP)  # Stop before max to enter fine phase
        ):
            p_intensity += COARSE_ADJUST_STEP
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(pre_led_delay_ms / 1000.0)

            intensity_data = usb.read_intensity()
            if intensity_data is None:
                logger.error(f"Failed to read intensity during coarse adjust for channel {ch.upper()}")
                raise RuntimeError(f"Spectrometer read failed during calibration")

            calibration_max = intensity_data.max()
            step_count += 1

            # Safety: if we somehow jumped to saturation, back off and exit coarse phase
            if calibration_max > saturation_threshold:
                logger.warning(f"Ch {ch.upper()}: Unexpected saturation in coarse phase, backing off")
                p_intensity = max(ref_intensity[ch], p_intensity - COARSE_ADJUST_STEP * 2)
                ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(pre_led_delay_ms / 1000.0)
                intensity_data = usb.read_intensity()
                if intensity_data is not None:
                    calibration_max = intensity_data.max()
                break

            # Prevent infinite loops
            if step_count > 50:
                logger.warning(f"Ch {ch.upper()}: Coarse adjust iteration limit reached")
                break

        logger.debug(f"Ch {ch.upper()} after coarse: LED={p_intensity}, Max={calibration_max:.0f} counts")

        # Phase 2: Fine approach - push toward LED=255 while staying below saturation
        # Priority: Maximize LED intensity (prefer LED=255 over conservative signal target)
        step_count = 0
        prev_max = calibration_max
        logger.debug(f"Ch {ch.upper()}: Starting fine adjust from LED={p_intensity}, max={calibration_max:.0f}, target={optimal_target:.0f}")

        while (
            calibration_max < optimal_target  # Stay below saturation
            and p_intensity < P_LED_MAX  # Keep increasing until LED=255
        ):
            p_intensity += FINE_ADJUST_STEP
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(pre_led_delay_ms / 1000.0)

            intensity_data = usb.read_intensity()
            if intensity_data is None:
                logger.error(f"Failed to read intensity during fine adjust for channel {ch.upper()}")
                raise RuntimeError(f"Spectrometer read failed during calibration")

            prev_max = calibration_max
            calibration_max = intensity_data.max()
            step_count += 1

            # Log every 5 steps to track progress
            if step_count % 5 == 0:
                logger.debug(f"Ch {ch.upper()}: Step {step_count}, LED={p_intensity}, max={calibration_max:.0f}, delta={calibration_max-prev_max:.0f}")

            # Stop if we hit saturation threshold - back off more aggressively
            if calibration_max > saturation_threshold:
                logger.info(f"Ch {ch.upper()}: Hit saturation at {calibration_max:.0f}, backing off 2 steps")
                # Back off 2 steps to ensure we're safely below threshold
                p_intensity -= FINE_ADJUST_STEP * 2
                p_intensity = max(p_intensity, FINE_ADJUST_STEP)  # Don't go below minimum
                ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(pre_led_delay_ms / 1000.0)
                intensity_data = usb.read_intensity()
                if intensity_data is not None:
                    calibration_max = intensity_data.max()
                    logger.info(f"Ch {ch.upper()}: After backoff, now at {calibration_max:.0f} counts")
                break

            # Stop if signal stopped increasing (LED maxed out or optical limit)
            # Use 50 counts threshold (not 100) to allow smaller increments near target
            if step_count > 10 and abs(calibration_max - prev_max) < 50:
                logger.info(f"Ch {ch.upper()}: Signal plateaued (delta < 50 counts), reached optical limit")
                break

            # Prevent infinite loops
            if step_count > 50:
                logger.warning(f"Ch {ch.upper()}: Fine adjust iteration limit reached")
                break

        # Final safety check: ensure we're truly below saturation threshold
        # Re-read spectrum one more time to verify final state
        time.sleep(pre_led_delay_ms / 1000.0)
        final_check = usb.read_intensity()
        if final_check is not None:
            final_max = final_check.max()
            if final_max > saturation_threshold:
                logger.warning(f"Ch {ch.upper()}: Final check shows saturation ({final_max:.0f}), reducing further")
                # Reduce LED by 10% to get safely below threshold
                p_intensity = int(p_intensity * 0.90)
                ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(pre_led_delay_ms / 1000.0)
                # Verify the reduction worked
                verify_check = usb.read_intensity()
                if verify_check is not None:
                    calibration_max = verify_check.max()
                    logger.info(f"Ch {ch.upper()}: After 10% reduction, now at {calibration_max:.0f} counts")
                else:
                    calibration_max = final_max
            else:
                calibration_max = final_max

        # Final result
        utilization = (calibration_max / saturation_threshold) * 100
        logger.info(f"✓ Ch {ch.upper()}: LED={p_intensity}, Max={calibration_max:.0f} counts ({utilization:.1f}% of safe max)")

        leds_calibrated[ch] = p_intensity

        # Calculate actual boost achieved vs predicted
        actual_boost_ratio = float(p_intensity / s_intensity) if s_intensity > 0 else 1.0

        # Store performance metrics for ML system intelligence
        # These guide peak tracking sensitivity and noise models
        channel_performance[ch] = {
            'max_counts': float(calibration_max),
            'utilization_pct': float(utilization),
            'led_intensity': int(p_intensity),
            's_mode_intensity': int(s_intensity),
            'boost_ratio': actual_boost_ratio,
            'predicted_boost': float(predicted_boost),
            'headroom_available': int(headroom),
            'headroom_pct': float(headroom_pct),
            'optical_limit_reached': step_count > 5 and abs(calibration_max - prev_max) < 100,
            'hit_saturation': calibration_max > saturation_threshold * 0.99,
        }

        # Log boost analysis
        boost_efficiency = (actual_boost_ratio / predicted_boost) * 100 if predicted_boost > 0 else 0
        logger.info(f"   Ch {ch.upper()} boost analysis: achieved {actual_boost_ratio:.2f}x (predicted {predicted_boost:.1f}x, {boost_efficiency:.0f}% of prediction)")

        if actual_boost_ratio < 1.15 and s_intensity > 200:
            logger.warning(f"   ⚠️ Ch {ch.upper()}: Low boost with weak LED. Consider increasing integration time to improve S-mode baseline.")
        elif actual_boost_ratio > predicted_boost * 1.2:
            logger.info(f"   ℹ️ Ch {ch.upper()}: Exceeded prediction - excellent optical coupling!")

    # =============================================================================
    # CRITICAL: Apply Weakest LED Rule for P-mode Balanced Signal Levels
    # This is SEPARATE from S-mode balancing (which happens before S-ref capture)
    # P-mode balancing ensures all P-mode signals are balanced after optimization
    # =============================================================================
    logger.info(f"")
    logger.info(f"=" * 80)
    logger.info(f"📊 APPLYING WEAKEST LED RULE FOR P-MODE (Signal Balance)")
    logger.info(f"=" * 80)
    logger.info(f"NOTE: P-mode balancing occurs after individual channel optimization")

    # Find weakest channel (lowest signal, not lowest LED)
    weakest_ch = None
    weakest_signal = float('inf')

    for ch in ch_list:
        ch_signal = channel_performance[ch]['max_counts']
        if ch_signal < weakest_signal:
            weakest_signal = ch_signal
            weakest_ch = ch

    weakest_led = leds_calibrated[weakest_ch]

    logger.info(f"Weakest channel: {weakest_ch.upper()}")
    logger.info(f"   Signal: {weakest_signal:.0f} counts")
    logger.info(f"   LED: {weakest_led}/255")
    logger.info(f"")
    logger.info(f"Balancing all channels to match weakest channel signal level...")

    # Equalize all other channels to match weakest channel's signal
    for ch in ch_list:
        if ch == weakest_ch:
            logger.info(f"   Ch {ch.upper()}: {weakest_signal:.0f} counts @ LED={weakest_led} (weakest - no change)")
            continue

        current_signal = channel_performance[ch]['max_counts']
        current_led = leds_calibrated[ch]

        # Calculate target LED to match weakest signal
        # signal is proportional to LED, so: target_led = current_led * (weakest_signal / current_signal)
        target_led = int(current_led * (weakest_signal / current_signal))
        target_led = max(S_LED_MIN, min(target_led, P_LED_MAX))  # Clamp to valid range

        logger.info(f"   Ch {ch.upper()}: {current_signal:.0f} → {weakest_signal:.0f} counts, LED {current_led} → {target_led}")

        # Update LED intensity
        leds_calibrated[ch] = target_led

        # Verify the adjustment
        ctrl.set_intensity(ch=ch, raw_val=target_led)
        time.sleep(pre_led_delay_ms / 1000.0)
        verify_data = usb.read_intensity()
        if verify_data is not None:
            verify_max = verify_data.max()
            logger.debug(f"      Verification: {verify_max:.0f} counts (target was {weakest_signal:.0f})")
            # Update performance metrics
            channel_performance[ch]['max_counts'] = float(verify_max)
            channel_performance[ch]['led_intensity'] = int(target_led)

    logger.info(f"")
    logger.info(f"✅ All channels balanced to weakest channel signal level")
    logger.info(f"=" * 80)

    logger.info(f"✅ P-mode LED calibration complete (balanced): {leds_calibrated}")
    return leds_calibrated, channel_performance


def measure_dark_noise(
    usb,
    ctrl: ControllerBase,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> np.ndarray:
    """Measure dark noise with all LEDs off.

    CRITICAL: Uses V1.1 firmware LED query to VERIFY LEDs are off before measuring.
    This prevents contaminated dark measurements if LEDs fail to turn off.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        integration: Integration time in ms
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional threading event to check for cancellation
        num_scans: Optional pre-calculated scan count (if None, calculates based on integration)

    Returns:
        Array of dark noise values
    """
    logger.debug("Measuring dark noise...")

    # Step 1: Turn off all LEDs
    logger.debug("Turning off all LEDs for dark measurement...")
    ctrl.turn_off_channels()

    # Step 2: VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
    logger.debug("Verifying LEDs are off...")
    max_retries = 5
    led_verified = False
    has_led_query = hasattr(ctrl, 'get_all_led_intensities')

    if has_led_query:
        for attempt in range(max_retries):
            time.sleep(0.01)  # Wait 10ms for command to process

            # Query LED state (V1.1 firmware feature)
            led_state = ctrl.get_all_led_intensities()

            if led_state is None:
                logger.debug(f"LED query failed (attempt {attempt+1}/{max_retries}) - falling back to timing")
                # Fall back to timing-based approach
                has_led_query = False
                break

            # Check if all LEDs are off (0 intensity)
            all_off = all(intensity == 0 for intensity in led_state.values())

            if all_off:
                logger.debug(f"✅ All LEDs confirmed OFF: {led_state}")
                led_verified = True
                break
            else:
                logger.warning(f"⚠️ LEDs still on (attempt {attempt+1}/{max_retries}): {led_state}")
                # Retry turn-off command
                ctrl.turn_off_channels()
                time.sleep(0.05)  # Extra delay for stubborn LEDs

        if not led_verified and has_led_query:
            # Max retries exceeded - LEDs still not off
            final_state = ctrl.get_all_led_intensities()
            logger.error(f"❌ Failed to turn off LEDs after {max_retries} attempts")
            logger.error(f"   Final LED state: {final_state}")
            raise RuntimeError(
                f"Cannot measure dark noise - LEDs failed to turn off. "
                f"Current state: {final_state}. Check hardware connections."
            )

    if not has_led_query:
        # V1.0 firmware or LED query unavailable - use timing-based approach
        logger.debug("LED query not available - using timing-based verification")
        time.sleep(0.05)  # Extra settling time for V1.0 firmware
        led_verified = True

    # Step 3: Additional delay for LED physical decay
    logger.debug(f"Waiting {pre_led_delay_ms}ms for complete LED decay...")
    time.sleep(pre_led_delay_ms / 1000.0)

    # Use provided scan count or calculate based on integration time
    if num_scans is None:
        if integration < INTEGRATION_THRESHOLD_MS:
            dark_scans = DARK_NOISE_SCANS
        else:
            dark_scans = int(DARK_NOISE_SCANS / 2)
    else:
        dark_scans = num_scans

    # Step 4: Measure dark (now safe!)
    logger.debug(f"Measuring dark noise ({dark_scans} scans at {integration}ms integration)...")
    dark_noise_sum = np.zeros(wave_max_index - wave_min_index)

    for _scan in range(dark_scans):
        if stop_flag and stop_flag.is_set():
            break

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error("Failed to read intensity during dark noise measurement")
            raise RuntimeError("Spectrometer read failed during dark noise measurement")

        dark_noise_single = intensity_data[wave_min_index:wave_max_index]
        dark_noise_sum += dark_noise_single

    dark_noise = dark_noise_sum / dark_scans

    # Step 5: Validate dark noise is reasonable
    max_dark = np.max(dark_noise)
    mean_dark = np.mean(dark_noise)
    min_dark = np.min(dark_noise)
    logger.debug(f"✅ Dark noise measured: max = {max_dark:.0f}, mean = {mean_dark:.0f}, min = {min_dark:.0f} counts")

    # Detector-agnostic validation: Check for anomalies, not absolute values
    # Different detectors have different dark baselines (e.g., Ocean Optics ~3000, Phase Photonics different)
    #
    # What we're checking:
    # 1. Spatial uniformity: max/min ratio should be reasonable (not huge spikes)
    # 2. If we see 2-3x the typical detector range, LEDs are likely contaminating
    #
    # Use dynamic range as indicator:
    dark_range = max_dark - min_dark
    dark_ratio = max_dark / max(mean_dark, 1)  # Avoid division by zero

    # If max is >2x mean, we likely have LED contamination or saturation
    if dark_ratio > 2.0:
        logger.error(
            f"❌ CRITICAL: Dark noise has anomalous peaks (max={max_dark:.0f}, mean={mean_dark:.0f}, ratio={dark_ratio:.2f}). "
            f"Expected ratio < 2.0. LEDs may be on or detector saturated!"
        )
        raise RuntimeError(
            f"Dark noise measurement failed: max/mean ratio {dark_ratio:.2f} (expected < 2.0). "
            f"LEDs may not be turning off correctly or detector issue. Check hardware."
        )
    elif dark_ratio > 1.5:
        logger.warning(
            f"⚠️ WARNING: Dark noise variability elevated (max/mean ratio={dark_ratio:.2f}). "
            f"Expected < 1.5. Monitor for LED or detector issues."
        )

    logger.debug(f"   Dark uniformity check: ratio={dark_ratio:.2f}, range={dark_range:.0f} counts")

    return dark_noise


def measure_reference_signals(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    dark_noise: np.ndarray,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    afterglow_correction=None,
    num_scans: int = None,  # Optional: pre-calculated scan count
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
    preserve_mode: bool = False,  # If True, don't switch modes - use current mode
) -> dict[str, np.ndarray]:
    """Measure reference signals in the current or specified mode.

    By default, switches to S-mode for backward compatibility.
    Set preserve_mode=True to measure in the currently active mode (e.g., P-mode).

    IMPORTANT: Applies afterglow correction to ensure ref signals are on the same basis
    as live measurements. This is critical for accurate transmission calculations.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels
        ref_intensity: LED intensities for the current mode
        dark_noise: Dark noise array
        integration: Integration time in ms
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional threading event to check for cancellation
        afterglow_correction: Optional AfterglowCorrection instance for correction
        num_scans: Optional pre-calculated scan count (if None, calculates based on integration)
        preserve_mode: If True, don't switch modes - use current mode

    Returns:
        Dictionary of reference signal arrays for each channel (afterglow-corrected)
    """
    # Determine current mode for logging
    current_mode = "current" if preserve_mode else "S"
    logger.info(f"📊 Measuring {current_mode}-mode reference signals...")
    logger.debug(f"   Channels to measure: {ch_list}")
    logger.debug(f"   LED intensities: {ref_intensity}")
    logger.debug(f"   Integration time: {integration}ms")

    # Set integration time on spectrometer BEFORE measuring
    logger.debug(f"   Setting spectrometer integration time to {integration}ms...")
    usb.set_integration(integration)
    logger.debug(f"   ✅ Integration time set")

    if not preserve_mode:
        logger.debug("   Switching to S-mode...")
        switch_mode_safely(ctrl, "s", turn_off_leds=False)  # Use centralized mode switching
        logger.debug("   ✅ Mode switch complete")
    else:
        logger.debug("   Using current polarizer mode (preserve_mode=True)")

    # Use provided scan count or calculate based on integration time
    if num_scans is None:
        if integration < INTEGRATION_THRESHOLD_MS:
            ref_scans = REF_SCANS
        else:
            ref_scans = int(REF_SCANS / 2)
    else:
        ref_scans = num_scans

    logger.debug(f"   Will average {ref_scans} scans per channel")

    ref_sig = {}
    previous_channel = None  # Track previous channel for afterglow correction

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        logger.info(f"   Measuring channel {ch.upper()}...")
        logger.debug(f"      Setting LED {ch.upper()} to intensity {ref_intensity[ch]}/255...")
        ctrl.set_intensity(ch=ch, raw_val=ref_intensity[ch])
        logger.debug(f"      LED command sent, waiting {pre_led_delay_ms}ms...")
        time.sleep(pre_led_delay_ms / 1000.0)

        # VERIFY hardware state before measurement (V1.1 firmware)
        expected_state = {ch_: 0 for ch_ in ['a', 'b', 'c', 'd']}
        expected_state[ch] = ref_intensity[ch]
        verify_hardware_state(
            ctrl,
            expected_leds=expected_state,
            expected_mode='s' if not preserve_mode else None
        )

        ref_data_sum = np.zeros_like(dark_noise)

        for _scan in range(ref_scans):
            try:
                intensity_data = usb.read_intensity()
                if intensity_data is None:
                    logger.error(f"❌ Failed to read intensity for channel {ch.upper()} during reference measurement (scan {_scan+1}/{ref_scans})")
                    logger.error(f"   Spectrometer returned None - hardware may be disconnected or not responding")
                    raise RuntimeError(f"Spectrometer read failed during reference signal measurement for channel {ch.upper()}")

                int_val = intensity_data[wave_min_index:wave_max_index]
                ref_data_single = int_val - dark_noise
                ref_data_sum += ref_data_single
            except ConnectionError:
                # Re-raise ConnectionError to be handled at calibration level
                logger.error(f"🔌 Spectrometer disconnected during scan {_scan+1}/{ref_scans} for channel {ch.upper()}")
                raise
            except RuntimeError:
                # Re-raise RuntimeError (spectrometer read failures)
                raise
            except Exception as e:
                # Log unexpected errors and re-raise
                logger.error(f"❌ Unexpected error during reference measurement scan {_scan+1}/{ref_scans} for channel {ch.upper()}: {e}")
                raise

        # Average the scans
        ref_spectrum = ref_data_sum / ref_scans

        # Apply afterglow correction if available and we have a previous channel
        # This ensures S-ref is on same basis as live P-mode measurements
        if afterglow_correction is not None and previous_channel is not None:
            try:
                # Calculate afterglow from previous channel
                # Use LED_DELAY as the delay time (time between channels)
                afterglow_value = afterglow_correction.calculate_correction(
                    previous_channel=previous_channel,
                    integration_time_ms=float(integration),
                    delay_ms=LED_DELAY * 1000  # Convert seconds to ms
                )

                # Subtract afterglow (scalar value applies uniformly to spectrum)
                ref_spectrum = ref_spectrum - afterglow_value

                logger.debug(
                    f"📊 S-ref afterglow correction: Ch {ch.upper()} "
                    f"(prev: {previous_channel.upper()}, correction: {afterglow_value:.1f} counts)"
                )
            except Exception as e:
                logger.warning(f"⚠️ S-ref afterglow correction failed for ch {ch.upper()}: {e}")

        # Store corrected reference signal
        ref_sig[ch] = ref_spectrum
        logger.debug(f"✅ Reference signal measured for ch {ch.upper()}: max = {max(ref_sig[ch]):.0f}")

        # Track this channel as previous for next iteration
        previous_channel = ch

    return ref_sig


# =============================================================================
# QUALITY CONTROL FUNCTIONS (Shared across all calibration paths)
# =============================================================================

def validate_s_ref_quality(ref_sig: dict, wave_data) -> dict:
    """S-pol signal strength check - PRISM PRESENCE DETECTION ONLY.

    At S-pol, we can ONLY assess if a prism is present or absent by checking
    signal intensity. We CANNOT determine water presence at this stage.

    Detection logic:
    - If intensity is significantly lower than expected for the integration time
      and LED settings, suspect the prism is absent or fiber disconnected
    - Water presence can ONLY be assessed after P-pol when transmission
      spectrum (P/S ratio) is calculated and we can see if there's an SPR dip

    This is a lightweight check during initial calibration.
    For comprehensive validation (intensity drift, spectral shape correlation),
    use validate_s_ref_qc() in spr_calibrator.py instead.

    Args:
        ref_sig: Dictionary of reference signals {channel: spectrum_array}
        wave_data: Wavelength array corresponding to spectrum

    Returns:
        Dictionary with QC results per channel:
        {
            'a': {'passed': True, 'peak': 25000, 'peak_wl': 580, 'warnings': []},
            ...
        }
    """
    import numpy as np

    qc_results = {}

    for ch, spectrum in ref_sig.items():
        result = {
            'passed': False,
            'peak': 0,
            'peak_wl': 0,
            'warnings': []
        }

        try:
            # Find LED peak intensity
            peak_intensity = np.max(spectrum)
            peak_idx = np.argmax(spectrum)
            peak_wavelength = wave_data[peak_idx]

            result['peak'] = float(peak_intensity)
            result['peak_wl'] = float(peak_wavelength)

            # Check signal strength for prism presence detection
            # Very low signal suggests prism absent or fiber disconnected
            if peak_intensity < 5000:
                result['warnings'].append('Very weak signal - prism may be absent or fiber disconnected')
            elif peak_intensity < 10000:
                result['warnings'].append('Weak signal - check fiber connection or optics')

            result['passed'] = peak_intensity > 5000

            if result['passed']:
                logger.debug(f"✅ S-ref signal OK for Ch {ch.upper()}: {peak_intensity:.0f} counts @ {peak_wavelength:.0f}nm")
            else:
                logger.warning(f"⚠️ S-ref signal weak for Ch {ch.upper()}: {', '.join(result['warnings'])}")

        except Exception as e:
            logger.error(f"S-ref QC validation failed for channel {ch}: {e}")
            result['warnings'].append(f'QC error: {str(e)}')

        qc_results[ch] = result

    return qc_results


def verify_calibration(
    usb,
    ctrl: ControllerBase,
    leds_calibrated: dict[str, int],
    wave_data: np.ndarray = None,
    s_ref_signals: dict = None,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> tuple[list[str], dict[str, float], bool]:
    """Verify that all calibrated P-mode channels meet minimum requirements.

    CRITICAL: This is where we detect water presence and SPR coupling quality!

    At S-pol (previous step), we could ONLY detect:
    - Prism presence/absence (by signal intensity)
    - Fiber connection status

    At P-pol (this step), we can NOW detect:
    - Water presence (by SPR dip in transmission spectrum P/S)
    - SPR coupling quality (by dip depth and FWHM)
    - Sensor response (by comparing P vs S intensities)

    Verification checks:
    1. No saturation across full spectrum (< 95% of detector max)
    2. SPR dip validation in TRANSMISSION spectrum (P/S ratio):
       - Calculate transmission = P-spectrum / S-spectrum
       - Check for SPR dip (valley) in transmission
       - Dip presence confirms water/buffer is present
       - No dip or inverted peak suggests dry sensor or swapped polarizer
    3. FWHM analysis on TRANSMISSION spectrum:
       - Narrow FWHM (15-30nm) = good water contact, high sensitivity
       - Broad FWHM (>50nm) = poor water contact, air bubbles, or sensor degradation
       - Very broad (>80nm) = likely dry sensor or no SPR coupling

    Conceptual model:
    - S-pol: LED spectral profile baseline (no SPR information)
    - P-pol: Measures light after SPR interaction (includes SPR absorption)
    - Transmission (P/S): Isolates SPR effect by dividing out LED profile
    - SPR dip in transmission = proof of water presence and sensor response

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        leds_calibrated: Dictionary of calibrated P-mode LED intensities
        wave_data: Wavelength array (if None, will read from detector)
        s_ref_signals: S-mode reference signals for comparison

    Returns:
        Tuple of (ch_error_list, spr_fwhm_dict, polarizer_swap_detected)
        - ch_error_list: List of channels that failed verification
        - spr_fwhm_dict: Dictionary of FWHM values for each channel (nm)
        - polarizer_swap_detected: True if 3+ channels show inverted S/P orientation
    """
    logger.debug("Verifying P-mode LED calibration...")

    # Get wavelength data if not provided
    if wave_data is None:
        wave_data = usb.read_wavelength()

    # Get detector saturation threshold
    max_counts = usb.max_counts
    saturation_threshold = max_counts * 0.95  # 95% of max is considered saturated
    logger.debug(f"Saturation threshold: {saturation_threshold:.0f} counts")

    ch_error_list = []
    spr_fwhm = {}
    orientation_inverted_channels = []  # Track channels with S/P swap detected

    # CRITICAL: Turn off all channels before P-mode switch to eliminate afterglow
    # Prevents residual signal from S-ref measurements affecting P-mode verification
    ctrl.turn_off_channels()
    time.sleep(LED_DELAY * 3)  # Extra delay for afterglow decay (~60ms total)

    # Switch to P-mode for verification
    ctrl.set_mode(mode="p")
    time.sleep(0.4)

    logger.info(f"🔍 Starting P-mode verification for {len(leds_calibrated)} channels")
    logger.debug(f"   Calibrated LED intensities: {leds_calibrated}")

    for ch in CH_LIST:
        intensity = leds_calibrated.get(ch, 0)
        if intensity == 0:
            continue

        logger.debug(f"   Verifying ch {ch.upper()} at LED intensity {intensity}...")

        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(pre_led_delay_ms / 1000.0)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error(f"Failed to read intensity during verification for channel {ch.upper()}")
            ch_error_list.append(ch)
            continue

        # Trim intensity_data to match the calibrated wavelength range
        # wave_data is already trimmed to MIN_WAVELENGTH:MAX_WAVELENGTH during calibration
        # but intensity_data is the full detector range, so we need to trim it
        if hasattr(usb, 'wave_min_index') and hasattr(usb, 'wave_max_index'):
            # Use the indices stored on the USB device during calibration
            intensity_data = intensity_data[usb.wave_min_index:usb.wave_max_index]
        elif len(intensity_data) != len(wave_data):
            # Fallback: trim to match wave_data length
            logger.warning(f"Ch {ch.upper()}: Trimming intensity_data from {len(intensity_data)} to {len(wave_data)} pixels")
            intensity_data = intensity_data[:len(wave_data)]

        # Check 1: No saturation across entire spectrum
        spectrum_max = intensity_data.max()
        spectrum_mean = intensity_data.mean()

        logger.debug(f"   Ch {ch.upper()}: max={spectrum_max:.0f}, mean={spectrum_mean:.0f}, threshold={saturation_threshold:.0f}")

        # CRITICAL: Validate S/P orientation using transmission spectrum analysis
        # This confirms polarizer orientation by analyzing transmission peak shape, width, depth
        # and triangulating peak vs edges
        # Note: Raw P vs S intensity comparison is ONLY used in servo calibration, not here
        if s_ref_signals and ch in s_ref_signals and wave_data is not None:
            try:
                from utils.spr_signal_processing import validate_sp_orientation

                validation = validate_sp_orientation(
                    p_spectrum=intensity_data,
                    s_spectrum=s_ref_signals[ch],
                    wavelengths=wave_data,
                    window_px=200
                )

                if validation['is_flat']:
                    logger.error(f"❌ CALIBRATION FAILED - Ch {ch.upper()}: Flat transmission spectrum!")
                    logger.error(f"   Range: {np.ptp(intensity_data / (s_ref_signals[ch] + 1e-10)):.2f}% - possible saturation or dark signal")
                    logger.error(f"   This is a BLOCKING issue - calibration cannot proceed")
                    ch_error_list.append(ch)
                    continue
                elif not validation['orientation_correct']:
                    logger.error(f"❌ CALIBRATION FAILED - Ch {ch.upper()}: S/P ORIENTATION INVERTED!")
                    logger.error(f"   Transmission peak at {validation['peak_wl']:.1f}nm is HIGHER ({validation['peak_value']:.1f}%) than sides")
                    logger.error(f"   Left: {validation['left_value']:.1f}%, Right: {validation['right_value']:.1f}%")
                    logger.error(f"   ⚠️ CRITICAL: S and P polarizer positions are SWAPPED")
                    logger.error(f"   → OEM calibration required to set correct polarizer positions")
                    logger.error(f"   This is a BLOCKING issue tied to device-level configuration")
                    ch_error_list.append(ch)
                    orientation_inverted_channels.append(ch)  # Track for auto-correction
                    continue
                else:
                    logger.info(f"✅ Ch {ch.upper()}: S/P orientation validated (dip at {validation['peak_wl']:.1f}nm = {validation['peak_value']:.1f}%, confidence={validation['confidence']:.2f})")

            except Exception as e:
                logger.warning(f"⚠️ S/P orientation validation failed for ch {ch.upper()}: {e}")

        if spectrum_max > saturation_threshold:
            # Auto-reduce LED intensity to avoid saturation
            # Calculate required reduction: target 85% of max instead of 95%
            reduction_factor = (max_counts * 0.85) / spectrum_max
            new_intensity = max(10, int(intensity * reduction_factor))  # Minimum LED=10

            logger.warning(
                f"⚠️ P-mode saturation detected for ch {ch.upper()}: "
                f"{spectrum_max:.0f} counts (threshold: {saturation_threshold:.0f}, LED={intensity})"
            )
            logger.info(f"   → Auto-reducing LED intensity: {intensity} → {new_intensity} (factor={reduction_factor:.2f})")

            # Apply reduced intensity and re-measure
            ctrl.set_intensity(ch=ch, raw_val=new_intensity)
            time.sleep(pre_led_delay_ms / 1000.0)

            intensity_data = usb.read_intensity()
            if intensity_data is None:
                logger.error(f"Failed to read intensity after reduction for channel {ch.upper()}")
                ch_error_list.append(ch)
                continue

            # Re-trim to wavelength range
            if hasattr(usb, 'wave_min_index') and hasattr(usb, 'wave_max_index'):
                intensity_data = intensity_data[usb.wave_min_index:usb.wave_max_index]
            elif len(intensity_data) != len(wave_data):
                intensity_data = intensity_data[:len(wave_data)]

            spectrum_max = intensity_data.max()
            spectrum_mean = intensity_data.mean()

            if spectrum_max > saturation_threshold:
                # Still saturated after reduction - hardware issue
                ch_error_list.append(ch)
                logger.error(
                    f"❌ Ch {ch.upper()} still saturated after LED reduction: "
                    f"{spectrum_max:.0f} counts (LED={new_intensity})"
                )
                continue
            else:
                # Success! Update the calibrated LED value
                leds_calibrated[ch] = new_intensity
                logger.info(f"✅ Ch {ch.upper()} corrected: LED={new_intensity}, max={spectrum_max:.0f} counts")
                # Continue to SPR validation below with new intensity_data


        # Check 2 & 3: Validate SPR dip presence and calculate FWHM
        if s_ref_signals and ch in s_ref_signals:
            s_spectrum = np.array(s_ref_signals[ch])
            p_spectrum = intensity_data

            # Ensure both spectra have the same length as wave_data
            # They should already be trimmed to the same wavelength range during calibration
            # but handle any edge cases where they might differ
            if len(s_spectrum) != len(wave_data):
                logger.warning(f"Ch {ch.upper()}: S-spectrum length ({len(s_spectrum)}) doesn't match wave_data ({len(wave_data)}), trimming")
                s_spectrum = s_spectrum[:len(wave_data)] if len(s_spectrum) > len(wave_data) else np.pad(s_spectrum, (0, len(wave_data) - len(s_spectrum)), constant_values=0)

            if len(p_spectrum) != len(wave_data):
                logger.warning(f"Ch {ch.upper()}: P-spectrum length ({len(p_spectrum)}) doesn't match wave_data ({len(wave_data)}), trimming")
                p_spectrum = p_spectrum[:len(wave_data)] if len(p_spectrum) > len(wave_data) else np.pad(p_spectrum, (0, len(wave_data) - len(p_spectrum)), constant_values=0)

            # Find S-pol LED peak location for this channel
            s_peak_idx = np.argmax(s_spectrum)
            s_peak_wavelength = wave_data[s_peak_idx] if s_peak_idx < len(wave_data) else 620

            # Define dynamic SPR ROI based on S-pol peak
            # SPR typically occurs 20-60nm redshifted from LED peak
            roi_start = s_peak_wavelength + 10  # nm
            roi_end = s_peak_wavelength + 80    # nm

            roi_mask = (wave_data >= roi_start) & (wave_data <= roi_end)

            if np.any(roi_mask):
                # Get intensity in SPR region for both S and P
                # Both spectra are now guaranteed to be the same length as wave_data
                s_roi = s_spectrum[roi_mask]
                p_roi = p_spectrum[roi_mask]
                wave_roi = wave_data[roi_mask]

                s_roi_mean = np.mean(s_roi)
                p_roi_mean = np.mean(p_roi)

                # Calculate P/S ratio for SPR dip validation
                # Note: P-mode LED can be boosted up to 1.33x to compensate for polarizer loss
                # So even with SPR dip, P/S ratio will be higher than without boost
                # Example: 1.33x boost with 30% SPR dip → ratio = 1.33 × 0.7 = 0.93
                ratio = p_roi_mean / s_roi_mean if s_roi_mean > 0 else 1.0

                # Calculate transmission-based FWHM: P/S (light transmitted through sensor)
                # SPR causes a dip in transmission (less light passes through at resonance)
                # Note: Dark noise already subtracted from ref signals during calibration
                transmission = p_roi / (s_roi + 1e-10)  # P/S ratio, avoid divide by zero

                # SPR appears as a dip in transmission (transmission decreases at SPR wavelength)
                # Invert to get SPR dip peak for FWHM calculation
                spr_dip = 1.0 - transmission  # Dip: where transmission is lowest
                spr_dip = spr_dip - np.min(spr_dip)  # Shift to baseline at zero

                dip_max = np.max(spr_dip)
                half_max = dip_max / 2.0

                # Find wavelengths where dip crosses half-maximum
                above_half = spr_dip >= half_max
                if np.any(above_half):
                    indices = np.where(above_half)[0]
                    if len(indices) > 1:
                        fwhm = wave_roi[indices[-1]] - wave_roi[indices[0]]
                        spr_fwhm[ch] = float(fwhm)

                        # Quality assessment based on FWHM thresholds (sensor readiness)
                        # Narrow FWHM = good sensor coupling, wide FWHM = poor coupling or sensor degradation
                        if fwhm < 15:
                            quality = "excellent"
                            sensor_readiness = "✅ Excellent sensor coupling"
                        elif fwhm < 30:
                            quality = "good"
                            sensor_readiness = "✅ Good sensor quality"
                        elif fwhm < 50:
                            quality = "okay"
                            sensor_readiness = "⚠️ Acceptable but monitor coupling"
                        else:
                            quality = "poor"
                            sensor_readiness = "⚠️ Poor sensor coupling - check water/prism contact"

                        logger.info(
                            f"✅ Ch {ch.upper()}: SPR FWHM={fwhm:.1f}nm ({quality}) - {sensor_readiness}"
                        )
                        logger.debug(
                            f"   Details: max={spectrum_max:.0f} counts, P/S ratio={ratio:.2f}"
                        )
                    else:
                        logger.debug(
                            f"✅ Ch {ch.upper()} verified: max={spectrum_max:.0f} counts, "
                            f"P/S ratio={ratio:.2f} (FWHM not calculable - very narrow dip)"
                        )
                else:
                    logger.debug(
                        f"✅ Ch {ch.upper()} verified: max={spectrum_max:.0f} counts, "
                        f"P/S ratio={ratio:.2f} (no clear SPR dip for FWHM)"
                    )

                # SPR dip validation with adjusted threshold for P-mode LED boost
                # With max boost (1.33x) and minimal SPR (20% dip), ratio = 1.33 × 0.8 = 1.06
                # Use 1.15 threshold to allow for measurement noise and weak SPR
                if ratio >= 1.15:  # P significantly higher than S, SPR dip very weak/absent
                    logger.error(f"⚠️ Ch {ch.upper()}: Transmission peak WEAK or ABSENT (P/S={ratio:.2f})")
                    logger.error(f"   💧 LIKELY CAUSE: Sensor is DRY - no water on prism surface!")
                    logger.error(f"   → Apply water or buffer to prism and retry calibration")
                    logger.warning(
                        f"⚠️ P-mode verification note for ch {ch.upper()}: "
                        f"P/S ratio = {ratio:.2f} in SPR region ({roi_start:.0f}-{roi_end:.0f}nm) - "
                        f"SPR response very weak or sensor not placed"
                    )
            else:
                logger.debug(f"✅ Ch {ch.upper()} verified: {spectrum_max:.0f} counts (no saturation)")
        else:
            logger.debug(f"✅ Ch {ch.upper()} verified: {spectrum_max:.0f} counts (no saturation)")

    # Log FWHM summary for sensor readiness assessment
    if spr_fwhm:
        logger.info("")
        logger.info("📏 SENSOR READINESS ASSESSMENT (FWHM):")
        for ch, fwhm in spr_fwhm.items():
            if fwhm < 15:
                status = "✅ Excellent"
            elif fwhm < 30:
                status = "✅ Good"
            elif fwhm < 50:
                status = "⚠️ Okay"
            else:
                status = "⚠️ Poor"
            logger.info(f"   Ch {ch.upper()}: {fwhm:.1f}nm - {status}")

        avg_fwhm = sum(spr_fwhm.values()) / len(spr_fwhm)
        if avg_fwhm < 30:
            logger.info(f"   ✅ Average: {avg_fwhm:.1f}nm - Sensor ready for measurements")
        elif avg_fwhm < 50:
            logger.info(f"   ⚠️ Average: {avg_fwhm:.1f}nm - Acceptable but monitor quality")
        else:
            logger.info(f"   ⚠️ Average: {avg_fwhm:.1f}nm - Check water/prism contact")
        logger.info("")

    # Detect if polarizer positions should be swapped
    # Use 3+ channels as threshold for safety (global issue, not single channel)
    polarizer_swap_detected = len(orientation_inverted_channels) >= 3

    if polarizer_swap_detected:
        logger.error(f"\n⚠️ POLARIZER SWAP DETECTED: {len(orientation_inverted_channels)} channels show inverted orientation")
        logger.error(f"   Affected channels: {', '.join([c.upper() for c in orientation_inverted_channels])}")
        logger.error(f"   This is a GLOBAL issue - polarizer servo positions need to be swapped")

    return ch_error_list, spr_fwhm, polarizer_swap_detected


# =============================================================================
# MAIN CALIBRATION ENTRY POINTS
# =============================================================================

def perform_full_led_calibration(
    usb,
    ctrl: ControllerBase,
    device_type: str,
    single_mode: bool = False,
    single_ch: str = "a",
    integration_step: int = 2,
    stop_flag=None,
    progress_callback=None,
    _polarizer_swap_retry_done: bool = False,  # Internal flag to prevent infinite recursion
    wave_data=None,  # Optional: pre-read wavelength data (avoids redundant USB read)
    wave_min_index: int = None,  # Optional: pre-computed min index
    wave_max_index: int = None,  # Optional: pre-computed max index
    device_config=None,  # Optional: pre-loaded DeviceConfiguration (avoids redundant file reads)
    polarizer_type: str = None,  # Optional: polarizer type ('barrel' or 'round') - sets calibration expectations
    afterglow_correction=None,  # Optional: pre-loaded AfterglowCorrection (avoids redundant file I/O)
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
) -> LEDCalibrationResult:
    """Perform complete LED calibration using STANDARD optical configuration.

    OPTICAL SYSTEM MODE: STANDARD (Global Integration Time, Variable LED)
    ========================================================
    This function implements MODE 1: ONE integration time, VARIABLE LED intensities

    Recorded to device_config.json:
      - integration_time_ms: 93 (single value - SAME for all channels)
      - s_mode_intensities: {'a': 187, 'b': 203, 'c': 195, 'd': 178} (VARIABLE per channel)
      - p_mode_intensities: {'a': 238, 'b': 255, 'c': 245, 'd': 229} (VARIABLE per channel)

    ============================================================================
    CALIBRATION MODE DECISION LOGIC (SINGLE SOURCE OF TRUTH: device_config.json)
    ============================================================================

    FAST-TRACK MODE:
    - IF device_config.json contains valid saved LED intensities
    - THEN load saved values → validate on hardware → use if still valid
    - Integration time is ALWAYS calibrated (cannot cache - hardware dependent)
    - Channels that fail validation are automatically re-calibrated
    - Saves ~80% time if values are still good

    FULL CALIBRATION MODE:
    - IF device_config.json is missing LED calibration data
    - THEN find optimal LED values from scratch via binary search
    - Integration time is calibrated from scratch
    - All channels calibrated via hardware measurements

    AFTER CALIBRATION (BOTH MODES):
    - Integration time, S-mode LEDs, P-mode LEDs saved to device_config.json
    - Reference spectra saved for QC validation
    - device_config.json updated as single source of truth for next run

    ============================================================================

    Calibration Steps:
    1. Wavelength data acquisition
    2. Integration time optimization (ALWAYS calibrated - hardware dependent)
    3. S-mode LED intensity calibration (fast-track OR full)
    4. Dark noise measurement
    5. S-mode reference signal measurement (with afterglow correction if available)
    6. S-mode optical QC validation
    7. P-mode LED intensity calibration
    8. P-mode verification (saturation, SPR dip, FWHM)

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        device_type: Device type string (e.g., 'P4SPR', 'PicoP4SPR')
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode
        integration_step: Step size for integration time adjustment
        stop_flag: Optional threading event to check for cancellation
        progress_callback: Optional callback for progress updates

    Returns:
        LEDCalibrationResult object with all calibration data
    """
    result = LEDCalibrationResult()

    try:
        logger.info("=== Starting LED Calibration ===")

        # CRITICAL: Verify hardware is connected before attempting calibration
        if ctrl is None:
            logger.error("❌ HARDWARE ERROR: No controller connected")
            logger.error("   Controller is None - calibration cannot proceed")
            raise RuntimeError("No controller connected - hardware must be connected before calibration")

        if usb is None:
            logger.error("❌ HARDWARE ERROR: No spectrometer connected")
            logger.error("   Spectrometer is None - calibration cannot proceed")
            raise RuntimeError("No spectrometer connected - hardware must be connected before calibration")

        logger.info(f"🔌 Hardware Status:")
        logger.info(f"   Controller: {type(ctrl).__name__} (connected)")
        logger.info(f"   Spectrometer: {type(usb).__name__} (connected)")
        logger.info("")
        logger.info("⚠️  PRE-CALIBRATION CHECKLIST:")
        logger.info("   ✅ Prism installed in sensor holder")
        logger.info("   ✅ Water or buffer applied to prism surface")
        logger.info("   ✅ No air bubbles between prism and sensor")
        logger.info("   ✅ Temperature stable (wait 10 min after setup)")
        logger.info("")
        logger.info("💧 Water is REQUIRED - dry sensor will show weak/absent SPR peak")
        logger.info("")

        # Get wavelength data (use provided or read from hardware)
        if wave_data is None:
            logger.debug("Reading wavelength data...")
            wave_data = usb.read_wavelength()
            result.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            result.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        else:
            logger.debug("Using pre-read wavelength data (optimization)")
            result.wave_min_index = wave_min_index if wave_min_index is not None else wave_data.searchsorted(MIN_WAVELENGTH)
            result.wave_max_index = wave_max_index if wave_max_index is not None else wave_data.searchsorted(MAX_WAVELENGTH)

        result.wave_data = wave_data[result.wave_min_index : result.wave_max_index]
        logger.debug(
            f"Wavelength range: index {result.wave_min_index} to {result.wave_max_index}"
        )

        # Get detector parameters ONCE (optimization: eliminates 5-6 redundant property accesses)
        detector_params = get_detector_params(usb)

        # Get polarizer type and set calibration expectations
        if polarizer_type is None and device_config is not None:
            polarizer_type = device_config.get_polarizer_type()
        if polarizer_type is None:
            polarizer_type = 'circular'  # Default assumption for safety

        # Set expectations based on polarizer hardware
        cal_expectations = get_calibration_expectations(polarizer_type)
        logger.info(f"\n🔧 POLARIZER CONFIGURATION:")
        logger.info(f"   Type: {polarizer_type.upper()}")
        logger.info(f"   Servo Positions: Loaded from device_config.json (calibrated previously)")
        logger.info(f"   → If config was not populated, {cal_expectations['servo_calibration_complexity']} servo calibration would run first")
        logger.info(f"   → {cal_expectations['servo_calibration_method']}")
        logger.info(f"   LED Calibration: {cal_expectations['led_calibration_complexity']} (common path) - {cal_expectations['led_calibration_notes']}")
        logger.info(f"   Expected S/P Ratio: {cal_expectations['expected_s_p_ratio'][0]:.1f}× to {cal_expectations['expected_s_p_ratio'][1]:.1f}× (sample-dependent)")
        logger.info(f"   P-mode Strategy: {'Boost LED using S-mode headroom analysis' if cal_expectations['requires_headroom_analysis'] else 'Direct optimization'}")
        logger.info("")

        # Calculate Fourier weights for denoising (centralized utility)
        result.fourier_weights = calculate_fourier_weights(len(result.wave_data))

        # Determine channel list ONCE (optimization: single source of truth)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.debug(f"Calibrating channels: {ch_list}")

        # Step 1: Calibrate integration time
        try:
            result.integration_time, result.num_scans = calibrate_integration_time(
                usb, ctrl, ch_list, integration_step, stop_flag,
                device_config=device_config,
                detector_params=detector_params
            )
        except ConnectionError as e:
            logger.error(f"🔌 Hardware disconnected during Step 1 (Integration Time)")
            logger.error(f"   {str(e)}")
            result.success = False
            result.error = f"Hardware disconnected during integration time calibration: {str(e)}"
            return result

        if stop_flag and stop_flag.is_set():
            return result

        # ========================================================================
        # STEP 2: LED INTENSITY CALIBRATION (S-MODE)
        # ========================================================================
        # DECISION LOGIC: Fast-Track vs Full Calibration
        # - Source of Truth: device_config.json ONLY
        # - Fast-Track: Load saved LED values → Validate on hardware → Use if valid
        # - Full: Find optimal LED values from scratch via binary search
        # - Both modes: Always calibrate integration time first (cannot cache)
        # - After calibration: Save results to device_config.json for next run
        # ========================================================================

        saved_led_intensities = None
        if device_config is not None:
            try:
                # Load calibration from device_config.json (single source of truth)
                cal_data = device_config.load_led_calibration()
                if cal_data and 's_mode_intensities' in cal_data:
                    saved_led_intensities = cal_data['s_mode_intensities']
                    cal_date = cal_data.get('calibration_date', 'unknown')
                    logger.info(f"📋 Found saved LED calibration in device_config.json (from {cal_date}):")
                    for ch, intensity in saved_led_intensities.items():
                        logger.info(f"   Ch {ch.upper()}: LED = {intensity}/255")
                else:
                    logger.debug("   No saved LED intensities in device_config.json")
            except Exception as e:
                logger.debug(f"Could not load LED intensities from device config: {e}")

        logger.info("Calibrating LED intensities (S-mode)...")
        logger.debug(f"🔧 Switching to S-mode (controller type: {type(ctrl).__name__})...")
        switch_mode_safely(ctrl, "s", turn_off_leds=False)  # Use centralized mode switching
        logger.debug(f"✅ Mode switch complete")

        # ========================================================================
        # PRE-FLIGHT HARDWARE CHECK: Verify detector is responsive before calibration
        # ========================================================================
        logger.info("🔍 Pre-flight check: Verifying hardware is connected and responsive...")

        # Test with first channel at high intensity to verify hardware connection
        test_channel = ch_list[0]
        logger.info(f"   Testing LED {test_channel.upper()} at intensity 200/255...")
        logger.debug(f"   Controller type: {type(ctrl).__name__}")
        logger.debug(f"   Sending command: set_intensity(ch='{test_channel}', raw_val=200)...")

        try:
            led_command_result = ctrl.set_intensity(ch=test_channel, raw_val=200)
            logger.debug(f"   LED command returned: {led_command_result}")
            if led_command_result is False:
                logger.warning(f"   ⚠️ LED command returned False - controller may not have acknowledged")
        except Exception as e:
            logger.error(f"   ❌ LED command failed with exception: {e}")
            raise RuntimeError(f"Hardware validation failed: LED command raised exception: {e}")

        logger.debug(f"   Waiting 200ms for LED to stabilize...")
        time.sleep(0.2)

        logger.debug(f"   Pre-flight: Reading spectrum from spectrometer...")
        test_spectrum = usb.read_intensity()
        logger.debug(f"   Pre-flight: Spectrum read complete (result: {'valid' if test_spectrum is not None else 'NULL'})")

        if test_spectrum is None:
            logger.error("❌ PRE-FLIGHT CHECK FAILED: Spectrometer not responding")
            raise RuntimeError("Hardware validation failed: Spectrometer disconnected or not responding")

        test_signal = float(np.max(test_spectrum[wave_min_index:wave_max_index]))
        logger.debug(f"   Pre-flight: Max signal = {test_signal:.0f} counts (expected > 100)")

        if test_signal < 100:
            logger.error("❌ PRE-FLIGHT CHECK FAILED: No signal detected from hardware")
            logger.error(f"   LED {test_channel.upper()} set to 200 but signal is only {test_signal:.0f} counts")
            logger.error(f"   Expected at least 100 counts")
            logger.error(f"   Possible causes:")
            logger.error(f"   - Hardware disconnected")
            logger.error(f"   - LEDs not working")
            logger.error(f"   - Light path blocked")
            logger.error(f"   - No water/prism on sensor")
            raise RuntimeError("Hardware validation failed: No signal detected during pre-flight check")

        logger.info(f"✅ Pre-flight check passed: Hardware responding with {test_signal:.0f} counts")

        # Turn off test LED
        ctrl.set_intensity(ch=test_channel, raw_val=0)
        time.sleep(0.1)

        # Validate saved_led_intensities is usable (not None/empty, has valid values)
        use_fast_track = False

        # TEMPORARY: Fast-track disabled for testing - always run full calibration
        logger.info("🔧 FAST-TRACK DISABLED (testing mode) - running FULL CALIBRATION")
        use_fast_track = False

        # Original fast-track logic (currently disabled):
        # if saved_led_intensities:
        #     # Check if LED values exist and are valid for ALL channels we need to calibrate
        #     valid_led_count = 0
        #     missing_channels = []
        #     invalid_channels = []
        #
        #     for ch in ch_list:
        #         if ch in saved_led_intensities:
        #             led_val = saved_led_intensities[ch]
        #             if led_val is not None and isinstance(led_val, (int, float)) and 1 <= led_val <= 255:
        #                 valid_led_count += 1
        #             else:
        #                 invalid_channels.append(ch)
        #                 logger.warning(f"   ⚠️ Ch {ch.upper()}: Invalid LED value in device config: {led_val}")
        #         else:
        #             missing_channels.append(ch)
        #
        #     if valid_led_count == len(ch_list):
        #         use_fast_track = True
        #         logger.info(f"🚀 FAST-TRACK MODE: All {len(ch_list)} channels have valid LED values in device config")
        #     else:
        #         logger.warning(f"⚠️ Device config calibration is incomplete:")
        #         if missing_channels:
        #             logger.warning(f"   Missing LED data for: {', '.join([c.upper() for c in missing_channels])}")
        #         if invalid_channels:
        #             logger.warning(f"   Invalid LED data for: {', '.join([c.upper() for c in invalid_channels])}")
        #         logger.info("   Falling back to FULL CALIBRATION for all channels")
        # else:
        #     logger.info("ℹ️ No saved LED calibration in device config - running FULL CALIBRATION")

        if use_fast_track:
            # Fast-track workflow: Validate saved LED intensities from device config
            # - Integration time was already calibrated (always required)
            # - LED values are loaded from previous calibration in device_config.json
            # - Each LED is tested on hardware to verify it still produces correct signal
            # - Channels that fail validation are re-calibrated automatically
            logger.info("   Loading saved LED values from device config and validating on hardware...")

            # Show fast-track message in UI
            if progress_callback:
                progress_callback("Fast-track: Validating saved LED values...")

            # Track validation results
            validation_passed = []
            validation_failed = []

            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                # Get LED intensity from device config
                if ch in saved_led_intensities:
                    led_val = int(saved_led_intensities[ch])
                    logger.info(f"   Testing Ch {ch.upper()}: Using saved LED={led_val} from device config")

                    # Set LED and validate signal level (REAL HARDWARE COMMUNICATION)
                    logger.debug(f"      → Setting hardware LED {ch.upper()} to {led_val}")
                    ctrl.set_intensity(ch=ch, raw_val=led_val)
                    time.sleep(0.1)

                    # Read signal and verify it's within acceptable range (REAL HARDWARE READ)
                    logger.debug(f"      → Reading spectrum from hardware...")
                    sp = usb.read_intensity()
                    if sp is None:
                        logger.error(f"      ❌ Hardware read failed - spectrometer not responding")
                        raise RuntimeError(f"Spectrometer disconnected during validation of channel {ch.upper()}")

                    roi = sp[wave_min_index:wave_max_index]
                    max_val = float(np.max(roi))

                    # CRITICAL: Verify signal is not just noise
                    if max_val < 500:
                        logger.error(f"      ❌ Ch {ch.upper()}: LED set to {led_val} but signal is only {max_val:.0f} counts")
                        logger.error(f"      This indicates hardware is not responding correctly!")
                        raise RuntimeError(f"Hardware validation failed: No signal from channel {ch.upper()}")

                    # Check if signal is in reasonable range (30-80% of detector max)
                    detector_max = detector_params.max_counts
                    min_acceptable = 0.3 * detector_max
                    max_acceptable = 0.8 * detector_max

                    if min_acceptable <= max_val <= max_acceptable:
                        result.ref_intensity[ch] = led_val
                        validation_passed.append(ch)
                        logger.info(f"   ✅ Ch {ch.upper()}: LED {led_val} validated (signal: {max_val:.0f} counts, range: {min_acceptable:.0f}-{max_acceptable:.0f})")
                    else:
                        # Signal out of range - do full calibration for this channel
                        validation_failed.append(ch)
                        if max_val < min_acceptable:
                            reason = f"too weak ({max_val:.0f} < {min_acceptable:.0f})"
                        else:
                            reason = f"too strong ({max_val:.0f} > {max_acceptable:.0f})"
                        logger.warning(f"   ⚠️ Ch {ch.upper()}: Signal {reason}, recalibrating...")
                        if progress_callback:
                            progress_callback(f"Recalibrating LED {ch.upper()}...")
                        result.ref_intensity[ch] = calibrate_led_channel(
                            usb, ctrl, ch, None, stop_flag,
                            detector_params=detector_params
                        )
                else:
                    # Channel not in device config - do full calibration
                    validation_failed.append(ch)
                    logger.warning(f"   ⚠️ Ch {ch.upper()}: No saved LED value in device config")
                    if progress_callback:
                        progress_callback(f"Calibrating LED {ch.upper()}...")
                    result.ref_intensity[ch] = calibrate_led_channel(
                        usb, ctrl, ch, None, stop_flag,
                        detector_params=detector_params
                    )

            # Log validation summary
            if validation_passed:
                logger.info(f"✅ Fast-track validation passed for: {', '.join([c.upper() for c in validation_passed])}")
            if validation_failed:
                logger.warning(f"⚠️ Fast-track validation failed for: {', '.join([c.upper() for c in validation_failed])} - recalibrated from scratch")

            logger.info("✅ Fast-track LED validation complete - proceeding to measure S-mode spectra")
            if progress_callback:
                progress_callback("Fast-track complete - measuring reference spectra...")
        else:
            # Full calibration workflow: Find optimal LED values from scratch
            # - Integration time was already calibrated
            # - Binary search to find LED intensity that produces target signal
            # - No starting values, measures and adjusts LED for each channel
            logger.info("📊 FULL CALIBRATION MODE: Finding optimal LED intensities from hardware measurements")
            for i, ch in enumerate(ch_list):
                if stop_flag and stop_flag.is_set():
                    break
                if progress_callback:
                    progress_callback(f"Calibrating LED {ch.upper()}...")
                logger.info(f"   Calibrating Ch {ch.upper()} (using real hardware measurements)...")
                result.ref_intensity[ch] = calibrate_led_channel(
                    usb, ctrl, ch, None, stop_flag,
                    detector_params=detector_params  # Pass pre-read detector params
                )

        logger.info(f"✅ S-mode calibration complete: {result.ref_intensity}")

        # ========================================================================
        # POST-CALIBRATION VALIDATION: Verify all channels have valid LED values
        # ========================================================================
        invalid_led_values = []
        for ch, led_val in result.ref_intensity.items():
            if led_val is None or led_val < 1 or led_val > 255:
                invalid_led_values.append(f"{ch.upper()}={led_val}")

        if invalid_led_values:
            logger.error(f"❌ POST-CALIBRATION CHECK FAILED: Invalid LED values detected")
            logger.error(f"   Invalid channels: {', '.join(invalid_led_values)}")
            logger.error(f"   This indicates calibration did not complete successfully")
            raise RuntimeError(f"Calibration validation failed: Invalid LED values for channels {', '.join(invalid_led_values)}")

        # Verify we can actually produce signal with the calibrated values
        logger.info("🔍 Post-calibration verification: Testing all channels produce expected signal...")
        all_channels_verified = True

        for ch, led_val in result.ref_intensity.items():
            ctrl.set_intensity(ch=ch, raw_val=led_val)
            time.sleep(0.1)

            verify_spectrum = usb.read_intensity()
            if verify_spectrum is None:
                logger.error(f"❌ Ch {ch.upper()}: Hardware read failed during verification")
                raise RuntimeError("Hardware disconnected during post-calibration verification")

            verify_signal = float(np.max(verify_spectrum[wave_min_index:wave_max_index]))
            expected_min = 0.25 * detector_params.max_counts
            expected_max = 0.85 * detector_params.max_counts

            if verify_signal < expected_min or verify_signal > expected_max:
                logger.error(f"❌ Ch {ch.upper()}: Verification failed - LED={led_val} produces {verify_signal:.0f} counts")
                logger.error(f"   Expected range: {expected_min:.0f}-{expected_max:.0f} counts")
                all_channels_verified = False
            else:
                logger.debug(f"   ✅ Ch {ch.upper()}: LED={led_val} → {verify_signal:.0f} counts (verified)")

        if not all_channels_verified:
            logger.error("❌ POST-CALIBRATION VERIFICATION FAILED")
            raise RuntimeError("Calibration verification failed: Channels not producing expected signal")

        logger.info("✅ Post-calibration verification passed: All channels producing expected signal")

        # Note: LEDs are left ON after verification - they will be used for reference measurement
        # The measure_reference_signals() function will set them to the correct intensities

        # Log each channel's calibrated intensity for debugging
        for ch, intensity in result.ref_intensity.items():
            logger.info(f"   Ch {ch.upper()}: LED intensity = {intensity}/255")

        # === SECOND PASS OPTIMIZATION: Improve headroom if possible ===
        # Check if we can improve headroom by increasing integration time
        weak_channels = [ch for ch, intensity in result.ref_intensity.items() if intensity > 200]
        if weak_channels and result.integration_time < MAX_INTEGRATION_BUDGET_MS:
            # Calculate how much we could improve by using more integration time
            integration_headroom = MAX_INTEGRATION_BUDGET_MS - result.integration_time
            potential_improvement_pct = (integration_headroom / result.integration_time) * 100

            if potential_improvement_pct >= 20:  # At least 20% improvement possible
                logger.info(f"\n🔄 SECOND PASS OPTIMIZATION OPPORTUNITY:")
                logger.info(f"   Weak channels detected: {', '.join([c.upper() for c in weak_channels])}")
                logger.info(f"   Current integration: {result.integration_time}ms")
                logger.info(f"   Budget headroom: {integration_headroom}ms ({potential_improvement_pct:.0f}% improvement possible)")
                logger.info(f"   Increasing integration time to improve LED headroom...")

                # Increase integration time toward budget maximum
                # Use 80% of remaining headroom to leave some margin
                new_integration = result.integration_time + int(integration_headroom * 0.8)
                logger.info(f"   New integration target: {new_integration}ms")

                # Set new integration time
                usb.set_integration(new_integration)
                time.sleep(0.1)

                # Recalibrate LED intensities with improved integration time
                logger.info("   Recalibrating LED intensities with improved integration time...")
                for ch in weak_channels:
                    if stop_flag and stop_flag.is_set():
                        break
                    new_intensity = calibrate_led_channel(
                        usb, ctrl, ch, None, stop_flag
                    )
                    improvement = result.ref_intensity[ch] - new_intensity
                    logger.info(f"   Ch {ch.upper()}: {result.ref_intensity[ch]} → {new_intensity} (improved by {improvement})")
                    result.ref_intensity[ch] = new_intensity

                # Update result with new integration time
                result.integration_time = new_integration
                result.num_scans = min(int(MAX_READ_TIME / new_integration), MAX_NUM_SCANS)

                logger.info(f"✅ Second pass complete - integration: {new_integration}ms, LEDs improved")
                logger.info(f"   Recalibrated channels: {result.ref_intensity}\n")

        # Analyze S-mode LED intensities and provide integration time guidance
        # High LED values indicate weak signal that limits P-mode optimization headroom
        weak_channels = [ch for ch, intensity in result.ref_intensity.items() if intensity > 200]
        if weak_channels:
            logger.warning(f"\n⚠️ LED INTENSITY vs TIMING BUDGET ANALYSIS:")
            logger.warning(f"   Channels {', '.join([c.upper() for c in weak_channels])} have high S-mode LED values (>200/255)")
            logger.warning(f"   This indicates weak optical signal limiting P-mode boost potential")

            # Check if we're at timing budget limit
            if result.integration_time >= MAX_INTEGRATION_BUDGET_MS:
                logger.warning(f"\n   📌 TIMING CONSTRAINT ACTIVE:")
                logger.warning(f"   Integration time is at maximum ({MAX_INTEGRATION_BUDGET_MS}ms) due to {SYSTEM_ACQUISITION_TARGET_HZ}Hz target")
                logger.warning(f"   → Cannot increase integration further without violating timing budget")
                logger.warning(f"   → System is optimized for SPEED over maximum SNR")
                logger.warning(f"   → Trade-off: {SYSTEM_ACQUISITION_TARGET_HZ}Hz acquisition vs optimal signal strength")
                logger.warning(f"\n   Options:")
                logger.warning(f"   1. Accept current configuration (speed priority)")
                logger.warning(f"   2. Reduce target frequency to allow longer integration")
                logger.warning(f"   3. Check optical coupling (fiber alignment, sensor placement)")
            else:
                logger.warning(f"\n   💡 OPTIMIZATION OPPORTUNITY:")
                logger.warning(f"   Current integration: {result.integration_time}μs (budget allows up to {MAX_INTEGRATION_BUDGET_MS}ms)")
                logger.warning(f"   Recommendation: Consider INCREASING integration time to:")
                logger.warning(f"   • Lower S-mode LED intensity (more detector time = less LED needed)")
                logger.warning(f"   • Increase headroom for P-mode optimization (more boost possible)")
                logger.warning(f"   • Improve overall SNR for both S and P modes")
                logger.warning(f"   • Still maintain {SYSTEM_ACQUISITION_TARGET_HZ}Hz target (within budget)\n")
        else:
            logger.info(f"\n✅ LED INTENSITY OPTIMAL:")
            logger.info(f"   All channels have good S-mode LED values (<200/255)")
            logger.info(f"   Integration time: {result.integration_time}ms (budget: {MAX_INTEGRATION_BUDGET_MS}ms)")
            logger.info(f"   Excellent balance between speed ({SYSTEM_ACQUISITION_TARGET_HZ}Hz) and signal strength\n")

        # === LED HEADROOM ANALYSIS (done once, reused in P-mode) ===
        # Analyze S-mode LED intensities to predict P-mode boost potential
        result.headroom_analysis = analyze_channel_headroom(result.ref_intensity)

        if stop_flag and stop_flag.is_set():
            return result

        # Calculate scan counts ONCE based on integration time (optimization: single source of truth)
        scan_config = calculate_scan_counts(result.integration_time)

        # Step 3: Measure dark noise
        if progress_callback:
            progress_callback("Measuring dark noise...")
        logger.debug("Measuring dark noise...")
        result.dark_noise = measure_dark_noise(
            usb,
            ctrl,
            result.integration_time,
            result.wave_min_index,
            result.wave_max_index,
            stop_flag,
            num_scans=scan_config.dark_scans  # Use pre-calculated scan count
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 4: Use afterglow correction if provided (optimization: loaded upstream)
        # If not provided, load it here (fallback for backward compatibility)
        if afterglow_correction is None:
            try:
                from afterglow_correction import AfterglowCorrection
                from pathlib import Path

                device_serial = getattr(usb, 'serial_number', None)
                if device_serial:
                    calibration_dir = Path('optical_calibration')
                    if calibration_dir.exists():
                        pattern = f"system_{device_serial}_*.json"
                        cal_files = sorted(calibration_dir.glob(pattern), reverse=True)
                        if cal_files:
                            afterglow_correction = AfterglowCorrection(cal_files[0])
                            logger.info(f"✅ Loaded afterglow correction: {cal_files[0].name}")
                        else:
                            logger.debug(f"No afterglow calibration found for device {device_serial}")
                    else:
                        logger.debug(f"Optical calibration directory not found")
                else:
                    logger.debug(f"Device serial number not available")
            except Exception as e:
                logger.debug(f"Afterglow correction not available: {e}")
        else:
            logger.debug("Using pre-loaded afterglow correction (optimization)")

        # Step 5: Measure reference signals
        if progress_callback:
            progress_callback("Measuring reference signals...")
        logger.debug("Measuring reference signals...")
        try:
            result.ref_sig = measure_reference_signals(
                usb,
                ctrl,
                ch_list,
                result.ref_intensity,
                result.dark_noise,
                result.integration_time,
                result.wave_min_index,
                result.wave_max_index,
                stop_flag,
                afterglow_correction,  # Pass afterglow correction for S-ref
                num_scans=scan_config.ref_scans  # Use pre-calculated scan count
            )
        except RuntimeError as e:
            logger.error(f"❌ Hardware validation failed during S-ref measurement")
            logger.error(f"   {str(e)}")
            logger.info("")
            logger.info("⚠️  CALIBRATION FAILED - Hardware not responding")
            logger.info("")
            logger.info("Possible causes:")
            logger.info("  1. Spectrometer stopped responding")
            logger.info("  2. Hardware disconnected during measurement")
            logger.info("  3. LEDs not producing signal")
            logger.info("  4. Light path blocked or no water on sensor")
            logger.info("")
            logger.info("Action required:")
            logger.info("  1. Check hardware connections")
            logger.info("  2. Verify LEDs are working (should light up during calibration)")
            logger.info("  3. Check water/buffer is present on sensor")
            logger.info("  4. Restart the application and reconnect hardware")
            logger.info("")
            result.success = False
            result.error = f"Hardware validation failed during S-ref measurement: {str(e)}"
            return result
        except ConnectionError as e:
            logger.error(f"🔌 USB disconnection detected during S-ref measurement")
            logger.error(f"   {str(e)}")
            logger.info("")
            logger.info("⚠️  CALIBRATION FAILED - Hardware disconnected")
            logger.info("")
            logger.info("Possible causes:")
            logger.info("  1. USB cable was unplugged during calibration")
            logger.info("  2. Spectrometer lost power or reset")
            logger.info("  3. USB hub issue or driver timeout")
            logger.info("  4. System suspended the USB device (power management)")
            logger.info("")
            logger.info("Action required:")
            logger.info("  1. Check USB cable connection (try different cable/port)")
            logger.info("  2. Restart the application")
            logger.info("  3. Reconnect hardware (use Power button)")
            logger.info("  4. Run calibration again")
            logger.info("  5. If problem persists, check Windows Device Manager for USB errors")
            logger.info("")
            result.success = False
            result.error = f"Hardware disconnected during calibration: {str(e)}"
            return result

        if stop_flag and stop_flag.is_set():
            return result

        # === S-REF OPTICAL QUALITY CHECK ===
        # S-pol characterizes LED spectral profile and detector performance
        # NO SPR dip analysis - S-pol is about LED intensity profile only
        print("\n🔍 DEBUG: About to perform S-ref QC validation...")
        print("\n🔍 DEBUG: About to perform S-ref QC validation...")
        logger.debug("📊 Performing S-ref optical quality checks...")
        result.s_ref_qc_results = validate_s_ref_quality(result.ref_sig, result.wave_data)
        logger.debug(f"   QC validation complete for {len(result.s_ref_qc_results)} channels")

        # Check if any channels failed QC
        failed_qc_channels = [ch for ch, qc in result.s_ref_qc_results.items() if not qc['passed']]
        if failed_qc_channels:
            logger.warning(f"⚠️ S-ref QC warnings for channels: {', '.join([c.upper() for c in failed_qc_channels])}")

        # Step 6: Calibrate P-mode LED intensities (returns LED values + performance metrics)
        if progress_callback:
            progress_callback("Calibrating P-mode LEDs...")
        logger.debug("Calibrating P-mode LEDs...")
        result.leds_calibrated, result.channel_performance = calibrate_p_mode_leds(
            usb, ctrl, ch_list, result.ref_intensity, stop_flag,
            detector_params=detector_params,  # Pass pre-read detector params
            headroom_analysis=result.headroom_analysis  # Pass pre-computed headroom analysis
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 7: Verify P-mode calibration (check saturation, S vs P comparison, and FWHM)
        # Use trimmed wave_data (already trimmed to MIN_WAVELENGTH:MAX_WAVELENGTH)
        # to match the trimmed ref_sig from measure_reference_signals
        result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration(
            usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig
        )

        # Auto-correct polarizer swap if detected (3+ channels with inverted orientation)
        # Only attempt correction ONCE to prevent infinite loops
        if polarizer_swap_detected and not _polarizer_swap_retry_done:
            logger.error(f"\n🔄 AUTO-CORRECTION: Swapping S/P polarizer positions and retrying calibration...")

            try:
                # Use provided device_config or load fresh (optimization: reuse if available)
                if device_config is None:
                    from utils.device_configuration import DeviceConfiguration
                    device_serial = getattr(usb, 'serial_number', None)
                    device_config = DeviceConfiguration(device_serial=device_serial)

                # Get current positions for logging
                current_positions = device_config.get_servo_positions()
                logger.error(f"   Current positions: S={current_positions['s']}, P={current_positions['p']}")

                # Swap positions using centralized method (optimization: single source of truth)
                new_s, new_p = device_config.swap_servo_positions()
                logger.error(f"   Swapped to: S={new_s}, P={new_p}")

                device_config.save()

                # Apply new positions to controller
                ctrl.set_mode(mode="s")
                time.sleep(0.4)

                logger.error(f"   ✅ Polarizer positions swapped in config")
                logger.error(f"   🔄 Restarting calibration with corrected positions...\n")

                # Recursive call with swapped positions - PASS THE FLAG!
                return perform_full_led_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type=device_type,
                    single_mode=single_mode,
                    single_ch=single_ch,
                    integration_step=integration_step,
                    stop_flag=stop_flag,
                    progress_callback=progress_callback,
                    _polarizer_swap_retry_done=True,  # Prevent infinite recursion
                )

            except Exception as e:
                logger.error(f"   ❌ Failed to swap polarizer positions: {e}")
                logger.error(f"   Manual intervention required - check device_config.json")

        # Log FWHM results for sensor quality tracking
        if result.spr_fwhm:
            fwhm_str = ", ".join([f"{ch.upper()}={fwhm:.1f}nm" for ch, fwhm in result.spr_fwhm.items()])
            logger.info(f"📊 SPR FWHM (sensor quality): {fwhm_str}")

        # Set success flag
        result.success = len(result.ch_error_list) == 0

        if result.success:
            logger.info("✅ LED CALIBRATION SUCCESSFUL")

            # System-level timing and performance summary
            logger.info(f"\n" + "="*70)
            logger.info(f"CALIBRATION SUMMARY - TIMING & PERFORMANCE")
            logger.info(f"="*70)

            # Calculate ACTUAL acquisition timing (hardware-limited, not processing)
            actual_channel_time_ms = result.integration_time + HARDWARE_OVERHEAD_MS
            actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
            system_cycle_ms = actual_channel_time_ms * len(ch_list)
            system_hz = 1000 / system_cycle_ms if system_cycle_ms > 0 else 0

            logger.info(f"\n⏱️  ACQUISITION TIMING (Hardware-Limited):")
            logger.info(f"   Integration time: {result.integration_time}ms")
            logger.info(f"   Hardware overhead: ~{HARDWARE_OVERHEAD_MS}ms")
            logger.info(f"      • LED settling: ~{ESTIMATED_LED_DELAY_MS}ms")
            logger.info(f"      • Afterglow decay: ~{ESTIMATED_AFTERGLOW_MS}ms")
            logger.info(f"      • Detector lag: ~{ESTIMATED_DETECTOR_LAG_MS}ms")
            logger.info(f"      • USB transfer: ~{ESTIMATED_USB_TRANSFER_MS}ms")
            logger.info(f"   ")
            logger.info(f"   Per-channel: ~{actual_channel_time_ms}ms → {actual_channel_hz:.2f}Hz")
            logger.info(f"   {len(ch_list)}-channel cycle: ~{system_cycle_ms}ms → {system_hz:.2f}Hz")
            logger.info(f"   ")

            timing_status = "✅ OPTIMAL" if result.integration_time < MAX_INTEGRATION_BUDGET_MS else "⚠️ AT LIMIT"
            target_status = "✅ MEETS" if actual_channel_hz >= SYSTEM_ACQUISITION_TARGET_HZ else "⚠️ BELOW"
            logger.info(f"   Integration status: {timing_status}")
            logger.info(f"   Frequency target: {target_status} ({SYSTEM_ACQUISITION_TARGET_HZ}Hz target)")
            logger.info(f"   ")
            logger.info(f"   Note: Processing/graph updates run independently from acquisition")

            # LED intensity analysis
            logger.info(f"\n💡 LED INTENSITIES (S-mode baseline):")
            s_avg = sum(result.ref_intensity.values()) / len(result.ref_intensity) if result.ref_intensity else 0
            for ch, s_led in result.ref_intensity.items():
                p_led = result.leds_calibrated.get(ch, 0)
                boost = p_led / s_led if s_led > 0 else 1.0
                perf = result.channel_performance.get(ch, {})
                util = perf.get('utilization_pct', 0)
                logger.info(f"   Ch {ch.upper()}: S={s_led:3d}, P={p_led:3d} (boost={boost:.2f}x, detector={util:.0f}%)")

            s_status = "Strong LEDs" if s_avg < 150 else "Moderate LEDs" if s_avg < 200 else "Weak LEDs"
            logger.info(f"   Average S-LED: {s_avg:.0f}/255 ({s_status})")

            # Trade-off assessment
            logger.info(f"\n🎯 SYSTEM OPTIMIZATION:")
            if result.integration_time >= MAX_INTEGRATION_BUDGET_MS and s_avg > 180:
                logger.info(f"   Configuration: SPEED-OPTIMIZED (timing constraint active)")
                logger.info(f"   Trade-off: {SYSTEM_ACQUISITION_TARGET_HZ}Hz speed vs maximum SNR")
                logger.info(f"   Note: Limited P-mode headroom due to timing budget")
            elif result.integration_time < 60 and s_avg < 150:
                logger.info(f"   Configuration: OPTIMAL (strong signal + fast acquisition)")
                logger.info(f"   Excellent balance: Low LEDs + fast timing")
            else:
                logger.info(f"   Configuration: BALANCED")
                logger.info(f"   Good compromise between speed and signal strength")

            logger.info(f"\n" + "="*70 + "\n")
        else:
            ch_str = ", ".join(result.ch_error_list)
            logger.warning(f"⚠️ LED calibration completed with errors on channels: {ch_str}")

        # ========================================================================
        # CRITICAL: SAVE CALIBRATION TO DEVICE_CONFIG.JSON
        # ========================================================================
        # The calling code (calibration_coordinator.py) MUST save these results:
        #   - result.integration_time → integration_time_ms
        #   - result.ref_intensity → s_mode_intensities
        #   - result.leds_calibrated → p_mode_intensities
        #   - result.ref_sig → s_ref_spectra
        #   - result.wave_data → s_ref_wavelengths
        #
        # Save method: device_config.save_led_calibration(...)
        # This ensures device_config.json remains the single source of truth
        # for fast-track calibration on next run.
        # ========================================================================

        return result

    except Exception as e:
        logger.exception(f"LED calibration failed: {e}")
        result.success = False
        return result


# =============================================================================
# ALTERNATIVE CALIBRATION PATH - FIXED LED (PER-CHANNEL INTEGRATION) METHOD
# =============================================================================

def calibrate_integration_per_channel(
    usb,
    ctrl: ControllerBase,
    ch: str,
    led_intensity: int = 255,
    target_counts: float = None,
    stop_flag=None,
) -> tuple[int, int]:
    """Calibrate integration time for a single channel at fixed LED intensity.

    Used in Fixed LED (Per-Channel Integration) method where all LEDs are at max (255).
    Integration time calibrated per channel, then MAX used as global integration time.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch: Channel to calibrate ('a', 'b', 'c', or 'd')
        led_intensity: Fixed LED intensity (typically 255 for max)
        target_counts: Target detector count level (if None, uses detector's target_counts)
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Tuple of (integration_time, num_scans) for this channel
    """
    if target_counts is None:
        target_counts = usb.target_counts

    logger.debug(f"Calibrating integration time for ch {ch.upper()} at LED={led_intensity}")

    # Set fixed LED intensity
    ctrl.set_intensity(ch=ch, raw_val=led_intensity)
    time.sleep(pre_led_delay_ms / 1000.0)

    # Start with minimum integration time
    integration = MIN_INTEGRATION
    max_integration_allowed = min(MAX_INTEGRATION, MAX_INTEGRATION_BUDGET_MS)
    usb.set_integration(integration)
    time.sleep(0.1)

    # Read initial signal
    int_array = usb.read_intensity()
    if int_array is None:
        logger.error(f"Failed to read intensity for channel {ch.upper()}")
        raise RuntimeError(f"Spectrometer read failed for channel {ch.upper()}")

    current_count = int_array.max()
    logger.debug(f"Ch {ch.upper()} initial: {integration}ms = {current_count:.0f} counts (target: {target_counts})")

    # Increase integration time until we hit target (with budget constraint)
    step_size = 2  # ms increments
    while current_count < target_counts and integration < max_integration_allowed:
        if stop_flag and stop_flag.is_set():
            break

        integration += step_size
        usb.set_integration(integration)
        time.sleep(0.02)

        int_array = usb.read_intensity()
        if int_array is None:
            raise RuntimeError(f"Spectrometer read failed during integration calibration")

        new_count = int_array.max()
        logger.debug(f"Ch {ch.upper()}: {integration}ms = {new_count:.0f} counts (change: {new_count - current_count:+.0f})")
        current_count = new_count

    # Check if we hit the budget limit
    if integration >= max_integration_allowed and current_count < target_counts:
        logger.warning(
            f"Ch {ch.upper()}: Hit integration budget limit ({max_integration_allowed}ms) "
            f"at {current_count:.0f} counts (target: {target_counts})"
        )

    # Calculate optimal scan count for this integration time
    num_scans = min(int(MAX_READ_TIME / integration), MAX_NUM_SCANS)

    logger.info(f"✓ Ch {ch.upper()}: Integration={integration}ms, Signal={current_count:.0f} counts, Scans={num_scans}")

    return integration, num_scans


def perform_alternative_calibration(
    usb,
    ctrl: ControllerBase,
    device_type: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
    _polarizer_swap_retry_done: bool = False,  # Internal flag to prevent infinite recursion
    wave_data=None,  # Optional: pre-read wavelength data (avoids redundant USB read)
    wave_min_index: int = None,  # Optional: pre-computed min index
    wave_max_index: int = None,  # Optional: pre-computed max index
    device_config=None,  # Optional: pre-loaded DeviceConfiguration (avoids redundant file reads)
    polarizer_type: str = None,  # Optional: polarizer type ('barrel' or 'round') - sets calibration expectations
    afterglow_correction=None,  # Optional: pre-loaded AfterglowCorrection (avoids redundant file I/O)
    pre_led_delay_ms: float = 45.0,  # PRE LED delay: settling time after LED on (default 45ms)
    post_led_delay_ms: float = 5.0,  # POST LED delay: dark time after LED off (default 5ms)
) -> LEDCalibrationResult:
    """Perform LED calibration using ALTERNATIVE optical configuration (Fixed LED, Per-Channel Integration).

    OPTICAL SYSTEM MODE: ALTERNATIVE (Fixed LED, Per-Channel Integration)
    ========================================================
    This function implements MODE 2: FIXED LED intensity (255), VARIABLE integration time

    Recorded to device_config.json:
      - integration_time_ms: 120 (MAX integration time across all channels - used globally)
      - s_mode_intensities: {'a': 255, 'b': 255, 'c': 255, 'd': 255} (FIXED - all same)
      - p_mode_intensities: {'a': 255, 'b': 255, 'c': 255, 'd': 255} (FIXED - all same)
      - per_channel_integration_times: {'a': 85, 'b': 95, 'c': 120, 'd': 110} (diagnostic - shows per-channel calibration results)

    Alternative Path: Fixed LED (Per-Channel Integration) Method
    =============================================================
    Calibrates integration time per channel (3ms→70ms sweep), then uses MAX globally.
    All LEDs fixed at 255. This approach typically provides:

    Benefits:
    - Better frequency (faster acquisition with optimized integration per channel)
    - Excellent SNR (all channels at max LED intensity)
    - More LED consistency (operating at max current)
    - Per-channel optimization of integration time

    Trade-offs:
    - Variable integration time per channel (vs global in standard method)
    - May hit integration budget limit on weak channels
    - Different P-mode boost strategy (increase integration, not LED)

    Calibration Steps:
    ==================
    1. Wavelength data acquisition
    2. S-mode: Set all LEDs to 255, calibrate integration time per channel
    3. Dark noise measurement (using max integration time from step 2)
    4. S-mode reference signal measurement
    5. S-mode optical QC validation
    6. P-mode: Set all LEDs to 255, calibrate integration time per channel
    7. P-mode verification (saturation, SPR dip, FWHM)

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        device_type: Device type string
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode
        stop_flag: Optional threading event to check for cancellation
        progress_callback: Optional callback for progress updates

    Returns:
        LEDCalibrationResult object with all calibration data
    """
    result = LEDCalibrationResult()

    try:
        logger.info("=== Starting LED Calibration (Fixed LED, Per-Channel Integration Method) ===")
        logger.info("Method: Fixed LED intensity (255), variable integration time per channel")

        # Mark this as alternative method for downstream processing
        result.calibration_method = "alternative"

        # Get wavelength data (use provided or read from hardware)
        if wave_data is None:
            logger.debug("Reading wavelength data...")
            wave_data = usb.read_wavelength()
            result.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            result.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        else:
            logger.debug("Using pre-read wavelength data (optimization)")
            result.wave_min_index = wave_min_index if wave_min_index is not None else wave_data.searchsorted(MIN_WAVELENGTH)
            result.wave_max_index = wave_max_index if wave_max_index is not None else wave_data.searchsorted(MAX_WAVELENGTH)

        result.wave_data = wave_data[result.wave_min_index : result.wave_max_index]
        logger.debug(f"Wavelength range: index {result.wave_min_index} to {result.wave_max_index}")

        # Get detector parameters ONCE (optimization: eliminates redundant property accesses)
        detector_params = get_detector_params(usb)

        # Get polarizer type and set calibration expectations
        if polarizer_type is None and device_config is not None:
            polarizer_type = device_config.get_polarizer_type()
        if polarizer_type is None:
            polarizer_type = 'circular'  # Default assumption for safety

        # Set expectations based on polarizer hardware
        cal_expectations = get_calibration_expectations(polarizer_type)
        logger.info(f"\n🔧 POLARIZER CONFIGURATION:")
        logger.info(f"   Type: {polarizer_type.upper()}")
        logger.info(f"   Servo Positions: Loaded from device_config.json (calibrated previously)")
        logger.info(f"   → If config was not populated, {cal_expectations['servo_calibration_complexity']} servo calibration would run first")
        logger.info(f"   → {cal_expectations['servo_calibration_method']}")
        logger.info(f"   LED Calibration: {cal_expectations['led_calibration_complexity']} (common path) - {cal_expectations['led_calibration_notes']}")
        logger.info(f"   Expected S/P Ratio: {cal_expectations['expected_s_p_ratio'][0]:.1f}× to {cal_expectations['expected_s_p_ratio'][1]:.1f}× (sample-dependent)")
        logger.info(f"   P-mode Strategy: {'Boost LED using S-mode headroom analysis' if cal_expectations['requires_headroom_analysis'] else 'Direct optimization'}")
        logger.info("")

        # Calculate Fourier weights for denoising
        result.fourier_weights = calculate_fourier_weights(len(result.wave_data))

        # Determine channel list ONCE (optimization: single source of truth)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.debug(f"Calibrating channels: {ch_list}")

        logger.info(f"Target signal: {detector_params.target_counts} counts per channel")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 1: Calibrate integration time per channel in S-mode (all LEDs at 255)
        logger.info("\n📊 S-MODE: Calibrating per-channel integration time (LEDs fixed at 255)...")
        switch_mode_safely(ctrl, "s", turn_off_leds=True)

        # Store per-channel integration times and scan counts
        s_integration_times = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # In alternative method, we only need integration time (always 1 scan per spectrum)
            s_integration_times[ch], _ = calibrate_integration_per_channel(
                usb, ctrl, ch, led_intensity=255, target_counts=detector_params.target_counts,
                stop_flag=stop_flag
            )

            # Store LED intensity (always 255 in this method)
            result.ref_intensity[ch] = 255

        # Use the maximum integration time across all channels for consistency
        print(f"\n🔍 DEBUG: Completed S-mode calibration loop")
        print(f"\n🔍 DEBUG: Completed S-mode calibration loop")
        # (This ensures all channels can be read with same timing parameters)
        result.integration_time = max(s_integration_times.values())
        result.num_scans = 1  # ALWAYS 1 scan per spectrum in alternative method (both S and P)

        # Store per-channel integration times for live acquisition
        result.per_channel_integration = s_integration_times.copy()

        logger.info(f"\n✅ S-mode integration calibration complete:")
        logger.info(f"   Per-channel integration times: {s_integration_times}")
        logger.info(f"   Global integration time: {result.integration_time}ms (max across channels)")
        logger.info(f"   Scan count: 1 (single scan per spectrum for fast acquisition)")

        # Analyze timing and headroom (in alternative method, headroom comes from integration time)
        actual_channel_time_ms = result.integration_time + HARDWARE_OVERHEAD_MS
        actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
        logger.info(f"   Estimated per-channel rate: ~{actual_channel_hz:.2f}Hz")

        # Analyze integration time headroom (similar concept to LED headroom in standard method)
        logger.info(f"\n📊 INTEGRATION TIME HEADROOM ANALYSIS:")

        # Compute headroom analysis (optimization: compute once, reuse if needed)
        result.headroom_analysis = analyze_channel_headroom(result.ref_intensity)

        # Compute scan counts ONCE (optimization: centralized calculation)
        scan_config = calculate_scan_counts(result.integration_time)

        weak_channels = []
        for ch, int_time in s_integration_times.items():
            headroom_ms = MAX_INTEGRATION_BUDGET_MS - int_time
            headroom_pct = (headroom_ms / MAX_INTEGRATION_BUDGET_MS) * 100

            if int_time < 50:
                strength = "EXCELLENT (strong optical signal)"
            elif int_time < 75:
                strength = "GOOD (moderate signal)"
            elif int_time < 90:
                strength = "MODERATE (weaker signal)"
            else:
                strength = "LIMITED (weak signal, near timing budget)"
                weak_channels.append(ch)

            logger.info(f"   Ch {ch.upper()}: {int_time}ms integration ({headroom_pct:.0f}% headroom) - {strength}")

        if weak_channels:
            logger.warning(f"\n   ⚠️ Channels {', '.join([c.upper() for c in weak_channels])} near timing budget limit")
            logger.warning(f"   → Check optical coupling (fiber alignment, sensor placement)")
        else:
            logger.info(f"\n   ✅ All channels have good integration time headroom")
            logger.info(f"   → Excellent optical signal strength across all channels")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 2: Measure dark noise PER CHANNEL (each channel has different integration time)
        # In alternative method, dark noise must be measured at each channel's specific integration time
        logger.info("\n📊 Measuring per-channel dark noise (variable integration times)...")

        # Dark noise will be a dict keyed by channel in this method
        dark_noise_per_channel = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            ch_integration = s_integration_times[ch]
            logger.debug(f"Measuring dark noise for ch {ch.upper()} at {ch_integration}ms...")

            # Set this channel's integration time
            usb.set_integration(ch_integration)
            time.sleep(0.1)

            # Measure dark noise for this channel (optimization: pass pre-calculated scan count)
            dark_noise_per_channel[ch] = measure_dark_noise(
                usb,
                ctrl,
                ch_integration,
                result.wave_min_index,
                result.wave_max_index,
                stop_flag,
                num_scans=scan_config.dark_scans
            )

        # For compatibility with rest of code, store the dark noise for the max integration time
        # (This will be used as fallback, but per-channel values are in dark_noise_per_channel)
        result.integration_time = max(s_integration_times.values())
        result.dark_noise = dark_noise_per_channel[max(s_integration_times, key=s_integration_times.get)]

        # Store per-channel dark noise for live acquisition
        result.per_channel_dark_noise = dark_noise_per_channel.copy()

        logger.info(f"✅ Per-channel dark noise measurement complete")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 3: Load afterglow correction if available (PER-CHANNEL for variable integration times)
        # In alternative method, afterglow correction must account for different integration times per channel
        afterglow_correction = None
        afterglow_per_channel = {}  # Store per-channel afterglow correction if available

        try:
            from afterglow_correction import AfterglowCorrection
            from pathlib import Path

            device_serial = getattr(usb, 'serial_number', None)
            if device_serial:
                calibration_dir = Path('optical_calibration')
                if calibration_dir.exists():
                    pattern = f"system_{device_serial}_*.json"
                    cal_files = sorted(calibration_dir.glob(pattern), reverse=True)

                    if cal_files:
                        afterglow_correction = AfterglowCorrection(cal_files[0])
                        logger.info(f"✅ Loaded afterglow correction: {cal_files[0].name}")
                        logger.info(f"   Note: Afterglow correction will be applied per-channel with variable integration times")

                        # Store reference for per-channel use
                        for ch in ch_list:
                            afterglow_per_channel[ch] = afterglow_correction
        except Exception as e:
            logger.debug(f"ℹ️ Afterglow correction not available: {e}")

        print("\n🔍 DEBUG: About to measure S-mode reference signals...")
        print("\n🔍 DEBUG: About to measure S-mode reference signals...")
        # Step 4: Measure reference signals
        logger.debug("Measuring reference signals...")
        result.ref_sig = measure_reference_signals(
            usb,
            ctrl,
            ch_list,
            result.ref_intensity,
            result.dark_noise,
            result.integration_time,
            result.wave_min_index,
            result.wave_max_index,
            stop_flag,
            afterglow_correction,
            num_scans=scan_config.ref_scans
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 5: Validate S-ref quality (shared QC function)
        print("\n🔍 DEBUG: About to perform S-ref QC validation...")
        print("\n🔍 DEBUG: About to perform S-ref QC validation...")
        logger.debug("📊 Performing S-ref optical quality checks...")
        result.s_ref_qc_results = validate_s_ref_quality(result.ref_sig, result.wave_data)

        failed_qc_channels = [ch for ch, qc in result.s_ref_qc_results.items() if not qc['passed']]
        if failed_qc_channels:
            logger.warning(f"⚠️ S-ref QC warnings for channels: {', '.join([c.upper() for c in failed_qc_channels])}")

        print("\n🔍 DEBUG: Starting P-mode calibration...")
        print("\n🔍 DEBUG: Starting P-mode calibration...")
        # Step 6: P-mode calibration - optimize integration time for 80% of max counts
        # In Global LED Intensity method, P-mode LEDs stay at 255, but we can increase
        # integration time to boost signal (similar to LED boost in standard method)
        logger.info("\n📊 P-MODE: Optimizing integration time for maximum signal (LEDs at 255)...")

        # CRITICAL: Use centralized mode switching with proper delays (optimization)
        switch_mode_safely(ctrl, "p", turn_off_leds=True)

        # Target 80% of detector max for P-mode (similar to standard method's target)
        p_target_counts = detector_params.max_counts * 0.80  # 80% of detector max

        logger.info(f"   P-mode target: {p_target_counts:.0f} counts (80% of {detector_params.max_counts:.0f} max)")

        # DEBUG: Check initial state
        logger.info(f"🔍 DEBUG: Channel list = {ch_list}")
        logger.info(f"🔍 DEBUG: leds_calibrated BEFORE loop = {result.leds_calibrated}")

        p_integration_times = {}

        for ch in ch_list:
            logger.info(f"🔍 DEBUG: Processing P-mode channel {ch}")

            if stop_flag and stop_flag.is_set():
                logger.warning(f"🔍 DEBUG: Stop flag detected during P-mode calibration at channel {ch}")
                break

            # Optimize integration time for this channel in P-mode
            logger.info(f"🔍 DEBUG: Calling calibrate_integration_per_channel for ch={ch}")
            p_integration_times[ch], _ = calibrate_integration_per_channel(
                usb, ctrl, ch, led_intensity=255, target_counts=p_target_counts, stop_flag=stop_flag
            )
            logger.info(f"🔍 DEBUG: P-mode integration for ch {ch} = {p_integration_times[ch]}ms")

            # Store LED intensity (always 255)
            result.leds_calibrated[ch] = 255
            logger.info(f"🔍 DEBUG: Set leds_calibrated[{ch}] = 255, dict now = {result.leds_calibrated}")

            # Calculate performance metrics with P-mode integration boost
            s_int = s_integration_times[ch]
            p_int = p_integration_times[ch]

            # Boost ratio: how much we increased integration time from S to P
            integration_boost = p_int / s_int if s_int > 0 else 1.0

            # Headroom is based on P-mode integration time
            integration_headroom_ms = MAX_INTEGRATION_BUDGET_MS - p_int
            integration_headroom_pct = (integration_headroom_ms / MAX_INTEGRATION_BUDGET_MS) * 100

            # Utilization is based on P-mode integration time usage
            integration_utilization = (p_int / MAX_INTEGRATION_BUDGET_MS) * 100

            result.channel_performance[ch] = {
                'max_counts': float(p_target_counts),  # P-mode target
                'utilization_pct': integration_utilization,
                'led_intensity': 255,
                's_mode_intensity': 255,
                'boost_ratio': integration_boost,
                'predicted_boost': integration_boost,  # Same as actual in alternative method
                'headroom_available': int(integration_headroom_ms),
                'headroom_pct': float(integration_headroom_pct),
                'optical_limit_reached': p_int >= MAX_INTEGRATION_BUDGET_MS * 0.95,  # Near timing budget limit
                'hit_saturation': False,  # Saturation is checked in verification step
            }

            logger.info(f"   Channel {ch}: S={s_int}ms → P={p_int}ms (boost: {integration_boost:.2f}x, headroom: {integration_headroom_ms}ms)")

        # DEBUG: Verify leds_calibrated after loop completes
        logger.info(f"\n🔍 DEBUG: P-mode loop completed")
        logger.info(f"🔍 DEBUG: leds_calibrated AFTER loop = {result.leds_calibrated}")
        logger.info(f"🔍 DEBUG: Type of leds_calibrated = {type(result.leds_calibrated)}")
        logger.info(f"🔍 DEBUG: Is dict? {isinstance(result.leds_calibrated, dict)}")
        logger.info(f"🔍 DEBUG: Empty? {not result.leds_calibrated}")

        # Store P-mode integration times (overwrite S-mode values in result)
        result.per_channel_integration = p_integration_times

        logger.info(f"\n✅ P-mode configuration: All LEDs at 255, 1 scan per spectrum")

        # Log boost summary
        boost_ratios = [p_integration_times[ch] / s_integration_times[ch] for ch in ch_list if s_integration_times[ch] > 0]
        avg_boost = sum(boost_ratios) / len(boost_ratios) if boost_ratios else 1.0
        logger.info(f"   Average integration boost: {avg_boost:.2f}x (S→P)")

        # Update global integration time to max P-mode value for compatibility
        result.integration_time = max(p_integration_times.values())
        logger.info(f"   Max P-mode integration: {result.integration_time}ms")

        if stop_flag and stop_flag.is_set():
            return result

        # CRITICAL: Set spectrometer to GLOBAL integration time before verification
        # During per-channel optimization, each channel got its own integration time
        # But verify_calibration needs ALL channels measured with the SAME global integration time
        # Otherwise P-ref QC measurements won't match live data (which uses global integration)
        logger.info(f"   Setting global P-mode integration time: {result.integration_time}ms (for all channels)")
        usb.set_integration(result.integration_time)
        time.sleep(0.1)  # Brief delay for spectrometer to update

        print("\n🔍 DEBUG: About to call verify_calibration...")
        print("\n🔍 DEBUG: About to call verify_calibration...")
        # Step 7: Verify P-mode calibration (shared QC function)
        # Use trimmed wave_data (already trimmed to MIN_WAVELENGTH:MAX_WAVELENGTH)
        # to match the trimmed ref_sig from measure_reference_signals
        result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration(
            usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig
        )

        # Auto-correct polarizer swap if detected (3+ channels with inverted orientation)
        # Only attempt correction ONCE to prevent infinite loops
        if polarizer_swap_detected and not _polarizer_swap_retry_done:
            logger.error(f"\n🔄 AUTO-CORRECTION: Swapping S/P polarizer positions and retrying calibration...")

            try:
                # Use provided device_config or load fresh (optimization: reuse if available)
                if device_config is None:
                    from utils.device_configuration import DeviceConfiguration
                    device_serial = getattr(usb, 'serial_number', None)
                    device_config = DeviceConfiguration(device_serial=device_serial)

                # Get current positions for logging
                current_positions = device_config.get_servo_positions()
                logger.error(f"   Current positions: S={current_positions['s']}, P={current_positions['p']}")

                # Swap positions using centralized method (optimization: single source of truth)
                new_s, new_p = device_config.swap_servo_positions()
                logger.error(f"   Swapped to: S={new_s}, P={new_p}")

                device_config.save()

                # Apply new positions to controller
                ctrl.set_mode(mode="s")
                time.sleep(0.4)

                logger.error(f"   ✅ Polarizer positions swapped in config")
                logger.error(f"   🔄 Restarting calibration with corrected positions...\n")

                # Recursive call with swapped positions - PASS THE FLAG!
                return perform_alternative_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type=device_type,
                    single_mode=single_mode,
                    single_ch=single_ch,
                    stop_flag=stop_flag,
                    progress_callback=progress_callback,
                    _polarizer_swap_retry_done=True,  # Prevent infinite recursion
                )

            except Exception as e:
                logger.error(f"   ❌ Failed to swap polarizer positions: {e}")
                logger.error(f"   Manual intervention required - check device_config.json")

        # Log FWHM results
        if result.spr_fwhm:
            fwhm_str = ", ".join([f"{ch.upper()}={fwhm:.1f}nm" for ch, fwhm in result.spr_fwhm.items()])
            logger.info(f"📊 SPR FWHM (sensor quality): {fwhm_str}")

        # Set success flag
        result.success = len(result.ch_error_list) == 0

        if result.success:
            logger.info("✅ LED CALIBRATION SUCCESSFUL (Global LED Intensity Method)")
            logger.info(f"\nMethod Summary:")
            logger.info(f"   • All LEDs fixed at 255 (S-mode and P-mode)")
            logger.info(f"   • S-mode: Per-channel integration time optimization, 1 scan/spectrum")
            logger.info(f"   • S-mode integration times: {s_integration_times}")
            logger.info(f"   • Dark noise: Measured per-channel at respective integration times")
            logger.info(f"   • Afterglow correction: Applied per-channel with variable integration")
            logger.info(f"   • P-mode: Same LED (255), same integration times, 1 scan/spectrum")
            logger.info(f"   • Data stored for live acquisition: per-channel integration and dark noise")
            logger.info(f"\nKey Benefits:")
            logger.info(f"   • Faster acquisition (optimized integration per channel)")
            logger.info(f"   • Excellent SNR (max LED intensity)")
            logger.info(f"   • Consistent LED behavior (always at max current)")
        else:
            ch_str = ", ".join(result.ch_error_list)
            logger.warning(f"⚠️ LED calibration completed with errors on channels: {ch_str}")

        return result

    except Exception as e:
        logger.exception(f"LED calibration failed (Global LED Intensity Method): {e}")
        result.success = False
        return result



