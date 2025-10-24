"""
Temporal Smoothing - EXACT OLD SOFTWARE METHOD

Old software used a simple backward-looking mean filter (NOT median!):
- Window size: 5 points (MED_FILT_WIN = 5)
- Method: np.nanmean() of last 5 values
- Causal: Only looks backward (no future data)

This removes high-frequency noise from the sensorgram over time while
preserving real SPR signal changes.

Author: From old software line 1556-1572
Date: 2025-10-21
"""

import numpy as np
from utils.logger import logger


class TemporalMeanFilter:
    """Backward-looking mean filter matching old software exactly.

    Old software line 1556-1572:
    - If enough history (> window): mean of last window_size values
    - If not enough history: mean of all available values
    - Handles NaN gracefully with np.nanmean()
    """

    def __init__(self, window_size: int = 5):
        """Initialize temporal mean filter.

        Args:
            window_size: Number of past values to average (default 5 from old software)
        """
        self.window_size = window_size
        self.history = {'a': [], 'b': [], 'c': [], 'd': []}
        logger.info(f"📊 Temporal mean filter initialized: window={window_size}")

    def update(self, channel: str, value: float) -> float:
        """Add new value and return filtered value.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            value: New peak wavelength value

        Returns:
            Filtered value (mean of last window_size values)
        """
        # Add to history
        self.history[channel].append(value)

        # Apply filter (EXACT old software logic)
        if np.isnan(value):
            return np.nan
        elif len(self.history[channel]) > self.window_size:
            # Use last window_size values
            unfiltered = self.history[channel][-self.window_size:]
            filtered_value = np.nanmean(unfiltered)
        else:
            # Use all available values
            unfiltered = self.history[channel]
            # Old software ensured odd length (removed first if even)
            if len(unfiltered) % 2 == 0:
                unfiltered = unfiltered[1:]
            filtered_value = np.nanmean(unfiltered)

        return filtered_value

    def reset(self, channel: str = None):
        """Reset history for channel or all channels."""
        if channel:
            self.history[channel] = []
        else:
            self.history = {'a': [], 'b': [], 'c': [], 'd': []}
