"""Spectrum acquisition helper for live data collection using Spectrometer HAL."""

from __future__ import annotations

from typing import Optional

import numpy as np
from utils.logger import logger
from utils.hal.interfaces import Spectrometer


class SpectrumAcquisition:
    """Handles spectrum acquisition with averaging via Spectrometer HAL."""

    def __init__(self, spectrometer: Spectrometer):
        self.spec = spectrometer

    def acquire_averaged_spectrum(
        self,
        wave_min_index: int,
        wave_max_index: int,
        num_scans: int = 1,
    ) -> Optional[np.ndarray]:
        try:
            return self.spec.read_roi(wave_min_index, wave_max_index, num_scans)
        except Exception as e:
            logger.error(f"Error acquiring spectrum: {e}")
            return None
