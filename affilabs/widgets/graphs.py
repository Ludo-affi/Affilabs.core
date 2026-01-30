from copy import deepcopy

import numpy as np
from pyqtgraph import (
    GraphicsLayoutWidget,
    InfiniteLine,
    LinearRegionItem,
    mkPen,
    setConfigOptions,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsProxyWidget,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

import settings
from affilabs.utils.logger import logger
from settings import CH_LIST, STATIC_PLOT, UNIT_LIST

# Configure PyQtGraph for maximum performance
setConfigOptions(
    antialias=True,  # Smooth lines
    useNumba=False,  # Disable numba (can cause issues with batched updates)
    exitCleanup=True,  # Clean shutdown
    enableExperimental=False,  # Stable features only
)

# Import modern theme colors
try:
    from styles import create_channel_pens, get_graph_colors, style_plot_widget

    MODERN_COLORS = get_graph_colors()
    MODERN_THEME = True
except ImportError:
    MODERN_THEME = False
    MODERN_COLORS = None


class SensorgramGraph(GraphicsLayoutWidget):
    """Master/Overview graph for full experiment timeline (Live Sensorgram).

    **Navigation Philosophy:**
    - The LIVE SENSORGRAM is the NAVIGATION SPACE (full experiment overview)
    - Shows continuous trace from experiment start with cycle boundaries marked
    - Focus on monitoring/acquisition - review done in separate Cycle Review dialog

    Purpose:
    - Shows complete timeline of all collected data (navigational view)
    - Vertical lines/shaded regions mark cycle boundaries
    - Intelligent auto-scaling handles spikes/outliers automatically (95th percentile)
    - Compact layout (30% height) for navigation/context

    Y-Axis Scaling:
    - Smart outlier detection: Uses 95th percentile to ignore spikes
    - No manual cursor adjustment needed (deprecated legacy feature)
    - Maintains clean view even with transient noise/artifacts

    Downsampling Strategy (Navigational View):
    - AGGRESSIVE downsampling for historical data (old cycles)
      → Static data: 1/2500 sampling (n=max(len/2500, 1))
      → Purpose: Fast rendering, navigation only
    - GENTLE downsampling for live/recent data
      → Threshold: 301 points, target: 150 points
      → Preserves detail in current viewing region
    - Tracks cycle boundaries to identify regions of interest
      → self.cycle_start_time, self.cycle_end_time

    Architecture:
    - Part of master-detail layout (paired with SegmentGraph/Cycle of Interest)
    - When cycle starts: gray zone appears, fixed window applied
    - Live data continues updating, cursor auto-follow disabled during cycle
    - Historical data can be heavily downsampled since it's for navigation only
    """

    segment_signal = Signal(float, float, bool)
    shift_values_signal = Signal(dict)  # Signal to emit shift values to display box

    def __init__(self, title_string, show_title=False):
        super(SensorgramGraph, self).__init__()

        # Downsampling strategy: aggressive for historical, gentle for cycle of interest
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
        self.fixed_window_active = (
            False  # Flag to prevent auto-range when window is fixed
        )

        # Smart downsampling: track cycle boundaries for selective downsampling
        self.cycle_start_time = None  # When current cycle started
        self.cycle_end_time = None  # When current cycle ended (if completed)
        self.cycle_warning_region = None  # Yellow warning region for cycle nearing end

        setConfigOptions(antialias=True)

        # Set plot settings: minimalist chrome for maximum data area
        if show_title:
            self.plot = self.addPlot(title=title_string)
            # Style title
            self.plot.titleLabel.setText(title_string, color=(30, 30, 30), size="11pt")
        else:
            self.plot = self.addPlot()
        self.plot.showGrid(x=False, y=False)
        self.plot.setAxisItems()
        self.plot.setLabel("left", text=f"λ ({self.unit})")  # Lambda symbol
        self.plot.setLabel("bottom", text="Time (s)")
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible()

        # Set default Y-axis range for detector (580-660 nm)
        self.plot.setYRange(580, 660, padding=0)

        # ViewBox performance optimizations for smooth rendering:
        # - Reduce update frequency during resize/pan/zoom
        # - Enable faster clipping (only render visible region)
        vb = self.plot.getViewBox()
        vb.setLimits(xMin=0)  # Time always positive
        vb.setMouseEnabled(x=True, y=True)

        # Reduce Y-axis tick density for cleaner compact view
        self.plot.getAxis("left").setStyle(maxTickLevel=1)  # Show fewer tick levels

        # Ensure bottom axis has space for label - explicit sizing for visibility
        bottom_axis = self.plot.getAxis("bottom")
        left_axis = self.plot.getAxis("left")
        bottom_axis.setHeight(45)  # Increased space for 'Time (s)' label visibility
        left_axis.setWidth(55)  # Space for Y-axis label

        # Ensure label is visible
        bottom_axis.label.show()
        left_axis.label.show()

        # set up channel data and plots
        self.plots = {}
        self.static = {}
        self.time_data = {}
        self.lambda_data = {}
        for ch in CH_LIST:
            # Performance optimizations for smooth display:
            # - clipToView: Only render data visible in viewport (huge speedup)
            # - autoDownsample: Automatic decimation when zoomed out
            # - connect='finite': Better handling of batch data gaps
            # - skipFiniteCheck: Faster rendering (data already validated)
            self.plots[ch] = self.plot.plot(
                pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
                connect="finite",
                clipToView=True,
                autoDownsample=True,
                skipFiniteCheck=True,
            )
            self.static[ch] = self.plot.plot(
                pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
                connect="finite",
                clipToView=True,
                autoDownsample=True,
                skipFiniteCheck=True,
            )
        self.latest_time = 0

        self.live = True

        # Cursor styling: thicker lines for easier interaction
        # Main pen: 3px width for better visibility and click target
        cursor_pen = mkPen("#333333", width=3)
        cursor_label_opts = {
            "position": 0.95,
            "color": (51, 51, 51),
            "movable": False,
            "fill": (255, 255, 255, 220),
            "anchor": (1.0, 0.5),
            "rotateAxis": (0, 1),
        }

        start_label_opts = cursor_label_opts.copy()
        start_label_opts.update(
            {
                "position": 0.04,
                "anchor": (0.5, 1.25),
            },
        )

        # Set vertical cursors: left and right with thicker styling for easier selection
        # The live sensorgram is the navigation space - cursors define the cycle of interest region
        self.left_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=cursor_pen,
            movable=True,
            label="Start 0.00s",
            labelOpts=start_label_opts,
        )

        self.right_cursor = InfiniteLine(
            pos=0,
            angle=90,
            pen=cursor_pen,
            movable=True,
            label="Stop 0.00s",
            labelOpts=cursor_label_opts.copy(),
        )

        # Set cursor hover color: even thicker on hover (5px) for clear visual feedback
        self.left_cursor.setHoverPen(mkPen("#666666", width=5))
        self.right_cursor.setHoverPen(mkPen("#666666", width=5))

        self.left_cursor.label.setAngle(-90)
        self.right_cursor.label.setAngle(-90)

        # DEPRECATED: Cursors removed from Live Sensorgram for predetermined cycle workflow
        # Cursors were legacy feature for free-form mode and manual Y-scale adjustment
        # Now using intelligent auto-scaling with outlier detection instead
        # Cursors still available in Cycle Review dialog for post-acquisition analysis
        self.left_cursor.setVisible(False)
        self.right_cursor.setVisible(False)
        self.left_cursor.setMovable(False)  # Disable interaction
        self.right_cursor.setMovable(False)

        # Keep cursor objects for compatibility but don't add to plot
        # self.plot.addItem(self.left_cursor)
        # self.plot.addItem(self.right_cursor)

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

        # Add Clear Graph button to top-left corner
        self.clear_button = None
        if show_title:
            self._create_clear_button()

    @property
    def curves(self):
        """Provide list-based access to plot curves for compatibility.

        Returns list in channel order: [a, b, c, d]
        Maps to internal self.plots dictionary.
        """
        return [self.plots["a"], self.plots["b"], self.plots["c"], self.plots["d"]]

    @property
    def start_cursor(self):
        """Alias for left_cursor for API compatibility."""
        return self.left_cursor

    @property
    def stop_cursor(self):
        """Alias for right_cursor for API compatibility."""
        return self.right_cursor

    def _create_clear_button(self):
        """Create a Clear Graph button positioned at the top-left corner."""
        # Create button widget
        button = QPushButton("Clear")
        button.setMinimumSize(50, 24)
        button.setMaximumSize(60, 26)
        button.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 25);
                color: rgb(45, 45, 45);
                border: 1px solid rgba(0, 0, 0, 40);
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 8pt;
                font-weight: normal;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 50);
                color: white;
            }
            QPushButton:pressed {
                background: rgba(0, 0, 0, 70);
            }
        """)

        # Create proxy widget to add button to the graphics scene
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(button)

        # Store references
        self.clear_button = button
        self.clear_button_proxy = proxy

        # Add to scene
        self.plot.scene().addItem(proxy)

        # Position the button - will be adjusted in layout
        self._position_clear_button()

    def _position_clear_button(self):
        """Position the Clear button at the top-left of the graph."""
        if hasattr(self, "clear_button_proxy"):
            # Get the plot area coordinates
            plot_rect = self.plot.sceneBoundingRect()

            # Position at top-left corner with some padding
            x = plot_rect.left() + 10
            y = plot_rect.top() + 10

            self.clear_button_proxy.setPos(x, y)

    def update_colors(self):
        """Update plot colors when colorblind mode is toggled."""
        for ch in CH_LIST:
            self.plots[ch].setPen(
                mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
            )
            if hasattr(self, "static") and ch in self.static:
                self.static[ch].setPen(
                    mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
                )

    def movable_cursors(self, state):
        self.left_cursor.setMovable(state)
        self.right_cursor.setMovable(state)

    def check_subsample(self, n):
        """Smart downsampling strategy:
        - Historical data (before cycle): aggressive downsampling
        - Cycle of interest region: gentle downsampling to preserve detail
        - Future/live data: minimal downsampling

        The live sensorgram is the navigational graph - we can afford
        to downsample historical data more aggressively while keeping
        the current cycle region detailed.
        """
        if n > self.subsample_threshold:
            # Calculate adaptive downsampling factor based on data regions
            base_factor = int(n / self.subsample_target)

            # Enable downsampling with base factor
            self.plot.setDownsampling(ds=base_factor)
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(f"sensorgram downsample factor: {base_factor} (n={n})")

        if self.subsampling:
            if n < (self.subsample_threshold - self.subsample_target):
                self.plot.setDownsampling(ds=False)
                self.subsampling = False
                self.subsample_threshold = 2 * self.subsample_target
                logger.debug("stopped subsampling sensorgram plot")

    def is_updating(self):
        return self.updating

    def update(self, lambda_values, lambda_times):
        """Update sensorgram with smart downsampling strategy:
        - Historical data (old cycles): aggressive downsampling for navigation
        - Current cycle region: gentle downsampling to preserve detail
        - Live/recent data: minimal downsampling for real-time monitoring
        """
        try:
            self.updating = True
            static_x_data = None
            static_y_data = None
            static_data = False

            for ch in CH_LIST:
                y_data = deepcopy(lambda_values[ch])
                x_data = deepcopy(lambda_times[ch])

                if ch == "a":
                    self.check_subsample(len(y_data))

                    # Static plot optimization for long datasets
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

                # Create static downsampled data for old historical regions
                if static_data:
                    # Aggressive downsampling for historical data (navigational view only)
                    # Historical = everything before the live window
                    n = max(int(len(y_data) / 2500), 1)
                    static_x_data = x_data[0 : (self.static_index + 1) : n]
                    static_y_data = y_data[0 : (self.static_index + 1) : n]

                # Live data window (recent/current cycle)
                x_data = x_data[self.static_index :]
                y_data = y_data[self.static_index :]

                if len(y_data) == len(x_data):
                    # Plot live data with minimal downsampling
                    self.plots[ch].setData(y=y_data, x=x_data)

                    if static_data and (static_y_data is not None):
                        # Plot heavily downsampled historical data
                        self.static[ch].setData(y=static_y_data, x=static_x_data)
                        logger.debug(
                            f"static sensorgram data plotted (downsampled 1/{n})",
                        )

                    self.time_data[ch] = lambda_times[ch]
                    self.lambda_data[ch] = lambda_values[ch]

                    if len(lambda_times[ch]) > 0:
                        if lambda_times[ch][-1] > self.latest_time:
                            self.latest_time = lambda_times[ch][-1] + 0.01
                else:
                    logger.debug(
                        f"sensorgram data not plottable, y = {y_data}, x = {x_data}",
                    )

            # Auto-follow the latest data when live mode is enabled AND fixed window is not active
            if self.live and not self.wait_for_reset and not self.fixed_window_active:
                self.set_right(self.latest_time, update=True)
            elif self.fixed_window_active:
                # Log that we're in fixed window mode - data still updates but cursor doesn't move
                if not hasattr(self, "_logged_fixed_window"):
                    logger.info(
                        "📊 Fixed window active - live data updating but cursor locked",
                    )
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
        # Show cursor and label when user interacts
        self.left_cursor.setVisible(True)
        self.left_cursor.label.setVisible(True)
        self.set_left(self.left_cursor.value())

    def right_cursor_moved(self):
        # Show cursor and label when user interacts
        self.right_cursor.setVisible(True)
        self.right_cursor.label.setVisible(True)
        self.set_right(self.right_cursor.value())

    def left_cursor_sig_dragged(self):
        # Show cursor and label when user drags
        self.left_cursor.setVisible(True)
        self.left_cursor.label.setVisible(True)
        n_pts = len(self.time_data["d"]) if "d" in self.time_data else 0
        if n_pts < 300 or abs(self.left_cursor.value() - self.left_cursor_pos) > (
            n_pts * 0.005
        ):
            self.set_left(self.left_cursor.value())

    def right_cursor_sig_dragged(self):
        # Show cursor and label when user drags
        self.right_cursor.setVisible(True)
        self.right_cursor.label.setVisible(True)
        n_pts = len(self.time_data["d"]) if "d" in self.time_data else 0
        if n_pts < 300 or abs(self.right_cursor.value() - self.right_cursor_pos) > (
            n_pts * 0.005
        ):
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
        # Update label with time value - single line format
        self.left_cursor.label.setText(f"Start {l_pos:.2f}s")
        if emit:
            self.segment_signal.emit(
                self.left_cursor_pos,
                self.right_cursor_pos,
                update,
            )

    def set_right(self, r_pos, update=False, emit=True):
        if r_pos < self.left_cursor_pos:
            r_pos = self.left_cursor_pos + 1

        # Always update visual position and label (consistent with set_left behavior)
        self.right_cursor_pos = r_pos
        self.right_cursor.setPos(r_pos)
        # Update label with time value - single line format
        self.right_cursor.label.setText(f"Stop {r_pos:.2f}s")

        # Only skip signal emission if updates are blocked
        if update and self.block_updates:
            logger.debug("update_blocked - visual updated but signal emission skipped")
        elif emit:
            self.segment_signal.emit(
                self.left_cursor_pos,
                self.right_cursor_pos,
                update,
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
        self.plot.setLabel("left", text=f"λ ({self.unit})")  # Lambda symbol

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))
        self.static[ch].setVisible(bool(flag))

    def show_cycle_time_region(self, cycle_time_minutes):
        """Show cycle time markers - either as vertical lines or a shaded bar.
        Also tracks cycle boundaries for smart downsampling.
        """
        if cycle_time_minutes is None or cycle_time_minutes <= 0:
            self.hide_cycle_time_region()
            return

        # Remove existing markers first
        self.hide_cycle_time_region()

        # Calculate time window and track for downsampling strategy
        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)

        # Track cycle boundaries for smart downsampling
        self.cycle_start_time = start_time
        self.cycle_end_time = end_time

        logger.debug(
            f"Cycle markers ({settings.CYCLE_MARKER_STYLE}): [{start_time:.1f}, {end_time:.1f}]s",
        )
        logger.debug(
            f"📊 Cycle region tracked for smart downsampling: preserve detail in [{start_time:.1f}, {end_time:.1f}]s",
        )

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
            pen=mkPen("g", width=4, style=Qt.SolidLine),
            movable=False,
            label="Cycle Start",
            labelOpts={
                "position": 0.95,
                "color": (0, 255, 0),
                "movable": False,
                "fill": (0, 0, 0, 100),
            },
        )

        self.cycle_end_line = InfiniteLine(
            pos=end_time,
            angle=90,
            pen=mkPen("r", width=4, style=Qt.SolidLine),
            movable=False,
            label="Cycle End",
            labelOpts={
                "position": 0.95,
                "color": (255, 0, 0),
                "movable": False,
                "fill": (0, 0, 0, 100),
            },
        )

        self.cycle_start_line.setZValue(100)
        self.cycle_end_line.setZValue(100)
        self.cycle_start_line.setVisible(True)
        self.cycle_end_line.setVisible(True)

        self.plot.addItem(self.cycle_start_line)
        self.plot.addItem(self.cycle_end_line)
        self.plot.getViewBox().update()

    def _create_shaded_region(self, start_time: float, end_time: float) -> None:
        """Create shaded region for cycle window with yellow warning for last portion."""
        self.cycle_time_region = LinearRegionItem(
            values=[start_time, end_time],
            orientation="vertical",
            brush=QBrush(QColor(100, 100, 255, 70)),
            movable=False,
            pen=None,
        )
        self.cycle_time_region.setZValue(-10)
        self.cycle_time_region.setVisible(True)

        self.plot.addItem(self.cycle_time_region)

        # Add yellow warning region for last 60 seconds (or 10% of cycle, whichever is smaller)
        cycle_duration = end_time - start_time
        warning_duration = min(60, cycle_duration * 0.1)  # Last 60s or 10%
        warning_start = end_time - warning_duration

        self.cycle_warning_region = LinearRegionItem(
            values=[warning_start, end_time],
            orientation="vertical",
            brush=QBrush(QColor(255, 200, 0, 100)),  # Bright yellow, more opaque
            movable=False,
            pen=None,
        )
        self.cycle_warning_region.setZValue(-5)  # Above cycle region but below data
        self.cycle_warning_region.setVisible(True)

        self.plot.addItem(self.cycle_warning_region)
        self.plot.getViewBox().update()

    def hide_cycle_time_region(self):
        """Hide all cycle time markers.
        Clears cycle boundary tracking for downsampling.
        """
        markers = [
            (self.cycle_time_region, "cycle_time_region"),
            (self.cycle_start_line, "cycle_start_line"),
            (self.cycle_end_line, "cycle_end_line"),
            (self.cycle_warning_region, "cycle_warning_region"),
        ]

        for marker, attr_name in markers:
            if marker is not None:
                self.plot.removeItem(marker)
                setattr(self, attr_name, None)

        # Clear cycle boundary tracking (no active cycle)
        self.cycle_start_time = None
        self.cycle_end_time = None

    def update_cycle_time_region(self, cycle_time_minutes):
        """Update cycle marker positions if cursor moves during cycle."""
        if not (cycle_time_minutes and cycle_time_minutes > 0):
            return

        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)

        # Update existing markers or create new ones
        if self.cycle_time_region is not None:
            self.cycle_time_region.setRegion([start_time, end_time])

            # Update warning region too
            if self.cycle_warning_region is not None:
                cycle_duration = end_time - start_time
                warning_duration = min(60, cycle_duration * 0.1)
                warning_start = end_time - warning_duration
                self.cycle_warning_region.setRegion([warning_start, end_time])

        elif self.cycle_start_line is not None and self.cycle_end_line is not None:
            self.cycle_start_line.setPos(start_time)
            self.cycle_end_line.setPos(end_time)
        else:
            # No markers exist, create them
            self.show_cycle_time_region(cycle_time_minutes)


class SegmentGraph(GraphicsLayoutWidget):
    """Detail/Cycle of Interest graph - shows zoomed view of selected data.

    Purpose:
    - Shows data between yellow/red cursors from sensorgram (detail view)
    - During active cycle: displays fixed window view (0 → cycle_duration × 1.1)
    - Takes 70% of screen height for detailed analysis
    - Shows processed shift data (nm or RU)

    Downsampling Strategy (Detail View):
    - GENTLE downsampling to preserve data fidelity
      → Threshold: 1001 points (higher than sensorgram)
      → Target: 500 points (keeps 2x more data than sensorgram)
      → Purpose: High-quality visualization for analysis
    - This is where users analyze binding kinetics - detail is critical
    - Paired with aggressive sensorgram downsampling for performance balance

    Architecture:
    - Part of master-detail layout (paired with SensorgramGraph)
    - Updates live as data flows during cycle recording
    - Supports dissociation/association cursor analysis
    - Fixed window during cycles, auto-range otherwise
    - Gentle downsampling to preserve detail in cycle of interest
    """

    average_channel_flag = False
    average_channel_ids = []
    # Gentle downsampling for cycle of interest (preserves more detail than sensorgram)
    subsample_threshold = 1001  # Higher threshold before downsampling kicks in
    subsample_target = 500  # Keep more data points when downsampling
    subsampling = False
    updating = False
    fixed_window_active = False
    dissoc_cursor_sig = Signal(str, float, float)
    assoc_cursor_sig = Signal(str, float, float)
    shift_values_signal = Signal(dict)  # Signal to emit shift values to display box

    @property
    def curves(self):
        """Provide list-based access to plot curves for compatibility.

        Returns list in channel order: [a, b, c, d]
        Maps to internal self.plots dictionary.
        """
        return [self.plots["a"], self.plots["b"], self.plots["c"], self.plots["d"]]

    def __init__(
        self,
        title_string,
        unit_string,
        show_title=False,
        parent=None,
        has_cursors=False,
    ):
        super(SegmentGraph, self).__init__(parent=parent)
        setConfigOptions(antialias=True)
        self.unit = unit_string

        # Set plot settings: maximize data view (no title/grid)
        if show_title:
            self.plot = self.addPlot(title=title_string)
            # Style title
            self.plot.titleLabel.setText(title_string, color=(30, 30, 30), size="11pt")
        else:
            self.plot = self.addPlot()
        self.plot.setDownsampling(ds=False, mode="subsample")
        self.plot.showGrid(x=False, y=False)
        self.plot.setLabel("left", f"Δ SPR ({unit_string})")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setMenuEnabled(True)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        self.plot.setAutoVisible(x=True, y=True)
        self.plots = {}

        # ViewBox performance optimizations for smooth rendering:
        # - Reduce update frequency during resize/pan/zoom
        # - Enable faster clipping (only render visible region)
        vb = self.plot.getViewBox()
        vb.setLimits(xMin=0)  # Time always positive
        vb.setMouseEnabled(x=True, y=True)

        # Ensure axes have space for labels - explicit sizing for visibility
        bottom_axis = self.plot.getAxis("bottom")
        left_axis = self.plot.getAxis("left")
        bottom_axis.setHeight(45)  # Increased space for 'Time (s)' label visibility
        left_axis.setWidth(55)  # Space for Y-axis label

        # Ensure label is visible
        bottom_axis.label.show()
        left_axis.label.show()

        # Set minimum Y-axis range (10 RU minimum)
        self.min_y_range = 10.0
        self.plot.getViewBox().sigRangeChanged.connect(self._enforce_min_range)

        # Set default Y-axis range for Cycle of Interest (-5 to 10 RU)
        self.plot.setYRange(-5, 10, padding=0)

        self.wait_to_update = False
        self.dissoc_cursors = {ch: {"Start": None, "End": None} for ch in CH_LIST}
        self.dissoc_cursor_en = False
        self.assoc_cursors = {ch: {"Start": None, "End": None} for ch in CH_LIST}
        self.assoc_cursor_en = False

        # Add crosshair cursor for precise measurements and zoom selection
        self.crosshair_enabled = True
        self.vLine = InfiniteLine(
            angle=90,
            movable=False,
            pen=mkPen("y", width=1, style=Qt.PenStyle.DashLine),
        )
        self.hLine = InfiniteLine(
            angle=0,
            movable=False,
            pen=mkPen("y", width=1, style=Qt.PenStyle.DashLine),
        )
        self.plot.addItem(self.vLine, ignoreBounds=True)
        self.plot.addItem(self.hLine, ignoreBounds=True)

        # Add text label for cursor coordinates
        from pyqtgraph import TextItem

        self.cursorLabel = TextItem(anchor=(0, 1), color="y")
        self.plot.addItem(self.cursorLabel)

        # Connect mouse movement to update crosshair
        self.plot.scene().sigMouseMoved.connect(self._update_crosshair)

        # Enable mouse tracking for crosshair
        self.plot.setMouseTracking(True)

        # Fixed annotation box for shift values (always visible in upper-left)
        self.shift_annotation = None
        for ch in CH_LIST:
            # Performance optimizations for smooth display:
            # - clipToView: Only render visible data (huge speedup for long cycles)
            # - autoDownsample: Automatic decimation when zoomed out
            # - connect='finite': Better handling of batch data gaps
            # - skipFiniteCheck: Faster rendering (data already validated)
            self.plots[ch] = self.plot.plot(
                pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
                connect="finite",
                clipToView=True,
                autoDownsample=True,
                skipFiniteCheck=True,
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
                            pen=mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3),
                            movable=True,
                        )
                        cursor_dict[ch][cursor].setHoverPen("y")
                        self.plot.addItem(cursor_dict[ch][cursor])
                        cursor_dict[ch][cursor].setVisible(False)
                    self.dissoc_cursors[ch][cursor].sigPositionChangeFinished.connect(
                        self.dissoc_update,
                    )
                    self.assoc_cursors[ch][cursor].sigPositionChangeFinished.connect(
                        self.assoc_update,
                    )

        # Create custom legend widget with checkboxes if title is shown
        self.legend_checkboxes = {}
        if show_title:
            self._create_legend_with_checkboxes(title_string)

        # Add Delta SPR overlay widget for real-time biosensing measurements
        self.delta_overlay = None
        self._create_delta_overlay()

    def _create_legend_with_checkboxes(self, title_string):
        """Create a custom legend with title and channel checkboxes."""
        # Create container widget for legend
        legend_widget = QWidget()
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setContentsMargins(8, 2, 8, 2)
        legend_layout.setSpacing(12)

        # Add title label (styled to match the plot title)
        from PySide6.QtWidgets import QLabel

        title_label = QLabel(title_string)
        title_label.setStyleSheet("""
            QLabel {
                color: rgb(30, 30, 30);
                font-size: 11pt;
                font-weight: bold;
                background: transparent;
            }
        """)
        legend_layout.addWidget(title_label)

        # Add spacer to push checkboxes to the right
        legend_layout.addStretch()

        # Create checkboxes for each channel with appropriate colors
        for ch in CH_LIST:
            checkbox = QCheckBox(f"Ch {ch.upper()}")
            checkbox.setChecked(True)  # All channels visible by default

            # Get color from settings
            color = settings.ACTIVE_GRAPH_COLORS[ch]
            if isinstance(color, tuple):
                color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
            else:
                color_str = color

            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {color_str};
                    font-weight: bold;
                    font-size: 9pt;
                    background: transparent;
                    spacing: 5px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                }}
            """)

            # Store reference to checkbox
            self.legend_checkboxes[ch] = checkbox

            # Connect to display_channel_changed method
            checkbox.stateChanged.connect(
                lambda state, channel=ch: self.display_channel_changed(
                    channel,
                    state == Qt.CheckState.Checked.value,
                ),
            )

            legend_layout.addWidget(checkbox)

        # Make widget background transparent
        legend_widget.setStyleSheet("background: transparent;")
        legend_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        legend_widget.setMaximumHeight(40)

        # Replace the title label with our custom legend widget
        # Hide the default title
        if hasattr(self.plot, "titleLabel"):
            self.plot.titleLabel.setVisible(False)

        # Add the legend widget as a graphics proxy to the plot
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(legend_widget)

        # Position it at the top of the plot area
        self.legend_proxy = proxy
        self.plot.scene().addItem(proxy)

        # Position the legend - will be adjusted in layout
        self._position_legend()

    def _position_legend(self):
        """Position the legend widget at the top of the graph."""
        if hasattr(self, "legend_proxy"):
            # Get the view box coordinates
            vb = self.plot.getViewBox()
            plot_rect = self.plot.sceneBoundingRect()

            # Position at top-left of the plot area
            x = plot_rect.left() + 10
            y = plot_rect.top() + 5

            self.legend_proxy.setPos(x, y)

    def _create_delta_overlay(self):
        """Create and position the Delta SPR overlay widget."""
        try:
            from affilabs.widgets.delta_spr_overlay import DeltaSPROverlay

            self.delta_overlay = DeltaSPROverlay()

            # Add as graphics proxy to plot
            overlay_proxy = QGraphicsProxyWidget()
            overlay_proxy.setWidget(self.delta_overlay)

            self.delta_overlay_proxy = overlay_proxy
            self.plot.scene().addItem(overlay_proxy)

            # Position in top-right corner
            self._position_delta_overlay()

        except Exception as e:
            logger.warning(f"Failed to create Delta SPR overlay: {e}")
            self.delta_overlay = None

    def _position_delta_overlay(self):
        """Position Delta SPR overlay in top-right corner of graph."""
        if hasattr(self, "delta_overlay_proxy") and self.delta_overlay:
            try:
                vb = self.plot.getViewBox()
                plot_rect = self.plot.sceneBoundingRect()

                # Position at top-right with padding
                x = plot_rect.right() - self.delta_overlay.width() - 15
                y = plot_rect.top() + 10

                self.delta_overlay_proxy.setPos(x, y)
            except Exception as e:
                logger.debug(f"Error positioning delta overlay: {e}")

    def update_delta_overlay(self, cycle_type=None, elapsed_sec=None, total_sec=None,
                           start_cursor_pos=None, end_cursor_pos=None):
        """Update Delta SPR overlay with current cycle information and measurements.

        Args:
            cycle_type: Type of cycle (Baseline, Association, etc.)
            elapsed_sec: Elapsed time in seconds
            total_sec: Total cycle duration in seconds
            start_cursor_pos: Start cursor time position in seconds
            end_cursor_pos: End cursor time position in seconds
        """
        if not self.delta_overlay:
            return

        try:
            # Update cycle info if provided
            if cycle_type and elapsed_sec is not None and total_sec is not None:
                self.delta_overlay.update_cycle_info(cycle_type, elapsed_sec, total_sec)

            # Calculate and update delta RU if cursor positions provided
            if start_cursor_pos is not None and end_cursor_pos is not None:
                delta_time = abs(end_cursor_pos - start_cursor_pos)
                self.delta_overlay.update_delta_time(delta_time)

                # Calculate delta RU for each channel (with ±2s averaging window)
                delta_values = {}
                for ch in CH_LIST:
                    if self.plots[ch].isVisible():
                        start_val = self._get_averaged_value(ch, start_cursor_pos, window_sec=2.0)
                        end_val = self._get_averaged_value(ch, end_cursor_pos, window_sec=2.0)
                        if start_val is not None and end_val is not None:
                            delta_values[ch] = end_val - start_val

                if delta_values:
                    self.delta_overlay.update_delta_ru(delta_values)

        except Exception as e:
            logger.debug(f"Error updating delta overlay: {e}")

    def _get_averaged_value(self, channel, time_pos, window_sec=2.0):
        """Get averaged value at time position using ±window_sec averaging.

        Args:
            channel: Channel identifier ('a', 'b', 'c', or 'd')
            time_pos: Time position in seconds
            window_sec: Half-width of averaging window in seconds

        Returns:
            Averaged value or None if insufficient data
        """
        try:
            import numpy as np

            # Get plot data
            x_data, y_data = self.plots[channel].getData()
            if x_data is None or y_data is None or len(x_data) == 0:
                return None

            # Find points within window
            x_data = np.array(x_data)
            y_data = np.array(y_data)
            mask = (x_data >= time_pos - window_sec) & (x_data <= time_pos + window_sec)

            if not np.any(mask):
                # No points in window, find closest point
                idx = np.argmin(np.abs(x_data - time_pos))
                return float(y_data[idx])

            # Return mean of points in window
            return float(np.mean(y_data[mask]))

        except Exception as e:
            logger.debug(f"Error getting averaged value: {e}")
            return None

    def update_colors(self):
        """Update plot and cursor colors when colorblind mode is toggled."""
        try:
            for ch in CH_LIST:
                # Update line colors for each channel
                self.plots[ch].setPen(
                    mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=2),
                )

                # Update checkbox colors in legend
                if ch in self.legend_checkboxes:
                    color = settings.ACTIVE_GRAPH_COLORS[ch]
                    if isinstance(color, tuple):
                        color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
                    else:
                        color_str = color

                    self.legend_checkboxes[ch].setStyleSheet(f"""
                        QCheckBox {{
                            color: {color_str};
                            font-weight: bold;
                            font-size: 9pt;
                            background: transparent;
                            spacing: 5px;
                        }}
                        QCheckBox::indicator {{
                            width: 16px;
                            height: 16px;
                        }}
                    """)

                # Update dissociation/association cursor colors if present
                for cursor in ["Start", "End"]:
                    if (
                        ch in self.dissoc_cursors
                        and self.dissoc_cursors[ch][cursor] is not None
                    ):
                        self.dissoc_cursors[ch][cursor].setPen(
                            mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3),
                        )
                    if (
                        ch in self.assoc_cursors
                        and self.assoc_cursors[ch][cursor] is not None
                    ):
                        self.assoc_cursors[ch][cursor].setPen(
                            mkPen(color=settings.ACTIVE_GRAPH_COLORS[ch], width=3),
                        )

            # Update Delta SPR overlay colors
            if self.delta_overlay:
                for ch in CH_LIST:
                    color = settings.ACTIVE_GRAPH_COLORS[ch]
                    if isinstance(color, tuple):
                        color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
                    else:
                        color_str = color

                    if ch in self.delta_overlay.channel_labels:
                        self.delta_overlay.channel_labels[ch].setStyleSheet(
                            f"font-size: 12px;"
                            f"font-weight: 600;"
                            f"color: {color_str};"
                            f"background: transparent;"
                            f"border: none;"
                            f"font-family: 'Consolas', 'Monaco', monospace;"
                        )
        except Exception as e:
            logger.debug(f"Error updating SegmentGraph colors: {e}")

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

    def _update_crosshair(self, evt):
        """Update crosshair position and label when mouse moves."""
        if not self.crosshair_enabled:
            return

        try:
            # Get mouse position in plot coordinates
            vb = self.plot.getViewBox()
            if vb.sceneBoundingRect().contains(evt):
                mousePoint = vb.mapSceneToView(evt)
                x, y = mousePoint.x(), mousePoint.y()

                # Update crosshair lines
                self.vLine.setPos(x)
                self.hLine.setPos(y)

                # Update label with coordinates
                self.cursorLabel.setText(f"Time: {x:.2f}s\nΔSPR: {y:.2f} {self.unit}")
                self.cursorLabel.setPos(x, y)

                # Show crosshair
                self.vLine.setVisible(True)
                self.hLine.setVisible(True)
                self.cursorLabel.setVisible(True)
            else:
                # Hide crosshair when mouse outside plot
                self.vLine.setVisible(False)
                self.hLine.setVisible(False)
                self.cursorLabel.setVisible(False)
        except Exception as e:
            logger.debug(f"Error updating crosshair: {e}")

    def toggle_crosshair(self, enabled: bool):
        """Enable or disable crosshair cursor."""
        self.crosshair_enabled = enabled
        if not enabled:
            self.vLine.setVisible(False)
            self.hLine.setVisible(False)
            self.cursorLabel.setVisible(False)

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
                    self.set_plot_pen(ch, settings.ACTIVE_GRAPH_COLORS[ch])
            if x_data is not None and y_data is not None:
                # Track min/max for visible channels to apply padding
                y_min = float("inf")
                y_max = float("-inf")
                x_min = float("inf")
                x_max = float("-inf")
                has_visible_data = False

                for ch in CH_LIST:
                    y = y_data[ch]
                    x = x_data[ch]
                    if len(x) == len(y) and len(x) > 0:
                        # Skip first point (same as live sensorgram on top)
                        if len(x) > 1:
                            plot_x = x[1:]
                            plot_y = y[1:]
                        else:
                            plot_x = x
                            plot_y = y

                        self.plots[ch].setData(y=plot_y, x=plot_x)
                        # Only consider visible channels for padding calculation
                        if self.plots[ch].isVisible():
                            has_visible_data = True
                            y_min = min(y_min, np.nanmin(plot_y))
                            y_max = max(y_max, np.nanmax(plot_y))
                            x_min = min(x_min, np.nanmin(plot_x))
                            x_max = max(x_max, np.nanmax(plot_x))

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
                    if hasattr(seg, "cycle_time") and seg.cycle_time is not None:
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
                        self.plot.setRange(
                            xRange=(padded_x_min, padded_x_max),
                            yRange=(padded_y_min, padded_y_max),
                            padding=0,
                        )
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
        """Enable intelligent auto-ranging with outlier detection.

        Uses 95th percentile scaling to ignore spikes/outliers automatically,
        eliminating the need for manual cursor-based Y-scale adjustment.
        """
        yrange = self.plot.viewRange()[1]
        self.plot.setRange(
            yRange=(yrange[0], yrange[1]),
            update=True,
            disableAutoRange=False,
        )

    def _calculate_smart_y_range(self, y_data_dict):
        """Calculate intelligent Y-axis range ignoring outliers.

        Args:
            y_data_dict: Dictionary of channel data {ch: y_array}

        Returns:
            tuple: (y_min, y_max) using 95th percentile to ignore spikes
        """
        try:
            # Collect all visible channel data
            all_data = []
            for ch, y_data in y_data_dict.items():
                if len(y_data) > 0 and self.plots.get(ch) and self.plots[ch].isVisible():
                    all_data.extend(y_data)

            if len(all_data) == 0:
                return (-5, 10)  # Default range

            all_data = np.array(all_data)

            # Use percentile-based range to ignore outliers/spikes
            # 2.5th and 97.5th percentiles capture 95% of data
            y_min = np.percentile(all_data, 2.5)
            y_max = np.percentile(all_data, 97.5)

            # Add 10% padding for visual comfort
            y_range = y_max - y_min
            y_min -= y_range * 0.1
            y_max += y_range * 0.1

            # Ensure minimum range of 10 RU
            if (y_max - y_min) < self.min_y_range:
                center = (y_min + y_max) / 2
                y_min = center - self.min_y_range / 2
                y_max = center + self.min_y_range / 2

            return (y_min, y_max)

        except Exception as e:
            logger.debug(f"Error calculating smart Y range: {e}")
            return (-5, 10)  # Fallback to default

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

        # Update checkbox state if it exists (without triggering signal)
        if ch in self.legend_checkboxes:
            self.legend_checkboxes[ch].blockSignals(True)
            self.legend_checkboxes[ch].setChecked(bool(flag))
            self.legend_checkboxes[ch].blockSignals(False)

        if self.dissoc_cursor_en:
            self.dissoc_cursors[ch]["Start"].setVisible(bool(flag))
            self.dissoc_cursors[ch]["End"].setVisible(bool(flag))
        if self.assoc_cursor_en:
            self.assoc_cursors[ch]["Start"].setVisible(bool(flag))
            self.assoc_cursors[ch]["End"].setVisible(bool(flag))

    def check_subsample(self, n):
        """Gentle downsampling for Cycle of Interest graph.
        Preserves more detail than the overview sensorgram since this is
        the detailed analysis view.
        """
        if n > self.subsample_threshold:
            # Use gentler downsampling factor for detail view
            factor = int(n / self.subsample_target)
            self.plot.setDownsampling(ds=factor)
            self.subsampling = True
            self.subsample_threshold += self.subsample_target
            logger.debug(
                f"Cycle of Interest downsample factor: {factor} (n={n}, preserving detail)",
            )

        if self.subsampling:
            if n < (2 * self.subsample_target):
                self.plot.setDownsampling(ds=False)
                self.subsampling = False
                self.subsample_threshold = 2 * self.subsample_target
                logger.debug("stopped downsampling Cycle of Interest plot")

    def reset_segment_graph(self, unit=None):
        for ch in CH_LIST:
            self.plots[ch].clear()
        if unit is None:
            unit = self.unit
        self.plot.setLabel("left", text=f"Δ SPR ({unit})")

        # Clear shift annotation
        self._clear_shift_annotation()

    def _clear_shift_annotation(self):
        """Remove the shift value annotation box from the graph."""
        if self.shift_annotation is not None:
            self.plot.removeItem(self.shift_annotation)
            self.shift_annotation = None

    def _update_shift_labels(self, seg, x_data, y_data):
        """Display shift values in annotation box on graph."""
        try:
            # Get shift values from the segment object (stored in seg.shift dict)
            if not hasattr(seg, "shift"):
                return

            # Build text for visible channels only
            text_lines = []
            for ch in CH_LIST:
                if self.plots[ch].isVisible():
                    shift_val = seg.shift.get(ch, 0.0)
                    color = settings.ACTIVE_GRAPH_COLORS[ch]
                    # Handle different color formats
                    if isinstance(color, str):
                        color_str = color
                    elif hasattr(color, "name"):
                        color_str = color.name()
                    elif isinstance(color, (tuple, list)) and len(color) == 3:
                        color_str = f"rgb({color[0]}, {color[1]}, {color[2]})"
                    else:
                        color_str = "black"
                    text_lines.append(
                        f'<span style="color: {color_str}">Ch {ch.upper()}: {shift_val:.2f} {self.unit}</span>',
                    )

            if text_lines:
                # Create or update annotation box
                from pyqtgraph import TextItem

                if self.shift_annotation is None:
                    self.shift_annotation = TextItem(anchor=(0, 0))
                    self.plot.addItem(self.shift_annotation)

                # Set HTML text with colored channel labels
                html_text = (
                    '<div style="background-color: rgba(255, 255, 255, 200); padding: 8px; border: 1px solid rgb(100, 100, 100); border-radius: 4px;">'
                    + "<br>".join(text_lines)
                    + "</div>"
                )
                self.shift_annotation.setHtml(html_text)

                # Position in upper-left corner of graph
                view_range = self.plot.viewRange()
                x_pos = view_range[0][0] + (view_range[0][1] - view_range[0][0]) * 0.02
                y_pos = view_range[1][1] - (view_range[1][1] - view_range[1][0]) * 0.02
                self.shift_annotation.setPos(x_pos, y_pos)
            else:
                # Clear annotation if no channels visible
                self._clear_shift_annotation()

            # Also emit signal for external display
            shift_data = {
                ch: seg.shift.get(ch, 0.0)
                for ch in CH_LIST
                if self.plots[ch].isVisible()
            }
            if shift_data:
                self.shift_values_signal.emit(shift_data)

        except Exception as e:
            logger.debug(f"Error updating shift annotation: {e}")
