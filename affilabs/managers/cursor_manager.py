"""Cursor Manager - Handles cursor positioning and range selection.

This manager encapsulates all cursor-related logic:
- Cursor positioning and movement
- Snap-to-data functionality
- Time range selection
- Cursor input synchronization
- Export of selected ranges
"""

from typing import Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from ..affilabs_core_ui import AffilabsMainWindow


class CursorManager:
    """Manages cursor positioning, snap-to-data, and range selection."""

    def __init__(self, window: 'AffilabsMainWindow'):
        """Initialize the cursor manager.

        Args:
            window: Reference to the main window
        """
        self.window = window
        self._updating_cursor_inputs = False

    def select_time_range(self, seconds_from_end: float) -> None:
        """Select time range relative to current end time.

        Args:
            seconds_from_end: Negative number of seconds to go back from end
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return
        if not hasattr(self.window.full_timeline_graph, 'stop_cursor'):
            return

        try:
            # Get current stop position (latest data)
            stop_time = self.window.full_timeline_graph.stop_cursor.value()

            # Calculate start time (negative seconds means go back from stop)
            start_time = max(0, stop_time + seconds_from_end)

            # Update cursors
            self.window.full_timeline_graph.start_cursor.setValue(start_time)
            self.window.full_timeline_graph.stop_cursor.setValue(stop_time)

            # Update spinboxes
            self.update_cursor_inputs()

            print(f"Selected range: {start_time:.1f}s to {stop_time:.1f}s ({abs(seconds_from_end)}s duration)")
        except Exception as e:
            print(f"Error selecting time range: {e}")

    def select_all_data(self) -> None:
        """Select entire timeline from 0 to latest data."""
        if not hasattr(self.window, 'full_timeline_graph'):
            return
        if not hasattr(self.window.full_timeline_graph, 'stop_cursor'):
            return

        try:
            # Set start to 0
            self.window.full_timeline_graph.start_cursor.setValue(0)

            # Stop stays at current position (latest data)
            stop_time = self.window.full_timeline_graph.stop_cursor.value()

            # Update spinboxes
            self.update_cursor_inputs()

            print(f"Selected all data: 0s to {stop_time:.1f}s")
        except Exception as e:
            print(f"Error selecting all data: {e}")

    def on_start_input_changed(self, value: float) -> None:
        """Update start cursor when spinbox changes.

        Args:
            value: New start time value
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return
        if not hasattr(self.window.full_timeline_graph, 'start_cursor'):
            return

        # Prevent circular updates
        if self._updating_cursor_inputs:
            return

        try:
            self.window.full_timeline_graph.start_cursor.setValue(value)
            self.update_duration_label()
        except Exception as e:
            print(f"Error updating start cursor: {e}")

    def on_stop_input_changed(self, value: float) -> None:
        """Update stop cursor when spinbox changes.

        Args:
            value: New stop time value
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return
        if not hasattr(self.window.full_timeline_graph, 'stop_cursor'):
            return

        # Prevent circular updates
        if self._updating_cursor_inputs:
            return

        try:
            self.window.full_timeline_graph.stop_cursor.setValue(value)
            self.update_duration_label()
        except Exception as e:
            print(f"Error updating stop cursor: {e}")

    def update_cursor_inputs(self) -> None:
        """Update spinboxes to match cursor positions."""
        if not hasattr(self.window, 'start_time_input') or not hasattr(self.window, 'stop_time_input'):
            return
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        try:
            self._updating_cursor_inputs = True

            start_val = self.window.full_timeline_graph.start_cursor.value()
            stop_val = self.window.full_timeline_graph.stop_cursor.value()

            self.window.start_time_input.setValue(start_val)
            self.window.stop_time_input.setValue(stop_val)

            self.update_duration_label()
        except Exception as e:
            print(f"Error updating cursor inputs: {e}")
        finally:
            self._updating_cursor_inputs = False

    def update_duration_label(self) -> None:
        """Update duration label based on cursor positions."""
        if not hasattr(self.window, 'duration_label'):
            return
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        try:
            start = self.window.full_timeline_graph.start_cursor.value()
            stop = self.window.full_timeline_graph.stop_cursor.value()
            duration = abs(stop - start)
            self.window.duration_label.setText(f"({duration:.1f}s)")
        except Exception as e:
            pass

    def export_cursor_range(self) -> None:
        """Export data from selected cursor range to CSV."""
        if not hasattr(self.window, 'app') or not self.window.app:
            print("Application not initialized")
            return

        try:
            start_time = self.window.full_timeline_graph.start_cursor.value()
            stop_time = self.window.full_timeline_graph.stop_cursor.value()

            # Forward to application's export cycle method
            if hasattr(self.window.app, 'export_cycle_data'):
                self.window.app.export_cycle_data()
                print(f"Exporting range: {start_time:.1f}s to {stop_time:.1f}s")
            else:
                print("Export function not available")
        except Exception as e:
            print(f"Error exporting cursor range: {e}")

    def on_cursor_dragged(self, evt) -> None:
        """Handle cursor being dragged - update inputs in real-time.

        Args:
            evt: Cursor event
        """
        self.update_cursor_inputs()

    def on_cursor_moved(self, evt) -> None:
        """Handle cursor movement finished - update inputs and apply snap if enabled.

        Args:
            evt: Cursor event
        """
        # Apply snap to data if enabled
        if hasattr(self.window, 'snap_checkbox') and self.window.snap_checkbox.isChecked():
            self.apply_snap_to_data(evt)

        self.update_cursor_inputs()

    def apply_snap_to_data(self, cursor) -> None:
        """Snap cursor to nearest data point timestamp.

        Args:
            cursor: The cursor to snap
        """
        if not hasattr(self.window, 'app') or not self.window.app:
            return
        if not hasattr(self.window.app, 'buffer_mgr'):
            return

        try:
            # Get cursor position
            cursor_time = cursor.value()

            # Find nearest timestamp from any channel with data
            nearest_time = cursor_time
            min_distance = float('inf')

            for ch in ['a', 'b', 'c', 'd']:
                time_data = self.window.app.buffer_mgr.timeline_data[ch].time
                if len(time_data) > 0:
                    timestamps = np.array(time_data)
                    idx = np.argmin(np.abs(timestamps - cursor_time))
                    if idx < len(timestamps):
                        candidate = timestamps[idx]
                        distance = abs(candidate - cursor_time)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_time = candidate

            # Snap to nearest (only if within reasonable distance)
            if min_distance < float('inf'):
                cursor.setValue(float(nearest_time))
        except Exception as e:
            print(f"Error applying snap: {e}")
