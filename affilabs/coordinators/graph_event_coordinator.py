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

from typing import TYPE_CHECKING

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
            # UNIFIED FLAG SYSTEM: Manual flag placement on the live graph is
            # disabled. Flags are now placed by software only during acquisition.
            # Users can add/adjust flags in the Edits tab.
            pass

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
        """Add a flag marker — delegates to FlagManager (unified flag system).

        DEPRECATED: This legacy method now routes to FlagManager.add_flag_marker().
        Flags during acquisition are placed by software, not by user interaction.

        Args:
            channel: Channel index (0-3)
            time: Time position for flag
            annotation: Flag annotation text (mapped to flag_type)
        """
        # Map annotation to flag_type
        annotation_to_type = {
            "Inject": "injection",
            "injection": "injection",
            "Wash": "wash",
            "wash": "wash",
            "Spike": "spike",
            "spike": "spike",
        }
        flag_type = annotation_to_type.get(annotation, "injection")

        # Map channel index to letter
        channel_letter = chr(97 + channel)  # 0->a, 1->b, etc.

        # Delegate to FlagManager
        if hasattr(self.app, "flag_mgr") and self.app.flag_mgr:
            self.app.flag_mgr.add_flag_marker(
                channel=channel_letter,
                time_val=time,
                spr_val=0.0,  # Legacy path doesn't provide SPR
                flag_type=flag_type,
            )
        else:
            logger.warning("FlagManager not available — flag not added")

        logger.info(
            f"Added flag for Channel {chr(65 + channel)} at {time:.2f}s: '{annotation}'",
        )

    def update_cycle_data_table(self):
        """Update the Flags column in cycle data table with flag information.

        Reads from FlagManager (unified flag system) when available.
        """
        from PySide6.QtWidgets import QTableWidgetItem

        # Build flag summary from FlagManager
        if hasattr(self.app, "flag_mgr") and self.app.flag_mgr:
            live_flags = self.app.flag_mgr.get_live_flags()
            flag_summary = "\n".join(
                f"Ch {f.channel.upper()} @ {f.time:.1f}s: {f.flag_type}"
                for f in live_flags
            )
        else:
            # Legacy fallback via CycleCoordinator
            flag_data = getattr(self.app.cycles, "_flag_data", [])
            flag_summary = "\n".join(
                f"Ch {chr(65 + f['channel'])} @ {f['time']:.1f}s: {f['annotation']}"
                for f in flag_data
            )

        # Update first row's Flags column with all flags
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
