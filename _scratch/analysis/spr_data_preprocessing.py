"""SPR Data Preprocessing Module

Handles data preparation before kinetic analysis:
- Baseline correction
- Reference subtraction (double referencing)
- Y-axis zeroing and alignment
- Smoothing and outlier removal
- Time range selection
- Curve alignment

Author: AI Assistant
Date: February 2, 2026
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from typing import Dict, Tuple, Optional


class SPRPreprocessor:
    """Preprocessing pipeline for SPR sensorgram data."""
    
    def __init__(self, time_data: np.ndarray, response_data: np.ndarray):
        """Initialize with raw data.
        
        Args:
            time_data: Time array (seconds)
            response_data: Response array (RU or nm)
        """
        self.time_original = time_data.copy()
        self.response_original = response_data.copy()
        
        # Working copies
        self.time = time_data.copy()
        self.response = response_data.copy()
        
        # Track preprocessing steps
        self.steps_applied = []
    
    def baseline_correction(self, baseline_start: float, baseline_end: float) -> 'SPRPreprocessor':
        """Subtract average baseline from pre-injection region.
        
        Args:
            baseline_start: Start time of baseline region (s)
            baseline_end: End time of baseline region (s)
            
        Returns:
            Self for method chaining
        """
        # Find baseline region
        mask = (self.time >= baseline_start) & (self.time <= baseline_end)
        
        if not mask.any():
            raise ValueError(f"No data in baseline region {baseline_start}-{baseline_end}s")
        
        # Calculate average baseline
        baseline_value = np.mean(self.response[mask])
        
        # Subtract from entire curve
        self.response = self.response - baseline_value
        
        self.steps_applied.append(f"Baseline correction: {baseline_value:.2f} RU subtracted")
        return self
    
    def zero_at_time(self, zero_time: float, window: float = 5.0) -> 'SPRPreprocessor':
        """Set response to zero at specific timepoint (e.g., injection start).
        
        Args:
            zero_time: Time to set as zero point (s)
            window: Averaging window around zero_time (s)
            
        Returns:
            Self for method chaining
        """
        # Find points near zero time
        mask = (self.time >= zero_time - window/2) & (self.time <= zero_time + window/2)
        
        if not mask.any():
            raise ValueError(f"No data near zero time {zero_time}s")
        
        # Average response in window
        zero_value = np.mean(self.response[mask])
        
        # Subtract from entire curve
        self.response = self.response - zero_value
        
        self.steps_applied.append(f"Zeroed at t={zero_time}s: {zero_value:.2f} RU")
        return self
    
    def reference_subtraction(self, reference_response: np.ndarray) -> 'SPRPreprocessor':
        """Subtract reference channel or blank injection.
        
        Args:
            reference_response: Reference sensorgram (same length as data)
            
        Returns:
            Self for method chaining
        """
        if len(reference_response) != len(self.response):
            raise ValueError("Reference must have same length as data")
        
        self.response = self.response - reference_response
        
        self.steps_applied.append("Reference subtraction applied")
        return self
    
    def double_reference(
        self, 
        reference_surface: np.ndarray, 
        blank_injection: np.ndarray
    ) -> 'SPRPreprocessor':
        """Apply double referencing: subtract both reference surface and blank.
        
        Standard SPR best practice to remove bulk refractive index changes
        and non-specific binding.
        
        Args:
            reference_surface: Response from reference spot/channel
            blank_injection: Response from blank buffer injection
            
        Returns:
            Self for method chaining
        """
        if len(reference_surface) != len(self.response):
            raise ValueError("Reference surface must match data length")
        
        if len(blank_injection) != len(self.response):
            raise ValueError("Blank injection must match data length")
        
        # Double referencing formula
        self.response = self.response - reference_surface - blank_injection
        
        self.steps_applied.append("Double referencing applied")
        return self
    
    def smooth(self, window_length: int = 11, polyorder: int = 3) -> 'SPRPreprocessor':
        """Apply Savitzky-Golay smoothing filter.
        
        Args:
            window_length: Length of filter window (must be odd)
            polyorder: Polynomial order for fitting
            
        Returns:
            Self for method chaining
        """
        if window_length % 2 == 0:
            window_length += 1  # Must be odd
        
        if window_length > len(self.response):
            window_length = len(self.response) if len(self.response) % 2 == 1 else len(self.response) - 1
        
        self.response = savgol_filter(self.response, window_length, polyorder)
        
        self.steps_applied.append(f"Smoothed: window={window_length}, poly={polyorder}")
        return self
    
    def moving_average(self, window_size: int = 5) -> 'SPRPreprocessor':
        """Apply moving average smoothing.
        
        Args:
            window_size: Number of points to average
            
        Returns:
            Self for method chaining
        """
        kernel = np.ones(window_size) / window_size
        self.response = np.convolve(self.response, kernel, mode='same')
        
        self.steps_applied.append(f"Moving average: window={window_size}")
        return self
    
    def remove_outliers(self, threshold: float = 3.0) -> 'SPRPreprocessor':
        """Remove outliers using z-score method.
        
        Args:
            threshold: Z-score threshold (typically 2-3)
            
        Returns:
            Self for method chaining
        """
        # Calculate z-scores
        mean = np.mean(self.response)
        std = np.std(self.response)
        z_scores = np.abs((self.response - mean) / std)
        
        # Find outliers
        outliers = z_scores > threshold
        n_outliers = np.sum(outliers)
        
        # Interpolate outliers
        if n_outliers > 0:
            # Use linear interpolation to replace outliers
            good_indices = np.where(~outliers)[0]
            outlier_indices = np.where(outliers)[0]
            
            self.response[outliers] = np.interp(
                outlier_indices, 
                good_indices, 
                self.response[good_indices]
            )
        
        self.steps_applied.append(f"Outliers removed: {n_outliers} points (z>{threshold})")
        return self
    
    def trim_time_range(self, start_time: float, end_time: float) -> 'SPRPreprocessor':
        """Select specific time range for analysis.
        
        Args:
            start_time: Start time (s)
            end_time: End time (s)
            
        Returns:
            Self for method chaining
        """
        mask = (self.time >= start_time) & (self.time <= end_time)
        
        if not mask.any():
            raise ValueError(f"No data in range {start_time}-{end_time}s")
        
        self.time = self.time[mask]
        self.response = self.response[mask]
        
        self.steps_applied.append(f"Trimmed to {start_time}-{end_time}s")
        return self
    
    def align_to_time(self, target_time: float) -> 'SPRPreprocessor':
        """Shift time axis so target_time becomes t=0.
        
        Args:
            target_time: Time to align to (becomes new zero)
            
        Returns:
            Self for method chaining
        """
        self.time = self.time - target_time
        
        self.steps_applied.append(f"Time aligned: t={target_time}s → t=0")
        return self
    
    def normalize_to_max(self) -> 'SPRPreprocessor':
        """Normalize response to maximum value (0-1 range).
        
        Returns:
            Self for method chaining
        """
        max_val = np.max(self.response)
        min_val = np.min(self.response)
        
        if max_val == min_val:
            raise ValueError("Cannot normalize: constant response")
        
        self.response = (self.response - min_val) / (max_val - min_val)
        
        self.steps_applied.append("Normalized to 0-1")
        return self
    
    def get_processed_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get processed time and response data.
        
        Returns:
            (time_array, response_array) tuple
        """
        return self.time, self.response
    
    def get_processing_summary(self) -> str:
        """Get summary of applied preprocessing steps.
        
        Returns:
            Formatted string with all steps
        """
        if not self.steps_applied:
            return "No preprocessing applied"
        
        summary = "Preprocessing steps applied:\n"
        for i, step in enumerate(self.steps_applied, 1):
            summary += f"  {i}. {step}\n"
        return summary
    
    def reset(self) -> 'SPRPreprocessor':
        """Reset to original data.
        
        Returns:
            Self for method chaining
        """
        self.time = self.time_original.copy()
        self.response = self.response_original.copy()
        self.steps_applied = []
        return self


