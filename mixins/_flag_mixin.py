"""Flag and Marker Management Mixin for Main Application.

Extracted from main.py to improve maintainability.
Contains 6 methods for managing flag markers on the cycle of interest graph.

Methods:
    - _remove_flag_near_click: Remove flag marker near click position using 2D distance
    - _try_select_flag_for_movement: Check if click is near a flag and select it for keyboard movement
    - _highlight_selected_flag: Highlight the selected flag with a yellow ring
    - _move_selected_flag: Move the selected flag left or right by one data point
    - _deselect_flag: Deselect currently selected flag
    - _add_flag: Add a flag marker to the graph and save to table
"""

import numpy as np

from affilabs.utils.logger import logger


class FlagMixin:
    """Mixin providing flag and marker management functionality.
    
    This mixin handles:
    - Adding/removing flag markers on the cycle of interest graph
    - Selecting and moving flags with keyboard controls
    - Visual feedback for selected flags
    - Injection alignment and time shift management
    """

    def _remove_flag_near_click(self, time_clicked: float, spr_clicked: float, tolerance: float = 2.0):
        """Delegate to FlagManager (interactive flag removal on cycle graph)."""
        if hasattr(self, 'flag_mgr') and self.flag_mgr is not None:
            self.flag_mgr.remove_flag_near_click(time_clicked, spr_clicked)

    def _try_select_flag_for_movement(self, time_clicked: float, spr_clicked: float):
        """Delegate to FlagManager (select flag for keyboard nudge)."""
        if hasattr(self, 'flag_mgr') and self.flag_mgr is not None:
            self.flag_mgr.try_select_flag_for_movement(time_clicked, spr_clicked)

    def _highlight_selected_flag(self, flag_idx: int):
        """Delegate to FlagManager."""
        if hasattr(self, 'flag_mgr') and self.flag_mgr is not None:
            self.flag_mgr._highlight_selected_flag(flag_idx)

    def _setup_keyboard_event_filter(self):
        """Install event filter on main window to capture keyboard events for flag movement."""
        from PySide6.QtCore import QObject, QEvent, Qt

        class KeyboardEventFilter(QObject):
            def __init__(self, app_instance):
                super().__init__()
                self.app = app_instance

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    key = event.key()

                    # Priority 1: If a flag is selected, arrow keys move the flag
                    if hasattr(self.app, '_selected_flag_idx') and self.app._selected_flag_idx is not None:
                        if key == Qt.Key.Key_Left:
                            self.app._move_selected_flag(-1)
                            return True
                        elif key == Qt.Key.Key_Right:
                            self.app._move_selected_flag(1)
                            return True
                        elif key == Qt.Key.Key_Escape:
                            self.app._deselect_flag()
                            return True

                    # Priority 2: Arrow keys shift the selected channel in time
                    # Shift modifier = coarse step (1.0s), plain = fine step (0.1s)
                    elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                        step = 1.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.1
                        direction = -1 if key == Qt.Key.Key_Left else 1
                        self.app._shift_selected_channel(direction * step)
                        return True
                    elif key == Qt.Key.Key_Escape:
                        # Reset shift for the selected channel only
                        ch = getattr(self.app, '_selected_flag_channel', None)
                        if ch and hasattr(self.app, '_channel_time_shifts'):
                            if self.app._channel_time_shifts.get(ch, 0.0) != 0.0:
                                self.app._channel_time_shifts[ch] = 0.0
                                self.app._update_cycle_of_interest_graph()
                                self.app._update_channel_shift_label()
                                logger.info(f"↩ Reset Channel {ch.upper()} time shift to 0")
                                return True

                return super().eventFilter(obj, event)

        self._keyboard_filter = KeyboardEventFilter(self)
        self.main_window.installEventFilter(self._keyboard_filter)
        logger.debug("✓ Keyboard event filter installed for flag movement")

    def _move_selected_flag(self, direction: int):
        """Delegate to FlagManager (arrow-key flag nudge)."""
        if hasattr(self, 'flag_mgr') and self.flag_mgr is not None:
            self.flag_mgr.move_selected_flag(direction)

    def _deselect_flag(self):
        """Delegate to FlagManager."""
        if hasattr(self, 'flag_mgr') and self.flag_mgr is not None:
            self.flag_mgr.deselect_flag()

    def _shift_selected_channel(self, delta_seconds: float):
        """Shift the selected channel's display time by delta_seconds.

        This is a pure visual shift on the Active Cycle graph.
        Arrow Left/Right = ±0.1s, Shift+Arrow = ±1.0s.

        Args:
            delta_seconds: Time offset to add (negative = shift left, positive = shift right)
        """
        ch = getattr(self, '_selected_flag_channel', None)
        if not ch:
            return

        current_shift = self._channel_time_shifts.get(ch, 0.0)
        new_shift = round(current_shift + delta_seconds, 2)  # avoid float drift
        self._channel_time_shifts[ch] = new_shift

        # Refresh the Active Cycle graph (shift is applied in ui_update_helpers)
        self._update_cycle_of_interest_graph()

        # Update shift indicator in UI
        self._update_channel_shift_label()

    def _update_channel_shift_label(self):
        """Update the channel shift indicator label in the UI."""
        if not hasattr(self.main_window, 'channel_shift_label'):
            return

        # Build compact shift text showing only non-zero shifts
        shifts = []
        for ch in ['a', 'b', 'c', 'd']:
            s = self._channel_time_shifts.get(ch, 0.0)
            if s != 0.0:
                shifts.append(f"{ch.upper()}: {s:+.1f}s")

        if shifts:
            self.main_window.channel_shift_label.setText("  ".join(shifts))
            self.main_window.channel_shift_label.setVisible(True)
        else:
            self.main_window.channel_shift_label.setVisible(False)

    def _add_flag(self, channel: int, time: float, annotation: str):
        """Add a flag marker to the graph and save to table."""
        pass  # graph_events removed

    # ------------------------------------------------------------------ #
    # Graph click / flag interaction                                       #
    # ------------------------------------------------------------------ #

    def _on_graph_clicked(self, event):
        """Handle mouse clicks on cycle_of_interest_graph.

        Double-Click: Select nearest channel (highlights curve)
        Ctrl+Click: Show flag type menu to add marker
        Right-Click: Remove flag marker near cursor
        """
        import numpy as np
        from PySide6.QtCore import Qt

        pos = event.scenePos()
        view_box = self.main_window.cycle_of_interest_graph.plotItem.vb
        mouse_point = view_box.mapSceneToView(pos)
        time_clicked = mouse_point.x()
        spr_clicked = mouse_point.y()

        if event.double():
            nearest_channel = self._find_nearest_channel_at_click(time_clicked, spr_clicked)
            if nearest_channel:
                self._select_flag_channel_visual(nearest_channel)
            return

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            selected_channel = getattr(self, '_selected_flag_channel', 'a')
            cycle_time_raw = self.buffer_mgr.cycle_data[selected_channel].time
            cycle_spr_raw = self.buffer_mgr.cycle_data[selected_channel].spr
            if len(cycle_time_raw) < 2 or len(cycle_spr_raw) < 2:
                return
            first_time = cycle_time_raw[1]
            cycle_time_display = cycle_time_raw[1:] - first_time
            cycle_spr_display = cycle_spr_raw[1:]
            time_idx = np.argmin(np.abs(cycle_time_display - time_clicked))
            time_at_point = cycle_time_display[time_idx]
            spr_at_time = cycle_spr_display[time_idx]
            self.flag_mgr.show_flag_type_menu(event, selected_channel, time_at_point, spr_at_time)

        elif event.button() == Qt.MouseButton.RightButton:
            self.flag_mgr.remove_flag_near_click(time_clicked, spr_clicked)

        elif event.button() == Qt.MouseButton.LeftButton:
            self.flag_mgr.try_select_flag_for_movement(time_clicked, spr_clicked)

    def _find_nearest_channel_at_click(self, time_clicked: float, spr_clicked: float):
        """Return channel identifier ('a'-'d') closest to click, or None."""
        import numpy as np
        min_distance = float('inf')
        nearest_channel = None
        try:
            view_box = self.main_window.cycle_of_interest_graph.plotItem.vb
            view_ranges = view_box.viewRange()
            spr_range = max(view_ranges[1][1] - view_ranges[1][0], 1.0)
        except Exception:
            spr_range = 100.0

        for ch in ['a', 'b', 'c', 'd']:
            cycle_time_raw = self.buffer_mgr.cycle_data[ch].time
            cycle_spr_raw = self.buffer_mgr.cycle_data[ch].spr
            if len(cycle_time_raw) < 2 or len(cycle_spr_raw) < 2:
                continue
            first_time = cycle_time_raw[1]
            cycle_time_display = cycle_time_raw[1:] - first_time
            cycle_spr_display = cycle_spr_raw[1:]
            time_idx = np.argmin(np.abs(cycle_time_display - time_clicked))
            if time_idx < len(cycle_spr_display):
                spr_at_time = cycle_spr_display[time_idx]
                distance = abs(spr_at_time - spr_clicked) / spr_range
                if distance < min_distance:
                    min_distance = distance
                    nearest_channel = ch

        TOLERANCE = 0.15
        return nearest_channel if nearest_channel and min_distance < TOLERANCE else None

    def _select_flag_channel_visual(self, channel: str):
        """Select a channel for flagging and update visual highlighting."""
        self._selected_flag_channel = channel
        if hasattr(self.main_window, '_on_flag_channel_selected'):
            self.main_window._on_flag_channel_selected(channel)

    def _add_flag_marker(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """DEPRECATED — use self.flag_mgr.add_flag_marker() instead.

        This legacy method maintained a separate dict-based _flag_markers list
        that was out of sync with FlagManager. All callers should use FlagManager.
        """
        from affilabs.utils.logger import logger
        logger.warning(
            f"_add_flag_marker called (DEPRECATED) — routing to flag_mgr.add_flag_marker: "
            f"channel={channel}, type={flag_type}"
        )
        if hasattr(self, 'flag_mgr'):
            self.flag_mgr.add_flag_marker(channel, time_val, spr_val, flag_type)
        else:
            logger.error("Cannot add flag: flag_mgr not initialized")
