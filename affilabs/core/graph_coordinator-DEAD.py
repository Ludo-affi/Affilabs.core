"""Graph Coordinator - Helper methods for graph updates and rendering.

This coordinator provides helper methods for:
- Cycle of interest graph updates
- Delta SPR display
- Graph scaling operations
- Reference subtraction visualization

Note: Timeline sensorgram updates are handled by main_simplified._process_pending_ui_updates()
Note: Transmission/raw spectrum plots are handled by AL_UIUpdateCoordinator
"""

import numpy as np
from PySide6.QtCore import QObject

from affilabs.utils.logger import logger
from affilabs.utils.performance_profiler import measure


class GraphCoordinator(QObject):
    """Helper class for graph operations (no independent timer - main app controls timing)."""

    def __init__(self, app) -> None:
        """Initialize graph coordinator.

        Args:
            app: Reference to main Application instance

        """
        super().__init__()
        self.app = app

        # Note: No timer here - main_simplified handles UI update timing at 10 Hz
        # This coordinator just provides helper methods for graph operations

        # ==================== Cycle of Interest Graph ====================
        """Update the cycle of interest graph based on cursor positions."""
        with measure("cycle_graph_update.total"):
            # Get cursor positions
            start_time = self.app.main_window.full_timeline_graph.start_cursor.value()
            stop_time = self.app.main_window.full_timeline_graph.stop_cursor.value()

        # Extract data within cursor range for each channel
        for ch_letter, ch_idx in self.app._channel_pairs:
            cycle_time, cycle_wavelength = self.app.buffer_mgr.extract_cycle_region(
                ch_letter,
                start_time,
                stop_time,
            )

            if len(cycle_time) == 0:
                continue

            # Apply filtering to cycle data
            if self.app._filter_enabled and len(cycle_wavelength) > 2:
                cycle_wavelength = self.app._apply_smoothing(
                    cycle_wavelength,
                    self.app._filter_strength,
                )

            # Calculate Δ SPR
            from config import WAVELENGTH_TO_RU_CONVERSION

            baseline = self.app.buffer_mgr.baseline_wavelengths[ch_letter]
            if baseline is None:
                baseline = cycle_wavelength[0] if len(cycle_wavelength) > 0 else 0

            delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

            # Store in buffer manager
            self.app.buffer_mgr.update_cycle_data(
                ch_letter,
                cycle_time,
                cycle_wavelength,
                delta_spr,
            )

        # Apply reference subtraction if enabled
        self.app._apply_reference_subtraction()

        # Update graph curves
        for ch_letter, ch_idx in self.app._channel_pairs:
            cycle_time = self.app.buffer_mgr.cycle_data[ch_letter].time
            delta_spr = self.app.buffer_mgr.cycle_data[ch_letter].spr

            if len(cycle_time) == 0:
                continue

            curve = self.app.main_window.cycle_of_interest_graph.curves[ch_idx]
            curve.setData(cycle_time, delta_spr)

        # Update Δ SPR display
        self.update_delta_display()

    def update_delta_display(self) -> None:
        """Update the Δ SPR display label with values at Stop cursor."""
        if self.app.main_window.cycle_of_interest_graph.delta_display is None:
            return

        stop_time = self.app.main_window.full_timeline_graph.stop_cursor.value()

        # Get Δ SPR values at stop cursor
        delta_values = {}
        for ch in self.app._idx_to_channel:
            time_data = self.app.buffer_mgr.cycle_data[ch].time
            spr_data = self.app.buffer_mgr.cycle_data[ch].spr

            if len(time_data) > 0 and len(spr_data) > 0:
                idx = np.argmin(np.abs(time_data - stop_time))
                delta_values[ch] = spr_data[idx]
            else:
                delta_values[ch] = 0.0

        # Update label
        self.app.main_window.cycle_of_interest_graph.delta_display.setText(
            f"Δ SPR: Ch A: {delta_values['a']:.1f} RU  |  Ch B: {delta_values['b']:.1f} RU  |  "
            f"Ch C: {delta_values['c']:.1f} RU  |  Ch D: {delta_values['d']:.1f} RU",
        )

    def redraw_timeline_graph(self) -> None:
        """Redraw the full timeline graph with current filter settings."""
        for ch_letter, ch_idx in self.app._channel_pairs:
            time_data = self.app.buffer_mgr.timeline_data[ch_letter].time
            wavelength_data = self.app.buffer_mgr.timeline_data[ch_letter].wavelength

            if len(time_data) == 0:
                continue

            # Apply smoothing if enabled
            display_data = wavelength_data
            if self.app._filter_enabled:
                display_data = self.app._apply_smoothing(
                    wavelength_data,
                    self.app._filter_strength,
                )

            # Update curve
            curve = self.app.main_window.full_timeline_graph.curves[ch_idx]
            curve.setData(time_data, display_data)

    def on_autoscale_toggled(self, checked: bool) -> None:
        """Handle autoscale radio button toggle."""
        if not checked:
            return

        logger.info(f"Autoscale enabled for {self.app._selected_axis.upper()}-axis")

        if self.app._selected_axis == "x":
            self.app.main_window.cycle_of_interest_graph.enableAutoRange(axis="x")
        else:
            self.app.main_window.cycle_of_interest_graph.enableAutoRange(axis="y")

    def on_manual_scale_toggled(self, checked: bool) -> None:
        """Handle manual scale radio button toggle."""
        if not checked:
            return

        logger.info(f"Manual scale enabled for {self.app._selected_axis.upper()}-axis")

        self.app.main_window.min_input.setEnabled(True)
        self.app.main_window.max_input.setEnabled(True)

        self.on_manual_range_changed()

    def on_manual_range_changed(self) -> None:
        """Handle manual range input changes."""
        if not self.app.main_window.manual_radio.isChecked():
            return

        try:
            min_text = self.app.main_window.min_input.text()
            max_text = self.app.main_window.max_input.text()

            if not min_text or not max_text:
                return

            min_val = float(min_text)
            max_val = float(max_text)

            if min_val >= max_val:
                logger.warning(f"Invalid range: min ({min_val}) >= max ({max_val})")
                return

            logger.info(
                f"Setting {self.app._selected_axis.upper()}-axis range: [{min_val}, {max_val}]",
            )

            if self.app._selected_axis == "x":
                self.app.main_window.cycle_of_interest_graph.setXRange(
                    min_val,
                    max_val,
                    padding=0,
                )
            else:
                self.app.main_window.cycle_of_interest_graph.setYRange(
                    min_val,
                    max_val,
                    padding=0,
                )

        except ValueError as e:
            logger.warning(f"Invalid manual range input: {e}")

    def on_axis_selected(self, checked: bool) -> None:
        """Handle axis selector button toggle."""
        if not checked:
            return

        if self.app.main_window.x_axis_btn.isChecked():
            self.app._selected_axis = "x"
            logger.info("X-axis selected for scaling controls")
        else:
            self.app._selected_axis = "y"
            logger.info("Y-axis selected for scaling controls")

        # Re-apply current mode to new axis
        if self.app.main_window.auto_radio.isChecked():
            self.on_autoscale_toggled(True)
        else:
            self.on_manual_range_changed()

    def on_filter_toggled(self, checked: bool) -> None:
        """Handle data filtering checkbox toggle."""
        self.app._filter_enabled = checked
        logger.info(f"Data filtering: {'enabled' if checked else 'disabled'}")
        self.redraw_timeline_graph()

    def on_filter_strength_changed(self, value: int) -> None:
        """Handle filter strength slider change."""
        self.app._filter_strength = value
        logger.info(f"Filter strength set to: {value}")

        if self.app._filter_enabled:
            self.redraw_timeline_graph()

    def on_tab_changing(self, index: int) -> None:
        """Temporarily pause graph updates during tab transition."""
        self._skip_graph_updates = True
        QTimer.singleShot(200, lambda: setattr(self, "_skip_graph_updates", False))

    def auto_follow_stop_cursor(self, elapsed_time: float) -> None:
        """Auto-follow latest data with stop cursor.

        Args:
            elapsed_time: Current elapsed time

        """
        if (
            hasattr(self.app.main_window.full_timeline_graph, "stop_cursor")
            and self.app.main_window.full_timeline_graph.stop_cursor is not None
        ):
            stop_cursor = self.app.main_window.full_timeline_graph.stop_cursor

            is_moving = getattr(stop_cursor, "moving", False)

            if not is_moving:
                stop_cursor.setValue(elapsed_time)
                if hasattr(stop_cursor, "label") and stop_cursor.label:
                    stop_cursor.label.setFormat(f"Stop: {elapsed_time:.1f}s")
