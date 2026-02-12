"""Flag Manager - Handles flag marker management.

ARCHITECTURE LAYER: Manager (Business Logic)

This manager encapsulates all flag-related logic:
- Adding/removing flag markers on cycle graph
- Flag type management (injection, wash, spike)
- Injection alignment and channel time shifts
- Flag selection and keyboard movement
- Auto-calculated markers (wash deadline, etc.)
- Exporting flags to recording manager
- Clearing flags for new cycles

UNIFIED MARKER SYSTEM:
- User-placed flags: InjectionFlag, WashFlag, SpikeFlag (domain models)
- Auto-markers: Wash deadline, injection deadline (AutoMarker, calculated by system)
- Both stored in unified marker list for selection/movement

DEPENDENCIES:
- main_window.cycle_of_interest_graph (UI component)
- recording_mgr (for export)
- buffer_mgr (for cycle data)

USAGE:
    flag_mgr = FlagManager(app_instance)
    flag_mgr.show_flag_type_menu(event, channel, time, spr)
    flag_mgr.create_auto_marker(marker_type, time, contact_time)
    flag_mgr.clear_all_flags()
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QMenu

from affilabs.domain.flag import Flag, InjectionFlag, create_flag

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from main import Application


@dataclass
class AutoMarker:
    """Auto-calculated marker for system-generated timeline events.

    Represents markers that are calculated by the system (e.g., wash deadline)
    rather than manually placed by the user. Can be moved/adjusted like flags.

    Attributes:
        marker_type: Type of auto-marker ('wash_deadline', 'injection_deadline', etc.)
        time: Position on timeline (seconds)
        label: Display label (e.g., '⏱ Wash Due')
        color: Color code (e.g., '#FF9500')
        marker: PyQtGraph visual object (InfiniteLine or similar)
        is_selectable: Whether user can select/move this marker
    """

    marker_type: str
    time: float
    label: str
    color: str
    marker: any = None
    is_selectable: bool = True


class FlagManager:
    """Manages flag markers on graphs and flag-related operations.

    This is the SINGLE source of truth for all flag functionality.
    All flag methods have been moved here from Application class.
    """

    def __init__(self, app: "Application"):
        """Initialize the flag manager.

        Args:
            app: Reference to the Application instance (for accessing main_window, recording_mgr, etc.)

        """
        self.app = app

        # Flag marker storage - now using Flag domain model instances
        self._flag_markers: list[
            Flag
        ] = []  # List of Flag instances (InjectionFlag, WashFlag, SpikeFlag)

        # Auto-marker storage - system-calculated markers (wash deadline, etc.)
        self._auto_markers: list[AutoMarker] = []

        # Flag selection state (for keyboard movement)
        # Can select either user-placed flags OR auto-markers
        self._selected_marker_type = None  # 'flag' or 'auto_marker'
        self._selected_marker_idx = None
        self._flag_highlight_ring = None
        self._selected_flag_channel = "a"  # Default to Channel A

        # Injection alignment state
        self._injection_reference_time = None
        self._injection_reference_channel = None
        self._injection_alignment_line = None
        self._injection_snap_tolerance = 10.0  # Seconds

        # Contact time timer overlay
        self._contact_timer_overlay = None  # Text item for contact time display
        self._contact_timer_start_time = None  # When contact time started
        self._contact_timer_duration = None  # Total contact duration (seconds)
        self._contact_timer_position = (20, 20)  # Default top-left position in pixels
        self._contact_timer_dragging = False
        self._contact_timer_drag_offset = (0, 0)

        # Install keyboard event filter for flag movement
        self._setup_keyboard_event_filter()

    def _setup_keyboard_event_filter(self):
        """Install event filter on main window to capture keyboard events for flag movement."""

        class KeyboardEventFilter(QObject):
            def __init__(self, flag_mgr):
                super().__init__()
                self.flag_mgr = flag_mgr

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    # Check if a flag is selected
                    if self.flag_mgr._selected_marker_idx is not None:
                        key = event.key()

                        # Arrow keys move flag
                        if key == Qt.Key.Key_Left:
                            self.flag_mgr.move_selected_flag(-1)
                            return True
                        elif key == Qt.Key.Key_Right:
                            self.flag_mgr.move_selected_flag(1)
                            return True
                        elif key == Qt.Key.Key_Escape:
                            self.flag_mgr.deselect_flag()
                            return True

                return super().eventFilter(obj, event)

        self._keyboard_filter = KeyboardEventFilter(self)
        self.app.main_window.installEventFilter(self._keyboard_filter)
        logger.debug("✓ FlagManager: Keyboard event filter installed")

    def show_flag_type_menu(self, event, channel: str, time_val: float, spr_val: float):
        """Show dropdown menu to select flag type.

        Args:
            event: Mouse event
            channel: Channel identifier ('a', 'b', 'c', 'd')
            time_val: Time position for flag
            spr_val: SPR value at flag position
        """
        menu = QMenu()

        # Create flag type actions
        injection_action = QAction("▲ Injection", menu)
        injection_action.triggered.connect(
            lambda: self.add_flag_marker(channel, time_val, spr_val, "injection")
        )

        wash_action = QAction("■ Wash", menu)
        wash_action.triggered.connect(
            lambda: self.add_flag_marker(channel, time_val, spr_val, "wash")
        )

        spike_action = QAction("★ Spike", menu)
        spike_action.triggered.connect(
            lambda: self.add_flag_marker(channel, time_val, spr_val, "spike")
        )

        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)

        # Show menu at cursor position
        menu.exec(QCursor.pos())

    def select_flag_channel_visual(self, channel: str):
        """Select a channel for flagging and update visual highlighting.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        # Store the selected channel
        self._selected_flag_channel = channel

        # Update visual highlighting through UI
        self.app.main_window._on_flag_channel_selected(channel)

    def add_flag_marker(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a visual flag marker to the cycle graph.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            time_val: Time position for flag
            spr_val: SPR value at flag position
            flag_type: Type of flag ('injection', 'wash', 'spike')
        """
        # Create Flag domain model instance (determines appearance from type)
        is_reference = False

        # INJECTION ALIGNMENT LOGIC
        if flag_type == "injection":
            if self._injection_reference_time is None:
                # First injection - set as reference
                is_reference = True
                self._injection_reference_time = time_val
                self._injection_reference_channel = channel

                # Create vertical alignment line on cycle graph
                self._injection_alignment_line = pg.InfiniteLine(
                    pos=time_val,
                    angle=90,  # Vertical
                    pen=pg.mkPen(color=(255, 50, 50, 100), width=2, style=Qt.PenStyle.DashLine),
                    movable=False,
                    label="Injection Reference",
                )
                self.app.main_window.cycle_of_interest_graph.addItem(self._injection_alignment_line)

                logger.info(
                    f"✓ Injection reference set at t={time_val:.2f}s (Channel {channel.upper()})"
                )
            else:
                # Subsequent injection - ALWAYS align channel data to reference
                time_diff = time_val - self._injection_reference_time

                # Shift this channel's data to align with reference
                shift_amount = -time_diff  # Negative because we shift left to align
                self.app._channel_time_shifts[channel] = shift_amount

                logger.info(
                    f"→ Aligning Channel {channel.upper()}: shifting {shift_amount:+.2f}s to match reference"
                )

                # Export time shift to recording metadata
                if self.app.recording_mgr.is_recording:
                    self.app.recording_mgr.update_metadata(
                        f"channel_{channel}_time_shift", shift_amount
                    )

                # Trigger graph update to show shifted data
                self.app._update_cycle_of_interest_graph()

                # Snap flag marker to reference position
                time_val = self._injection_reference_time

        # Create Flag instance using factory
        flag = create_flag(
            flag_type=flag_type,
            channel=channel.upper(),  # Ensure uppercase A/B/C/D
            time=time_val,
            spr=spr_val,
            is_reference=is_reference,  # Only used for InjectionFlag
        )

        # Create visual marker using flag's appearance properties
        # Thicker white outline for better contrast against graph background
        marker = pg.ScatterPlotItem(
            [flag.time],
            [flag.spr],
            symbol=flag.marker_symbol,
            size=flag.marker_size,
            brush=pg.mkBrush(flag.marker_color),
            pen=pg.mkPen("#FFFFFF", width=3),  # Thicker white outline
        )

        # Add marker to graph
        self.app.main_window.cycle_of_interest_graph.addItem(marker)

        # Store marker reference in Flag instance
        flag.marker = marker

        # Add to flag list
        self._flag_markers.append(flag)

        # Export flag to recording manager
        if self.app.recording_mgr.is_recording:
            import datetime as dt

            flag_export_data = flag.to_export_dict()
            timestamp_raw = time.time()
            flag_export_data["timestamp"] = dt.datetime.fromtimestamp(timestamp_raw).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            self.app.recording_mgr.add_flag(flag_export_data)

        logger.info(
            f"🚩 {flag_type.capitalize()} flag added: Channel {channel.upper()} at t={time_val:.2f}s"
        )

    def remove_flag_near_click(self, time_clicked: float, spr_clicked: float):
        """Remove flag marker near the click position using 2D distance.

        Args:
            time_clicked: Time coordinate of click
            spr_clicked: SPR coordinate of click
        """
        if not self._flag_markers:
            return

        # Find flag closest to click position using 2D distance
        min_distance = float("inf")
        closest_flag_idx = None

        # Get view range for normalization
        view_range = self.app.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag.time - time_clicked) / time_range
            spr_dist = abs(flag.spr - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_flag_idx = idx

        # Remove the closest flag if within tolerance (2% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.02:
            flag = self._flag_markers[closest_flag_idx]

            # Remove from graph
            self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)

            # If this was the selected flag, remove the highlight ring
            if closest_flag_idx == self._selected_flag_idx:
                if self._flag_highlight_ring is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(
                        self._flag_highlight_ring
                    )
                    self._flag_highlight_ring = None
                self._selected_flag_idx = None

            # Remove from storage
            self._flag_markers.pop(closest_flag_idx)

            # If we removed an injection flag, check if we need to clear alignment
            if isinstance(flag, InjectionFlag):
                # Count remaining injection flags
                remaining_injections = [
                    f for f in self._flag_markers if isinstance(f, InjectionFlag)
                ]
                if len(remaining_injections) == 0:
                    # No more injections - clear alignment line
                    if self._injection_alignment_line is not None:
                        self.app.main_window.cycle_of_interest_graph.removeItem(
                            self._injection_alignment_line
                        )
                        self._injection_alignment_line = None
                    self._injection_reference_time = None
                    logger.info("✓ Injection alignment cleared")

            logger.info(
                f"🚩 {flag.flag_type.capitalize()} flag removed: Channel {flag.channel.upper()}"
            )

    def try_select_flag_for_movement(self, time_clicked: float, spr_clicked: float):
        """Check if click is near a flag or auto-marker and select it for keyboard movement.

        Searches both user-placed flags and auto-calculated markers in order of proximity.
        """
        min_distance = float("inf")
        closest_flag_idx = None
        closest_type = None

        # Get view range for normalization
        view_range = self.app.main_window.cycle_of_interest_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        # Check user-placed flags
        if self._flag_markers:
            for idx, flag in enumerate(self._flag_markers):
                # Calculate normalized 2D distance
                time_dist = abs(flag.time - time_clicked) / time_range
                spr_dist = abs(flag.spr - spr_clicked) / spr_range
                distance = np.sqrt(time_dist**2 + spr_dist**2)

                if distance < min_distance:
                    min_distance = distance
                    closest_flag_idx = idx
                    closest_type = "flag"

        # Check auto-markers (only time component matters for vertical lines)
        if self._auto_markers:
            for idx, auto_marker in enumerate(self._auto_markers):
                if not auto_marker.is_selectable:
                    continue

                # For vertical lines, only check time distance
                time_dist = abs(auto_marker.time - time_clicked) / time_range
                distance = time_dist  # Vertical line: only time matters

                if distance < min_distance:
                    min_distance = distance
                    closest_flag_idx = idx
                    closest_type = "auto_marker"

        # Select marker if within tolerance (3% of screen diagonal)
        if closest_flag_idx is not None and min_distance < 0.03:
            self._selected_marker_type = closest_type
            self._selected_marker_idx = closest_flag_idx

            if closest_type == "flag":
                flag = self._flag_markers[closest_flag_idx]
                self._highlight_selected_flag(closest_flag_idx)
                logger.info(
                    f"🎯 Selected {flag.flag_type} flag (use arrow keys ← → to move, ESC to deselect)"
                )
            else:
                auto_marker = self._auto_markers[closest_flag_idx]
                self._highlight_selected_marker(closest_flag_idx)
                logger.info(
                    f"🎯 Selected {auto_marker.label} (use arrow keys ← → to adjust, ESC to deselect)"
                )

    def _highlight_selected_flag(self, flag_idx: int):
        """Highlight the selected flag with a yellow ring."""
        # Remove previous highlight if any
        if self._flag_highlight_ring is not None:
            self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)

        flag = self._flag_markers[flag_idx]

        # Create a ring around the selected flag
        self._flag_highlight_ring = pg.ScatterPlotItem(
            [flag.time],
            [flag.spr],
            symbol="o",
            size=25,
            pen=pg.mkPen("y", width=3),  # Yellow ring
            brush=None,
        )
        self.app.main_window.cycle_of_interest_graph.addItem(self._flag_highlight_ring)

    def _highlight_selected_marker(self, auto_marker_idx: int):
        """Highlight the selected auto-marker with a brightened line."""
        # Remove previous highlight if any
        if self._flag_highlight_ring is not None:
            self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)

        auto_marker = self._auto_markers[auto_marker_idx]

        # Brighten the InfiniteLine by updating its pen
        if auto_marker.marker is not None:
            auto_marker.marker.setPen(pg.mkPen(auto_marker.color, width=3))

        # Create a vertical highlight at the marker's time position
        from PySide6.QtCore import Qt

        self._flag_highlight_ring = pg.InfiniteLine(
            pos=auto_marker.time,
            angle=90,
            pen=pg.mkPen("y", width=4, style=Qt.PenStyle.SolidLine),  # Yellow solid highlight
        )
        self.app.main_window.cycle_of_interest_graph.addItem(self._flag_highlight_ring)

    def move_selected_flag(self, direction: int):
        """Move the selected flag or auto-marker left (-1) or right (+1) by one second.

        Args:
            direction: -1 for left, +1 for right (±1 second per press)
        """
        # Handle auto-marker movement
        if self._selected_marker_type == "auto_marker":
            if self._selected_marker_idx is None or self._selected_marker_idx >= len(
                self._auto_markers
            ):
                return

            auto_marker = self._auto_markers[self._selected_marker_idx]

            # Move by ±1 second
            new_time = auto_marker.time + direction

            # Prevent moving before t=0
            if new_time < 0:
                new_time = 0

            # Update marker position
            if auto_marker.marker is not None:
                auto_marker.marker.setPos(new_time)

            auto_marker.time = new_time

            # Update highlight
            self._highlight_selected_marker(self._selected_marker_idx)

            logger.info(f"→ Moved {auto_marker.label}: {new_time:.1f}s")
            return

        # Handle user-placed flag movement
        if self._selected_marker_type != "flag":
            return

        if self._selected_marker_idx is None or self._selected_marker_idx >= len(
            self._flag_markers
        ):
            return

        flag = self._flag_markers[self._selected_marker_idx]
        channel = flag.channel

        # Get DISPLAY data (rebased time)
        cycle_time_raw = self.app.buffer_mgr.cycle_data[channel].time
        cycle_spr_raw = self.app.buffer_mgr.cycle_data[channel].spr

        if len(cycle_time_raw) < 2:
            return

        # Match display logic: skip first point and rebase
        first_time = cycle_time_raw[1]
        cycle_time_display = cycle_time_raw[1:] - first_time
        cycle_spr_display = cycle_spr_raw[1:]

        # Find current flag position in data array
        current_idx = np.argmin(np.abs(cycle_time_display - flag.time))

        # Move to adjacent data point
        new_idx = current_idx + direction
        new_idx = max(0, min(len(cycle_time_display) - 1, new_idx))  # Clamp to valid range

        # Update flag position
        new_time = cycle_time_display[new_idx]
        new_spr = cycle_spr_display[new_idx]

        # Remove old marker
        self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)

        # Create new marker at new position using flag's appearance properties
        # Thicker white outline for better contrast
        new_marker = pg.ScatterPlotItem(
            [new_time],
            [new_spr],
            symbol=flag.marker_symbol,
            size=flag.marker_size,
            brush=pg.mkBrush(flag.marker_color),
            pen=pg.mkPen("#FFFFFF", width=3),  # Thicker white outline
        )
        self.app.main_window.cycle_of_interest_graph.addItem(new_marker)

        # Update flag instance (mutable dataclass)
        flag.time = new_time
        flag.spr = new_spr
        flag.marker = new_marker

        # Update highlight ring position
        self._highlight_selected_flag(self._selected_flag_idx)

        # If this is an injection flag and NOT the reference, recalculate alignment
        if isinstance(flag, InjectionFlag) and self._injection_reference_time is not None:
            if flag.channel != self._injection_reference_channel:
                time_diff = new_time - self._injection_reference_time
                shift_amount = -time_diff
                self.app._channel_time_shifts[channel] = shift_amount

                # Export updated time shift to recording metadata
                if self.app.recording_mgr.is_recording:
                    self.app.recording_mgr.update_metadata(
                        f"channel_{channel}_time_shift", shift_amount
                    )

                self.app._update_cycle_of_interest_graph()
                logger.info(
                    f"→ Moved & realigned Channel {channel.upper()}: shift={shift_amount:+.2f}s"
                )
            else:
                # Moving the reference flag - update reference time
                old_ref = self._injection_reference_time
                self._injection_reference_time = new_time

                # Update alignment line
                if self._injection_alignment_line is not None:
                    self._injection_alignment_line.setPos(new_time)

                logger.info(f"→ Moved reference flag: {old_ref:.2f}s → {new_time:.2f}s")

    def deselect_flag(self):
        """Deselect currently selected flag."""
        if self._flag_highlight_ring is not None:
            self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
            self._flag_highlight_ring = None

        self._selected_marker_type = None
        self._selected_marker_idx = None
        logger.debug("Marker deselected")

    def create_auto_marker(self, marker_type: str, time: float, label: str, color: str):
        """Create an auto-calculated marker on the cycle graph.

        Args:
            marker_type: Type of marker ('wash_deadline', 'injection_deadline', etc.)
            time: Position on timeline (seconds)
            label: Display label (e.g., '⏱ Wash Due')
            color: Color code (e.g., '#FF9500')

        Returns:
            AutoMarker instance, or None if failed
        """
        try:
            if not hasattr(self.app.main_window, "cycle_of_interest_graph"):
                return None

            # Create vertical line marker
            from PySide6.QtCore import Qt

            visual_marker = pg.InfiniteLine(
                pos=time,
                angle=90,  # Vertical line
                pen=pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine),
                label={
                    "text": label,
                    "color": color,
                    "fill": (*self._hex_to_rgb(color), 100),
                    "movable": False,
                },
            )

            # Add to graph
            self.app.main_window.cycle_of_interest_graph.addItem(visual_marker)

            # Create AutoMarker instance
            auto_marker = AutoMarker(
                marker_type=marker_type,
                time=time,
                label=label,
                color=color,
                marker=visual_marker,
                is_selectable=True,
            )

            self._auto_markers.append(auto_marker)
            logger.info(f"✓ Created auto-marker: {label} at t={time:.1f}s")
            return auto_marker

        except Exception as e:
            logger.debug(f"Could not create auto-marker: {e}")
            return None

    def clear_auto_markers(self):
        """Remove all auto-calculated markers from graph."""
        try:
            for auto_marker in self._auto_markers:
                if auto_marker.marker is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(auto_marker.marker)
            self._auto_markers.clear()
            logger.debug("✓ Auto-markers cleared")
        except Exception as e:
            logger.debug(f"Could not clear auto-markers: {e}")

    def create_contact_timer_overlay(self, duration: float):
        """Create draggable contact time timer overlay on cycle graph.

        Args:
            duration: Contact time duration in seconds
        """
        try:
            if not hasattr(self.app.main_window, "cycle_of_interest_graph"):
                return

            import time as time_module

            # Store timer state
            self._contact_timer_start_time = time_module.time()
            self._contact_timer_duration = duration

            # Create text item with large, bold, easy-to-read font
            self._contact_timer_overlay = pg.TextItem(
                text=f"⏱ 0s / {duration:.0f}s",
                color="#000000",  # Black text
                anchor=(0, 0),  # Anchor to top-left
                fill=pg.mkBrush(255, 255, 200, 200),  # Light yellow background, semi-transparent
            )

            # Set large, bold font
            font = self._contact_timer_overlay.font()
            font.setPointSize(14)
            font.setBold(True)
            font.setFamily("Monospace")
            self._contact_timer_overlay.setFont(font)

            # Add shadow/outline for better visibility
            self._contact_timer_overlay.setDefault()

            # Position at saved location (top-left by default)
            vb = self.app.main_window.cycle_of_interest_graph.plotItem.vb
            view_rect = vb.viewRect()

            # Convert pixel coordinates to data coordinates
            pixel_pos = self._contact_timer_position
            scene_pos = vb.mapViewToScene(
                view_rect.topLeft()
            ) + self.app.main_window.cycle_of_interest_graph.mapFromScene(
                vb.mapViewToScene(view_rect.topLeft())
            )

            self._contact_timer_overlay.setPos(pixel_pos[0], pixel_pos[1])

            # Add to graph
            self.app.main_window.cycle_of_interest_graph.addItem(self._contact_timer_overlay)

            logger.info(f"✓ Contact timer created: {duration:.0f}s")

        except Exception as e:
            logger.debug(f"Could not create contact timer overlay: {e}")

    def update_contact_timer_display(self):
        """Update contact timer overlay with current elapsed/remaining time.

        Should be called every second during contact time.
        """
        if (
            self._contact_timer_overlay is None
            or self._contact_timer_start_time is None
            or self._contact_timer_duration is None
        ):
            return

        try:
            import time as time_module

            # Calculate elapsed time
            elapsed = time_module.time() - self._contact_timer_start_time

            # Cap at duration (don't go over)
            elapsed = min(elapsed, self._contact_timer_duration)

            # Update text with elapsed / total
            self._contact_timer_overlay.setText(
                f"⏱ {elapsed:.0f}s / {self._contact_timer_duration:.0f}s"
            )

        except Exception as e:
            logger.debug(f"Could not update contact timer: {e}")

    def clear_contact_timer_overlay(self):
        """Remove and clean up contact timer overlay."""
        try:
            if self._contact_timer_overlay is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(self._contact_timer_overlay)
            self._contact_timer_overlay = None
            self._contact_timer_start_time = None
            self._contact_timer_duration = None
            logger.debug("✓ Contact timer cleared")
        except Exception as e:
            logger.debug(f"Could not clear contact timer: {e}")

    def make_timer_draggable(self):
        """Enable dragging for the contact timer overlay.

        Installs mouse event handler on the timer text item.
        """
        if self._contact_timer_overlay is None:
            return

        # Store reference to flag manager for closure
        flag_mgr = self

        class DraggableTimerHandler:
            def __init__(self, timer_item):
                self.timer_item = timer_item
                self.dragging = False
                self.drag_offset = (0, 0)

            def mouseDragEvent(self, ev):
                """Handle mouse drag on timer."""
                if ev.isStart():
                    self.dragging = True
                    self.drag_offset = (
                        ev.pos().x() - self.timer_item.pos().x(),
                        ev.pos().y() - self.timer_item.pos().y(),
                    )
                elif ev.isFinish():
                    self.dragging = False
                    # Save new position
                    flag_mgr._contact_timer_position = (
                        int(self.timer_item.pos().x()),
                        int(self.timer_item.pos().y()),
                    )
                    logger.info(f"Timer position saved: {flag_mgr._contact_timer_position}")
                else:
                    # Move timer with mouse
                    new_x = ev.pos().x() - self.drag_offset[0]
                    new_y = ev.pos().y() - self.drag_offset[1]
                    self.timer_item.setPos(new_x, new_y)

        # Attach custom mouse handler
        try:
            original_mouseDrag = self._contact_timer_overlay.mouseDragEvent
            handler = DraggableTimerHandler(self._contact_timer_overlay)
            self._contact_timer_overlay.mouseDragEvent = handler.mouseDragEvent
            logger.debug("✓ Timer made draggable")
        except Exception as e:
            logger.debug(f"Could not make timer draggable: {e}")

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def clear_all_flags(self):
        """Clear all flags and auto-markers when user clicks Clear Flags button."""
        logger.info("[FlagManager] Clearing all flags and markers")
        try:
            # Remove all visual markers from graph
            for flag in self._flag_markers:
                if flag.marker is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)

            self._flag_markers.clear()

            # Remove highlight ring if present
            if self._flag_highlight_ring is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
                self._flag_highlight_ring = None

            # Clear selection
            self._selected_marker_type = None
            self._selected_marker_idx = None

            # Clear auto-markers
            self.clear_auto_markers()

            # Clear injection alignment line and references
            self._injection_reference_time = None
            self._injection_reference_channel = None
            if self._injection_alignment_line is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(
                    self._injection_alignment_line
                )
                self._injection_alignment_line = None

            # Reset channel time shifts to default
            if hasattr(self.app, "_channel_time_shifts"):
                self.app._channel_time_shifts = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}

            logger.info("✓ All flags cleared and timing reset")
        except Exception as e:
            logger.error(f"[ERROR] Error clearing flags: {e}", exc_info=True)

    def clear_flags_for_new_cycle(self):
        """Clear all flags and auto-markers when a cycle ends to start fresh for the next cycle.

        This also resets channel time shifts to default (live sensorgram timing).
        Flags are cycle-specific, so timing adjustments should not carry over.
        """
        try:
            # Remove all flag markers from graph
            for flag in self._flag_markers:
                if flag.marker is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)
            self._flag_markers.clear()

            # Remove flag highlight ring if present
            if self._flag_highlight_ring is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
                self._flag_highlight_ring = None

            # Clear flag selection
            self._selected_marker_type = None
            self._selected_marker_idx = None

            # Clear auto-markers
            self.clear_auto_markers()

            # Clear contact timer overlay
            self.clear_contact_timer_overlay()

            # Clear injection alignment reference and line
            self._injection_reference_time = None
            self._injection_reference_channel = None
            if self._injection_alignment_line is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(
                    self._injection_alignment_line
                )
                self._injection_alignment_line = None

            # Reset channel time shifts to default (live sensorgram timing)
            # Flags are cycle-specific, so timing adjustments should not persist across cycles
            if hasattr(self.app, "_channel_time_shifts"):
                self.app._channel_time_shifts = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}

            logger.debug("Flags and timing cleared for new cycle")
        except Exception as e:
            logger.debug(f"Error clearing flags for new cycle: {e}")

    def get_flag_data_for_export(self) -> list[dict]:
        """Get all flag data in format suitable for export.

        Returns:
            List of flag dicts with channel, time, spr, type
        """
        return [flag.to_export_dict() for flag in self._flag_markers]
