import PySide6
import pyqtgraph
import numpy as np
from PySide6.QtCore import Signal, Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem
from pyqtgraph import GraphicsLayoutWidget, setConfigOptions, mkPen, InfiniteLine, LinearRegionItem
from copy import deepcopy
import settings
from settings import CH_LIST, UNIT_LIST, STATIC_PLOT, DEV
from utils.logger import logger


class SensorgramGraph(GraphicsLayoutWidget):
    """
    Master/Overview graph for full experiment timeline.

    Purpose:
    - Shows complete timeline of all collected data
    - Yellow/Red cursors mark region of interest for detailed view
    - Gray zone/lines indicate active cycle being recorded
    - Compact layout (20% height) for navigation/context

    Architecture:
    - Part of master-detail layout (paired with SegmentGraph/Cycle of Interest)
    - When cycle starts: gray zone appears, fixed window applied
    - Live data continues updating, cursor auto-follow disabled during cycle
    """
    segment_signal = Signal(float, float, bool)
    shift_values_signal = Signal(dict)  # Signal to emit shift values to display box

    def __init__(self, title_string):
        super(SensorgramGraph, self).__init__()

        self.subsample_threshold = 301
        self.subsample_target = 150
        self.subsampling = False
        self.block_updates = False
        self.unit = 'nm'
        self.unit_factor = UNIT_LIST[self.unit]
        self.updating = False
        self.live_range = 50
        self.static_index = 0
        self.wait_for_reset = False
        self.fixed_window_active = False  # Flag to prevent auto-range when window is fixed

        setConfigOptions(antialias=True)

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, size='13pt')
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setAxisItems()
        self.plot.setLabel('left', text=f'λ ({self.unit})')  # Lambda symbol
        self.plot.setLabel('bottom', text='Time (s)')
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible()

        # Set default Y-axis range for detector (580-660 nm)
        self.plot.setYRange(580, 660, padding=0)

        # Reduce Y-axis tick density for cleaner compact view
        self.plot.getAxis('left').setStyle(maxTickLevel=1)  # Show fewer tick levels

        # Ensure bottom axis has space for label - explicit sizing for visibility
        bottom_axis = self.plot.getAxis('bottom')
        left_axis = self.plot.getAxis('left')
        bottom_axis.setHeight(45)  # Increased space for 'Time (s)' label visibility
        left_axis.setWidth(55)     # Space for Y-axis label

        # Ensure label is visible
        bottom_axis.label.show()
        left_axis.label.show()

        # set up channel data and plots
        self.plots = {}
        self.static = {}
        self.time_data = {}
        self.lambda_data = {}
        for ch in CH_LIST:
            self.plots[ch] = self.plot.plot(pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2), connect='finite')
            self.static[ch] = self.plot.plot(pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2), connect='finite')
        self.latest_time = 0

        self.live = True

        # set vertical cursors: left and right with labels
        self.left_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=mkPen('#333333', width=2),
            movable=True,
            label='Start 0.00s',
            labelOpts={
                'position': 0.95,
                'color': (51, 51, 51),
                'movable': False,
                'fill': (255, 255, 255, 220),
                'anchor': (1.0, 0.5),
                'rotateAxis': (0, 1)
            })

        self.right_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=mkPen('#333333', width=2),
            movable=True,
            label='Stop 0.00s',
            labelOpts={
                'position': 0.95,
                'color': (51, 51, 51),
                'movable': False,
                'fill': (255, 255, 255, 220),
                'anchor': (1.0, 0.5),
                'rotateAxis': (0, 1)
            })

        # set cursor hover color
        self.left_cursor.setHoverPen(mkPen('#666666', width=3))
        self.right_cursor.setHoverPen(mkPen('#666666', width=3))

        self.left_cursor.label.setAngle(-90)
        self.right_cursor.label.setAngle(-90)

        self.plot.addItem(self.left_cursor)
        self.plot.addItem(self.right_cursor)

        # Cycle time markers (can be either shaded region or vertical lines)
        self.cycle_time_region = None
        self.cycle_start_line = None
        self.cycle_end_line = None

        self.left_cursor.sigDragged.connect(self.left_cursor_sig_dragged)
        self.right_cursor.sigDragged.connect(self.right_cursor_sig_dragged)
        self.left_cursor.sigPositionChangeFinished.connect(self.left_cursor_moved)
        self.right_cursor.sigPositionChangeFinished.connect(self.right_cursor_moved)

        # initial position of cursors
        self.left_cursor_pos = 0
        self.right_cursor_pos = 1
        self.set_left(0, emit=False)
        self.set_right(1, emit=False)

    def update_colors(self):
        """Update plot colors when colorblind mode is toggled."""
        for ch in CH_LIST:
            self.plots[ch].setPen(mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2))
            if hasattr(self, 'static') and ch in self.static:
                self.static[ch].setPen(mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2))

    def movable_cursors(self, state):
        self.left_cursor.setMovable(state)
        self.right_cursor.setMovable(state)

    def check_subsample(self, n):
        if n > self.subsample_threshold:
            self.plot.setDownsampling(ds=int(n / self.subsample_target))
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(f"sensorgram subsample factor: {int(n/self.subsample_target)}")

        if self.subsampling:
            if n < (self.subsample_threshold - self.subsample_target):
                self.plot.setDownsampling(ds=False)
                self.subsampling = False
                self.subsample_threshold = 2 * self.subsample_target
                logger.debug("stopped subsampling sensorgram plot")

    def is_updating(self):
        return self.updating

    def update(self, lambda_values, lambda_times):
        try:
            self.updating = True
            static_x_data = None
            static_y_data = None
            static_data = False
            for ch in CH_LIST:
                y_data = deepcopy(lambda_values[ch])
                x_data = deepcopy(lambda_times[ch])
                if ch == 'a':
                    self.check_subsample(len(y_data))
                    if STATIC_PLOT:
                        if (min(len(lambda_values['a']),
                                len(lambda_values['b']),
                                len(lambda_values['c']),
                                len(lambda_values['d']))) > (self.static_index + self.live_range + 5):
                            self.static_index += self.live_range
                            static_data = True
                            # logger.debug(f"len a = {len(y_data)}, len b = {len(lambda_values['b'])}, "
                            #             f"len c = {len(lambda_values['c'])}, len d = {len(lambda_values['d'])}, "
                            #             f"static index = {self.static_index}")
                if static_data:
                    n = max(int(len(y_data) / 2500), 1)
                    static_x_data = x_data[0:(self.static_index + 1):n]
                    static_y_data = y_data[0:(self.static_index + 1):n]
                x_data = x_data[self.static_index:]
                y_data = y_data[self.static_index:]
                if len(y_data) == len(x_data):
                    self.plots[ch].setData(y=y_data, x=x_data)
                    if static_data and (static_y_data is not None):
                        self.static[ch].setData(y=static_y_data, x=static_x_data)
                        logger.debug(f"static sensorgram data plotted")
                    self.time_data[ch] = lambda_times[ch]
                    self.lambda_data[ch] = lambda_values[ch]
                    if len(lambda_times[ch]) > 0:
                        if lambda_times[ch][-1] > self.latest_time:
                            self.latest_time = lambda_times[ch][-1] + 0.01
                else:
                    logger.debug(f"sensorgram data not plottable, y = {y_data}, x = {x_data}")
            # Auto-follow the latest data when live mode is enabled AND fixed window is not active
            if self.live and not self.wait_for_reset and not self.fixed_window_active:
                self.set_right(self.latest_time, update=True)
            elif self.fixed_window_active:
                # Log that we're in fixed window mode - data still updates but cursor doesn't move
                if not hasattr(self, '_logged_fixed_window'):
                    logger.info(f"📊 Fixed window active - live data updating but cursor locked")
                    self._logged_fixed_window = True

            self.wait_for_reset = False
            self.updating = False
        except Exception as e:
            logger.debug(f"Error during sensorgram update: {e}")

    def reset_time(self):
        self.static_index = 0
        self.latest_time = 0
        self.wait_for_reset = True

    def left_cursor_moved(self):
        self.set_left(self.left_cursor.value())

    def right_cursor_moved(self):
        self.set_right(self.right_cursor.value())

    def left_cursor_sig_dragged(self):
        n_pts = len(self.time_data['d']) if 'd' in self.time_data else 0
        if n_pts < 300:
            self.set_left(self.left_cursor.value())
        else:
            if abs(self.left_cursor.value() - self.left_cursor_pos) > (n_pts * 0.005):
                self.set_left(self.left_cursor.value())

    def right_cursor_sig_dragged(self):
        n_pts = len(self.time_data['d']) if 'd' in self.time_data else 0
        if n_pts < 300:
            self.set_right(self.right_cursor.value())
        else:
            if abs(self.right_cursor.value() - self.right_cursor_pos) > (n_pts * 0.005):
                self.set_right(self.right_cursor.value())

    def center_cursors(self):
        l_pos = 0
        r_pos = 1
        if len(self.time_data) == 4:
            if len(self.time_data['d']) > 4:
                l_pos = self.time_data['d'][1]
                r_pos = self.time_data['d'][-2]
        self.set_left(l_pos)
        self.set_right(r_pos)

    def get_time(self):
        return self.latest_time

    def get_left(self):
        return self.left_cursor_pos

    def get_right(self):
        return self.right_cursor_pos

    def move_both_cursors(self, l_val, r_val):
        self.set_left(l_val, emit=False)
        self.set_right(r_val)

    def set_left(self, l_pos, update=False, emit=True):
        if l_pos > self.right_cursor_pos:
            self.right_cursor_pos = l_pos + 1
        self.left_cursor_pos = l_pos
        self.left_cursor.setPos(l_pos)
        # Update label with time value - single line format
        self.left_cursor.label.setText(f"Start {l_pos:.2f}s")
        if emit:
            self.segment_signal.emit(self.left_cursor_pos, self.right_cursor_pos, update)

    def set_right(self, r_pos, update=False, emit=True):
        if r_pos < self.left_cursor_pos:
            r_pos = self.left_cursor_pos + 1
        if update and self.block_updates:
            logger.debug(f"update_blocked")
        else:
            self.right_cursor_pos = r_pos
            self.right_cursor.setPos(r_pos)
            # Update label with time value - single line format
            self.right_cursor.label.setText(f"Stop {r_pos:.2f}s")
            if emit:
                self.segment_signal.emit(self.left_cursor_pos, self.right_cursor_pos, update)

    def set_live(self, state):
        self.live = state

    def reset_sensorgram(self):
        for ch in CH_LIST:
            self.plots[ch].clear()
            self.static[ch].clear()
        self.static_index = 0
        self.time_data = {}
        self.lambda_data = {}
        self.unit_factor = UNIT_LIST[self.unit]
        self.latest_time = 0
        self.plot.setLabel('left', text=f'λ ({self.unit})')  # Lambda symbol

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.static[ch].setVisible(bool(flag))

    def show_cycle_time_region(self, cycle_time_minutes):
        """Show cycle time markers - either as vertical lines or a shaded bar."""
        if cycle_time_minutes is None or cycle_time_minutes <= 0:
            self.hide_cycle_time_region()
            return

        # Remove existing markers first
        self.hide_cycle_time_region()

        # Calculate time window
        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)

        logger.debug(f"Cycle markers ({settings.CYCLE_MARKER_STYLE}): [{start_time:.1f}, {end_time:.1f}]s")

        if settings.CYCLE_MARKER_STYLE == "lines":
            self._create_line_markers(start_time, end_time)
        else:
            self._create_shaded_region(start_time, end_time)

    def _create_line_markers(self, start_time: float, end_time: float) -> None:
        """Create vertical line markers for cycle start/end."""
        from PySide6.QtCore import Qt

        self.cycle_start_line = InfiniteLine(
            pos=start_time,
            angle=90,
            pen=mkPen('g', width=4, style=Qt.SolidLine),
            movable=False,
            label='Cycle Start',
            labelOpts={'position': 0.95, 'color': (0, 255, 0), 'movable': False, 'fill': (0, 0, 0, 100)}
        )

        self.cycle_end_line = InfiniteLine(
            pos=end_time,
            angle=90,
            pen=mkPen('r', width=4, style=Qt.SolidLine),
            movable=False,
            label='Cycle End',
            labelOpts={'position': 0.95, 'color': (255, 0, 0), 'movable': False, 'fill': (0, 0, 0, 100)}
        )

        self.cycle_start_line.setZValue(100)
        self.cycle_end_line.setZValue(100)
        self.cycle_start_line.setVisible(True)
        self.cycle_end_line.setVisible(True)

        self.plot.addItem(self.cycle_start_line)
        self.plot.addItem(self.cycle_end_line)
        self.plot.getViewBox().update()

    def _create_shaded_region(self, start_time: float, end_time: float) -> None:
        """Create shaded region for cycle window."""
        from PySide6.QtGui import QBrush, QColor

        self.cycle_time_region = LinearRegionItem(
            values=[start_time, end_time],
            orientation='vertical',
            brush=QBrush(QColor(100, 100, 255, 70)),
            movable=False,
            pen=None
        )
        self.cycle_time_region.setZValue(-10)
        self.cycle_time_region.setVisible(True)

        self.plot.addItem(self.cycle_time_region)
        self.plot.getViewBox().update()

    def hide_cycle_time_region(self):
        """Hide all cycle time markers."""
        markers = [
            (self.cycle_time_region, 'cycle_time_region'),
            (self.cycle_start_line, 'cycle_start_line'),
            (self.cycle_end_line, 'cycle_end_line')
        ]

        for marker, attr_name in markers:
            if marker is not None:
                self.plot.removeItem(marker)
                setattr(self, attr_name, None)

    def update_cycle_time_region(self, cycle_time_minutes):
        """Update cycle marker positions if cursor moves during cycle."""
        if not (cycle_time_minutes and cycle_time_minutes > 0):
            return

        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)

        # Update existing markers or create new ones
        if self.cycle_time_region is not None:
            self.cycle_time_region.setRegion([start_time, end_time])
        elif self.cycle_start_line is not None and self.cycle_end_line is not None:
            self.cycle_start_line.setPos(start_time)
            self.cycle_end_line.setPos(end_time)
        else:
            # No markers exist, create them
            self.show_cycle_time_region(cycle_time_minutes)


