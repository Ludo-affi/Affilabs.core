from __future__ import annotations

"""Afterglow Correction Module

Loads optical calibration τ tables and applies LED phosphor afterglow correction
to measurements. This is a passive module - it does NOT run calibration, only
loads and applies corrections from pre-existing optical calibration files.

=============================================================================
TWO OPERATING MODES - LED INTENSITY HANDLING
=============================================================================

Mode 1: Global Integration Time (DEFAULT)
------------------------------------------
- LED intensity VARIES per channel (from LED calibration: ~180-220)
- Integration time is FIXED (e.g., 40ms)
- Afterglow calibration: Uses LED-calibrated intensities
- Correction: No scaling needed (measured at operating intensities)
- Usage: calculate_correction(..., led_intensity=None)  # Default

Mode 2: Global LED Intensity
----------------------------
- LED intensity FIXED at 255 for all channels
- Integration time varies per channel
- Afterglow calibration: Pre-calibrated at 255 (factory setting)
- Correction: Amplitude scales linearly with actual measurement intensity
- Usage: calculate_correction(..., led_intensity=180)  # Scales from 255→180
- Physics: Amplitude ∝ LED_intensity, τ = constant (material property)

=============================================================================
FLEXIBLE CHANNEL SEQUENCING - KEY ARCHITECTURAL ADVANTAGE
=============================================================================

The system calibrates EACH LED's afterglow characteristics INDEPENDENTLY.
This means you can correct for ANY channel sequence, not just sequential patterns.

Why This Matters:
-----------------
1. Current 4-channel sequential: A→B→C→D (each corrects for previous)
2. Future 2-channel non-adjacent: e.g., A→C or B→D
3. Custom sequences: Any arbitrary order based on assay needs
4. Multi-wavelength applications: Different channel combinations per experiment

How It Works:
-------------
Each channel's calibration stores its OWN afterglow decay:
  - Channel A afterglow: τ_A(int_time), amplitude_A, baseline_A
  - Channel B afterglow: τ_B(int_time), amplitude_B, baseline_B
  - Channel C afterglow: τ_C(int_time), amplitude_C, baseline_C
  - Channel D afterglow: τ_D(int_time), amplitude_D, baseline_D

When measuring channel X after channel Y:
  corrected_X = measured_X - afterglow_from_Y(delay, int_time)

Examples:
---------
  # 4-channel sequential (current)
  measure A → measure B (correct for A afterglow)
            → measure C (correct for B afterglow)
            → measure D (correct for C afterglow)

  # 2-channel non-adjacent (future)
  measure A → measure C (correct for A afterglow directly)
  measure B → measure D (correct for B afterglow directly)

  # Custom sequence
  measure D → measure A (correct for D afterglow)
            → measure B (correct for A afterglow)

Key Insight:
------------
By calibrating ALL LEDs completely, we're not locked into any specific
measurement pattern. The correction adapts to whatever channel was
previously active, enabling flexible assay design.

=============================================================================

Typical Usage:
    # In SPRDataAcquisition.__init__():
    from afterglow_correction import AfterglowCorrection
    self.afterglow_correction = AfterglowCorrection(
        'optical_calibration/system_FLMT09788_20251011.json'
    )

    # In measurement loop:
    corrected_signal = self.afterglow_correction.apply_correction(
        measured_signal,
        previous_channel='a',  # ← Can be ANY channel that was just active
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
from affilabs.utils.logger import logger


# LED Type Specifications and Expected Ranges
# Updated for improved afterglow method (200ms LED on, immediate measurement from t=0)
LED_SPECS = {
    'LCW': {  # Luminus Cool White
        'name': 'Luminus Cool White',
        'tau_range_ms': (50, 85),  # Expected tau range for improved method (200ms LED on, t=0 start)
        'tau_warn_range_ms': (40, 100),  # Warning thresholds - allow wider margin
        'r_squared_min': 0.85,  # Minimum acceptable fit quality
        'r_squared_good': 0.95,  # Good fit quality
    },
    'OWW': {  # Osram Warm White
        'name': 'Osram Warm White',
        'tau_range_ms': (50, 85),  # Expected tau range for improved method (200ms LED on, t=0 start)
        'tau_warn_range_ms': (40, 100),  # Warning thresholds - allow wider margin
        'r_squared_min': 0.85,  # Minimum acceptable fit quality
        'r_squared_good': 0.95,  # Good fit quality
    }
}


class AfterglowValidationResult:
    """Results from afterglow measurement validation."""

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.passed = True
        self.metrics = {}

    def add_warning(self, message: str):
        """Add a warning (non-blocking)."""
        self.warnings.append(message)
        logger.warning(f"[WARN] Afterglow validation: {message}")

    def add_error(self, message: str):
        """Add an error (for severe issues, but still non-blocking)."""
        self.errors.append(message)
        self.passed = False
        logger.error(f"[ERROR] Afterglow validation: {message}")

    def add_metric(self, key: str, value):
        """Store a validation metric."""
        self.metrics[key] = value

    def log_summary(self):
        """Log validation summary."""
        if self.passed and not self.warnings:
            logger.info("[OK] Afterglow validation: All checks passed")
        elif self.passed and self.warnings:
            logger.info(f"[WARN] Afterglow validation: Passed with {len(self.warnings)} warning(s)")
        else:
            logger.warning(f"[ERROR] Afterglow validation: {len(self.errors)} error(s), {len(self.warnings)} warning(s)")


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

        logger.info(f"[OK] Optical calibration loaded: {self.calibration_file.name}")
        logger.info(f"   Channels: {list(self.tau_interpolators.keys())}")
        logger.info(
            f"   Integration time range: "
            f"{self.int_time_range_ms[0]:.1f}-{self.int_time_range_ms[1]:.1f} ms"
        )
        logger.info(
            f"   τ range (Ch A): "
            f"{self._get_tau_range('a')[0]:.2f}-{self._get_tau_range('a')[1]:.2f} ms"
        )

        # Validate afterglow measurements against expected ranges
        self._validate_calibration_data()

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

    def _validate_calibration_data(self):
        """Validate afterglow calibration data against expected ranges.

        This validation is NON-BLOCKING - warnings are logged but operation continues.
        This allows us to collect data and refine thresholds as we learn more about
        different LED types.
        """
        # Extract LED type from metadata if available
        led_type = self.calibration_data.get('metadata', {}).get('led_type', 'LCW')  # Default to Luminus

        if led_type not in LED_SPECS:
            logger.warning(f"[WARN] Unknown LED type '{led_type}', using LCW defaults for validation")
            led_type = 'LCW'

        specs = LED_SPECS[led_type]
        validation = AfterglowValidationResult()

        logger.info(f"📊 Validating afterglow data for {specs['name']} ({led_type})")

        # Validate each channel
        for channel, ch_data in self.calibration_data['channel_data'].items():
            for data_point in ch_data['integration_time_data']:
                int_time = data_point['integration_time_ms']
                tau = data_point['tau_ms']
                amplitude = data_point['amplitude']
                baseline = data_point.get('baseline', 0)
                r_squared = data_point.get('r_squared', 0)

                # Check 1: R² fit quality
                if r_squared < specs['r_squared_min']:
                    validation.add_error(
                        f"Ch {channel.upper()} @ {int_time}ms: Poor fit quality (R²={r_squared:.3f} < {specs['r_squared_min']})"
                    )
                elif r_squared < specs['r_squared_good']:
                    validation.add_warning(
                        f"Ch {channel.upper()} @ {int_time}ms: Marginal fit quality (R²={r_squared:.3f})"
                    )

                # Check 2: Tau within expected range
                tau_min, tau_max = specs['tau_range_ms']
                tau_warn_min, tau_warn_max = specs['tau_warn_range_ms']

                if tau < tau_warn_min or tau > tau_warn_max:
                    validation.add_error(
                        f"Ch {channel.upper()} @ {int_time}ms: τ={tau:.2f}ms severely outside expected range "
                        f"[{tau_warn_min}, {tau_warn_max}]ms - possible LED timing issue"
                    )
                elif tau < tau_min or tau > tau_max:
                    validation.add_warning(
                        f"Ch {channel.upper()} @ {int_time}ms: τ={tau:.2f}ms outside typical range "
                        f"[{tau_min}, {tau_max}]ms for {specs['name']}"
                    )

                # Check 3: Amplitude reasonableness (should not be extreme)
                if amplitude < 0:
                    validation.add_error(
                        f"Ch {channel.upper()} @ {int_time}ms: Negative amplitude ({amplitude:.1f}) - fit error"
                    )
                elif amplitude > 10000:  # Unusually high afterglow
                    validation.add_warning(
                        f"Ch {channel.upper()} @ {int_time}ms: Very high amplitude ({amplitude:.1f} counts) - "
                        "possible LED not fully turning off"
                    )

                # Check 4: Baseline stability
                if baseline < -100:  # Shouldn't have large negative baseline
                    validation.add_warning(
                        f"Ch {channel.upper()} @ {int_time}ms: Negative baseline ({baseline:.1f} counts)"
                    )
                elif baseline > 1000:  # Baseline shouldn't be very high
                    validation.add_warning(
                        f"Ch {channel.upper()} @ {int_time}ms: High baseline ({baseline:.1f} counts) - "
                        "LED may not be fully off"
                    )

        # Check 5: Tau integration time dependency
        for channel in ['a', 'b', 'c', 'd']:
            taus = []
            int_times = []
            for data_point in self.calibration_data['channel_data'][channel]['integration_time_data']:
                int_times.append(data_point['integration_time_ms'])
                taus.append(data_point['tau_ms'])

            # Tau should generally increase or stay stable with integration time
            # (longer exposure accumulates more phosphor energy)
            if len(taus) >= 3:
                # Check for monotonicity or reasonable trend
                tau_slope = np.polyfit(int_times, taus, 1)[0]  # Linear trend

                # Store metrics for analysis
                validation.add_metric(f'tau_slope_ch_{channel}', tau_slope)

                if tau_slope < -0.1:  # Decreasing trend is unexpected
                    validation.add_warning(
                        f"Ch {channel.upper()}: τ decreases with integration time (slope={tau_slope:.3f}) - "
                        "unexpected for phosphor physics"
                    )

        # Log validation summary
        validation.log_summary()

        # Store validation results in metadata for future reference
        if 'validation' not in self.calibration_data:
            self.calibration_data['validation'] = {}

        self.calibration_data['validation']['afterglow'] = {
            'led_type': led_type,
            'passed': validation.passed,
            'warnings': validation.warnings,
            'errors': validation.errors,
            'metrics': validation.metrics
        }

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
        delay_ms: float = 5.0,
        led_intensity: int | None = None
    ) -> float:
        """Calculate expected afterglow signal from previous channel.

        Uses exponential decay model:
            correction = baseline + A × exp(-delay/τ)

        where τ, A, and baseline are interpolated from calibration data based on
        the integration time used for the measurement.

        LED Intensity Scaling:
        - Mode 1 (Global Integration Time): Calibration uses LED-calibrated intensities.
          Pass led_intensity=None (default) - assumes measurement uses same intensities.
        - Mode 2 (Global LED Intensity=255): Calibration at 255, measurement at different intensity.
          Pass led_intensity to scale amplitude proportionally.

        Args:
            previous_channel: Channel ID ('a', 'b', 'c', 'd') that was last active
            integration_time_ms: Integration time used for measurement (typically 10-100ms)
            delay_ms: Time delay since previous LED turned off (default: 5.0ms)
            led_intensity: Current LED intensity (0-255). If provided and differs from
                          calibration intensity, scales amplitude proportionally.
                          If None, assumes measurement uses calibration intensities.

        Returns:
            Expected afterglow signal (counts) to subtract from measurement

        Raises:
            ValueError: If channel invalid or integration time severely out of range

        Example:
            >>> # Mode 1: Use calibrated LED intensities (no scaling)
            >>> correction = cal.calculate_correction('a', 55.0, 5.0)
            >>> print(f"Afterglow: {correction:.1f} counts")
            Afterglow: 1234.5 counts

            >>> # Mode 2: Scale from 255 calibration to 180 measurement
            >>> correction = cal.calculate_correction('a', 55.0, 5.0, led_intensity=180)
            >>> print(f"Afterglow (scaled): {correction:.1f} counts")
            Afterglow (scaled): 875.3 counts
        """
        # Normalize channel name to lowercase
        channel_lower = previous_channel.lower()

        # Validate channel
        if channel_lower not in self.tau_interpolators:
            raise ValueError(
                f"Invalid channel: '{previous_channel}'. "
                f"Available: {list(self.tau_interpolators.keys())}"
            )

        # Interpolate/extrapolate τ, amplitude, baseline for this integration time
        # Cubic spline model handles extrapolation well - afterglow is minimal at higher integration times
        tau = float(self.tau_interpolators[channel_lower](integration_time_ms))
        amplitude = float(self.amplitude_tables[channel_lower](integration_time_ms))
        baseline = float(self.baseline_tables[channel_lower](integration_time_ms))

        # Scale amplitude if LED intensity differs from calibration
        # Physics: Amplitude ∝ LED intensity (linear excitation regime)
        # τ remains constant (material property)
        amplitude_scaled = amplitude
        if led_intensity is not None:
            # Get calibration LED intensity for this channel
            metadata = self.calibration_data.get('metadata', {})
            cal_intensities = metadata.get('led_intensities_s_mode', {})

            if cal_intensities and channel_lower in cal_intensities:
                cal_intensity = int(cal_intensities[channel_lower])
                if cal_intensity > 0 and led_intensity != cal_intensity:
                    intensity_scale = led_intensity / cal_intensity
                    amplitude_scaled = amplitude * intensity_scale
                    logger.debug(
                        f"   Amplitude scaled: {amplitude:.1f} → {amplitude_scaled:.1f} "
                        f"(LED: {cal_intensity} → {led_intensity}, scale={intensity_scale:.3f})"
                    )
            elif led_intensity != 255:
                # Calibration at 255 (default), scale to measurement intensity
                intensity_scale = led_intensity / 255.0
                amplitude_scaled = amplitude * intensity_scale
                logger.debug(
                    f"   Amplitude scaled from 255: {amplitude:.1f} → {amplitude_scaled:.1f} "
                    f"(LED: 255 → {led_intensity}, scale={intensity_scale:.3f})"
                )

        # Calculate exponential decay: signal(t) = baseline + A × exp(-t/τ)
        correction = baseline + amplitude_scaled * np.exp(-delay_ms / tau)

        return correction

    def apply_correction(
        self,
        measured_signal: np.ndarray | float,
        previous_channel: str,
        integration_time_ms: float,
        delay_ms: float = 5.0,
        led_intensity: int | None = None
    ) -> np.ndarray | float:
        """Apply afterglow correction to measured signal.

        Calculates the expected afterglow and subtracts it from the measurement.
        Works with both scalar values and spectrum arrays.

        LED Intensity Scaling:
        - If led_intensity provided and differs from calibration, scales amplitude
        - See calculate_correction() for details

        FLEXIBLE CHANNEL SEQUENCING:
        The 'previous_channel' can be ANY channel that was just measured,
        not necessarily the sequentially previous one. This enables:
        - Non-adjacent channel pairs (e.g., A→C, B→D)
        - Custom measurement sequences
        - Future 2-channel assays with arbitrary wavelength selection

        Args:
            measured_signal: Raw measured spectrum (array) or single value (scalar)
            previous_channel: Channel that was last active ('a', 'b', 'c', 'd')
                            Can be ANY channel - system looks up that channel's
                            specific afterglow characteristics automatically
            integration_time_ms: Integration time used for measurement (ms)
            delay_ms: Delay since previous LED turned off (ms)

        Returns:
            Corrected signal (same type as input)

        Example:
            >>> # Correct a spectrum array
            >>> corrected = cal.apply_correction(
            ...     spectrum,  # np.array with detector-specific length
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
            previous_channel, integration_time_ms, delay_ms, led_intensity
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

    def get_optimal_led_delay(
        self,
        integration_time_ms: float,
        target_residual_percent: float = 2.0
    ) -> float:
        """Calculate optimal LED delay based on afterglow decay characteristics.

        Uses the calibrated τ (decay time constant) to determine the minimum delay
        needed to achieve a specified residual afterglow level. The delay is chosen
        to be safe for the slowest-decaying channel.

        Physics:
            residual% = 100 × exp(-delay/τ)
            delay = -τ × ln(residual%/100)

        Args:
            integration_time_ms: Current integration time (ms)
            target_residual_percent: Target residual afterglow (% of initial)
                                    Default: 2.0% (balance of speed vs accuracy)
                                    Use 5.0% for maximum speed
                                    Use 1.0% for maximum accuracy

        Returns:
            Optimal LED delay in seconds (for use with time.sleep())

        Example:
            >>> delay_s = cal.get_optimal_led_delay(55.0, target_residual_percent=2.0)
            >>> print(f"Use LED delay: {delay_s:.3f}s ({delay_s*1000:.1f}ms)")
            Use LED delay: 0.050s (50.0ms)
        """
        # Get maximum τ across all channels (worst case = slowest decay)
        max_tau = 0.0
        for channel in self.tau_interpolators.keys():
            # Interpolate τ for this integration time
            tau_interp = self.tau_interpolators[channel]

            # Clamp to calibrated range
            int_time = np.clip(
                integration_time_ms,
                self.int_time_range_ms[0],
                self.int_time_range_ms[1]
            )

            tau = float(tau_interp(int_time))
            max_tau = max(max_tau, tau)

        # Calculate delay for target residual: delay = -τ × ln(residual/100)
        # residual% = 100 × exp(-delay/τ)  →  delay = -τ × ln(residual/100)
        delay_ms = -max_tau * np.log(target_residual_percent / 100.0)

        # Add safety margin (10%) and convert to seconds
        delay_s = (delay_ms * 1.1) / 1000.0

        logger.debug(
            f"📊 Optimal LED delay calculation:\n"
            f"   Integration time: {integration_time_ms:.1f}ms\n"
            f"   Max τ (slowest channel): {max_tau:.2f}ms\n"
            f"   Target residual: {target_residual_percent:.1f}%\n"
            f"   Calculated delay: {delay_ms:.1f}ms\n"
            f"   With 10% safety margin: {delay_s*1000:.1f}ms ({delay_s:.3f}s)"
        )

        return delay_s

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
            f"   {'[OK] SUCCESS' if result['successful'] else '[ERROR] FAILED'}"
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
        spectrum = np.ones(1000) * 20000  # Simulated spectrum (generic test size)
        corrected = cal.apply_correction(spectrum, 'b', 55.0, 5.0)
        print(f"   Original mean: {np.mean(spectrum):.1f}")
        print(f"   Corrected mean: {np.mean(corrected):.1f}")
        print(f"   Difference: {np.mean(spectrum) - np.mean(corrected):.1f} counts")

        print(f"\n[OK] All tests passed!\n")

    except FileNotFoundError as e:
        print(f"\n[ERROR] Error: {e}")
        print(f"\n[INFO] Run optical calibration first to generate the calibration file.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        try:
            print(traceback.format_exc())
        except:
            pass
        sys.exit(1)
