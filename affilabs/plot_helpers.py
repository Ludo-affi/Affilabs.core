"""Plot helper functions extracted from LL_UI_v1_0.py to reduce duplication."""

import pyqtgraph as pg

from affilabs.ui_styles import Colors

AXIS_COLOR = "#86868B"
GRID_ALPHA = 0.15
AXIS_PEN_COLOR = "#E5E5EA"

# Default channel colors (Black, Red, Blue, Green)
CHANNEL_COLORS = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]

# Colorblind-friendly palette (ColorBrewer PuOr divergent) - matches settings.GRAPH_COLORS_COLORBLIND
# Ch A: Dark Orange #e66101, Ch B: Light Orange #fdb863, Ch C: Light Purple #b2abd2, Ch D: Dark Purple #5e3c99
CHANNEL_COLORS_COLORBLIND = ["#e66101", "#fdb863", "#b2abd2", "#5e3c99"]


def create_time_plot(
    left_label: str,
    bottom_label: str = "Time (seconds)",
    left_size: str = "11pt",
    size: str = None,
) -> pg.PlotWidget:
    """Create a standardized time-series plot widget."""
    # Allow overriding both axes size with 'size' parameter
    if size is not None:
        left_size = size
        bottom_size = size
    else:
        bottom_size = left_size

    w = pg.PlotWidget()
    w.setBackground(Colors.BACKGROUND_WHITE)
    w.setLabel("left", left_label, color=AXIS_COLOR, size=left_size)
    w.setLabel("bottom", bottom_label, color=AXIS_COLOR, size=bottom_size)
    w.showGrid(x=False, y=False, alpha=GRID_ALPHA)  # Grid OFF by default
    w.getPlotItem().getAxis("left").setPen(color=AXIS_PEN_COLOR, width=1)
    w.getPlotItem().getAxis("bottom").setPen(color=AXIS_PEN_COLOR, width=1)
    w.getPlotItem().getAxis("left").setTextPen(AXIS_COLOR)
    w.getPlotItem().getAxis("bottom").setTextPen(AXIS_COLOR)

    # Don't enable Y-axis autorange initially to prevent slope from 0
    # Will be enabled dynamically when first data arrives

    return w


def add_channel_curves(plot: pg.PlotWidget, clickable: bool = False, width: int = 2):
    """Add four channel curves to a plot and return list of curve refs."""
    curves = []
    for i, color in enumerate(CHANNEL_COLORS):
        curve = plot.plot(
            pen=pg.mkPen(color=color, width=width),
            name=f"Channel {chr(65+i)}",
            connect="finite",  # Skip NaN/Inf values, prevents vertical lines from missing data
        )
        curve.original_color = color
        curve.original_pen = pg.mkPen(color=color, width=width)
        curve.selected_pen = pg.mkPen(color=color, width=width + 2)
        curve.channel_index = i

        # PERFORMANCE OPTIMIZATION: Enable clipToView and autoDownsample
        # clipToView=True: Only render data points visible in current view (CRITICAL for performance)
        # autoDownsample=True: Intelligently downsample when zoomed out
        # connect='finite': Skip NaN/Inf, prevents artifacts from missing data
        curve.setClipToView(True)
        curve.setDownsampling(
            auto=True,
            method="subsample",
        )  # 'subsample' better for smooth curves

        # Clickable curve support (caller connects signals)
        if clickable:
            try:
                curve.setCurveClickable(True, width=10)
            except Exception:
                pass
        curves.append(curve)
    return curves


def create_spectroscopy_plot(
    left_label: str,
    bottom_label: str,
    size: str = "10pt",
    detector_type: str = "USB4000",
) -> pg.PlotWidget:
    """Create standardized spectroscopy (wavelength) plot.

    Args:
        left_label: Label for y-axis
        bottom_label: Label for x-axis
        size: Font size for labels
        detector_type: Type of detector ("USB4000" or "PhasePhotonics")
    """
    plot = pg.PlotWidget()
    plot.setBackground(Colors.BACKGROUND_WHITE)
    plot.setLabel("left", left_label, color=AXIS_COLOR, size=size)
    plot.setLabel("bottom", bottom_label, color=AXIS_COLOR, size=size)
    plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    plot.getPlotItem().getAxis("left").setPen(color=AXIS_PEN_COLOR, width=1)
    plot.getPlotItem().getAxis("bottom").setPen(color=AXIS_PEN_COLOR, width=1)
    plot.getPlotItem().getAxis("left").setTextPen(AXIS_COLOR)
    plot.getPlotItem().getAxis("bottom").setTextPen(AXIS_COLOR)

    # Set x-axis range based on detector type
    if "Phase" in detector_type or "ST" in detector_type:
        # PhasePhotonics detector: start at 570 nm
        plot.setXRange(570, 720, padding=0)
    else:
        # USB4000: full range
        plot.setXRange(560, 720, padding=0)

    # Enable autorange for y-axis only
    try:
        plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
    except Exception:
        plot.enableAutoRange("y", True)

    return plot