class SegmentGraph(GraphicsLayoutWidget):
    """
    Detail/Cycle of Interest graph - shows zoomed view of selected data.

    Purpose:
    - Shows data between yellow/red cursors from sensorgram
    - During active cycle: displays fixed window view (0 → cycle_duration × 1.1)
    - Takes 80% of screen height for detailed analysis
    - Shows processed shift data (nm or RU)

    Architecture:
    - Part of master-detail layout (paired with SensorgramGraph)
    - Updates live as data flows during cycle recording
    - Supports dissociation/association cursor analysis
    - Fixed window during cycles, auto-range otherwise
    """
    average_channel_flag = False
    average_channel_ids = []
    subsample_threshold = 501
    subsample_target = 250
    subsampling = False
    updating = False
    fixed_window_active = False
    dissoc_cursor_sig = Signal(str, float, float)
    assoc_cursor_sig = Signal(str, float, float)
    shift_values_signal = Signal(dict)  # Signal to emit shift values to display box

    def __init__(self, title_string, unit_string, parent=None, has_cursors=False):
        super(SegmentGraph, self).__init__(parent=parent)
        setConfigOptions(antialias=True)
        self.unit = unit_string

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, size='10pt')
        self.plot.setDownsampling(ds=False, mode='subsample')
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel("left", f"Δ SPR ({unit_string})")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible(x=True, y=True)
        self.plots = {}

        # Ensure axes have space for labels - explicit sizing for visibility
        bottom_axis = self.plot.getAxis('bottom')
        left_axis = self.plot.getAxis('left')
        bottom_axis.setHeight(45)  # Increased space for 'Time (s)' label visibility
        left_axis.setWidth(55)     # Space for Y-axis label

        # Ensure label is visible
        bottom_axis.label.show()
        left_axis.label.show()

        # Set minimum Y-axis range (10 RU minimum)
        self.min_y_range = 10.0
        self.plot.getViewBox().sigRangeChanged.connect(self._enforce_min_range)

        # Set default Y-axis range for Cycle of Interest (-5 to 10 RU)
        self.plot.setYRange(-5, 10, padding=0)

        self.wait_to_update = False
        self.dissoc_cursors = {ch: {'Start': None, 'End': None} for ch in CH_LIST}
        self.dissoc_cursor_en = False
        self.assoc_cursors = {ch: {'Start': None, 'End': None} for ch in CH_LIST}
        self.assoc_cursor_en = False

        # Fixed annotation box for shift values (always visible in upper-left)
        self.shift_annotation = None
        for ch in CH_LIST:
            self.plots[ch] = self.plot.plot(pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2), connect='finite')
            if has_cursors:
                for cursor in ['Start', 'End']:
                    for cursor_dict in [self.dissoc_cursors, self.assoc_cursors]:
                        cursor_dict[ch][cursor] = InfiniteLine(
                            pos=0,
                            name=ch,
                            label=f"{cursor}",
                            labelOpts={'rotateAxis': (1, 0)},
                            angle=90,
                            pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3),
                            movable=True)
                        cursor_dict[ch][cursor].setHoverPen('y')
                        self.plot.addItem(cursor_dict[ch][cursor])
                        cursor_dict[ch][cursor].setVisible(False)
                    self.dissoc_cursors[ch][cursor].sigPositionChangeFinished.connect(self.dissoc_update)
                    self.assoc_cursors[ch][cursor].sigPositionChangeFinished.connect(self.assoc_update)

    def update_colors(self):
        """Update plot and cursor colors when colorblind mode is toggled."""
        try:
            for ch in CH_LIST:
                # Update line colors for each channel
                self.plots[ch].setPen(mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2))

                # Update dissociation/association cursor colors if present
                for cursor in ['Start', 'End']:
                    if ch in self.dissoc_cursors and self.dissoc_cursors[ch][cursor] is not None:
                        self.dissoc_cursors[ch][cursor].setPen(mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3))
                    if ch in self.assoc_cursors and self.assoc_cursors[ch][cursor] is not None:
                        self.assoc_cursors[ch][cursor].setPen(mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3))
        except Exception as e:
            logger.debug(f"Error updating SegmentGraph colors: {e}")

    def en_dissoc_cursors(self, en):
        self.dissoc_cursor_en = bool(en)
        for ch in CH_LIST:
            if self.plots[ch].isVisible():
                for cursor in ['Start', 'End']:
                    self.dissoc_cursors[ch][cursor].setVisible(bool(en))

    def en_assoc_cursors(self, en):
        self.assoc_cursor_en = bool(en)
        for ch in CH_LIST:
            if self.plots[ch].isVisible():
                for cursor in ['Start', 'End']:
                    self.assoc_cursors[ch][cursor].setVisible(bool(en))

    def dissoc_update(self, sender):
        if not self.wait_to_update:
            ch = sender.name()
            self.dissoc_cursor_sig.emit(ch, self.dissoc_cursors[ch]['Start'].value(),
                                        self.dissoc_cursors[ch]['End'].value())

    def assoc_update(self, sender):
        if not self.wait_to_update:
            ch = sender.name()
            self.assoc_cursor_sig.emit(ch, self.assoc_cursors[ch]['Start'].value(),
                                       self.assoc_cursors[ch]['End'].value())

    def move_dissoc_cursors(self, ch, start, end):
        self.wait_to_update = True
        self.dissoc_cursors[ch]['Start'].setPos(start)
        self.wait_to_update = False
        self.dissoc_cursors[ch]['End'].setPos(end)

    def move_assoc_cursors(self, ch, start, end):
        self.wait_to_update = True
        self.assoc_cursors[ch]['Start'].setPos(start)
        self.wait_to_update = False
        self.assoc_cursors[ch]['End'].setPos(end)

    def set_plot_pen(self, ch, pen_colour):
        self.plots[ch].setPen(mkPen(color=pen_colour, width=2), connect='finite')

    def update_display(self, seg, use_data=False):
        self.updating = True
        try:
            if use_data:
                x_data = seg.data_x
                y_data = seg.data_y
            else:
                x_data = seg.seg_x
                y_data = seg.seg_y
            for ch in CH_LIST:
                if ch == seg.ref_ch:
                    self.set_plot_pen(ch, 'purple')
                else:
                    self.set_plot_pen(ch, settings.ACTIVE_GRAPH_COLORS[ch])
            if x_data is not None and y_data is not None:
                # Track min/max for visible channels to apply padding
                y_min = float('inf')
                y_max = float('-inf')
                x_min = float('inf')
                x_max = float('-inf')
                has_visible_data = False

                for ch in CH_LIST:
                    y = y_data[ch]
                    x = x_data[ch]
                    if len(x) == len(y) and len(x) > 0:
                        self.plots[ch].setData(y=y, x=x)
                        # Only consider visible channels for padding calculation
                        if self.plots[ch].isVisible():
                            has_visible_data = True
                            y_min = min(y_min, np.nanmin(y))
                            y_max = max(y_max, np.nanmax(y))
                            x_min = min(x_min, np.nanmin(x))
                            x_max = max(x_max, np.nanmax(x))

                # Apply padding: +10 RU above max, -5 RU below min, minimum 10s time span
                if has_visible_data:
                    # Y-axis padding (convert to RU if needed)
                    if self.unit == "nm":
                        # Convert nm to RU for padding calculation (approximate: 1 RU ≈ 0.1 nm)
                        y_padding_top = 10 * 0.1  # 10 RU ≈ 1 nm
                        y_padding_bottom = 5 * 0.1  # 5 RU ≈ 0.5 nm
                    else:
                        y_padding_top = 10  # 10 RU
                        y_padding_bottom = 5  # 5 RU

                    padded_y_min = y_min - y_padding_bottom
                    padded_y_max = y_max + y_padding_top

                    # X-axis: use cycle_time if available (with 10% padding), otherwise rolling 10-second window
                    if hasattr(seg, 'cycle_time') and seg.cycle_time is not None:
                        # Cycle has a defined time: show cycle_time + 10%
                        target_time = seg.cycle_time * 60  # Convert minutes to seconds
                        padded_x_min = x_min
                        padded_x_max = x_min + (target_time * 1.1)  # Add 10% padding
                    else:
                        # Auto-read or no cycle time: rolling 10-second window
                        x_span = x_max - x_min
                        if x_span < 10:
                            # Show 0-10 second window, moving forward with new data
                            padded_x_min = x_min
                            padded_x_max = x_min + 10
                        else:
                            # Data exceeds 10 seconds, show all data
                            padded_x_min = x_min
                            padded_x_max = x_max

                    # Set the ranges with padding disabled to avoid auto-scaling
                    # BUT only if fixed window is not active (from cycle start)
                    if not self.fixed_window_active:
                        self.plot.setRange(xRange=(padded_x_min, padded_x_max),
                                          yRange=(padded_y_min, padded_y_max),
                                          padding=0)
                    else:
                        # Fixed window active - only update Y range, keep X as-is
                        self.plot.setYRange(padded_y_min, padded_y_max, padding=0)

                # Add shift value labels on the signals
                self._update_shift_labels(seg, x_data, y_data)
        except Exception as e:
            logger.debug(f"Error updating SOI display: {e}")
        self.updating = False

    def is_updating(self):
        return self.updating

    def auto_range(self):
        yrange = self.plot.viewRange()[1]
        self.plot.setRange(yRange=(yrange[0], yrange[1]), update=True, disableAutoRange=False)

    def _enforce_min_range(self):
        """Enforce minimum Y-axis range of 10 RU."""
        try:
            viewbox = self.plot.getViewBox()
            yrange = viewbox.viewRange()[1]
            y_span = yrange[1] - yrange[0]

            if y_span < self.min_y_range:
                # Expand range to minimum, centered on current view
                center = (yrange[0] + yrange[1]) / 2
                new_min = center - self.min_y_range / 2
                new_max = center + self.min_y_range / 2
                viewbox.setYRange(new_min, new_max, padding=0)
        except Exception as e:
            logger.debug(f"Error enforcing min range: {e}")

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.auto_range()
        if self.dissoc_cursor_en:
            self.dissoc_cursors[ch]['Start'].setVisible(bool(flag))
            self.dissoc_cursors[ch]['End'].setVisible(bool(flag))
        if self.assoc_cursor_en:
            self.assoc_cursors[ch]['Start'].setVisible(bool(flag))
            self.assoc_cursors[ch]['End'].setVisible(bool(flag))

    def check_subsample(self, n):
        if n > self.subsample_threshold:
            self.plot.setDownsampling(ds=int(n/self.subsample_target))
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(f"SOI subsample factor: {int(n/self.subsample_target)}")

        if self.subsampling:
            if n < (2 * self.subsample_target):
                self.plot.setDownsampling(ds=False)
                self.subsampling = False
                self.subsample_threshold = 2 * self.subsample_target
                logger.debug("stopped subsampling SOI plot")

    def reset_segment_graph(self, unit=None):
        for ch in CH_LIST:
            self.plots[ch].clear()
        if unit is None:
            unit = self.unit
        self.plot.setLabel('left', text=f'Δ SPR ({unit})')

        # Clear shift annotation
        self._clear_shift_annotation()

    def _clear_shift_annotation(self):
        """Remove the shift value annotation box from the graph."""
        if self.shift_annotation is not None:
            self.plot.removeItem(self.shift_annotation)
            self.shift_annotation = None

    def _update_shift_labels(self, seg, x_data, y_data):
        """Emit shift values to display box instead of drawing on graph."""
        try:
            # Get shift values from the segment object (stored in seg.shift dict)
            if not hasattr(seg, 'shift'):
                return

            # Build dictionary for visible channels only
            shift_data = {}
            for ch in CH_LIST:
                if self.plots[ch].isVisible():
                    shift_val = seg.shift.get(ch, 0.0)
                    shift_data[ch] = shift_val

            if shift_data:
                # Emit signal with shift data
                self.shift_values_signal.emit(shift_data)
            else:
                # Clear display if no channels visible
                self.shift_values_signal.emit({})

            # Clear any old annotation
            self._clear_shift_annotation()

        except Exception as e:
            logger.debug(f"Error updating shift annotation: {e}")
