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
import pyqtgraph as pg

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
        """Remove flag marker near the click position using 2D distance.

        Args:
            time_clicked: Time coordinate of click
            spr_clicked: SPR coordinate of click
            tolerance: Not used (kept for compatibility)
        """
        if not hasattr(self, '_flag_markers') or not self._flag_markers:
            return

        # Find flag closest to click position using 2D distance
        min_distance = float('inf')
        closest_flag_idx = None

        # Get view range for normalization
        view_range = self.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag['time'] - time_clicked) / time_range
            spr_dist = abs(flag['spr'] - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_flag_idx = idx

        # Remove the closest flag if within tolerance (2% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.02:
            flag = self._flag_markers[closest_flag_idx]

            # Remove from graph - clear the marker data first to ensure complete cleanup
            try:
                flag['marker'].clear()  # Clear any internal data/points
            except Exception:
                pass

            self.main_window.cycle_of_interest_graph.removeItem(flag['marker'])

            # Remove from storage
            self._flag_markers.pop(closest_flag_idx)

            # If we removed an injection flag, check if we need to clear alignment
            if flag['type'] == 'injection':
                # Count remaining injection flags
                remaining_injections = [f for f in self._flag_markers if f['type'] == 'injection']
                if len(remaining_injections) == 0:
                    # No more injections - clear alignment line and time shifts
                    if self._injection_alignment_line is not None:
                        self.main_window.cycle_of_interest_graph.removeItem(self._injection_alignment_line)
                        self._injection_alignment_line = None
                    self._injection_reference_time = None
                    self._injection_reference_channel = None

                    # CRITICAL: Reset all channel time shifts
                    self._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}

                    # Refresh graph to show unshifted data
                    self._update_cycle_of_interest_graph()

                    logger.info("✓ Injection alignment and time shifts cleared")

            logger.info(f"🚩 {flag['type'].capitalize()} flag removed: Channel {flag['channel'].upper()} at t={flag['time']:.2f}s")

            # Recalculate and display time deltas with remaining flags
            self._calculate_and_display_flag_deltas()

    def _try_select_flag_for_movement(self, time_clicked: float, spr_clicked: float):
        """Check if click is near a flag and select it for keyboard movement."""
        if not hasattr(self, '_flag_markers') or not self._flag_markers:
            return

        # Find flag closest to click
        min_distance = float('inf')
        closest_flag_idx = None

        # Get view range for normalization
        view_range = self.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag['time'] - time_clicked) / time_range
            spr_dist = abs(flag['spr'] - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_flag_idx = idx

        # Select flag if within tolerance (3% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.03:
            self._selected_flag_idx = closest_flag_idx
            flag = self._flag_markers[closest_flag_idx]

            # Visual feedback: highlight selected flag
            self._highlight_selected_flag(closest_flag_idx)

            logger.info(f"🎯 Selected {flag['type']} flag at t={flag['time']:.2f}s (use arrow keys ← → to move, ESC to deselect)")

    def _highlight_selected_flag(self, flag_idx: int):
        """Highlight the selected flag with a yellow ring."""
        # Remove previous highlight if any
        if self._flag_highlight_ring is not None:
            self.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)

        flag = self._flag_markers[flag_idx]

        # Create a ring around the selected flag
        self._flag_highlight_ring = pg.ScatterPlotItem(
            [flag['time']],
            [flag['spr']],
            symbol='o',
            size=25,
            pen=pg.mkPen('y', width=3),  # Yellow ring
            brush=None
        )
        self.main_window.cycle_of_interest_graph.addItem(self._flag_highlight_ring)

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
        """Move the selected flag left (-1) or right (+1) by one data point.

        Args:
            direction: -1 for left, +1 for right
        """
        if self._selected_flag_idx is None or self._selected_flag_idx >= len(self._flag_markers):
            return

        flag = self._flag_markers[self._selected_flag_idx]
        channel = flag['channel']

        # Get DISPLAY data (rebased time)
        cycle_time_raw = self.buffer_mgr.cycle_data[channel].time
        cycle_spr_raw = self.buffer_mgr.cycle_data[channel].spr

        if len(cycle_time_raw) < 2:
            return

        # Match display logic: skip first point and rebase
        first_time = cycle_time_raw[1]
        cycle_time_display = cycle_time_raw[1:] - first_time
        cycle_spr_display = cycle_spr_raw[1:]

        # Find current flag position in data array
        current_idx = np.argmin(np.abs(cycle_time_display - flag['time']))

        # Move to adjacent data point
        new_idx = current_idx + direction
        new_idx = max(0, min(len(cycle_time_display) - 1, new_idx))  # Clamp to valid range

        # Update flag position
        new_time = cycle_time_display[new_idx]
        new_spr = cycle_spr_display[new_idx]

        # Remove old marker
        self.main_window.cycle_of_interest_graph.removeItem(flag['marker'])

        # Create new marker at new position
        flag_styles = {
            'injection': {'symbol': 't', 'size': 15, 'color': (255, 50, 50, 230)},
            'wash': {'symbol': 's', 'size': 12, 'color': (50, 150, 255, 230)},
            'spike': {'symbol': 'star', 'size': 18, 'color': (255, 200, 0, 230)}
        }
        style = flag_styles.get(flag['type'], flag_styles['injection'])

        new_marker = pg.ScatterPlotItem(
            [new_time],
            [new_spr],
            symbol=style['symbol'],
            size=style['size'],
            brush=pg.mkBrush(*style['color']),
            pen=pg.mkPen('w', width=2)
        )
        self.main_window.cycle_of_interest_graph.addItem(new_marker)

        # Update flag data
        flag['time'] = new_time
        flag['spr'] = new_spr
        flag['marker'] = new_marker

        # Update highlight ring position
        self._highlight_selected_flag(self._selected_flag_idx)

        # If this is an injection flag and NOT the reference, recalculate alignment
        if flag['type'] == 'injection' and self._injection_reference_time is not None:
            if flag['channel'] != self._injection_reference_channel:
                time_diff = new_time - self._injection_reference_time
                shift_amount = -time_diff
                self._channel_time_shifts[channel] = shift_amount

                # Export updated time shift to recording metadata
                if self.recording_mgr.is_recording:
                    self.recording_mgr.update_metadata(f'channel_{channel}_time_shift', shift_amount)

                self._update_cycle_of_interest_graph()
                logger.info(f"→ Moved & realigned Channel {channel.upper()}: shift={shift_amount:+.2f}s")
            else:
                # Moving the reference flag - update reference time
                old_ref = self._injection_reference_time
                self._injection_reference_time = new_time

                # Update alignment line
                if self._injection_alignment_line is not None:
                    self._injection_alignment_line.setPos(new_time)

                logger.info(f"→ Moved reference flag: {old_ref:.2f}s → {new_time:.2f}s")
        else:
            logger.debug(f"Flag moved: t={new_time:.2f}s, SPR={new_spr:.2f} RU")

    def _deselect_flag(self):
        """Deselect currently selected flag."""
        if self._flag_highlight_ring is not None:
            self.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
            self._flag_highlight_ring = None

        self._selected_flag_idx = None
        logger.debug("Flag deselected")

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
