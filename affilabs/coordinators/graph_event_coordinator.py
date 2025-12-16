"""Graph Event Coordinator.

Manages graph interaction and display control events including:
- Graph clicking and channel selection
- Flag/annotation management
- Axis scaling controls (auto/manual)
- Filter toggling and strength
- Cycle data table updates

This coordinator handles UI interactions with the graph displays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from main_simplified import Application

from affilabs.utils.logger import logger


class GraphEventCoordinator:
    """Coordinates graph interaction and display control events.

    Handles:
    - Graph click events (channel selection, flag annotations)
    - Axis scaling controls
    - Data filtering controls
    - Cycle data table updates

    This is a pure coordinator - it routes events and updates UI,
    but does not contain business logic.
    """

    def __init__(self, app: Application):
        """Initialize graph event coordinator.

        Args:
            app: Main application instance for accessing managers and UI

        """
        self.app = app

    # =========================================================================
    # GRAPH CLICK INTERACTIONS
    # =========================================================================

    def on_graph_clicked(self, event):
        """Handle mouse clicks on cycle_of_interest_graph.

        Left click: Select channel closest to cursor
        Right click: Add flag/annotation at cursor position for selected channel

        Args:
            event: Mouse click event from PyQtGraph

        """
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QInputDialog

            # Safety check - ensure graph is initialized
            if not hasattr(self.app.main_window, "cycle_of_interest_graph"):
                return
            if not hasattr(self.app.main_window.cycle_of_interest_graph, "curves"):
                return
            if self.app.main_window.cycle_of_interest_graph.curves is None:
                return

            # Get click position in data coordinates
            pos = event.scenePos()
            mouse_point = self.app.main_window.cycle_of_interest_graph.getPlotItem().vb.mapSceneToView(
                pos,
            )
            click_time = mouse_point.x()
            click_value = mouse_point.y()
        except Exception:
            # Silently ignore errors during graph initialization
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Left click: Select nearest channel
            self.select_nearest_channel(click_time, click_value)

        elif event.button() == Qt.MouseButton.RightButton:
            # Right click: Add flag for selected channel
            if self.app._selected_channel is None:
                logger.warning(
                    "No channel selected. Left-click a channel first to select it.",
                )
                return

            # Prompt user for flag type
            flag_type, ok = QInputDialog.getItem(
                self.app.main_window,
                "Add Flag",
                f"Select flag type for Channel {chr(65 + self.app._selected_channel)} at {click_time:.2f}s:",
                ["Inject", "Wash", "Spike"],
                0,
                False,
            )

            if ok:
                self.add_flag(self.app._selected_channel, click_time, flag_type)

    def select_nearest_channel(self, click_time: float, click_value: float):
        """Select the channel whose curve is nearest to the click position.

        Args:
            click_time: X coordinate of click in data space
            click_value: Y coordinate of click in data space

        """
        try:
            import numpy as np

            # Safety check - ensure curves exist
            if not hasattr(self.app.main_window, "cycle_of_interest_graph"):
                return
            if not hasattr(self.app.main_window.cycle_of_interest_graph, "curves"):
                return
            if self.app.main_window.cycle_of_interest_graph.curves is None:
                return

            # Find nearest channel by checking distance to each curve
            min_distance = float("inf")
            nearest_channel = None

            for ch_idx in range(4):
                try:
                    curve = self.app.main_window.cycle_of_interest_graph.curves[ch_idx]
                    if not curve.isVisible():
                        continue

                    x_data, y_data = curve.getData()
                    if x_data is None or len(x_data) == 0:
                        continue

                    # Find point on curve closest to click_time
                    idx = np.argmin(np.abs(x_data - click_time))
                    curve_value = y_data[idx]

                    # Calculate distance (normalized by axis ranges for fair comparison)
                    distance = abs(curve_value - click_value)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_channel = ch_idx
                except Exception:
                    # Skip this channel if there's an error
                    continue

            if nearest_channel is not None:
                # Update selection
                old_channel = self.app._selected_channel
                self.app._selected_channel = nearest_channel

                # Update visual feedback (make selected channel thicker)
                if old_channel is not None:
                    try:
                        old_curve = self.app.main_window.cycle_of_interest_graph.curves[
                            old_channel
                        ]
                        old_pen = old_curve.opts["pen"]
                        old_pen.setWidth(2)  # Normal width
                        old_curve.setPen(old_pen)
                    except Exception:
                        pass

                try:
                    new_curve = self.app.main_window.cycle_of_interest_graph.curves[
                        nearest_channel
                    ]
                    new_pen = new_curve.opts["pen"]
                    new_pen.setWidth(4)  # Thicker for selected
                    new_curve.setPen(new_pen)
                except Exception:
                    pass

                logger.info(f"Selected Channel {chr(65 + nearest_channel)}")
        except Exception as e:
            # Silently handle errors
            logger.debug(f"Error selecting channel: {e}")

    def add_flag(self, channel: int, time: float, annotation: str):
        """Add a flag marker to the graph and save to table.

        Args:
            channel: Channel index (0-3)
            time: Time position for flag
            annotation: Flag annotation text

        """
        import pyqtgraph as pg

        # Store flag data
        flag_entry = {
            "channel": channel,
            "time": time,
            "annotation": annotation,
        }
        self.app._flag_data.append(flag_entry)

        # Get channel color
        curve = self.app.main_window.full_timeline_graph.curves[channel]
        color = curve.opts["pen"].color()

        # Create flag marker for Navigation graph (prominent)
        flag_line = pg.InfiniteLine(
            pos=time,
            angle=90,
            pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False,
        )

        # Add flag symbol at top
        flag_symbol = pg.ScatterPlotItem(
            [time],
            [self.app.main_window.full_timeline_graph.getPlotItem().viewRange()[1][1]],
            symbol="t",  # Triangle down (flag shape)
            size=15,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color=color, width=2),
        )

        # Add to Navigation graph (full_timeline_graph)
        self.app.main_window.full_timeline_graph.addItem(flag_line)
        self.app.main_window.full_timeline_graph.addItem(flag_symbol)

        # Store references on Navigation graph
        if not hasattr(self.app.main_window.full_timeline_graph, "flag_markers"):
            self.app.main_window.full_timeline_graph.flag_markers = []

        self.app.main_window.full_timeline_graph.flag_markers.append(
            {
                "line": flag_line,
                "symbol": flag_symbol,
                "data": flag_entry,
            },
        )

        # Update cycle data table
        self.update_cycle_data_table()

        logger.info(
            f"Added flag for Channel {chr(65 + channel)} at {time:.2f}s: '{annotation}'",
        )

    def update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information."""
        from PySide6.QtWidgets import QTableWidgetItem

        # Build flag summary string for each row (currently just showing all flags)
        # In a real implementation, this would map flags to specific cycles
        flag_summary = "\n".join(
            [
                f"Ch {chr(65 + f['channel'])} @ {f['time']:.1f}s: {f['annotation']}"
                for f in self.app._flag_data
            ],
        )

        # Update first row's Flags column with all flags
        # (In production, you'd map each flag to its corresponding cycle row)
        if self.app.main_window.cycle_data_table.rowCount() > 0:
            flags_item = QTableWidgetItem(flag_summary)
            self.app.main_window.cycle_data_table.setItem(0, 4, flags_item)

    # =========================================================================
    # AXIS SCALING CONTROLS
    # =========================================================================

    def on_autoscale_toggled(self, checked: bool):
        """Handle autoscale radio button toggle.

        Args:
            checked: Radio button state

        """
        if not checked:  # Radio button was unchecked (manual selected)
            return

        logger.info(f"Autoscale enabled for {self.app._selected_axis.upper()}-axis")

        # Enable autoscale for selected axis
        if self.app._selected_axis == "x":
            self.app.main_window.cycle_of_interest_graph.enableAutoRange(axis="x")
        else:
            self.app.main_window.cycle_of_interest_graph.enableAutoRange(axis="y")

    def on_manual_scale_toggled(self, checked: bool):
        """Handle manual scale radio button toggle.

        Args:
            checked: Radio button state

        """
        if not checked:  # Radio button was unchecked (auto selected)
            return

        logger.info(f"Manual scale enabled for {self.app._selected_axis.upper()}-axis")

        # Disable autoscale and enable manual inputs
        self.app.main_window.min_input.setEnabled(True)
        self.app.main_window.max_input.setEnabled(True)

        # Apply current manual range values if any
        self.on_manual_range_changed()

    def on_manual_range_changed(self):
        """Handle manual range input value changes."""
        # Only apply if manual mode is selected
        if not self.app.main_window.manual_radio.isChecked():
            return

        try:
            min_text = self.app.main_window.min_input.text()
            max_text = self.app.main_window.max_input.text()

            # Parse values
            if not min_text or not max_text:
                return  # Need both values

            min_val = float(min_text)
            max_val = float(max_text)

            if min_val >= max_val:
                logger.warning(f"Invalid range: min ({min_val}) >= max ({max_val})")
                return

            logger.info(
                f"Setting {self.app._selected_axis.upper()}-axis range: [{min_val}, {max_val}]",
            )

            # Apply range to selected axis
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

    def on_axis_selected(self, checked: bool):
        """Handle axis selector button toggle.

        Args:
            checked: Button state

        """
        if not checked:  # Button was unchecked
            return

        # Determine which axis is now selected
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

    # =========================================================================
    # FILTER CONTROLS
    # =========================================================================

    def on_filter_toggled(self, checked: bool):
        """Handle data filtering checkbox toggle.

        Args:
            checked: Checkbox state

        """
        self.app._filter_enabled = checked
        logger.info(f"Data filtering: {'enabled' if checked else 'disabled'}")

        # Redraw full timeline graph with/without filtering
        self.app._redraw_timeline_graph()

        # IMMEDIATE REFRESH: Also update cycle of interest graph
        self.app._update_cycle_of_interest_graph()
        logger.info(
            "[OK] Filter toggle complete - both timeline and cycle graphs refreshed",
        )
