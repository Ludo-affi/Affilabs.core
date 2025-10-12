"""Afterglow Correction Module

Loads optical calibration τ tables and applies LED phosphor afterglow correction
to measurements. This is a passive module - it does NOT run calibration, only
loads and applies corrections from pre-existing optical calibration files.

Typical Usage:
    # In SPRDataAcquisition.__init__():
    from afterglow_correction import AfterglowCorrection
    self.afterglow_correction = AfterglowCorrection(
        'optical_calibration/system_FLMT09788_20251011.json'
    )

    # In measurement loop:
    corrected_signal = self.afterglow_correction.apply_correction(
        measured_signal,
        previous_channel='a',
        integration_time_ms=55.0,
        delay_ms=5.0
    )

Calibration File Format:
    {
        "metadata": {...},
        "channel_data": {
            "a": {
                "integration_time_data": [
                    {
                        "integration_time_ms": 20.0,
                        "tau_ms": 21.45,
                        "amplitude": 1234.5,
                        "baseline": 890.2,
                        "r_squared": 0.978
                    },
                    ...
                ]
            },
            "b": {...},
            "c": {...},
            "d": {...}
        }
    }

Author: GitHub Copilot (generated for control-3.2.9)
Date: October 11, 2025
"""

from pathlib import Path
import json
import numpy as np
from scipy.interpolate import CubicSpline
from utils.logger import logger


