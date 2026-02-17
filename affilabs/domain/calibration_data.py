"""Calibration Data Models

Pure Python data structures for calibration.
NO Qt dependencies - fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class CalibrationMetrics:
    """Quality metrics for calibration validation.

    Used to assess whether calibration is acceptable.
    """

    snr: float  # Signal-to-noise ratio
    peak_intensity: float  # Maximum intensity in spectrum
    mean_intensity: float  # Average intensity
    std_dev: float  # Standard deviation
    dynamic_range: float  # Max / Min intensity
    saturation_percent: float  # % of pixels at max value

    def is_saturated(self, threshold: float = 5.0) -> bool:
        """Check if spectrum is saturated."""
        return self.saturation_percent > threshold

    def is_low_signal(self, threshold: float = 1000.0) -> bool:
        """Check if signal is too low."""
        return self.mean_intensity < threshold

    def is_acceptable(self) -> bool:
        """Check if metrics indicate good calibration."""
        return (
            not self.is_saturated()
            and not self.is_low_signal()
            and self.snr > 10.0
            and self.dynamic_range > 1.5
        )


@dataclass
class CalibrationData:
    """Complete calibration dataset.

    Contains S-mode reference spectra and LED intensities
    used for transmission calculations.

    This replaces the legacy CalibrationData namedtuple with
    a proper domain model.
    """

    # Core calibration data
    s_pol_ref: dict[str, np.ndarray]  # channel -> reference spectrum
    wavelengths: np.ndarray  # wavelength array in nanometers (nm), converted from SeaBreeze µm

    # LED intensities
    p_mode_intensities: dict[str, int]  # P-mode LED brightness
    s_mode_intensities: dict[str, int]  # S-mode LED brightness

    # Acquisition parameters
    integration_time_s: float = 0.0  # S-mode integration time (ms)
    integration_time_p: float = 0.0  # P-mode integration time (ms)
    num_scans: int = 5  # Number of averaged scans

    # Timing parameters (separated LED and detector tracks)
    led_off_period: float = 5.0  # LED transition time between channels (ms)
    detector_wait_before: float = 35.0  # Wait for LED stabilization (ms)
    detector_window: float = 210.0  # Spectrum acquisition window (ms)
    detector_wait_after: float = 5.0  # Gap after detection (ms)

    # Legacy timing parameters (deprecated - for backward compatibility)
    pre_led_delay: float = 35.0  # DEPRECATED: Maps to detector_wait_before
    post_led_delay: float = 5.0  # DEPRECATED: Maps to led_off_period

    # Dark references (per-channel for S-pol and P-pol integration times)
    # CRITICAL: Dark current scales with integration time!
    dark_s: dict[str, np.ndarray] = field(
        default_factory=dict,
    )  # S-pol dark per channel
    dark_p: dict[str, np.ndarray] = field(
        default_factory=dict,
    )  # P-pol dark per channel

    # Per-channel integration times (alternative calibration mode)
    channel_integration_times: dict[str, float] = field(
        default_factory=dict,
    )  # P-mode per-channel (ms)

    # Quality metrics per channel
    metrics: dict[str, CalibrationMetrics] = field(default_factory=dict)

    # QC validation results (from 7-step calibration)
    transmission_validation: dict[str, dict] = field(default_factory=dict)

    # Timing synchronization results (from Step 6)
    # timing_sync deleted - old calibration code, not used

    # Convergence summary (from LED calibration Steps 3-5)
    convergence_summary: dict | None = None  # LED convergence results for QC report

    # Convergence iteration counts (from S- and P-mode engines)
    s_iterations: int = 0  # S-mode convergence iterations
    p_iterations: int = 0  # P-mode convergence iterations

    # Metadata
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    detector_serial: str = "Unknown"  # Device serial number
    roi_start: float = 560.0  # ROI start wavelength (nm)
    roi_end: float = 720.0  # ROI end wavelength (nm)

    # ROI indices into FULL detector spectrum (3648 pixels)
    # These are the indices used to crop the full spectrum to the ROI
    # CRITICAL: Must be stored from calibration, not recalculated!
    _wave_min_index: int = 0  # Index of roi_start in full detector spectrum
    _wave_max_index: int = 0  # Index of roi_end in full detector spectrum

    def __post_init__(self):
        """Validate calibration data."""
        # Validate channels
        expected_channels = {"a", "b", "c", "d"}
        ref_channels = set(self.s_pol_ref.keys())
        p_channels = set(self.p_mode_intensities.keys())
        s_channels = set(self.s_mode_intensities.keys())

        if ref_channels != expected_channels:
            raise ValueError(
                f"Missing reference channels: {expected_channels - ref_channels}",
            )
        if p_channels != expected_channels:
            raise ValueError(
                f"Missing P-mode intensities: {expected_channels - p_channels}",
            )
        if s_channels != expected_channels:
            raise ValueError(
                f"Missing S-mode intensities: {expected_channels - s_channels}",
            )

        # Validate wavelength array
        if len(self.wavelengths) == 0:
            raise ValueError("Empty wavelength array")

        # Validate each reference spectrum
        for channel, spectrum in self.s_pol_ref.items():
            if len(spectrum) != len(self.wavelengths):
                raise ValueError(
                    f"Channel {channel} spectrum length mismatch: "
                    f"{len(spectrum)} vs {len(self.wavelengths)} wavelengths",
                )
            if np.count_nonzero(spectrum) == 0:
                raise ValueError(f"Channel {channel} reference spectrum is all zeros")

    @property
    def channels(self) -> list[str]:
        """List of calibrated channels."""
        return sorted(self.s_pol_ref.keys())

    @property
    def num_points(self) -> int:
        """Number of wavelength points."""
        return len(self.wavelengths)

    @property
    def wavelength_range(self) -> tuple[float, float]:
        """Wavelength range (nm)."""
        return (float(self.wavelengths[0]), float(self.wavelengths[-1]))

    @property
    def datetime(self) -> datetime:
        """Calibration timestamp as datetime."""
        return datetime.fromtimestamp(self.timestamp)

    def get_reference(self, channel: str) -> np.ndarray:
        """Get reference spectrum for channel."""
        if channel not in self.s_pol_ref:
            raise KeyError(f"No reference for channel {channel}")
        return self.s_pol_ref[channel]

    def get_p_led(self, channel: str) -> int:
        """Get P-mode LED intensity for channel."""
        if channel not in self.p_mode_intensities:
            raise KeyError(f"No P-mode intensity for channel {channel}")
        return self.p_mode_intensities[channel]

    def get_s_led(self, channel: str) -> int:
        """Get S-mode LED intensity for channel."""
        if channel not in self.s_mode_intensities:
            raise KeyError(f"No S-mode intensity for channel {channel}")
        return self.s_mode_intensities[channel]

    def get_metrics(self, channel: str) -> CalibrationMetrics | None:
        """Get quality metrics for channel."""
        return self.metrics.get(channel)

    def is_channel_acceptable(self, channel: str) -> bool:
        """Check if channel calibration is acceptable."""
        metrics = self.get_metrics(channel)
        if metrics is None:
            return True  # No metrics = assume acceptable
        return metrics.is_acceptable()

    def all_channels_acceptable(self) -> bool:
        """Check if all channels have acceptable calibration."""
        return all(self.is_channel_acceptable(ch) for ch in self.channels)

    def copy(self) -> "CalibrationData":
        """Create a deep copy of calibration data."""
        return CalibrationData(
            s_pol_ref={k: v.copy() for k, v in self.s_pol_ref.items()},
            wavelengths=self.wavelengths.copy(),
            p_mode_intensities=self.p_mode_intensities.copy(),
            s_mode_intensities=self.s_mode_intensities.copy(),
            integration_time_s=self.integration_time_s,
            integration_time_p=self.integration_time_p,
            num_scans=self.num_scans,
            pre_led_delay=self.pre_led_delay,
            post_led_delay=self.post_led_delay,
            metrics=self.metrics.copy(),
            timestamp=self.timestamp,
            roi_start=self.roi_start,
            roi_end=self.roi_end,
            s_iterations=self.s_iterations,
            p_iterations=self.p_iterations,
        )

    # ============================================================================
    # BACKWARD COMPATIBILITY ALIASES
    # ============================================================================

    @property
    def wave_data(self) -> np.ndarray:
        """Alias for wavelengths (legacy naming)."""
        return self.wavelengths

    @property
    def s_mode_integration_time(self) -> float:
        """Alias for integration_time_s."""
        return self.integration_time_s

    @property
    def p_mode_integration_time(self) -> float:
        """Alias for integration_time_p."""
        return self.integration_time_p

    @property
    def pre_led_delay_ms(self) -> float:
        """DEPRECATED: Legacy accessor for pre_led_delay (maps to detector_wait_before)."""
        return self.detector_wait_before

    @property
    def post_led_delay_ms(self) -> float:
        """DEPRECATED: Legacy accessor for post_led_delay (maps to led_off_period)."""
        return self.led_off_period

    @property
    def cycle_time_ms(self) -> float:
        """Total cycle time per channel (ms)."""
        return self.led_off_period + (
            self.detector_wait_before + self.detector_window + self.detector_wait_after
        )

    @property
    def p_integration_time(self) -> float:
        """Alias for integration_time_p (backward compatibility)."""
        return self.integration_time_p

    @property
    def s_integration_time(self) -> float:
        """Alias for integration_time_s (backward compatibility)."""
        return self.integration_time_s

    # Additional backward compatibility properties for DataAcquisitionManager
    @property
    def integration_time(self) -> float:
        """Default integration time (P-mode preferred, fallback to S-mode)."""
        return self.integration_time_p if self.integration_time_p > 0 else self.integration_time_s

    @property
    def wavelength_min(self) -> float:
        """Minimum wavelength in range."""
        return float(self.wavelengths[0])

    @property
    def wavelength_max(self) -> float:
        """Maximum wavelength in range."""
        return float(self.wavelengths[-1])

    @property
    def wave_min_index(self) -> int:
        """Index of minimum wavelength in FULL detector spectrum.

        Returns the pixel index in the full 3648-pixel detector array
        where the ROI starts (e.g., pixel 750 for 560nm).
        """
        return self._wave_min_index

    @property
    def wave_max_index(self) -> int:
        """Index of maximum wavelength in FULL detector spectrum.

        Returns the pixel index in the full 3648-pixel detector array
        where the ROI ends (e.g., pixel 2746 for 720nm).
        """
        return self._wave_max_index

    def get_channels(self) -> list[str]:
        """Get list of calibrated channels (compatibility method)."""
        return self.channels

    def validate(self) -> bool:
        """Validate calibration data (compatibility method)."""
        try:
            # All validation happens in __post_init__
            # If we got this far, data is valid
            return True
        except Exception:
            return False

    @property
    def dark_noise(self) -> np.ndarray | None:
        """Dark noise spectrum (legacy property - not stored in domain model)."""
        # Domain model doesn't store dark noise (it's used during calibration only)
        # Return None for compatibility
        return None

    # NOTE: channel_integration_times is a regular dataclass field at line 78
    # No property wrapper needed - direct access to field works correctly

    def to_dict(self) -> dict:
        """Convert calibration data to dictionary for QC dialog and serialization.

        Returns:
            Dictionary with all calibration data in the format expected by CalibrationQCDialog

        """
        # Extract P-pol and transmission data from validation results if available
        p_pol_spectra = {}
        transmission_spectra = {}
        dark_scan = {}  # Legacy: Single dark per channel
        dark_s_scans = {}  # NEW: S-pol dark per channel
        dark_p_scans = {}  # NEW: P-pol dark per channel
        qc_validation = {}

        # NEW: Extract per-channel dark references if available
        if self.dark_s:
            dark_s_scans = {ch: dark.copy() for ch, dark in self.dark_s.items()}
        if self.dark_p:
            dark_p_scans = {ch: dark.copy() for ch, dark in self.dark_p.items()}

        if self.transmission_validation:
            for channel, validation_data in self.transmission_validation.items():
                if isinstance(validation_data, dict):
                    # Extract P-pol spectrum if available
                    if "p_pol_raw" in validation_data:
                        p_pol_spectra[channel] = validation_data["p_pol_raw"]
                    # Extract transmission spectrum if available
                    if "transmission" in validation_data:
                        transmission_spectra[channel] = validation_data["transmission"]
                    # Extract dark scan if available (legacy single dark)
                    if "dark_scan" in validation_data:
                        dark_scan[channel] = validation_data["dark_scan"]

                    # Extract QC metrics if available
                    if "qc_metrics" in validation_data:
                        qc_metrics = validation_data["qc_metrics"]
                        qc_validation[channel] = {
                            "transmission_min": qc_metrics.get(
                                "dip_depth",
                                0.0,
                            ),  # Positive percentage (dip depth)
                            "ratio": qc_metrics.get("p_s_ratio"),  # None if not calculated
                            "dip_detected": qc_metrics.get("dip_detected", False),
                            "fwhm": qc_metrics.get("fwhm", 0.0),
                            "reason": ", ".join(qc_metrics.get("warnings", []))
                            if qc_metrics.get("warnings")
                            else "OK",
                            "status": "PASS" if qc_metrics.get("overall_pass", False) else "FAIL",
                        }

        return {
            # Spectra
            "s_pol_spectra": self.s_pol_ref.copy(),
            "p_pol_spectra": p_pol_spectra,
            "dark_scan": dark_scan,  # Legacy: for backward compatibility
            "dark_s_scans": dark_s_scans,  # NEW: Per-channel S-pol darks
            "dark_p_scans": dark_p_scans,  # NEW: Per-channel P-pol darks
            "transmission_spectra": transmission_spectra,
            "wavelengths": self.wavelengths,
            # Acquisition parameters
            "integration_time": self.integration_time_s,
            "integration_time_s": self.integration_time_s,
            "integration_time_p": self.integration_time_p,
            "channel_integration_times": self.channel_integration_times.copy()
            if self.channel_integration_times
            else {},
            "num_scans": self.num_scans,
            # LED parameters
            "led_intensities": self.s_mode_intensities.copy(),
            "s_mode_intensities": self.s_mode_intensities.copy(),
            "p_mode_intensities": self.p_mode_intensities.copy(),
            # Timing parameters
            # Timing tracks (new architecture)
            "led_off_period": self.led_off_period,
            "detector_wait_before": self.detector_wait_before,
            "detector_window": self.detector_window,
            "detector_wait_after": self.detector_wait_after,
            "cycle_time_ms": self.cycle_time_ms,
            # Legacy timing (deprecated - for backward compatibility)
            "pre_led_delay": self.pre_led_delay,
            "post_led_delay": self.post_led_delay,
            # Metadata
            "timestamp": datetime.fromtimestamp(self.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S",
            ),
            "device_type": "USB4000",  # Default value
            "detector_serial": self.detector_serial,  # Use stored serial
            "firmware_version": "Unknown",  # Not stored in domain model
            # QC validation results (flattened for table display)
            "transmission_validation": qc_validation
            if qc_validation
            else self.transmission_validation,
            # Convergence summary (LED calibration Steps 3-5)
            "convergence_summary": (
                self.convergence_summary.copy()
                if isinstance(self.convergence_summary, dict)
                else None
            ),
            # ROI
            "roi_start": self.roi_start,
            "roi_end": self.roi_end,
            # Convergence iteration counts
            "s_iterations": self.s_iterations,
            "p_iterations": self.p_iterations,
        }
