from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from .interfaces import Spectrometer, ROIExtractor


@dataclass
class LinearSpectrometerSim(Spectrometer):
    base_per_led: Mapping[str, float]
    noise_sigma: float
    params_max_counts: float
    saturation_threshold: float

    def acquire(
        self,
        *,
        integration_time_ms: float,
        num_scans: int,
        channel: str,
        led_intensity: int,
        use_batch_command: bool,
    ) -> Optional[Sequence[float]]:
        slope = self.base_per_led.get(channel, 500.0) * (integration_time_ms / 10.0)
        signal = slope * max(0, led_intensity)
        # Simulate saturation clipping
        clipped = min(signal, self.params_max_counts)
        # Create a simple flat spectrum with the signal packed in ROI region size 100
        length = 2048
        spec = [0.0] * length
        # Place the counts in indices 400..499
        per_pixel = clipped / 100.0
        for i in range(400, 500):
            val = per_pixel + random.gauss(0.0, self.noise_sigma)
            if val < 0:
                val = 0.0
            spec[i] = val
        return spec


class SimpleROISum(ROIExtractor):
    def __call__(self, spectrum: Sequence[float], i_min: int, i_max: int) -> float:
        return float(sum(spectrum[i_min:i_max]))
