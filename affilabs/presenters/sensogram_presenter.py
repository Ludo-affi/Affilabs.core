"""Sensogram Presenter

Handles all graph-related UI updates for timeline and cycle-of-interest plots.
Extracted from AffilabsMainWindow to follow Presenter Pattern and improve testability.
"""

from typing import Optional, Dict, List, Any, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from affilabs_core_ui import AffilabsMainWindow


class SensogramPresenter:
    """Presenter for sensogram graph updates.

    Manages:
    - Timeline graph data updates
    - Cycle-of-interest graph data updates
    - Cursor position synchronization
    - Channel visibility toggling
    - Flag markers
    - Region highlighting
    """

    def __init__(self, main_window: 'AffilabsMainWindow'):
        """Initialize presenter with reference to main window.

        Args:
            main_window: The AffilabsMainWindow instance containing the graph widgets
        """
        self.window = main_window
        self._updating_cursor_inputs = False

    def update_timeline_data(self, channel_data: Dict[int, np.ndarray], time_array: np.ndarray) -> None:
        """Update full timeline graph with new data.

        Args:
            channel_data: Dictionary mapping channel index (0-3) to data array
            time_array: Time axis array
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        try:
            for ch_idx, data in channel_data.items():
                if ch_idx < len(self.window.full_timeline_graph.curves):
                    curve = self.window.full_timeline_graph.curves[ch_idx]
                    curve.setData(time_array, data)
        except Exception as e:
            print(f"Error updating timeline data: {e}")

    def update_cycle_data(self, channel_data: Dict[int, np.ndarray], time_array: np.ndarray) -> None:
        """Update cycle-of-interest graph with new data.

        Args:
            channel_data: Dictionary mapping channel index (0-3) to data array
            time_array: Time axis array for the cycle region
        """
        if not hasattr(self.window, 'cycle_of_interest_graph'):
            return

        try:
            for ch_idx, data in channel_data.items():
                if ch_idx < len(self.window.cycle_of_interest_graph.curves):
                    curve = self.window.cycle_of_interest_graph.curves[ch_idx]
                    curve.setData(time_array, data)
        except Exception as e:
            print(f"Error updating cycle data: {e}")

    def update_cursor_positions(self, start_time: Optional[float] = None,
                               stop_time: Optional[float] = None) -> None:
        """Update cursor positions programmatically.

        Args:
            start_time: New start cursor position (seconds), or None to keep current
            stop_time: New stop cursor position (seconds), or None to keep current
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        try:
            if start_time is not None and hasattr(self.window.full_timeline_graph, 'start_cursor'):
                self.window.full_timeline_graph.start_cursor.setValue(start_time)

            if stop_time is not None and hasattr(self.window.full_timeline_graph, 'stop_cursor'):
                self.window.full_timeline_graph.stop_cursor.setValue(stop_time)

            self.update_cursor_inputs()
        except Exception as e:
            print(f"Error updating cursor positions: {e}")

    def update_cursor_inputs(self) -> None:
        """Sync cursor input spinboxes with actual cursor positions."""
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

    def toggle_channel_visibility(self, channel: str, visible: bool) -> None:
        """Toggle visibility of a channel on both graphs.

        Args:
            channel: Channel letter ('A', 'B', 'C', or 'D')
            visible: True to show, False to hide
        """
        channel_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(channel)
        if channel_idx is None:
            return

        # Update full timeline graph
        if hasattr(self.window, 'full_timeline_graph'):
            if channel_idx < len(self.window.full_timeline_graph.curves):
                curve = self.window.full_timeline_graph.curves[channel_idx]
                curve.show() if visible else curve.hide()

        # Update cycle of interest graph
        if hasattr(self.window, 'cycle_of_interest_graph'):
            if channel_idx < len(self.window.cycle_of_interest_graph.curves):
                curve = self.window.cycle_of_interest_graph.curves[channel_idx]
                curve.show() if visible else curve.hide()

    def clear_all_graph_data(self) -> None:
        """Clear all timeline data and reset graphs to empty state."""
        try:
            # Clear plot curves in full timeline graph
            if hasattr(self.window, 'full_timeline_graph'):
                for curve in self.window.full_timeline_graph.curves:
                    curve.setData([], [])

            # Clear plot curves in cycle of interest graph
            if hasattr(self.window, 'cycle_of_interest_graph'):
                for curve in self.window.cycle_of_interest_graph.curves:
                    curve.setData([], [])

            # Reset cursors to initial position
            if hasattr(self.window, 'full_timeline_graph'):
                if hasattr(self.window.full_timeline_graph, 'start_cursor'):
                    self.window.full_timeline_graph.start_cursor.setValue(0)
                if hasattr(self.window.full_timeline_graph, 'stop_cursor'):
                    self.window.full_timeline_graph.stop_cursor.setValue(0)

            print("✅ Graph data cleared")
        except Exception as e:
            print(f"❌ Error clearing graph data: {e}")

    def add_flag_marker(self, time: float, label: str, color: str = '#FF3B30') -> None:
        """Add a flag marker to the timeline graph.

        Args:
            time: Time position (seconds) for the flag
            label: Text label for the flag
            color: Color hex string for the flag marker
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        try:
            import pyqtgraph as pg

            # Create vertical line
            flag_line = pg.InfiniteLine(
                pos=time,
                angle=90,
                pen=pg.mkPen(color=color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine)
            )

            # Create text label
            flag_text = pg.TextItem(text=label, color=color, anchor=(0.5, 1))
            flag_text.setPos(time, self.window.full_timeline_graph.viewRange()[1][1])

            # Add to graph
            self.window.full_timeline_graph.addItem(flag_line)
            self.window.full_timeline_graph.addItem(flag_text)

            # Store reference for later removal
            if not hasattr(self.window.full_timeline_graph, 'flag_markers'):
                self.window.full_timeline_graph.flag_markers = []

            self.window.full_timeline_graph.flag_markers.append({
                'line': flag_line,
                'text': flag_text,
                'time': time,
                'label': label
            })
        except Exception as e:
            print(f"Error adding flag marker: {e}")

    def clear_all_flags(self) -> None:
        """Remove all flag markers from graphs."""
        try:
            if not hasattr(self.window, 'full_timeline_graph'):
                return

            if hasattr(self.window.full_timeline_graph, 'flag_markers'):
                for marker in self.window.full_timeline_graph.flag_markers:
                    # Remove line
                    if marker.get('line'):
                        self.window.full_timeline_graph.removeItem(marker['line'])
                    # Remove text
                    if marker.get('text'):
                        self.window.full_timeline_graph.removeItem(marker['text'])

                # Clear the list
                self.window.full_timeline_graph.flag_markers.clear()
                print("✅ All flags cleared")
        except Exception as e:
            print(f"Error clearing flags: {e}")

    def highlight_selected_curve(self, channel_idx: int) -> None:
        """Highlight a specific channel curve and dim others.

        Args:
            channel_idx: Channel index (0-3) to highlight, or -1 to reset all
        """
        try:
            # Update full timeline graph
            if hasattr(self.window, 'full_timeline_graph'):
                for idx, curve in enumerate(self.window.full_timeline_graph.curves):
                    if hasattr(curve, 'selected_pen') and hasattr(curve, 'original_pen'):
                        if channel_idx == -1 or idx == channel_idx:
                            curve.setPen(curve.selected_pen if idx == channel_idx else curve.original_pen)

            # Update cycle graph
            if hasattr(self.window, 'cycle_of_interest_graph'):
                for idx, curve in enumerate(self.window.cycle_of_interest_graph.curves):
                    if hasattr(curve, 'selected_pen') and hasattr(curve, 'original_pen'):
                        if channel_idx == -1 or idx == channel_idx:
                            curve.setPen(curve.selected_pen if idx == channel_idx else curve.original_pen)
        except Exception as e:
            print(f"Error highlighting curve: {e}")

    def set_live_data_enabled(self, enabled: bool) -> None:
        """Enable or disable live data updates for graphs.

        Args:
            enabled: True to enable live updates, False to freeze display
        """
        self.window.live_data_enabled = enabled
        if enabled:
            print("Live data updates enabled")
        else:
            print("Live data updates disabled - graph frozen")
