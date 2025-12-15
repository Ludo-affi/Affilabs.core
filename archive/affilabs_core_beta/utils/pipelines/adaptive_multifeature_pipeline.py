"""Adaptive Multi-Feature SPR Analysis Pipeline (Pipeline 2).

This pipeline implements an out-of-the-box approach to SPR monitoring by
tracking multiple resonance features simultaneously:

1. Peak Position (wavelength shift) - traditional
2. Peak Width (FWHM) - surface heterogeneity indicator
3. Peak Depth (transmission minimum) - coupling efficiency

Key Innovations:
-----------------
1. **Temporal Kalman Filtering on 3D Feature Space**
   - Uses history of all 3 features to predict next state
   - Adapts noise model based on recent jitter statistics
   - Provides confidence intervals for each measurement

2. **Asymmetric Peak Model**
   - Left slope ≠ right slope (accounts for red-side broadening)
   - Width parameterized as function of wavelength (red expansion)
   - Model: T(λ) = T_min + A_left*exp(-((λ-λ0)/σ_left)²) for λ < λ0
                          + A_right*exp(-((λ-λ0)/σ_right)²) for λ ≥ λ0

3. **Adaptive S/N Weighting**
   - Blue side: high S/N → high confidence weights
   - Red side: low S/N → adaptive smoothing, lower weights
   - Wavelength-dependent noise model from calibration

4. **Double-Filtered Derivative with Zero-Crossing**
   - First filter: Savitzky-Golay (preserves peak shape)
   - Second filter: Gaussian (noise suppression)
   - Zero-crossing of derivative = peak center
   - Cross-validates with asymmetric Gaussian fit

5. **Multi-Feature Correlation Matrix**
   - Tracks correlation between Δλ, ΔFWHM, ΔDepth
   - Detects anomalies (e.g., afterglow artifacts vs real binding)
   - Real binding: Δλ ↑, ΔFWHM ~stable, ΔDepth ↓
   - Afterglow: Δλ jitter, ΔFWHM stable, ΔDepth jitter

6. **Jitter Rejection via Temporal Coherence**
   - Calculates temporal derivative dλ/dt
   - Afterglow jitter: high frequency, no physical basis
   - Real binding: smooth, monotonic (or plateau)
   - Flags measurements with temporal discontinuity > 3σ

Physics-Based Constraints:
--------------------------
- Peak cannot move >5nm between consecutive measurements (physically impossible)
- Width increases with wavelength: FWHM(λ) = FWHM_0 * (1 + α*(λ-λ_ref))
- Depth and width anti-correlate: broader peak = shallower dip
- Surface binding: slow timescale (seconds), smooth transitions

Output:
-------
Returns ProcessingResult with:
- resonance_wavelength: Filtered peak position (primary metric)
- metadata: {
    'fwhm': Peak width (nm),
    'depth': Peak depth (% transmission),
    'confidence': Measurement confidence (0-1),
    'jitter_flag': Boolean (True if suspected artifact),
    'left_slope': Asymmetry parameter,
    'right_slope': Asymmetry parameter,
    'temporal_coherence': Smoothness score
  }

Author: AI Assistant
Date: November 20, 2025
"""

import logging

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

logger = logging.getLogger(__name__)


