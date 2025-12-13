from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

@dataclass
class LEDCalibrationResult:
    success: bool = False
    error: Optional[str] = None

    # Wavelength data
    # NOTE: wave_data and wavelengths are ALIASES (same array, different names for backward compatibility)
    # - wave_data: Legacy name from original calibration code
    # - wavelengths: Modern name used in live acquisition
    # Both point to the SPR-filtered wavelength range (e.g., 560-750nm)
    full_wavelengths: Optional[np.ndarray] = None  # Full detector range (e.g., 337-1020nm)
    wave_data: Optional[np.ndarray] = None  # SPR-filtered range (legacy name)
    wavelengths: Optional[np.ndarray] = None  # SPR-filtered range (modern name, same as wave_data)
    wave_min_index: Optional[int] = None  # Start index of SPR range in full spectrum
    wave_max_index: Optional[int] = None  # End index of SPR range in full spectrum

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
    # LED intensities
    # NOTE: Multiple naming conventions for historical reasons:
    # - s_mode_intensity: S-mode LED intensities (legacy)
    # - ref_intensity: Same as s_mode_intensity (alias)
    # - p_mode_intensity: P-mode LED intensities (final calibrated values)
    # - normalized_leds: Intermediate normalized values (Step 3C)
    s_mode_intensity: Dict[str, int] = field(default_factory=dict)  # S-mode LED intensities
    ref_intensity: Dict[str, int] = field(default_factory=dict)  # Alias for s_mode_intensity
    normalized_leds: Dict[str, int] = field(default_factory=dict)  # Step 3C output
    brightness_ratios: Dict[str, float] = field(default_factory=dict)  # For alternative mode (LED=255 fixed)

    # Integration times (ms)
    # NOTE: Different naming for S vs P mode:
    # - s_integration_time / s_mode_integration_time: Both refer to S-mode integration time
    # - p_integration_time / p_mode_integration_time: Both refer to P-mode integration time
    # - channel_integration_times: Per-channel P-mode times (alternative calibration mode)
    s_integration_time: Optional[float] = None  # S-mode integration time (ms)
    p_integration_time: Optional[float] = None  # P-mode integration time (ms)
    channel_integration_times: Dict[str, float] = field(default_factory=dict)  # Per-channel P-mode integration times

    # ROI signal measurements (Step 4 and Step 5)
    s_roi1_signals: Dict[str, float] = field(default_factory=dict)  # S-mode ROI1 (560-570nm)
    s_roi2_signals: Dict[str, float] = field(default_factory=dict)  # S-mode ROI2 (710-720nm)
    p_roi1_signals: Dict[str, float] = field(default_factory=dict)  # P-mode ROI1 (560-570nm)
    p_roi2_signals: Dict[str, float] = field(default_factory=dict)  # P-mode ROI2 (710-720nm)

    # LED timing delays (ms)
    # SHARED WITH LIVE ACQUISITION: These exact timing values are reused in data_acquisition_manager
    # - pre_led_delay_ms: LED stabilization time before spectrum acquisition (typically 12ms)
    # - post_led_delay_ms: Afterglow decay time after LED off (typically 40ms)
    # Same timing ensures calibration and live data match
    pre_led_delay_ms: Optional[float] = None  # LED stabilization delay (used in acquire_raw_spectrum)
    post_led_delay_ms: Optional[float] = None  # Afterglow decay delay (used in acquire_raw_spectrum)

    # Cycle time metrics (for 1Hz constraint validation)
    cycle_time_ms: Optional[float] = None
    acquisition_rate_hz: Optional[float] = None

    # Raw and processed data
    num_scans: int = 5

    # Dark noise reference
    dark_noise: Optional[np.ndarray] = None  # Dark spectrum for QC reconstruction

    # Reference spectra (clean, preprocessed by SpectrumPreprocessor)
    # SHARED WITH LIVE ACQUISITION: These are used in TransmissionProcessor.process_single_channel()
    # - s_pol_ref: S-polarization reference spectra (dark-subtracted, used as denominator in P/S ratio)
    # - p_pol_ref: P-polarization reference spectra (dark-subtracted, used for QC validation)
    # Both calibration and live acquisition use s_pol_ref for transmission calculation
    s_pol_ref: Dict[str, np.ndarray] = field(default_factory=dict)  # S-mode references (for P/S transmission)
    p_pol_ref: Dict[str, np.ndarray] = field(default_factory=dict)  # P-mode references (for QC)

    transmission: Dict[str, np.ndarray] = field(default_factory=dict)
    afterglow_curves: Dict[str, np.ndarray] = field(default_factory=dict)

    # Final LEDs (for compatibility)
    leds_calibrated: Dict[str, int] = field(default_factory=dict)

    # QC results
    qc_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    p_mode_intensity: Dict[str, int] = field(default_factory=dict)

    # Timing synchronization metrics (Step 6)
    # Contains: avg_cycle_ms, std_cycle_ms, jitter_percent, status ('PASS'/'FAIL')
    timing_sync: Optional[Dict[str, float]] = None

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

        # UI-only safeguard: if S/P appear inverted across most channels,
        # swap display mapping to match expected labels without altering stored data.
        sp_swap_applied = False
        try:
            ratios = []
            for ch in self.s_pol_ref.keys():
                s_max = float(np.max(self.s_pol_ref[ch])) if ch in self.s_pol_ref and self.s_pol_ref[ch] is not None else 0.0
                p_max = float(np.max(self.p_pol_ref[ch])) if ch in self.p_pol_ref and self.p_pol_ref[ch] is not None else 0.0
                if s_max > 0:
                    ratios.append(p_max / s_max)
            # If majority clearly > 1.15, assume labels inverted in capture/mapping
            if ratios and sum(1 for r in ratios if r > 1.15) >= max(1, len(ratios) // 2 + 1):
                s_pol_raw, p_pol_raw = p_pol_raw, s_pol_raw
                sp_swap_applied = True
        except Exception:
            # Do not fail QC rendering due to heuristic; keep original mapping
            sp_swap_applied = False

        return {
            's_pol_spectra': s_pol_raw,
            'p_pol_spectra': p_pol_raw,
            'sp_swap_applied': sp_swap_applied,
            'dark_scan': {ch: self.dark_noise for ch in self.s_pol_ref.keys()} if self.dark_noise is not None else {},
            'afterglow_curves': self.afterglow_curves,
            'transmission_spectra': self.transmission,
            'wavelengths': self.wave_data,
            'integration_time': self.s_integration_time,
            'p_integration_time': self.p_integration_time,
            'led_intensities': self.p_mode_intensity,
            'spr_fwhm': getattr(self, 'spr_fwhm', {}),
            'num_scans': self.num_scans,
            'timing_sync': self.timing_sync,  # Step 6 timing synchronization metrics
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
