"""Modern PyQtGraph Styling Configuration
Professional scientific plotting appearance
"""

import pyqtgraph as pg

from .design_system import *


def apply_modern_graph_style():
    """Apply modern styling to all PyQtGraph plots."""
    # Enable antialiasing for smooth lines
    pg.setConfigOptions(
        antialias=True,
        foreground="#1F2937",  # TEXT_PRIMARY
        background="#FFFFFF",  # SURFACE (white)
    )

    return {
        "background": SURFACE,
        "foreground": TEXT_PRIMARY,
        "antialias": True,
    }


def get_modern_plot_style():
    """Get styling dict for individual plots."""
    return {
        "background": SURFACE,
        "foreground": TEXT_PRIMARY,
        "axisColor": AXIS_COLOR,
        "gridAlpha": 0.1,
        "gridColor": GRID_COLOR,
    }


def create_modern_pen(color, width=2):
    """Create a pen with modern styling."""
    from pyqtgraph import mkPen

    return mkPen(color=color, width=width)


def create_channel_pens():
    """Create pens for each channel with modern colors."""
    from pyqtgraph import mkPen

    return {
        "a": mkPen(color=CHANNEL_A, width=2),
        "b": mkPen(color=CHANNEL_B, width=2),
        "c": mkPen(color=CHANNEL_C, width=2),
        "d": mkPen(color=CHANNEL_D, width=2),
    }


def get_cursor_style():
    """Get styling for cursors/infinite lines."""
    from pyqtgraph import mkPen

    return {
        "left_cursor": mkPen(
            color=CURSOR_COLOR,
            width=2,
            style=pg.QtCore.Qt.PenStyle.DashLine,
        ),
        "right_cursor": mkPen(
            color=CURSOR_COLOR,
            width=2,
            style=pg.QtCore.Qt.PenStyle.DashLine,
        ),
    }


def style_plot_widget(plot_widget):
    """Apply modern styling to a PlotWidget."""
    # Set background
    plot_widget.setBackground(SURFACE)

    # Get plot item
    plot_item = plot_widget.getPlotItem()

    # Style axes
    for axis in ["left", "bottom", "right", "top"]:
        ax = plot_item.getAxis(axis)
        ax.setPen(AXIS_COLOR)
        ax.setTextPen(TEXT_PRIMARY)

    # Style grid
    plot_item.showGrid(x=True, y=True, alpha=0.15)

    # Title style
    plot_item.titleLabel.item.setDefaultTextColor(TEXT_PRIMARY)

    return plot_widget


def get_graph_colors():
    """Get modern color palette for graphs."""
    return {
        "channel_a": CHANNEL_A,
        "channel_b": CHANNEL_B,
        "channel_c": CHANNEL_C,
        "channel_d": CHANNEL_D,
        "cursor": CURSOR_COLOR,
        "grid": GRID_COLOR,
        "axis": AXIS_COLOR,
        "background": SURFACE,
        "text": TEXT_PRIMARY,
        "selection": SELECTION_COLOR,
    }


# Pre-configured plot settings
MODERN_PLOT_CONFIG = {
    "antialias": True,
    "background": SURFACE,
    "foreground": TEXT_PRIMARY,
    "pen": {"color": PRIMARY, "width": 2},
}

# Axis configuration
MODERN_AXIS_CONFIG = {
    "pen": AXIS_COLOR,
    "textPen": TEXT_PRIMARY,
}

# Grid configuration
MODERN_GRID_CONFIG = {
    "x": True,
    "y": True,
    "alpha": 0.15,
}
