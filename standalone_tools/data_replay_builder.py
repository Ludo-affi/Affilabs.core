"""Data Replay Tab Builder

Handles building the Data Replay tab UI for importing and playing back historical experiment data.

Features:
- Load Excel files with cycle data
- Replay data as an animated playback
- Export as GIF or PNG
- Playback controls (play, pause, speed, scrubber)
- Cycle navigation and info display

Author: Affilabs
"""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QComboBox,
    QFileDialog,
    QSpinBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
import pandas as pd
import numpy as np

from affilabs.sections import CollapsibleSection
from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    label_style,
    primary_button_style,
    section_header_style,
)
from affilabs.plot_helpers import CHANNEL_COLORS

try:
    import pyqtgraph as pg
except ImportError:
    pg = None


class DataReplayTabBuilder:
    """Builder for constructing the Data Replay tab UI."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to

        """
        self.sidebar = sidebar
        self.loaded_data = None  # Store loaded Excel data
        self.cycles_df = None  # Cycle metadata
        self.time_data = None  # Time array (numpy)
        self.channel_data = {}  # Dict of channel_name -> wavelength array
        self.cycle_boundaries = []  # [(start_idx, end_idx), ...]
        self.channel_visible = {'Channel_A': True, 'Channel_B': True, 'Channel_C': True, 'Channel_D': True}
        
        self.current_cycle_idx = 0
        self.current_frame = 0
        self.total_frames = 0
        self.is_playing = False
        self.playback_speed = 1  # 1x, 2x, 5x, 10x
        
        # Playback timer
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self._advance_frame)
        
        # Graph plot curves (one per channel)
        self.plot_curves = {}  # Dict of channel_name -> curve

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Data Replay tab UI.

        Args:
            tab_layout: QVBoxLayout to add replay tab widgets to

        """
        self._build_load_section(tab_layout)
        self._build_playback_section(tab_layout)
        self._build_cycle_info_section(tab_layout)
        self._build_export_section(tab_layout)
        
        tab_layout.addStretch()

    def _build_load_section(self, tab_layout: QVBoxLayout):
        """Build the Load Experiment section."""
        load_section = CollapsibleSection("Load Experiment", is_expanded=True)
        
        load_card = QFrame()
        load_card.setStyleSheet(card_style())
        load_card_layout = QVBoxLayout(load_card)
        load_card_layout.setContentsMargins(12, 10, 12, 10)
        load_card_layout.setSpacing(10)

        # File selection row
        file_row = QHBoxLayout()
        file_row.setSpacing(8)

        self.sidebar.replay_file_input = QLineEdit()
        self.sidebar.replay_file_input.setPlaceholderText("No file loaded")
        self.sidebar.replay_file_input.setReadOnly(True)
        self.sidebar.replay_file_input.setStyleSheet(self._lineedit_style())
        file_row.addWidget(self.sidebar.replay_file_input)

        self.sidebar.replay_browse_btn = QPushButton("Browse...")
        self.sidebar.replay_browse_btn.setFixedHeight(32)
        self.sidebar.replay_browse_btn.setFixedWidth(90)
        self.sidebar.replay_browse_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.SECONDARY_TEXT};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )
        self.sidebar.replay_browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.sidebar.replay_browse_btn)
        
        load_card_layout.addLayout(file_row)

        # Status label
        self.sidebar.replay_status_label = QLabel("📂 Load an Excel file to begin")
        self.sidebar.replay_status_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic; margin-top: 4px;"
        )
        load_card_layout.addWidget(self.sidebar.replay_status_label)

        load_section.add_content_widget(load_card)
        tab_layout.addWidget(load_section)
        tab_layout.addSpacing(12)

    def _build_playback_section(self, tab_layout: QVBoxLayout):
        """Build the Playback Window section with graph and controls."""
        playback_section = CollapsibleSection("Playback Window", is_expanded=True)
        
        playback_card = QFrame()
        playback_card.setStyleSheet(card_style())
        playback_card_layout = QVBoxLayout(playback_card)
        playback_card_layout.setContentsMargins(12, 10, 12, 10)
        playback_card_layout.setSpacing(10)

        # Channel toggles
        channel_row = QHBoxLayout()
        channel_row.setSpacing(8)
        
        channel_label = QLabel("Channels:")
        channel_label.setFixedWidth(70)
        channel_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        channel_row.addWidget(channel_label)
        
        self.sidebar.replay_channel_toggles = []
        for ch_idx, (ch, color) in enumerate([
            ("A", "#1D1D1F"),  # Black
            ("B", "#FF3B30"),  # Red
            ("C", "#007AFF"),  # Blue
            ("D", "#34C759"),  # Green
        ]):
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(50, 28)
            ch_btn.setProperty('channel_index', ch_idx)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "  color: #8E8E93;"
                "}"
                "QPushButton:hover {"
                "  opacity: 0.8;"
                "}"
            )
            ch_btn.toggled.connect(lambda checked, idx=ch_idx: self._toggle_channel(idx, checked))
            channel_row.addWidget(ch_btn)
            self.sidebar.replay_channel_toggles.append(ch_btn)
        
        channel_row.addStretch()
        playback_card_layout.addLayout(channel_row)

        # Playback graph
        if pg:
            self.sidebar.replay_graph = pg.PlotWidget()
            self.sidebar.replay_graph.setMinimumHeight(200)
            self.sidebar.replay_graph.setBackground('w')
            self.sidebar.replay_graph.setLabel('left', 'Intensity', units='RU')
            self.sidebar.replay_graph.setLabel('bottom', 'Time', units='s')
            self.sidebar.replay_graph.showGrid(x=True, y=True, alpha=0.3)
            playback_card_layout.addWidget(self.sidebar.replay_graph)
        else:
            placeholder = QLabel("Graph preview will appear here")
            placeholder.setMinimumHeight(200)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(f"background: {Colors.OVERLAY_LIGHT_6}; color: {Colors.SECONDARY_TEXT}; border-radius: 8px;")
            playback_card_layout.addWidget(placeholder)

        # Playback controls
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        # Previous cycle button
        self.sidebar.replay_prev_btn = QPushButton("◀◀")
        self.sidebar.replay_prev_btn.setFixedSize(40, 32)
        self.sidebar.replay_prev_btn.setEnabled(False)
        self.sidebar.replay_prev_btn.clicked.connect(self._previous_cycle)
        self.sidebar.replay_prev_btn.setStyleSheet(self._control_button_style())
        controls_row.addWidget(self.sidebar.replay_prev_btn)

        # Play/Pause button
        self.sidebar.replay_play_btn = QPushButton("▶️")
        self.sidebar.replay_play_btn.setFixedSize(40, 32)
        self.sidebar.replay_play_btn.setEnabled(False)
        self.sidebar.replay_play_btn.clicked.connect(self._toggle_playback)
        self.sidebar.replay_play_btn.setStyleSheet(self._control_button_style())
        controls_row.addWidget(self.sidebar.replay_play_btn)

        # Next cycle button
        self.sidebar.replay_next_btn = QPushButton("▶▶")
        self.sidebar.replay_next_btn.setFixedSize(40, 32)
        self.sidebar.replay_next_btn.setEnabled(False)
        self.sidebar.replay_next_btn.clicked.connect(self._next_cycle)
        self.sidebar.replay_next_btn.setStyleSheet(self._control_button_style())
        controls_row.addWidget(self.sidebar.replay_next_btn)

        # Timeline scrubber
        self.sidebar.replay_scrubber = QSlider(Qt.Orientation.Horizontal)
        self.sidebar.replay_scrubber.setMinimum(0)
        self.sidebar.replay_scrubber.setMaximum(100)
        self.sidebar.replay_scrubber.setValue(0)
        self.sidebar.replay_scrubber.setEnabled(False)
        self.sidebar.replay_scrubber.valueChanged.connect(self._scrubber_changed)
        self.sidebar.replay_scrubber.setStyleSheet(self._slider_style())
        controls_row.addWidget(self.sidebar.replay_scrubber, 1)

        # Time label
        self.sidebar.replay_time_label = QLabel("0:00")
        self.sidebar.replay_time_label.setFixedWidth(50)
        self.sidebar.replay_time_label.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT))
        controls_row.addWidget(self.sidebar.replay_time_label)

        playback_card_layout.addLayout(controls_row)

        # Speed control
        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        speed_row.addWidget(speed_label)

        self.sidebar.replay_speed_1x = QPushButton("1x")
        self.sidebar.replay_speed_1x.setCheckable(True)
        self.sidebar.replay_speed_1x.setChecked(True)
        self.sidebar.replay_speed_1x.setFixedSize(45, 28)
        self.sidebar.replay_speed_1x.clicked.connect(lambda: self._set_speed(1))
        self.sidebar.replay_speed_1x.setStyleSheet(self._speed_button_style())
        speed_row.addWidget(self.sidebar.replay_speed_1x)

        self.sidebar.replay_speed_2x = QPushButton("2x")
        self.sidebar.replay_speed_2x.setCheckable(True)
        self.sidebar.replay_speed_2x.setFixedSize(45, 28)
        self.sidebar.replay_speed_2x.clicked.connect(lambda: self._set_speed(2))
        self.sidebar.replay_speed_2x.setStyleSheet(self._speed_button_style())
        speed_row.addWidget(self.sidebar.replay_speed_2x)

        self.sidebar.replay_speed_5x = QPushButton("5x")
        self.sidebar.replay_speed_5x.setCheckable(True)
        self.sidebar.replay_speed_5x.setFixedSize(45, 28)
        self.sidebar.replay_speed_5x.clicked.connect(lambda: self._set_speed(5))
        self.sidebar.replay_speed_5x.setStyleSheet(self._speed_button_style())
        speed_row.addWidget(self.sidebar.replay_speed_5x)

        self.sidebar.replay_speed_10x = QPushButton("10x")
        self.sidebar.replay_speed_10x.setCheckable(True)
        self.sidebar.replay_speed_10x.setFixedSize(45, 28)
        self.sidebar.replay_speed_10x.clicked.connect(lambda: self._set_speed(10))
        self.sidebar.replay_speed_10x.setStyleSheet(self._speed_button_style())
        speed_row.addWidget(self.sidebar.replay_speed_10x)

        speed_row.addStretch()
        playback_card_layout.addLayout(speed_row)

        playback_section.add_content_widget(playback_card)
        tab_layout.addWidget(playback_section)
        tab_layout.addSpacing(12)

    def _build_cycle_info_section(self, tab_layout: QVBoxLayout):
        """Build the Cycle Info section showing current cycle details."""
        info_section = CollapsibleSection("Cycle Info", is_expanded=True)
        
        info_card = QFrame()
        info_card.setStyleSheet(card_style())
        info_card_layout = QVBoxLayout(info_card)
        info_card_layout.setContentsMargins(12, 10, 12, 10)
        info_card_layout.setSpacing(8)

        # Cycle name/number
        self.sidebar.replay_cycle_name = QLabel("No data loaded")
        self.sidebar.replay_cycle_name.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {Colors.PRIMARY_TEXT}; font-family: {Fonts.SYSTEM};"
        )
        info_card_layout.addWidget(self.sidebar.replay_cycle_name)

        # Time progress
        self.sidebar.replay_cycle_time = QLabel("Time: --:-- / --:--")
        self.sidebar.replay_cycle_time.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        info_card_layout.addWidget(self.sidebar.replay_cycle_time)

        # Current value
        self.sidebar.replay_current_value = QLabel("Value: --- RU")
        self.sidebar.replay_current_value.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        info_card_layout.addWidget(self.sidebar.replay_current_value)

        info_section.add_content_widget(info_card)
        tab_layout.addWidget(info_section)
        tab_layout.addSpacing(12)

    def _build_export_section(self, tab_layout: QVBoxLayout):
        """Build the Export Options section for GIF and PNG export."""
        export_section = CollapsibleSection("Export Options", is_expanded=True)
        
        export_card = QFrame()
        export_card.setStyleSheet(card_style())
        export_card_layout = QVBoxLayout(export_card)
        export_card_layout.setContentsMargins(12, 10, 12, 10)
        export_card_layout.setSpacing(10)

        # Cycle range selector
        range_row = QHBoxLayout()
        range_row.setSpacing(8)

        range_label = QLabel("Export cycles:")
        range_label.setFixedWidth(90)
        range_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        range_row.addWidget(range_label)

        self.sidebar.replay_start_cycle_spin = QSpinBox()
        self.sidebar.replay_start_cycle_spin.setMinimum(1)
        self.sidebar.replay_start_cycle_spin.setMaximum(1)
        self.sidebar.replay_start_cycle_spin.setValue(1)
        self.sidebar.replay_start_cycle_spin.setPrefix("From: ")
        self.sidebar.replay_start_cycle_spin.setFixedWidth(90)
        self.sidebar.replay_start_cycle_spin.setStyleSheet(self._spinbox_style())
        range_row.addWidget(self.sidebar.replay_start_cycle_spin)

        self.sidebar.replay_end_cycle_spin = QSpinBox()
        self.sidebar.replay_end_cycle_spin.setMinimum(1)
        self.sidebar.replay_end_cycle_spin.setMaximum(1)
        self.sidebar.replay_end_cycle_spin.setValue(1)
        self.sidebar.replay_end_cycle_spin.setPrefix("To: ")
        self.sidebar.replay_end_cycle_spin.setFixedWidth(90)
        self.sidebar.replay_end_cycle_spin.setStyleSheet(self._spinbox_style())
        range_row.addWidget(self.sidebar.replay_end_cycle_spin)

        range_row.addStretch()
        export_card_layout.addLayout(range_row)

        # Export GIF button
        self.sidebar.replay_export_gif_btn = QPushButton("🎞 Export as GIF")
        self.sidebar.replay_export_gif_btn.setFixedHeight(36)
        self.sidebar.replay_export_gif_btn.setMaximumWidth(200)
        self.sidebar.replay_export_gif_btn.setEnabled(False)
        self.sidebar.replay_export_gif_btn.clicked.connect(self._export_gif)
        self.sidebar.replay_export_gif_btn.setStyleSheet(primary_button_style())
        self.sidebar.replay_export_gif_btn.setToolTip("Export selected cycles as animated GIF for email/Slack sharing")
        export_card_layout.addWidget(self.sidebar.replay_export_gif_btn)

        # Export PNG button
        self.sidebar.replay_export_png_btn = QPushButton("📸 Export Current Frame as PNG")
        self.sidebar.replay_export_png_btn.setFixedHeight(36)
        self.sidebar.replay_export_png_btn.setMaximumWidth(250)
        self.sidebar.replay_export_png_btn.setEnabled(False)
        self.sidebar.replay_export_png_btn.clicked.connect(self._export_png)
        self.sidebar.replay_export_png_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 6px;"
            f"  padding: 8px 16px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
            f"QPushButton:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}"
        )
        self.sidebar.replay_export_png_btn.setToolTip("Export current frame as PNG image")
        export_card_layout.addWidget(self.sidebar.replay_export_png_btn)

        export_section.add_content_widget(export_card)
        tab_layout.addWidget(export_section)
        tab_layout.addSpacing(12)

    # === Event Handlers ===

    def _browse_file(self):
        """Open file browser to select Excel file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.sidebar,
            "Open Experiment Data",
            "", 
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        """Load Excel file and prepare for playback."""
        try:
            import os
            filename = os.path.basename(file_path)
            self.sidebar.replay_file_input.setText(filename)
            
            # Load Excel file
            xls = pd.ExcelFile(file_path)
            
            # Load cycle metadata
            self.cycles_df = pd.read_excel(xls, 'Cycles')
            num_cycles = len(self.cycles_df)
            
            # Try to load data - support multiple formats
            self.channel_data = {}
            
            # Format 1: Live acquisition format (elapsed, wavelength_a/b/c/d)
            if 'Raw Data' in xls.sheet_names:
                df_raw = pd.read_excel(xls, 'Raw Data')
                
                # Check for live format (wavelength_a, wavelength_b, etc.)
                if 'wavelength_a' in df_raw.columns:
                    self.time_data = df_raw['elapsed'].values if 'elapsed' in df_raw.columns else df_raw['time'].values
                    self.total_frames = len(self.time_data)
                    
                    for ch_letter, col_name in [
                        ('A', 'wavelength_a'),
                        ('B', 'wavelength_b'),
                        ('C', 'wavelength_c'),
                        ('D', 'wavelength_d'),
                    ]:
                        if col_name in df_raw.columns:
                            self.channel_data[f'Channel_{ch_letter}'] = df_raw[col_name].values
                
                # Check for export format (A, B, C, D)
                elif 'A' in df_raw.columns:
                    self.time_data = df_raw['Time'].values
                    self.total_frames = len(self.time_data)
                    
                    for ch_letter in ['A', 'B', 'C', 'D']:
                        if ch_letter in df_raw.columns:
                            self.channel_data[f'Channel_{ch_letter}'] = df_raw[ch_letter].values
            
            # Format 2: Per-channel sheets (Channel_A with Elapsed Time and Wavelength)
            if not self.channel_data:
                available_channels = [s for s in xls.sheet_names if s.startswith('Channel_')]
                
                for channel_name in available_channels:
                    df = pd.read_excel(xls, channel_name)
                    if self.time_data is None:
                        # Use time data from first channel (same for all)
                        self.time_data = df['Elapsed Time (s)'].values
                        self.total_frames = len(self.time_data)
                    self.channel_data[channel_name] = df['Wavelength (nm)'].values
            
            # Calculate cycle boundaries
            self.cycle_boundaries = []
            cycle_duration = 300.0  # seconds per cycle
            for i in range(num_cycles):
                start_time = i * cycle_duration
                end_time = (i + 1) * cycle_duration
                start_idx = np.searchsorted(self.time_data, start_time)
                end_idx = np.searchsorted(self.time_data, end_time)
                self.cycle_boundaries.append((start_idx, end_idx))
            
            # Update status
            total_points = self.total_frames
            num_channels = len(self.channel_data)
            self.sidebar.replay_status_label.setText(
                f"✅ {num_cycles} cycles loaded • {num_channels} channels • {total_points:,} points/ch"
            )
            
            # Enable controls
            self.sidebar.replay_play_btn.setEnabled(True)
            self.sidebar.replay_next_btn.setEnabled(True)
            self.sidebar.replay_prev_btn.setEnabled(True)
            self.sidebar.replay_scrubber.setEnabled(True)
            self.sidebar.replay_export_gif_btn.setEnabled(True)
            self.sidebar.replay_export_png_btn.setEnabled(True)
            
            # Update cycle range spinboxes
            self.sidebar.replay_start_cycle_spin.setMaximum(num_cycles)
            self.sidebar.replay_end_cycle_spin.setMaximum(num_cycles)
            self.sidebar.replay_end_cycle_spin.setValue(num_cycles)
            
            # Load first cycle
            self.current_cycle_idx = 0
            self.current_frame = 0
            self._load_cycle(0)
            
        except Exception as e:
            QMessageBox.critical(
                self.sidebar,
               "Load Error",
                f"Failed to load file:\n{str(e)}"
            )

    def _toggle_playback(self):
        """Toggle play/pause state."""
        if self.is_playing:
            self._pause_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        """Start playback animation."""
        self.is_playing = True
        self.sidebar.replay_play_btn.setText("⏸")
        # Update timer interval based on speed (base 50ms)
        interval = int(50 / self.playback_speed)
        self.playback_timer.start(interval)

    def _pause_playback(self):
        """Pause playback animation."""
        self.is_playing = False
        self.sidebar.replay_play_btn.setText("▶")
        self.playback_timer.stop()

    def _advance_frame(self):
        """Advance to next frame in playback."""
        if self.cycle_boundaries is None or len(self.cycle_boundaries) == 0:
            return
        
        start_idx, end_idx = self.cycle_boundaries[self.current_cycle_idx]
        
        # Advance frame
        self.current_frame += self.playback_speed
        
        # Check if we've passed the end of current cycle
        if self.current_frame >= end_idx:
            # Move to next cycle
            if self.current_cycle_idx < len(self.cycle_boundaries) - 1:
                self.current_cycle_idx += 1
                start_idx, _ = self.cycle_boundaries[self.current_cycle_idx]
                self.current_frame = start_idx
            else:
                # End of all cycles - stop playback
                self._pause_playback()
                return
        
        # Update display
        self._update_graph()
        self._update_scrubber()
        self._update_cycle_info()

    def _scrubber_changed(self, value):
        """Handle scrubber position change."""
        if self.time_data is None:
            return
        
        # Map scrubber value (0-100) to frame index
        self.current_frame = int((value / 100.0) * (self.total_frames - 1))
        
        # Update which cycle we're in
        for i, (start_idx, end_idx) in enumerate(self.cycle_boundaries):
            if start_idx <= self.current_frame < end_idx:
                self.current_cycle_idx = i
                break
        
        # Update display
        self._update_graph()
        self._update_cycle_info()

    def _set_speed(self, speed: int):
        """Set playback speed multiplier."""
        self.playback_speed = speed
        
        # Update button states
        self.sidebar.replay_speed_1x.setChecked(speed == 1)
        self.sidebar.replay_speed_2x.setChecked(speed == 2)
        self.sidebar.replay_speed_5x.setChecked(speed == 5)
        self.sidebar.replay_speed_10x.setChecked(speed == 10)
        
        # Update timer if playing
        if self.is_playing:
            interval = int(50 / self.playback_speed)
            self.playback_timer.setInterval(interval)

    def _previous_cycle(self):
        """Jump to previous cycle."""
        if self.current_cycle_idx > 0:
            self.current_cycle_idx -= 1
            self._load_cycle(self.current_cycle_idx)

    def _next_cycle(self):
        """Jump to next cycle."""
        if self.cycle_boundaries and self.current_cycle_idx < len(self.cycle_boundaries) - 1:
            self.current_cycle_idx += 1
            self._load_cycle(self.current_cycle_idx)

    def _load_cycle(self, cycle_idx: int):
        """Load and display specific cycle."""
        if self.cycle_boundaries is None or cycle_idx >= len(self.cycle_boundaries):
            return
        
        self.current_cycle_idx = cycle_idx
        start_idx, _ = self.cycle_boundaries[cycle_idx]
        self.current_frame = start_idx
        
        # Update display
        self._update_graph()
        self._update_scrubber()
        self._update_cycle_info()
    
    def _toggle_channel(self, ch_idx: int, visible: bool):
        """Toggle channel visibility."""
        channel_name = f'Channel_{chr(65 + ch_idx)}'
        self.channel_visible[channel_name] = visible
        
        # Update graph visibility
        if channel_name in self.plot_curves:
            self.plot_curves[channel_name].setVisible(visible)
    
    def _update_graph(self):
        """Update graph to show data up to current frame for all channels."""
        if self.time_data is None or not pg:
            return
        
        # Get data up to current frame
        time_slice = self.time_data[:self.current_frame + 1]
        
        # Update or create plot curves for each channel
        for i, (channel_name, wavelength_data) in enumerate(self.channel_data.items()):
            wavelength_slice = wavelength_data[:self.current_frame + 1]
            
            if channel_name not in self.plot_curves:
                # Create new curve with appropriate color
                is_visible = self.channel_visible.get(channel_name, True)
                self.plot_curves[channel_name] = self.sidebar.replay_graph.plot(
                    time_slice,
                    wavelength_slice,
                    pen=pg.mkPen(color=CHANNEL_COLORS[i], width=2),
                    name=channel_name.replace('_', ' ')
                )
                self.plot_curves[channel_name].setVisible(is_visible)
            else:
                # Update existing curve
                self.plot_curves[channel_name].setData(time_slice, wavelength_slice)
    
    def _update_scrubber(self):
        """Update scrubber position based on current frame."""
        if self.total_frames == 0:
            return
        
        # Map current frame to scrubber value (0-100)
        scrubber_value = int((self.current_frame / (self.total_frames - 1)) * 100)
        
        # Block signals to avoid triggering _scrubber_changed
        self.sidebar.replay_scrubber.blockSignals(True)
        self.sidebar.replay_scrubber.setValue(scrubber_value)
        self.sidebar.replay_scrubber.blockSignals(False)
        
        # Update time label
        if self.time_data is not None:
            current_time = self.time_data[self.current_frame]
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            self.sidebar.replay_time_label.setText(f"{minutes}:{seconds:02d}")
    
    def _update_cycle_info(self):
        """Update cycle info display."""
        if self.cycles_df is None or self.current_cycle_idx >= len(self.cycles_df):
            return
        
        cycle_row = self.cycles_df.iloc[self.current_cycle_idx]
        
        # Support both formats (simulated vs real data)
        if 'cycle_num' in cycle_row:
            cycle_num = cycle_row['cycle_num']
        elif 'cycle_number' in cycle_row:
            cycle_num = cycle_row['cycle_number']
        else:
            cycle_num = self.current_cycle_idx + 1
        
        # Get cycle name/note
        if 'name' in cycle_row:
            cycle_name = cycle_row['name']
        elif 'note' in cycle_row and pd.notna(cycle_row['note']):
            cycle_name = cycle_row['note']
        elif 'notes' in cycle_row and pd.notna(cycle_row['notes']):
            cycle_name = cycle_row['notes']
        else:
            cycle_name = f'Cycle {cycle_num}'
        
        total_cycles = len(self.cycles_df)
        
        # Update cycle name
        self.sidebar.replay_cycle_name.setText(f"Cycle {cycle_num}/{total_cycles}: {cycle_name}")
        
        # Update time within cycle
        start_idx, end_idx = self.cycle_boundaries[self.current_cycle_idx]
        cycle_start_time = self.time_data[start_idx]
        cycle_end_time = self.time_data[end_idx - 1] if end_idx > start_idx else cycle_start_time
        current_time = self.time_data[self.current_frame]
        
        elapsed = current_time - cycle_start_time
        duration = cycle_end_time - cycle_start_time
        
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        duration_min = int(duration // 60)
        duration_sec = int(duration % 60)
        
        self.sidebar.replay_cycle_time.setText(
            f"Time: {elapsed_min:02d}:{elapsed_sec:02d} / {duration_min:02d}:{duration_sec:02d}"
        )
        
        # Update current values for all channels
        if self.channel_data:
            values_text = "Values: "
            for i, (ch_name, ch_data) in enumerate(self.channel_data.items()):
                ch_label = ch_name.replace('Channel_', 'Ch')
                values_text += f"{ch_label}: {ch_data[self.current_frame]:.1f}  "
            self.sidebar.replay_current_value.setText(values_text.rstrip())

    def _export_gif(self):
        """Export selected cycles as animated GIF."""
        # TODO: Implement GIF export
        QMessageBox.information(
            self.sidebar,
            "Export GIF",
            "GIF export will be available in the next update.\n\n"
            "This will create an animated GIF of the selected cycles."
        )

    def _export_png(self):
        """Export current frame as PNG image."""
        # TODO: Implement PNG export
        file_path, _ = QFileDialog.getSaveFileName(
            self.sidebar,
            "Save PNG Image",
            "",
            "PNG Files (*.png)"
        )
        if file_path:
            # Export current graph view
            # exporter = pg.exporters.ImageExporter(self.sidebar.replay_graph.plotItem)
            # exporter.export(file_path)
            QMessageBox.information(
                self.sidebar,
                "Export PNG",
                f"Frame would be saved to:\n{file_path}"
            )

    # === Style Helpers ===

    def _control_button_style(self) -> str:
        """Style for playback control buttons."""
        return (
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.SECONDARY_TEXT};"
            f"  border-radius: 6px;"
            f"  font-size: 14px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
            f"QPushButton:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}"
        )

    def _slider_style(self) -> str:
        """Return slider stylesheet."""
        return (
            f"QSlider::groove:horizontal {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  height: 6px;"
            f"  border-radius: 3px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {Colors.PRIMARY_BLUE};"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  margin: -5px 0;"
            f"  border-radius: 8px;"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background: {Colors.PRIMARY_BLUE};"
            f"}}"
        )

    def _speed_button_style(self) -> str:
        """Return speed button stylesheet."""
        return (
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 4px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: {Colors.PRIMARY_BLUE};"
            f"  color: white;"
            f"  border: 1px solid {Colors.PRIMARY_BLUE};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )

    def _lineedit_style(self) -> str:
        """Return line edit stylesheet."""
        return (
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 6px 8px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
        )

    def _control_button_style(self) -> str:
        """Return control button stylesheet."""
        return (
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 6px;"
            f"  font-size: 14px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
            f"QPushButton:pressed {{ background: {Colors.OVERLAY_LIGHT_10}; }}"
            f"QPushButton:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}"
        )

    def _slider_style(self) -> str:
        """Return slider stylesheet."""
        return (
            f"QSlider::groove:horizontal {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  height: 4px;"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {Colors.BUTTON_PRIMARY};"
            f"  border: none;"
            f"  width: 14px;"
            f"  height: 14px;"
            f"  margin: -5px 0;"
            f"  border-radius: 7px;"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background: #005BBB;"
            f"}}"
        )

    def _speed_button_style(self) -> str:
        """Return speed button stylesheet."""
        return (
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 4px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: {Colors.BUTTON_PRIMARY};"
            f"  color: white;"
            f"  border-color: {Colors.BUTTON_PRIMARY};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )

    def _spinbox_style(self) -> str:
        """Return spinbox stylesheet."""
        return (
            f"QSpinBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QSpinBox:focus {{ border: 2px solid {Colors.PRIMARY_TEXT}; }}"
        )
    
    def _combobox_style(self) -> str:
        """Return combobox stylesheet."""
        return (
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 5px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox:hover {{ border-color: {Colors.OVERLAY_LIGHT_20}; }}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 20px;"
            f"}}"
            f"QComboBox::down-arrow {{"
            f"  image: none;"
            f"  border-left: 4px solid transparent;"
            f"  border-right: 4px solid transparent;"
            f"  border-top: 5px solid {Colors.SECONDARY_TEXT};"
            f"  margin-right: 8px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  selection-background-color: {Colors.OVERLAY_LIGHT_6};"
            f"  selection-color: {Colors.PRIMARY_TEXT};"
            f"}}"
        )
