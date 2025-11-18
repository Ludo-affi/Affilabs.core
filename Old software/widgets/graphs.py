import PySide6
import pyqtgraph
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from pyqtgraph import GraphicsLayoutWidget, setConfigOptions, mkPen, InfiniteLine, LinearRegionItem
from copy import deepcopy
import settings
from settings import CH_LIST, UNIT_LIST, STATIC_PLOT, DEV
from utils.logger import logger


class SensorgramGraph(GraphicsLayoutWidget):
    segment_signal = Signal(float, float, bool)

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
        self.plot.showGrid(x=False, y=False)
        self.plot.setAxisItems()
        self.plot.setLabel('left', text=f'Lambda ({self.unit})')
        self.plot.setLabel('bottom', text='Time (s)')
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible()

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

        # set vertical cursors: left and right
        self.left_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=mkPen('y', width=3),
            movable=True)

        self.right_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=mkPen('r', width=3),
            movable=True)

        # set cursor color
        self.left_cursor.setHoverPen('k')
        self.right_cursor.setHoverPen('k')

        self.plot.addItem(self.left_cursor)
        self.plot.addItem(self.right_cursor)

        # Cycle time shaded region
        self.cycle_time_region = None

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
            if self.live and not self.wait_for_reset:
                # Always follow the latest time while live is enabled
                # But don't re-enable auto-range if it's disabled (for fixed window)
                self.set_right(self.latest_time, update=True)
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
        self.plot.setLabel('left', text=f'Lambda ({self.unit})')

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.static[ch].setVisible(bool(flag))

    def show_cycle_time_region(self, cycle_time_minutes):
        """Show a shaded region indicating the expected cycle duration."""
        logger.debug(f"show_cycle_time_region called: cycle_time={cycle_time_minutes} min")
        if cycle_time_minutes is None or cycle_time_minutes <= 0:
            self.hide_cycle_time_region()
            return

        # Remove existing region if any
        self.hide_cycle_time_region()

        # Create shaded region from left cursor to left cursor + cycle_time
        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)  # Convert minutes to seconds
        logger.debug(f"Creating gray zone: from {start_time:.2f}s to {end_time:.2f}s")

        # Use LinearRegionItem for a vertical shaded region
        from pyqtgraph import LinearRegionItem
        self.cycle_time_region = LinearRegionItem(
            values=[start_time, end_time],
            orientation='vertical',
            brush=(150, 150, 255, 100),  # Light blue with higher opacity
            movable=False
        )
        
        # Set z-order to ensure it's visible but behind data plots
        self.cycle_time_region.setZValue(-10)
        logger.debug(f"Gray zone created with brush opacity 100, z-value -10")
        
        # Add to plot
        self.plot.addItem(self.cycle_time_region)
        logger.debug(f"Gray zone added to plot: region object = {self.cycle_time_region}")
        
        # Force update/redraw
        self.cycle_time_region.update()
        self.plot.update()
        logger.debug("Plot update called to render gray zone")

    def hide_cycle_time_region(self):
        """Hide the cycle time shaded region."""
        if self.cycle_time_region is not None:
            self.plot.removeItem(self.cycle_time_region)
            self.cycle_time_region = None

    def update_cycle_time_region(self, cycle_time_minutes):
        """Update the cycle time region position based on left cursor."""
        if cycle_time_minutes is not None and cycle_time_minutes > 0:
            start_time = self.left_cursor_pos
            end_time = start_time + (cycle_time_minutes * 60)

            if self.cycle_time_region is not None:
                self.cycle_time_region.setRegion([start_time, end_time])
            else:
                self.show_cycle_time_region(cycle_time_minutes)
        yrange = self.plot.viewRange()[1]
        self.plot.setRange(yRange=(yrange[0], yrange[1]), update=True, disableAutoRange=False)


class SegmentGraph(GraphicsLayoutWidget):
    average_channel_flag = False
    average_channel_ids = []
    subsample_threshold = 501
    subsample_target = 250
    subsampling = False
    updating = False
    dissoc_cursor_sig = Signal(str, float, float)
    assoc_cursor_sig = Signal(str, float, float)

    def __init__(self, title_string, unit_string, parent=None, has_cursors=False):
        super(SegmentGraph, self).__init__(parent=parent)
        setConfigOptions(antialias=True)
        self.unit = unit_string

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, size='10pt')
        self.plot.setDownsampling(ds=False, mode='subsample')
        self.plot.showGrid(x=False, y=False)
        self.plot.setLabel("left", f"Shift ({unit_string})")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible(x=True, y=True)
        self.plots = {}

        # Set minimum Y-axis range (10 RU minimum)
        self.min_y_range = 10.0
        self.plot.getViewBox().sigRangeChanged.connect(self._enforce_min_range)

        self.wait_to_update = False
        self.dissoc_cursors = {ch: {'Start': None, 'End': None} for ch in CH_LIST}
        self.dissoc_cursor_en = False
        self.assoc_cursors = {ch: {'Start': None, 'End': None} for ch in CH_LIST}
        self.assoc_cursor_en = False
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
                    self.plot.setRange(xRange=(padded_x_min, padded_x_max),
                                      yRange=(padded_y_min, padded_y_max),
                                      padding=0)
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
        self.plot.setLabel('left', text=f'Shift ({unit})')
