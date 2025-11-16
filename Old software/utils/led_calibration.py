"""LED calibration module for SPR systems.

This module handles the automatic calibration of LED intensities across all channels,
integration time optimization, and reference signal measurements.
"""

from __future__ import annotations

import time
from copy import deepcopy
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
    P_COUNT_THRESHOLD,
    P_LED_MAX,
    P_MAX_INCREASE,
    REF_SCANS,
    S_COUNT_MAX,
    S_LED_INT,
    S_LED_MIN,
)
from utils.logger import logger

if TYPE_CHECKING:
    from utils.controller import ControllerBase
    from utils.usb4000_wrapper import USB4000


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


def calibrate_integration_time(
    usb: USB4000,
    ctrl: ControllerBase,
    ch_list: list[str],
    integration_step: int,
    stop_flag=None,
) -> tuple[int, int]:
    """Calibrate integration time to find optimal value for all channels.

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels to calibrate
        integration_step: Step size for integration time adjustment
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Tuple of (integration_time, max_integration_allowed)
    """
    integration = deepcopy(MIN_INTEGRATION)
    max_int = deepcopy(MAX_INTEGRATION)

    # Set to S-mode for integration time calibration
    ctrl.set_mode(mode="s")
    time.sleep(0.5)
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
        logger.debug(f"Ch {ch} initial reading at {integration}ms: {current_count:.0f} counts (target: {S_COUNT_MAX})")

        while current_count < S_COUNT_MAX and integration < max_int:
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
        logger.debug(f"Saturation check ch {ch}: {current_count:.0f}, limit: {S_COUNT_MAX}")

        while current_count > S_COUNT_MAX and integration > MIN_INTEGRATION:
            integration -= integration_step
            if integration < max_int:
                max_int = deepcopy(integration)
            logger.debug(f"Decreasing integration time for ch {ch} - {integration}ms")
            usb.set_integration(integration)
            time.sleep(0.02)
            int_array = usb.read_intensity()
            current_count = int_array.max()

    logger.info(f"✅ Integration time calibrated: {integration}ms")

    # Calculate number of scans based on integration time
    num_scans = min(int(MAX_READ_TIME / integration), MAX_NUM_SCANS)
    logger.debug(f"Scans to average: {num_scans}")

    return integration, num_scans


def calibrate_led_channel(
    usb: USB4000,
    ctrl: ControllerBase,
    ch: str,
    target_counts: float = S_COUNT_MAX,
    stop_flag=None,
) -> int:
    """Calibrate a single LED channel to target count level.

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        ch: Channel to calibrate ('a', 'b', 'c', or 'd')
        target_counts: Target detector count level
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Calibrated LED intensity value (0-255)
    """
    logger.debug(f"Calibrating LED {ch.upper()}...")

    # Start at maximum intensity
    intensity = deepcopy(P_LED_MAX)
    ctrl.set_intensity(ch=ch, raw_val=intensity)
    time.sleep(LED_DELAY)
    calibration_max = usb.read_intensity().max()

    logger.debug(f"Initial intensity: {intensity} = {calibration_max:.0f} counts")

    # Coarse adjust by 20
    quick_adjustment = 20
    while (
        calibration_max > target_counts
        and intensity > quick_adjustment
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity -= quick_adjustment
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)
        calibration_max = usb.read_intensity().max()

    logger.debug(f"Coarse adjust: {intensity} = {calibration_max:.0f} counts")

    # Medium adjust by 5
    medium_adjustment = 5
    while (
        calibration_max < target_counts
        and intensity < P_LED_MAX
        and (not stop_flag or not stop_flag.is_set())
    ):
        intensity += medium_adjustment
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)
        calibration_max = usb.read_intensity().max()

    logger.debug(f"Medium adjust: {intensity} = {calibration_max:.0f} counts")

    # Fine adjust by 1
    fine_adjustment = 1
    while calibration_max > target_counts and intensity > fine_adjustment + 1:
        intensity -= fine_adjustment
        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)
        calibration_max = usb.read_intensity().max()

    logger.debug(f"Fine adjust: {intensity} = {calibration_max:.0f} counts")

    return intensity


