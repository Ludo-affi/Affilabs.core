from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

@dataclass
class LEDCalibrationResult:
    success: bool = False
    error: Optional[str] = None

    # Wavelength data
    full_wavelengths: Optional[np.ndarray] = None
    wave_data: Optional[np.ndarray] = None
    wavelengths: Optional[np.ndarray] = None
    wave_min_index: Optional[int] = None
    wave_max_index: Optional[int] = None

    # Detector
    detector_max_counts: Optional[int] = None
    detector_saturation_threshold: Optional[int] = None

    # Polarizer positions
    polarizer_s_position: Optional[int] = None
    polarizer_p_position: Optional[int] = None
    polarizer_sp_ratio: Optional[float] = None

    # Ranking & normalization
    led_ranking: Optional[list] = None
    weakest_channel: Optional[str] = None
    s_mode_intensity: Dict[str, int] = field(default_factory=dict)
    ref_intensity: Dict[str, int] = field(default_factory=dict)
    normalized_leds: Dict[str, int] = field(default_factory=dict)  # Step 3C output
    brightness_ratios: Dict[str, float] = field(default_factory=dict)  # For alternative mode (LED=255 fixed)

    # Integration times (ms)
    s_integration_time: Optional[float] = None
    p_integration_time: Optional[float] = None
    channel_integration_times: Dict[str, float] = field(default_factory=dict)  # Per-channel P-mode integration times

    # ROI signal measurements (Step 4 and Step 5)
    s_roi1_signals: Dict[str, float] = field(default_factory=dict)  # S-mode ROI1 (560-570nm)
    s_roi2_signals: Dict[str, float] = field(default_factory=dict)  # S-mode ROI2 (710-720nm)
    p_roi1_signals: Dict[str, float] = field(default_factory=dict)  # P-mode ROI1 (560-570nm)
    p_roi2_signals: Dict[str, float] = field(default_factory=dict)  # P-mode ROI2 (710-720nm)

    # LED timing delays (ms)
    pre_led_delay_ms: Optional[float] = None
    post_led_delay_ms: Optional[float] = None

    # Cycle time metrics (for 1Hz constraint validation)
    cycle_time_ms: Optional[float] = None
    acquisition_rate_hz: Optional[float] = None

    # Raw and processed data
    num_scans: int = 5
    s_raw_data: Dict[str, np.ndarray] = field(default_factory=dict)
    p_raw_data: Dict[str, np.ndarray] = field(default_factory=dict)
    dark_noise: Optional[np.ndarray] = None

    # Modern architecture: s_pol_ref and p_pol_ref (clean spectra from SpectrumPreprocessor)
    s_pol_ref: Dict[str, np.ndarray] = field(default_factory=dict)
    p_pol_ref: Dict[str, np.ndarray] = field(default_factory=dict)

    transmission: Dict[str, np.ndarray] = field(default_factory=dict)
    afterglow_curves: Dict[str, np.ndarray] = field(default_factory=dict)

    # Final LEDs (for compatibility)
    leds_calibrated: Dict[str, int] = field(default_factory=dict)

    # QC results
    qc_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    p_mode_intensity: Dict[str, int] = field(default_factory=dict)

    # Diagnostic data
    ch_error_list: list = field(default_factory=list)  # List of channels that failed QC

    def validate(self) -> bool:
        """Validate that calibration data is complete.

        Returns:
            True if calibration has minimum required data for acquisition
        """
        # Must have successful calibration
        if not self.success:
            return False

        # Must have P-mode intensities (required for acquisition)
        if not self.p_mode_intensity:
            return False

        # Must have reference spectra
        if not self.s_pol_ref:
            return False

        # Must have wavelength data
        if self.wave_data is None or len(self.wave_data) == 0:
            return False

        # Must have integration times
        if not self.s_integration_time or self.s_integration_time <= 0:
            return False

        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for QC display.

        Returns:
            Dictionary with calibration data for UI display
        """
        # Reconstruct RAW spectra for QC (add dark back if available)
        s_pol_raw = {}
        p_pol_raw = {}

        if self.dark_noise is not None:
            for ch in self.s_pol_ref.keys():
                s_pol_raw[ch] = self.s_pol_ref[ch] + self.dark_noise
                p_pol_raw[ch] = self.p_pol_ref[ch] + self.dark_noise if ch in self.p_pol_ref else self.s_pol_ref[ch]
        else:
            s_pol_raw = self.s_pol_ref
            p_pol_raw = self.p_pol_ref

        return {
            's_pol_spectra': s_pol_raw,
            'p_pol_spectra': p_pol_raw,
            'dark_scan': {ch: self.dark_noise for ch in self.s_pol_ref.keys()} if self.dark_noise is not None else {},
            'afterglow_curves': self.afterglow_curves,
            'transmission_spectra': self.transmission,
            'wavelengths': self.wave_data,
            'integration_time': self.s_integration_time,
            'p_integration_time': self.p_integration_time,
            'led_intensities': self.p_mode_intensity,
            'spr_fwhm': getattr(self, 'spr_fwhm', {}),
            'num_scans': self.num_scans,
        }

    def get_channels(self) -> list:
        """Get list of calibrated channels.

        Returns:
            List of channel identifiers
        """
        return sorted(self.s_pol_ref.keys()) if self.s_pol_ref else []

    # ============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES (data_acquisition_manager expects these)
    # ============================================================================

    @property
    def integration_time(self) -> Optional[float]:
        """Alias for s_integration_time (primary integration time)."""
        return self.s_integration_time

    @property
    def s_mode_integration_time(self) -> Optional[float]:
        """Alias for s_integration_time."""
        return self.s_integration_time

    @property
    def p_mode_intensities(self) -> Dict[str, int]:
        """Alias for p_mode_intensity (with correct plural form)."""
        return self.p_mode_intensity

    @property
    def s_mode_intensities(self) -> Dict[str, int]:
        """Alias for s_mode_intensity (with correct plural form)."""
        return self.s_mode_intensity

    @property
    def wavelength_min(self) -> Optional[float]:
        """Minimum wavelength in SPR range."""
        return float(self.wave_data[0]) if self.wave_data is not None and len(self.wave_data) > 0 else None

    @property
    def wavelength_max(self) -> Optional[float]:
        """Maximum wavelength in SPR range."""
        return float(self.wave_data[-1]) if self.wave_data is not None and len(self.wave_data) > 0 else None