# ============================================================================
# Helper Functions
# ============================================================================

def auto_baseline_correction(time: np.ndarray, response: np.ndarray) -> Tuple[np.ndarray, float]:
    """Automatically detect and correct baseline using first 10% of data.
    
    Args:
        time: Time array
        response: Response array
        
    Returns:
        (corrected_response, baseline_value)
    """
    # Use first 10% as baseline
    baseline_points = int(len(response) * 0.1)
    baseline_value = np.mean(response[:baseline_points])
    
    corrected = response - baseline_value
    return corrected, baseline_value


def detect_injection_start(time: np.ndarray, response: np.ndarray, threshold: float = 0.5) -> float:
    """Automatically detect injection start time from response change.
    
    Args:
        time: Time array
        response: Response array
        threshold: Minimum response change to detect (RU)
        
    Returns:
        Estimated injection start time (s)
    """
    # Calculate derivative
    dt = np.diff(time)
    dR = np.diff(response)
    derivative = dR / dt
    
    # Smooth derivative
    if len(derivative) > 5:
        derivative = savgol_filter(derivative, 5, 2)
    
    # Find first significant positive derivative
    for i, deriv in enumerate(derivative):
        if deriv > threshold:
            return time[i]
    
    # Fallback: return 10% into data
    return time[int(len(time) * 0.1)]


