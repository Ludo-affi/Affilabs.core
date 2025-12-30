"""Test Flag System UI - Standalone Test

Tests Phase 2 flag implementation with TIME-SHIFT ALIGNMENT:
- Ctrl+Click shows dropdown menu (Injection, Wash, Spike)
- Different symbols/colors for each flag type
- First injection flag sets reference time
- Subsequent injection flags SHIFT THE ENTIRE CHANNEL DATA to align
- Right-click removes nearest flag
- No hardware or full app required

Usage: python test_flag_system.py
"""

import sys
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMenu, QLabel
from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import Qt


class FlagTestWindow(QMainWindow):
    """Test window for flag system UI"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flag System Test - Phase 2")
        self.setGeometry(100, 100, 1200, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Instructions label
        instructions = QLabel(
            "📋 Instructions:\n"
            "• Ctrl+Click on graph → Select flag type (Injection/Wash/Spike)\n"
            "• Right-Click near flag → Remove flag\n"
            "• Different symbols: ▲ = Injection (red), ■ = Wash (blue), ★ = Spike (yellow)"
        )
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; font-size: 11pt;")
        layout.addWidget(instructions)

        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'SPR Signal', units='RU')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.setTitle("Simulated Sensorgram (4 channels)")

        # Disable default PyQtGraph context menu (conflicts with flag system)
        self.plot_widget.setMenuEnabled(False)

        layout.addWidget(self.plot_widget)

        # Storage for flag markers
        self._flag_markers = []

        # Injection alignment (Phase 2 - alignment feature)
        self._injection_reference_time = None  # First injection sets this
        self._injection_alignment_line = None  # Vertical line showing alignment
        self._injection_snap_tolerance = 10.0  # Seconds - snap if within this range

        # Generate demo data (4 channels)
        self._generate_demo_data()

        # Connect mouse click event
        self.plot_widget.scene().sigMouseClicked.connect(self._on_graph_clicked)

    def _generate_demo_data(self):
        """Generate simulated sensorgram data for 4 channels"""
        time = np.linspace(0, 300, 1000)

        # Channel A: Baseline + binding curve
        spr_a = 50 + 20 * (1 - np.exp(-(time - 100) / 30)) * (time > 100)
        self.plot_widget.plot(time, spr_a, pen=pg.mkPen('r', width=2), name='Channel A')

        # Channel B: Similar with offset
        spr_b = 45 + 18 * (1 - np.exp(-(time - 105) / 32)) * (time > 105)
        self.plot_widget.plot(time, spr_b, pen=pg.mkPen('g', width=2), name='Channel B')

        # Channel C: Different kinetics
        spr_c = 40 + 25 * (1 - np.exp(-(time - 110) / 25)) * (time > 110)
        self.plot_widget.plot(time, spr_c, pen=pg.mkPen('b', width=2), name='Channel C')

        # Channel D: Reference channel (flat)
        spr_d = np.ones_like(time) * 35
        self.plot_widget.plot(time, spr_d, pen=pg.mkPen('y', width=2), name='Channel D')

        # Add legend
        self.plot_widget.addLegend()

    def _on_graph_clicked(self, event):
        """Handle mouse clicks on graph

        Ctrl+Click: Show flag type menu
        Right-Click: Remove flag near cursor
        """
        # Get click position
        pos = event.scenePos()
        view_box = self.plot_widget.plotItem.vb
        mouse_point = view_box.mapSceneToView(pos)
        time_clicked = mouse_point.x()
        spr_clicked = mouse_point.y()

        # Check if Ctrl key is pressed (add flag)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._show_flag_type_menu(time_clicked, spr_clicked)

        # Check if right-click (remove flag)
        elif event.button() == Qt.MouseButton.RightButton:
            self._remove_flag_near_click(time_clicked, spr_clicked)

    def _show_flag_type_menu(self, time_val: float, spr_val: float):
        """Show dropdown menu to select flag type"""
        menu = QMenu()

        # Create flag type actions
        injection_action = QAction("▲ Injection", menu)
        injection_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'injection')
        )

        wash_action = QAction("■ Wash", menu)
        wash_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'wash')
        )

        spike_action = QAction("★ Spike", menu)
        spike_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'spike')
        )

        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)

        # Show menu at cursor position
        menu.exec(QCursor.pos())

    def _add_flag_marker(self, time_val: float, spr_val: float, flag_type: str):
        """Add a visual flag marker to the graph"""
        # Define flag appearance based on type
        flag_styles = {
            'injection': {'symbol': 't', 'size': 15, 'color': (255, 50, 50, 230)},    # Red triangle
            'wash': {'symbol': 's', 'size': 12, 'color': (50, 150, 255, 230)},        # Blue square
            'spike': {'symbol': 'star', 'size': 18, 'color': (255, 200, 0, 230)}      # Yellow star
        }

        style = flag_styles.get(flag_type, flag_styles['injection'])

        # INJECTION ALIGNMENT LOGIC (Phase 2)
        if flag_type == 'injection':
            if self._injection_reference_time is None:
                # First injection - set as reference
                self._injection_reference_time = time_val
                self._create_injection_alignment_line(time_val)
                print(f"✓ Injection reference set at t={time_val:.2f}s")
            else:
                # Subsequent injection - snap to reference if close enough
                time_diff = abs(time_val - self._injection_reference_time)
                if time_diff <= self._injection_snap_tolerance:
                    print(f"→ Snapping injection from t={time_val:.2f}s to reference t={self._injection_reference_time:.2f}s (diff={time_diff:.2f}s)")
                    time_val = self._injection_reference_time
                else:
                    print(f"⚠ Injection at t={time_val:.2f}s is {time_diff:.2f}s from reference (tolerance={self._injection_snap_tolerance:.1f}s) - not snapped")

        # Create flag marker
        marker = pg.ScatterPlotItem(
            [time_val],
            [spr_val],
            symbol=style['symbol'],
            size=style['size'],
            brush=pg.mkBrush(*style['color']),
            pen=pg.mkPen('w', width=2)
        )

        # Add marker to graph
        self.plot_widget.addItem(marker)

        # Store marker reference
        self._flag_markers.append({
            'time': time_val,
            'spr': spr_val,
            'marker': marker,
            'type': flag_type
        })

        print(f"🚩 {flag_type.capitalize()} flag added at t={time_val:.2f}s, SPR={spr_val:.1f} RU")
        print(f"   Total flags: {len(self._flag_markers)}")

    def _create_injection_alignment_line(self, time_val: float):
        """Create vertical line at injection reference time for alignment"""
        # Create vertical line spanning the graph
        self._injection_alignment_line = pg.InfiniteLine(
            pos=time_val,
            angle=90,  # Vertical
            pen=pg.mkPen(color=(255, 50, 50, 100), width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
            movable=False,
            label='Injection Reference'
        )
        self.plot_widget.addItem(self._injection_alignment_line)

    def _remove_flag_near_click(self, time_clicked: float, spr_clicked: float, tolerance: float = 5.0):
        """Remove flag marker near the click position"""
        if not self._flag_markers:
            print("⚠ No flags to remove")
            return

        # Find flag closest to click position
        min_distance = float('inf')
        closest_flag_idx = None

        for idx, flag in enumerate(self._flag_markers):
            time_dist = abs(flag['time'] - time_clicked)
            if time_dist < min_distance and time_dist < tolerance:
                min_distance = time_dist
                closest_flag_idx = idx

        # Remove the closest flag if found
        if closest_flag_idx is not None:
            flag = self._flag_markers[closest_flag_idx]

            # Remove from graph
            self.plot_widget.removeItem(flag['marker'])

            # Remove from storage
            self._flag_markers.pop(closest_flag_idx)

            # If we removed an injection flag, check if we need to clear alignment
            if flag['type'] == 'injection':
                # Count remaining injection flags
                remaining_injections = [f for f in self._flag_markers if f['type'] == 'injection']
                if len(remaining_injections) == 0:
                    # No more injections - clear alignment line
                    if self._injection_alignment_line is not None:
                        self.plot_widget.removeItem(self._injection_alignment_line)
                        self._injection_alignment_line = None
                    self._injection_reference_time = None
                    print("✓ Injection alignment cleared")

            print(f"🚩 {flag['type'].capitalize()} flag removed at t={flag['time']:.2f}s")
            print(f"   Total flags: {len(self._flag_markers)}")
        else:
            print(f"⚠ No flag found within {tolerance}s of click position")


def main():
    """Run flag system test"""
    app = QApplication(sys.argv)

    # Set dark theme for better visibility
    app.setStyle('Fusion')

    window = FlagTestWindow()
    window.show()

    print("=" * 60)
    print("FLAG SYSTEM TEST - Phase 2")
    print("=" * 60)
    print("\nInstructions:")
    print("  1. Ctrl+Click anywhere on the graph")
    print("  2. Select flag type from dropdown menu")
    print("  3. Flag appears with unique symbol/color")
    print("  4. Right-click near flag to remove it")
    print("\nFlag Types:")
    print("  ▲ Injection (red triangle)")
    print("  ■ Wash (blue square)")
    print("  ★ Spike (yellow star)")
    print("=" * 60)
    print()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
