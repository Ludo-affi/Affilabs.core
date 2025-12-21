"""Test Flag System UI - With Time-Shift Alignment

Tests Phase 2 flag implementation with TIME-SHIFT ALIGNMENT:
- Ctrl+Click shows dropdown menu (Injection, Wash, Spike)
- Different symbols/colors for each flag type  
- First injection flag sets reference time
- Subsequent injection flags SHIFT THE ENTIRE CHANNEL DATA to align
- Right-click removes nearest flag

Usage: python test_flag_system_v2.py
"""

import sys
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMenu, QLabel
from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import Qt


class FlagTestWindow(QMainWindow):
    """Test window for flag system UI with time-shift alignment"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flag System Test - Phase 2 (Time-Shift Alignment)")
        self.setGeometry(100, 100, 1200, 600)
        
        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Instructions label
        instructions = QLabel(
            "📋 Instructions:\n"
            "• Ctrl+Click on graph → Select flag type (Injection/Wash/Spike)\n"
            "• First INJECTION flag → Sets reference time (red dashed line)\n"
            "• Subsequent INJECTION flags → SHIFTS ENTIRE CHANNEL to align\n"
            "• Right-Click near flag → Remove flag\n"
            "• Symbols: ▲ = Injection (red), ■ = Wash (blue), ★ = Spike (yellow)"
        )
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; font-size: 11pt;")
        layout.addWidget(instructions)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'SPR Signal', units='RU')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.setTitle("Simulated Sensorgram (4 channels) - Try injections at different times!")
        
        # Disable default context menu
        self.plot_widget.setMenuEnabled(False)
        
        layout.addWidget(self.plot_widget)
        
        # Storage for flag markers
        self._flag_markers = []
        
        # Injection alignment (Phase 2 - time-shift alignment)
        self._injection_reference_time = None
        self._injection_reference_channel = None
        self._injection_alignment_line = None
        self._injection_snap_tolerance = 15.0  # Seconds
        
        # Channel data and plots
        self._channel_data = {}  # Original unshifted data
        self._channel_plots = {}  # Plot items to update
        self._channel_offsets = {'A': 0.0, 'B': 0.0, 'C': 0.0, 'D': 0.0}
        
        # Generate demo data
        self._generate_demo_data()
        
        # Connect mouse click event
        self.plot_widget.scene().sigMouseClicked.connect(self._on_graph_clicked)
    
    def _generate_demo_data(self):
        """Generate simulated sensorgram data for 4 channels"""
        time = np.linspace(0, 300, 1000)
        
        # Channel A: Injection at t=100s
        spr_a = 50 + 20 * (1 - np.exp(-(time - 100) / 30)) * (time > 100)
        plot_a = self.plot_widget.plot(time, spr_a, pen=pg.mkPen('r', width=2), name='Channel A')
        self._channel_data['A'] = {'time': time.copy(), 'spr': spr_a.copy()}
        self._channel_plots['A'] = plot_a
        
        # Channel B: Injection at t=105s (5s later)
        spr_b = 45 + 18 * (1 - np.exp(-(time - 105) / 32)) * (time > 105)
        plot_b = self.plot_widget.plot(time, spr_b, pen=pg.mkPen('g', width=2), name='Channel B')
        self._channel_data['B'] = {'time': time.copy(), 'spr': spr_b.copy()}
        self._channel_plots['B'] = plot_b
        
        # Channel C: Injection at t=110s (10s later)
        spr_c = 40 + 25 * (1 - np.exp(-(time - 110) / 25)) * (time > 110)
        plot_c = self.plot_widget.plot(time, spr_c, pen=pg.mkPen('b', width=2), name='Channel C')
        self._channel_data['C'] = {'time': time.copy(), 'spr': spr_c.copy()}
        self._channel_plots['C'] = plot_c
        
        # Channel D: Injection at t=98s (2s earlier)
        spr_d = 35 + 15 * (1 - np.exp(-(time - 98) / 28)) * (time > 98)
        plot_d = self.plot_widget.plot(time, spr_d, pen=pg.mkPen('y', width=2), name='Channel D')
        self._channel_data['D'] = {'time': time.copy(), 'spr': spr_d.copy()}
        self._channel_plots['D'] = plot_d
        
        # Add legend
        self.plot_widget.addLegend()
    
    def _on_graph_clicked(self, event):
        """Handle mouse clicks on graph"""
        pos = event.scenePos()
        view_box = self.plot_widget.plotItem.vb
        mouse_point = view_box.mapSceneToView(pos)
        time_clicked = mouse_point.x()
        spr_clicked = mouse_point.y()
        
        # Find nearest channel
        clicked_channel = self._find_nearest_channel(time_clicked, spr_clicked)
        
        # Ctrl+Click: Add flag
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._show_flag_type_menu(time_clicked, spr_clicked, clicked_channel)
        
        # Right-click: Remove flag
        elif event.button() == Qt.MouseButton.RightButton:
            self._remove_flag_near_click(time_clicked, spr_clicked)
    
    def _find_nearest_channel(self, time_clicked: float, spr_clicked: float) -> str:
        """Find which channel curve is closest to click"""
        min_distance = float('inf')
        nearest_channel = 'A'
        
        for ch_name, ch_data in self._channel_data.items():
            offset = self._channel_offsets[ch_name]
            shifted_time = ch_data['time'] + offset
            time_idx = np.argmin(np.abs(shifted_time - time_clicked))
            
            spr_at_time = ch_data['spr'][time_idx]
            distance = abs(spr_at_time - spr_clicked)
            
            if distance < min_distance:
                min_distance = distance
                nearest_channel = ch_name
        
        return nearest_channel
    
    def _show_flag_type_menu(self, time_val: float, spr_val: float, channel: str):
        """Show dropdown menu to select flag type"""
        menu = QMenu()
        
        injection_action = QAction("▲ Injection", menu)
        injection_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'injection', channel)
        )
        
        wash_action = QAction("■ Wash", menu)
        wash_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'wash', channel)
        )
        
        spike_action = QAction("★ Spike", menu)
        spike_action.triggered.connect(
            lambda: self._add_flag_marker(time_val, spr_val, 'spike', channel)
        )
        
        menu.addAction(injection_action)
        menu.addAction(wash_action)
        menu.addAction(spike_action)
        
        menu.exec(QCursor.pos())
    
    def _add_flag_marker(self, time_val: float, spr_val: float, flag_type: str, channel: str):
        """Add flag marker and apply time-shift alignment if injection"""
        flag_styles = {
            'injection': {'symbol': 't', 'size': 15, 'color': (255, 50, 50, 230)},
            'wash': {'symbol': 's', 'size': 12, 'color': (50, 150, 255, 230)},
            'spike': {'symbol': 'star', 'size': 18, 'color': (255, 200, 0, 230)}
        }
        
        style = flag_styles.get(flag_type, flag_styles['injection'])
        
        # TIME-SHIFT ALIGNMENT for injections
        if flag_type == 'injection':
            if self._injection_reference_time is None:
                # First injection - set reference
                self._injection_reference_time = time_val
                self._injection_reference_channel = channel
                self._create_injection_alignment_line(time_val)
                print(f"✓ Injection reference: Channel {channel} at t={time_val:.2f}s")
            else:
                # Subsequent injection - shift channel to align
                time_diff = time_val - self._injection_reference_time
                
                if abs(time_diff) <= self._injection_snap_tolerance:
                    # Calculate offset and shift data
                    offset = -time_diff
                    self._channel_offsets[channel] += offset
                    self._shift_channel_data(channel)
                    
                    # Update marker position to aligned time
                    time_val = self._injection_reference_time
                    
                    print(f"→ Channel {channel} shifted {offset:+.2f}s")
                    print(f"  Now aligned at t={self._injection_reference_time:.2f}s")
                    print(f"  Total offset: {self._channel_offsets[channel]:+.2f}s")
                else:
                    print(f"⚠ Injection {abs(time_diff):.2f}s from reference - outside tolerance")
        
        # Create marker
        marker = pg.ScatterPlotItem(
            [time_val], [spr_val],
            symbol=style['symbol'],
            size=style['size'],
            brush=pg.mkBrush(*style['color']),
            pen=pg.mkPen('w', width=2)
        )
        
        self.plot_widget.addItem(marker)
        
        self._flag_markers.append({
            'time': time_val,
            'spr': spr_val,
            'marker': marker,
            'type': flag_type,
            'channel': channel
        })
        
        print(f"🚩 {flag_type.capitalize()} added: Ch {channel} at t={time_val:.2f}s")
    
    def _shift_channel_data(self, channel: str):
        """Shift channel's time axis and update plot"""
        offset = self._channel_offsets[channel]
        original = self._channel_data[channel]
        
        shifted_time = original['time'] + offset
        
        # Update plot
        self._channel_plots[channel].setData(shifted_time, original['spr'])
    
    def _create_injection_alignment_line(self, time_val: float):
        """Create vertical alignment line"""
        self._injection_alignment_line = pg.InfiniteLine(
            pos=time_val,
            angle=90,
            pen=pg.mkPen(color=(255, 50, 50, 100), width=2, style=Qt.PenStyle.DashLine),
            movable=False,
            label='Injection Reference'
        )
        self.plot_widget.addItem(self._injection_alignment_line)
    
    def _remove_flag_near_click(self, time_clicked: float, spr_clicked: float, tolerance: float = 5.0):
        """Remove flag near click position using 2D distance"""
        if not self._flag_markers:
            return
        
        min_distance = float('inf')
        closest_idx = None
        
        # Get view ranges to normalize distances
        view_range = self.plot_widget.viewRange()
        time_range = view_range[0][1] - view_range[0][0]
        spr_range = view_range[1][1] - view_range[1][0]
        
        for idx, flag in enumerate(self._flag_markers):
            # Calculate normalized 2D distance
            time_dist = abs(flag['time'] - time_clicked) / time_range
            spr_dist = abs(flag['spr'] - spr_clicked) / spr_range
            distance = np.sqrt(time_dist**2 + spr_dist**2)
            
            if distance < min_distance:
                min_distance = distance
                closest_idx = idx
        
        # Only remove if close enough (tolerance in normalized units)
        if closest_idx is not None and min_distance < 0.02:  # 2% of screen diagonal
            flag = self._flag_markers[closest_idx]
            self.plot_widget.removeItem(flag['marker'])
            self._flag_markers.pop(closest_idx)
            
            # If last injection removed, clear alignment
            if flag['type'] == 'injection':
                remaining = [f for f in self._flag_markers if f['type'] == 'injection']
                if len(remaining) == 0:
                    if self._injection_alignment_line:
                        self.plot_widget.removeItem(self._injection_alignment_line)
                    self._injection_reference_time = None
                    self._injection_reference_channel = None
                    print("✓ Injection alignment cleared")
            
            print(f"🚩 {flag['type'].capitalize()} removed: Ch {flag['channel']}")


def main():
    """Run flag system test"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = FlagTestWindow()
    window.show()
    
    print("=" * 70)
    print("FLAG SYSTEM TEST - Phase 2 (TIME-SHIFT ALIGNMENT)")
    print("=" * 70)
    print("\nInstructions:")
    print("  1. Ctrl+Click on any channel curve")
    print("  2. Select 'Injection' from menu")
    print("  3. First injection → Sets reference time (red dashed line)")
    print("  4. Ctrl+Click on DIFFERENT channel curves")
    print("  5. Select 'Injection' → Watch the CURVE SHIFT to align!")
    print("\nNotice:")
    print("  - Channels start at different injection times:")
    print("    • Channel A: ~100s")
    print("    • Channel B: ~105s (5s later)")
    print("    • Channel C: ~110s (10s later)")
    print("    • Channel D: ~98s (2s earlier)")
    print("  - When you flag injections, curves shift to align perfectly!")
    print("=" * 70)
    print()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
