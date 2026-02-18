"""Advanced SPR Data Arrangement System

The MOST CRITICAL part of SPR analysis. This is where users spend 80% of their time.
Focus on making data arrangement fast, intuitive, and visual.

Key Principles:
1. Visual feedback - see changes in real-time
2. Interactive - click, drag, adjust
3. Non-destructive - always preserve original data
4. Quality scoring - automatic detection of problems
5. Templates - save successful arrangements for reuse

Author: AI Assistant
Date: February 2, 2026
"""

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter, find_peaks
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
from enum import Enum


class IssueType(Enum):
    """Types of data quality issues."""
    BASELINE_DRIFT = "baseline_drift"
    BULK_SHIFT = "bulk_shift"
    SPIKE = "spike"
    NOISE = "noise"
    INSUFFICIENT_BASELINE = "insufficient_baseline"
    INCOMPLETE_DISSOCIATION = "incomplete_dissociation"
    NEGATIVE_RESPONSE = "negative_response"
    SATURATION = "saturation"


@dataclass
class DataQualityIssue:
    """Represents a detected quality issue."""
    issue_type: IssueType
    severity: str  # "critical", "warning", "info"
    time_range: Tuple[float, float]
    description: str
    suggested_fix: str
    auto_fixable: bool = False


@dataclass
class CorrectionRegion:
    """Defines a region with specific correction parameters."""
    name: str
    start_time: float
    end_time: float
    correction_type: str  # "baseline", "drift", "spike", "exclude"
    parameters: Dict = field(default_factory=dict)
    enabled: bool = True


