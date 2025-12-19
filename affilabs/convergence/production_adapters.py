"""Production adapters for convergence engine.

This module provides adapters that bridge the convergence engine with the
existing production calibration orchestrator and hardware stack.

The goal is to allow incremental migration: use the engine's clean architecture
while maintaining compatibility with the battle-tested calibration workflow.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence, Dict
import numpy as np

from .interfaces import Spectrometer, LEDActuator, ROIExtractor, Logger


class CalibrationSpectrometerAdapter(Spectrometer):
    """Adapter for calibration orchestrator's spectrometer interface.

    This adapter works with:
    - OceanSpectrometerAdapter (usb device)
    - ControllerHAL (ctrl device)
    - acquire_spectrum_fn and roi_signal_fn from orchestrator

    It maintains compatibility with the existing calibration workflow
    while conforming to the convergence engine's Spectrometer protocol.
    """

    def __init__(
        self,
        *,
        usb: object,  # OceanSpectrometerAdapter
        ctrl: object,  # ControllerHAL
        acquire_spectrum_fn,  # Function to acquire raw spectrum
        use_batch_command: bool = True,
        logger: Optional[Logger] = None,
    ) -> None:
        """Initialize adapter.

        Args:
            usb: Spectrometer device (OceanSpectrometerAdapter)
            ctrl: Controller device (ControllerHAL)
            acquire_spectrum_fn: Function(usb, ctrl, channel, led, integration_ms, use_batch, num_scans)
            use_batch_command: Use batch LED command (default True)
            logger: Optional logger instance
        """
        self.usb = usb
        self.ctrl = ctrl
        self.acquire_fn = acquire_spectrum_fn
        self.use_batch = use_batch_command
        self.log = logger

    def _log(self, level: str, msg: str) -> None:
        """Log message if logger is available."""
        if self.log:
            fn = getattr(self.log, level, None)
            if callable(fn):
                try:
                    fn(msg)
                except Exception:
                    pass

    def acquire(
        self,
        *,
        integration_time_ms: float,
        num_scans: int,
        channel: str,
        led_intensity: int,
        use_batch_command: bool,
    ) -> Optional[Sequence[float]]:
        """Acquire spectrum for a single channel.

        This calls the existing acquire_spectrum_fn used by LEDconverge,
        maintaining full compatibility with the production stack.

        Args:
            integration_time_ms: Integration time in milliseconds
            num_scans: Number of scans to average (typically 1)
            channel: Channel name ('a', 'b', 'c', 'd')
            led_intensity: LED intensity (0-255)
            use_batch_command: Use batch LED command

        Returns:
            Spectrum as sequence of floats, or None on failure
        """
        try:
            # Call existing acquire function with production-tested logic
            spectrum = self.acquire_fn(
                usb=self.usb,
                ctrl=self.ctrl,
                channel=channel,
                led_intensity=led_intensity,
                integration_time_ms=integration_time_ms,
                use_batch_command=use_batch_command,
                num_scans=num_scans,
            )

            if spectrum is None:
                self._log("error", f"Spectrum acquisition failed for channel {channel}")
                return None

            # Ensure it's a sequence (list or numpy array)
            if isinstance(spectrum, np.ndarray):
                return spectrum.tolist()
            return spectrum

        except Exception as e:
            self._log("error", f"Error acquiring spectrum for channel {channel}: {e}")
            return None


class ProductionROIExtractor(ROIExtractor):
    """ROI extractor that matches production calibration logic.

    This uses the same ROI extraction method as the existing
    led_convergence_algorithm, ensuring identical behavior.
    """

    def __call__(
        self,
        spectrum: Sequence[float],
        i_min: int,
        i_max: int,
    ) -> float:
        """Extract ROI signal from spectrum.

        Args:
            spectrum: Full spectrum (list or array)
            i_min: ROI start index (inclusive)
            i_max: ROI end index (exclusive)

        Returns:
            Mean signal in ROI window
        """
        try:
            # Convert to numpy array if needed
            if isinstance(spectrum, (list, tuple)):
                arr = np.array(spectrum, dtype=np.float64)
            else:
                arr = spectrum

            # Extract ROI window
            roi = arr[i_min:i_max]

            # Use TOP 50 pixels for signal (more robust to noise/baseline)
            # Sort descending and take mean of brightest pixels
            if len(roi) > 50:
                top_pixels = np.partition(roi, -50)[-50:]  # Fast selection of top 50
                return float(np.mean(top_pixels))
            else:
                # If ROI < 50 pixels, use all
                return float(np.mean(roi))

        except Exception:
            return 0.0


class ProductionLogger(Logger):
    """Logger adapter for Python logging module.

    This wraps a standard Python logger to match the engine's
    Logger protocol.
    """

    def __init__(self, logger):
        """Initialize with a Python logger instance."""
        self.logger = logger

    def info(self, msg: str) -> None:
        """Log info message."""
        if self.logger:
            self.logger.info(msg)

    def warning(self, msg: str) -> None:
        """Log warning message."""
        if self.logger:
            self.logger.warning(msg)

    def error(self, msg: str) -> None:
        """Log error message."""
        if self.logger:
            self.logger.error(msg)


class ProductionLEDActuator(LEDActuator):
    """LED actuator using production controller HAL.

    This adapter allows the convergence engine to control LEDs
    through the existing ControllerHAL interface.
    """

    def __init__(self, *, ctrl, logger: Optional[Logger] = None) -> None:
        """Initialize actuator.

        Args:
            ctrl: Controller HAL instance (ControllerHAL)
            logger: Optional logger instance
        """
        self.ctrl = ctrl
        self.log = logger

    def _log(self, level: str, msg: str) -> None:
        """Log message if logger is available."""
        if self.log:
            fn = getattr(self.log, level, None)
            if callable(fn):
                try:
                    fn(msg)
                except Exception:
                    pass

    def set_many(self, mapping: Mapping[str, int]) -> bool:
        """Set LED intensities for multiple channels.

        Args:
            mapping: Dict mapping channel names to LED intensities (0-255)
            Keys should be in {'a', 'b', 'c', 'd'}

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract intensities, defaulting to 0 for missing channels
            a = int(max(0, min(255, mapping.get('a', 0))))
            b = int(max(0, min(255, mapping.get('b', 0))))
            c = int(max(0, min(255, mapping.get('c', 0))))
            d = int(max(0, min(255, mapping.get('d', 0))))

            # Use batch command (production-tested)
            success = self.ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)

            if not success:
                self._log("warning", f"Batch LED command failed: a={a}, b={b}, c={c}, d={d}")
                return False

            return True

        except Exception as e:
            self._log("error", f"Error setting LED intensities: {e}")
            return False


def create_production_adapters(
    usb,
    ctrl,
    acquire_spectrum_fn,
    logger=None,
    use_batch_command: bool = True,
) -> Dict[str, object]:
    """Factory function to create all production adapters.

    This is a convenience function for the calibration orchestrator
    to create all necessary adapters in one call.

    Args:
        usb: Spectrometer device (OceanSpectrometerAdapter)
        ctrl: Controller HAL instance
        acquire_spectrum_fn: Spectrum acquisition function
        logger: Optional Python logger instance
        use_batch_command: Use batch LED command (default True)

    Returns:
        Dict with keys: 'spectrometer', 'roi_extractor', 'led_actuator', 'logger'
    """
    # Wrap logger if provided
    engine_logger = ProductionLogger(logger) if logger else None

    return {
        'spectrometer': CalibrationSpectrometerAdapter(
            usb=usb,
            ctrl=ctrl,
            acquire_spectrum_fn=acquire_spectrum_fn,
            use_batch_command=use_batch_command,
            logger=engine_logger,
        ),
        'roi_extractor': ProductionROIExtractor(),
        'led_actuator': ProductionLEDActuator(ctrl=ctrl, logger=engine_logger),
        'logger': engine_logger,
    }