class AfterglowCorrection:
    """Apply LED phosphor afterglow correction using optical calibration data.

    This class loads pre-computed optical calibration data (τ, amplitude, baseline
    as functions of integration time) and applies exponential decay corrections
    to measurements affected by LED afterglow from previous channels.

    Physics Model:
        signal(t) = baseline + A × exp(-t/τ)

    where:
        - t: time since LED turned off (delay_ms)
        - τ: phosphor decay time constant (ms) - function of integration time
        - A: amplitude of exponential component - function of integration time
        - baseline: steady-state residual phosphor glow

    Integration Time Dependency:
        τ(int_time) varies because longer exposures accumulate more phosphor energy.
        Typical range: τ ∈ [15, 25]ms for integration times 10-80ms.
    """

    def __init__(self, calibration_file: str | Path):
        """Load optical calibration from JSON file.

        Args:
            calibration_file: Path to optical calibration JSON file
                             (e.g., 'optical_calibration/system_FLMT09788_20251011.json')

        Raises:
            FileNotFoundError: If calibration file doesn't exist
            ValueError: If calibration data is invalid or missing required fields
        """
        self.calibration_file = Path(calibration_file)
        self.calibration_data = self._load_calibration()
        self._build_interpolators()

        logger.info(f"✅ Optical calibration loaded: {self.calibration_file.name}")
        logger.info(f"   Channels: {list(self.tau_interpolators.keys())}")
        logger.info(
            f"   Integration time range: "
            f"{self.int_time_range_ms[0]:.1f}-{self.int_time_range_ms[1]:.1f} ms"
        )
        logger.info(
            f"   τ range (Ch A): "
            f"{self._get_tau_range('a')[0]:.2f}-{self._get_tau_range('a')[1]:.2f} ms"
        )

    def _load_calibration(self) -> dict:
        """Load and validate calibration JSON.

        Returns:
            Parsed JSON data as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not self.calibration_file.exists():
            raise FileNotFoundError(
                f"Optical calibration file not found: {self.calibration_file}\n"
                f"Expected path (absolute): {self.calibration_file.resolve()}\n"
                f"Run optical calibration first to generate this file."
            )

        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in calibration file: {self.calibration_file}\n"
                f"Error: {e}"
            )

        # Validate structure
        if 'channel_data' not in data:
            raise ValueError(
                f"Invalid calibration file: missing 'channel_data' key\n"
                f"File: {self.calibration_file}"
            )

        # Validate each channel has required data
        required_channels = ['a', 'b', 'c', 'd']
        for channel in required_channels:
            if channel not in data['channel_data']:
                raise ValueError(
                    f"Missing channel '{channel}' in calibration data\n"
                    f"Available channels: {list(data['channel_data'].keys())}"
                )

            ch_data = data['channel_data'][channel]
            if 'integration_time_data' not in ch_data:
                raise ValueError(
                    f"Channel '{channel}' missing 'integration_time_data'\n"
                    f"Available keys: {list(ch_data.keys())}"
                )

            # Validate at least 3 data points for cubic spline
            if len(ch_data['integration_time_data']) < 3:
                raise ValueError(
                    f"Channel '{channel}' has insufficient data points "
                    f"({len(ch_data['integration_time_data'])}). Need at least 3 for interpolation."
                )

        logger.debug(f"Calibration file validated: {len(data['channel_data'])} channels")
        return data

    def _build_interpolators(self):
        """Build cubic spline interpolators for τ(integration_time).

        Creates interpolators for each channel:
            - τ(int_time): decay time constant
            - A(int_time): exponential amplitude
            - baseline(int_time): steady-state offset

        Uses cubic spline for smooth interpolation between calibrated points.
        """
        self.tau_interpolators = {}
        self.amplitude_tables = {}
        self.baseline_tables = {}

        all_int_times = []

        for channel, ch_data in self.calibration_data['channel_data'].items():
            # Extract arrays for interpolation
            int_times = []
            taus = []
            amplitudes = []
            baselines = []

            for data_point in ch_data['integration_time_data']:
                int_times.append(data_point['integration_time_ms'])
                taus.append(data_point['tau_ms'])
                amplitudes.append(data_point['amplitude'])
                baselines.append(data_point['baseline'])

            # Build cubic spline interpolators
            # CubicSpline provides smooth interpolation and extrapolation
            self.tau_interpolators[channel] = CubicSpline(int_times, taus)
            self.amplitude_tables[channel] = CubicSpline(int_times, amplitudes)
            self.baseline_tables[channel] = CubicSpline(int_times, baselines)

            logger.debug(
                f"Ch {channel.upper()}: {len(int_times)} calibration points, "
                f"τ ∈ [{min(taus):.2f}, {max(taus):.2f}] ms"
            )

            all_int_times.extend(int_times)

        # Store integration time range for validation
        self.int_time_range_ms = (min(all_int_times), max(all_int_times))

    def _get_tau_range(self, channel: str) -> tuple[float, float]:
        """Get τ range for a channel (for logging)."""
        int_times = []
        taus = []
        for data_point in self.calibration_data['channel_data'][channel]['integration_time_data']:
            int_times.append(data_point['integration_time_ms'])
            taus.append(data_point['tau_ms'])
        return (min(taus), max(taus))

    def calculate_correction(
        self,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float = 5.0
    ) -> float:
        """Calculate expected afterglow signal from previous channel.

        Uses exponential decay model:
            correction = baseline + A × exp(-delay/τ)

        where τ, A, and baseline are interpolated from calibration data based on
        the integration time used for the measurement.

        Args:
            previous_channel: Channel ID ('a', 'b', 'c', 'd') that was last active
            integration_time_ms: Integration time used for measurement (typically 10-100ms)
            delay_ms: Time delay since previous LED turned off (default: 5.0ms)

        Returns:
            Expected afterglow signal (counts) to subtract from measurement

        Raises:
            ValueError: If channel invalid or integration time severely out of range

        Example:
            >>> correction = cal.calculate_correction('a', 55.0, 5.0)
            >>> print(f"Afterglow: {correction:.1f} counts")
            Afterglow: 1234.5 counts
        """
        # Normalize channel name to lowercase
        channel_lower = previous_channel.lower()

        # Validate channel
        if channel_lower not in self.tau_interpolators:
            raise ValueError(
                f"Invalid channel: '{previous_channel}'. "
                f"Available: {list(self.tau_interpolators.keys())}"
            )

        # Validate integration time
        min_int, max_int = self.int_time_range_ms
        if integration_time_ms < min_int * 0.5 or integration_time_ms > max_int * 1.5:
            # Only raise error if severely out of range (50% margin)
            raise ValueError(
                f"Integration time {integration_time_ms:.1f}ms severely out of "
                f"calibrated range [{min_int:.1f}, {max_int:.1f}]ms. "
                f"Correction would be unreliable."
            )
        elif not (min_int <= integration_time_ms <= max_int):
            # Warning for mild extrapolation
            logger.warning(
                f"⚠️ Integration time {integration_time_ms:.1f}ms outside calibrated "
                f"range [{min_int:.1f}, {max_int:.1f}]ms. Using extrapolation."
            )

        # Interpolate τ, amplitude, baseline for this integration time
        tau = float(self.tau_interpolators[channel_lower](integration_time_ms))
        amplitude = float(self.amplitude_tables[channel_lower](integration_time_ms))
        baseline = float(self.baseline_tables[channel_lower](integration_time_ms))

        # Calculate exponential decay: signal(t) = baseline + A × exp(-t/τ)
        correction = baseline + amplitude * np.exp(-delay_ms / tau)

        logger.debug(
            f"✨ Afterglow correction calculated: "
            f"Ch {previous_channel.upper()} @ {integration_time_ms:.1f}ms, "
            f"delay={delay_ms:.1f}ms → "
            f"τ={tau:.2f}ms, A={amplitude:.1f}, baseline={baseline:.1f} → "
            f"correction={correction:.1f} counts"
        )

        return correction

    def apply_correction(
        self,
        measured_signal: np.ndarray | float,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float = 5.0
    ) -> np.ndarray | float:
        """Apply afterglow correction to measured signal.

        Calculates the expected afterglow and subtracts it from the measurement.
        Works with both scalar values and spectrum arrays.

        Args:
            measured_signal: Raw measured spectrum (array) or single value (scalar)
            previous_channel: Channel that was last active ('a', 'b', 'c', 'd')
            integration_time_ms: Integration time used for measurement (ms)
            delay_ms: Delay since previous LED turned off (ms)

        Returns:
            Corrected signal (same type as input)

        Example:
            >>> # Correct a spectrum array
            >>> corrected = cal.apply_correction(
            ...     spectrum,  # np.array with shape (2048,)
            ...     previous_channel='a',
            ...     integration_time_ms=55.0,
            ...     delay_ms=5.0
            ... )

            >>> # Correct a scalar (e.g., averaged intensity)
            >>> corrected_avg = cal.apply_correction(
            ...     avg_intensity,  # float
            ...     previous_channel='b',
            ...     integration_time_ms=55.0
            ... )
        """
        correction = self.calculate_correction(
            previous_channel, integration_time_ms, delay_ms
        )

        # Subtract correction from signal
        if isinstance(measured_signal, np.ndarray):
            # Array: subtract uniform correction from all pixels
            # (afterglow is spectrally uniform across LED spectrum)
            corrected = measured_signal - correction
        else:
            # Scalar: direct subtraction
            corrected = measured_signal - correction

        return corrected

    def get_calibration_info(self) -> dict:
        """Get information about loaded calibration.

        Returns:
            Dictionary with calibration metadata and parameters

        Example:
            >>> info = cal.get_calibration_info()
            >>> print(f"Calibration from: {info['metadata']['timestamp']}")
            >>> print(f"Channels: {info['channels']}")
        """
        return {
            'file': str(self.calibration_file),
            'channels': list(self.tau_interpolators.keys()),
            'integration_time_range_ms': self.int_time_range_ms,
            'metadata': self.calibration_data.get('metadata', {}),
            'tau_ranges': {
                ch: self._get_tau_range(ch)
                for ch in self.tau_interpolators.keys()
            }
        }

    def validate_correction(
        self,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float,
        measured_uncorrected: float,
        measured_corrected: float,
        expected_clean: float
    ) -> dict:
        """Validate correction by comparing to known clean measurement.

        This is a diagnostic method to check correction accuracy during testing.

        Args:
            previous_channel: Channel that was last active
            integration_time_ms: Integration time used
            delay_ms: Delay used
            measured_uncorrected: Measurement without correction (with afterglow)
            measured_corrected: Measurement after correction applied
            expected_clean: Expected value from clean measurement (long delay)

        Returns:
            Dictionary with validation metrics:
                - 'correction_value': Amount subtracted
                - 'error_before': Error before correction (%)
                - 'error_after': Error after correction (%)
                - 'improvement': Improvement in error (%)

        Example:
            >>> validation = cal.validate_correction(
            ...     'a', 55.0, 5.0,
            ...     measured_uncorrected=25000,
            ...     measured_corrected=23500,
            ...     expected_clean=23450
            ... )
            >>> print(f"Error reduction: {validation['improvement']:.1f}%")
        """
        correction = self.calculate_correction(
            previous_channel, integration_time_ms, delay_ms
        )

        error_before = abs(measured_uncorrected - expected_clean) / expected_clean * 100
        error_after = abs(measured_corrected - expected_clean) / expected_clean * 100
        improvement = error_before - error_after

        result = {
            'correction_value': correction,
            'error_before_pct': error_before,
            'error_after_pct': error_after,
            'improvement_pct': improvement,
            'successful': error_after < error_before
        }

        logger.info(
            f"📊 Validation: Ch {previous_channel.upper()} @ {integration_time_ms:.1f}ms\n"
            f"   Correction: {correction:.1f} counts\n"
            f"   Error before: {error_before:.2f}%\n"
            f"   Error after: {error_after:.2f}%\n"
            f"   Improvement: {improvement:.2f}%\n"
            f"   {'✅ SUCCESS' if result['successful'] else '❌ FAILED'}"
        )

        return result


# ============================================================================
# Example Usage (for testing)
# ============================================================================

if __name__ == "__main__":
    import sys

    # Example: Load calibration and test interpolation
    if len(sys.argv) > 1:
        cal_file = sys.argv[1]
    else:
        cal_file = "optical_calibration/system_FLMT09788_20251011_210859.json"

    print(f"\n{'='*70}")
    print("Afterglow Correction Module - Test")
    print(f"{'='*70}\n")

    try:
        # Load calibration
        print(f"Loading calibration: {cal_file}")
        cal = AfterglowCorrection(cal_file)

        # Get info
        info = cal.get_calibration_info()
        print(f"\n📋 Calibration Info:")
        print(f"   File: {info['file']}")
        print(f"   Channels: {info['channels']}")
        print(f"   Integration time range: {info['integration_time_range_ms']}")

        # Test interpolation at non-calibrated points
        print(f"\n🧪 Testing Interpolation:")
        test_int_times = [30.0, 45.0, 60.0]  # Likely between calibrated points

        for int_time in test_int_times:
            correction = cal.calculate_correction('a', int_time, 5.0)
            print(f"   @ {int_time:.1f}ms: {correction:.1f} counts")

        # Test array correction
        print(f"\n📊 Testing Array Correction:")
        spectrum = np.ones(2048) * 20000  # Simulated spectrum
        corrected = cal.apply_correction(spectrum, 'b', 55.0, 5.0)
        print(f"   Original mean: {np.mean(spectrum):.1f}")
        print(f"   Corrected mean: {np.mean(corrected):.1f}")
        print(f"   Difference: {np.mean(spectrum) - np.mean(corrected):.1f} counts")

        print(f"\n✅ All tests passed!\n")

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print(f"\nℹ️ Run optical calibration first to generate the calibration file.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