def segment_sensorgram(
    time: np.ndarray, 
    response: np.ndarray,
    injection_start: float,
    injection_end: float
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Segment sensorgram into baseline, association, and dissociation phases.
    
    Args:
        time: Time array
        response: Response array
        injection_start: When analyte injection starts
        injection_end: When analyte injection ends
        
    Returns:
        Dictionary with 'baseline', 'association', 'dissociation' segments
    """
    segments = {}
    
    # Baseline (before injection)
    baseline_mask = time < injection_start
    segments['baseline'] = (time[baseline_mask], response[baseline_mask])
    
    # Association (during injection)
    assoc_mask = (time >= injection_start) & (time < injection_end)
    segments['association'] = (time[assoc_mask], response[assoc_mask])
    
    # Dissociation (after injection)
    dissoc_mask = time >= injection_end
    segments['dissociation'] = (time[dissoc_mask], response[dissoc_mask])
    
    return segments


# ============================================================================
# Example Usage
# ============================================================================

def example_preprocessing():
    """Example preprocessing workflow for SPR data."""
    
    # Load data (example)
    df = pd.read_excel("experiment.xlsx", sheet_name="Channel Data")
    time = df["Time A (s)"].values
    response = df["Channel A (nm)"].values
    
    # Convert wavelength to RU (if needed)
    WAVELENGTH_TO_RU = 355.0
    response_ru = response * WAVELENGTH_TO_RU
    
    # Create preprocessor
    prep = SPRPreprocessor(time, response_ru)
    
    # Apply preprocessing pipeline
    prep.baseline_correction(0, 50)           # Baseline: first 50s
    prep.zero_at_time(60)                     # Zero at injection start
    prep.smooth(window_length=11)             # Smooth data
    prep.remove_outliers(threshold=3.0)       # Remove spikes
    prep.trim_time_range(60, 360)             # Keep association phase
    prep.align_to_time(60)                    # Shift so injection = t=0
    
    # Get processed data
    t_processed, R_processed = prep.get_processed_data()
    
    # Print summary
    print(prep.get_processing_summary())
    
    return t_processed, R_processed


if __name__ == "__main__":
    # Demo with synthetic data
    t = np.linspace(0, 600, 600)
    R = 5 + 0.01*t + 50*(1 - np.exp(-0.01*(t-100))) * (t > 100)  # Simulated binding
    R += np.random.normal(0, 0.5, len(t))  # Add noise
    
    print("SPR Data Preprocessing Demo")
    print("=" * 60)
    
    # Process data
    prep = SPRPreprocessor(t, R)
    prep.baseline_correction(0, 90)
    prep.zero_at_time(100, window=10)
    prep.smooth(window_length=11)
    prep.remove_outliers(threshold=3.0)
    
    t_clean, R_clean = prep.get_processed_data()
    
    print(prep.get_processing_summary())
    print(f"\nOriginal: {len(t)} points, range [{R.min():.1f}, {R.max():.1f}] RU")
    print(f"Processed: {len(t_clean)} points, range [{R_clean.min():.1f}, {R_clean.max():.1f}] RU")
