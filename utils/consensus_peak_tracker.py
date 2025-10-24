"""
Consensus Peak Tracking for SPR Measurements

Combines centroid and parabolic methods to achieve robust peak detection
that is invariant to peak shape and intensity variations.

Phase 1 Implementation:
- Fixed filtering parameters (no adaptive phase behavior yet)
- Centroid + Parabolic combination (60/40 weighting)
- Adaptive thresholding to maintain consistent pixel count
- Outlier detection with MAD-based statistical method
- Confidence scoring based on method agreement

Author: AI Assistant
Date: 2025-10-21
Version: 0.2.0-phase1
"""

from typing import Tuple, Optional, Dict
from collections import deque
import numpy as np
from scipy.signal import savgol_filter

from utils.logger import logger


class CentroidTracker:
    """Centroid-based peak detection with adaptive thresholding"""

    def __init__(self, target_pixels: int = 20):
        """
        Initialize centroid tracker.

        Args:
            target_pixels: Target number of pixels to include in centroid
                          (maintains consistent noise averaging)
        """
        self.target_pixels = target_pixels

    def find_peak(
        self,
        wavelengths: np.ndarray,
        spectrum: np.ndarray,
        search_range: Tuple[float, float] = (600, 720),
        channel: str = ''
    ) -> Tuple[float, int, float]:
        """
        Find peak using weighted centroid with adaptive threshold.

        Args:
            wavelengths: Wavelength array (nm)
            spectrum: Transmission spectrum (normalized 0-1)
            search_range: SPR wavelength range (min, max) in nm
            channel: Channel identifier for logging

        Returns:
            (peak_wavelength, num_pixels_used, threshold_used)
        """
        # Extract search region
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        wl_region = wavelengths[mask]
        spec_region = spectrum[mask]

        if len(wl_region) < 3:
            logger.warning(f"Centroid Ch {channel}: Insufficient points ({len(wl_region)})")
            if len(wl_region) > 0:
                return wl_region[np.argmin(spec_region)], len(wl_region), 0.0
            else:
                return np.nan, 0, 0.0

        # Invert spectrum (SPR dip becomes peak)
        inverted = 1.0 - spec_region
        max_signal = np.max(inverted)

        if max_signal < 0.01:
            logger.warning(f"Centroid Ch {channel}: Very low signal (max={max_signal:.3f})")
            return wl_region[np.argmin(spec_region)], len(wl_region), 0.0

        # Adaptive threshold to maintain target pixel count
        threshold_fraction = self._adaptive_threshold(
            inverted, max_signal, self.target_pixels
        )

        # Apply threshold
        threshold_value = max_signal * threshold_fraction
        significant_mask = inverted >= threshold_value
        num_pixels = np.sum(significant_mask)

        if num_pixels < 3:
            logger.debug(f"Centroid Ch {channel}: Too few pixels ({num_pixels}), using min")
            peak_idx = np.argmin(spec_region)
            return wl_region[peak_idx], num_pixels, threshold_fraction

        # Calculate weighted centroid
        weights = inverted[significant_mask]
        positions = wl_region[significant_mask]
        centroid = np.sum(weights * positions) / np.sum(weights)

        logger.debug(
            f"Centroid Ch {channel}: λ={centroid:.3f}nm, "
            f"n_pixels={num_pixels}, thresh={threshold_fraction:.2f}"
        )

        return float(centroid), num_pixels, threshold_fraction

    def _adaptive_threshold(
        self,
        inverted: np.ndarray,
        max_signal: float,
        target_pixels: int
    ) -> float:
        """
        Adjust threshold to maintain approximately target_pixels above threshold.

        Uses binary search to find threshold that gives target_pixels ± 5.

        Args:
            inverted: Inverted spectrum (peak not dip)
            max_signal: Maximum signal value
            target_pixels: Target number of pixels

        Returns:
            Threshold fraction (0.0-1.0) relative to max_signal
        """
        # Start with standard 0.5 threshold
        low_thresh = 0.2
        high_thresh = 0.8
        best_thresh = 0.5

        # Binary search for optimal threshold (max 10 iterations)
        for iteration in range(10):
            mid_thresh = (low_thresh + high_thresh) / 2.0
            threshold_value = max_signal * mid_thresh
            num_pixels = np.sum(inverted >= threshold_value)

            # Check if close enough to target
            if abs(num_pixels - target_pixels) <= 5:
                best_thresh = mid_thresh
                break
            elif num_pixels > target_pixels:
                # Too many pixels, increase threshold
                low_thresh = mid_thresh
            else:
                # Too few pixels, decrease threshold
                high_thresh = mid_thresh

            best_thresh = mid_thresh

        return best_thresh


