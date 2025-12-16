"""Data Processing Helper Utilities.

Provides data processing utility functions for:
- Smoothing and filtering operations
- Timeline graph rendering
- Online mode optimizations
- Kalman and median filtering

These are pure utility functions extracted from the main Application class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]

import numpy as np
import pyqtgraph as pg  # type: ignore[import-untyped]


class DataProcessingHelpers:
    """Data processing utility functions.

    Static methods for filtering, smoothing, and graph rendering operations.
    """

    @staticmethod
    def apply_smoothing(
        app: Application,
        data: np.ndarray,
        strength: int,
        channel: str | None = None,
        method: str | None = None,
        online_mode: bool = False,
    ) -> np.ndarray:
        """Apply smoothing filter to data (median or Kalman).

        Args:
            app: Application instance
            data: Input data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier ('a', 'b', 'c', 'd') - required for Kalman
            method: Filter method override ('median' or 'kalman'), uses app._filter_method if None
            online_mode: If True, only filters recent window for large datasets (optimized for real-time display)

        Returns:
            Smoothed data array

        """
        if len(data) < 3:
            return data

        # Online mode optimization: For large datasets, only filter recent window
        if online_mode and len(data) > 200:
            ONLINE_FILTER_WINDOW = 200
            split_point = len(data) - ONLINE_FILTER_WINDOW
            overlap = 20
            filter_start = max(0, split_point - overlap)

            result = np.copy(data)
            recent_data = data[filter_start:]
            filtered_recent = DataProcessingHelpers.apply_smoothing(
                app,
                recent_data,
                strength,
                channel,
                method,
                online_mode=False,
            )
            result[filter_start:] = filtered_recent
            return result

        # Use instance method if not overridden
        filter_method = method if method is not None else app._filter_method

        if filter_method == "kalman":
            # Kalman filter - optimal for smooth trajectories
            if channel is None:
                print(
                    "[FILTER-WARN] Kalman filter requires channel ID, falling back to median",
                )
                filter_method = "median"
            elif channel not in app._kalman_filters:
                print(
                    f"[FILTER-WARN] No Kalman filter for channel {channel}, falling back to median",
                )
                filter_method = "median"

        if filter_method == "kalman" and channel is not None:
            # Apply Kalman filter
            kalman = app._kalman_filters[channel]
            smoothed = np.zeros_like(data)

            # Reset filter state before processing
            kalman.reset()

            for i, value in enumerate(data):
                smoothed[i] = kalman.update(float(value))

            return smoothed

        else:
            # Median filter - robust to outliers
            # Window size based on strength (1=size 3, 10=size 21)
            window_size = 2 * strength + 1
            window_size = max(3, min(window_size, 21))  # Clamp between 3 and 21

            # Ensure window size is odd
            if window_size % 2 == 0:
                window_size += 1

            # Import medfilt from scipy if available
            try:
                from scipy.signal import medfilt  # type: ignore[import-untyped]

                return medfilt(data, kernel_size=window_size)  # type: ignore[no-any-return]
            except ImportError:
                # Fallback to simple moving average if scipy not available
                pad_width = window_size // 2
                padded = np.pad(data, pad_width, mode="edge")
                smoothed = np.convolve(
                    padded,
                    np.ones(window_size) / window_size,
                    mode="valid",
                )
                return smoothed  # type: ignore[return-value]

    @staticmethod
    def apply_online_smoothing(
        app: Application,
        data: np.ndarray,
        strength: int,
        channel: str,
    ) -> np.ndarray:
        """Apply incremental median filtering for real-time display (alias for optimized mode).

        This is an alias that calls apply_smoothing with online_mode=True, which only
        processes recent data window instead of refiltering entire timeline on every update.

        Args:
            app: Application instance
            data: Full timeline data array
            strength: Smoothing strength (1-10)
            channel: Channel identifier

        Returns:
            Smoothed data array (full length, but efficiently computed)

        """
        return DataProcessingHelpers.apply_smoothing(
            app,
            data,
            strength,
            channel,
            online_mode=True,
        )

    @staticmethod
    def redraw_timeline_graph(app: Application) -> None:
        """Redraw the full timeline graph with current filter settings.

        Args:
            app: Application instance

        """
        for ch_letter, ch_idx in app._channel_pairs:
            time_data = app.buffer_mgr.timeline_data[ch_letter].time
            wavelength_data = app.buffer_mgr.timeline_data[ch_letter].wavelength

            if len(time_data) == 0:
                continue

            # Apply smoothing if enabled
            display_data = wavelength_data
            if app._filter_enabled:
                # Apply smoothing to timeline data
                display_data = DataProcessingHelpers.apply_smoothing(
                    app,
                    wavelength_data,
                    app._filter_strength,
                    ch_letter,
                )

            # Skip first point and shift time axis so displayed data starts at t=0
            if len(time_data) > 1:
                first_time = time_data[1]
                time_data = time_data[1:] - first_time
                display_data = display_data[1:]

            # Update curve
            curve = app.main_window.full_timeline_graph.curves[ch_idx]
            curve.setData(time_data, display_data)

            # Enable Y-axis autorange after first data point (prevents slope from 0)
            if len(time_data) > 0 and not app.main_window.full_timeline_graph.getPlotItem().getViewBox().autoRangeEnabled()[1]:
                app.main_window.full_timeline_graph.enableAutoRange(axis="y", enable=True)
