from copy import deepcopy

from pyqtgraph import GraphicsLayoutWidget, InfiniteLine, mkPen, setConfigOptions
from PySide6.QtCore import Signal

from settings import CH_LIST, GRAPH_COLORS, STATIC_PLOT, UNIT_LIST
from utils.logger import logger


class SensorgramGraph(GraphicsLayoutWidget):
    segment_signal = Signal(float, float, bool)

    def __init__(self, title_string):
        super().__init__()

        self.subsample_threshold = 301
        self.subsample_target = 150
        self.subsampling = False
        self.block_updates = False
        self.unit = "nm"
        self.unit_factor = UNIT_LIST[self.unit]
        self.updating = False
        self.live_range = 50
        self.static_index = 0
        self.wait_for_reset = False

        setConfigOptions(antialias=True)

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, size="13pt")
        self.plot.showGrid(x=True, y=True)
        self.plot.setAxisItems()
        self.plot.setLabel("left", text=f"Lambda ({self.unit})")
        self.plot.setLabel("bottom", text="Time (s)")
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
            self.plots[ch] = self.plot.plot(
                pen=mkPen(GRAPH_COLORS[ch], width=2), connect="finite"
            )
            self.static[ch] = self.plot.plot(
                pen=mkPen(GRAPH_COLORS[ch], width=2), connect="finite"
            )
        self.latest_time = 0

        self.live = True

        # set vertical cursors: left and right
        self.left_cursor = InfiniteLine(
            pos=0, angle=90, pen=mkPen("y", width=3), movable=True
        )

        self.right_cursor = InfiniteLine(
            pos=0, angle=90, pen=mkPen("r", width=3), movable=True
        )

        # set cursor color
        self.left_cursor.setHoverPen("k")
        self.right_cursor.setHoverPen("k")

        self.plot.addItem(self.left_cursor)
        self.plot.addItem(self.right_cursor)

        self.left_cursor.sigDragged.connect(self.left_cursor_sig_dragged)
        self.right_cursor.sigDragged.connect(self.right_cursor_sig_dragged)
        self.left_cursor.sigPositionChangeFinished.connect(self.left_cursor_moved)
        self.right_cursor.sigPositionChangeFinished.connect(self.right_cursor_moved)

        # initial position of cursors
        self.left_cursor_pos = 0
        self.right_cursor_pos = 1
        self.set_left(0, emit=False)
        self.set_right(1, emit=False)

    def movable_cursors(self, state):
        self.left_cursor.setMovable(state)
        self.right_cursor.setMovable(state)

    def check_subsample(self, n):
        if n > self.subsample_threshold:
            self.plot.setDownsampling(ds=int(n / self.subsample_target))
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(
                f"sensorgram subsample factor: {int(n / self.subsample_target)}"
            )

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
            
            # Enhanced logging to debug plot updates
            total_points = sum(len(lambda_values.get(ch, [])) for ch in CH_LIST)
            if total_points > 0:
                logger.debug(f"📊 Plotting data: {total_points} total points across channels")
            
            for ch in CH_LIST:
                y_data = deepcopy(lambda_values[ch])
                x_data = deepcopy(lambda_times[ch])
                if ch == "a":
                    self.check_subsample(len(y_data))
                    if STATIC_PLOT:
                        if (
                            min(
                                len(lambda_values["a"]),
                                len(lambda_values["b"]),
                                len(lambda_values["c"]),
                                len(lambda_values["d"]),
                            )
                        ) > (self.static_index + self.live_range + 5):
                            self.static_index += self.live_range
                            static_data = True
                            # logger.debug(f"len a = {len(y_data)}, len b = {len(lambda_values['b'])}, "
                            #             f"len c = {len(lambda_values['c'])}, len d = {len(lambda_values['d'])}, "
                            #             f"static index = {self.static_index}")
                if static_data:
                    n = max(int(len(y_data) / 2500), 1)
                    static_x_data = x_data[0 : (self.static_index + 1) : n]
                    static_y_data = y_data[0 : (self.static_index + 1) : n]
                x_data = x_data[self.static_index :]
                y_data = y_data[self.static_index :]
                if len(y_data) == len(x_data):
                    self.plots[ch].setData(y=y_data, x=x_data)
                    if static_data and (static_y_data is not None):
                        self.static[ch].setData(y=static_y_data, x=static_x_data)
                        logger.debug("static sensorgram data plotted")
                    self.time_data[ch] = lambda_times[ch]
                    self.lambda_data[ch] = lambda_values[ch]
                    if len(lambda_times[ch]) > 0:
                        if lambda_times[ch][-1] > self.latest_time:
                            self.latest_time = lambda_times[ch][-1] + 0.01
                else:
                    logger.debug(
                        f"sensorgram data not plottable, y = {y_data}, x = {x_data}"
                    )
            if self.live and not self.wait_for_reset:
                # Auto-scroll right cursor to latest time while live
                if (len(self.time_data.get("d", [])) < 300) or (
                    abs(self.right_cursor.value() - self.latest_time)
                    > (len(self.time_data) * 0.01)
                ):
                    self.set_right(self.latest_time, True)
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
        if len(self.time_data.get("d", [])) < 300 or abs(
            self.left_cursor.value() - self.left_cursor_pos
        ) > (len(self.time_data) * 0.005):
            self.set_left(self.left_cursor.value())

    def right_cursor_sig_dragged(self):
        if len(self.time_data.get("d", [])) < 300 or abs(
            self.right_cursor.value() - self.right_cursor_pos
        ) > (len(self.time_data) * 0.005):
            self.set_right(self.right_cursor.value())

    def center_cursors(self):
        l_pos = 0
        r_pos = 1
        if len(self.time_data) == 4:
            if len(self.time_data["d"]) > 4:
                l_pos = self.time_data["d"][1]
                r_pos = self.time_data["d"][-2]
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
            self.segment_signal.emit(
                self.left_cursor_pos, self.right_cursor_pos, update
            )

    def set_right(self, r_pos, update=False, emit=True):
        if r_pos < self.left_cursor_pos:
            r_pos = self.left_cursor_pos + 1
        if update and self.block_updates:
            logger.debug("update_blocked")
        else:
            self.right_cursor_pos = r_pos
            self.right_cursor.setPos(r_pos)
            if emit:
                self.segment_signal.emit(
                    self.left_cursor_pos, self.right_cursor_pos, update
                )

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
        self.plot.setLabel("left", text=f"Lambda ({self.unit})")

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.static[ch].setVisible(bool(flag))
        yrange = self.plot.viewRange()[1]
        self.plot.setRange(
            yRange=(yrange[0], yrange[1]), update=True, disableAutoRange=False
        )


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
        super().__init__(parent=parent)
        setConfigOptions(antialias=True)
        self.unit = unit_string

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, size="10pt")
        self.plot.setDownsampling(ds=False, mode="subsample")
        self.plot.showGrid(x=True, y=True)
        self.plot.setLabel("left", f"Shift ({unit_string})")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible(x=True, y=True)
        self.plots = {}

        self.wait_to_update = False
        self.dissoc_cursors = {ch: {"Start": None, "End": None} for ch in CH_LIST}
        self.dissoc_cursor_en = False
        self.assoc_cursors = {ch: {"Start": None, "End": None} for ch in CH_LIST}
        self.assoc_cursor_en = False
        for ch in CH_LIST:
            self.plots[ch] = self.plot.plot(
                pen=mkPen(GRAPH_COLORS[ch], width=2), connect="finite"
            )
            if has_cursors:
                for cursor in ["Start", "End"]:
                    for cursor_dict in [self.dissoc_cursors, self.assoc_cursors]:
                        cursor_dict[ch][cursor] = InfiniteLine(
                            pos=0,
                            name=ch,
                            label=f"{cursor}",
                            labelOpts={"rotateAxis": (1, 0)},
                            angle=90,
                            pen=mkPen(GRAPH_COLORS[ch], width=3),
                            movable=True,
                        )
                        cursor_dict[ch][cursor].setHoverPen("y")
                        self.plot.addItem(cursor_dict[ch][cursor])
                        cursor_dict[ch][cursor].setVisible(False)
                    self.dissoc_cursors[ch][cursor].sigPositionChangeFinished.connect(
                        self.dissoc_update
                    )
                    self.assoc_cursors[ch][cursor].sigPositionChangeFinished.connect(
                        self.assoc_update
                    )

    def en_dissoc_cursors(self, en):
        self.dissoc_cursor_en = bool(en)
        for ch in CH_LIST:
            if self.plots[ch].isVisible():
                for cursor in ["Start", "End"]:
                    self.dissoc_cursors[ch][cursor].setVisible(bool(en))

    def en_assoc_cursors(self, en):
        self.assoc_cursor_en = bool(en)
        for ch in CH_LIST:
            if self.plots[ch].isVisible():
                for cursor in ["Start", "End"]:
                    self.assoc_cursors[ch][cursor].setVisible(bool(en))

    def dissoc_update(self, sender):
        if not self.wait_to_update:
            ch = sender.name()
            self.dissoc_cursor_sig.emit(
                ch,
                self.dissoc_cursors[ch]["Start"].value(),
                self.dissoc_cursors[ch]["End"].value(),
            )

    def assoc_update(self, sender):
        if not self.wait_to_update:
            ch = sender.name()
            self.assoc_cursor_sig.emit(
                ch,
                self.assoc_cursors[ch]["Start"].value(),
                self.assoc_cursors[ch]["End"].value(),
            )

    def move_dissoc_cursors(self, ch, start, end):
        self.wait_to_update = True
        self.dissoc_cursors[ch]["Start"].setPos(start)
        self.wait_to_update = False
        self.dissoc_cursors[ch]["End"].setPos(end)

    def move_assoc_cursors(self, ch, start, end):
        self.wait_to_update = True
        self.assoc_cursors[ch]["Start"].setPos(start)
        self.wait_to_update = False
        self.assoc_cursors[ch]["End"].setPos(end)

    def set_plot_pen(self, ch, pen_colour):
        self.plots[ch].setPen(mkPen(color=pen_colour, width=2), connect="finite")

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
                    self.set_plot_pen(ch, "purple")
                else:
                    self.set_plot_pen(ch, GRAPH_COLORS[ch])
            if x_data is not None and y_data is not None:
                for ch in CH_LIST:
                    y = y_data[ch]
                    x = x_data[ch]
                    if len(x) == len(y):
                        self.plots[ch].setData(y=y, x=x)
        except Exception as e:
            logger.debug(f"Error updating SOI display: {e}")
        self.updating = False

    def is_updating(self):
        return self.updating

    def auto_range(self):
        yrange = self.plot.viewRange()[1]
        self.plot.setRange(
            yRange=(yrange[0], yrange[1]), update=True, disableAutoRange=False
        )

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.auto_range()
        if self.dissoc_cursor_en:
            self.dissoc_cursors[ch]["Start"].setVisible(bool(flag))
            self.dissoc_cursors[ch]["End"].setVisible(bool(flag))
        if self.assoc_cursor_en:
            self.assoc_cursors[ch]["Start"].setVisible(bool(flag))
            self.assoc_cursors[ch]["End"].setVisible(bool(flag))

    def check_subsample(self, n):
        if n > self.subsample_threshold:
            self.plot.setDownsampling(ds=int(n / self.subsample_target))
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(f"SOI subsample factor: {int(n / self.subsample_target)}")

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
        self.plot.setLabel("left", text=f"Shift ({unit})")
