from dataclasses import dataclass, field

import numpy as np


@dataclass
class LEDCalibrationResult:
    success: bool = False
    error: str | None = None

    # Wavelength data
    # NOTE: wave_data and wavelengths are ALIASES (same array, different names for backward compatibility)
    # - wave_data: Legacy name from original calibration code
    # - wavelengths: Modern name used in live acquisition
    # Both point to the SPR-filtered wavelength range (e.g., 560-750nm)
    full_wavelengths: np.ndarray | None = None  # Full detector range (e.g., 337-1020nm)
    wave_data: np.ndarray | None = None  # SPR-filtered range (legacy name)
    wavelengths: np.ndarray | None = (
        None  # SPR-filtered range (modern name, same as wave_data)
    )
    wave_min_index: int | None = None  # Start index of SPR range in full spectrum
    wave_max_index: int | None = None  # End index of SPR range in full spectrum

    # Detector
    detector_max_counts: int | None = None
    detector_saturation_threshold: int | None = None

    # Polarizer positions
    polarizer_s_position: int | None = None
    polarizer_p_position: int | None = None
    polarizer_sp_ratio: float | None = None

    # Ranking & normalization
    led_ranking: list | None = None
    weakest_channel: str | None = None
    # LED intensities
    # NOTE: Multiple naming conventions for historical reasons:
    # - s_mode_intensity: S-mode LED intensities (legacy)
    # - ref_intensity: Same as s_mode_intensity (alias)
    # - p_mode_intensity: P-mode LED intensities (final calibrated values)
    # - normalized_leds: Intermediate normalized values (Step 3C)
    s_mode_intensity: dict[str, int] = field(
        default_factory=dict,
    )  # S-mode LED intensities
    ref_intensity: dict[str, int] = field(
        default_factory=dict,
    )  # Alias for s_mode_intensity
    normalized_leds: dict[str, int] = field(default_factory=dict)  # Step 3C output
    brightness_ratios: dict[str, float] = field(
        default_factory=dict,
    )  # For alternative mode (LED=255 fixed)

    # Integration times (ms)
    # NOTE: Different naming for S vs P mode:
    # - s_integration_time / s_mode_integration_time: Both refer to S-mode integration time
    # - p_integration_time / p_mode_integration_time: Both refer to P-mode integration time
    # - channel_integration_times: Per-channel P-mode times (alternative calibration mode)
    s_integration_time: float | None = None  # S-mode integration time (ms)
    p_integration_time: float | None = None  # P-mode integration time (ms)
    channel_integration_times: dict[str, float] = field(
        default_factory=dict,
    )  # Per-channel P-mode integration times

    # ROI signal measurements (Step 4 and Step 5)
    s_roi1_signals: dict[str, float] = field(
        default_factory=dict,
    )  # S-mode ROI1 (560-570nm)
    s_roi2_signals: dict[str, float] = field(
        default_factory=dict,
    )  # S-mode ROI2 (710-720nm)
    p_roi1_signals: dict[str, float] = field(
        default_factory=dict,
    )  # P-mode ROI1 (560-570nm)
    p_roi2_signals: dict[str, float] = field(
        default_factory=dict,
    )  # P-mode ROI2 (710-720nm)

    # OLD LED timing delays deleted - replaced by new timing architecture
    # All timing now in settings: LED_ON_TIME_MS, DETECTOR_WAIT_MS, NUM_SCANS, SAFETY_BUFFER_MS

    # Cycle time metrics (for 1Hz constraint validation)
    cycle_time_ms: float | None = None
    acquisition_rate_hz: float | None = None

    # Raw and processed data
    num_scans: int = 5

    # Dark noise reference
    dark_noise: np.ndarray | None = None  # Dark spectrum for QC reconstruction

    # Reference spectra (clean, preprocessed by SpectrumPreprocessor)
    # SHARED WITH LIVE ACQUISITION: These are used in TransmissionProcessor.process_single_channel()
    # - s_pol_ref: S-polarization reference spectra (dark-subtracted, used as denominator in P/S ratio)
    # - p_pol_ref: P-polarization reference spectra (dark-subtracted, used for QC validation)
    # Both calibration and live acquisition use s_pol_ref for transmission calculation
    s_pol_ref: dict[str, np.ndarray] = field(
        default_factory=dict,
    )  # S-mode references (for P/S transmission)
    p_pol_ref: dict[str, np.ndarray] = field(
        default_factory=dict,
    )  # P-mode references (for QC)

    transmission: dict[str, np.ndarray] = field(default_factory=dict)
    afterglow_curves: dict[str, np.ndarray] = field(default_factory=dict)

    # Final LEDs (for compatibility)
    leds_calibrated: dict[str, int] = field(default_factory=dict)

    # QC results
    qc_results: dict[str, dict[str, float]] = field(default_factory=dict)
    p_mode_intensity: dict[str, int] = field(default_factory=dict)

    # timing_sync deleted - old calibration code

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
                p_pol_raw[ch] = (
                    self.p_pol_ref[ch] + self.dark_noise
                    if ch in self.p_pol_ref
                    else self.s_pol_ref[ch]
                )
        else:
            s_pol_raw = self.s_pol_ref
            p_pol_raw = self.p_pol_ref

        # UI-only safeguard: if S/P appear inverted across most channels,
        # swap display mapping to match expected labels without altering stored data.
        sp_swap_applied = False
        try:
            ratios = []
            for ch in self.s_pol_ref.keys():
                s_max = (
                    float(np.max(self.s_pol_ref[ch]))
                    if ch in self.s_pol_ref and self.s_pol_ref[ch] is not None
                    else 0.0
                )
                p_max = (
                    float(np.max(self.p_pol_ref[ch]))
                    if ch in self.p_pol_ref and self.p_pol_ref[ch] is not None
                    else 0.0
                )
                if s_max > 0:
                    ratios.append(p_max / s_max)
            # If majority clearly > 1.15, assume labels inverted in capture/mapping
            if ratios and sum(1 for r in ratios if r > 1.15) >= max(
                1,
                len(ratios) // 2 + 1,
            ):
                s_pol_raw, p_pol_raw = p_pol_raw, s_pol_raw
                sp_swap_applied = True
        except Exception:
            # Do not fail QC rendering due to heuristic; keep original mapping
            sp_swap_applied = False

        return {
            "s_pol_spectra": s_pol_raw,
            "p_pol_spectra": p_pol_raw,
            "sp_swap_applied": sp_swap_applied,
            "dark_scan": {ch: self.dark_noise for ch in self.s_pol_ref.keys()}
            if self.dark_noise is not None
            else {},
            "afterglow_curves": self.afterglow_curves,
            "transmission_spectra": self.transmission,
            "wavelengths": self.wave_data,
            "integration_time": self.s_integration_time,
            "p_integration_time": self.p_integration_time,
            "led_intensities": self.p_mode_intensity,
            "spr_fwhm": getattr(self, "spr_fwhm", {}),
            "num_scans": self.num_scans,
            "timing_sync": self.timing_sync,  # Step 6 timing synchronization metrics
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
    def integration_time(self) -> float | None:
        """Alias for s_integration_time (primary integration time)."""
        return self.s_integration_time

    @property
    def s_mode_integration_time(self) -> float | None:
        """Alias for s_integration_time."""
        return self.s_integration_time

    @property
    def p_mode_intensities(self) -> dict[str, int]:
        """Alias for p_mode_intensity (with correct plural form)."""
        return self.p_mode_intensity

    @property
    def s_mode_intensities(self) -> dict[str, int]:
        """Alias for s_mode_intensity (with correct plural form)."""
        return self.s_mode_intensity

    @property
    def wavelength_min(self) -> float | None:
        """Minimum wavelength in SPR range."""
        return (
            float(self.wave_data[0])
            if self.wave_data is not None and len(self.wave_data) > 0
            else None
        )

    @property
    def wavelength_max(self) -> float | None:
        """Maximum wavelength in SPR range."""
        return (
            float(self.wave_data[-1])
            if self.wave_data is not None and len(self.wave_data) > 0
            else None
        )
