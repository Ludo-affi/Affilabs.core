"""Transmission spectrum processor - Core business logic (Layer 2).

Single source of truth for P/S ratio calculations used throughout application.
This consolidates transmission calculation logic from:
- data_acquisition_manager.py (live acquisition)
- calibration_6step.py (QC display)

IMPORTANT: TransmissionProcessor expects CLEAN spectra (dark and afterglow already removed).
Use SpectrumPreprocessor before calling TransmissionProcessor methods.

Created: November 27, 2025
Architecture: Layer 2 (Core Business Logic)
"""

import numpy as np

from utils.logger import logger


class TransmissionProcessor:
    """Process clean P-pol spectra into transmission spectra.

    This is the ONLY place where transmission calculation logic should exist.
    Used by:
    - Calibration QC display
    - Live data acquisition
    - Post-calibration analysis

    Pipeline steps:
    1. Calculate P/S ratio
    2. Correct for LED boost (P_LED / S_LED)
    3. Apply baseline correction (method-dependent):
       - 'percentile': Use Nth percentile (default: 95th) - assumes flat off-SPR
       - 'polynomial': Fit polynomial to remove OPTICAL tilt (polarizer/detector wavelength response)
       - 'off_spr': Use off-SPR region (560-570nm) for physics-based baseline
       - 'none': Skip baseline correction (preserves all SPR physics + optical artifacts)

       ⚠️  CRITICAL: Polynomial correction removes OPTICAL wavelength dependence, NOT SPR physics!
           SPR has intrinsic wavelength-dependent sensitivity - polynomial should flatten
           OPTICAL artifacts (polarizer extinction, detector QE) but preserve SPR shape.

    4. Clip to 0-100% range
    5. Apply Savitzky-Golay filter (optional)

    Note: Input spectra must be preprocessed (use SpectrumPreprocessor first)
    """

    @staticmethod
    def process_single_channel(
        p_pol_clean: np.ndarray,
        s_pol_ref: np.ndarray,
        led_intensity_s: int = 200,
        led_intensity_p: int = 255,
        wavelengths: np.ndarray | None = None,
        apply_sg_filter: bool = True,
        baseline_method: str = "percentile",
        baseline_percentile: float = 95.0,
        baseline_polynomial_degree: int = 2,
        off_spr_wavelength_range: tuple | None = None,
        verbose: bool = False,
    ) -> np.ndarray:
        """Process ONE channel with transmission calculation pipeline.

        IMPORTANT: Input spectra must be PREPROCESSED (dark and afterglow already removed).
        Use SpectrumPreprocessor.process_polarization_data() before calling this method.

        Args:
            p_pol_clean: CLEAN P-mode spectrum (dark and afterglow already removed)
            s_pol_ref: CLEAN S-mode reference spectrum (dark and afterglow already removed)
            led_intensity_s: S-mode LED intensity for this channel
            led_intensity_p: P-mode LED intensity for this channel
            wavelengths: Wavelength array (for logging and off-SPR baseline)
            apply_sg_filter: Apply Savitzky-Golay smoothing (default: True)
            baseline_method: Baseline correction method:
                - 'percentile': Use Nth percentile (simple, robust)
                - 'polynomial': Fit polynomial to flatten LED spectral profile
                - 'off_spr': Use off-SPR region (560-570nm) for physics-based baseline
                - 'none': Skip baseline correction
            baseline_percentile: Percentile for 'percentile' method (default: 95.0)
            baseline_polynomial_degree: Polynomial degree for 'polynomial' method (default: 2)
            off_spr_wavelength_range: Tuple (min_wl, max_wl) for 'off_spr' method (default: (560, 570))
            verbose: Enable detailed logging (for QC display)

        Returns:
            transmission: Transmission spectrum (%)

        Pipeline:
            1. Calculate P/S ratio
            2. Correct for LED boost (P_LED / S_LED)
            3. Apply baseline correction (method-dependent)
            4. Clip to 0-100% range
            5. Apply Savitzky-Golay filter (optional)

        """
        if verbose:
            logger.info("=" * 80)
            logger.info("TransmissionProcessor: Clean P-pol → Transmission")
            logger.info("=" * 80)
            logger.info(
                f"   P-pol clean: mean={np.mean(p_pol_clean):.0f}, max={np.max(p_pol_clean):.0f}",
            )

        # Step 1: Calculate transmission (P / S)
        # Step 1: Calculate transmission (P / S)
        s_pol_safe = np.where(s_pol_ref < 1, 1, s_pol_ref)
        raw_transmission = (p_pol_clean / s_pol_safe) * 100.0

        if verbose:
            logger.info(
                f"Step 1: Raw transmission (P/S): mean={np.mean(raw_transmission):.1f}%",
            )

        # Step 2: LED boost correction (P_LED / S_LED)
        led_boost_factor = max(led_intensity_p, 1) / max(led_intensity_s, 1)
        transmission = raw_transmission / led_boost_factor

        if verbose:
            logger.info("Step 2: LED boost correction")
            logger.info(
                f"   LED boost: S={led_intensity_s}, P={led_intensity_p}, factor={led_boost_factor:.3f}",
            )
            logger.info(
                f"   Transmission after LED correction: mean={np.mean(transmission):.1f}%",
            )

        # Step 3: Baseline correction (method-dependent)
        if baseline_method == "percentile":
            # Method 1: Simple percentile (robust, fast)
            baseline = np.percentile(transmission, baseline_percentile)
            transmission = transmission - baseline + 100.0

            if verbose:
                logger.info("Step 3: Baseline correction (percentile method)")
                logger.info(f"   {baseline_percentile}th percentile: {baseline:.2f}%")
                logger.info("   Re-centered to 100% baseline")

        elif baseline_method == "polynomial":
            # Method 2: Polynomial fit to remove LED spectral profile skew
            x = np.linspace(0, 1, len(transmission))
            coeffs = np.polyfit(x, transmission, baseline_polynomial_degree)
            baseline = np.polyval(coeffs, x)

            # Avoid division by very small values
            baseline = np.where(baseline < 1.0, 1.0, baseline)

            # Divide by baseline to flatten, then re-center to 100%
            transmission = (transmission / baseline) * 100.0

            if verbose:
                logger.info("Step 3: Baseline correction (polynomial method)")
                logger.info(f"   Polynomial degree: {baseline_polynomial_degree}")
                logger.info("   Flattened LED spectral profile")

        elif baseline_method == "off_spr":
            # Method 3: Physics-based off-SPR region baseline
            if wavelengths is not None:
                if off_spr_wavelength_range is None:
                    off_spr_wavelength_range = (560.0, 570.0)

                min_wl, max_wl = off_spr_wavelength_range
                off_spr_mask = (wavelengths >= min_wl) & (wavelengths <= max_wl)

                if np.any(off_spr_mask):
                    baseline = np.mean(transmission[off_spr_mask])
                    transmission = transmission - baseline + 100.0

                    if verbose:
                        logger.info(
                            "Step 3: Baseline correction (off-SPR region method)",
                        )
                        logger.info(f"   Off-SPR region: {min_wl}-{max_wl}nm")
                        logger.info(f"   Baseline: {baseline:.2f}%")
                        logger.info("   Re-centered to 100% baseline")
                elif verbose:
                    logger.warning(
                        f"Step 3: Off-SPR region {min_wl}-{max_wl}nm not available",
                    )
                    logger.info("   Skipping baseline correction")
            elif verbose:
                logger.warning("Step 3: Wavelengths not provided for off-SPR baseline")
                logger.info("   Skipping baseline correction")

        elif baseline_method == "none":
            if verbose:
                logger.info("Step 3: Baseline correction disabled")
        else:
            logger.warning(
                f"Unknown baseline method '{baseline_method}', skipping correction",
            )

        # Step 4: No clipping - allow full dynamic range of transmission data
        # Transmission can exceed 100% (S/P formula produces values >100%)
        # and can go below 0% due to noise or baseline corrections

        # Step 5: Savitzky-Golay filter (optional)
        if apply_sg_filter and len(transmission) >= 11:
            from scipy.signal import savgol_filter

            transmission = savgol_filter(transmission, window_length=11, polyorder=3)
            if verbose:
                logger.info("Step 4: Applied Savitzky-Golay filter (window=11, poly=3)")

        # Log final result
        if verbose and wavelengths is not None:
            min_transmission = np.min(transmission)
            min_idx = np.argmin(transmission)
            min_wavelength = wavelengths[min_idx]
            logger.info("\n✅ Final transmission spectrum:")
            logger.info(
                f"   SPR dip: {min_transmission:.1f}% at {min_wavelength:.1f}nm",
            )
            logger.info(f"   Mean: {np.mean(transmission):.1f}%")
            logger.info("=" * 80)

        return transmission

    @staticmethod
    def diagnose_spectral_tilt(
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        spr_region: tuple = (640, 680),
        off_spr_regions: list = None,
    ) -> dict:
        """Diagnose cause of spectral tilt in transmission spectrum.

        Distinguishes between:
        1. SPR physics (wavelength-dependent sensitivity) - PRESERVE
        2. Optical artifacts (polarizer/detector wavelength response) - CORRECT

        Strategy:
        - Check off-SPR regions (560-570nm, 750-770nm) for tilt
        - If off-SPR is tilted → optical artifact (should correct)
        - If off-SPR is flat but SPR region tilted → SPR physics (don't correct)

        Args:
            transmission: Transmission spectrum (%)
            wavelengths: Wavelength array (nm)
            spr_region: Tuple (min_wl, max_wl) defining SPR-active region
            off_spr_regions: List of tuples for off-SPR regions (default: [(560,570), (750,770)])

        Returns:
            Dictionary with diagnostic results:
            {
                'off_spr_tilt_deg': float,  # Degrees per 100nm in off-SPR regions
                'spr_tilt_deg': float,      # Degrees per 100nm in SPR region
                'tilt_type': str,           # 'optical_artifact', 'spr_physics', 'mixed', 'none'
                'correction_recommended': bool,
                'off_spr_left': float,      # Mean transmission at left off-SPR
                'off_spr_right': float,     # Mean transmission at right off-SPR
                'spr_mean': float           # Mean transmission in SPR region
            }

        """
        if off_spr_regions is None:
            off_spr_regions = [(560.0, 570.0), (750.0, 770.0)]

        result = {
            "off_spr_tilt_deg": 0.0,
            "spr_tilt_deg": 0.0,
            "tilt_type": "none",
            "correction_recommended": False,
            "off_spr_left": None,
            "off_spr_right": None,
            "spr_mean": None,
        }

        # Analyze off-SPR regions for optical artifacts
        off_spr_means = []
        off_spr_wavelengths = []

        for min_wl, max_wl in off_spr_regions:
            mask = (wavelengths >= min_wl) & (wavelengths <= max_wl)
            if np.any(mask):
                mean_trans = np.mean(transmission[mask])
                mean_wl = np.mean(wavelengths[mask])
                off_spr_means.append(mean_trans)
                off_spr_wavelengths.append(mean_wl)

        # Calculate off-SPR tilt (optical artifact indicator)
        if len(off_spr_means) >= 2:
            result["off_spr_left"] = off_spr_means[0]
            result["off_spr_right"] = off_spr_means[-1]

            # Tilt in transmission % per 100nm
            wl_diff_nm = off_spr_wavelengths[-1] - off_spr_wavelengths[0]
            trans_diff = off_spr_means[-1] - off_spr_means[0]
            result["off_spr_tilt_deg"] = (
                (trans_diff / wl_diff_nm) * 100.0 if wl_diff_nm > 0 else 0.0
            )

        # Analyze SPR region tilt
        spr_mask = (wavelengths >= spr_region[0]) & (wavelengths <= spr_region[1])
        if np.any(spr_mask):
            spr_trans = transmission[spr_mask]
            spr_wl = wavelengths[spr_mask]
            result["spr_mean"] = np.mean(spr_trans)

            # Fit linear tilt in SPR region
            if len(spr_wl) > 1:
                coeffs = np.polyfit(spr_wl, spr_trans, 1)
                result["spr_tilt_deg"] = coeffs[0] * 100.0  # slope × 100nm

        # Classify tilt type
        off_spr_tilt_abs = abs(result["off_spr_tilt_deg"])
        spr_tilt_abs = abs(result["spr_tilt_deg"])

        if off_spr_tilt_abs > 5.0:  # >5% per 100nm in off-SPR
            if spr_tilt_abs > off_spr_tilt_abs * 1.5:
                result["tilt_type"] = "mixed"  # Both optical + SPR
                result["correction_recommended"] = True  # Correct optical part
            else:
                result["tilt_type"] = "optical_artifact"  # Purely optical
                result["correction_recommended"] = True
        elif spr_tilt_abs > 5.0:  # SPR region tilted but off-SPR flat
            result["tilt_type"] = "spr_physics"  # Natural SPR wavelength dependence
            result["correction_recommended"] = False  # DON'T correct physics!
        else:
            result["tilt_type"] = "none"  # Minimal tilt
            result["correction_recommended"] = False

        return result

    @staticmethod
    def calculate_transmission_qc(
        transmission_spectrum: np.ndarray,
        wavelengths: np.ndarray,
        channel: str,
        p_spectrum: np.ndarray = None,
        s_spectrum: np.ndarray = None,
        detector_max_counts: float = 65535,
        saturation_threshold: float = 62259,
    ) -> dict:
        """Calculate comprehensive QC metrics from transmission spectrum.

        This consolidates all QC validation logic in one place:
        - FWHM calculation
        - SPR dip detection
        - Transmission quality assessment
        - Orientation validation (if P/S spectra provided)
        - Saturation checks for S and P spectra

        Args:
            transmission_spectrum: Processed transmission spectrum (%)
            wavelengths: Wavelength array (nm)
            channel: Channel identifier ('a', 'b', 'c', 'd')
            p_spectrum: Optional P-pol spectrum for saturation check
            s_spectrum: Optional S-pol spectrum for saturation check
            detector_max_counts: Detector maximum counts (default: 65535)
            saturation_threshold: Saturation limit (default: 95% of max)

        Returns:
            Dictionary with QC metrics:
            {
                'fwhm': float,              # FWHM in nm
                'dip_detected': bool,       # SPR dip presence
                'transmission_min': float,  # Minimum transmission %
                'dip_wavelength': float,    # Wavelength at minimum transmission
                'dip_depth': float,         # SPR dip depth %
                'ratio': float,             # P/S ratio (if spectra provided)
                'orientation_correct': bool,# Orientation validation (if spectra provided)
                'status': str,              # Overall status string
                'fwhm_quality': str,        # FWHM quality category
                'warnings': list,           # List of warning messages
                's_saturated': bool,        # S-pol saturation flag
                'p_saturated': bool,        # P-pol saturation flag
                's_max_counts': float,      # S-pol max counts
                'p_max_counts': float       # P-pol max counts
            }

        """
        qc = {
            "fwhm": None,
            "dip_detected": False,
            "transmission_min": None,
            "dip_wavelength": None,
            "dip_depth": None,
            "ratio": None,
            "orientation_correct": None,
            "status": "⚠️ INDETERMINATE",
            "fwhm_quality": "unknown",
            "warnings": [],
            "s_saturated": False,
            "p_saturated": False,
            "s_max_counts": None,
            "p_max_counts": None,
        }

        try:
            # 0. Saturation Checks (if spectra provided)
            if s_spectrum is not None:
                s_max = float(np.max(s_spectrum))
                qc["s_max_counts"] = s_max
                qc["s_saturated"] = s_max >= saturation_threshold

                if qc["s_saturated"]:
                    qc["warnings"].append(
                        f"S-pol SATURATED: {s_max:.0f} counts >= {saturation_threshold:.0f}",
                    )
                    logger.warning(
                        f"Ch {channel.upper()}: S-pol saturation detected ({s_max:.0f} counts)",
                    )

            if p_spectrum is not None:
                p_max = float(np.max(p_spectrum))
                qc["p_max_counts"] = p_max
                qc["p_saturated"] = p_max >= saturation_threshold

                if qc["p_saturated"]:
                    qc["warnings"].append(
                        f"P-pol SATURATED: {p_max:.0f} counts >= {saturation_threshold:.0f}",
                    )
                    logger.warning(
                        f"Ch {channel.upper()}: P-pol saturation detected ({p_max:.0f} counts)",
                    )
            # 1. SPR Dip Detection
            min_transmission = np.min(transmission_spectrum)
            min_idx = np.argmin(transmission_spectrum)
            spr_wavelength = wavelengths[min_idx]
            dip_depth = 100.0 - min_transmission

            qc["transmission_min"] = float(min_transmission)
            qc["dip_wavelength"] = float(spr_wavelength)
            qc["dip_depth"] = float(dip_depth)
            qc["dip_detected"] = dip_depth > 5.0

            if not qc["dip_detected"]:
                qc["warnings"].append(
                    f"Weak SPR dip ({dip_depth:.1f}%) - check sensor hydration",
                )

            # 2. FWHM Calculation
            half_max = (100.0 + min_transmission) / 2.0
            below_half_max = transmission_spectrum < half_max
            fwhm_indices = np.where(below_half_max)[0]

            if len(fwhm_indices) > 1:
                fwhm_wavelengths = wavelengths[fwhm_indices]
                fwhm = fwhm_wavelengths[-1] - fwhm_wavelengths[0]
                qc["fwhm"] = float(fwhm)

                # FWHM Quality Assessment
                if fwhm < 30:
                    qc["fwhm_quality"] = "excellent"
                elif fwhm < 50:
                    qc["fwhm_quality"] = "good"
                elif fwhm < 60:
                    qc["fwhm_quality"] = "acceptable"
                    qc["warnings"].append(
                        f"Broad FWHM ({fwhm:.1f}nm) - acceptable but not optimal",
                    )
                else:
                    qc["fwhm_quality"] = "poor"
                    qc["warnings"].append(
                        f"Wide FWHM ({fwhm:.1f}nm) - poor sensor contact or degradation",
                    )
            else:
                qc["warnings"].append("Cannot calculate FWHM - no clear SPR dip")

            # 3. P/S Ratio Calculation (if spectra provided)
            if p_spectrum is not None and s_spectrum is not None:
                # Calculate mean P/S ratio in SPR region
                roi_mask = (wavelengths >= spr_wavelength - 20) & (
                    wavelengths <= spr_wavelength + 20
                )
                if np.any(roi_mask):
                    p_roi = p_spectrum[roi_mask]
                    s_roi = s_spectrum[roi_mask]
                    s_roi_mean = np.mean(s_roi)
                    p_roi_mean = np.mean(p_roi)

                    if s_roi_mean > 0:
                        qc["ratio"] = float(p_roi_mean / s_roi_mean)

                        # Validate P/S ratio for orientation check
                        # Expected: 0.1-0.95 for correct orientation (P < S due to SPR absorption)
                        if qc["ratio"] > 1.15:
                            qc["orientation_correct"] = False
                            qc["warnings"].append(
                                f"P/S ratio ({qc['ratio']:.2f}) > 1.15 - polarizer may be inverted",
                            )
                        elif 0.95 < qc["ratio"] <= 1.15:
                            qc["orientation_correct"] = None  # Indeterminate
                            qc["warnings"].append(
                                f"P/S ratio ({qc['ratio']:.2f}) borderline - cannot confirm orientation",
                            )
                        elif 0.10 <= qc["ratio"] <= 0.95:
                            qc["orientation_correct"] = True
                        else:
                            qc["orientation_correct"] = None
                            qc["warnings"].append(
                                f"P/S ratio ({qc['ratio']:.2f}) < 0.10 - unusual, verify sensor",
                            )

            # 4. Overall Status Assessment
            passed = (
                qc["dip_detected"]
                and qc["fwhm"] is not None
                and qc["fwhm"] < 60.0
                and (
                    qc["orientation_correct"] is True
                    or qc["orientation_correct"] is None
                )
                and not qc["s_saturated"]
                and not qc["p_saturated"]
            )

            failed = (
                not qc["dip_detected"]
                or (qc["fwhm"] is not None and qc["fwhm"] >= 80.0)
                or qc["orientation_correct"] is False
                or qc["s_saturated"]
                or qc["p_saturated"]
            )

            if passed:
                qc["status"] = "✅ PASS"
            elif failed:
                qc["status"] = "❌ FAIL"
            else:
                qc["status"] = "⚠️ WARNING"

            logger.debug(
                f"Ch {channel.upper()} QC: {qc['status']} | FWHM={qc['fwhm']:.1f}nm | Dip={qc['dip_depth']:.1f}% @ {qc['dip_wavelength']:.1f}nm",
            )

        except Exception as e:
            logger.error(f"QC calculation failed for channel {channel}: {e}")
            qc["warnings"].append(f"QC calculation error: {e!s}")

        return qc