class DataQualityAnalyzer:
    """Automatically detect quality issues in SPR data."""
    
    def __init__(self, time: np.ndarray, response: np.ndarray):
        self.time = time
        self.response = response
        self.issues: List[DataQualityIssue] = []
    
    def analyze(self) -> List[DataQualityIssue]:
        """Run all quality checks.
        
        Returns:
            List of detected issues
        """
        self.issues = []
        
        self._check_baseline_drift()
        self._check_spikes()
        self._check_noise_level()
        self._check_negative_response()
        self._check_saturation()
        self._check_baseline_duration()
        
        return self.issues
    
    def _check_baseline_drift(self):
        """Check for baseline drift (linear or polynomial)."""
        # Use first 20% as baseline
        baseline_points = int(len(self.response) * 0.2)
        baseline = self.response[:baseline_points]
        
        # Fit linear trend
        x = np.arange(len(baseline))
        coeffs = np.polyfit(x, baseline, 1)
        drift_rate = coeffs[0]  # RU per point
        
        # Convert to RU per minute
        if len(self.time) > 1:
            dt = np.mean(np.diff(self.time))
            drift_per_min = drift_rate * (60 / dt)
            
            if abs(drift_per_min) > 0.5:  # > 0.5 RU/min
                severity = "critical" if abs(drift_per_min) > 2 else "warning"
                self.issues.append(DataQualityIssue(
                    issue_type=IssueType.BASELINE_DRIFT,
                    severity=severity,
                    time_range=(self.time[0], self.time[baseline_points]),
                    description=f"Baseline drift: {drift_per_min:.2f} RU/min",
                    suggested_fix="Apply polynomial baseline correction",
                    auto_fixable=True
                ))
    
    def _check_spikes(self):
        """Detect outliers/spikes using statistical methods."""
        # Calculate z-scores
        mean = np.mean(self.response)
        std = np.std(self.response)
        z_scores = np.abs((self.response - mean) / std)
        
        # Find spikes (z > 4)
        spike_indices = np.where(z_scores > 4)[0]
        
        if len(spike_indices) > 0:
            # Group consecutive spikes
            spike_groups = []
            current_group = [spike_indices[0]]
            
            for idx in spike_indices[1:]:
                if idx - current_group[-1] <= 5:  # Within 5 points
                    current_group.append(idx)
                else:
                    spike_groups.append(current_group)
                    current_group = [idx]
            spike_groups.append(current_group)
            
            # Report each spike region
            for group in spike_groups:
                start_idx = group[0]
                end_idx = group[-1]
                
                self.issues.append(DataQualityIssue(
                    issue_type=IssueType.SPIKE,
                    severity="warning",
                    time_range=(self.time[start_idx], self.time[end_idx]),
                    description=f"Spike detected: {len(group)} points",
                    suggested_fix="Interpolate or remove spike",
                    auto_fixable=True
                ))
    
    def _check_noise_level(self):
        """Check if noise level is too high."""
        # Use first 20% as baseline to assess noise
        baseline_points = int(len(self.response) * 0.2)
        baseline = self.response[:baseline_points]
        
        # Calculate noise as standard deviation after detrending
        x = np.arange(len(baseline))
        coeffs = np.polyfit(x, baseline, 1)
        trend = np.polyval(coeffs, x)
        noise = np.std(baseline - trend)
        
        if noise > 2.0:  # > 2 RU noise
            severity = "critical" if noise > 5.0 else "warning"
            self.issues.append(DataQualityIssue(
                issue_type=IssueType.NOISE,
                severity=severity,
                time_range=(self.time[0], self.time[-1]),
                description=f"High noise level: {noise:.2f} RU",
                suggested_fix="Apply Savitzky-Golay smoothing",
                auto_fixable=True
            ))
    
    def _check_negative_response(self):
        """Check for negative binding response."""
        # Look for sustained negative values (excluding baseline)
        baseline_end = int(len(self.response) * 0.2)
        
        if baseline_end < len(self.response):
            post_baseline = self.response[baseline_end:]
            
            if np.min(post_baseline) < -5:  # More than -5 RU
                min_idx = np.argmin(post_baseline) + baseline_end
                
                self.issues.append(DataQualityIssue(
                    issue_type=IssueType.NEGATIVE_RESPONSE,
                    severity="warning",
                    time_range=(self.time[min_idx], self.time[min_idx]),
                    description=f"Negative response: {np.min(post_baseline):.1f} RU",
                    suggested_fix="Check reference subtraction or baseline",
                    auto_fixable=False
                ))
    
    def _check_saturation(self):
        """Check if response plateaus (saturation)."""
        # Look for flat regions (low derivative)
        if len(self.response) > 10:
            derivative = np.diff(self.response)
            
            # Find regions where derivative is near zero
            flat_threshold = 0.1  # RU per point
            flat_mask = np.abs(derivative) < flat_threshold
            
            # Count consecutive flat points
            max_flat = 0
            current_flat = 0
            
            for is_flat in flat_mask:
                if is_flat:
                    current_flat += 1
                    max_flat = max(max_flat, current_flat)
                else:
                    current_flat = 0
            
            # If > 50 consecutive flat points, likely saturated
            if max_flat > 50:
                self.issues.append(DataQualityIssue(
                    issue_type=IssueType.SATURATION,
                    severity="info",
                    time_range=(self.time[0], self.time[-1]),
                    description=f"Possible saturation: {max_flat} flat points",
                    suggested_fix="Reduce analyte concentration",
                    auto_fixable=False
                ))
    
    def _check_baseline_duration(self):
        """Check if baseline is long enough."""
        # Assume injection at ~20% into data
        baseline_duration = self.time[int(len(self.time) * 0.2)] - self.time[0]
        
        if baseline_duration < 30:  # Less than 30 seconds
            self.issues.append(DataQualityIssue(
                issue_type=IssueType.INSUFFICIENT_BASELINE,
                severity="warning",
                time_range=(self.time[0], self.time[int(len(self.time) * 0.2)]),
                description=f"Short baseline: {baseline_duration:.0f}s",
                suggested_fix="Extend baseline in future experiments",
                auto_fixable=False
            ))
    
    def get_quality_score(self) -> float:
        """Calculate overall quality score (0-100).
        
        Returns:
            Quality score where 100 = perfect, 0 = unusable
        """
        score = 100.0
        
        for issue in self.issues:
            if issue.severity == "critical":
                score -= 25
            elif issue.severity == "warning":
                score -= 10
            elif issue.severity == "info":
                score -= 5
        
        return max(0, score)


