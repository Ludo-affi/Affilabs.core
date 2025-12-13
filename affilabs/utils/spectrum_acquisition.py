"""Spectrum acquisition helper for live data collection using Spectrometer HAL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    import numpy as np

    from affilabs.utils.hal.interfaces import Spectrometer


class SpectrumAcquisition:
    """Handles spectrum acquisition with averaging via Spectrometer HAL."""

    def __init__(self, spectrometer: Spectrometer) -> None:
        self.spec = spectrometer

    def acquire_averaged_spectrum(
        self,
        wave_min_index: int,
        wave_max_index: int,
        num_scans: int = 1,
    ) -> np.ndarray | None:
        try:
            return self.spec.read_roi(wave_min_index, wave_max_index, num_scans)
        except Exception as e:
            logger.error(f"Error acquiring spectrum: {e}")
            return None