def calibrate_p_mode_leds(
    usb: USB4000,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    stop_flag=None,
) -> dict[str, int]:
    """Calibrate LED intensities in P-mode (after polarizer rotation).

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels to calibrate
        ref_intensity: S-mode reference intensities for each channel
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Dictionary of calibrated P-mode LED intensities
    """
    logger.debug("Starting P-mode LED calibration...")

    ctrl.set_mode(mode="p")
    time.sleep(0.4)

    leds_calibrated = {}
    quick_adjustment = 20
    medium_adjustment = 5
    fine_adjustment = 1

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        logger.debug(f"Finishing calibration LED {ch.upper()}...")
        p_intensity = deepcopy(ref_intensity[ch])
        ctrl.set_intensity(ch=ch, raw_val=p_intensity)
        time.sleep(LED_DELAY)
        calibration_max = usb.read_intensity().max()
        initial_counts = deepcopy(calibration_max)
        logger.debug(f"Initial counts: {initial_counts:.0f}")

        # Coarse adjust by 20
        while (
            calibration_max < initial_counts * P_MAX_INCREASE
            and calibration_max < S_COUNT_MAX
            and p_intensity < (P_LED_MAX - 20)
        ):
            p_intensity += quick_adjustment
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(LED_DELAY)
            calibration_max = usb.read_intensity().max()

        logger.debug(f"Coarse adjust: {p_intensity} = {calibration_max:.0f} counts")

        # Medium adjust by 5
        while calibration_max > initial_counts * P_MAX_INCREASE and p_intensity > medium_adjustment:
            p_intensity -= medium_adjustment
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(LED_DELAY)
            calibration_max = usb.read_intensity().max()

        logger.debug(f"Medium adjust: {p_intensity} = {calibration_max:.0f} counts")

        # Fine adjust by 1
        while (
            calibration_max < initial_counts * P_MAX_INCREASE
            and calibration_max < S_COUNT_MAX
            and p_intensity < P_LED_MAX
        ):
            p_intensity += fine_adjustment
            ctrl.set_intensity(ch=ch, raw_val=p_intensity)
            time.sleep(LED_DELAY)
            calibration_max = usb.read_intensity().max()

        logger.debug(f"Fine adjust: {p_intensity} = {calibration_max:.0f} counts")

        leds_calibrated[ch] = deepcopy(p_intensity)

    logger.info(f"✅ P-mode LED calibration complete: {leds_calibrated}")
    return leds_calibrated


