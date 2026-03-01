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
    def apply_reference_curve_styles(app: Application, ref_ch: "str | None") -> None:
        """Style the reference channel curve as dashed+dim; restore all others to solid.

        Args:
            app: Application instance
            ref_ch: Channel letter (lower) that is now the reference, or None to clear all.

        """
        from affilabs.settings import settings

        colorblind = getattr(app.main_window, "colorblind_check", None)
        colorblind_on = colorblind.isChecked() if colorblind is not None else False

        _STANDARD_COLORS = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]

        curves = app.main_window.cycle_of_interest_graph.curves
        for ch_idx, ch_letter in enumerate(["a", "b", "c", "d"]):
            if ch_idx >= len(curves):
                continue
            curve = curves[ch_idx]

            # Determine base color
            if colorblind_on:
                rgb = settings.GRAPH_COLORS_COLORBLIND[ch_letter]
                hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            else:
                hex_color = _STANDARD_COLORS[ch_idx]

            if ref_ch is not None and ch_letter == ref_ch.lower():
                # Reference channel: dashed line, 80% alpha
                r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                curve.setPen(
                    pg.mkPen(
                        color=(r, g, b, 204),  # 204 / 255 ≈ 80%
                        width=2,
                        style=pg.QtCore.Qt.PenStyle.DashLine,
                    )
                )
            else:
                # Normal channel: solid line, full opacity
                curve.setPen(pg.mkPen(color=hex_color, width=2))

    @staticmethod
    def subtract_reference(
        ch_time: "np.ndarray",
        ch_spr: "np.ndarray",
        ref_time: "np.ndarray",
        ref_spr: "np.ndarray",
    ) -> "np.ndarray":
        """Return ch_spr with reference interpolated and subtracted — display only, no mutation.

        Args:
            ch_time: Time array for the channel being plotted
            ch_spr: SPR (delta) array for the channel being plotted
            ref_time: Time array for the reference channel
            ref_spr: SPR (delta) array for the reference channel

        Returns:
            Subtracted SPR array (same length as ch_spr).  Returns ch_spr unchanged
            if there are fewer than 2 reference points or arrays are empty.

        """
        if len(ref_time) < 2 or len(ch_time) == 0:
            return ch_spr
        ref_interp = np.interp(ch_time, ref_time, ref_spr)
        return ch_spr - ref_interp

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
