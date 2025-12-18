from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .interfaces import Spectrometer, LEDActuator, ROIExtractor, Logger
from affilabs.hardware.device_interface import ISpectrometer
from affilabs.utils.hal.controller_hal import ControllerHAL


class RealSpectrometerAdapter(Spectrometer):
    """Adapter that ties together the USB4000 spectrometer and Pico LED controller.

    Notes:
    - This adapter assumes exclusive hardware access. Do not use with parallel_workers > 1.
    - LED control is performed per-acquisition using the Pico batch command for reliability.
    """

    def __init__(self, *, spectrometer: ISpectrometer, controller: ControllerHAL, logger: Optional[Logger] = None) -> None:
        self.spec_hal = spectrometer
        self.ctrl_hal = controller
        self.log = logger

    def _log(self, level: str, msg: str) -> None:
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
        # Set LEDs: turn only the requested channel on at requested intensity.
        a = b = c = d = 0
        ch = (channel or "").lower()
        if ch == "a":
            a = int(max(0, min(255, led_intensity)))
        elif ch == "b":
            b = int(max(0, min(255, led_intensity)))
        elif ch == "c":
            c = int(max(0, min(255, led_intensity)))
        elif ch == "d":
            d = int(max(0, min(255, led_intensity)))
        else:
            self._log("error", f"Unknown channel '{channel}' in acquire()")
            return None

        # Prefer batch command via HAL for reliability and speed
        try:
            ok = self.ctrl_hal.set_batch_intensities(a=a, b=b, c=c, d=d)
            if not ok:
                self._log("warning", "Batch LED command failed; attempting single-channel fallback")
                # Fallback to single channel if available
                self.ctrl_hal.turn_on_channel(ch=ch)
                self.ctrl_hal.set_intensity(ch=ch, raw_val=int(max(0, min(255, led_intensity))))
        except Exception as e:
            self._log("error", f"LED control error: {e}")
            return None

        # Set integration time
        try:
            self.spec_hal.set_integration_time(float(integration_time_ms))
        except Exception as e:
            self._log("error", f"Error setting integration: {e}")
            return None

        # Acquire spectrum (averaging if num_scans > 1)
        try:
            arr = self.spec_hal.read_spectrum(num_scans=num_scans)
            # The engine expects a Sequence[float]
            if arr is None:
                return None
            return arr.tolist()
        except Exception as e:
            self._log("error", f"Spectrometer read error: {e}")
            return None


class LEDBatchActuator(LEDActuator):
    """LED actuator using Pico batch intensity command.

    Accepts a mapping of channel -> intensity for keys in {"a","b","c","d"}.
    Missing keys default to 0 (off).
    """

    def __init__(self, *, pico_ctrl, logger: Optional[Logger] = None) -> None:
        self.ctrl = pico_ctrl
        self.log = logger

    def set_many(self, mapping: Mapping[str, int]) -> bool:
        def _v(key: str) -> int:
            return int(max(0, min(255, mapping.get(key, 0))))

        try:
            return bool(self.ctrl.set_batch_intensities(a=_v("a"), b=_v("b"), c=_v("c"), d=_v("d")))
        except Exception:
            return False


class ROIFromStartup(ROIExtractor):
    """ROI extractor bridging to utils.startup_calibration.roi_signal.

    Parameters affect robustness of the signal within the ROI.
    """

    def __init__(
        self,
        *,
        method: str = "median",
        trim_fraction: float = 0.1,
        top_n: Optional[int] = None,
    ) -> None:
        self.method = method
        self.trim_fraction = float(trim_fraction)
        self.top_n = top_n

    def __call__(self, spectrum: Sequence[float], i_min: int, i_max: int) -> float:
        # Lazy import to avoid heavy dependencies unless used
        from affilabs.utils.startup_calibration import roi_signal
        try:
            return float(
                roi_signal(
                    spectrum,  # type: ignore[arg-type]
                    i_min,
                    i_max,
                    method=self.method,
                    trim_fraction=self.trim_fraction,
                    top_n=self.top_n,
                ),
            )
        except Exception:
            # Fallback to simple sum if robust method fails
            try:
                return float(sum(spectrum[i_min:i_max]))
            except Exception:
                return 0.0