def measure_dark_noise(
    usb: USB4000,
    ctrl: ControllerBase,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
) -> np.ndarray:
    """Measure dark noise with all LEDs off.

    Args:
        usb: USB4000 spectrometer instance
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
    fifty = 50
    if integration < fifty:
        dark_scans = DARK_NOISE_SCANS
    else:
        dark_scans = int(DARK_NOISE_SCANS / 2)

    dark_noise_sum = np.zeros(wave_max_index - wave_min_index)

    for _scan in range(dark_scans):
        if stop_flag and stop_flag.is_set():
            break
        dark_noise_single = usb.read_intensity()[wave_min_index:wave_max_index]
        dark_noise_sum += dark_noise_single

    dark_noise = dark_noise_sum / dark_scans
    logger.debug(f"✅ Dark noise measured: max counts = {max(dark_noise):.0f}")

    return dark_noise


def measure_reference_signals(
    usb: USB4000,
    ctrl: ControllerBase,
    ch_list: list[str],
    ref_intensity: dict[str, int],
    dark_noise: np.ndarray,
    integration: int,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
) -> dict[str, np.ndarray]:
    """Measure reference signals in S-mode for each channel.

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        ch_list: List of LED channels
        ref_intensity: S-mode LED intensities
        dark_noise: Dark noise array
        integration: Integration time in ms
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional threading event to check for cancellation

    Returns:
        Dictionary of reference signal arrays for each channel
    """
    logger.debug("Measuring reference signals in S-mode...")

    ctrl.set_mode(mode="s")
    time.sleep(0.4)

    ref_sig = {}
    fifty = 50

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        ctrl.set_intensity(ch=ch, raw_val=ref_intensity[ch])
        time.sleep(LED_DELAY)

        # Adjust scan count based on integration time
        if integration < fifty:
            ref_scans = REF_SCANS
        else:
            ref_scans = int(REF_SCANS / 2)

        ref_data_sum = np.zeros_like(dark_noise)

        for _scan in range(ref_scans):
            int_val = usb.read_intensity()[wave_min_index:wave_max_index]
            ref_data_single = int_val - dark_noise
            ref_data_sum += ref_data_single

        ref_sig[ch] = deepcopy(ref_data_sum / ref_scans)
        logger.debug(f"✅ Reference signal measured for ch {ch.upper()}: max = {max(ref_sig[ch]):.0f}")

    return ref_sig


def verify_calibration(
    usb: USB4000,
    ctrl: ControllerBase,
    leds_calibrated: dict[str, int],
) -> list[str]:
    """Verify that all calibrated channels meet minimum requirements.

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        leds_calibrated: Dictionary of calibrated LED intensities

    Returns:
        List of channels that failed verification
    """
    logger.debug("Verifying calibrated LED intensities...")

    ch_error_list = []

    for ch in CH_LIST:
        intensity = leds_calibrated.get(ch, 0)
        if intensity == 0:
            continue

        ctrl.set_intensity(ch=ch, raw_val=intensity)
        time.sleep(LED_DELAY)
        calibration_max = usb.read_intensity().max()

        if calibration_max < P_COUNT_THRESHOLD:
            ch_error_list.append(ch)
            logger.warning(
                f"⚠️ Calibration verification failed for ch {ch.upper()}: "
                f"{calibration_max:.0f} counts at intensity {intensity}"
            )
        else:
            logger.debug(f"✅ Ch {ch.upper()} verified: {calibration_max:.0f} counts")

    return ch_error_list


def perform_full_led_calibration(
    usb: USB4000,
    ctrl: ControllerBase,
    device_type: str,
    single_mode: bool = False,
    single_ch: str = "a",
    integration_step: int = 2,
    stop_flag=None,
) -> LEDCalibrationResult:
    """Perform complete LED calibration sequence.

    This includes:
    1. Wavelength data acquisition
    2. Integration time optimization
    3. S-mode LED intensity calibration
    4. Dark noise measurement
    5. Reference signal measurement
    6. P-mode LED intensity calibration
    7. Verification

    Args:
        usb: USB4000 spectrometer instance
        ctrl: Controller instance
        device_type: Device type string (e.g., 'P4SPR', 'PicoP4SPR')
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode
        integration_step: Step size for integration time adjustment
        stop_flag: Optional threading event to check for cancellation

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

        # Calculate Fourier weights for denoising
        alpha = 2e3
        n = len(result.wave_data) - 1
        phi = np.pi / n * np.arange(1, n)
        phi2 = phi**2
        result.fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

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
        time.sleep(0.5)

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break
            result.ref_intensity[ch] = calibrate_led_channel(
                usb, ctrl, ch, S_COUNT_MAX, stop_flag
            )

        logger.info(f"✅ S-mode calibration complete: {result.ref_intensity}")

        if stop_flag and stop_flag.is_set():
            return result

        # Step 3: Measure dark noise
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

        # Step 4: Measure reference signals
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
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 5: Calibrate P-mode LED intensities
        result.leds_calibrated = calibrate_p_mode_leds(
            usb, ctrl, ch_list, result.ref_intensity, stop_flag
        )

        if stop_flag and stop_flag.is_set():
            return result

        # Step 6: Verify calibration
        result.ch_error_list = verify_calibration(usb, ctrl, result.leds_calibrated)

        # Set success flag
        result.success = len(result.ch_error_list) == 0

        if result.success:
            logger.info("✅ LED CALIBRATION SUCCESSFUL")
        else:
            ch_str = ", ".join(result.ch_error_list)
            logger.warning(f"⚠️ LED calibration completed with errors on channels: {ch_str}")

        return result

    except Exception as e:
        logger.exception(f"LED calibration failed: {e}")
        result.success = False
        return result
