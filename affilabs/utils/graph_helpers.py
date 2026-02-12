"""Graph Helper Utilities.

Provides graph-related utility functions for:
- Channel styling and color management
- Reference channel subtraction
- Kalman filter initialization
- Graph data processing

These are pure utility functions extracted from the main Application class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]

import numpy as np
import pyqtgraph as pg  # type: ignore[import-untyped]


class GraphHelpers:
    """Graph-related utility functions.

    Static methods for graph styling, data processing, and filtering.
    """

    @staticmethod
    def reset_channel_style(app: Application, ch_idx: int) -> None:
        """Reset channel curve to standard or colorblind style.

        Args:
            app: Application instance
            ch_idx: Channel index (0-3)

        """
        from affilabs.settings import settings

        # Determine if colorblind mode is active
        if app.main_window.colorblind_check.isChecked():
            colors = settings.GRAPH_COLORS_COLORBLIND
            ch_letter = ["a", "b", "c", "d"][ch_idx]
            rgb = colors[ch_letter]
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        else:
            # Standard colors
            color_list = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]
            color = color_list[ch_idx]

        # Reset to solid line with full opacity
        app.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
            pg.mkPen(color=color, width=2),
        )

    @staticmethod
    def apply_reference_subtraction(app: Application) -> None:
        """Apply reference channel subtraction to all other channels.

        Args:
            app: Application instance

        """
        if app._reference_channel is None:
            # No reference selected - this is normal, user hasn't selected one yet
            return

        ref_time = app.buffer_mgr.cycle_data[app._reference_channel].time
        ref_spr = app.buffer_mgr.cycle_data[app._reference_channel].spr

        if len(ref_time) == 0:
            return

        # Subtract reference from all other channels
        for ch in app._idx_to_channel:
            if ch == app._reference_channel:
                continue  # Don't subtract reference from itself

            ch_time = app.buffer_mgr.cycle_data[ch].time
            ch_spr = app.buffer_mgr.cycle_data[ch].spr

            if len(ch_time) == 0:
                continue

            # Interpolate reference to match channel time points
            if len(ref_time) > 1:
                ref_interp = np.interp(ch_time, ref_time, ref_spr)
                # Update the cycle data with subtracted values
                subtracted_spr = ch_spr - ref_interp
                app.buffer_mgr.cycle_data[ch].spr = subtracted_spr

    @staticmethod
    def init_kalman_filters(app: Application) -> None:
        """Initialize Kalman filter instances for each channel.

        Args:
            app: Application instance

        """
        import sys
        from pathlib import Path

        # Add utils to path for KalmanFilter import
        utils_path = str(Path(__file__).parent.parent.parent / "utils")
        if utils_path not in sys.path:
            sys.path.insert(0, utils_path)

        from spr_data_processor import KalmanFilter  # type: ignore[import-untyped]

        # Map strength to Kalman noise parameters
        # Strength controls trust in measurements vs model:
        # Lower strength (1) = heavy filtering: high R, low Q → trust model, smooth heavily
        # Higher strength (10) = light filtering: low R, high Q → trust data, track closely
        #
        # R (measurement_noise): Variance of sensor noise
        # Q (process_noise): Variance of system dynamics
        # Kalman gain K = P / (P + R), so higher R → lower K → less weight on measurements
        #
        # Strength 1: R=0.10, Q=0.001 (heavy smoothing for noisy historical data)
        # Strength 5: R=0.02, Q=0.005 (balanced)
        # Strength 10: R=0.005, Q=0.01 (light smoothing for clean live data)
        measurement_noise = (
            0.1 / app._filter_strength
        )  # Lower strength → higher R → more filtering
        process_noise = (
            0.001 * app._filter_strength
        )  # Lower strength → lower Q → steadier model

        app._kalman_filters = {}
        for ch in app._idx_to_channel:
            app._kalman_filters[ch] = KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise,
            )

        # Log filter initialization
        print(
            f"[KALMAN] Filters initialized (R={measurement_noise:.4f}, Q={process_noise:.4f})",
        )
