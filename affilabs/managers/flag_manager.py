"""Flag Manager - Handles flag marker management.

This manager encapsulates all flag-related logic:
- Adding flag markers to graphs
- Removing flags at specific positions
- Updating flag table displays
- Clearing flags per channel or all flags
- Flagging mode management
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..affilabs_core_ui import AffilabsMainWindow


class FlagManager:
    """Manages flag markers on graphs and flag-related UI operations."""

    def __init__(self, window: 'AffilabsMainWindow'):
        """Initialize the flag manager.

        Args:
            window: Reference to the main window
        """
        self.window = window
        self.flagging_enabled = False
        self.selected_channel_for_flagging = None

    def enable_flagging_mode(self, channel_idx: int, channel_letter: str) -> None:
        """Enable flagging mode for the selected channel.

        Args:
            channel_idx: Channel index (0-3)
            channel_letter: Channel letter (A-D)
        """
        self.selected_channel_for_flagging = channel_idx

        # Inform user that they can now click on points to flag them
        print(f"Flagging mode ready for Channel {channel_letter}")
        print("Right-click on the Live Sensorgram to add a flag at that position")
        print("Ctrl+Right-click to remove a flag near that position")

    def on_plot_clicked(self, event, plot_widget) -> None:
        """Handle clicks on the Live Sensorgram for adding/removing flags.

        Right-click: Add flag at position on selected channel
        Ctrl+Right-click: Remove flag near position on selected channel

        Args:
            event: Mouse click event
            plot_widget: The plot widget that was clicked
        """
        # Only process right-clicks for flagging
        if event.button() != 2:  # 2 = right mouse button
            return

        # Check if a channel is selected for flagging
        if self.selected_channel_for_flagging is None:
            print("Please select a channel first by clicking on its curve")
            return

        # Get click position in data coordinates
        pos = event.scenePos()
        mouse_point = plot_widget.getPlotItem().vb.mapSceneToView(pos)
        x_pos = mouse_point.x()
        y_pos = mouse_point.y()

        # Check for Ctrl modifier to remove flags
        from PySide6.QtCore import Qt
        modifiers = event.modifiers()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Remove flag near this position
            self.remove_flag_at_position(self.selected_channel_for_flagging, x_pos)
        else:
            # Add flag at this position
            self.add_flag_to_point(self.selected_channel_for_flagging, x_pos, y_pos)

        event.accept()

    def add_flag_to_point(self, channel_idx: int, x_pos: float, y_pos: float, note: str = "") -> None:
        """Add a flag marker at the specified position on the selected channel.

        Args:
            channel_idx: Channel index (0-3)
            x_pos: X position (time) for the flag
            y_pos: Y position (value) for the flag
            note: Optional note/label for the flag
        """
        # Get channel letter
        channel_letter = chr(65 + channel_idx)

        # Create label with channel and note
        label = f"Ch{channel_letter}"
        if note:
            label += f": {note}"

        # Add flag using presenter
        self.window.sensogram_presenter.add_flag_marker(x_pos, label, color='#FF3B30')

        # Store in channel flags for table tracking
        if not hasattr(self.window.full_timeline_graph, 'channel_flags'):
            self.window.full_timeline_graph.channel_flags = {0: [], 1: [], 2: [], 3: []}
        self.window.full_timeline_graph.channel_flags[channel_idx].append((x_pos, y_pos, note))

        # Update the table Flags column
        self.update_flags_table()

        print(f"Flag added to Channel {channel_letter} at x={x_pos:.2f}, y={y_pos:.2f}")

    def remove_flag_at_position(self, channel_idx: int, x_pos: float, tolerance: float = 5.0) -> None:
        """Remove a flag marker near the specified x position on the selected channel.

        Args:
            channel_idx: Channel index (0-3)
            x_pos: X position to search for flags
            tolerance: Distance tolerance for finding nearby flags
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        # Find and remove flags within tolerance
        removed_count = 0
        markers_to_remove = []

        for marker in self.window.full_timeline_graph.flag_markers:
            if marker['channel'] == channel_idx and abs(marker['x'] - x_pos) <= tolerance:
                # Remove visual elements
                self.window.full_timeline_graph.removeItem(marker['line'])
                self.window.full_timeline_graph.removeItem(marker['text'])
                markers_to_remove.append(marker)
                removed_count += 1

        # Remove from list
        for marker in markers_to_remove:
            self.window.full_timeline_graph.flag_markers.remove(marker)

        # Update channel flags
        self.window.full_timeline_graph.channel_flags[channel_idx] = [
            (x, y, note) for x, y, note in self.window.full_timeline_graph.channel_flags[channel_idx]
            if abs(x - x_pos) > tolerance
        ]

        # Update table
        self.update_flags_table()

        if removed_count > 0:
            channel_letter = chr(65 + channel_idx)
            print(f"Removed {removed_count} flag(s) from Channel {channel_letter} near x={x_pos:.2f}")

    def update_flags_table(self) -> None:
        """Update the Flags column in the cycle data table with current flags."""
        if not hasattr(self.window, 'cycle_data_table') or not hasattr(self.window, 'full_timeline_graph'):
            return

        # Count flags per channel
        flag_counts = {}
        for ch_idx in range(4):
            channel_letter = chr(65 + ch_idx)
            count = len(self.window.full_timeline_graph.channel_flags.get(ch_idx, []))
            if count > 0:
                flag_counts[channel_letter] = count

        # Update table - show flag summary
        if flag_counts:
            flag_summary = ", ".join([f"Ch{ch}: {count}" for ch, count in flag_counts.items()])
            print(f"Flags summary: {flag_summary}")

    def clear_all_flags(self, channel_idx: Optional[int] = None) -> None:
        """Clear all flags, optionally for a specific channel only.

        Args:
            channel_idx: If specified, only clear flags for this channel.
                        If None, clear all flags from all channels.
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return

        # Use presenter to clear flags
        self.window.sensogram_presenter.clear_all_flags()

        # Also clear flag data if stored in app
        if hasattr(self.window, 'app') and self.window.app and hasattr(self.window.app, '_flag_data'):
            self.window.app._flag_data.clear()

        # Clear channel_flags tracking structure if present
        if hasattr(self.window.full_timeline_graph, 'channel_flags'):
            if channel_idx is None:
                for ch_idx in range(4):
                    self.window.full_timeline_graph.channel_flags[ch_idx] = []
                print("All flags cleared")
            else:
                self.window.full_timeline_graph.channel_flags[channel_idx] = []
                channel_letter = chr(65 + channel_idx)
                print(f"All flags cleared for Channel {channel_letter}")

        # Update table
        self.update_flags_table()

    def clear_all_flags_legacy(self, channel_idx: Optional[int] = None) -> None:
        """Clear all flags (legacy method that directly manipulates flag_markers).

        This is kept for compatibility with older flag management code.

        Args:
            channel_idx: If specified, only clear flags for this channel.
        """
        if not hasattr(self.window, 'full_timeline_graph'):
            return
        if not hasattr(self.window.full_timeline_graph, 'flag_markers'):
            return

        markers_to_remove = []

        if channel_idx is None:
            # Clear all flags
            markers_to_remove = self.window.full_timeline_graph.flag_markers.copy()
        else:
            # Clear flags for specific channel
            markers_to_remove = [m for m in self.window.full_timeline_graph.flag_markers
                                if m['channel'] == channel_idx]

        # Remove visual elements
        for marker in markers_to_remove:
            self.window.full_timeline_graph.removeItem(marker['line'])
            self.window.full_timeline_graph.removeItem(marker['text'])
            self.window.full_timeline_graph.flag_markers.remove(marker)

        # Clear channel_flags
        if hasattr(self.window.full_timeline_graph, 'channel_flags'):
            if channel_idx is None:
                for ch_idx in range(4):
                    self.window.full_timeline_graph.channel_flags[ch_idx] = []
            else:
                self.window.full_timeline_graph.channel_flags[channel_idx] = []

        # Update table
        self.update_flags_table()

        if channel_idx is None:
            print("All flags cleared")
        else:
            channel_letter = chr(65 + channel_idx)
            print(f"All flags cleared for Channel {channel_letter}")
