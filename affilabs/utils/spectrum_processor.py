"""Spectrum Processing Service - Centralized spectrum analysis and pipeline execution.

This module extracts spectrum processing logic from the main application loop,
providing a clean interface for:
- Pipeline selection and execution
- Fallback handling
- Quality monitoring
- Processing statistics

Design Goals:
- Single Responsibility: Only process spectra, don't manage hardware or UI
- Pluggable: Works with any pipeline that implements the interface
- Testable: Pure functions with clear inputs/outputs
- Observable: Emits quality warnings and statistics
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from affilabs.utils.detector_config import get_spr_wavelength_range
from affilabs.utils.logger import logger
from affilabs.utils.processing_pipeline import get_pipeline_registry
from affilabs.utils.spr_signal_processing import (
    apply_centered_median_filter,
)
from affilabs.utils.spr_signal_processing_compat import (
    find_resonance_wavelength_fourier,
)


def _compute_fwhm_and_depth(
    transmission: np.ndarray,
    wavelengths: np.ndarray,
    peak_nm: float,
) -> tuple[float | None, float | None]:
    """Compute FWHM and dip depth from a transmission spectrum at a known peak.

    Args:
        transmission: 1-D transmission array (0–100 %).
        wavelengths: Corresponding wavelength array (nm).
        peak_nm: Resonance wavelength found by the pipeline (nm).

    Returns:
        (fwhm_nm, dip_depth) where dip_depth is a fraction 0–1.
        Both are None if computation fails.
    """
    try:
        if transmission is None or wavelengths is None or len(transmission) < 5:
            return None, None

        peak_idx = int(np.argmin(np.abs(wavelengths - peak_nm)))
        dip_val = float(transmission[peak_idx])
        baseline = float(np.percentile(transmission, 90))  # upper envelope ≈ baseline

        depth = max(0.0, (baseline - dip_val) / baseline) if baseline > 0 else None

        # FWHM: find half-maximum level and walk outward from peak
        half_max = dip_val + (baseline - dip_val) * 0.5
        # Walk left
        left_idx = peak_idx
        while left_idx > 0 and transmission[left_idx] < half_max:
            left_idx -= 1
        # Walk right
        right_idx = peak_idx
        while right_idx < len(transmission) - 1 and transmission[right_idx] < half_max:
            right_idx += 1

        if right_idx > left_idx:
            fwhm = float(wavelengths[right_idx] - wavelengths[left_idx])
            # Sanity-check: SPR dip should be 10–80 nm wide
            fwhm = fwhm if 5.0 <= fwhm <= 100.0 else None
        else:
            fwhm = None

        return fwhm, depth

    except Exception:
        return None, None


@dataclass
class ProcessingResult:
    """Result of processing a single spectrum.

    Attributes:
        resonance_wavelength: Detected resonance peak (nm)
        pipeline_used: Name of pipeline that produced result
        fallback_used: Whether fallback method was needed
        processing_time_ms: Time taken to process (milliseconds)
        quality_score: Quality metric (0-1, optional)
        warnings: List of quality warnings
        metadata: Additional pipeline-specific data

    """

    resonance_wavelength: float
    pipeline_used: str
    fallback_used: bool = False
    processing_time_ms: float = 0.0
    quality_score: float | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SpectrumProcessor:
    """Centralized spectrum processing with pluggable pipelines.

    This class handles all spectrum processing operations, including:
    - Executing the active pipeline
    - Falling back to Fourier method if pipeline fails
    - Tracking processing statistics per channel
    - Emitting quality warnings
    - Periodic logging for diagnostics

    Example:
        >>> processor = SpectrumProcessor(fourier_weights)
        >>> result = processor.process_transmission(
        ...     transmission=trans_spectrum,
        ...     wavelengths=wave_data,
        ...     channel='a'
        ... )
        >>> print(f"Peak at {result.resonance_wavelength:.2f} nm")

    """

    def __init__(
        self,
        fourier_weights: np.ndarray | None = None,
        fourier_window_size: int = 165,
        spectral_correction: dict[str, np.ndarray] | None = None,
        detector_serial: str | None = None,
        detector_type: str | None = None,
    ) -> None:
        """Initialize the spectrum processor.

        Args:
            fourier_weights: Pre-computed Fourier weights for fallback method
            fourier_window_size: Window size for Fourier peak detection
            spectral_correction: Per-channel spectral response correction weights.
                Dictionary mapping channel -> correction array (same length as wavelengths).
                Used to normalize out fiber coupling differences, LED variations,
                and detector non-uniformity.
            detector_serial: Detector serial number for automatic wavelength range detection
            detector_type: Detector type string (e.g., "USB4000", "PhasePhotonics")

        """
        self.fourier_weights = fourier_weights
        self.fourier_window_size = fourier_window_size
        self.spectral_correction = spectral_correction or {}
        self.detector_serial = detector_serial
        self.detector_type = detector_type

        # Processing statistics per channel
        self.stats = {
            ch: {
                "total_processed": 0,
                "fallback_count": 0,
                "error_count": 0,
                "last_pipeline": None,
                "avg_processing_time_ms": 0.0,
            }
            for ch in ["a", "b", "c", "d"]
        }

        # For periodic logging
        self._log_counter = dict.fromkeys(["a", "b", "c", "d"], 0)
        self._log_interval = 100  # Log every N spectra

        # Pipeline caching for performance (avoid registry lookup every call)
        self._cached_pipeline = None
        self._cached_pipeline_id = None

        # Stats update optimization - only calculate detailed stats periodically
        self._stats_update_counter = dict.fromkeys(["a", "b", "c", "d"], 0)
        self._stats_update_interval = 10  # Update detailed stats every N cycles

    def set_detector_info(
        self,
        detector_serial: str | None = None,
        detector_type: str | None = None,
    ) -> None:
        """Update detector information for automatic wavelength range detection.

        Args:
            detector_serial: Detector serial number (e.g., "ST00012", "USB4H14526")
            detector_type: Detector type string (e.g., "USB4000", "PhasePhotonics")
        """
        self.detector_serial = detector_serial
        self.detector_type = detector_type

    def process_transmission(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        channel: str,
        s_reference: np.ndarray = None,
    ) -> ProcessingResult:
        """Process transmission spectrum to find resonance wavelength.

        This is the main entry point for spectrum processing. It:
        1. Gets the active pipeline from the registry
        2. Attempts processing with the active pipeline (with SNR weighting if s_reference provided)
        3. Falls back to Fourier method if pipeline fails
        4. Updates statistics and logs periodically

        Args:
            transmission: Transmission spectrum (T = I/I_ref)
            wavelengths: Wavelength array corresponding to transmission
            channel: Channel identifier ('a', 'b', 'c', 'd')
            s_reference: S-pol reference spectrum for SNR-aware weighting (optional)

        Returns:
            ProcessingResult with resonance wavelength and metadata

        Raises:
            ValueError: If transmission or wavelengths are invalid

        """
        start_time = time.perf_counter()

        # Validate inputs
        if transmission is None or wavelengths is None:
            msg = "Transmission and wavelengths cannot be None"
            raise ValueError(msg)
        if len(transmission) != len(wavelengths):
            msg = "Transmission and wavelengths must have same length"
            raise ValueError(msg)
        if channel not in self.stats:
            msg = f"Invalid channel: {channel}"
            raise ValueError(msg)

        # Apply spectral correction if available for this channel
        # This normalizes out fiber coupling, LED variations, and detector non-uniformity
        if channel in self.spectral_correction:
            transmission = transmission * self.spectral_correction[channel]

        # Try active pipeline first - use cached version if available
        try:
            registry = get_pipeline_registry()
            pipeline_id = registry.active_pipeline_id

            # Check if we can reuse cached pipeline
            if self._cached_pipeline is None or self._cached_pipeline_id != pipeline_id:
                self._cached_pipeline = registry.get_active_pipeline()
                self._cached_pipeline_id = pipeline_id

            active_pipeline = self._cached_pipeline
            pipeline_metadata = active_pipeline.get_metadata()

            # Calculate hint wavelength for peak finding guidance
            # This prevents algorithms from finding spurious minimums in noisy regions
            minimum_hint_nm = None
            if (
                transmission is not None
                and wavelengths is not None
                and len(transmission) == len(wavelengths)
            ):
                # Get detector-specific SPR region (Phase Photonics: 570-720nm, Ocean Optics: 560-720nm)
                detector_serial_val = getattr(self, 'detector_serial', None)
                detector_type_val = getattr(self, 'detector_type', None)
                spr_min, spr_max = get_spr_wavelength_range(detector_serial_val, detector_type_val)

                # Find minimum transmission in detector-specific SPR region as hint
                spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
                if np.any(spr_mask):
                    spr_transmission = transmission[spr_mask]
                    spr_wavelengths = wavelengths[spr_mask]
                    min_idx = np.argmin(spr_transmission)
                    minimum_hint_nm = float(spr_wavelengths[min_idx])
                    # Debug: Hint calculation complete

            # Execute pipeline with SNR weighting and detector info
            resonance_wavelength = active_pipeline.find_resonance_wavelength(
                transmission=transmission,
                wavelengths=wavelengths,
                s_reference=s_reference,
                detector_serial=self.detector_serial,
                detector_type=self.detector_type,
                hint_wavelength_nm=minimum_hint_nm,  # Pass hint to guide peak finding
            )

            # Check for valid result
            if resonance_wavelength is None or np.isnan(resonance_wavelength):
                msg = f"Pipeline returned invalid result: {resonance_wavelength}"
                raise ValueError(msg)

            # Dip tracking complete

            # Compute FWHM and dip depth from transmission at the found peak.
            # Done here so all pipelines (fourier, centroid, adaptive, etc.) produce
            # these metrics consistently, regardless of what the pipeline itself returns.
            fwhm_nm, dip_depth = _compute_fwhm_and_depth(
                transmission, wavelengths, resonance_wavelength
            )

            # Success - create result (only calculate timing every 10th cycle for efficiency)
            self._stats_update_counter[channel] += 1
            if self._stats_update_counter[channel] % self._stats_update_interval == 0:
                processing_time = (time.perf_counter() - start_time) * 1000
            else:
                processing_time = self.stats[channel][
                    "avg_processing_time_ms"
                ]  # Use cached value

            result = ProcessingResult(
                resonance_wavelength=resonance_wavelength,
                pipeline_used=pipeline_metadata.name,
                fallback_used=False,
                processing_time_ms=processing_time,
                metadata={
                    "pipeline_id": pipeline_id,
                    "fwhm": fwhm_nm,
                    "depth": dip_depth,
                },
            )

            # Update statistics (lightweight)
            self.stats[channel]["total_processed"] += 1
            self.stats[channel]["last_pipeline"] = result.pipeline_used

            # Only do expensive stats updates periodically
            if self._stats_update_counter[channel] % self._stats_update_interval == 0:
                self._update_detailed_stats(channel, result)
                self._maybe_log_status(channel, result)

            return result

        except Exception as e:
            # Pipeline failed - fall back to Fourier method
            logger.warning(
                f"Pipeline processing failed for channel {channel}: {e}. "
                f"Falling back to Fourier method.",
            )
            return self._fallback_processing(
                transmission=transmission,
                wavelengths=wavelengths,
                channel=channel,
                start_time=start_time,
                error=str(e),
            )

    def _fallback_processing(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        channel: str,
        start_time: float,
        error: str,
    ) -> ProcessingResult:
        """Execute fallback Fourier processing when pipeline fails.

        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            channel: Channel identifier
            start_time: Processing start time (for timing)
            error: Error message from failed pipeline

        Returns:
            ProcessingResult using Fourier method

        """
        try:
            resonance_wavelength = find_resonance_wavelength_fourier(
                transmission_spectrum=transmission,
                wavelengths=wavelengths,
                fourier_weights=self.fourier_weights,
                window_size=self.fourier_window_size,
                s_reference=None,  # Fallback doesn't have s_reference context
            )

            processing_time = (time.perf_counter() - start_time) * 1000
            result = ProcessingResult(
                resonance_wavelength=resonance_wavelength,
                pipeline_used="Fourier (Fallback)",
                fallback_used=True,
                processing_time_ms=processing_time,
                warnings=[f"Primary pipeline failed: {error}"],
                metadata={"fallback_reason": error},
            )

            # Update statistics
            self._update_stats(channel, result)

            return result

        except Exception as fallback_error:
            # Even fallback failed - return NaN
            logger.error(
                f"Fallback processing also failed for channel {channel}: {fallback_error}",
            )

            processing_time = (time.perf_counter() - start_time) * 1000
            result = ProcessingResult(
                resonance_wavelength=np.nan,
                pipeline_used="None (Error)",
                fallback_used=True,
                processing_time_ms=processing_time,
                warnings=[
                    f"Primary pipeline failed: {error}",
                    f"Fallback also failed: {fallback_error}",
                ],
                metadata={
                    "primary_error": error,
                    "fallback_error": str(fallback_error),
                },
            )

            self._update_stats(channel, result)
            return result

    def _update_stats(self, channel: str, result: ProcessingResult) -> None:
        """Update processing statistics for a channel (lightweight version for backward compatibility).

        Args:
            channel: Channel identifier
            result: Processing result to record

        """
        stats = self.stats[channel]
        stats["total_processed"] += 1

        if result.fallback_used:
            stats["fallback_count"] += 1

        if np.isnan(result.resonance_wavelength):
            stats["error_count"] += 1

        stats["last_pipeline"] = result.pipeline_used

        # Update moving average of processing time
        n = stats["total_processed"]
        old_avg = stats["avg_processing_time_ms"]
        stats["avg_processing_time_ms"] = (
            old_avg * (n - 1) + result.processing_time_ms
        ) / n

    def _update_detailed_stats(self, channel: str, result: ProcessingResult) -> None:
        """Update detailed processing statistics (called periodically to reduce overhead).

        Args:
            channel: Channel identifier
            result: Processing result to record

        """
        stats = self.stats[channel]

        # Update moving average of processing time
        n = stats["total_processed"]
        old_avg = stats["avg_processing_time_ms"]
        stats["avg_processing_time_ms"] = (
            old_avg * (n - 1) + result.processing_time_ms
        ) / n

    def _maybe_log_status(self, channel: str, result: ProcessingResult) -> None:
        """Log processing status periodically for diagnostics.

        Args:
            channel: Channel identifier
            result: Latest processing result

        """
        self._log_counter[channel] += 1

        if self._log_counter[channel] % self._log_interval == 0:
            stats = self.stats[channel]
            logger.debug(
                f"Channel {channel} processing stats (#{stats['total_processed']}): "
                f"Pipeline='{result.pipeline_used}', "
                f"Fallback rate={stats['fallback_count'] / stats['total_processed'] * 100:.1f}%, "
                f"Error rate={stats['error_count'] / stats['total_processed'] * 100:.1f}%, "
                f"Avg time={stats['avg_processing_time_ms']:.2f}ms",
            )

    def get_statistics(self, channel: str | None = None) -> dict:
        """Get processing statistics.

        Args:
            channel: Specific channel, or None for all channels

        Returns:
            Dictionary of statistics

        """
        if channel is not None:
            return self.stats[channel].copy()
        return {ch: stats.copy() for ch, stats in self.stats.items()}

    def reset_statistics(self, channel: str | None = None) -> None:
        """Reset processing statistics.

        Args:
            channel: Specific channel to reset, or None for all channels

        """
        channels = [channel] if channel else list(self.stats.keys())

        for ch in channels:
            self.stats[ch] = {
                "total_processed": 0,
                "fallback_count": 0,
                "error_count": 0,
                "last_pipeline": None,
                "avg_processing_time_ms": 0.0,
            }
            self._log_counter[ch] = 0


class TemporalFilter:
    """Apply temporal filtering to resonance wavelength time series.

    This class provides various filtering methods that can be applied
    to the raw resonance wavelength values to reduce noise.

    Currently supports:
    - Median filtering (centered window)
    - Moving average (future: exponential smoothing, Kalman)
    """

    def __init__(self, method: str = "median", window_size: int = 5) -> None:
        """Initialize temporal filter.

        Args:
            method: Filter method ('median', 'moving_average')
            window_size: Size of filter window (must be odd for median)

        """
        self.method = method
        self.window_size = window_size

        if method == "median" and window_size % 2 == 0:
            msg = "Median filter window_size must be odd"
            raise ValueError(msg)

    def apply(
        self,
        values: np.ndarray,
        current_index: int,
    ) -> float:
        """Apply temporal filter at current index.

        Args:
            values: Array of all values up to current point
            current_index: Index to filter

        Returns:
            Filtered value

        """
        if self.method == "median":
            return apply_centered_median_filter(
                values=values,
                current_index=current_index,
                window_size=self.window_size,
            )
        if self.method == "moving_average":
            return self._moving_average(values, current_index)
        msg = f"Unknown filter method: {self.method}"
        raise ValueError(msg)

    def _moving_average(self, values: np.ndarray, current_index: int) -> float:
        """Simple moving average filter.

        Args:
            values: Array of values
            current_index: Current position

        Returns:
            Moving average

        """
        start = max(0, current_index - self.window_size + 1)
        end = current_index + 1
        return np.mean(values[start:end])