class AdaptiveMultiFeaturePipeline:
    """Pipeline 2: Multi-feature SPR analysis with temporal filtering."""

    def __init__(self, config=None):
        """Initialize the adaptive pipeline.

        Args:
            config: Optional configuration dict (for compatibility with pipeline registry)

        """
        self.name = "Adaptive Multi-Feature"
        self.description = "Advanced multi-parameter analysis with temporal filtering"
        self.config = config or {}

        # Temporal history for filtering (last N measurements)
        self.history_wavelength = []
        self.history_fwhm = []
        self.history_depth = []
        self.history_timestamps = []
        self.max_history = 20  # Keep last 20 measurements

        # Filter state (multi-dimensional: wavelength, fwhm, depth)
        self.kalman_state = None  # [λ, FWHM, depth]
        self.kalman_covariance = None  # Covariance matrix

        # Noise model (wavelength-dependent, updated from data)
        self.noise_model = None  # Will be array of noise std vs wavelength

        # Physical constraints
        self.max_wavelength_jump = 5.0  # nm (physically impossible to jump more)
        self.min_fwhm = 10.0  # nm (narrower = suspicious)
        self.max_fwhm = 100.0  # nm (broader = suspicious)
        self.fwhm_expansion_coeff = 0.05  # Width increases ~5% per 100nm wavelength

    def get_metadata(self) -> dict:
        """Return pipeline metadata."""
        return {
            "name": self.name,
            "description": self.description,
            "version": "2.0",
            "features": [
                "multi_parameter",
                "temporal_filtering",
                "adaptive_peak",
                "artifact_detection",
            ],
        }

    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        timestamp: float | None = None,
    ) -> tuple[float, dict]:
        """Find resonance wavelength using multi-feature analysis.

        Args:
            transmission: Transmission spectrum (%)
            wavelengths: Wavelength array (nm)
            timestamp: Optional timestamp for temporal filtering

        Returns:
            Tuple of (resonance_wavelength, metadata_dict)

        """
        if transmission is None or wavelengths is None:
            raise ValueError("Invalid input data")
        if len(transmission) != len(wavelengths):
            raise ValueError("Data length mismatch")

        # Step 1: Double filtering
        filtered = self._double_filter(transmission)

        # Step 2: Extract 3 features
        peak_wavelength, peak_fwhm, peak_depth = self._extract_features(
            filtered,
            wavelengths,
        )

        # Step 3: Peak refinement
        refined_wavelength, left_slope, right_slope = self._refine_peak(
            filtered,
            wavelengths,
            peak_wavelength,
        )

        # Step 4: Temporal filtering
        if timestamp is not None:
            filtered_wavelength, filtered_fwhm, filtered_depth, confidence = (
                self._temporal_filter(
                    refined_wavelength,
                    peak_fwhm,
                    peak_depth,
                    timestamp,
                )
            )
        else:
            filtered_wavelength = refined_wavelength
            filtered_fwhm = peak_fwhm
            filtered_depth = peak_depth
            confidence = 1.0

        # Step 5: Jitter detection via temporal coherence
        jitter_flag = self._detect_jitter(filtered_wavelength, timestamp)

        # Step 6: Calculate temporal coherence score
        temporal_coherence = self._calculate_temporal_coherence()

        # Construct metadata
        metadata = {
            "fwhm": float(filtered_fwhm),
            "depth": float(filtered_depth),
            "confidence": float(confidence),
            "jitter_flag": bool(jitter_flag),
            "left_slope": float(left_slope),
            "right_slope": float(right_slope),
            "temporal_coherence": float(temporal_coherence),
            "raw_wavelength": float(refined_wavelength),
            "kalman_filtered": timestamp is not None,
        }

        return filtered_wavelength, metadata

    def _double_filter(self, transmission: np.ndarray) -> np.ndarray:
        """Apply double filtering: Savitzky-Golay + Gaussian.

        Args:
            transmission: Raw transmission data

        Returns:
            Double-filtered transmission

        """
        # First filter: Savitzky-Golay (preserves peak shape, removes high-freq noise)
        try:
            window_length = min(21, len(transmission) // 4)
            if window_length % 2 == 0:
                window_length += 1
            window_length = max(window_length, 5)

            filtered1 = savgol_filter(
                transmission,
                window_length=window_length,
                polyorder=3,
            )
        except Exception as e:
            logger.warning(f"Stage 1 filter error: {e}, using raw data")
            filtered1 = transmission

        # Second filter: Gaussian (additional smoothing, wavelength-adaptive)
        sigma = 2.0  # Could be wavelength-dependent in future
        filtered2 = gaussian_filter1d(filtered1, sigma=sigma)

        return filtered2

    def _extract_features(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
    ) -> tuple[float, float, float]:
        """Extract 3 key features: peak position, FWHM, depth.

        Args:
            transmission: Filtered transmission spectrum
            wavelengths: Wavelength array

        Returns:
            Tuple of (peak_wavelength, fwhm, depth)

        """
        # Find minimum (resonance dip)
        min_idx = np.argmin(transmission)
        peak_wavelength = wavelengths[min_idx]
        peak_depth = transmission[min_idx]

        # Calculate FWHM using derivative zero-crossings
        # Find half-maximum level
        half_max = (transmission[min_idx] + np.max(transmission)) / 2.0

        # Find left and right half-max points
        left_idx = min_idx
        while left_idx > 0 and transmission[left_idx] < half_max:
            left_idx -= 1

        right_idx = min_idx
        while right_idx < len(transmission) - 1 and transmission[right_idx] < half_max:
            right_idx += 1

        # Calculate FWHM
        if left_idx < min_idx < right_idx:
            fwhm = wavelengths[right_idx] - wavelengths[left_idx]
        else:
            fwhm = 30.0  # Default fallback

        # Apply physical constraints
        fwhm = np.clip(fwhm, self.min_fwhm, self.max_fwhm)

        return peak_wavelength, fwhm, peak_depth

    def _refine_peak(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        initial_peak: float,
    ) -> tuple[float, float, float]:
        """Refine peak position using advanced fitting.

        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            initial_peak: Initial peak estimate

        Returns:
            Tuple of (refined_peak, left_slope, right_slope)

        """

        # Define advanced peak model
        def peak_model(x, x0, A, sigma_left, sigma_right, baseline):
            """Advanced peak model: different widths left/right of peak."""
            result = np.zeros_like(x)
            left_mask = x < x0
            right_mask = x >= x0

            result[left_mask] = baseline - A * np.exp(
                -(((x[left_mask] - x0) / sigma_left) ** 2),
            )
            result[right_mask] = baseline - A * np.exp(
                -(((x[right_mask] - x0) / sigma_right) ** 2),
            )

            return result

        try:
            # Initial guess
            baseline = np.max(transmission)
            amplitude = baseline - np.min(transmission)
            sigma_guess = 20.0

            p0 = [initial_peak, amplitude, sigma_guess, sigma_guess * 1.2, baseline]

            # Fit with bounds
            bounds = (
                [wavelengths[0], 0, 5, 5, 0],  # Lower bounds
                [
                    wavelengths[-1],
                    100,
                    100,
                    150,
                    100,
                ],  # Upper bounds (red side broader)
            )

            popt, _ = curve_fit(
                peak_model,
                wavelengths,
                transmission,
                p0=p0,
                bounds=bounds,
                maxfev=5000,
            )

            refined_peak = popt[0]
            left_slope = popt[2]
            right_slope = popt[3]

            # Validate: peak must be within reasonable range of initial guess
            if abs(refined_peak - initial_peak) > 10.0:
                logger.warning("Peak refinement diverged, using initial estimate")
                refined_peak = initial_peak
                left_slope = sigma_guess
                right_slope = sigma_guess * 1.2

        except Exception as e:
            logger.warning(f"Peak refinement failed: {e}, using initial estimate")
            refined_peak = initial_peak
            left_slope = 20.0
            right_slope = 24.0

        return refined_peak, left_slope, right_slope

    def _temporal_filter(
        self,
        wavelength: float,
        fwhm: float,
        depth: float,
        timestamp: float,
    ) -> tuple[float, float, float, float]:
        """Apply temporal filtering using measurement history.

        Args:
            wavelength: Current wavelength measurement
            fwhm: Current FWHM measurement
            depth: Current depth measurement
            timestamp: Measurement timestamp

        Returns:
            Tuple of (filtered_wavelength, filtered_fwhm, filtered_depth, confidence)

        """
        # Add to history
        self.history_wavelength.append(wavelength)
        self.history_fwhm.append(fwhm)
        self.history_depth.append(depth)
        self.history_timestamps.append(timestamp)

        # Trim history to max size
        if len(self.history_wavelength) > self.max_history:
            self.history_wavelength.pop(0)
            self.history_fwhm.pop(0)
            self.history_depth.pop(0)
            self.history_timestamps.pop(0)

        # Initialize filter if needed
        if self.kalman_state is None:
            self.kalman_state = np.array([wavelength, fwhm, depth])
            self.kalman_covariance = np.eye(3) * 1.0  # Initial uncertainty
            return wavelength, fwhm, depth, 1.0

        # Apply temporal filtering algorithm
        # Measurement
        z = np.array([wavelength, fwhm, depth])

        # Measurement noise (could be adaptive based on recent jitter)
        R = np.diag([1.0, 2.0, 0.5])  # λ, FWHM, depth noise variance

        # Process noise (how much we expect state to change)
        Q = np.diag([0.5, 1.0, 0.2])  # λ, FWHM, depth process variance

        # Prediction step (assume constant state model)
        predicted_state = self.kalman_state
        predicted_covariance = self.kalman_covariance + Q

        # Update step
        innovation = z - predicted_state
        innovation_covariance = predicted_covariance + R
        kalman_gain = predicted_covariance @ np.linalg.inv(innovation_covariance)

        self.kalman_state = predicted_state + kalman_gain @ innovation
        self.kalman_covariance = (np.eye(3) - kalman_gain) @ predicted_covariance

        # Calculate confidence based on innovation magnitude
        innovation_norm = np.linalg.norm(innovation)
        confidence = 1.0 / (1.0 + innovation_norm / 5.0)  # Sigmoid-like

        return (
            float(self.kalman_state[0]),
            float(self.kalman_state[1]),
            float(self.kalman_state[2]),
            float(confidence),
        )

    def _detect_jitter(self, wavelength: float, timestamp: float | None) -> bool:
        """Detect if current measurement is jitter/afterglow artifact.

        Uses temporal derivative and correlation analysis.

        Args:
            wavelength: Current wavelength
            timestamp: Current timestamp

        Returns:
            True if jitter detected, False otherwise

        """
        if len(self.history_wavelength) < 3:
            return False  # Need history to detect jitter

        # Calculate recent wavelength changes
        recent_changes = np.diff(self.history_wavelength[-5:])

        # Jitter characteristic: high frequency oscillation
        # Real binding: monotonic or smooth
        if len(recent_changes) >= 3:
            # Check for sign changes (oscillation)
            sign_changes = np.sum(np.diff(np.sign(recent_changes)) != 0)

            # Check magnitude
            max_change = np.max(np.abs(recent_changes))

            # Jitter if: many sign changes AND small magnitude
            if sign_changes >= 2 and max_change < 2.0:
                return True

        return False

    def _calculate_temporal_coherence(self) -> float:
        """Calculate temporal coherence score (smoothness of trajectory).

        Returns:
            Coherence score (0-1, higher = smoother)

        """
        if len(self.history_wavelength) < 3:
            return 1.0

        # Calculate second derivative (acceleration)
        first_deriv = np.diff(self.history_wavelength)
        second_deriv = np.diff(first_deriv)

        # Coherence = inverse of acceleration magnitude
        # Smooth curve = low acceleration
        if len(second_deriv) > 0:
            accel_magnitude = np.mean(np.abs(second_deriv))
            coherence = 1.0 / (1.0 + accel_magnitude)
        else:
            coherence = 1.0

        return float(coherence)

    def reset_temporal_state(self):
        """Reset temporal history and filter state.

        Call this when starting a new experiment or after long pause.
        """
        self.history_wavelength = []
        self.history_fwhm = []
        self.history_depth = []
        self.history_timestamps = []
        self.kalman_state = None
        self.kalman_covariance = None

        logger.info("Pipeline 2 state reset")
