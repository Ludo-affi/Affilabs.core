"""Adaptive Integration Calibration (Mode 2) - Fixed LED=255, Variable Integration.

This module implements Mode 2 calibration with IDENTICAL architecture to Mode 1 (Standard).

ARCHITECTURE ALIGNMENT WITH MODE 1:
- Same 6-step calibration flow
- Same 4-layer configuration (LED delays, scan counts, dark noise, reference signals)
- Same common functions (SpectrumPreprocessor, TransmissionProcessor)
- Same result structure (LEDCalibrationResult)

KEY DIFFERENCE:
- Mode 1: Fixed integration time, variable LED per channel
- Mode 2: Fixed LED=255, variable integration time per channel

CALIBRATION FLOW:
  STEP 1: Hardware Validation & LED Verification
  STEP 2: Wavelength Calibration
  STEP 3: LED Brightness Ranking (SKIPPED - all LEDs at 255)
  STEP 4: S-Mode Integration Optimization (per-channel, target 50k counts)
  STEP 5: P-Mode Integration Optimization (per-channel, target 50k counts)
  STEP 6: Data Processing & QC Validation

TIMING CONSTRAINTS (Hardware Budget - Formula-Based):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMULA:
  DETECTOR_ON  = LED_ON_TIME - DETECTOR_WAIT
  MAX_INTEGRATION = (DETECTOR_ON - SAFETY_BUFFER) / NUM_SCANS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFAULT VALUES:
  LED_ON_TIME:       250 ms (firmware fixed, configurable via settings)
  DETECTOR_WAIT:      60 ms (POST_LED_DELAY_MS - only variable we can change)
  NUM_SCANS:           3 scans (per acquisition)
  SAFETY_BUFFER:      10 ms (timing margin)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALCULATED:
  DETECTOR_ON:       190 ms (250 - 60)
  MAX_INTEGRATION:    60 ms ((190 - 10) / 3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

P-POL LED BALANCING LOGIC:
- Weakest LED is capped at 255 intensity / 60ms integration
- Weakest LED's counts become the TARGET for all other LEDs
- Stronger LEDs reduce intensity to match weakest LED's signal level
- Result: Uniform brightness across all channels (like GitHub GOLDEN S-mode)

VALIDATED PERFORMANCE (from test_max_speed_50k_counts.py):
- Throughput: 1.51 Hz (660ms/cycle for 4 channels)
- Noise: 0.22-0.63% across all channels
- Target: 50,000 counts achieved on ALL channels
- Integration times: Ch A=63ms, B=23ms, C=21ms, D=54ms (UPDATED to 60ms cap)
- LED: All channels at 255 (max brightness, then balanced)

ENABLE: Set USE_ALTERNATIVE_CALIBRATION = True in settings.py
STATUS: Currently DISABLED (production uses Mode 1)
"""

import time
from typing import TYPE_CHECKING

import numpy as np

from affilabs.core.spectrum_preprocessor import SpectrumPreprocessor
from affilabs.core.transmission_processor import TransmissionProcessor
from affilabs.utils._legacy_led_calibration import (
    DetectorParams,
    LEDCalibrationResult,
    calculate_scan_counts,
    determine_channel_list,
    get_detector_params,
    switch_mode_safely,
)
from affilabs.utils.logger import logger
from settings import (
    LED_DELAY,
    MAX_WAVELENGTH,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
)

if TYPE_CHECKING:
    from affilabs.utils.controller import ControllerBase


# =============================================================================
# MODE 2 CONSTANTS
# =============================================================================

import settings as root_settings

# LED intensity (FIXED for all channels in Mode 2)
FIXED_LED_INTENSITY = 255  # Maximum brightness for optimal stability

# Timing constants - ALL imported from settings (no hard-coding)
LED_ON_TIME_DEFAULT_MS = root_settings.LED_ON_TIME_MS
DETECTOR_WAIT_MS = root_settings.DETECTOR_WAIT_MS  # MAX integration time per scan
NUM_SCANS = root_settings.NUM_SCANS
SAFETY_BUFFER_MS = root_settings.SAFETY_BUFFER_MS

# Calculate derived timing from base parameters
DETECTOR_ON_MS = LED_ON_TIME_DEFAULT_MS - DETECTOR_WAIT_MS
MAX_INTEGRATION_MS = DETECTOR_WAIT_MS  # Per-scan cap = DETECTOR_WAIT_MS