class ParabolicTracker:
    """Parabolic fit peak detection for sub-pixel precision"""

    def find_peak(
        self,
        wavelengths: np.ndarray,
        spectrum: np.ndarray,
        search_range: Tuple[float, float] = (600, 720),
        channel: str = ''
    ) -> Tuple[float, bool]:
        """
        Find peak by fitting parabola to minimum point.

        Uses 3-point analytical solution for parabolic vertex.

        Args:
            wavelengths: Wavelength array (nm)
            spectrum: Transmission spectrum (normalized 0-1)
            search_range: SPR wavelength range (min, max) in nm
            channel: Channel identifier for logging

        Returns:
            (peak_wavelength, fit_success)
        """
        # Extract search region
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        wl_region = wavelengths[mask]
        spec_region = spectrum[mask]

        if len(wl_region) < 3:
            logger.warning(f"Parabolic Ch {channel}: Insufficient points ({len(wl_region)})")
            if len(wl_region) > 0:
                return wl_region[np.argmin(spec_region)], False
            else:
                return np.nan, False

        # Find discrete minimum
        min_idx = np.argmin(spec_region)

        # Need at least 3 points for parabolic fit
        if min_idx == 0 or min_idx == len(wl_region) - 1:
            logger.debug(f"Parabolic Ch {channel}: Peak at edge, can't fit")
            return wl_region[min_idx], False

        # Extract 3 points around minimum
        idx = [min_idx - 1, min_idx, min_idx + 1]
        x = wl_region[idx]
        y = spec_region[idx]

        # Fit parabola: y = a(x-h)^2 + k, where h is vertex (peak position)
        try:
            x0, x1, x2 = x
            y0, y1, y2 = y

            # Analytical solution for parabolic vertex
            denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
            if abs(denom) < 1e-10:
                logger.debug(f"Parabolic Ch {channel}: Singular matrix")
                return wl_region[min_idx], False

            A = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
            B = (x2**2 * (y0 - y1) + x1**2 * (y2 - y0) + x0**2 * (y1 - y2)) / denom

            if abs(A) < 1e-10:
                logger.debug(f"Parabolic Ch {channel}: Parabola is flat")
                return wl_region[min_idx], False

            # Check if it's actually a minimum (A > 0)
            if A < 0:
                logger.debug(f"Parabolic Ch {channel}: Parabola is maximum, not minimum")
                return wl_region[min_idx], False

            # Vertex position
            vertex_x = -B / (2 * A)

            # Sanity check: vertex should be near original minimum
            if abs(vertex_x - x1) > 2.0:  # More than 2nm away
                logger.debug(
                    f"Parabolic Ch {channel}: Vertex too far "
                    f"({vertex_x:.3f} vs {x1:.3f})"
                )
                return wl_region[min_idx], False

            logger.debug(f"Parabolic Ch {channel}: λ={vertex_x:.3f}nm (fitted)")
            return float(vertex_x), True

        except Exception as e:
            logger.debug(f"Parabolic Ch {channel}: Fit failed: {e}")
            return wl_region[min_idx], False


