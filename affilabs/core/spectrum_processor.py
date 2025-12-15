"""Spectrum Processing Module - Extracts spectrum processing logic from DataAcquisitionManager.

This module handles the conversion of raw detector data into processed transmission spectra,
following the same processing pipeline as calibration.

Responsibilities:
- Dark subtraction using SpectrumPreprocessor
- Transmission calculation using TransmissionProcessor
- Quality validation (LED detection, array alignment)
- Data preparation for peak finding

Extracted from DataAcquisitionManager to reduce file complexity (~500 lines).
"""

from __future__ import annotations

import builtins
import contextlib
import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from affilabs.core.calibration_data import CalibrationData

logger = logging.getLogger(__name__)


class SpectrumProcessor:
    """Processes raw detector spectra into transmission data.

    This class extracts the _process_spectrum logic from DataAcquisitionManager
    to create a cleaner separation of concerns.
    """

    def __init__(self, calibration_data: CalibrationData):
        """Initialize spectrum processor with calibration data.

        Args:
            calibration_data: Calibration parameters (dark refs, S-pol refs, etc.)
        """
        self.calibration_data = calibration_data

        # Processing state tracking
        self._process_entry_count = {}
        self._last_spectrum_hash = {}
        self._spol_ref_logged = set()
        self._ref_spectrum_logged = set()
        self._first_trans_calc = False
        self._trans_result_count = 0
        self._transmission_debug_counter = 0
        self._fallback_logged = False

    def process_spectrum(self, channel: str, spectrum_data: dict) -> dict:
        """Process raw spectrum into transmission (matches calibration Step 6).

        This function uses the exact same processing as calibration Step 6:
        - SpectrumPreprocessor.process_polarization_data() for dark subtraction
        - TransmissionProcessor.process_single_channel() for transmission

        Args:
            channel: Channel name ('a', 'b', 'c', or 'd')
            spectrum_data: Dict with 'raw_spectrum' (numpy array) and 'wavelength' from Layer 3

        Returns:
            Dict with processed transmission data

        Note: Processing parameters (baseline_method, baseline_percentile, etc.)
              MUST match calibration exactly to ensure consistency.
        """
        # Import processors here to avoid circular dependencies
        from affilabs.core.calibration.preprocessing import SpectrumPreprocessor
        from affilabs.core.calibration.transmission import TransmissionProcessor

        # DIAGNOSTIC: Entry point logging
        if channel not in self._process_entry_count:
            self._process_entry_count[channel] = 0
        self._process_entry_count[channel] += 1

        try:
            # Get truly raw data from Layer 3 (hardware acquisition)
            wavelength = spectrum_data["wavelength"]
            raw_intensity = spectrum_data["raw_spectrum"]  # Truly raw from detector

            # GUARD: Validate raw spectrum before processing
            if raw_intensity is None:
                return None
            if len(raw_intensity) == 0:
                return None
            if np.count_nonzero(raw_intensity) == 0:
                return None

            # CRITICAL: Apply ROI mask to match calibration wavelengths
            # Raw spectrum is 3840 pixels, but calibration data is already sliced
            # We need to slice raw data to match the CALIBRATED size (wavelengths array)
            if hasattr(self.calibration_data, "wavelengths") and len(
                self.calibration_data.wavelengths
            ) < len(raw_intensity):
                # Slice from the center or use wave_min_index as starting point
                if hasattr(self.calibration_data, "wave_min_index"):
                    start_idx = self.calibration_data.wave_min_index
                    end_idx = start_idx + len(self.calibration_data.wavelengths)
                    raw_intensity = raw_intensity[start_idx:end_idx]
                else:
                    # Fallback: slice to match wavelengths size from start
                    raw_intensity = raw_intensity[: len(self.calibration_data.wavelengths)]

            # CRITICAL QC: Check if LED actually turned on
            # If LEDs are off, spectrum should be dark-level (~2000-3000 counts)
            # If LEDs are on, spectrum should be significantly higher (>10,000 counts for typical setup)
            raw_peak = np.max(raw_intensity)
            raw_mean = np.mean(raw_intensity)

            # Get dark level for comparison
            if hasattr(self.calibration_data, "dark_p") and channel in self.calibration_data.dark_p:
                dark_ref_check = self.calibration_data.dark_p[channel]
                dark_peak = np.max(dark_ref_check) if dark_ref_check is not None else 3000
            else:
                dark_peak = 3000  # Typical dark level

            # LED ON should give at least 3X the dark level
            if raw_peak < dark_peak * 3.0:
                logger.warning(
                    f"[LED-OFF-DETECTED] Ch {channel}: Raw peak ({raw_peak:.0f}) is < 3X dark ({dark_peak:.0f}) "
                    f"- LED may not have turned on! Mean={raw_mean:.0f}"
                )

            # DIAGNOSTIC: Track whether spectrum data is changing between acquisitions
            try:
                spectrum_hash = hash(raw_intensity.tobytes())
                if channel in self._last_spectrum_hash:
                    if self._last_spectrum_hash[channel] == spectrum_hash:
                        pass
                self._last_spectrum_hash[channel] = spectrum_hash
            except Exception:
                pass

            # Get per-channel P-pol dark if available, otherwise fall back to legacy dark_noise
            if hasattr(self.calibration_data, "dark_p") and channel in self.calibration_data.dark_p:
                dark_ref = self.calibration_data.dark_p[channel]
            else:
                # Fallback to legacy dark_noise (backward compatibility)
                dark_ref = (
                    self.calibration_data.dark_noise
                    if hasattr(self.calibration_data, "dark_noise")
                    else None
                )
                # Legacy dark_noise needs slicing to match calibration size
                if dark_ref is not None and hasattr(self.calibration_data, "wavelengths"):
                    if len(dark_ref) > len(self.calibration_data.wavelengths):
                        if hasattr(self.calibration_data, "wave_min_index"):
                            start_idx = self.calibration_data.wave_min_index
                            end_idx = start_idx + len(self.calibration_data.wavelengths)
                            dark_ref = dark_ref[start_idx:end_idx]
                        else:
                            dark_ref = dark_ref[: len(self.calibration_data.wavelengths)]

            clean_spectrum = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=raw_intensity,
                dark_noise=dark_ref,
                channel_name=channel,
                verbose=False,  # Suppress logging for performance
            )

            # GUARD: Validate clean spectrum after preprocessing
            if clean_spectrum is None:
                return None
            if len(clean_spectrum) == 0:
                return None

            # Store clean spectrum (dark-corrected)
            raw_spectrum = clean_spectrum  # Ready for transmission calculation
            intensity = clean_spectrum  # For peak finding

            # LAYER 4: Calculate transmission spectrum using TransmissionProcessor
            transmission_spectrum = None

            # DIAGNOSTIC: Log s_pol_ref dictionary state on first call per channel
            if channel not in self._spol_ref_logged:
                self._spol_ref_logged.add(channel)

            if (
                channel in self.calibration_data.s_pol_ref
                and self.calibration_data.s_pol_ref[channel] is not None
            ):
                try:
                    ref_spectrum = self.calibration_data.s_pol_ref[channel]

                    # GUARD: Validate ref_spectrum and array alignment
                    if (
                        ref_spectrum is None
                        or len(ref_spectrum) == 0
                        or len(clean_spectrum) != len(ref_spectrum)
                    ):
                        logger.warning(
                            f"[RANK] Channel {channel} array size mismatch: clean={len(clean_spectrum)}, ref={len(ref_spectrum)}"
                        )
                        transmission_spectrum = None
                    else:
                        # CRITICAL DIAGNOSTIC: Log reference spectrum values
                        if channel not in self._ref_spectrum_logged:
                            self._ref_spectrum_logged.add(channel)
                            if np.count_nonzero(ref_spectrum) == 0:
                                pass

                        # Arrays are valid and aligned - proceed with calculation
                        # Get LED intensities
                        p_led = self.calibration_data.p_mode_intensities.get(channel, 255)
                        s_led = self.calibration_data.s_mode_intensities.get(channel, 200)

                        # DEBUG: Log first transmission calculation inputs
                        if not self._first_trans_calc:
                            # CRITICAL DEBUG: Check if arrays are aligned
                            if len(clean_spectrum) != len(ref_spectrum):
                                pass

                            if len(clean_spectrum) != len(self.calibration_data.wavelengths):
                                pass

                            self._first_trans_calc = True

                        transmission_spectrum = TransmissionProcessor.process_single_channel(
                            p_pol_clean=clean_spectrum,
                            s_pol_ref=ref_spectrum,
                            led_intensity_s=s_led,
                            led_intensity_p=p_led,
                            wavelengths=self.calibration_data.wavelengths,
                            apply_sg_filter=True,
                            baseline_method="percentile",
                            baseline_percentile=95.0,
                            verbose=(not self._first_trans_calc),
                        )

                        # GUARD: Validate transmission result
                        if transmission_spectrum is None:
                            pass
                        elif len(transmission_spectrum) == 0:
                            transmission_spectrum = None
                        elif np.count_nonzero(transmission_spectrum) == 0:
                            pass
                        elif np.isnan(transmission_spectrum).all():
                            transmission_spectrum = None

                    # DEBUG: Log first 3 transmission results
                    if self._trans_result_count < 3:
                        if transmission_spectrum is not None:
                            np.count_nonzero(transmission_spectrum) == 0
                        self._trans_result_count += 1

                    # Debug log LED correction (throttled)
                    self._transmission_debug_counter += 1

                except Exception:
                    with contextlib.suppress(builtins.BaseException):
                        pass
                    transmission_spectrum = None

            # Guard: if transmission_spectrum is invalid, fall back to intensity
            peak_input = transmission_spectrum if transmission_spectrum is not None else intensity
            fallback_reason = None
            try:
                if transmission_spectrum is not None:
                    if len(transmission_spectrum) == 0:
                        peak_input = intensity
                        fallback_reason = "empty array"
                    elif np.isnan(transmission_spectrum).all():
                        peak_input = intensity
                        fallback_reason = "all NaN"
                    elif np.count_nonzero(transmission_spectrum) == 0:
                        peak_input = intensity
                        fallback_reason = "all zeros"
                else:
                    fallback_reason = "None returned"

                # Log fallback only for first few occurrences
                if fallback_reason and not self._fallback_logged:
                    self._fallback_logged = True
            except Exception:
                pass

            # Calculate minimum hint from smoothed transmission
            minimum_hint_nm = None
            if (
                transmission_spectrum is not None
                and len(transmission_spectrum) > 0
                and len(wavelength) == len(transmission_spectrum)
            ):
                # Find indices for SPR region
                spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
                if np.any(spr_mask):
                    spr_transmission = transmission_spectrum[spr_mask]
                    spr_wavelengths = wavelength[spr_mask]
                    min_idx_in_region = np.argmin(spr_transmission)
                    minimum_hint_nm = spr_wavelengths[min_idx_in_region]

            return {
                "intensity": intensity,
                "raw_spectrum": raw_spectrum,
                "transmission_spectrum": transmission_spectrum,
                "peak_input": peak_input,
                "minimum_hint_nm": minimum_hint_nm,
                "wavelength": wavelength,
            }

        except Exception:
            with contextlib.suppress(builtins.BaseException):
                pass
            return None
