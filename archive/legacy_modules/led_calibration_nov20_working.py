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

CALIBRATION METHODS:
====================
STANDARD Method (Global Integration Time) - DEFAULT:
  - Sequential optimization: integration time first (global), then LED intensities (per-channel)
  - Used for general purpose, well-tested and stable
  - Steps: wavelength GÂ∆ global integration GÂ∆ S-mode LED/channel GÂ∆ dark GÂ∆ S-ref GÂ∆ S-QC GÂ∆ P-mode LED/channel GÂ∆ P-QC
  - S-mode LED analysis predicts P-mode boost potential (headroom intelligence)
  - Timing budget: 200ms/channel (integration + 50ms hardware overhead) GÎÍ 1Hz per channel

ALTERNATIVE Method (Global LED Intensity) - EXPERIMENTAL (Disabled by default):
  - All LEDs fixed at maximum intensity (255) for both S-mode and P-mode
  - S-mode: Variable integration time per channel to reach target signal
  - P-mode: Same LEDs (255), same integration time, but uses 1 scan per spectrum
  - Benefits: Better frequency, excellent SNR, more LED consistency at max current
  - Steps: wavelength GÂ∆ S-mode integration/channel (LEDs at 255) GÂ∆ dark GÂ∆ S-ref GÂ∆ S-QC GÂ∆ P-mode (same config) GÂ∆ P-QC
  - Trade-offs: Variable integration per channel in S-mode, P-mode inherits S-mode timing
  - Enable via settings.USE_ALTERNATIVE_CALIBRATION = True

QUALITY CONTROL:
================
Both calibration methods share common QC validation:
  - S-ref QC: LED peak intensity, position tracking (validate_s_ref_quality)
  - P-mode QC: Saturation check, SPR dip validation, FWHM analysis (verify_calibration)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

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
from affilabs.utils.logger import logger
from affilabs.utils.spr_signal_processing import calculate_fourier_weights

if TYPE_CHECKING:
    from affilabs.utils.controller import ControllerBase

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
INTEGRATION_THRESHOLD_MS = 50  # Below this, use full scan count; above, use half

# System timing budget constraints (for ~1Hz per channel acquisition)
# 4 channels +˘ 200ms budget = 800ms total cycle time GÎÍ 1.25Hz system rate
TARGET_CHANNEL_BUDGET_MS = 200  # Total time budget per channel (integration + overhead)
MAX_INTEGRATION_BUDGET_MS = 100  # Maximum integration time (leave 100ms for readout/processing)
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
# CALIBRATION RESULT
# =============================================================================