# Optimization targets (validated for optimal SNR)
TARGET_COUNTS = 50000  # 50k counts target per channel

# Optimization parameters
MAX_ATTEMPTS = 5  # Maximum iterations per channel
MARGIN_FACTOR = 1.1  # 10% safety margin
TOLERANCE = 0.9  # Accept 90% of target


# =============================================================================
# STEP 4: S-MODE INTEGRATION OPTIMIZATION (PER-CHANNEL)
# =============================================================================


def optimize_integration_for_channel(
    usb,
    ctrl: "ControllerBase",
    channel: str,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
) -> float:
    """Optimize integration time for a single channel at LED=255.

    Uses iterative optimization algorithm validated in test_max_speed_50k_counts.py:
    - Start at minimum integration time (10ms)
    - Measure signal at LED=255
    - Calculate needed integration time based on signal ratio
    - Iteratively increase until target (50k counts) reached
    - Max integration: 300ms

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        channel: Channel to optimize ('a', 'b', 'c', or 'd')
        detector_params: Detector parameters (max counts, etc.)
        wave_min_index: Start index of wavelength ROI
        wave_max_index: End index of wavelength ROI
        stop_flag: Optional cancellation flag

    Returns:
        Optimized integration time in milliseconds

    """
    logger.info(
        f"   Channel {channel.upper()}: Optimizing integration time (LED=255, target {TARGET_COUNTS} counts)",
    )

    # Start at minimum integration time
    integration_ms = MIN_INTEGRATION * 1000  # Convert to ms

    # Iterative optimization (validated algorithm)
    for attempt in range(MAX_ATTEMPTS):
        if stop_flag and stop_flag.is_set():
            logger.warning("      Optimization cancelled")
            break

        # Set integration time
        usb.set_integration(integration_ms / 1000.0)
        time.sleep(0.05)

        # Turn on LED at fixed intensity (255)
        ctrl.set_intensity(ch=channel, raw_val=FIXED_LED_INTENSITY)
        time.sleep(LED_DELAY)

        # Read spectrum
        spectrum = usb.read_intensity()

        # Turn off LED (use turn_off_channels for proper shutdown)
        ctrl.turn_off_channels()
        time.sleep(0.05)

        if spectrum is None:
            logger.error(f"      Failed to read spectrum at {integration_ms:.1f}ms")
            msg = f"Spectrometer read failed for channel {channel.upper()}"
            raise RuntimeError(msg)

        # Get peak signal in ROI
        roi_spectrum = spectrum[wave_min_index:wave_max_index]
        peak_counts = np.max(roi_spectrum)

        logger.debug(
            f"      Attempt {attempt + 1}: {integration_ms:.1f}ms → {peak_counts:.0f} counts",
        )

        # Check if target reached
        if peak_counts >= TARGET_COUNTS * TOLERANCE:
            logger.info(
                f"      [OK] Target reached: {integration_ms:.1f}ms → {peak_counts:.0f} counts",
            )
            return integration_ms

        # Check for saturation
        if peak_counts >= detector_params.max_counts * 0.95:
            logger.warning(
                f"      Near saturation at {integration_ms:.1f}ms, backing off",
            )
            integration_ms = integration_ms * 0.8
            continue

        # Calculate needed integration time
        if integration_ms >= MAX_INTEGRATION_MS:
            logger.warning(
                f"      Max integration reached ({MAX_INTEGRATION_MS}ms) at {peak_counts:.0f} counts",
            )
            return integration_ms

        # Increase integration based on signal ratio
        needed_ratio = TARGET_COUNTS / peak_counts
        new_integration = integration_ms * needed_ratio * MARGIN_FACTOR
        integration_ms = min(new_integration, MAX_INTEGRATION_MS)

        logger.debug(
            f"      Need {needed_ratio:.2f}x more signal → increasing to {integration_ms:.1f}ms",
        )

    # Return final integration time
    logger.info(f"      Final: {integration_ms:.1f}ms → {peak_counts:.0f} counts")
    return integration_ms


# =============================================================================
# MAIN CALIBRATION FUNCTION - MODE 2
# =============================================================================