class ConsensusTracker:
    """
    Consensus peak tracker combining centroid + parabolic methods.
    Phase 1: Fixed filtering, no adaptive behavior.
    """

    def __init__(
        self,
        savgol_window: int = 7,
        savgol_polyorder: int = 3,
        target_pixels: int = 20,
        history_size: int = 10,
        outlier_threshold_mad: float = 3.0,
        search_range: Tuple[float, float] = (600, 720)
    ):
        """
        Initialize consensus tracker.

        Args:
            savgol_window: Savitzky-Golay window size (odd number)
            savgol_polyorder: Savitzky-Golay polynomial order
            target_pixels: Target pixels for centroid method
            history_size: Number of recent peaks to keep for outlier detection
            outlier_threshold_mad: MAD multiplier for outlier threshold
            search_range: SPR wavelength range (min, max) in nm
        """
        self.savgol_window = savgol_window
        self.savgol_polyorder = savgol_polyorder
        self.target_pixels = target_pixels
        self.outlier_threshold_mad = outlier_threshold_mad
        self.search_range = search_range

        # Trackers
        self.centroid_tracker = CentroidTracker(target_pixels)
        self.parabolic_tracker = ParabolicTracker()

        # History for outlier detection (per channel)
        self.peak_history: Dict[str, deque] = {
            ch: deque(maxlen=history_size) for ch in 'abcd'
        }
        self.outlier_count: Dict[str, int] = {ch: 0 for ch in 'abcd'}
        self.total_count: Dict[str, int] = {ch: 0 for ch in 'abcd'}

    def find_peak(
        self,
        wavelengths: np.ndarray,
        spectrum: np.ndarray,
        channel: str
    ) -> Dict:
        """
        Find peak using consensus method.

        Args:
            wavelengths: Wavelength array (nm)
            spectrum: Transmission spectrum (normalized 0-1)
            channel: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            dict with:
                'peak_nm': consensus peak position
                'centroid_nm': centroid result
                'parabolic_nm': parabolic result (or None if failed)
                'num_pixels': pixels used in centroid
                'centroid_threshold': threshold fraction used
                'parabolic_success': bool
                'disagreement_nm': |centroid - parabolic|
                'is_outlier': bool
                'confidence': 0.0-1.0
                'outlier_rate': fraction of outliers detected
        """
        self.total_count[channel] += 1

        # Step 1: Apply spectral smoothing (Savitzky-Golay)
        if self.savgol_window > 0 and len(spectrum) >= self.savgol_window:
            try:
                smoothed = savgol_filter(
                    spectrum,
                    window_length=self.savgol_window,
                    polyorder=self.savgol_polyorder
                )
            except Exception as e:
                logger.warning(f"Consensus Ch {channel}: Savgol failed: {e}")
                smoothed = spectrum
        else:
            smoothed = spectrum

        # Step 2: Find peaks with both methods
        centroid_peak, num_pixels, centroid_threshold = self.centroid_tracker.find_peak(
            wavelengths, smoothed, self.search_range, channel
        )

        parabolic_peak, parabolic_success = self.parabolic_tracker.find_peak(
            wavelengths, smoothed, self.search_range, channel
        )

        # Check for NaN results
        if np.isnan(centroid_peak):
            logger.error(f"Consensus Ch {channel}: Centroid returned NaN!")
            return self._create_error_result(channel)

        # Step 3: Calculate consensus (weighted combination)
        if parabolic_success and not np.isnan(parabolic_peak):
            # Standard weighting: 60% centroid, 40% parabolic
            consensus_peak = 0.60 * centroid_peak + 0.40 * parabolic_peak
            disagreement = abs(centroid_peak - parabolic_peak)
        else:
            # Parabolic failed, use centroid only
            consensus_peak = centroid_peak
            parabolic_peak = None
            disagreement = 0.0

        # Step 4: Outlier detection
        is_outlier = False
        if len(self.peak_history[channel]) >= 5:
            is_outlier = self._is_outlier(consensus_peak, channel)

            if is_outlier:
                # Replace with predicted value
                predicted = self._predict_next_value(channel)
                logger.info(
                    f"Consensus Ch {channel}: Outlier detected "
                    f"({consensus_peak:.3f}nm) → replaced ({predicted:.3f}nm)"
                )
                self.outlier_count[channel] += 1
                consensus_peak = predicted

        # Step 5: Update history
        self.peak_history[channel].append(consensus_peak)

        # Step 6: Calculate confidence
        confidence = self._calculate_confidence(
            disagreement, parabolic_success, num_pixels
        )

        # Return detailed results
        return {
            'peak_nm': consensus_peak,
            'centroid_nm': centroid_peak,
            'parabolic_nm': parabolic_peak,
            'num_pixels': num_pixels,
            'centroid_threshold': centroid_threshold,
            'parabolic_success': parabolic_success,
            'disagreement_nm': disagreement,
            'is_outlier': is_outlier,
            'confidence': confidence,
            'outlier_rate': self.outlier_count[channel] / max(1, self.total_count[channel])
        }

    def _is_outlier(self, peak: float, channel: str) -> bool:
        """
        Detect outliers using Median Absolute Deviation (MAD).

        MAD is robust to outliers (unlike std dev).

        Args:
            peak: Peak position to test
            channel: Channel identifier

        Returns:
            True if peak is an outlier
        """
        history = list(self.peak_history[channel])
        median = np.median(history)
        mad = np.median(np.abs(np.array(history) - median))

        if mad < 0.001:  # Very stable signal
            mad = 0.01  # Use minimum threshold to avoid false positives

        threshold = self.outlier_threshold_mad * mad
        deviation = abs(peak - median)

        return deviation > threshold

    def _predict_next_value(self, channel: str) -> float:
        """
        Predict next value using linear extrapolation.

        Uses last 3 points to fit linear trend and extrapolate.

        Args:
            channel: Channel identifier

        Returns:
            Predicted peak position
        """
        history = list(self.peak_history[channel])

        if len(history) < 3:
            return np.median(history)

        # Use last 3 points for linear fit
        x = np.array([0, 1, 2])
        y = np.array(history[-3:])

        try:
            coeffs = np.polyfit(x, y, 1)  # Linear fit: y = mx + b
            predicted = coeffs[0] * 3 + coeffs[1]  # Extrapolate to x=3

            # Sanity check: prediction shouldn't be too far from recent values
            if abs(predicted - history[-1]) > 5.0:  # More than 5nm away
                logger.debug(
                    f"Consensus Ch {channel}: Prediction too far "
                    f"({predicted:.3f} vs {history[-1]:.3f}), using median"
                )
                return np.median(history)

            return predicted
        except Exception as e:
            logger.debug(f"Consensus Ch {channel}: Prediction failed: {e}")
            return np.median(history)

    def _calculate_confidence(
        self,
        disagreement: float,
        parabolic_success: bool,
        num_pixels: int
    ) -> float:
        """
        Calculate confidence score (0.0-1.0) based on method agreement.

        High confidence: Methods agree, good pixel count
        Low confidence: Methods disagree, poor fit, few pixels

        Args:
            disagreement: |centroid - parabolic| in nm
            parabolic_success: Whether parabolic fit succeeded
            num_pixels: Number of pixels used in centroid

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 1.0

        # Penalize disagreement
        if disagreement > 0.5:
            confidence *= 0.5
        elif disagreement > 0.3:
            confidence *= 0.8

        # Penalize parabolic failure
        if not parabolic_success:
            confidence *= 0.9

        # Penalize low pixel count (< 10)
        if num_pixels < 10:
            confidence *= 0.7
        elif num_pixels < 15:
            confidence *= 0.9

        return confidence

    def _create_error_result(self, channel: str) -> Dict:
        """Create error result dictionary"""
        return {
            'peak_nm': np.nan,
            'centroid_nm': np.nan,
            'parabolic_nm': None,
            'num_pixels': 0,
            'centroid_threshold': 0.0,
            'parabolic_success': False,
            'disagreement_nm': 0.0,
            'is_outlier': False,
            'confidence': 0.0,
            'outlier_rate': self.outlier_count[channel] / max(1, self.total_count[channel]),
            'error': True
        }

    def get_statistics(self, channel: str) -> Dict:
        """
        Get performance statistics for a channel.

        Args:
            channel: Channel identifier

        Returns:
            dict with mean, std, peak-to-peak, outlier_rate, etc.
        """
        history = list(self.peak_history[channel])

        if len(history) < 2:
            return {'error': 'Insufficient data', 'total_samples': self.total_count[channel]}

        return {
            'mean': np.mean(history),
            'std': np.std(history),
            'peak_to_peak': np.max(history) - np.min(history),
            'min': np.min(history),
            'max': np.max(history),
            'outlier_rate': self.outlier_count[channel] / max(1, self.total_count[channel]),
            'outlier_count': self.outlier_count[channel],
            'total_samples': self.total_count[channel],
            'history_size': len(history)
        }