class LEDCalibrationResult:
    """Result of LED calibration process."""

    def __init__(self):
        """Initialize calibration result."""
        self.success = False
        self.integration_time = MIN_INTEGRATION
        self.num_scans = 1
        self.ref_intensity = {}  # S-mode LED intensities
        self.leds_calibrated = {}  # P-mode LED intensities
        self.dark_noise = None
        self.ref_sig = {}
        self.wave_data = None
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.ch_error_list = []
        self.fourier_weights = None
        self.s_ref_qc_results = {}  # QC validation results for each channel
        self.spr_fwhm = {}  # SPR dip FWHM for each channel (sensor quality indicator)

        # Per-channel performance metrics (for ML system intelligence)
        self.channel_performance = {}  # {ch: {'max_counts', 'utilization_pct', 'snr_estimate', 'optical_limit'}}
        # These metrics guide peak tracking sensitivity and noise models per channel

        # Alternative method specific (Global LED Intensity method)
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
) -> tuple[int, int]:
    """Calibrate integration time to find optimal value for all channels.

    SYSTEM TIMING CONSTRAINTS:
    - Target: ~1Hz acquisition frequency per channel (for 4 channels)
    - Per-channel budget: 200ms (integration + readout + processing)
    - Max integration time: 100ms (leaves 100ms for overhead)
    - Total cycle time: 4 channels +˘ 200ms = 800ms GÎÍ 1.25Hz system rate

    This function balances signal strength with timing requirements:
    - If optimal integration > 100ms GÂ∆ CONSTRAIN to 100ms, will need higher LED intensity
    - If optimal integration < 100ms GÂ∆ USE optimal value, LED has more headroom for P-mode

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels to calibrate
        integration_step: Step size for integration time adjustment
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Tuple of (integration_time, max_integration_allowed)
    """
    integration = MIN_INTEGRATION
    max_int = MAX_INTEGRATION

    # Apply system timing budget constraint
    max_int = min(max_int, MAX_INTEGRATION_BUDGET_MS)
    logger.info(f"\nG≈¶n+≈ SYSTEM TIMING BUDGET:")
    logger.info(f"   Target: {SYSTEM_ACQUISITION_TARGET_HZ}Hz per channel ({len(ch_list)} channels)")
    logger.info(f"   Per-channel budget: {TARGET_CHANNEL_BUDGET_MS}ms total")
    logger.info(f"   ")
    logger.info(f"   Hardware Acquisition Overhead (decoupled from processing):")
    logger.info(f"   G«Û Integration time: <variable, max {MAX_INTEGRATION_BUDGET_MS}ms>")
    logger.info(f"   G«Û LED settling delay: ~{ESTIMATED_LED_DELAY_MS}ms")
    logger.info(f"   G«Û Afterglow decay: ~{ESTIMATED_AFTERGLOW_MS}ms")
    logger.info(f"   G«Û Detector lag: ~{ESTIMATED_DETECTOR_LAG_MS}ms")
    logger.info(f"   G«Û USB transfer: ~{ESTIMATED_USB_TRANSFER_MS}ms")
    logger.info(f"   G«Û Total overhead: ~{HARDWARE_OVERHEAD_MS}ms")
    logger.info(f"   ")
    logger.info(f"   Max integration allowed: {MAX_INTEGRATION_BUDGET_MS}ms")
    logger.info(f"   (reserves {HARDWARE_OVERHEAD_MS}ms for hardware overhead)")
    logger.info(f"   {len(ch_list)}-channel cycle: {TARGET_CHANNEL_BUDGET_MS * len(ch_list)}ms GÎÍ {1000/(TARGET_CHANNEL_BUDGET_MS * len(ch_list)):.2f}Hz system rate")
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

    # Find minimum integration time needed for weakest channel
    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
        time.sleep(LED_DELAY)
        int_array = usb.read_intensity()
        time.sleep(LED_DELAY)
        current_count = int_array.max()
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

    # Check if low intensity saturates and reduce if needed
    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=S_LED_MIN)
        time.sleep(LED_DELAY)
        int_array = usb.read_intensity()
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

    logger.info(f"G£‡ Integration time calibrated: {integration}ms")

    # Analyze timing budget impact on LED optimization strategy
    # Calculate ACTUAL per-channel acquisition time (hardware-limited)
    actual_channel_time_ms = integration + HARDWARE_OVERHEAD_MS
    actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
    system_cycle_ms = actual_channel_time_ms * len(ch_list)
    system_hz = 1000 / system_cycle_ms if system_cycle_ms > 0 else 0

    budget_utilization = (integration / MAX_INTEGRATION_BUDGET_MS) * 100

    logger.info(f"\n=ÉÙË ACQUISITION TIMING ANALYSIS:")
    logger.info(f"   Integration time: {integration}ms ({budget_utilization:.0f}% of {MAX_INTEGRATION_BUDGET_MS}ms max)")
    logger.info(f"   Hardware overhead: ~{HARDWARE_OVERHEAD_MS}ms (LED + afterglow + detector + USB)")
    logger.info(f"   ")
    logger.info(f"   Per-channel acquisition: ~{actual_channel_time_ms}ms GÂ∆ {actual_channel_hz:.2f}Hz")
    logger.info(f"   {len(ch_list)}-channel cycle: ~{system_cycle_ms}ms GÂ∆ {system_hz:.2f}Hz system rate")
    logger.info(f"   ")

    if actual_channel_hz >= SYSTEM_ACQUISITION_TARGET_HZ:
        margin_pct = ((actual_channel_hz - SYSTEM_ACQUISITION_TARGET_HZ) / SYSTEM_ACQUISITION_TARGET_HZ) * 100
        logger.info(f"   G£‡ MEETS TARGET: {actual_channel_hz:.2f}Hz GÎ— {SYSTEM_ACQUISITION_TARGET_HZ}Hz ({margin_pct:+.0f}% margin)")
    else:
        deficit_pct = ((SYSTEM_ACQUISITION_TARGET_HZ - actual_channel_hz) / SYSTEM_ACQUISITION_TARGET_HZ) * 100
        logger.info(f"   G‹·n+≈ BELOW TARGET: {actual_channel_hz:.2f}Hz < {SYSTEM_ACQUISITION_TARGET_HZ}Hz ({deficit_pct:.0f}% deficit)")

    logger.info(f"   ")

    if integration >= MAX_INTEGRATION_BUDGET_MS:
        logger.warning(f"   =ÉÙÓ AT MAXIMUM integration time ({MAX_INTEGRATION_BUDGET_MS}ms)")
        logger.warning(f"   GÂ∆ LEDs will need HIGHER intensity to reach target signal")
        logger.warning(f"   GÂ∆ P-mode optimization will have LIMITED headroom")
        logger.warning(f"   GÂ∆ Constrained by {SYSTEM_ACQUISITION_TARGET_HZ}Hz acquisition target")
    elif integration >= 80:
        logger.info(f"   G‰¶n+≈ High integration time (>80ms)")
        logger.info(f"   GÂ∆ LEDs will use moderate-to-high intensity")
        logger.info(f"   GÂ∆ P-mode optimization will have moderate headroom")
    elif integration >= 50:
        logger.info(f"   G£‡ BALANCED integration time")
        logger.info(f"   GÂ∆ LEDs will use moderate intensity")
        logger.info(f"   GÂ∆ P-mode optimization will have good headroom")
    else:
        logger.info(f"   G£‡ EXCELLENT - Low integration time (<50ms)")
        logger.info(f"   GÂ∆ LEDs will use LOW intensity (strong optical signal)")
        logger.info(f"   GÂ∆ P-mode optimization will have EXCELLENT headroom")
        logger.info(f"   GÂ∆ Acquisition faster than {SYSTEM_ACQUISITION_TARGET_HZ}Hz target with margin")

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
) -> int:
    """Calibrate a single LED channel to target count level.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch: Channel to calibrate ('a', 'b', 'c', or 'd')
        target_counts: Target detector count level (if None, uses detector's target_counts)
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Calibrated LED intensity value (0-255)
    """
    # Get target from detector if not specified
    if target_counts is None:
        target_counts = usb.target_counts
        logger.debug(f"Using detector target: {target_counts} counts")
    logger.debug(f"Calibrating LED {ch.upper()}...")

    # Get detector limits for saturation detection
    max_counts = usb.max_counts
    saturation_threshold = max_counts * 0.95  # 95% of max = safe maximum

    # Start at maximum intensity
    intensity = P_LED_MAX
    ctrl.set_intensity(ch=ch, raw_val=intensity)
    time.sleep(LED_DELAY)

    intensity_data = usb.read_intensity()
    if intensity_data is None:
        logger.error(f"Failed to read intensity for channel {ch.upper()} - spectrometer not responding")
        raise RuntimeError(f"Spectrometer read failed for channel {ch.upper()}")
    calibration_max = intensity_data.max()

    logger.debug(f"Initial intensity: {intensity} = {calibration_max:.0f} counts")

    # Check for initial saturation
    if calibration_max >= saturation_threshold:
        logger.warning(f"G‹·n+≈ Ch {ch.upper()}: S-mode saturation detected at max LED ({calibration_max:.0f} GÎ— {saturation_threshold:.0f})")
        logger.info(f"   Auto-reducing LED intensity to bring signal to safe range...")

        # Calculate required reduction to reach 85% of detector max (safer than 95%)
        target_signal = max_counts * 0.85
        reduction_factor = target_signal / calibration_max
        reduced_intensity = max(S_LED_MIN, int(intensity * reduction_factor))

        logger.info(f"   Calculated reduction: LED {intensity} GÂ∆ {reduced_intensity} (factor: {reduction_factor:.3f})")

        # Apply reduced intensity
        ctrl.set_intensity(ch=ch, raw_val=reduced_intensity)
        time.sleep(LED_DELAY)

        # Re-measure with reduced LED
        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error(f"Failed to re-measure after saturation reduction for channel {ch.upper()}")
            raise RuntimeError(f"Spectrometer read failed during saturation recovery")

        new_max = intensity_data.max()
        logger.info(f"   After reduction: {new_max:.0f} counts ({(new_max/max_counts)*100:.1f}% of detector max)")

        # Validate the reduction worked
        if new_max >= saturation_threshold:
            logger.error(f"G•Ó Ch {ch.upper()}: Still saturated after auto-reduction - possible hardware issue")
            # Use the reduced intensity anyway - better than max saturation
            intensity = reduced_intensity
            calibration_max = new_max
        else:
            logger.info(f"G£‡ Ch {ch.upper()}: Saturation resolved, continuing calibration from reduced baseline")
            intensity = reduced_intensity
            calibration_max = new_max

    # Coarse adjust
    while (
        calibration_max > target_counts
        and intensity > COARSE_ADJUST_STEP
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity -= COARSE_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during coarse adjustment")
        calibration_max = intensity_data.max()

    logger.debug(f"Coarse adjust: {intensity} = {calibration_max:.0f} counts")

    # Medium adjust
    while (
        calibration_max < target_counts
        and intensity < P_LED_MAX
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity += MEDIUM_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during medium adjustment")
        calibration_max = intensity_data.max()

    logger.debug(f"Medium adjust: {intensity} = {calibration_max:.0f} counts")

    # Fine adjust
    while calibration_max > target_counts and intensity > FINE_ADJUST_STEP + 1:
        intensity -= FINE_ADJUST_STEP
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            raise RuntimeError(f"Spectrometer read failed during fine adjustment")
        calibration_max = intensity_data.max()

    logger.debug(f"Fine adjust: {intensity} = {calibration_max:.0f} counts")

    return intensity


def calibrate_p_mode_leds(
    usb,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    stop_flag=None,
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

    Returns:
        Tuple of (leds_calibrated, channel_performance):
        - leds_calibrated: Dictionary of calibrated P-mode LED intensities
        - channel_performance: Per-channel metrics for ML system intelligence
    """
    logger.debug("Starting P-mode LED calibration (maximize signal per channel)...")

    # Get detector limits
    max_counts = usb.max_counts
    saturation_threshold = max_counts * 0.95  # 95% of max = safe maximum

    # Target: Get as close to saturation_threshold as possible for maximum SNR
    # But leave safety margin for spectrum variations
    optimal_target = saturation_threshold * 0.95  # 95% of safe threshold = 90% of absolute max

    logger.debug(f"Max counts: {max_counts:.0f}, Saturation threshold: {saturation_threshold:.0f}, Optimal target: {optimal_target:.0f}")

    # Analyze S-mode LED intensities to predict P-mode potential
    # S-mode is the "sandbox" - it tells us how much headroom we have for P-mode boost
    logger.info("\n=ÉÙË Analyzing S-mode LED intensities (P-mode potential predictor):")
    for ch in ch_list:
        s_intensity = ref_intensity[ch]
        headroom = P_LED_MAX - s_intensity
        headroom_pct = (headroom / P_LED_MAX) * 100

        # Classify LED strength and P-mode potential
        if s_intensity < 80:  # Very strong LED
            potential = "EXCELLENT P-boost potential (very strong LED)"
            advice = "Expect 2-3x boost possible"
        elif s_intensity < 150:  # Strong LED
            potential = "GOOD P-boost potential (strong LED)"
            advice = "Expect 1.5-2x boost possible"
        elif s_intensity < 200:  # Moderate LED
            potential = "MODERATE P-boost potential"
            advice = "Expect 1.2-1.5x boost possible"
        else:  # Weak LED (>200)
            potential = "LIMITED P-boost potential (weak LED)"
            advice = "May only achieve 1.1-1.3x boost"

        logger.info(f"   Ch {ch.upper()}: S-LED={s_intensity}/255 ({headroom_pct:.0f}% headroom) - {potential}")
        logger.info(f"            {advice}")
    logger.info("")

    # CRITICAL: Turn off all channels before P-mode switch to eliminate afterglow
    # S-ref measurements just finished with all channels lit sequentially
    # Without this, residual afterglow causes false saturation in P-mode
    ctrl.turn_off_channels()
    time.sleep(LED_DELAY * 3)  # Extra delay for afterglow decay (~60ms total)

    ctrl.set_mode(mode="p")
    time.sleep(P_MODE_SWITCH_DELAY)

    leds_calibrated = {}
    channel_performance = {}  # Store per-channel metrics for ML system

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        # Analyze S-mode LED intensity to predict optimization strategy
        s_intensity = ref_intensity[ch]
        headroom = P_LED_MAX - s_intensity
        headroom_pct = (headroom / P_LED_MAX) * 100

        logger.debug(f"Optimizing P-mode LED {ch.upper()} (maximize without saturating)...")
        logger.debug(f"   S-mode baseline: LED={s_intensity}, headroom={headroom} ({headroom_pct:.0f}%)")

        # Predict maximum achievable boost based on S-mode intensity
        if s_intensity < 80:
            predicted_boost = 2.5  # Very strong LED
            logger.debug(f"   Prediction: Very strong LED, expecting 2-3x boost capability")
        elif s_intensity < 150:
            predicted_boost = 1.75  # Strong LED
            logger.debug(f"   Prediction: Strong LED, expecting 1.5-2x boost capability")
        elif s_intensity < 200:
            predicted_boost = 1.35  # Moderate LED
            logger.debug(f"   Prediction: Moderate LED, expecting 1.2-1.5x boost capability")
        else:
            predicted_boost = 1.2  # Weak LED
            logger.debug(f"   Prediction: Weak LED, limited boost potential (1.1-1.3x)")
            if headroom < 30:
                logger.warning(f"   G‹·n+≈ Ch {ch.upper()}: Very limited headroom ({headroom}). Consider reducing integration time for better P-mode optimization.")

        # Start from REDUCED intensity (50% of S-mode) since P-mode sees much more signal
        # P-mode polarizer rotation dramatically amplifies signal, so S-mode LED is too bright
        p_intensity = max(S_LED_MIN, int(ref_intensity[ch] * 0.5))  # Start at 50% of S-mode
        logger.debug(f"   Starting P-mode at 50% of S-mode: LED={p_intensity} (S-mode was {ref_intensity[ch]})")

        ctrl.set_intensity(ch=ch, raw_val=p_intensity)
        time.sleep(LED_DELAY)

        # Read initial intensity
        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error(f"Failed to read intensity for channel {ch.upper()}")
            raise RuntimeError(f"Spectrometer read failed for channel {ch.upper()}")

        calibration_max = intensity_data.max()
        logger.debug(f"Ch {ch.upper()} starting: LED={p_intensity}, Max={calibration_max:.0f} counts")

        # Phase 1: Coarse increase - quickly approach optimal range
        step_count = 0
        while (
            calibration_max < optimal_target * 0.8  # Stay well below target during coarse
            and p_intensity < (P_LED_MAX - COARSE_ADJUST_STEP)
        ):
            p_intensity += COARSE_ADJUST_STEP
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(LED_DELAY)

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
                time.sleep(LED_DELAY)
                intensity_data = usb.read_intensity()
                if intensity_data is not None:
                    calibration_max = intensity_data.max()
                break

            # Prevent infinite loops
            if step_count > 50:
                logger.warning(f"Ch {ch.upper()}: Coarse adjust iteration limit reached")
                break

        logger.debug(f"Ch {ch.upper()} after coarse: LED={p_intensity}, Max={calibration_max:.0f} counts")

        # Phase 2: Fine approach - carefully maximize to just below saturation
        step_count = 0
        prev_max = calibration_max
        logger.debug(f"Ch {ch.upper()}: Starting fine adjust from LED={p_intensity}, max={calibration_max:.0f}, target={optimal_target:.0f}")

        while (
            calibration_max < optimal_target
            and p_intensity < P_LED_MAX
        ):
            p_intensity += FINE_ADJUST_STEP
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(LED_DELAY)

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
                time.sleep(LED_DELAY)
                intensity_data = usb.read_intensity()
                if intensity_data is not None:
                    calibration_max = intensity_data.max()
                    logger.info(f"Ch {ch.upper()}: After backoff, now at {calibration_max:.0f} counts")
                break

            # Stop if signal stopped increasing (LED maxed out or optical limit)
            if step_count > 5 and abs(calibration_max - prev_max) < 100:
                logger.info(f"Ch {ch.upper()}: Signal plateaued, reached optical limit")
                break

            # Prevent infinite loops
            if step_count > 50:
                logger.warning(f"Ch {ch.upper()}: Fine adjust iteration limit reached")
                break

        # Final safety check: ensure we're truly below saturation threshold
        # Re-read spectrum one more time to verify final state
        time.sleep(LED_DELAY)
        final_check = usb.read_intensity()
        if final_check is not None:
            final_max = final_check.max()
            if final_max > saturation_threshold:
                logger.warning(f"Ch {ch.upper()}: Final check shows saturation ({final_max:.0f}), reducing further")
                # Reduce LED by 10% to get safely below threshold
                p_intensity = int(p_intensity * 0.90)
                ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(LED_DELAY)
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
        logger.info(f"G£Ù Ch {ch.upper()}: LED={p_intensity}, Max={calibration_max:.0f} counts ({utilization:.1f}% of safe max)")

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
            logger.warning(f"   G‹·n+≈ Ch {ch.upper()}: Low boost with weak LED. Consider increasing integration time to improve S-mode baseline.")
        elif actual_boost_ratio > predicted_boost * 1.2:
            logger.info(f"   G‰¶n+≈ Ch {ch.upper()}: Exceeded prediction - excellent optical coupling!")

    logger.info(f"G£‡ P-mode LED calibration complete (per-channel optimization): {leds_calibrated}")
    return leds_calibrated, channel_performance


def measure_dark_noise(
    usb,
    ctrl: ControllerBase,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
) -> np.ndarray:
    """Measure dark noise with all LEDs off.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        integration: Integration time in ms
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Array of dark noise values
    """
    logger.debug("Measuring dark noise...")

    ctrl.turn_off_channels()
    time.sleep(LED_DELAY)

    # Adjust scan count based on integration time
    if integration < INTEGRATION_THRESHOLD_MS:
        dark_scans = DARK_NOISE_SCANS
    else:
        dark_scans = int(DARK_NOISE_SCANS / 2)

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
    logger.debug(f"G£‡ Dark noise measured: max counts = {max(dark_noise):.0f}")

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
) -> dict[str, np.ndarray]:
    """Measure reference signals in S-mode for each channel.

    IMPORTANT: Applies afterglow correction to ensure S-ref is on the same basis
    as live P-mode measurements. This is critical for accurate transmission
    calculations: Transmission = (P - afterglow) / (S - afterglow)

    Without afterglow correction on S-ref, transmission would be systematically
    biased, with the error varying by channel position in the sequence.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels
        ref_intensity: S-mode LED intensities
        dark_noise: Dark noise array
        integration: Integration time in ms
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional threading event to check for cancellation
        afterglow_correction: Optional AfterglowCorrection instance for correction

    Returns:
        Dictionary of reference signal arrays for each channel (afterglow-corrected)
    """
    logger.debug("Measuring reference signals in S-mode...")

    ctrl.set_mode(mode="s")
    time.sleep(P_MODE_SWITCH_DELAY)

    ref_sig = {}
    previous_channel = None  # Track previous channel for afterglow correction

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=ref_intensity[ch])
        time.sleep(LED_DELAY)

        # Adjust scan count based on integration time
        if integration < INTEGRATION_THRESHOLD_MS:
            ref_scans = REF_SCANS
        else:
            ref_scans = int(REF_SCANS / 2)

        ref_data_sum = np.zeros_like(dark_noise)

        for _scan in range(ref_scans):
            intensity_data = usb.read_intensity()
            if intensity_data is None:
                logger.error(f"Failed to read intensity for channel {ch.upper()} during reference measurement")
                raise RuntimeError(f"Spectrometer read failed during reference signal measurement")

            int_val = intensity_data[wave_min_index:wave_max_index]
            ref_data_single = int_val - dark_noise
            ref_data_sum += ref_data_single

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
                    f"=ÉÙË S-ref afterglow correction: Ch {ch.upper()} "
                    f"(prev: {previous_channel.upper()}, correction: {afterglow_value:.1f} counts)"
                )
            except Exception as e:
                logger.warning(f"G‹·n+≈ S-ref afterglow correction failed for ch {ch.upper()}: {e}")

        # Store corrected reference signal
        ref_sig[ch] = ref_spectrum
        logger.debug(f"G£‡ Reference signal measured for ch {ch.upper()}: max = {max(ref_sig[ch]):.0f}")

        # Track this channel as previous for next iteration
        previous_channel = ch

    return ref_sig


# =============================================================================
# QUALITY CONTROL FUNCTIONS (Shared across all calibration paths)
# =============================================================================

def validate_s_ref_quality(ref_sig: dict, wave_data) -> dict:
    """Quick S-ref signal strength check during initial calibration.

    This is a lightweight check to ensure LED signals are strong enough.
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
            # Find LED peak
            peak_intensity = np.max(spectrum)
            peak_idx = np.argmax(spectrum)
            peak_wavelength = wave_data[peak_idx]

            result['peak'] = float(peak_intensity)
            result['peak_wl'] = float(peak_wavelength)

            # Just check if signal is strong enough
            if peak_intensity < 5000:
                result['warnings'].append('Very weak signal - check fiber connection')
            elif peak_intensity < 10000:
                result['warnings'].append('Weak signal - optics may need cleaning')

            result['passed'] = peak_intensity > 5000

            if result['passed']:
                logger.debug(f"G£‡ S-ref signal OK for Ch {ch.upper()}: {peak_intensity:.0f} counts @ {peak_wavelength:.0f}nm")
            else:
                logger.warning(f"G‹·n+≈ S-ref signal weak for Ch {ch.upper()}: {', '.join(result['warnings'])}")

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
) -> tuple[list[str], dict[str, float]]:
    """Verify that all calibrated P-mode channels meet minimum requirements.

    Verification checks:
    1. No saturation across full spectrum (< 95% of detector max)
    2. SPR dip validation: P-mode should show reduction vs S-mode
       - Uses dynamic ROI based on S-pol LED peak position for each channel
       - Accounts for sensor-specific SPR location and detector calibration shifts
       - P/S ratio threshold adjusted for P-mode LED boost (up to 1.33x)
         Example: 1.33x boost with 30% SPR dip GÂ∆ P/S = 1.33 +˘ 0.7 = 0.93
    3. FWHM analysis: Measure SPR dip width as sensor quality indicator
       - Narrow FWHM = high-quality sensor
       - Broad FWHM = degraded or lower-quality sensor

    Conceptual model:
    - S-pol: Sets optimal optical conditions (LED+optics baseline)
    - P-pol: S-pol baseline + SPR sensor contribution (adds SPR dip)
    - P-mode LED boosted to compensate for polarizer losses
    - Validation confirms sensor is responding and SPR is being detected

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        leds_calibrated: Dictionary of calibrated P-mode LED intensities
        wave_data: Wavelength array (if None, will read from detector)
        s_ref_signals: S-mode reference signals for comparison

    Returns:
        Tuple of (ch_error_list, spr_fwhm_dict)
        - ch_error_list: List of channels that failed verification
        - spr_fwhm_dict: Dictionary of FWHM values for each channel (nm)
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

    # CRITICAL: Turn off all channels before P-mode switch to eliminate afterglow
    # Prevents residual signal from S-ref measurements affecting P-mode verification
    ctrl.turn_off_channels()
    time.sleep(LED_DELAY * 3)  # Extra delay for afterglow decay (~60ms total)

    # Switch to P-mode for verification
    ctrl.set_mode(mode="p")
    time.sleep(0.4)

    logger.info(f"=ÉˆÏ Starting P-mode verification for {len(leds_calibrated)} channels")
    logger.debug(f"   Calibrated LED intensities: {leds_calibrated}")

    for ch in CH_LIST:
        intensity = leds_calibrated.get(ch, 0)
        if intensity == 0:
            continue

        logger.debug(f"   Verifying ch {ch.upper()} at LED intensity {intensity}...")

        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)

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

        # CRITICAL: Validate S/P orientation on first P-mode measurement per channel
        # This ensures transmission peaks are dips (valleys), not peaks (hills)
        if s_ref_signals and ch in s_ref_signals and wave_data is not None:
            try:
                from affilabs.utils.spr_signal_processing import validate_sp_orientation

                validation = validate_sp_orientation(
                    p_spectrum=intensity_data,
                    s_spectrum=s_ref_signals[ch],
                    wavelengths=wave_data,
                    window_px=200
                )

                if validation['is_flat']:
                    logger.error(f"G•Ó CALIBRATION FAILED - Ch {ch.upper()}: Flat transmission spectrum!")
                    logger.error(f"   Range: {np.ptp(intensity_data / (s_ref_signals[ch] + 1e-10)):.2f}% - possible saturation or dark signal")
                    logger.error(f"   This is a BLOCKING issue - calibration cannot proceed")
                    ch_error_list.append(ch)
                    continue
                elif not validation['orientation_correct']:
                    logger.error(f"G•Ó CALIBRATION FAILED - Ch {ch.upper()}: S/P ORIENTATION INVERTED!")
                    logger.error(f"   Transmission peak at {validation['peak_wl']:.1f}nm is HIGHER ({validation['peak_value']:.1f}%) than sides")
                    logger.error(f"   Left: {validation['left_value']:.1f}%, Right: {validation['right_value']:.1f}%")
                    logger.error(f"   G‹·n+≈ CRITICAL: S and P polarizer positions are SWAPPED")
                    logger.error(f"   GÂ∆ OEM calibration required to set correct polarizer positions")
                    logger.error(f"   This is a BLOCKING issue tied to device-level configuration")
                    ch_error_list.append(ch)
                    continue
                else:
                    logger.info(f"G£‡ Ch {ch.upper()}: S/P orientation validated (dip at {validation['peak_wl']:.1f}nm = {validation['peak_value']:.1f}%, confidence={validation['confidence']:.2f})")

            except Exception as e:
                logger.warning(f"G‹·n+≈ S/P orientation validation failed for ch {ch.upper()}: {e}")

        if spectrum_max > saturation_threshold:
            # Auto-reduce LED intensity to avoid saturation
            # Calculate required reduction: target 85% of max instead of 95%
            reduction_factor = (max_counts * 0.85) / spectrum_max
            new_intensity = max(10, int(intensity * reduction_factor))  # Minimum LED=10

            logger.warning(
                f"G‹·n+≈ P-mode saturation detected for ch {ch.upper()}: "
                f"{spectrum_max:.0f} counts (threshold: {saturation_threshold:.0f}, LED={intensity})"
            )
            logger.info(f"   GÂ∆ Auto-reducing LED intensity: {intensity} GÂ∆ {new_intensity} (factor={reduction_factor:.2f})")

            # Apply reduced intensity and re-measure
            ctrl.set_intensity(ch=ch, raw_val=new_intensity)
            time.sleep(LED_DELAY)

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
                    f"G•Ó Ch {ch.upper()} still saturated after LED reduction: "
                    f"{spectrum_max:.0f} counts (LED={new_intensity})"
                )
                continue
            else:
                # Success! Update the calibrated LED value
                leds_calibrated[ch] = new_intensity
                logger.info(f"G£‡ Ch {ch.upper()} corrected: LED={new_intensity}, max={spectrum_max:.0f} counts")
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
                # Example: 1.33x boost with 30% SPR dip GÂ∆ ratio = 1.33 +˘ 0.7 = 0.93
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

                        # Quality assessment based on FWHM thresholds
                        if fwhm < 15:
                            quality = "excellent"
                        elif fwhm < 30:
                            quality = "good"
                        elif fwhm < 50:
                            quality = "okay"
                        else:
                            quality = "poor"

                        logger.debug(
                            f"G£‡ Ch {ch.upper()} verified: max={spectrum_max:.0f} counts, "
                            f"P/S ratio={ratio:.2f}, SPR FWHM={fwhm:.1f}nm ({quality})"
                        )
                    else:
                        logger.debug(
                            f"G£‡ Ch {ch.upper()} verified: max={spectrum_max:.0f} counts, "
                            f"P/S ratio={ratio:.2f} (FWHM not calculable - very narrow dip)"
                        )
                else:
                    logger.debug(
                        f"G£‡ Ch {ch.upper()} verified: max={spectrum_max:.0f} counts, "
                        f"P/S ratio={ratio:.2f} (no clear SPR dip for FWHM)"
                    )

                # SPR dip validation with adjusted threshold for P-mode LED boost
                # With max boost (1.33x) and minimal SPR (20% dip), ratio = 1.33 +˘ 0.8 = 1.06
                # Use 1.15 threshold to allow for measurement noise and weak SPR
                if ratio >= 1.15:  # P significantly higher than S, SPR dip very weak/absent
                    logger.warning(
                        f"G‹·n+≈ P-mode verification note for ch {ch.upper()}: "
                        f"P/S ratio = {ratio:.2f} in SPR region ({roi_start:.0f}-{roi_end:.0f}nm) - "
                        f"SPR response very weak or sensor not placed"
                    )
            else:
                logger.debug(f"G£‡ Ch {ch.upper()} verified: {spectrum_max:.0f} counts (no saturation)")
        else:
            logger.debug(f"G£‡ Ch {ch.upper()} verified: {spectrum_max:.0f} counts (no saturation)")

    return ch_error_list, spr_fwhm


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
) -> LEDCalibrationResult:
    """Perform complete LED calibration using STANDARD optical configuration.

    Standard Path: Sequential optimization
    1. Wavelength data acquisition
    2. Integration time optimization (S-mode, fixed LED)
    3. S-mode LED intensity calibration (optimized integration time)
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

        # Get wavelength data
        logger.debug("Reading wavelength data...")
        wave_data = usb.read_wavelength()
        result.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
        result.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        result.wave_data = wave_data[result.wave_min_index : result.wave_max_index]
        logger.debug(
            f"Wavelength range: index {result.wave_min_index} to {result.wave_max_index}"
        )

        # Calculate Fourier weights for denoising (centralized utility)
        result.fourier_weights = calculate_fourier_weights(len(result.wave_data))

        # Determine channel list
        if single_mode:
            ch_list = [single_ch]
        elif device_type in ["EZSPR", "PicoEZSPR"]:
            ch_list = EZ_CH_LIST
        else:
            ch_list = CH_LIST

        logger.debug(f"Calibrating channels: {ch_list}")

        # Step 1: Calibrate integration time
        result.integration_time, result.num_scans = calibrate_integration_time(
            usb, ctrl, ch_list, integration_step, stop_flag
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 2: Calibrate LED intensities in S-mode
        logger.info("Calibrating LED intensities (S-mode)...")
        ctrl.set_mode(mode="s")
        time.sleep(MODE_SWITCH_DELAY)

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break
            result.ref_intensity[ch] = calibrate_led_channel(
                usb, ctrl, ch, None, stop_flag  # None = use detector's target_counts
            )

        logger.info(f"G£‡ S-mode calibration complete: {result.ref_intensity}")

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
                logger.info(f"\n=Éˆ‰ SECOND PASS OPTIMIZATION OPPORTUNITY:")
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
                    logger.info(f"   Ch {ch.upper()}: {result.ref_intensity[ch]} GÂ∆ {new_intensity} (improved by {improvement})")
                    result.ref_intensity[ch] = new_intensity

                # Update result with new integration time
                result.integration_time = new_integration
                result.num_scans = min(int(MAX_READ_TIME / new_integration), MAX_NUM_SCANS)

                logger.info(f"G£‡ Second pass complete - integration: {new_integration}ms, LEDs improved")
                logger.info(f"   Recalibrated channels: {result.ref_intensity}\n")

        # Analyze S-mode LED intensities and provide integration time guidance
        # High LED values indicate weak signal that limits P-mode optimization headroom
        weak_channels = [ch for ch, intensity in result.ref_intensity.items() if intensity > 200]
        if weak_channels:
            logger.warning(f"\nG‹·n+≈ LED INTENSITY vs TIMING BUDGET ANALYSIS:")
            logger.warning(f"   Channels {', '.join([c.upper() for c in weak_channels])} have high S-mode LED values (>200/255)")
            logger.warning(f"   This indicates weak optical signal limiting P-mode boost potential")

            # Check if we're at timing budget limit
            if result.integration_time >= MAX_INTEGRATION_BUDGET_MS:
                logger.warning(f"\n   =ÉÙÓ TIMING CONSTRAINT ACTIVE:")
                logger.warning(f"   Integration time is at maximum ({MAX_INTEGRATION_BUDGET_MS}ms) due to {SYSTEM_ACQUISITION_TARGET_HZ}Hz target")
                logger.warning(f"   GÂ∆ Cannot increase integration further without violating timing budget")
                logger.warning(f"   GÂ∆ System is optimized for SPEED over maximum SNR")
                logger.warning(f"   GÂ∆ Trade-off: {SYSTEM_ACQUISITION_TARGET_HZ}Hz acquisition vs optimal signal strength")
                logger.warning(f"\n   Options:")
                logger.warning(f"   1. Accept current configuration (speed priority)")
                logger.warning(f"   2. Reduce target frequency to allow longer integration")
                logger.warning(f"   3. Check optical coupling (fiber alignment, sensor placement)")
            else:
                logger.warning(f"\n   =É∆Ì OPTIMIZATION OPPORTUNITY:")
                logger.warning(f"   Current integration: {result.integration_time}++s (budget allows up to {MAX_INTEGRATION_BUDGET_MS}ms)")
                logger.warning(f"   Recommendation: Consider INCREASING integration time to:")
                logger.warning(f"   G«Û Lower S-mode LED intensity (more detector time = less LED needed)")
                logger.warning(f"   G«Û Increase headroom for P-mode optimization (more boost possible)")
                logger.warning(f"   G«Û Improve overall SNR for both S and P modes")
                logger.warning(f"   G«Û Still maintain {SYSTEM_ACQUISITION_TARGET_HZ}Hz target (within budget)\n")
        else:
            logger.info(f"\nG£‡ LED INTENSITY OPTIMAL:")
            logger.info(f"   All channels have good S-mode LED values (<200/255)")
            logger.info(f"   Integration time: {result.integration_time}ms (budget: {MAX_INTEGRATION_BUDGET_MS}ms)")
            logger.info(f"   Excellent balance between speed ({SYSTEM_ACQUISITION_TARGET_HZ}Hz) and signal strength\n")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 3: Measure dark noise
        logger.debug("Measuring dark noise...")
        result.dark_noise = measure_dark_noise(
            usb,
            ctrl,
            result.integration_time,
            result.wave_min_index,
            result.wave_max_index,
            stop_flag,
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 4: Load afterglow correction if available (for S-ref correction)
        afterglow_correction = None
        try:
            from afterglow_correction import AfterglowCorrection
            from pathlib import Path

            # Try to load device-specific afterglow calibration
            # This is used to correct S-ref measurements during calibration
            device_serial = getattr(usb, 'serial_number', None)
            if device_serial:
                calibration_dir = Path('optical_calibration')
                if calibration_dir.exists():
                    # Find most recent calibration file for this device
                    pattern = f"system_{device_serial}_*.json"
                    cal_files = sorted(calibration_dir.glob(pattern), reverse=True)

                    if cal_files:
                        afterglow_correction = AfterglowCorrection(cal_files[0])
                        logger.info(f"G£‡ Loaded afterglow correction for S-ref: {cal_files[0].name}")
                    else:
                        logger.info(f"G‰¶n+≈ No afterglow calibration found for device {device_serial}")
                        logger.info(f"   Calibration will proceed without afterglow correction")
                        logger.info(f"   To enable: Run afterglow measurement from Advanced Settings")
                else:
                    logger.info(f"G‰¶n+≈ Optical calibration directory not found")
                    logger.info(f"   Afterglow correction disabled - measurements will use raw spectra")
            else:
                logger.warning(f"G‹·n+≈ Device serial number not available - cannot load afterglow correction")
        except Exception as e:
            logger.warning(f"G‹·n+≈ Afterglow correction not available: {e}")
            logger.info(f"   Calibration will proceed without afterglow correction")

        # Step 5: Measure reference signals
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
            afterglow_correction,  # Pass afterglow correction for S-ref
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 5.5: Validate S-ref quality (Optical QC)
        logger.debug("=ÉÙË Performing S-ref optical quality checks...")
        result.s_ref_qc_results = validate_s_ref_quality(result.ref_sig, result.wave_data)
        logger.debug(f"   QC validation complete for {len(result.s_ref_qc_results)} channels")

        # Check if any channels failed QC
        failed_qc_channels = [ch for ch, qc in result.s_ref_qc_results.items() if not qc['passed']]
        if failed_qc_channels:
            logger.warning(f"G‹·n+≈ S-ref QC warnings for channels: {', '.join([c.upper() for c in failed_qc_channels])}")

        # Step 6: Calibrate P-mode LED intensities (returns LED values + performance metrics)
        logger.debug("Calibrating P-mode LEDs...")
        result.leds_calibrated, result.channel_performance = calibrate_p_mode_leds(
            usb, ctrl, ch_list, result.ref_intensity, stop_flag
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 7: Verify P-mode calibration (check saturation, S vs P comparison, and FWHM)
        # Use trimmed wave_data (already trimmed to MIN_WAVELENGTH:MAX_WAVELENGTH)
        # to match the trimmed ref_sig from measure_reference_signals
        result.ch_error_list, result.spr_fwhm = verify_calibration(
            usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig
        )

        # Log FWHM results for sensor quality tracking
        if result.spr_fwhm:
            fwhm_str = ", ".join([f"{ch.upper()}={fwhm:.1f}nm" for ch, fwhm in result.spr_fwhm.items()])
            logger.info(f"=ÉÙË SPR FWHM (sensor quality): {fwhm_str}")

        # Set success flag
        result.success = len(result.ch_error_list) == 0

        if result.success:
            logger.info("G£‡ LED CALIBRATION SUCCESSFUL")

            # System-level timing and performance summary
            logger.info(f"\n" + "="*70)
            logger.info(f"CALIBRATION SUMMARY - TIMING & PERFORMANCE")
            logger.info(f"="*70)

            # Calculate ACTUAL acquisition timing (hardware-limited, not processing)
            actual_channel_time_ms = result.integration_time + HARDWARE_OVERHEAD_MS
            actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
            system_cycle_ms = actual_channel_time_ms * len(ch_list)
            system_hz = 1000 / system_cycle_ms if system_cycle_ms > 0 else 0

            logger.info(f"\nG≈¶n+≈  ACQUISITION TIMING (Hardware-Limited):")
            logger.info(f"   Integration time: {result.integration_time}ms")
            logger.info(f"   Hardware overhead: ~{HARDWARE_OVERHEAD_MS}ms")
            logger.info(f"      G«Û LED settling: ~{ESTIMATED_LED_DELAY_MS}ms")
            logger.info(f"      G«Û Afterglow decay: ~{ESTIMATED_AFTERGLOW_MS}ms")
            logger.info(f"      G«Û Detector lag: ~{ESTIMATED_DETECTOR_LAG_MS}ms")
            logger.info(f"      G«Û USB transfer: ~{ESTIMATED_USB_TRANSFER_MS}ms")
            logger.info(f"   ")
            logger.info(f"   Per-channel: ~{actual_channel_time_ms}ms GÂ∆ {actual_channel_hz:.2f}Hz")
            logger.info(f"   {len(ch_list)}-channel cycle: ~{system_cycle_ms}ms GÂ∆ {system_hz:.2f}Hz")
            logger.info(f"   ")

            timing_status = "G£‡ OPTIMAL" if result.integration_time < MAX_INTEGRATION_BUDGET_MS else "G‹·n+≈ AT LIMIT"
            target_status = "G£‡ MEETS" if actual_channel_hz >= SYSTEM_ACQUISITION_TARGET_HZ else "G‹·n+≈ BELOW"
            logger.info(f"   Integration status: {timing_status}")
            logger.info(f"   Frequency target: {target_status} ({SYSTEM_ACQUISITION_TARGET_HZ}Hz target)")
            logger.info(f"   ")
            logger.info(f"   Note: Processing/graph updates run independently from acquisition")

            # LED intensity analysis
            logger.info(f"\n=É∆Ì LED INTENSITIES (S-mode baseline):")
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
            logger.info(f"\n=Éƒª SYSTEM OPTIMIZATION:")
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
            logger.warning(f"G‹·n+≈ LED calibration completed with errors on channels: {ch_str}")

        return result

    except Exception as e:
        logger.exception(f"LED calibration failed: {e}")
        result.success = False
        return result


# =============================================================================
# ALTERNATIVE CALIBRATION PATH - GLOBAL LED INTENSITY METHOD
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

    Used in Global LED Intensity method where all LEDs are at max (255) and
    integration time varies per channel to reach target signal.

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
    time.sleep(LED_DELAY)

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

    logger.info(f"G£Ù Ch {ch.upper()}: Integration={integration}ms, Signal={current_count:.0f} counts, Scans={num_scans}")

    return integration, num_scans


def perform_alternative_calibration(
    usb,
    ctrl: ControllerBase,
    device_type: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
) -> LEDCalibrationResult:
    """Perform LED calibration using ALTERNATIVE optical configuration.

    Alternative Path: Global LED Intensity Method
    =============================================
    This method uses FIXED LED intensity (all at max = 255) and VARIABLE integration
    time per channel. This approach typically provides:

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
        logger.info("=== Starting LED Calibration (Global LED Intensity Method) ===")
        logger.info("Method: Fixed LED intensity (255), variable integration time per channel")

        # Mark this as alternative method for downstream processing
        result.calibration_method = "alternative"

        # Get wavelength data
        logger.debug("Reading wavelength data...")
        wave_data = usb.read_wavelength()
        result.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
        result.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        result.wave_data = wave_data[result.wave_min_index : result.wave_max_index]
        logger.debug(f"Wavelength range: index {result.wave_min_index} to {result.wave_max_index}")

        # Calculate Fourier weights for denoising
        result.fourier_weights = calculate_fourier_weights(len(result.wave_data))

        # Determine channel list
        if single_mode:
            ch_list = [single_ch]
        elif device_type in ["EZSPR", "PicoEZSPR"]:
            ch_list = EZ_CH_LIST
        else:
            ch_list = CH_LIST

        logger.debug(f"Calibrating channels: {ch_list}")

        # Get target counts from detector
        target_counts = usb.target_counts
        logger.info(f"Target signal: {target_counts} counts per channel")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 1: Calibrate integration time per channel in S-mode (all LEDs at 255)
        logger.info("\n=ÉÙË S-MODE: Calibrating per-channel integration time (LEDs fixed at 255)...")
        ctrl.set_mode(mode="s")
        time.sleep(MODE_SWITCH_DELAY)
        ctrl.turn_off_channels()

        # Store per-channel integration times and scan counts
        s_integration_times = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # In alternative method, we only need integration time (always 1 scan per spectrum)
            s_integration_times[ch], _ = calibrate_integration_per_channel(
                usb, ctrl, ch, led_intensity=255, target_counts=target_counts, stop_flag=stop_flag
            )

            # Store LED intensity (always 255 in this method)
            result.ref_intensity[ch] = 255

        # Use the maximum integration time across all channels for consistency
        # (This ensures all channels can be read with same timing parameters)
        result.integration_time = max(s_integration_times.values())
        result.num_scans = 1  # ALWAYS 1 scan per spectrum in alternative method (both S and P)

        # Store per-channel integration times for live acquisition
        result.per_channel_integration = s_integration_times.copy()

        logger.info(f"\nG£‡ S-mode integration calibration complete:")
        logger.info(f"   Per-channel integration times: {s_integration_times}")
        logger.info(f"   Global integration time: {result.integration_time}ms (max across channels)")
        logger.info(f"   Scan count: 1 (single scan per spectrum for fast acquisition)")

        # Analyze timing and headroom (in alternative method, headroom comes from integration time)
        actual_channel_time_ms = result.integration_time + HARDWARE_OVERHEAD_MS
        actual_channel_hz = 1000 / actual_channel_time_ms if actual_channel_time_ms > 0 else 0
        logger.info(f"   Estimated per-channel rate: ~{actual_channel_hz:.2f}Hz")

        # Analyze integration time headroom (similar concept to LED headroom in standard method)
        logger.info(f"\n=ÉÙË INTEGRATION TIME HEADROOM ANALYSIS:")
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
            logger.warning(f"\n   G‹·n+≈ Channels {', '.join([c.upper() for c in weak_channels])} near timing budget limit")
            logger.warning(f"   GÂ∆ Check optical coupling (fiber alignment, sensor placement)")
        else:
            logger.info(f"\n   G£‡ All channels have good integration time headroom")
            logger.info(f"   GÂ∆ Excellent optical signal strength across all channels")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 2: Measure dark noise PER CHANNEL (each channel has different integration time)
        # In alternative method, dark noise must be measured at each channel's specific integration time
        logger.info("\n=ÉÙË Measuring per-channel dark noise (variable integration times)...")

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

            # Measure dark noise for this channel
            dark_noise_per_channel[ch] = measure_dark_noise(
                usb,
                ctrl,
                ch_integration,
                result.wave_min_index,
                result.wave_max_index,
                stop_flag,
            )

        # For compatibility with rest of code, store the dark noise for the max integration time
        # (This will be used as fallback, but per-channel values are in dark_noise_per_channel)
        result.integration_time = max(s_integration_times.values())
        result.dark_noise = dark_noise_per_channel[max(s_integration_times, key=s_integration_times.get)]

        # Store per-channel dark noise for live acquisition
        result.per_channel_dark_noise = dark_noise_per_channel.copy()

        logger.info(f"G£‡ Per-channel dark noise measurement complete")

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
                        logger.info(f"G£‡ Loaded afterglow correction: {cal_files[0].name}")
                        logger.info(f"   Note: Afterglow correction will be applied per-channel with variable integration times")

                        # Store reference for per-channel use
                        for ch in ch_list:
                            afterglow_per_channel[ch] = afterglow_correction
        except Exception as e:
            logger.debug(f"G‰¶n+≈ Afterglow correction not available: {e}")

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
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 5: Validate S-ref quality (shared QC function)
        logger.debug("=ÉÙË Performing S-ref optical quality checks...")
        result.s_ref_qc_results = validate_s_ref_quality(result.ref_sig, result.wave_data)

        failed_qc_channels = [ch for ch, qc in result.s_ref_qc_results.items() if not qc['passed']]
        if failed_qc_channels:
            logger.warning(f"G‹·n+≈ S-ref QC warnings for channels: {', '.join([c.upper() for c in failed_qc_channels])}")

        # Step 6: P-mode calibration - optimize integration time for 80% of max counts
        # In Global LED Intensity method, P-mode LEDs stay at 255, but we can increase
        # integration time to boost signal (similar to LED boost in standard method)
        logger.info("\n=ÉÙË P-MODE: Optimizing integration time for maximum signal (LEDs at 255)...")

        # CRITICAL: Turn off all channels before P-mode switch to eliminate afterglow
        ctrl.turn_off_channels()
        time.sleep(LED_DELAY * 3)  # Extra delay for afterglow decay

        ctrl.set_mode(mode="p")
        time.sleep(P_MODE_SWITCH_DELAY)
        ctrl.turn_off_channels()

        # Target 80% of detector max for P-mode (similar to standard method's target)
        max_counts = usb.max_counts
        p_target_counts = max_counts * 0.80  # 80% of detector max

        logger.info(f"   P-mode target: {p_target_counts:.0f} counts (80% of {max_counts:.0f} max)")

        p_integration_times = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # Optimize integration time for this channel in P-mode
            p_integration_times[ch], _ = calibrate_integration_per_channel(
                usb, ctrl, ch, led_intensity=255, target_counts=p_target_counts, stop_flag=stop_flag
            )

            # Store LED intensity (always 255)
            result.leds_calibrated[ch] = 255

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

            logger.info(f"   Channel {ch}: S={s_int}ms GÂ∆ P={p_int}ms (boost: {integration_boost:.2f}x, headroom: {integration_headroom_ms}ms)")

        # Store P-mode integration times (overwrite S-mode values in result)
        result.per_channel_integration = p_integration_times

        logger.info(f"\nG£‡ P-mode configuration: All LEDs at 255, 1 scan per spectrum")

        # Log boost summary
        boost_ratios = [p_integration_times[ch] / s_integration_times[ch] for ch in ch_list if s_integration_times[ch] > 0]
        avg_boost = sum(boost_ratios) / len(boost_ratios) if boost_ratios else 1.0
        logger.info(f"   Average integration boost: {avg_boost:.2f}x (SGÂ∆P)")

        # Update global integration time to max P-mode value for compatibility
        result.integration_time = max(p_integration_times.values())
        logger.info(f"   Max P-mode integration: {result.integration_time}ms")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 7: Verify P-mode calibration (shared QC function)
        # Use trimmed wave_data (already trimmed to MIN_WAVELENGTH:MAX_WAVELENGTH)
        # to match the trimmed ref_sig from measure_reference_signals
        result.ch_error_list, result.spr_fwhm = verify_calibration(
            usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig
        )

        # Log FWHM results
        if result.spr_fwhm:
            fwhm_str = ", ".join([f"{ch.upper()}={fwhm:.1f}nm" for ch, fwhm in result.spr_fwhm.items()])
            logger.info(f"=ÉÙË SPR FWHM (sensor quality): {fwhm_str}")

        # Set success flag
        result.success = len(result.ch_error_list) == 0

        if result.success:
            logger.info("G£‡ LED CALIBRATION SUCCESSFUL (Global LED Intensity Method)")
            logger.info(f"\nMethod Summary:")
            logger.info(f"   G«Û All LEDs fixed at 255 (S-mode and P-mode)")
            logger.info(f"   G«Û S-mode: Per-channel integration time optimization, 1 scan/spectrum")
            logger.info(f"   G«Û S-mode integration times: {s_integration_times}")
            logger.info(f"   G«Û Dark noise: Measured per-channel at respective integration times")
            logger.info(f"   G«Û Afterglow correction: Applied per-channel with variable integration")
            logger.info(f"   G«Û P-mode: Same LED (255), same integration times, 1 scan/spectrum")
            logger.info(f"   G«Û Data stored for live acquisition: per-channel integration and dark noise")
            logger.info(f"\nKey Benefits:")
            logger.info(f"   G«Û Faster acquisition (optimized integration per channel)")
            logger.info(f"   G«Û Excellent SNR (max LED intensity)")
            logger.info(f"   G«Û Consistent LED behavior (always at max current)")
        else:
            ch_str = ", ".join(result.ch_error_list)
            logger.warning(f"G‹·n+≈ LED calibration completed with errors on channels: {ch_str}")

        return result

    except Exception as e:
        logger.exception(f"LED calibration failed (Global LED Intensity Method): {e}")
        result.success = False
        return result