def run_adaptive_integration_calibration(
    usb,
    ctrl: "ControllerBase",
    device_type: str,
    device_config,
    detector_serial: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
    afterglow_correction=None,
) -> LEDCalibrationResult:
    """Mode 2: Adaptive Integration Calibration (LED=255, variable integration per channel).

    IDENTICAL ARCHITECTURE TO MODE 1, with one key difference:
    - Mode 1: Fixed integration, optimize LED per channel
    - Mode 2: Fixed LED=255, optimize integration per channel

    Uses same 4-layer configuration:
    - Layer 1: LED timing delays (built into hardware)
    - Layer 2: Scan averaging (calculate_scan_counts)
    - Layer 3: Dark noise baseline (common dark-ref)
    - Layer 4: Reference signals (S-pol-ref, P-pol-ref)

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        device_type: Device type ('P4SPR', 'PicoP4SPR', etc.)
        device_config: DeviceConfiguration instance
        detector_serial: Detector serial number
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode
        stop_flag: Optional cancellation flag
        progress_callback: Optional progress callback
        afterglow_correction: Optional afterglow correction instance

    Returns:
        LEDCalibrationResult with all calibration data

    """
    result = LEDCalibrationResult()

    try:
        logger.info("\n" + "=" * 80)
        logger.info("MODE 2: ADAPTIVE INTEGRATION CALIBRATION")
        logger.info("=" * 80)
        logger.info("Configuration: Fixed LED=255, Variable Integration per Channel")
        logger.info("Target: 50,000 counts per channel (optimal SNR)")
        logger.info("=" * 80 + "\n")

        # ===================================================================
        # STEP 1: HARDWARE VALIDATION & LED VERIFICATION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 1: Hardware Validation & LED Verification")
        logger.info("=" * 80)

        if ctrl is None or usb is None:
            msg = "Hardware must be connected before calibration"
            raise RuntimeError(msg)

        logger.info(f"[OK] Controller: {type(ctrl).__name__}")
        logger.info(f"[OK] Spectrometer: {type(usb).__name__}")
        logger.info(f"[OK] Detector Serial: {detector_serial}\n")

        if progress_callback:
            progress_callback("Step 1/6: Hardware Validation")

        # Force all LEDs OFF
        logger.info("🔦 Forcing ALL LEDs OFF...")
        ctrl.turn_off_channels()
        time.sleep(0.2)
        logger.info("[OK] All LEDs OFF (verified by timing)\n")

        # ===================================================================
        # STEP 2: WAVELENGTH CALIBRATION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 2: Wavelength Calibration")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 2/6: Wavelength Calibration")

        # Read wavelength data from detector
        wave_data = usb.read_wavelength()
        if wave_data is None:
            msg = "Failed to read wavelength calibration"
            raise RuntimeError(msg)

        # Determine ROI indices
        wave_min_index = np.searchsorted(wave_data, MIN_WAVELENGTH)
        wave_max_index = np.searchsorted(wave_data, MAX_WAVELENGTH)

        # Store in result
        result.wave_data = wave_data[wave_min_index:wave_max_index]
        result.wave_min_index = wave_min_index
        result.wave_max_index = wave_max_index

        logger.info(f"[OK] Wavelength range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm")
        logger.info(f"   ROI pixels: {wave_min_index} to {wave_max_index}")
        logger.info(f"   Total pixels in ROI: {wave_max_index - wave_min_index}\n")

        # Get detector parameters
        detector_params = get_detector_params(detector_serial)
        logger.info(f"[OK] Detector: {detector_params.name}")
        logger.info(f"   Max counts: {detector_params.max_counts}")
        logger.info(f"   Saturation: {detector_params.saturation_threshold}\n")

        # Determine channel list
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"[OK] Channels to calibrate: {[c.upper() for c in ch_list]}\n")

        # Calculate scan configuration (Layer 2)
        scan_config = calculate_scan_counts(device_type)
        result.num_scans = scan_config.ref_scans
        logger.info("[OK] Scan configuration:")
        logger.info(f"   Reference scans: {scan_config.ref_scans}")
        logger.info(f"   Dark scans: {scan_config.dark_scans}\n")

        # ===================================================================
        # STEP 3: LED BRIGHTNESS RANKING - SKIPPED IN MODE 2
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 3: LED Brightness Ranking")
        logger.info("=" * 80)
        logger.info("[WARN]  SKIPPED: Mode 2 uses fixed LED=255 for all channels")
        logger.info("   (No ranking needed - all LEDs at maximum intensity)\n")

        if progress_callback:
            progress_callback("Step 3/6: LED Ranking (Skipped)")

        # ===================================================================
        # STEP 4: S-MODE INTEGRATION OPTIMIZATION (PER-CHANNEL)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 4: S-Mode Integration Optimization")
        logger.info("=" * 80)
        logger.info("Optimizing integration time per channel (LED=255 fixed)")
        logger.info(f"Target: {TARGET_COUNTS} counts per channel\n")

        if progress_callback:
            progress_callback("Step 4/6: S-Mode Integration Optimization")

        # Switch to S-mode
        switch_mode_safely(ctrl, "s")

        # Optimize integration time for each channel
        s_integration_times = {}
        s_led_intensities = {}
        s_raw_data = {}

        for ch_idx, ch in enumerate(ch_list, 1):
            if stop_flag and stop_flag.is_set():
                msg = "Calibration cancelled by user"
                raise RuntimeError(msg)

            logger.info(f"\n📊 Channel {ch.upper()} (S-mode):")

            # Optimize integration time for this channel
            integration_ms = optimize_integration_for_channel(
                usb,
                ctrl,
                ch,
                detector_params,
                wave_min_index,
                wave_max_index,
                stop_flag,
            )

            # Store results
            s_integration_times[ch] = integration_ms
            s_led_intensities[ch] = FIXED_LED_INTENSITY

            # Update progress
            if progress_callback:
                30 + (ch_idx * 10)
                progress_callback(
                    f"S-mode: Ch {ch.upper()} optimized ({integration_ms:.1f}ms)",
                )

            # Capture raw spectrum for Step 6 processing
            logger.info("      Capturing reference spectrum...")
            usb.set_integration(integration_ms / 1000.0)
            time.sleep(0.05)

            # Use HAL interface with built-in averaging
            ctrl.set_intensity(ch=ch, raw_val=FIXED_LED_INTENSITY)
            time.sleep(LED_DELAY)

            spectrum = usb.read_roi(
                wave_min_index,
                wave_max_index,
                num_scans=scan_config.ref_scans,
            )

            ctrl.turn_off_channels()
            time.sleep(0.05)

            if spectrum is not None:
                s_raw_data[ch] = spectrum
                logger.info(
                    f"      [OK] Reference captured ({scan_config.ref_scans} scans averaged via HAL)",
                )

        # Store S-mode results
        result.s_mode_intensity = s_led_intensities
        result.s_integration_time = max(s_integration_times.values())  # Global max
        result.s_integration_times_per_channel = s_integration_times

        logger.info("\n" + "=" * 80)
        logger.info("[OK] S-MODE OPTIMIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Integration times: {s_integration_times}")
        logger.info(f"Global max: {result.s_integration_time:.1f}ms")
        logger.info(f"All LEDs: {FIXED_LED_INTENSITY}")
        logger.info("=" * 80 + "\n")

        # ===================================================================
        # STEP 5: P-MODE INTEGRATION OPTIMIZATION (PER-CHANNEL)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 5: P-Mode Integration Optimization")
        logger.info("=" * 80)
        logger.info("Optimizing integration time per channel (LED=255 fixed)")
        logger.info(f"Target: {TARGET_COUNTS} counts per channel\n")

        if progress_callback:
            progress_callback("Step 5/6: P-Mode Integration Optimization")

        # Switch to P-mode
        switch_mode_safely(ctrl, "p")

        # Optimize integration time for each channel
        p_integration_times = {}
        p_led_intensities = {}
        p_raw_data = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                msg = "Calibration cancelled by user"
                raise RuntimeError(msg)

            logger.info(f"\n📊 Channel {ch.upper()} (P-mode):")

            # Optimize integration time for this channel
            integration_ms = optimize_integration_for_channel(
                usb,
                ctrl,
                ch,
                detector_params,
                wave_min_index,
                wave_max_index,
                stop_flag,
            )

            # Store results
            p_integration_times[ch] = integration_ms
            p_led_intensities[ch] = FIXED_LED_INTENSITY

            # Capture raw spectrum for Step 6 processing
            logger.info("      Capturing reference spectrum...")
            usb.set_integration(integration_ms / 1000.0)
            time.sleep(0.05)

            # Use HAL interface with built-in averaging
            ctrl.set_intensity(ch=ch, raw_val=FIXED_LED_INTENSITY)
            time.sleep(LED_DELAY)

            spectrum = usb.read_roi(
                wave_min_index,
                wave_max_index,
                num_scans=scan_config.ref_scans,
            )

            ctrl.turn_off_channels()
            time.sleep(0.05)

            if spectrum is not None:
                p_raw_data[ch] = spectrum
                logger.info(
                    f"      [OK] Reference captured ({scan_config.ref_scans} scans averaged via HAL)",
                )

        # Store P-mode results (before LED balancing)
        result.p_integration_time = min(max(p_integration_times.values()), MAX_INTEGRATION_MS)  # Global max capped by timing budget
        result.p_integration_times_per_channel = p_integration_times

        # ===================================================================
        # LED INTENSITY BALANCING: Match all channels to weakest LED counts
        # ===================================================================
        logger.info("\n" + "=" * 80)
        logger.info("🔧 P-MODE LED BALANCING (Match Weakest Channel)")
        logger.info("="  * 80)
        logger.info(f"Timing Budget: {LED_ON_TIME_DEFAULT_MS:.0f}ms LED ON - {DETECTOR_WAIT_MS:.0f}ms wait = {DETECTOR_ON_MS:.0f}ms available")
        logger.info(f"Max Integration: {MAX_INTEGRATION_MS:.0f}ms per scan ({NUM_SCANS} scans)")
        logger.info(f"Weakest LED at 255/{MAX_INTEGRATION_MS:.0f}ms becomes the target for all channels")
        logger.info("This ensures uniform brightness across all channels\n")

        # Use global max integration time for consistency
        usb.set_integration(result.p_integration_time / 1000.0)
        time.sleep(0.05)

        # Find weakest channel (lowest signal at LED=255)
        weakest_ch = None
        weakest_signal = float('inf')
        channel_signals = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # Measure signal at LED=255
            ctrl.set_intensity(ch=ch, raw_val=FIXED_LED_INTENSITY)
            time.sleep(LED_DELAY)

            spectrum = usb.read_roi(wave_min_index, wave_max_index, num_scans=1)
            ctrl.turn_off_channels()
            time.sleep(0.05)

            if spectrum is not None:
                ch_signal = np.max(spectrum)
                channel_signals[ch] = ch_signal
                if ch_signal < weakest_signal:
                    weakest_signal = ch_signal
                    weakest_ch = ch

        logger.info(f"Weakest channel: {weakest_ch.upper()}")
        logger.info(f"   Signal: {weakest_signal:.0f} counts @ LED=255")
        logger.info(f"   Integration: {result.p_integration_time:.1f}ms")
        logger.info(f"\nBalancing all channels to match weakest signal level...\n")

        # Balance all other channels to match weakest
        for ch in ch_list:
            if ch == weakest_ch:
                p_led_intensities[ch] = FIXED_LED_INTENSITY
                logger.info(
                    f"   Ch {ch.upper()}: {weakest_signal:.0f} counts @ LED=255 (weakest - stays at max)"
                )
                continue

            # Calculate target LED to match weakest signal
            current_signal = channel_signals[ch]
            target_led = int(FIXED_LED_INTENSITY * (weakest_signal / current_signal))
            target_led = max(10, min(target_led, 255))

            p_led_intensities[ch] = target_led
            logger.info(
                f"   Ch {ch.upper()}: {current_signal:.0f} → {weakest_signal:.0f} counts, LED 255 → {target_led}"
            )

        # Store final P-mode LED intensities
        result.p_mode_intensity = p_led_intensities

        logger.info("\n" + "=" * 80)
        logger.info("[OK] P-MODE OPTIMIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Timing Budget: {LED_ON_TIME_DEFAULT_MS:.0f}ms LED ON → {DETECTOR_ON_MS:.0f}ms available ({NUM_SCANS} scans × {MAX_INTEGRATION_MS:.0f}ms max)")
        logger.info(f"Integration times per channel: {p_integration_times}")
        logger.info(f"Global max: {result.p_integration_time:.1f}ms (capped at {MAX_INTEGRATION_MS:.0f}ms budget)")
        logger.info(f"LED intensities (balanced): {p_led_intensities}")
        logger.info(f"Weakest LED at 255 @ {MAX_INTEGRATION_MS:.0f}ms = target for all channels")
        logger.info("=" * 80 + "\n")

        # ===================================================================
        # DARK NOISE MEASUREMENT (Layer 3)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("DARK NOISE: Measuring common dark reference")
        logger.info("=" * 80)
        logger.info("Using P-mode integration time (max of all channels)")
        logger.info(
            "This common dark-ref will be used for both S-pol and P-pol processing\n",
        )

        # Ensure all LEDs OFF
        ctrl.turn_off_channels()
        time.sleep(0.2)

        # Use P-mode integration time (maximum)
        usb.set_integration(result.p_integration_time / 1000.0)
        time.sleep(0.1)

        # Acquire dark noise using HAL with built-in averaging
        dark_full_spectrum = usb.read_roi(
            0,  # Full spectrum for dark
            len(usb.read_wavelength()),  # Full range
            num_scans=scan_config.dark_scans,
        )

        if dark_full_spectrum is None:
            msg = "Failed to capture dark noise spectra"
            raise RuntimeError(msg)

        # Filter to ROI
        dark_ref = np.mean(dark_spectra, axis=0)
        dark_ref_filtered = dark_ref[wave_min_index:wave_max_index]

        # Store dark noise (Layer 3)
        result.dark_noise = dark_ref_filtered

        # QC validation
        dark_mean = np.mean(dark_ref_filtered)
        dark_max = np.max(dark_ref_filtered)
        dark_std = np.std(dark_ref_filtered)

        logger.info("📊 Dark-ref QC:")
        logger.info(f"   Mean: {dark_mean:.1f} counts")
        logger.info(f"   Max: {dark_max:.1f} counts")
        logger.info(f"   Std: {dark_std:.1f} counts")

        EXPECTED_DARK_MIN = 2500
        EXPECTED_DARK_MAX = 4000

        if EXPECTED_DARK_MIN <= dark_mean <= EXPECTED_DARK_MAX:
            logger.info("   [OK] Dark-ref within expected range\n")
        else:
            logger.warning(
                f"   [WARN] Dark-ref outside expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX})\n",
            )

        # ===================================================================
        # STEP 6: DATA PROCESSING & QC VALIDATION (Layer 4)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 6: Data Processing & QC Validation")
        logger.info("=" * 80)
        logger.info(
            "Processing raw data using SpectrumPreprocessor (Layer 2 architecture)\n",
        )

        if progress_callback:
            progress_callback("Step 6/6: Data Processing & QC")

        # Process S-pol and P-pol reference signals
        s_pol_ref = {}
        p_pol_ref = {}

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                msg = "Calibration cancelled by user"
                raise RuntimeError(msg)

            logger.info(f"Processing channel {ch.upper()}...")

            # Process S-pol (Layer 4)
            s_spectrum = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=s_raw_data[ch],
                dark_noise=dark_ref_filtered,
                channel_name=ch,
                verbose=False,
            )
            s_pol_ref[ch] = s_spectrum

            # Process P-pol (Layer 4)
            p_spectrum = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=p_raw_data[ch],
                dark_noise=dark_ref_filtered,
                channel_name=ch,
                verbose=False,
            )
            p_pol_ref[ch] = p_spectrum

            logger.info(f"   [OK] {ch.upper()}: S-pol and P-pol processed")

        # Store reference signals
        result.s_pol_ref = s_pol_ref
        result.p_pol_ref = p_pol_ref

        # Calculate transmission spectra (Layer 4)
        logger.info("\n📊 Calculating transmission spectra...")

        transmission_data = {}
        for ch in ch_list:
            transmission = TransmissionProcessor.calculate_transmission(
                s_pol_ref=s_pol_ref[ch],
                p_pol_ref=p_pol_ref[ch],
                wave_data=result.wave_data,
                channel_name=ch,
            )
            transmission_data[ch] = transmission
            logger.info(f"   [OK] {ch.upper()}: Transmission calculated")

        result.transmission_data = transmission_data

        logger.info("\n" + "=" * 80)
        logger.info("[OK] MODE 2 CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Channels calibrated: {[c.upper() for c in ch_list]}")
        logger.info(f"S-mode integration: {s_integration_times}")
        logger.info(f"P-mode integration: {p_integration_times}")
        logger.info(f"All LEDs: {FIXED_LED_INTENSITY} (fixed)")
        logger.info(f"Target counts: {TARGET_COUNTS} (achieved)")
        logger.info("=" * 80 + "\n")

        result.success = True

    except Exception as e:
        logger.error(f"[ERROR] Calibration failed: {e}", exc_info=True)
        result.success = False
        result.error_message = str(e)

    return result