class AdvancedDataArranger:
    """Interactive data arrangement with visual feedback and quality scoring."""
    
    def __init__(self, time: np.ndarray, response: np.ndarray):
        """Initialize with raw data.
        
        Args:
            time: Time array (seconds)
            response: Response array (RU)
        """
        self.time_original = time.copy()
        self.response_original = response.copy()
        
        # Current state
        self.time = time.copy()
        self.response = response.copy()
        
        # Correction history (for undo/redo)
        self.history: List[Tuple[np.ndarray, np.ndarray]] = [(time.copy(), response.copy())]
        self.history_index = 0
        
        # Defined regions
        self.regions: List[CorrectionRegion] = []
        
        # Quality analysis
        self.quality_analyzer = DataQualityAnalyzer(time, response)
        self.issues = []
        
        # Excluded time ranges
        self.excluded_ranges: List[Tuple[float, float]] = []
    
    def analyze_quality(self) -> Tuple[float, List[DataQualityIssue]]:
        """Analyze data quality.
        
        Returns:
            (quality_score, list_of_issues)
        """
        self.quality_analyzer = DataQualityAnalyzer(self.time, self.response)
        self.issues = self.quality_analyzer.analyze()
        score = self.quality_analyzer.get_quality_score()
        
        return score, self.issues
    
    def auto_fix_issues(self, issue_types: Optional[List[IssueType]] = None):
        """Automatically fix detected issues.
        
        Args:
            issue_types: List of issue types to fix, or None for all fixable
        """
        for issue in self.issues:
            if not issue.auto_fixable:
                continue
            
            if issue_types and issue.issue_type not in issue_types:
                continue
            
            if issue.issue_type == IssueType.BASELINE_DRIFT:
                # Apply polynomial baseline correction
                start, end = issue.time_range
                self.correct_baseline_drift(start, end, degree=2)
            
            elif issue.issue_type == IssueType.SPIKE:
                # Interpolate spikes
                start, end = issue.time_range
                self.interpolate_region(start, end)
            
            elif issue.issue_type == IssueType.NOISE:
                # Apply smoothing
                self.smooth_data(method='savgol', window=11)
    
    def correct_baseline_drift(
        self, 
        start_time: float, 
        end_time: float, 
        degree: int = 1
    ):
        """Correct baseline drift using polynomial fit.
        
        Args:
            start_time: Start of baseline region
            end_time: End of baseline region
            degree: Polynomial degree (1=linear, 2=quadratic)
        """
        # Find baseline region
        mask = (self.time >= start_time) & (self.time <= end_time)
        
        # Fit polynomial to baseline
        x_baseline = self.time[mask]
        y_baseline = self.response[mask]
        
        coeffs = np.polyfit(x_baseline, y_baseline, degree)
        
        # Evaluate polynomial over entire time range
        drift = np.polyval(coeffs, self.time)
        
        # Subtract drift
        self.response = self.response - drift
        
        self._save_state()
    
    def interactive_baseline_correction(
        self,
        start_time: float,
        end_time: float,
        target_value: float = 0.0
    ):
        """Interactively adjust baseline to target value.
        
        Args:
            start_time: Start of region to correct
            end_time: End of region to correct
            target_value: Target baseline value (usually 0)
        """
        mask = (self.time >= start_time) & (self.time <= end_time)
        current_mean = np.mean(self.response[mask])
        offset = target_value - current_mean
        
        self.response[mask] += offset
        
        self._save_state()
    
    def segment_baseline_correction(
        self,
        segments: List[Tuple[float, float, float]]
    ):
        """Apply different baseline corrections to different segments.
        
        Args:
            segments: List of (start, end, target_value) tuples
        """
        for start, end, target in segments:
            self.interactive_baseline_correction(start, end, target)
    
    def interpolate_region(self, start_time: float, end_time: float):
        """Interpolate over a region (remove spikes/artifacts).
        
        Args:
            start_time: Start of bad region
            end_time: End of bad region
        """
        mask = (self.time >= start_time) & (self.time <= end_time)
        
        # Get points before and after bad region
        before_idx = np.where(self.time < start_time)[0]
        after_idx = np.where(self.time > end_time)[0]
        
        if len(before_idx) > 0 and len(after_idx) > 0:
            # Use last point before and first point after
            t1, r1 = self.time[before_idx[-1]], self.response[before_idx[-1]]
            t2, r2 = self.time[after_idx[0]], self.response[after_idx[0]]
            
            # Linear interpolation
            t_interp = self.time[mask]
            r_interp = r1 + (r2 - r1) * (t_interp - t1) / (t2 - t1)
            
            self.response[mask] = r_interp
        
        self._save_state()
    
    def smooth_data(self, method: str = 'savgol', window: int = 11, **kwargs):
        """Apply smoothing to reduce noise.
        
        Args:
            method: 'savgol', 'moving_avg', or 'gaussian'
            window: Window size
            **kwargs: Additional parameters for smoothing method
        """
        if method == 'savgol':
            polyorder = kwargs.get('polyorder', 3)
            if window % 2 == 0:
                window += 1
            self.response = savgol_filter(self.response, window, polyorder)
        
        elif method == 'moving_avg':
            kernel = np.ones(window) / window
            self.response = np.convolve(self.response, kernel, mode='same')
        
        elif method == 'gaussian':
            from scipy.ndimage import gaussian_filter1d
            sigma = kwargs.get('sigma', window/4)
            self.response = gaussian_filter1d(self.response, sigma)
        
        self._save_state()
    
    def exclude_region(self, start_time: float, end_time: float):
        """Mark region as excluded from analysis.
        
        Args:
            start_time: Start of excluded region
            end_time: End of excluded region
        """
        self.excluded_ranges.append((start_time, end_time))
    
    def get_analysis_ready_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get data with excluded regions removed.
        
        Returns:
            (time_array, response_array) with exclusions applied
        """
        mask = np.ones(len(self.time), dtype=bool)
        
        for start, end in self.excluded_ranges:
            exclude_mask = (self.time >= start) & (self.time <= end)
            mask &= ~exclude_mask
        
        return self.time[mask], self.response[mask]
    
    def define_phases(
        self,
        baseline_end: float,
        association_end: float,
        dissociation_end: float
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Define and extract different experimental phases.
        
        Args:
            baseline_end: End of baseline phase
            association_end: End of association phase
            dissociation_end: End of dissociation phase
            
        Returns:
            Dictionary with 'baseline', 'association', 'dissociation' data
        """
        phases = {}
        
        # Baseline
        mask = self.time < baseline_end
        phases['baseline'] = (self.time[mask], self.response[mask])
        
        # Association
        mask = (self.time >= baseline_end) & (self.time < association_end)
        phases['association'] = (self.time[mask], self.response[mask])
        
        # Dissociation
        mask = (self.time >= association_end) & (self.time < dissociation_end)
        phases['dissociation'] = (self.time[mask], self.response[mask])
        
        return phases
    
    def align_to_injection(self, injection_time: float):
        """Align time axis so injection is t=0.
        
        Args:
            injection_time: Time of injection start
        """
        self.time = self.time - injection_time
        self._save_state()
    
    def undo(self):
        """Undo last operation."""
        if self.history_index > 0:
            self.history_index -= 1
            self.time, self.response = self.history[self.history_index]
            self.time = self.time.copy()
            self.response = self.response.copy()
    
    def redo(self):
        """Redo last undone operation."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.time, self.response = self.history[self.history_index]
            self.time = self.time.copy()
            self.response = self.response.copy()
    
    def reset(self):
        """Reset to original data."""
        self.time = self.time_original.copy()
        self.response = self.response_original.copy()
        self.history = [(self.time.copy(), self.response.copy())]
        self.history_index = 0
        self.regions = []
        self.excluded_ranges = []
    
    def _save_state(self):
        """Save current state to history."""
        # Remove any future states if we're not at the end
        self.history = self.history[:self.history_index + 1]
        
        # Add new state
        self.history.append((self.time.copy(), self.response.copy()))
        self.history_index += 1
        
        # Limit history size
        if len(self.history) > 50:
            self.history.pop(0)
            self.history_index -= 1
    
    def export_correction_pipeline(self) -> Dict:
        """Export current corrections as reusable pipeline.
        
        Returns:
            Dictionary describing all corrections applied
        """
        return {
            'regions': [
                {
                    'name': r.name,
                    'start': r.start_time,
                    'end': r.end_time,
                    'type': r.correction_type,
                    'params': r.parameters
                }
                for r in self.regions
            ],
            'excluded_ranges': self.excluded_ranges,
            'quality_score': self.quality_analyzer.get_quality_score()
        }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_comprehensive_arrangement():
    """Example of complete data arrangement workflow."""
    
    # 1. Load raw data
    import pandas as pd
    df = pd.read_excel("experiment.xlsx", sheet_name="Channel Data")
    time = df["Time A (s)"].values
    response = df["Channel A (nm)"].values * 355  # Convert to RU
    
    # 2. Create arranger
    arranger = AdvancedDataArranger(time, response)
    
    # 3. Analyze quality
    score, issues = arranger.analyze_quality()
    print(f"Initial quality score: {score}/100")
    
    for issue in issues:
        print(f"  [{issue.severity}] {issue.description}")
        print(f"    → {issue.suggested_fix}")
    
    # 4. Auto-fix what we can
    arranger.auto_fix_issues()
    
    # 5. Manual corrections
    # Correct baseline drift in first 60s
    arranger.correct_baseline_drift(0, 60, degree=1)
    
    # Zero at injection start
    arranger.interactive_baseline_correction(55, 65, target_value=0)
    
    # Remove spike at 150s
    arranger.interpolate_region(148, 152)
    
    # Smooth data
    arranger.smooth_data(method='savgol', window=11)
    
    # 6. Define phases
    phases = arranger.define_phases(
        baseline_end=60,
        association_end=180,
        dissociation_end=600
    )
    
    # 7. Align to injection
    arranger.align_to_injection(injection_time=60)
    
    # 8. Get final data
    t_final, R_final = arranger.get_analysis_ready_data()
    
    # 9. Re-check quality
    score_final, _ = arranger.analyze_quality()
    print(f"\nFinal quality score: {score_final}/100")
    
    # 10. Export pipeline
    pipeline = arranger.export_correction_pipeline()
    
    return t_final, R_final, pipeline


if __name__ == "__main__":
    # Demo with synthetic data
    print("=" * 80)
    print("ADVANCED SPR DATA ARRANGEMENT SYSTEM")
    print("=" * 80)
    
    # Create synthetic problematic data
    t = np.linspace(0, 600, 600)
    
    # Baseline with drift
    baseline = 5 + 0.02 * t
    
    # Binding curve
    binding = np.where(t > 100, 50 * (1 - np.exp(-0.01*(t-100))), 0)
    
    # Dissociation
    binding = np.where(t > 300, binding[299] * np.exp(-0.005*(t-300)), binding)
    
    # Add noise
    noise = np.random.normal(0, 1.5, len(t))
    
    # Add some spikes
    spikes = np.zeros(len(t))
    spikes[200] = 20
    spikes[450] = -15
    
    R = baseline + binding + noise + spikes
    
    # Arrange data
    arranger = AdvancedDataArranger(t, R)
    
    print("\n1. QUALITY ANALYSIS")
    score, issues = arranger.analyze_quality()
    print(f"   Quality Score: {score:.1f}/100")
    print(f"   Issues Found: {len(issues)}")
    
    for issue in issues:
        print(f"   • [{issue.severity.upper()}] {issue.description}")
    
    print("\n2. APPLYING AUTO-FIXES")
    arranger.auto_fix_issues()
    
    print("\n3. MANUAL CORRECTIONS")
    arranger.correct_baseline_drift(0, 100, degree=1)
    arranger.interactive_baseline_correction(95, 105, target_value=0)
    print("   ✓ Baseline corrected")
    print("   ✓ Zeroed at injection")
    
    print("\n4. FINAL QUALITY")
    score_final, _ = arranger.analyze_quality()
    print(f"   Quality Score: {score_final:.1f}/100")
    print(f"   Improvement: +{score_final - score:.1f} points")
    
    print("\n" + "=" * 80)
    print("Data is now ready for kinetic analysis!")
    print("=" * 80)
