from __future__ import annotations

"""LED Calibration Model Loader - 3-Stage Linear Model.

Loads pre-computed 3-stage linear LED calibration models and provides
instant LED intensity calculations without iterative search.

Model Equation: counts = slope_10ms × intensity × (time_ms / 10)

This replaces the old bilinear model with a simpler, faster linear model.

Author: ezControl-AI System
Date: December 10, 2025
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class ModelNotFoundError(Exception):
    """Raised when LED calibration model not found for device."""


class ModelValidationError(Exception):
    """Raised when model validation fails."""


class LEDCalibrationModelLoader:
    """Loads and uses 3-stage linear LED calibration models.

    Replaces iterative LED balancing with direct mathematical calculation.
    Model: counts = slope_10ms × intensity × (time_ms / 10)
    """

    def __init__(self, qc_base_path: Path | None = None) -> None:
        """Initialize model loader.

        Args:
            qc_base_path: Base path to LED calibration data folder.
                         If None, uses project_root/led_calibration_official/spr_calibration/data/

        """
        if qc_base_path is None:
            project_root = Path(__file__).resolve().parents[2]
            self.qc_base_path = (
                project_root / "led_calibration_official" / "spr_calibration" / "data"
            )
        else:
            self.qc_base_path = Path(qc_base_path)

        self.model_data = None
        self.detector_serial = None

    def load_model(self, detector_serial: str) -> dict:
        """Load 3-stage linear LED calibration model.

        Args:
            detector_serial: Detector serial number (e.g., "FLMT09116")

        Returns:
            Dictionary containing LED model parameters

        Raises:
            ModelNotFoundError: If model file not found

        """
        self.detector_serial = detector_serial

        # Try finding latest 3-stage calibration file
        # Pattern: led_calibration_3stage_YYYYMMDD_HHMMSS.json
        import glob

        pattern = str(self.qc_base_path / "led_calibration_3stage_*.json")
        model_files = sorted(glob.glob(pattern), reverse=True)  # Most recent first

        if not model_files:
            msg = (
                f"No 3-stage LED calibration model found in {self.qc_base_path}. "
                f"Run: python led_calibration_official/1_create_model.py"
            )
            raise ModelNotFoundError(
                msg,
            )

        model_file = Path(model_files[0])
        logger.info(f"Loading 3-stage LED calibration model: {model_file.name}")

        with open(model_file) as f:
            raw_data = json.load(f)

        # Transform to standard format expected by downstream code
        # New 3-stage format: {"led_models": {"A": [[10, slope_10], [20, slope_20], [30, slope_30]]}}
        # Expected output: {"bilinear_models": {"A": {"S": {r2, slope_10ms}}}}

        if "led_models" in raw_data:
            logger.info("  Converting 3-stage model to standard format")
            transformed = {
                "detector_serial": detector_serial,
                "timestamp": raw_data.get(
                    "timestamp",
                    model_file.stem.replace("led_calibration_3stage_", ""),
                ),
                "model_equation": "counts = slope_10ms × intensity × (time_ms / 10)",
                "calibration_type": "3-Stage Linear",
                "detector_max": 65535,
                "dark": raw_data.get("dark_counts_per_time", {}),
                "bilinear_models": {},  # Keep name for compatibility
                "correction_factors": raw_data.get(
                    "correction_factors",
                    {},
                ),  # NEW: Validation-based corrections
                "average_corrections": raw_data.get(
                    "average_corrections",
                    {},
                ),  # NEW: Fallback corrections
            }

            # Extract slopes from multistage model
            for led, stages in raw_data["led_models"].items():
                # Handle both formats:
                # Old: [[10, slope_10], [20, slope_20], [30, slope_30]]
                # New: [{"time_ms": 10, "slope": slope_10}, {"time_ms": 20, "slope": slope_20}, ...]

                # Extract 10ms slope (first stage)
                if len(stages) > 0:
                    if isinstance(stages[0], dict):
                        # New format: {"time_ms": 10, "slope": value}
                        slope_10ms = stages[0].get("slope", 0)
                    else:
                        # Old format: [10, slope]
                        slope_10ms = stages[0][1]
                else:
                    slope_10ms = 0

                # Calculate linearity as R² indicator (ratio of 20ms/10ms should be ~2.0)
                if len(stages) >= 2:
                    expected_20ms = slope_10ms * 2.0
                    if isinstance(stages[1], dict):
                        actual_20ms = stages[1].get("slope", 0)
                    else:
                        actual_20ms = stages[1][1]
                    linearity_20 = (
                        actual_20ms / expected_20ms if expected_20ms > 0 else 0
                    )
                else:
                    linearity_20 = 1.0

                if len(stages) >= 3:
                    expected_30ms = slope_10ms * 3.0
                    if isinstance(stages[2], dict):
                        actual_30ms = stages[2].get("slope", 0)
                    else:
                        actual_30ms = stages[2][1]
                    linearity_30 = (
                        actual_30ms / expected_30ms if expected_30ms > 0 else 0
                    )
                else:
                    linearity_30 = 1.0

                # Average linearity as pseudo-R² (1.0 = perfect, <0.95 = poor)
                pseudo_r2 = (linearity_20 + linearity_30) / 2.0

                # Store in compatible format (S and P have same values since no polarization in 3-stage)
                transformed["bilinear_models"][led] = {
                    "S": {
                        "slope_10ms": slope_10ms,
                        "r2": pseudo_r2,
                        "linearity": [linearity_20, linearity_30],
                    },
                    "P": {
                        "slope_10ms": slope_10ms,
                        "r2": pseudo_r2,
                        "linearity": [linearity_20, linearity_30],
                    },
                }

            self.model_data = transformed
        else:
            # Unexpected format
            msg = "Invalid 3-stage model format: missing 'led_models' key"
            raise ModelValidationError(msg)

        # Validate model structure
        self._validate_model_structure()

        logger.info(f"✓ Model loaded: {detector_serial}")
        logger.info(f"  Channels: {list(self.model_data['bilinear_models'].keys())}")
        logger.info("  Polarizations: S, P")

        return self.model_data

    def _validate_model_structure(self) -> None:
        """Validate loaded 3-stage linear model has required structure and quality.

        QC CHECKS:
        1. Required keys present (detector_serial, timestamp, bilinear_models)
        2. All 4 channels (A, B, C, D) present
        3. Both polarizations (S, P) present for each channel
        4. Required parameters present (slope_10ms)
        5. Linearity check (pseudo-R² from stage ratios)
        6. Physical constraints (slope > 0)
        """
        if not self.model_data:
            msg = "No model data loaded"
            raise ModelValidationError(msg)

        # === CHECK 1: Required top-level keys ===
        required_keys = ["bilinear_models", "detector_serial", "timestamp"]
        missing_keys = [key for key in required_keys if key not in self.model_data]
        if missing_keys:
            msg = f"Model missing required keys: {missing_keys}"
            raise ModelValidationError(msg)

        # === CHECK 2: All channels present ===
        models = self.model_data["bilinear_models"]
        required_channels = ["A", "B", "C", "D"]
        missing_channels = [ch for ch in required_channels if ch not in models]
        if missing_channels:
            msg = f"Model missing channels: {missing_channels}"
            raise ModelValidationError(msg)

        # === CHECK 3-6: Validate each channel ===
        validation_errors = []
        validation_warnings = []

        for channel in required_channels:
            for pol in ["S", "P"]:
                if pol not in models[channel]:
                    validation_errors.append(f"Missing {channel}-{pol} polarization")
                    continue

                params = models[channel][pol]
                prefix = f"{channel}-{pol}"

                # === 3-STAGE LINEAR MODEL VALIDATION ===
                if "slope_10ms" not in params:
                    validation_errors.append(f"{prefix}: missing slope_10ms parameter")
                    continue

                slope_10ms = params["slope_10ms"]

                # QC CHECK: Pseudo-R² from linearity ratios
                r2 = params.get("r2", 1.0)
                if r2 < 0.95:
                    validation_warnings.append(
                        f"{prefix}: Linearity={r2:.4f} below recommended threshold (0.95)",
                    )

                # QC CHECK: Physical constraints - slope must be positive
                if slope_10ms <= 0:
                    validation_errors.append(
                        f"{prefix}: Invalid slope_10ms={slope_10ms:.4f} (must be > 0)",
                    )
                    # 'a' is sensitivity slope (counts/intensity/ms) - typically small
                    if abs(a) > 100:
                        validation_warnings.append(
                            f"{prefix}: Large 'a' coefficient ({a:.2f}) - verify calibration data",
                        )

                    # 'c' is dark slope (counts/ms) - typically 1-1000 range
                    if abs(c) > 10000:
                        validation_warnings.append(
                            f"{prefix}: Large 'c' coefficient ({c:.2f}) - verify dark correction",
                        )

                    logger.info(
                        f"   ✓ {prefix}: a={a:.4f}, b={b:.2f}, c={c:.2f}, d={d:.2f}, R²={r2:.4f}",
                    )

        # === FAIL HARD ON ERRORS ===
        if validation_errors:
            error_msg = "Model validation FAILED:\n  " + "\n  ".join(validation_errors)
            raise ModelValidationError(error_msg)

        # === WARN ON QUALITY ISSUES ===
        if validation_warnings:
            logger.warning("⚠️  Model validation warnings:")
            for warning in validation_warnings:
                logger.warning(f"   • {warning}")

        logger.info("✓ Model structure validated successfully")

    def calculate_led_intensity(
        self,
        led: str,
        polarization: str,
        time_ms: float,
        target_counts: float,
        safety_margin: float = 1.0,
    ) -> int:
        """Calculate LED intensity to achieve target counts.

        Args:
            led: LED channel ('A', 'B', 'C', 'D')
            polarization: 'S' or 'P' (not used in 3-stage model, kept for compatibility)
            time_ms: Integration time in milliseconds
            target_counts: Desired detector counts
            safety_margin: Safety factor (1.0 = 100% of calculated, 0.95 = 95%)

        Returns:
            LED intensity (0-255)

        Uses 3-stage linear model: counts = slope_10ms × intensity × (time_ms / 10)
        Solves for intensity: I = target_counts / (slope_10ms × (time_ms / 10))

        """
        if not self.model_data:
            msg = "No model loaded. Call load_model() first."
            raise ModelValidationError(msg)

        try:
            # Get model parameters (S and P are identical in 3-stage model)
            params = self.model_data["bilinear_models"][led]["S"]
            slope_10ms = params["slope_10ms"]

            # 3-stage linear formula: counts = slope_10ms × intensity × (time_ms / 10)
            # Solve for intensity: I = target_counts / (slope_10ms × (time_ms / 10))

            if slope_10ms <= 0 or time_ms <= 0:
                logger.error(
                    f"Invalid parameters for {led}: slope_10ms={slope_10ms}, time_ms={time_ms}",
                )
                return 255

            # Calculate required intensity
            intensity_float = target_counts / (slope_10ms * (time_ms / 10.0))

            # Apply correction factor if available (compensates for model non-linearity)
            correction_factor = self._get_correction_factor(led, time_ms, slope_10ms)
            if correction_factor != 1.0:
                logger.debug(
                    f"{led}: Applying correction factor {correction_factor:.4f} @ {time_ms}ms",
                )
                intensity_float *= correction_factor

            # Apply safety margin (default 1.0 = no reduction)
            intensity_float *= safety_margin

            # Clamp to valid range [1, 255]
            intensity = int(np.clip(intensity_float, 1, 255))

            logger.debug(
                f"{led}: t={time_ms}ms, target={target_counts:.0f}, "
                f"slope_10ms={slope_10ms:.2f}, I={intensity}",
            )

            return intensity

        except KeyError as e:
            logger.exception(f"Missing model parameter for {led}: {e}")
            return 255
        except Exception as e:
            logger.exception(
                f"Error calculating LED intensity for {led}-{polarization}: {e}",
            )
            import traceback

            traceback.print_exc()
            return 255

    def _get_correction_factor(
        self,
        led: str,
        time_ms: float,
        slope_10ms: float = None,
    ) -> float:
        """Get correction factor for LED at specific integration time.

        Correction factors compensate for model non-linearity at longer integration times.
        If exact time not found, interpolates between nearest times or uses average fallback.
        For bright LEDs (high slope) at longer times without data, applies conservative scaling.

        Args:
            led: LED channel ('A', 'B', 'C', 'D')
            time_ms: Integration time in milliseconds
            slope_10ms: LED brightness (counts/intensity @ 10ms), used for conservative scaling

        Returns:
            Correction factor (typically 0.5-1.3, lower for bright LEDs at long times)

        """
        if not self.model_data:
            return 1.0

        correction_factors = self.model_data.get("correction_factors", {})
        average_corrections = self.model_data.get("average_corrections", {})

        # Try exact match: correction_factors[time_ms][led]
        time_key = str(int(time_ms))  # JSON keys are strings
        if time_key in correction_factors:
            led_corrections = correction_factors[time_key]
            if led in led_corrections:
                return led_corrections[led]

        # Interpolate between available times for this LED
        available_times = sorted([int(t) for t in correction_factors.keys()])
        if available_times and led in correction_factors.get(
            str(available_times[0]),
            {},
        ):
            # Collect this LED's correction factors at measured times
            led_cf_times = []
            led_cf_values = []
            for t in available_times:
                t_key = str(t)
                if led in correction_factors.get(t_key, {}):
                    led_cf_times.append(t)
                    led_cf_values.append(correction_factors[t_key][led])

            if len(led_cf_times) >= 2:
                # Interpolate between nearest times
                if time_ms <= led_cf_times[0]:
                    # Below first measured time - use first correction
                    correction = led_cf_values[0]
                    logger.debug(
                        f"{led}: Using {led_cf_times[0]}ms correction ({correction:.4f}) for {time_ms}ms",
                    )
                    return correction
                if time_ms >= led_cf_times[-1]:
                    # Above last measured time - use last correction
                    correction = led_cf_values[-1]
                    logger.debug(
                        f"{led}: Using {led_cf_times[-1]}ms correction ({correction:.4f}) for {time_ms}ms",
                    )
                    return correction
                # Interpolate between two nearest times
                for i in range(len(led_cf_times) - 1):
                    t1, t2 = led_cf_times[i], led_cf_times[i + 1]
                    if t1 <= time_ms <= t2:
                        cf1, cf2 = led_cf_values[i], led_cf_values[i + 1]
                        # Linear interpolation
                        weight = (time_ms - t1) / (t2 - t1)
                        correction = cf1 + weight * (cf2 - cf1)
                        logger.debug(
                            f"{led}: Interpolated correction {correction:.4f} for {time_ms}ms (between {t1}ms and {t2}ms)",
                        )
                        return correction
            elif len(led_cf_times) == 1:
                # Only one measurement - use it
                correction = led_cf_values[0]
                logger.debug(
                    f"{led}: Using only available correction ({correction:.4f}) for {time_ms}ms",
                )
                return correction

        # Fallback to average correction for this integration time
        if time_key in average_corrections:
            logger.debug(f"{led}: Using average correction for {time_ms}ms")
            return average_corrections[time_key]

        # Interpolate average corrections if time not exact match
        if average_corrections:
            avg_times = sorted([int(t) for t in average_corrections.keys()])
            if avg_times:
                if time_ms <= avg_times[0]:
                    correction = average_corrections[str(avg_times[0])]
                    logger.debug(
                        f"{led}: Using {avg_times[0]}ms avg correction ({correction:.4f}) for {time_ms}ms",
                    )
                    return correction
                if time_ms >= avg_times[-1]:
                    correction = average_corrections[str(avg_times[-1])]
                    logger.debug(
                        f"{led}: Using {avg_times[-1]}ms avg correction ({correction:.4f}) for {time_ms}ms",
                    )
                    return correction
                # Interpolate average corrections
                for i in range(len(avg_times) - 1):
                    t1, t2 = avg_times[i], avg_times[i + 1]
                    if t1 <= time_ms <= t2:
                        cf1 = average_corrections[str(t1)]
                        cf2 = average_corrections[str(t2)]
                        weight = (time_ms - t1) / (t2 - t1)
                        correction = cf1 + weight * (cf2 - cf1)
                        logger.debug(
                            f"{led}: Interpolated avg correction {correction:.4f} for {time_ms}ms",
                        )
                        return correction

        # CONSERVATIVE SAFETY: For bright LEDs (high slope) at longer times without correction data,
        # apply aggressive reduction to prevent saturation. Bright LEDs show non-linear saturation.
        if slope_10ms and slope_10ms > 80 and time_ms > 50:
            # LEDs with slope > 80 (like LED B=88, LED C=119) saturate at longer integration times
            # Apply scaling: reduce intensity more aggressively for brighter LEDs at longer times
            # Formula: correction = 0.5 + 0.5 * (50 / time_ms)
            # At 50ms: 1.0 (no reduction)
            # At 60ms: 0.92 (8% reduction)
            # At 70ms: 0.86 (14% reduction)
            # At 100ms: 0.75 (25% reduction)
            safety_correction = 0.5 + 0.5 * (50.0 / time_ms)
            logger.warning(
                f"{led}: BRIGHT LED (slope={slope_10ms:.1f}) @ {time_ms}ms - "
                f"applying conservative correction {safety_correction:.3f} to prevent saturation",
            )
            return safety_correction

        # No correction available
        return 1.0

    def get_slopes(
        self,
        polarization: str,
        channels: list | None = None,
    ) -> dict[str, float]:
        """Get slope_10ms calibration values for specified channels.

        Args:
            polarization: 'S' or 'P'
            channels: List of channels. If None, uses ['A', 'B', 'C', 'D']

        Returns:
            Dictionary: {channel: slope_10ms}

        """
        if channels is None:
            channels = ["A", "B", "C", "D"]

        slopes = {}
        for channel in channels:
            try:
                slopes[channel] = self.model_data["bilinear_models"][channel][
                    polarization
                ]["slope_10ms"]
            except (KeyError, TypeError):
                slopes[channel] = 0.0  # Fallback if channel/pol missing

        return slopes

    def calculate_all_led_intensities(
        self,
        polarization: str,
        time_ms: float,
        target_counts: float,
        channels: list | None = None,
    ) -> dict[str, int]:
        """Calculate intensities for all LED channels.

        Args:
            polarization: 'S' or 'P'
            time_ms: Integration time in milliseconds
            target_counts: Desired detector counts
            channels: List of channels to calculate. If None, uses ['A', 'B', 'C', 'D']

        Returns:
            Dictionary: {channel: intensity}

        """
        if channels is None:
            channels = ["A", "B", "C", "D"]

        intensities = {}
        for channel in channels:
            intensities[channel] = self.calculate_led_intensity(
                channel,
                polarization,
                time_ms,
                target_counts,
            )

        return intensities

    def calculate_optimal_time(
        self,
        led: str,
        polarization: str,
        target_counts: float,
        max_time_ms: float = 60.0,
        intensity: int = 255,
    ) -> float:
        """Calculate optimal integration time to achieve target counts.

        Args:
            led: LED channel ('A', 'B', 'C', or 'D')
            polarization: 'S' or 'P'
            target_counts: Desired detector counts
            max_time_ms: Maximum allowed integration time (default: 60ms)
            intensity: LED intensity to use (default: 255, max brightness)

        Returns:
            Optimal integration time in milliseconds

        Formula: time_ms = (target_counts / (slope_10ms × intensity)) × 10

        """
        try:
            params = self.model_data["bilinear_models"][led][polarization]
            slope_10ms = params["slope_10ms"]

            # Solve for time: target = slope_10ms × intensity × (time / 10)
            # time = (target / (slope_10ms × intensity)) × 10
            time_ms = (target_counts / (slope_10ms * intensity)) * 10.0

            # Clamp to valid range [10, max_time_ms]
            time_ms = np.clip(time_ms, 10.0, max_time_ms)

            return float(time_ms)

        except Exception as e:
            logger.exception(
                f"Error calculating optimal time for {led}-{polarization}: {e}",
            )
            return max_time_ms  # Fallback to max time

    def get_default_parameters(
        self,
        target_counts: float = 52428,
        max_time_ms: float = 60.0,
    ) -> dict:
        """Calculate optimal FIXED integration time and VARIABLE LED intensities.

        Strategy:
        1. Find time needed for each LED at max intensity (255) to reach target
        2. Use LONGEST time (weakest LED) as the fixed integration time
        3. Calculate variable LED intensities for other LEDs at this fixed time

        This ensures:
        - All LEDs can reach target counts (weakest LED sets the time requirement)
        - Weakest LED operates at intensity=255, others scale down proportionally
        - Time stays within max_time_ms constraint (default: 60ms)

        Args:
            target_counts: Target detector counts (default: 52428 = 80% of 65535)
            max_time_ms: Maximum integration time constraint (default: 60ms)

        Returns:
            Dictionary with:
                - integration_time_ms: Optimal fixed integration time
                - target_counts: Target counts used
                - led_intensities: Dict of variable LED intensities (A, B, C, D)
                - mode: '4led' (all LEDs active)
                - channels: ['A', 'B', 'C', 'D']

        Example:
            >>> loader = LEDCalibrationModelLoader()
            >>> loader.load_model("FLMT09116")
            >>> params = loader.get_default_parameters()
            >>> print(f"Fixed time: {params['integration_time_ms']}ms")
            >>> print(f"Variable intensities: {params['led_intensities']}")
            # Fixed time: 45.2ms
            # Variable intensities: {'A': 156, 'B': 189, 'C': 218, 'D': 255}
            # (LED D is weakest, requires longest time, operates at max intensity)

        """
        if not self.model_data:
            msg = "No model loaded. Call load_model() first."
            raise ModelValidationError(msg)

        channels = ["A", "B", "C", "D"]

        # Find time needed for each LED at max intensity (255) to reach target
        optimal_times = {}
        for led in channels:
            optimal_times[led] = self.calculate_optimal_time(
                led,
                "S",
                target_counts,
                max_time_ms,
                intensity=255,
            )

        # Use the longest time (weakest LED determines global integration time)
        # Weakest LED will be at intensity=255, others will scale down
        integration_time_ms = max(optimal_times.values())

        # Calculate variable LED intensities for this fixed time
        led_intensities = self.calculate_all_led_intensities(
            polarization="S",
            time_ms=integration_time_ms,
            target_counts=target_counts,
            channels=channels,
        )

        return {
            "integration_time_ms": integration_time_ms,
            "target_counts": target_counts,
            "led_intensities": led_intensities,
            "mode": "4led",
            "channels": channels,
        }

    def validate_model_range(
        self,
        time_ms: float,
        intensity: int,
        max_counts: int = 60000,
    ) -> tuple[bool, str]:
        """Validate if parameters are within model's valid range.

        Args:
            time_ms: Integration time in milliseconds
            intensity: LED intensity (0-255)
            max_counts: Maximum safe counts (default: 60k)

        Returns:
            (is_valid, message)

        """
        # Model validated range: 10-60ms, counts < 60k
        if time_ms < 10 or time_ms > 60:
            return False, f"Integration time {time_ms}ms out of range (10-60ms)"

        if intensity < 0 or intensity > 255:
            return False, f"Intensity {intensity} out of range (0-255)"

        # Estimate counts for all channels using 3-stage linear model
        # counts = slope_10ms × intensity × (time_ms / 10)
        for channel in ["A", "B", "C", "D"]:
            params = self.model_data["bilinear_models"][channel]["S"]
            slope_10ms = params["slope_10ms"]

            estimated_counts = slope_10ms * intensity * (time_ms / 10.0)

            if estimated_counts > max_counts:
                return False, f"{channel} would saturate: {estimated_counts:.0f} counts"

        return True, "Within valid range"

    def validate_convergence_vs_model(
        self,
        polarization: str,
        time_ms: float,
        measured_leds: dict[str, int],
        target_counts: float,
    ) -> dict:
        """Validate converged LED values against model predictions.

        Provides QC metric showing how well the model predicts hardware behavior.

        Args:
            polarization: 'S' or 'P'
            time_ms: Integration time used during convergence
            measured_leds: Dictionary of measured LED values {channel: intensity}
            target_counts: Target detector counts used during convergence

        Returns:
            Dictionary with:
                - predicted_leds: Model predictions for same conditions
                - measured_leds: Actual converged values
                - deviations: Difference (measured - predicted)
                - percent_errors: Percentage errors
                - average_error_percent: Mean absolute error
                - max_error_percent: Maximum absolute error
                - validation_status: 'excellent', 'good', 'fair', or 'poor'

        """
        if not self.model_data:
            msg = "No model loaded"
            raise ModelValidationError(msg)

        predicted_leds = {}
        deviations = {}
        percent_errors = {}

        for channel, measured_led in measured_leds.items():
            # Get model prediction for same conditions
            predicted_led = self.calculate_led_intensity(
                channel,
                polarization,
                time_ms,
                target_counts,
                safety_margin=1.0,
            )

            predicted_leds[channel] = predicted_led
            deviations[channel] = measured_led - predicted_led

            # Calculate percent error (based on predicted value)
            if predicted_led > 0:
                percent_errors[channel] = (deviations[channel] / predicted_led) * 100.0
            else:
                percent_errors[channel] = 0.0

        # Calculate summary statistics
        abs_errors = [abs(pct) for pct in percent_errors.values()]
        avg_error = np.mean(abs_errors) if abs_errors else 0.0
        max_error = np.max(abs_errors) if abs_errors else 0.0

        # Classify validation quality
        if max_error < 5.0:
            status = "excellent"  # <5% error
        elif max_error < 10.0:
            status = "good"  # 5-10% error
        elif max_error < 20.0:
            status = "fair"  # 10-20% error
        else:
            status = "poor"  # >20% error

        return {
            "predicted_leds": predicted_leds,
            "measured_leds": measured_leds,
            "deviations": deviations,
            "percent_errors": percent_errors,
            "average_error_percent": avg_error,
            "max_error_percent": max_error,
            "validation_status": status,
        }

    def predict_p_pol_from_s_pol(
        self,
        s_pol_time_ms: float,
        s_pol_leds: dict[str, int],
        target_counts: float,
    ) -> dict[str, int]:
        """Predict P-pol LED values based on actual S-pol convergence results.

        Uses S-pol performance to adjust P-pol predictions, accounting for
        systematic hardware deviations from the model.

        Strategy:
        1. Calculate what S-pol LEDs the model predicted
        2. Calculate deviation factors (measured / predicted)
        3. Apply same deviation factors to P-pol predictions

        This improves P-pol convergence speed by starting closer to target.

        Args:
            s_pol_time_ms: Integration time from S-pol convergence
            s_pol_leds: Actual LED values from S-pol convergence
            target_counts: Target detector counts

        Returns:
            Dictionary of predicted P-pol LED intensities {channel: intensity}

        """
        if not self.model_data:
            msg = "No model loaded"
            raise ModelValidationError(msg)

        p_pol_predictions = {}

        for channel, s_measured_led in s_pol_leds.items():
            # Get what model predicted for S-pol
            s_predicted_led = self.calculate_led_intensity(
                channel,
                "S",
                s_pol_time_ms,
                target_counts,
                safety_margin=1.0,
            )

            # Calculate deviation factor (how much hardware differs from model)
            if s_predicted_led > 0:
                deviation_factor = s_measured_led / s_predicted_led
            else:
                deviation_factor = 1.0

            # Get raw P-pol prediction from model
            p_predicted_led = self.calculate_led_intensity(
                channel,
                "P",
                s_pol_time_ms,
                target_counts,
                safety_margin=1.0,
            )

            # Apply S-pol deviation factor to P-pol prediction
            p_adjusted_led = int(np.clip(p_predicted_led * deviation_factor, 0, 255))

            p_pol_predictions[channel] = p_adjusted_led

        return p_pol_predictions

    def calculate_dark_signal(
        self,
        channel: str,
        time_ms: float,
        polarization: str = "S",
    ) -> float:
        """Calculate expected dark signal (LEDs OFF) for given integration time.

        In 3-stage model, dark counts are stored per time in dark_counts_per_time.
        Uses linear interpolation between calibrated time points.

        Args:
            channel: Channel letter ('A', 'B', 'C', 'D') [not used - dark is same for all channels]
            time_ms: Integration time in milliseconds
            polarization: 'S' or 'P' [not used - dark is same for both]

        Returns:
            Expected dark signal in counts

        """
        if not self.model_data:
            msg = "No model loaded"
            raise ModelValidationError(msg)

        # Get dark counts from model (same for all channels in 3-stage)
        dark_counts_per_time = self.model_data.get("dark_counts_per_time", {})

        # Check if dark data is available
        if not dark_counts_per_time:
            msg = "Model does not contain dark spectrum data (dark_counts_per_time is empty)"
            raise ModelValidationError(msg)

        # If exact time match, return it
        if str(int(time_ms)) in dark_counts_per_time:
            return dark_counts_per_time[str(int(time_ms))]

        # Otherwise interpolate (simple linear assumption)
        # Typically we have 10, 20, 30ms points
        times = sorted([float(t) for t in dark_counts_per_time])
        counts = [dark_counts_per_time[str(int(t))] for t in times]

        # Linear interpolation
        dark_signal = np.interp(time_ms, times, counts)
        return float(dark_signal)

    def validate_dark_spectrum(
        self,
        time_ms: float,
        measured_dark_roi: dict[str, np.ndarray],
        polarization: str = "S",
    ) -> dict:
        """Validate measured dark spectrum against model predictions.

        Dark spectrum should match model's dark signal prediction (c·t + d).
        This validates detector noise characteristics.

        Args:
            time_ms: Integration time used for dark measurement
            measured_dark_roi: Measured dark ROI per channel {channel: array}
            polarization: 'S' or 'P' (use same pol as calibration)

        Returns:
            Dictionary with:
                - predicted_dark: Model predictions per channel
                - measured_dark: Mean measured values per channel
                - deviations: Difference (measured - predicted)
                - percent_errors: Percentage errors
                - average_error_percent: Mean absolute error
                - max_error_percent: Maximum absolute error
                - validation_status: 'excellent', 'good', 'fair', or 'poor'

        """
        if not self.model_data:
            msg = "No model loaded"
            raise ModelValidationError(msg)

        predicted_dark = {}
        measured_dark = {}
        deviations = {}
        percent_errors = {}

        for channel, dark_array in measured_dark_roi.items():
            # Calculate model prediction
            predicted = self.calculate_dark_signal(channel, time_ms, polarization)
            predicted_dark[channel] = predicted

            # Calculate mean of measured dark spectrum
            measured = float(np.mean(dark_array))
            measured_dark[channel] = measured

            # Calculate deviation
            deviation = measured - predicted
            deviations[channel] = deviation

            # Calculate percent error
            if predicted > 0:
                percent_errors[channel] = (deviation / predicted) * 100.0
            else:
                percent_errors[channel] = 0.0

        # Calculate summary statistics
        abs_errors = [abs(pct) for pct in percent_errors.values()]
        avg_error = np.mean(abs_errors) if abs_errors else 0.0
        max_error = np.max(abs_errors) if abs_errors else 0.0

        # Classify validation quality (dark should be very accurate)
        if max_error < 10.0:
            status = "excellent"  # <10% error
        elif max_error < 20.0:
            status = "good"  # 10-20% error
        elif max_error < 50.0:
            status = "fair"  # 20-50% error
        else:
            status = "poor"  # >50% error (detector issue)

        return {
            "predicted_dark": predicted_dark,
            "measured_dark": measured_dark,
            "deviations": deviations,
            "percent_errors": percent_errors,
            "average_error_percent": avg_error,
            "max_error_percent": max_error,
            "validation_status": status,
        }

    def get_model_info(self) -> dict:
        """Get model metadata and validation statistics."""
        if not self.model_data:
            return {}

        info = {
            "detector_serial": self.model_data.get("detector_serial"),
            "timestamp": self.model_data.get("timestamp"),
            "channels": list(self.model_data["bilinear_models"].keys()),
            "polarizations": ["S", "P"],
            "r2_scores": {},
        }

        # Collect R² scores
        for channel in info["channels"]:
            ch_model = self.model_data["bilinear_models"][channel]

            # S-mode always has r2
            s_r2 = ch_model["S"].get("r2", ch_model["S"].get("r_squared", 0))

            # P-mode might use scaled S-mode (no separate r2)
            p_model = ch_model["P"]
            if p_model.get("p_from_s"):
                # P-mode scales S-mode, so use S-mode R² for P as well
                p_r2 = s_r2
            else:
                # P-mode has separate model
                p_r2 = p_model.get("r2", p_model.get("r_squared", 0))

            info["r2_scores"][channel] = {
                "S": s_r2,
                "P": p_r2,
            }

        return info

    def predict_counts(
        self,
        led: str,
        polarization: str,
        time_ms: float,
        intensity: int,
    ) -> float:
        """Predict detector counts for given parameters.

        Uses 3-stage linear model: counts = slope_10ms × intensity × (time_ms / 10)

        Args:
            led: LED channel ('A', 'B', 'C', 'D')
            polarization: 'S' or 'P' (not used - same model for both)
            time_ms: Integration time in milliseconds
            intensity: LED intensity (0-255)

        Returns:
            Predicted detector counts

        """
        if not self.model_data:
            msg = "No model loaded"
            raise ModelValidationError(msg)

        params = self.model_data["bilinear_models"][led][
            "S"
        ]  # S and P are same in 3-stage
        slope_10ms = params["slope_10ms"]

        # 3-stage linear formula
        return slope_10ms * intensity * (time_ms / 10.0)

    def generate_qc_report(self) -> dict:
        """Generate comprehensive QC report for model validation.

        Returns detailed analysis of:
        - Model completeness (all channels/polarizations present)
        - Parameter validity (physical constraints, R² scores)
        - Coefficient ranges and sanity checks
        - Calibration metadata (date, detector serial)

        Returns:
            Dictionary with QC status, warnings, and detailed metrics

        """
        if not self.model_data:
            return {
                "status": "FAIL",
                "error": "No model loaded",
                "passed": False,
            }

        report = {
            "detector_serial": self.model_data.get("detector_serial", "UNKNOWN"),
            "timestamp": self.model_data.get("timestamp", "UNKNOWN"),
            "model_equation": self.model_data.get("model_equation", "NOT DOCUMENTED"),
            "calibration_type": self.model_data.get("calibration_type", "UNKNOWN"),
            "checks": [],
            "warnings": [],
            "errors": [],
            "channel_details": {},
            "passed": True,
        }

        # CHECK 1: Metadata completeness
        if self.model_data.get("detector_serial"):
            report["checks"].append("✓ Detector serial present")
        else:
            report["errors"].append("✗ Missing detector serial")
            report["passed"] = False

        if self.model_data.get("timestamp"):
            report["checks"].append("✓ Calibration timestamp present")
        else:
            report["warnings"].append("⚠ Missing calibration timestamp")

        if self.model_data.get("model_equation"):
            report["checks"].append("✓ Model equation documented")
        else:
            report["warnings"].append("⚠ Model equation not documented")

        # CHECK 2: Channel completeness
        models = self.model_data.get("bilinear_models", {})
        required_channels = ["A", "B", "C", "D"]
        missing_channels = [ch for ch in required_channels if ch not in models]

        if missing_channels:
            report["errors"].append(f"✗ Missing channels: {missing_channels}")
            report["passed"] = False
        else:
            report["checks"].append("✓ All 4 channels present (A, B, C, D)")

        # CHECK 3: Validate each channel
        for channel in required_channels:
            if channel not in models:
                continue

            ch_report = {
                "S": {"status": "unknown", "details": {}},
                "P": {"status": "unknown", "details": {}},
            }

            for pol in ["S", "P"]:
                if pol not in models[channel]:
                    report["errors"].append(f"✗ {channel}-{pol}: Missing polarization")
                    report["passed"] = False
                    ch_report[pol]["status"] = "missing"
                    continue

                params = models[channel][pol]
                prefix = f"{channel}-{pol}"

                # 3-stage linear model validation
                # S and P have same parameters in 3-stage model
                required_params = ["slope_10ms", "r2", "linearity"]
                missing_params = [p for p in required_params if p not in params]

                if missing_params:
                    report["errors"].append(
                        f"✗ {prefix}: Missing parameters {missing_params}",
                    )
                    report["passed"] = False
                    ch_report[pol]["status"] = "incomplete"
                else:
                    slope_10ms = params["slope_10ms"]
                    r2 = params["r2"]
                    linearity = params.get("linearity", [])

                    ch_report[pol]["status"] = "complete"
                    ch_report[pol]["details"] = {
                        "slope_10ms": slope_10ms,
                        "r2": r2,
                        "linearity": linearity,
                        "method": "3-stage linear",
                    }

                    # QC: Linearity score (pseudo-R² from stage ratios)
                    if r2 >= 0.99:
                        report["checks"].append(
                            f"✓ {prefix}: Excellent linearity (R²={r2:.6f})",
                        )
                    elif r2 >= 0.95:
                        report["checks"].append(
                            f"✓ {prefix}: Good linearity (R²={r2:.6f})",
                        )
                    elif r2 >= 0.90:
                        report["warnings"].append(
                            f"⚠ {prefix}: Acceptable linearity (R²={r2:.6f}), but below ideal",
                        )
                    else:
                        report["errors"].append(
                            f"✗ {prefix}: Poor linearity (R²={r2:.6f}), recalibration recommended",
                        )
                        report["passed"] = False

                    # QC: Slope must be positive
                    if slope_10ms <= 0:
                        report["errors"].append(
                            f"✗ {prefix}: Invalid slope_10ms={slope_10ms:.2f} (must be > 0)",
                        )
                        report["passed"] = False
                    else:
                        report["checks"].append(
                            f"✓ {prefix}: Valid slope_10ms={slope_10ms:.2f}",
                        )

                    # QC: Slope magnitude sanity (typical range: 20-300 counts/(intensity*(10ms)))
                    if slope_10ms < 10:
                        report["warnings"].append(
                            f"⚠ {prefix}: Unusually low slope_10ms={slope_10ms:.2f}",
                        )
                    elif slope_10ms > 500:
                        report["warnings"].append(
                            f"⚠ {prefix}: Unusually high slope_10ms={slope_10ms:.2f}",
                        )

            report["channel_details"][channel] = ch_report

        # Summary
        report["status"] = "PASS" if report["passed"] else "FAIL"
        report["total_checks"] = len(report["checks"])
        report["total_warnings"] = len(report["warnings"])
        report["total_errors"] = len(report["errors"])

        # Add model validation section if available (populated during calibration)
        report["model_validation"] = {
            "s_pol": None,
            "p_pol": None,
            "notes": "Model validation vs convergence results populated during calibration",
        }

        return report

    def print_qc_report(self) -> None:
        """Print human-readable QC report to console."""
        report = self.generate_qc_report()

        if report["checks"]:
            for _check in report["checks"]:
                pass

        if report["warnings"]:
            for _warning in report["warnings"]:
                pass

        if report["errors"]:
            for _error in report["errors"]:
                pass


def quick_test() -> None:
    """Quick test of model loader functionality."""
    import sys

    if len(sys.argv) < 2:
        return

    detector_serial = sys.argv[1]

    # Load model
    loader = LEDCalibrationModelLoader()
    try:
        loader.load_model(detector_serial)
    except ModelNotFoundError:
        return

    # Show model info
    info = loader.get_model_info()
    for channel in info["channels"]:
        info["r2_scores"][channel]["S"]
        info["r2_scores"][channel]["P"]

    # Test calculation

    time_ms = 30.0
    target_counts = 50000

    intensities = loader.calculate_all_led_intensities("S", time_ms, target_counts)
    for channel, intensity in intensities.items():
        loader.predict_counts(channel, "S", time_ms, intensity)

    # Validate range
    for channel, intensity in intensities.items():
        _valid, _msg = loader.validate_model_range(time_ms, intensity)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    quick_test()
