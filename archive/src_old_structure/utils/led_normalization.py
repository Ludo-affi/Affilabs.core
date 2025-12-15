"""LED Normalization Framework

Detector-agnostic LED intensity normalization using existing HAL interfaces.
Works with IController and ISpectrometer from src.hardware without additional adapters.

Supports two normalization modes:
1. INTENSITY mode: Adjust LED intensity at fixed integration time
2. TIME mode: Adjust integration time at fixed LED intensity
"""

import json
import logging
import time
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# INTENSITY CALCULATION STRATEGIES
# ============================================================================


class IntensityCalculator(ABC):
    """Abstract base class for intensity calculation methods."""

    @abstractmethod
    def calculate(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> float:
        """Calculate intensity metric from spectrum."""


class PeakIntensityCalculator(IntensityCalculator):
    """Calculate peak intensity (maximum value in spectrum)."""

    def calculate(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> float:
        return float(np.max(spectrum))


class MeanIntensityCalculator(IntensityCalculator):
    """Calculate mean intensity over specified wavelength range."""

    def __init__(self, wavelength_min: float = 400, wavelength_max: float = 700):
        self.wavelength_min = wavelength_min
        self.wavelength_max = wavelength_max

    def calculate(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> float:
        if wavelengths is None:
            return float(np.mean(spectrum))

        mask = (wavelengths >= self.wavelength_min) & (
            wavelengths <= self.wavelength_max
        )
        return float(np.mean(spectrum[mask])) if np.any(mask) else 0.0


class IntegratedIntensityCalculator(IntensityCalculator):
    """Calculate integrated intensity (area under curve)."""

    def __init__(self, wavelength_min: float = 400, wavelength_max: float = 700):
        self.wavelength_min = wavelength_min
        self.wavelength_max = wavelength_max

    def calculate(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> float:
        if wavelengths is None:
            return float(np.trapz(spectrum))

        mask = (wavelengths >= self.wavelength_min) & (
            wavelengths <= self.wavelength_max
        )
        return (
            float(np.trapz(spectrum[mask], wavelengths[mask])) if np.any(mask) else 0.0
        )


# ============================================================================
# LED NORMALIZER (HAL-BASED)
# ============================================================================


class LEDNormalizer:
    """LED normalization using existing HAL interfaces (IController + ISpectrometer).

    No additional adapters needed - works directly with:
    - src.hardware.IController
    - src.hardware.ISpectrometer
    """

    def __init__(
        self,
        controller,  # IController from src.hardware
        spectrometer,  # ISpectrometer from src.hardware
        intensity_calculator: IntensityCalculator | None = None,
    ):
        """Initialize LED normalizer with HAL interfaces.

        Args:
            controller: Controller implementing IController interface
            spectrometer: Spectrometer implementing ISpectrometer interface
            intensity_calculator: Method to calculate intensity from spectrum

        """
        self.controller = controller
        self.spectrometer = spectrometer
        self.intensity_calculator = intensity_calculator or PeakIntensityCalculator()

        # Get available LED channels from controller
        self.led_channels = self._get_led_channels()

        logger.info(
            f"LED Normalizer initialized with {len(self.led_channels)} channels",
        )

    def _get_led_channels(self) -> list[str]:
        """Get available LED channels from controller capabilities."""
        try:
            caps = self.controller.get_capabilities()
            max_channels = caps.max_channels

            # Assume channels are a, b, c, d up to max_channels (lowercase for HAL)
            channel_names = ["a", "b", "c", "d"]
            return channel_names[:max_channels]
        except:
            # Fallback: assume 4 channels
            return ["a", "b", "c", "d"]

    def rank_leds(
        self,
        test_intensity: int = 255,
        integration_time: int = 10,
        settling_time: float = 0.2,
    ) -> tuple[dict[str, float], float]:
        """Rank LEDs from brightest to dimmest.

        Args:
            test_intensity: Intensity to test all LEDs at (0-255)
            integration_time: Integration time in ms
            settling_time: Time to wait after LED turn-on (seconds)

        Returns:
            (ranked_dict, recommended_target):
                - ranked_dict: {led: intensity_value} sorted brightest to dimmest
                - recommended_target: 90% of weakest LED

        """
        logger.info(
            f"Ranking LEDs at intensity {test_intensity}, integration {integration_time}ms...",
        )

        # Set integration time
        self.spectrometer.set_integration_time(integration_time)
        measurements = {}

        for led in self.led_channels:
            # Set intensity and turn on
            self.controller.set_intensity(led, test_intensity)
            self.controller.turn_on_channel(led)
            time.sleep(settling_time)

            # Measure
            spectrum = self.spectrometer.read_spectrum()
            if spectrum is None:
                logger.error(f"  LED {led}: Failed to read spectrum (returned None)")
                continue

            wavelengths = (
                self.spectrometer.get_wavelengths()
                if hasattr(self.spectrometer, "get_wavelengths")
                else None
            )
            intensity = self.intensity_calculator.calculate(spectrum, wavelengths)

            measurements[led] = intensity
            logger.info(f"  LED {led}: {intensity:.1f} counts")

            # Turn off
            self.controller.turn_off_channels()
            time.sleep(0.1)

        # Sort brightest to dimmest
        ranked = dict(sorted(measurements.items(), key=lambda x: x[1], reverse=True))

        weakest_count = min(measurements.values())
        recommended_target = weakest_count * 0.9

        logger.info(f"\nRanking (brightest to dimmest): {list(ranked.keys())}")
        logger.info(f"Recommended target: {recommended_target:.0f} counts")

        return ranked, recommended_target

    def normalize(
        self,
        mode: str = "intensity",
        target_value: float = 30000,
        tolerance: float = 500,
        max_iterations: int = 10,
        settling_time: float = 0.2,
    ) -> dict[str, dict]:
        """Normalize LEDs using intensity or time adjustment.

        Args:
            mode: 'intensity' or 'time'
            target_value: Target intensity count
            tolerance: Acceptable error (counts)
            max_iterations: Max binary search iterations
            settling_time: LED settling time (seconds)

        Returns:
            dict: Normalized parameters for each LED

        """
        if mode == "intensity":
            return self._normalize_by_intensity(
                target_value,
                tolerance,
                max_iterations,
                settling_time,
            )
        if mode == "time":
            return self._normalize_by_time(
                target_value,
                tolerance,
                max_iterations,
                settling_time,
            )
        raise ValueError(f"Invalid mode: {mode}. Use 'intensity' or 'time'")

    def _normalize_by_intensity(
        self,
        target_count: float,
        tolerance: float,
        max_iterations: int,
        settling_time: float,
    ) -> dict[str, dict]:
        """Normalize by adjusting LED intensity at fixed integration time."""
        # Rank first to get recommended target
        ranked, recommended_target = self.rank_leds()

        if target_count > recommended_target:
            logger.warning(
                f"Target {target_count:.0f} exceeds recommended "
                f"{recommended_target:.0f}. May cause saturation!",
            )

        # Fix integration time (use 10ms default for intensity normalization)
        current_integration_time = self.spectrometer.get_integration_time()
        fixed_integration_time = (
            max(current_integration_time, 10.0)
            if current_integration_time > 1.0
            else 10.0
        )
        self.spectrometer.set_integration_time(fixed_integration_time)
        logger.info(
            f"Normalizing by intensity (fixed time: {fixed_integration_time}ms)...",
        )

        results = {}

        for led in self.led_channels:
            logger.info(f"  Normalizing LED {led}...")

            best_intensity, best_count, best_error = self._binary_search(
                led=led,
                parameter="intensity",
                low=1,
                high=255,
                target_count=target_count,
                tolerance=tolerance,
                max_iterations=max_iterations,
                settling_time=settling_time,
            )

            results[led] = {
                "mode": "intensity",
                "parameter": "intensity",
                "value": best_intensity,
                "integration_time": fixed_integration_time,
                "achieved_count": best_count,
                "target_count": target_count,
                "error": best_error,
                "error_percent": (best_error / target_count) * 100,
            }

            logger.info(
                f"    Result: intensity={best_intensity}, "
                f"count={best_count:.0f}, error={best_error:.0f}",
            )

        return results

    def _normalize_by_time(
        self,
        target_count: float,
        tolerance: float,
        max_iterations: int,
        settling_time: float,
    ) -> dict[str, dict]:
        """Normalize by adjusting integration time at fixed LED intensity."""
        # Use max intensity for best SNR
        fixed_intensity = 255
        logger.info(f"Normalizing by time (fixed intensity: {fixed_intensity})...")

        results = {}

        for led in self.led_channels:
            logger.info(f"  Normalizing LED {led}...")

            # Set fixed intensity
            self.controller.set_intensity(led, fixed_intensity)

            best_time, best_count, best_error = self._binary_search(
                led=led,
                parameter="time",
                low=1,
                high=200,
                target_count=target_count,
                tolerance=tolerance,
                max_iterations=max_iterations,
                settling_time=settling_time,
            )

            results[led] = {
                "mode": "time",
                "parameter": "integration_time",
                "value": best_time,
                "intensity": fixed_intensity,
                "achieved_count": best_count,
                "target_count": target_count,
                "error": best_error,
                "error_percent": (best_error / target_count) * 100,
            }

            logger.info(
                f"    Result: time={best_time}ms, "
                f"count={best_count:.0f}, error={best_error:.0f}",
            )

        return results

    def _binary_search(
        self,
        led: str,
        parameter: str,
        low: int,
        high: int,
        target_count: float,
        tolerance: float,
        max_iterations: int,
        settling_time: float,
    ) -> tuple[int, float, float]:
        """Binary search to find optimal parameter value.

        Returns:
            (best_value, best_count, best_error)

        """
        best_value = None
        best_count = None
        best_error = float("inf")

        for iteration in range(max_iterations):
            mid = (low + high) // 2

            # Set parameter
            if parameter == "intensity":
                self.controller.set_intensity(led, mid)
            elif parameter == "time":
                self.spectrometer.set_integration_time(mid)

            # Measure
            self.controller.turn_on_channel(led)
            time.sleep(settling_time)

            spectrum = self.spectrometer.read_spectrum()
            wavelengths = (
                self.spectrometer.get_wavelengths()
                if hasattr(self.spectrometer, "get_wavelengths")
                else None
            )
            count = self.intensity_calculator.calculate(spectrum, wavelengths)

            self.controller.turn_off_channels()

            error = abs(count - target_count)

            if error < best_error:
                best_value = mid
                best_count = count
                best_error = error

            # Binary search logic
            if error < tolerance:
                break
            if count < target_count:
                low = mid + 1
            else:
                high = mid - 1

            if high <= low:
                break

        return best_value, best_count, best_error

    def save_results(self, results: dict[str, dict], filename: str):
        """Save normalization results to JSON file."""
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {filename}")

    def load_results(self, filename: str) -> dict[str, dict]:
        """Load normalization results from JSON file."""
        with open(filename) as f:
            results = json.load(f)
        logger.info(f"Results loaded from {filename}")
        return results

    def apply_normalization(self, results: dict[str, dict], led: str):
        """Apply saved normalization parameters for a specific LED.

        Args:
            results: Normalization results dict
            led: LED channel to configure

        """
        if led not in results:
            raise ValueError(f"LED {led} not found in normalization results")

        params = results[led]
        mode = params["mode"]

        if mode == "intensity":
            # Ensure integration time is at least 1ms for hardware compatibility
            integration_time = max(params["integration_time"], 1.0)
            self.spectrometer.set_integration_time(integration_time)
            self.controller.set_intensity(led, params["value"])
        elif mode == "time":
            self.controller.set_intensity(led, params["intensity"])
            self.spectrometer.set_integration_time(params["value"])

        logger.debug(
            f"Applied normalization for LED {led}: "
            f"{params['parameter']}={params['value']}",
        )
