"""
Test script to verify cycle marker rendering (gray zone and vertical lines).
Run this standalone to verify pyqtgraph rendering works correctly.
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QRadioButton, QButtonGroup
from PySide6.QtGui import QBrush, QColor
import pyqtgraph as pg
from pyqtgraph import PlotWidget, InfiniteLine, LinearRegionItem, mkPen
import numpy as np


class CycleMarkerTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cycle Marker Rendering Test")
        self.setGeometry(100, 100, 1200, 600)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Control buttons
        control_layout = QHBoxLayout()

        # Style selection
        self.style_group = QButtonGroup()
        self.cursors_radio = QRadioButton("Gray Zone (cursors)")
        self.lines_radio = QRadioButton("Vertical Lines")
        self.cursors_radio.setChecked(True)
        self.style_group.addButton(self.cursors_radio)
        self.style_group.addButton(self.lines_radio)

        control_layout.addWidget(self.cursors_radio)
        control_layout.addWidget(self.lines_radio)

        # Action buttons
        self.show_btn = QPushButton("Show Cycle Markers")
        self.hide_btn = QPushButton("Hide Cycle Markers")
        self.add_data_btn = QPushButton("Add Live Data")

        control_layout.addWidget(self.show_btn)
        control_layout.addWidget(self.hide_btn)
        control_layout.addWidget(self.add_data_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # Plot widget
        self.plot_widget = PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Response Units (RU)')
        self.plot_widget.setLabel('bottom', 'Time (seconds)')
        layout.addWidget(self.plot_widget)

        # Plot data
        self.plot = self.plot_widget.getPlotItem()

        # Generate initial data
        self.time_data = np.linspace(0, 100, 1000)
        self.signal_data = np.sin(self.time_data / 10) * 50 + 100
        self.data_curve = self.plot.plot(self.time_data, self.signal_data, pen=mkPen('b', width=2))

        # Cycle markers
        self.cycle_time_region = None
        self.cycle_start_line = None
        self.cycle_end_line = None
        self.left_cursor_pos = 20  # Simulated cursor position

        # Connect signals
        self.show_btn.clicked.connect(self.show_markers)
        self.hide_btn.clicked.connect(self.hide_markers)
        self.add_data_btn.clicked.connect(self.add_live_data)
        self.cursors_radio.toggled.connect(self.on_style_changed)

        print("✓ Test window initialized")
        print("  - Click 'Show Cycle Markers' to render markers")
        print("  - Toggle between Gray Zone and Vertical Lines")
        print("  - Click 'Add Live Data' to simulate live updates")

    def show_markers(self):
        """Show cycle markers based on selected style."""
        cycle_time_minutes = 1.0  # 1 minute cycle
        start_time = self.left_cursor_pos
        end_time = start_time + (cycle_time_minutes * 60)

        print(f"\n=== Showing Cycle Markers ===")
        print(f"Start: {start_time:.1f}s, End: {end_time:.1f}s")

        # Remove existing markers
        self.hide_markers()

        if self.lines_radio.isChecked():
            # Vertical line markers
            print("Mode: VERTICAL LINES")

            self.cycle_start_line = InfiniteLine(
                pos=start_time,
                angle=90,
                pen=mkPen('g', width=3, style=2),
                movable=False,
                label='Start',
                labelOpts={'position': 0.9, 'color': (0, 200, 0), 'movable': False}
            )

            self.cycle_end_line = InfiniteLine(
                pos=end_time,
                angle=90,
                pen=mkPen('r', width=3, style=2),
                movable=False,
                label='End',
                labelOpts={'position': 0.9, 'color': (200, 0, 0), 'movable': False}
            )

            self.cycle_start_line.setZValue(100)
            self.cycle_end_line.setZValue(100)

            self.plot.addItem(self.cycle_start_line)
            self.plot.addItem(self.cycle_end_line)
            print("✓ Vertical line markers added (green Start at z=100, red End at z=100)")
        else:
            # Gray shaded region
            print("Mode: GRAY ZONE (LinearRegionItem)")

            self.cycle_time_region = LinearRegionItem(
                values=[start_time, end_time],
                orientation='vertical',
                brush=QBrush(QColor(100, 100, 255, 40)),
                movable=False
            )
            self.cycle_time_region.setZValue(-10)
            self.plot.addItem(self.cycle_time_region)
            print("✓ Gray shaded region added (LinearRegionItem at z=-10)")

        # Force update
        self.plot.update()
        self.plot.getViewBox().update()
        print("✓ Plot updated")

    def hide_markers(self):
        """Hide all cycle markers."""
        print("\n=== Hiding Cycle Markers ===")

        if self.cycle_time_region is not None:
            self.plot.removeItem(self.cycle_time_region)
            self.cycle_time_region = None
            print("✓ Removed gray zone")

        if self.cycle_start_line is not None:
            self.plot.removeItem(self.cycle_start_line)
            self.cycle_start_line = None
            print("✓ Removed start line")

        if self.cycle_end_line is not None:
            self.plot.removeItem(self.cycle_end_line)
            self.cycle_end_line = None
            print("✓ Removed end line")

    def on_style_changed(self):
        """Re-render markers when style changes."""
        # Only re-render if markers are currently visible
        if self.cycle_time_region or self.cycle_start_line or self.cycle_end_line:
            print("\n=== Style Changed - Re-rendering ===")
            self.show_markers()

    def add_live_data(self):
        """Simulate adding live data to test auto-ranging."""
        print("\n=== Adding Live Data ===")
        # Extend time data
        last_time = self.time_data[-1]
        new_time = np.linspace(last_time, last_time + 10, 100)
        new_signal = np.sin(new_time / 10) * 50 + 100 + np.random.randn(100) * 5

        self.time_data = np.concatenate([self.time_data, new_time])
        self.signal_data = np.concatenate([self.signal_data, new_signal])

        # Update plot
        self.data_curve.setData(self.time_data, self.signal_data)
        print(f"✓ Added data up to {self.time_data[-1]:.1f}s")


def main():
    print("=" * 60)
    print("Cycle Marker Rendering Test")
    print("=" * 60)
    print("\nThis test verifies that:")
    print("1. Gray zone (LinearRegionItem) renders properly")
    print("2. Vertical lines (InfiniteLine) render properly")
    print("3. Switching between modes works dynamically")
    print("4. Markers persist during live data updates")
    print("\nExpected Results:")
    print("  - Gray zone: Semi-transparent blue region between cursors")
    print("  - Vertical lines: Green dashed 'Start', red dashed 'End'")
    print("  - Both should be visible and not hidden by data")
    print("=" * 60)

    app = QApplication(sys.argv)
    window = CycleMarkerTest()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
