"""Flag Manager - Unified flag marker management for all contexts.

ARCHITECTURE LAYER: Manager (Business Logic)

This manager is the SINGLE SOURCE OF TRUTH for all flags in the application.
Flags have a 'context' field: 'live' (acquisition) or 'edits' (post-hoc).

DESIGN PRINCIPLE:
- During LIVE acquisition, flags are placed by SOFTWARE only (injection detection,
  cycle events). Users cannot manually add flags on the live graph — the focus
  should remain on acquisition, not annotation.
- In the EDITS tab, users CAN add, adjust (arrow-key nudge with data snap),
  and delete flags. This is where precise flag placement happens.
- Both contexts share the same Flag domain model, visual appearance, and
  selection/movement behavior (yellow ring highlight, data-point snapping).

This manager encapsulates all flag-related logic:
- Adding/removing flag markers on cycle graph (live) and edits graph
- Flag type management (injection, wash, spike)
- Injection alignment and channel time shifts (live context)
- Flag selection and keyboard movement (both contexts)
- Auto-calculated markers (wash deadline, etc.)
- Exporting flags to recording manager / Excel
- Clearing flags for new cycles

NOTE: Contact-time countdown display was removed from this manager.
It now lives in QueueSummaryWidget (queue table STATUS cell).

DEPENDENCIES:
- main_window.cycle_of_interest_graph (live UI component)
- main_window.edits_primary_graph (edits UI component)
- recording_mgr (for export)
- buffer_mgr (for cycle data)

USAGE:
    flag_mgr = FlagManager(app_instance)
    # Software places live flags:
    flag_mgr.add_flag_marker(channel, time, spr, 'injection')
    # User places edits flags:
    flag_mgr.add_edits_flag(channel, time, spr, 'injection')
    flag_mgr.clear_all_flags()  # Only clears live flags
    flag_mgr.clear_edits_flags()  # Only clears edits flags
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
from affilabs.domain.timeline import (
    EventContext,
    InjectionFlag as TLInjectionFlag,
    WashFlag as TLWashFlag,
    SpikeFlag as TLSpikeFlag,
)
from affilabs.ui_styles import hex_to_rgb
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

        # Edits-context state
        self._edits_highlight_ring = None
        self._edits_keyboard_filter = None

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
        """Select a channel for timing adjustment and update visual highlighting.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        # Store the selected channel
        self._selected_flag_channel = channel

        # Update visual highlighting through UI
        self.app.main_window._on_timing_channel_selected(channel)

    def add_flag_marker(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a visual flag marker to the cycle graph (software-placed, live context).

        This is called by the software during acquisition (e.g., injection detection,
        wash events). Users cannot manually add flags on the live graph — they can
        adjust flags in the Edits tab.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            time_val: Time position for flag
            spr_val: SPR value at flag position
            flag_type: Type of flag ('injection', 'wash', 'spike')
        """
        # Guard: auto-detection can fire on data from before cycle start,
        # producing a negative display time. Clamp to 0 rather than crash.
        if time_val < 0:
            logger.debug(
                f"Flag time clamped: {time_val:.3f}s → 0.0s "
                f"(channel={channel}, type={flag_type})"
            )
            time_val = 0.0

        # Create Flag instance using factory
        flag = create_flag(
            flag_type=flag_type,
            channel=channel.upper(),  # Ensure uppercase A/B/C/D
            time=time_val,
            spr=spr_val,
            is_reference=False,
        )

        if flag_type == "injection":
            logger.info(
                f"✓ Injection flag placed at t={time_val:.2f}s (Channel {channel.upper()})"
            )

            # Hide "Flat baseline = ready for injection" hint
            try:
                lbl = getattr(self.app.main_window, '_baseline_hint_label', None)
                if lbl is not None and lbl.isVisible():
                    lbl.setVisible(False)
            except Exception:
                pass

        # Injection flags: thin dashed InfiniteLine. Other flags: scatter marker.
        if flag_type == "injection":
            marker = pg.InfiniteLine(
                pos=flag.time,
                angle=90,
                movable=False,
                pen=pg.mkPen(color=flag.marker_color, width=1, style=Qt.PenStyle.DashLine),
            )
        else:
            marker = pg.ScatterPlotItem(
                [flag.time],
                [flag.spr],
                symbol=flag.marker_symbol,
                size=flag.marker_size,
                brush=pg.mkBrush(flag.marker_color),
                pen=pg.mkPen("#FFFFFF", width=2),
            )
        self.app.main_window.cycle_of_interest_graph.addItem(marker)
        flag.marker = marker

        # Add to flag list
        self._flag_markers.append(flag)

        # Also add to unified timeline stream
        self._add_to_timeline_stream(channel, time_val, spr_val, flag_type, False)

        # Flash marker on placement for visibility (scatter-only — InfiniteLines don't support setSize)
        if flag_type != "injection":
            try:
                from PySide6.QtCore import QTimer as _QT
                original_size = flag.marker_size
                _flash_sizes = [original_size * 2.0, original_size * 1.5, original_size]
                _flash_step = [0]
                _flash_timer = _QT()
                _flash_timer.setInterval(100)
                def _flash():
                    try:
                        idx = _flash_step[0]
                        if idx < len(_flash_sizes):
                            marker.setSize(_flash_sizes[idx])
                            _flash_step[0] += 1
                        else:
                            _flash_timer.stop()
                    except Exception:
                        _flash_timer.stop()
                _flash_timer.timeout.connect(_flash)
                _flash_timer.start()
                flag._flash_timer = _flash_timer
            except Exception:
                pass

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

    def _add_to_timeline_stream(self, channel: str, time_val: float, spr_val: float, flag_type: str, is_reference: bool = False, context: EventContext = EventContext.LIVE) -> None:
        """Add a flag event to the unified timeline stream (parallel to _flag_markers).

        Called internally by add_flag_marker (LIVE) and add_edits_flag (EDITS).
        Keeps timeline in sync without touching existing flag logic.

        Args:
            channel: Channel identifier (upper or lower case)
            time_val: Time position for flag
            spr_val: SPR value at flag position
            flag_type: Type of flag ('injection', 'wash', 'spike')
            is_reference: Whether this is the reference injection
            context: EventContext.LIVE or EventContext.EDITS
        """
        try:
            import datetime as dt

            recording_mgr = self.app.recording_mgr
            if not recording_mgr.is_recording:
                return

            stream = recording_mgr.get_timeline_stream()
            ch = channel.upper()

            if flag_type == "injection":
                event = TLInjectionFlag(
                    time=time_val,
                    channel=ch,
                    context=context,
                    created_at=dt.datetime.now(),
                    spr_value=spr_val,
                    is_reference=is_reference,
                )
            elif flag_type == "wash":
                event = TLWashFlag(
                    time=time_val,
                    channel=ch,
                    context=context,
                    created_at=dt.datetime.now(),
                    wash_type="buffer_change",
                )
            elif flag_type == "spike":
                event = TLSpikeFlag(
                    time=time_val,
                    channel=ch,
                    context=context,
                    created_at=dt.datetime.now(),
                )
            else:
                return  # Unknown type — skip

            stream.add_event(event)

        except Exception as e:
            logger.warning(f"Timeline stream update failed (non-critical): {e}")

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

            # Remove from cycle graph only
            if flag.marker is not None:
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

        if isinstance(flag, InjectionFlag):
            # InfiniteLine has no y-position — highlight with a bright yellow vertical line
            self._flag_highlight_ring = pg.InfiniteLine(
                pos=flag.time,
                angle=90,
                pen=pg.mkPen("y", width=3, style=Qt.PenStyle.DashLine),
                movable=False,
            )
        else:
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

        # Get cycle data and compute display time matching Active Cycle graph
        # Active Cycle uses: display_time = raw_time - start_cursor_raw
        cycle_time_raw = self.app.buffer_mgr.cycle_data[channel].time
        cycle_spr_raw = self.app.buffer_mgr.cycle_data[channel].spr

        if len(cycle_time_raw) == 0:
            return

        # Match ui_update_helpers.py: rebase to start cursor position (raw coords)
        from affilabs.core.experiment_clock import TimeBase

        start_cursor_display = self.app.main_window.full_timeline_graph.start_cursor.value()
        start_time_raw = self.app.clock.convert(
            start_cursor_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED
        )
        cycle_time_display = cycle_time_raw - start_time_raw
        cycle_spr_display = cycle_spr_raw

        # Find current flag position in data array
        current_idx = np.argmin(np.abs(cycle_time_display - flag.time))

        # Move to adjacent data point
        new_idx = current_idx + direction
        new_idx = max(0, min(len(cycle_time_display) - 1, new_idx))  # Clamp to valid range

        # Update flag position
        new_time = cycle_time_display[new_idx]
        new_spr = cycle_spr_display[new_idx]

        # Remove old marker from cycle graph
        if flag.marker is not None:
            self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)

        # Create new marker at new position
        if isinstance(flag, InjectionFlag):
            # Injection flags: vertical InfiniteLine only, no scatter dot
            is_ref = getattr(flag, "is_reference", False)
            label_text = "" if is_ref else f"  {flag.channel}"
            line_style = Qt.PenStyle.SolidLine if is_ref else Qt.PenStyle.DotLine
            line_width = 2 if is_ref else 1
            new_marker = pg.InfiniteLine(
                pos=new_time,
                angle=90,
                pen=pg.mkPen(color="#FF3B30", width=line_width, style=line_style),
                movable=False,
                label=label_text,
                labelOpts={
                    "color": "#FFFFFF",
                    "position": 0.97 if is_ref else 0.90,
                    "fill": pg.mkBrush(255, 59, 48, 200),
                    "border": pg.mkPen("#FF3B30", width=0),
                },
            )
        else:
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
                label=label,
                labelOpts={
                    "color": color,
                    "fill": (*hex_to_rgb(color), 100),
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
            logger.debug(f"Auto-marker: {label} at t={time:.1f}s")
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

    def clear_all_flags(self):
        """Clear all live flags and auto-markers when user clicks Clear Flags button.

        Preserves edits-context flags — those are managed separately.
        """
        logger.info("[FlagManager] Clearing all live flags and markers")
        try:
            # Remove only LIVE visual markers from cycle graph
            live_flags = [f for f in self._flag_markers if f.context == "live"]
            for flag in live_flags:
                if flag.marker is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)
                self._flag_markers.remove(flag)

            # Remove highlight ring if present
            if self._flag_highlight_ring is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
                self._flag_highlight_ring = None

            # Clear selection
            self._selected_marker_type = None
            self._selected_marker_idx = None

            # Clear auto-markers
            self.clear_auto_markers()

            logger.info("✓ All flags cleared")
        except Exception as e:
            logger.error(f"[ERROR] Error clearing flags: {e}", exc_info=True)

    def clear_flags_for_new_cycle(self):
        """Clear all live flags and auto-markers when a cycle ends to start fresh.

        Preserves edits-context flags. Resets channel time shifts.
        """
        try:
            # Remove only LIVE flag markers from cycle graph
            live_flags = [f for f in self._flag_markers if f.context == "live"]
            for flag in live_flags:
                if flag.marker is not None:
                    self.app.main_window.cycle_of_interest_graph.removeItem(flag.marker)
                self._flag_markers.remove(flag)

            # Remove flag highlight ring if present
            if self._flag_highlight_ring is not None:
                self.app.main_window.cycle_of_interest_graph.removeItem(self._flag_highlight_ring)
                self._flag_highlight_ring = None

            # Clear flag selection
            self._selected_marker_type = None
            self._selected_marker_idx = None

            # Clear auto-markers
            self.clear_auto_markers()

            logger.debug("Flags cleared for new cycle")
        except Exception as e:
            logger.debug(f"Error clearing flags for new cycle: {e}")

    def get_flag_data_for_export(self, context: str | None = None) -> list[dict]:
        """Get all flag data in format suitable for export.

        Args:
            context: If provided, only return flags with this context ('live' or 'edits').
                     If None, return all flags.

        Returns:
            List of flag dicts with channel, time, spr, type, context
        """
        flags = self._flag_markers
        if context:
            flags = [f for f in flags if f.context == context]
        return [flag.to_export_dict() for flag in flags]

    # ── Edits-context flag management ──────────────────────────────────

    def get_edits_flags(self) -> list[Flag]:
        """Return only flags belonging to the edits context."""
        return [f for f in self._flag_markers if f.context == "edits"]

    def get_live_flags(self) -> list[Flag]:
        """Return only flags belonging to the live context."""
        return [f for f in self._flag_markers if f.context == "live"]

    def add_edits_flag(self, channel: str, time_val: float, spr_val: float, flag_type: str):
        """Add a flag in the Edits context (user-placed during post-hoc analysis).

        Args:
            channel: Channel identifier ('A', 'B', 'C', 'D')
            time_val: Time position for flag
            spr_val: SPR value at flag position
            flag_type: Type of flag ('injection', 'wash', 'spike')
        """
        try:
            # Create Flag instance in edits context
            flag = create_flag(
                flag_type=flag_type,
                channel=channel.upper(),
                time=time_val,
                spr=spr_val,
                context="edits",
            )

            # Create visual marker — injection flags use InfiniteLine, others use scatter
            if isinstance(flag, InjectionFlag):
                marker = pg.InfiniteLine(
                    pos=flag.time,
                    angle=90,
                    pen=pg.mkPen(color="#FF3B30", width=2, style=Qt.PenStyle.SolidLine),
                    movable=False,
                    label=f"  {flag.channel}",
                    labelOpts={
                        "color": "#FFFFFF",
                        "position": 0.97,
                        "fill": pg.mkBrush(255, 59, 48, 200),
                        "border": pg.mkPen("#FF3B30", width=0),
                    },
                )
            else:
                marker = pg.ScatterPlotItem(
                    [flag.time],
                    [flag.spr],
                    symbol=flag.marker_symbol,
                    size=flag.marker_size,
                    brush=pg.mkBrush(flag.marker_color),
                    pen=pg.mkPen("#FFFFFF", width=3),
                )
                marker.setZValue(100)  # Draw on top of data

            # Add to Edits graph
            edits_graph = self._get_edits_graph()
            if edits_graph is not None:
                edits_graph.addItem(marker)

            flag.marker = marker
            self._flag_markers.append(flag)

            # Also add to unified timeline stream with EDITS context
            self._add_to_timeline_stream(channel, time_val, spr_val, flag_type, context=EventContext.EDITS)

            logger.info(
                f"🚩 {flag_type.capitalize()} flag added in Edits: "
                f"Channel {channel.upper()} at t={time_val:.2f}s"
            )

        except Exception as e:
            logger.error(f"Failed to add edits flag: {e}")

    def remove_edits_flag(self, flag_idx_in_edits: int):
        """Remove a flag from the Edits context by its index within edits flags.

        Args:
            flag_idx_in_edits: Index within the edits-only flag list
        """
        edits_flags = self.get_edits_flags()
        if flag_idx_in_edits < 0 or flag_idx_in_edits >= len(edits_flags):
            return

        flag = edits_flags[flag_idx_in_edits]

        # Remove visual marker from Edits graph
        edits_graph = self._get_edits_graph()
        if edits_graph is not None and flag.marker is not None:
            edits_graph.removeItem(flag.marker)

        # Remove highlight if this was selected
        if self._selected_marker_idx is not None:
            selected_edits = [
                i for i, f in enumerate(self._flag_markers) if f.context == "edits"
            ]
            if (
                flag_idx_in_edits < len(selected_edits)
                and selected_edits[flag_idx_in_edits] == self._selected_marker_idx
            ):
                self._remove_edits_highlight()
                self._selected_marker_idx = None
                self._selected_marker_type = None

        # Remove from unified storage
        self._flag_markers.remove(flag)
        logger.info(f"🚩 Removed {flag.flag_type} flag from Edits")

    def select_edits_flag(self, flag_idx_in_edits: int):
        """Select an edits-context flag for keyboard movement/deletion.

        Args:
            flag_idx_in_edits: Index within the edits-only flag list
        """
        edits_flags = self.get_edits_flags()
        if flag_idx_in_edits < 0 or flag_idx_in_edits >= len(edits_flags):
            return

        # Deselect any previously selected edits flag
        self.deselect_edits_flag()

        flag = edits_flags[flag_idx_in_edits]

        # Find the global index in _flag_markers
        global_idx = self._flag_markers.index(flag)
        self._selected_marker_type = "edits_flag"
        self._selected_marker_idx = global_idx

        # Highlight with yellow ring (same as live)
        self._highlight_edits_flag(flag)

        logger.debug(f"Selected {flag.flag_type} flag at t={flag.time:.2f}s in Edits")

    def deselect_edits_flag(self):
        """Deselect currently selected edits flag."""
        if self._selected_marker_type == "edits_flag":
            self._remove_edits_highlight()
            self._selected_marker_type = None
            self._selected_marker_idx = None

    def move_edits_flag(self, direction: int):
        """Move the selected edits flag left (-1) or right (+1).

        Snaps to nearest data point in the edits graph data for accuracy.
        Falls back to ±1 second if no data is available for snapping.

        Args:
            direction: -1 for left, +1 for right
        """
        if self._selected_marker_type != "edits_flag":
            return
        if self._selected_marker_idx is None or self._selected_marker_idx >= len(self._flag_markers):
            return

        flag = self._flag_markers[self._selected_marker_idx]

        # Try to snap to data points in the edits graph
        new_time, new_spr = self._snap_edits_flag_to_data(flag, direction)

        # Remove old marker
        edits_graph = self._get_edits_graph()
        if edits_graph is not None and flag.marker is not None:
            edits_graph.removeItem(flag.marker)

        # Create new marker at new position
        if isinstance(flag, InjectionFlag):
            new_marker = pg.InfiniteLine(
                pos=new_time,
                angle=90,
                pen=pg.mkPen(color="#FF3B30", width=2, style=Qt.PenStyle.SolidLine),
                movable=False,
                label=f"  {flag.channel}",
                labelOpts={
                    "color": "#FFFFFF",
                    "position": 0.97,
                    "fill": pg.mkBrush(255, 59, 48, 200),
                    "border": pg.mkPen("#FF3B30", width=0),
                },
            )
        else:
            new_marker = pg.ScatterPlotItem(
                [new_time],
                [new_spr],
                symbol=flag.marker_symbol,
                size=flag.marker_size,
                brush=pg.mkBrush(flag.marker_color),
                pen=pg.mkPen("#FFFFFF", width=3),
            )
            new_marker.setZValue(100)

        if edits_graph is not None:
            edits_graph.addItem(new_marker)

        # Update flag
        flag.time = new_time
        flag.spr = new_spr
        flag.marker = new_marker

        # Update highlight
        self._remove_edits_highlight()
        self._highlight_edits_flag(flag)

        logger.debug(f"→ Moved edits flag to t={new_time:.2f}s")

    def try_select_edits_flag_near_click(self, time_clicked: float, spr_clicked: float) -> bool:
        """Check if click is near an edits flag and select it.

        Args:
            time_clicked: Time coordinate of click
            spr_clicked: SPR coordinate of click

        Returns:
            True if a flag was selected, False otherwise
        """
        edits_flags = self.get_edits_flags()
        if not edits_flags:
            return False

        edits_graph = self._get_edits_graph()
        if edits_graph is None:
            return False

        # Get view range for normalization
        view_range = edits_graph.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]

        if time_range == 0 or spr_range == 0:
            return False

        min_distance = float("inf")
        closest_idx = None

        for idx, flag in enumerate(edits_flags):
            time_dist = abs(flag.time - time_clicked) / time_range
            spr_dist = abs(flag.spr - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                closest_idx = idx

        # Select if within 3% of screen diagonal (same tolerance as live)
        if closest_idx is not None and min_distance < 0.03:
            self.select_edits_flag(closest_idx)
            return True

        # Clicked empty space — deselect
        self.deselect_edits_flag()
        return False

    def clear_edits_flags(self):
        """Remove all edits-context flags."""
        edits_graph = self._get_edits_graph()
        edits_flags = self.get_edits_flags()

        for flag in edits_flags:
            if edits_graph is not None and flag.marker is not None:
                edits_graph.removeItem(flag.marker)
            self._flag_markers.remove(flag)

        self._remove_edits_highlight()
        if self._selected_marker_type == "edits_flag":
            self._selected_marker_type = None
            self._selected_marker_idx = None

        logger.debug("✓ Edits flags cleared")

    # ── Edits-context private helpers ──────────────────────────────────

    def _get_edits_graph(self):
        """Get the edits primary graph widget, or None if not available."""
        if hasattr(self.app, "main_window") and hasattr(self.app.main_window, "edits_primary_graph"):
            return self.app.main_window.edits_primary_graph
        return None

    def _highlight_edits_flag(self, flag: Flag):
        """Highlight an edits flag with a yellow ring (consistent with live)."""
        edits_graph = self._get_edits_graph()
        if edits_graph is None:
            return

        self._remove_edits_highlight()

        if isinstance(flag, InjectionFlag):
            # InfiniteLine has no y-position — highlight with bright yellow vertical line
            self._edits_highlight_ring = pg.InfiniteLine(
                pos=flag.time,
                angle=90,
                pen=pg.mkPen("y", width=3, style=Qt.PenStyle.DashLine),
                movable=False,
            )
        else:
            self._edits_highlight_ring = pg.ScatterPlotItem(
                [flag.time],
                [flag.spr],
                symbol="o",
                size=25,
                pen=pg.mkPen("y", width=3),  # Yellow ring — same as live
                brush=None,
            )
            self._edits_highlight_ring.setZValue(101)
        edits_graph.addItem(self._edits_highlight_ring)

    def _remove_edits_highlight(self):
        """Remove the edits highlight ring if present."""
        if hasattr(self, "_edits_highlight_ring") and self._edits_highlight_ring is not None:
            edits_graph = self._get_edits_graph()
            if edits_graph is not None:
                try:
                    edits_graph.removeItem(self._edits_highlight_ring)
                except Exception:
                    pass
            self._edits_highlight_ring = None

    def _snap_edits_flag_to_data(self, flag: Flag, direction: int) -> tuple[float, float]:
        """Snap an edits flag to the nearest data point in the given direction.

        Tries to find actual graph data to snap to. Falls back to ±1 second.

        Args:
            flag: The flag to snap
            direction: -1 for left, +1 for right

        Returns:
            Tuple of (new_time, new_spr)
        """
        try:
            edits_graph = self._get_edits_graph()
            if edits_graph is None:
                return flag.time + direction, flag.spr

            # Try to get data from edits graph curves
            edits_tab = getattr(self.app.main_window, "edits_tab", None)
            if edits_tab and hasattr(edits_tab, "edits_graph_curves"):
                # Find the curve for the flag's channel
                channel_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                ch_idx = channel_map.get(flag.channel.upper(), 0)

                if ch_idx < len(edits_tab.edits_graph_curves):
                    curve = edits_tab.edits_graph_curves[ch_idx]
                    x_data, y_data = curve.getData()

                    if x_data is not None and len(x_data) > 0:
                        # Find current index
                        current_idx = np.argmin(np.abs(x_data - flag.time))

                        # Move to adjacent data point
                        new_idx = current_idx + direction
                        new_idx = max(0, min(len(x_data) - 1, new_idx))

                        return float(x_data[new_idx]), float(y_data[new_idx])

        except Exception as e:
            logger.debug(f"Could not snap edits flag to data: {e}")

        # Fallback: move ±1 second
        return flag.time + direction, flag.spr

    def setup_edits_keyboard_filter(self):
        """Install keyboard event filter on the edits graph for flag movement.

        Should be called once when the Edits tab is set up.
        """

        class EditsKeyboardFilter(QObject):
            def __init__(self, flag_mgr):
                super().__init__()
                self.flag_mgr = flag_mgr

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    # Only handle if an edits flag is selected
                    if self.flag_mgr._selected_marker_type != "edits_flag":
                        return False

                    key = event.key()

                    if key == Qt.Key.Key_Left:
                        self.flag_mgr.move_edits_flag(-1)
                        return True
                    elif key == Qt.Key.Key_Right:
                        self.flag_mgr.move_edits_flag(1)
                        return True
                    elif key == Qt.Key.Key_Escape:
                        self.flag_mgr.deselect_edits_flag()
                        return True
                    elif key == Qt.Key.Key_Delete:
                        # Find the flag's edits-local index and remove it
                        if self.flag_mgr._selected_marker_idx is not None:
                            flag = self.flag_mgr._flag_markers[self.flag_mgr._selected_marker_idx]
                            edits_flags = self.flag_mgr.get_edits_flags()
                            if flag in edits_flags:
                                edits_idx = edits_flags.index(flag)
                                self.flag_mgr.remove_edits_flag(edits_idx)
                        return True

                return False

        edits_graph = self._get_edits_graph()
        if edits_graph is not None:
            self._edits_keyboard_filter = EditsKeyboardFilter(self)
            edits_graph.installEventFilter(self._edits_keyboard_filter)
            logger.debug("✓ FlagManager: Edits keyboard event filter installed")
