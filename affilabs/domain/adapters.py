"""Domain Model Adapters

Converts between legacy data structures and new domain models.
These adapters allow gradual migration to the new architecture.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from affilabs.utils.logger import logger

from .acquisition_config import (
    AcquisitionConfig,
    AcquisitionMode,
    LEDConfig,
    PolarizerMode,
    TimingConfig,
)
from .calibration_data import CalibrationData, CalibrationMetrics
from .spectrum_data import ProcessedSpectrumData, RawSpectrumData, SpectrumData


def led_calibration_result_to_domain(legacy_result) -> CalibrationData:
    """Convert LEDCalibrationResult to domain CalibrationData.

    Args:
        legacy_result: LEDCalibrationResult from calibration_6step

    Returns:
        CalibrationData domain model

    Raises:
        ValueError: If legacy_result is missing required data

    """
    if not legacy_result.success:
        raise ValueError("Cannot convert failed calibration result")

    # Extract wavelengths (handle both naming conventions)
    wavelengths = (
        legacy_result.wavelengths
        if legacy_result.wavelengths is not None
        else legacy_result.wave_data
    )
    if wavelengths is None or len(wavelengths) == 0:
        raise ValueError("Calibration result missing wavelength data")

    # Validate reference spectra exist
    if not legacy_result.s_pol_ref:
        raise ValueError("Calibration result missing S-pol reference spectra")

    # Build quality metrics per channel (if QC results available)
    metrics = {}
    transmission_validation = {}

    if hasattr(legacy_result, "qc_results") and legacy_result.qc_results:
        for channel, qc_data in legacy_result.qc_results.items():
            if isinstance(qc_data, dict) and channel in legacy_result.s_pol_ref:
                spectrum = legacy_result.s_pol_ref[channel]
                max_counts = legacy_result.detector_max_counts or 65535

                metrics[channel] = CalibrationMetrics(
                    snr=qc_data.get("snr", 0.0),
                    peak_intensity=float(np.max(spectrum)),
                    mean_intensity=float(np.mean(spectrum)),
                    std_dev=float(np.std(spectrum)),
                    dynamic_range=float(np.max(spectrum) / np.min(spectrum))
                    if np.min(spectrum) > 0
                    else 0.0,
                    saturation_percent=float(
                        np.sum(spectrum >= max_counts * 0.95) / len(spectrum) * 100,
                    ),
                )

                # Store P-pol and transmission data for QC dialog
                validation_data = {
                    "qc_metrics": qc_data,
                }

                # Add P-pol spectrum if available (for comparison with live data)
                if (
                    hasattr(legacy_result, "p_pol_ref")
                    and legacy_result.p_pol_ref
                    and channel in legacy_result.p_pol_ref
                ):
                    validation_data["p_pol_raw"] = legacy_result.p_pol_ref[channel].copy()

                # Add transmission spectrum if available
                if (
                    hasattr(legacy_result, "transmission")
                    and legacy_result.transmission
                    and channel in legacy_result.transmission
                ):
                    validation_data["transmission"] = legacy_result.transmission[channel].copy()

                # Add dark scan if available
                if hasattr(legacy_result, "dark_noise") and legacy_result.dark_noise is not None:
                    if channel == list(legacy_result.qc_results.keys())[0]:  # Store once
                        validation_data["dark_scan"] = legacy_result.dark_noise.copy()

                transmission_validation[channel] = validation_data

    # Create domain model (ROI indices set directly on fields after creation)
    # Handle both dict and object forms (7-step returns dict, 6-step returns object)
    is_dict = isinstance(legacy_result, dict)

    logger.info(
        f"[ADAPTER] Converting calibration result: is_dict={is_dict}, type={type(legacy_result).__name__}",
    )

    # Extract S-pol reference
    if is_dict:
        s_pol_ref = {
            k: v.copy() if hasattr(v, "copy") else v
            for k, v in legacy_result.get("s_pol_ref", {}).items()
        }
    else:
        s_pol_ref = {k: v.copy() for k, v in legacy_result.s_pol_ref.items()}

    # Extract LED intensities (handle dict vs object, singular vs plural)
    if is_dict:
        p_mode_intensities = dict(legacy_result.get("p_mode_intensities", {}))
        s_mode_intensities = dict(legacy_result.get("s_mode_intensities", {}))
        logger.info(f"[ADAPTER] Dict form - P-mode LEDs: {p_mode_intensities}")
        logger.info(f"[ADAPTER] Dict form - S-mode LEDs: {s_mode_intensities}")
    else:
        # Object form: check for plural attribute first, then singular, then fallback
        p_mode_intensities = (
            dict(
                legacy_result.p_mode_intensities
                if hasattr(legacy_result, "p_mode_intensities")
                else legacy_result.p_mode_intensity,
            )
            if (
                hasattr(legacy_result, "p_mode_intensities")
                or hasattr(legacy_result, "p_mode_intensity")
            )
            else {}
        )
        s_mode_intensities = (
            dict(
                legacy_result.s_mode_intensities
                if hasattr(legacy_result, "s_mode_intensities")
                else legacy_result.s_mode_intensity,
            )
            if (
                hasattr(legacy_result, "s_mode_intensities")
                or hasattr(legacy_result, "s_mode_intensity")
            )
            else dict(legacy_result.ref_intensity)
            if hasattr(legacy_result, "ref_intensity") and legacy_result.ref_intensity
            else {}
        )

    # Helper function to safely get values from dict or object
    def safe_get(key, default=None):
        if is_dict:
            return legacy_result.get(key, default)
        return getattr(legacy_result, key, default)

    cal_data = CalibrationData(
        # Core calibration data
        s_pol_ref=s_pol_ref,
        wavelengths=wavelengths.copy(),
        # LED intensities (extracted above)
        p_mode_intensities=p_mode_intensities,
        s_mode_intensities=s_mode_intensities,
        # Acquisition parameters
        integration_time_s=float(safe_get("s_integration_time"))
        if safe_get("s_integration_time")
        else 0.0,
        integration_time_p=float(safe_get("p_integration_time"))
        if safe_get("p_integration_time")
        else float(safe_get("s_integration_time"))
        if safe_get("s_integration_time")
        else 0.0,
        num_scans=int(safe_get("num_scans", 5)),
        # Timing parameters
        pre_led_delay=float(safe_get("pre_led_delay_ms", 12.0)),
        post_led_delay=float(safe_get("post_led_delay_ms", 40.0)),
        # Dark references (per-channel for S-pol and P-pol integration times)
        dark_s={
            k: v.copy() if hasattr(v, "copy") else v
            for k, v in (safe_get("channel_dark_s") or {}).items()
        },
        dark_p={
            k: v.copy() if hasattr(v, "copy") else v
            for k, v in (safe_get("channel_dark_p") or {}).items()
        },
        # Per-channel integration times (alternative calibration mode)
        channel_integration_times=dict(safe_get("channel_integration_times") or {}),
        # Quality metrics
        metrics=metrics,
        # QC validation with spectra
        transmission_validation=transmission_validation,
        # Metadata
        timestamp=datetime.now().timestamp(),
        roi_start=float(wavelengths[0]),
        roi_end=float(wavelengths[-1]),
    )

    # timing_sync removed - old calibration code

    # Propagate convergence summary if available (Steps 3-5 results)
    try:
        convergence_summary = safe_get("convergence_summary")
        if convergence_summary:
            cal_data.convergence_summary = dict(convergence_summary)
    except Exception:
        pass

    # Set ROI indices directly (these have properties but underlying fields can be set)
    # CRITICAL: These are used by live acquisition to crop raw spectra correctly
    cal_data._wave_min_index = (
        int(legacy_result.wave_min_index) if hasattr(legacy_result, "wave_min_index") else 0
    )
    cal_data._wave_max_index = (
        int(legacy_result.wave_max_index)
        if hasattr(legacy_result, "wave_max_index")
        else len(wavelengths)
    )

    return cal_data


def domain_to_acquisition_config(
    calibration: CalibrationData,
    mode: AcquisitionMode = AcquisitionMode.LIVE,
) -> AcquisitionConfig:
    """Convert CalibrationData to AcquisitionConfig.

    Creates acquisition configuration based on calibration results.

    Args:
        calibration: CalibrationData domain model
        mode: Acquisition mode (LIVE, CALIBRATION, SINGLE)

    Returns:
        AcquisitionConfig with parameters from calibration

    """
    return AcquisitionConfig(
        mode=mode,
        integration_time_s=calibration.integration_time_s,
        integration_time_p=calibration.integration_time_p,
        per_channel_integration=False,
        num_scans=calibration.num_scans,
        s_mode_leds=LEDConfig.from_dict(calibration.s_mode_intensities),
        p_mode_leds=LEDConfig.from_dict(calibration.p_mode_intensities),
        timing=TimingConfig(
            pre_led_delay=calibration.pre_led_delay,
            post_led_delay=calibration.post_led_delay,
            servo_movement_delay=150.0,  # Standard value
            integration_time=calibration.integration_time_p,
        ),
        roi_start=calibration.roi_start,
        roi_end=calibration.roi_end,
        polarizer_mode=PolarizerMode.P_MODE
        if mode == AcquisitionMode.LIVE
        else PolarizerMode.S_MODE,
        apply_baseline_correction=True,
        apply_smoothing=False,
        smoothing_window=11,
    )


def numpy_spectrum_to_domain(
    wavelengths: np.ndarray,
    intensities: np.ndarray,
    channel: str,
    timestamp: float | None = None,
    **kwargs,
) -> SpectrumData:
    """Convert numpy arrays to SpectrumData domain model.

    Args:
        wavelengths: Wavelength array (nm)
        intensities: Intensity array (counts or %)
        channel: Channel identifier ('a', 'b', 'c', 'd')
        timestamp: Unix timestamp (defaults to now)
        **kwargs: Additional metadata

    Returns:
        SpectrumData domain model

    """
    return SpectrumData(
        wavelengths=wavelengths.copy()
        if isinstance(wavelengths, np.ndarray)
        else np.array(wavelengths),
        intensities=intensities.copy()
        if isinstance(intensities, np.ndarray)
        else np.array(intensities),
        channel=channel.lower(),
        timestamp=timestamp if timestamp is not None else datetime.now().timestamp(),
        metadata=dict(kwargs),
    )


def create_raw_spectrum(
    wavelengths: np.ndarray,
    intensities: np.ndarray,
    channel: str,
    integration_time: float,
    num_scans: int,
    led_intensity: int,
    timestamp: float | None = None,
    **kwargs,
) -> RawSpectrumData:
    """Create RawSpectrumData from acquisition parameters.

    Args:
        wavelengths: Wavelength array (nm)
        intensities: Raw intensity array (counts)
        channel: Channel identifier
        integration_time: Integration time (ms)
        num_scans: Number of averaged scans
        led_intensity: LED brightness (0-255)
        timestamp: Unix timestamp (defaults to now)
        **kwargs: Additional metadata

    Returns:
        RawSpectrumData domain model

    """
    return RawSpectrumData(
        wavelengths=wavelengths.copy()
        if isinstance(wavelengths, np.ndarray)
        else np.array(wavelengths),
        intensities=intensities.copy()
        if isinstance(intensities, np.ndarray)
        else np.array(intensities),
        channel=channel.lower(),
        timestamp=timestamp if timestamp is not None else datetime.now().timestamp(),
        metadata=dict(kwargs),
        integration_time=float(integration_time),
        num_scans=int(num_scans),
        led_intensity=int(led_intensity),
    )


def create_processed_spectrum(
    wavelengths: np.ndarray,
    transmission_percent: np.ndarray,
    channel: str,
    reference_spectrum: np.ndarray | None = None,
    baseline_corrected: bool = False,
    timestamp: float | None = None,
    **kwargs,
) -> ProcessedSpectrumData:
    """Create ProcessedSpectrumData from transmission calculation.

    Args:
        wavelengths: Wavelength array (nm)
        transmission_percent: Transmission spectrum (%)
        channel: Channel identifier
        reference_spectrum: S-pol reference spectrum (optional)
        baseline_corrected: Whether baseline correction was applied
        timestamp: Unix timestamp (defaults to now)
        **kwargs: Additional metadata

    Returns:
        ProcessedSpectrumData domain model

    """
    return ProcessedSpectrumData(
        wavelengths=wavelengths.copy()
        if isinstance(wavelengths, np.ndarray)
        else np.array(wavelengths),
        intensities=transmission_percent.copy()
        if isinstance(transmission_percent, np.ndarray)
        else np.array(transmission_percent),
        channel=channel.lower(),
        timestamp=timestamp if timestamp is not None else datetime.now().timestamp(),
        metadata=dict(kwargs),
        transmission_percent=transmission_percent.copy()
        if isinstance(transmission_percent, np.ndarray)
        else np.array(transmission_percent),
        reference_spectrum=reference_spectrum.copy()
        if reference_spectrum is not None and isinstance(reference_spectrum, np.ndarray)
        else reference_spectrum,
        baseline_corrected=baseline_corrected,
    )
