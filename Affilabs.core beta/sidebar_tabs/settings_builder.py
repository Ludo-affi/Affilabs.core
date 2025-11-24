"""
Settings Tab Builder

Handles building the Settings tab UI with spectroscopy diagnostics, hardware config, and calibration controls.
This is the largest and most complex tab.

Author: Affilabs
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QFrame, QLabel, QHBoxLayout, QPushButton,
    QLineEdit, QButtonGroup
)
import pyqtgraph as pg

# Import styles from central location
from ui_styles import section_header_style
from sections import CollapsibleSection


class SettingsTabBuilder:
    """Builder for constructing the Settings tab UI with diagnostics, hardware config, and calibration."""

    def __init__(self, sidebar):
        """Initialize builder with reference to parent sidebar.

        Args:
            sidebar: Parent AffilabsSidebar instance to attach widgets to
        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build the complete Settings tab UI.

        Args:
            tab_layout: QVBoxLayout to add settings tab widgets to
        """
        self._build_spectroscopy_diagnostics(tab_layout)
        tab_layout.addSpacing(12)

        self._build_hardware_configuration(tab_layout)
        tab_layout.addSpacing(12)

        self._build_calibration_controls(tab_layout)
        tab_layout.addSpacing(20)

    def _build_spectroscopy_diagnostics(self, tab_layout: QVBoxLayout):
        """Build spectroscopy diagnostics section with transmission/raw data graphs (collapsible, starts collapsed)."""
        spectroscopy_section = CollapsibleSection("🔬 Spectroscopy Diagnostics (QC)", is_expanded=False)

        spectroscopy_help = QLabel("Quality control: View spectral data for troubleshooting purposes only")
        spectroscopy_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        spectroscopy_section.content_layout.addWidget(spectroscopy_help)

        # Show/Hide Graphs toggle button
        self.sidebar.spectro_display_toggle_btn = QPushButton("▶ Show Graphs")
        self.sidebar.spectro_display_toggle_btn.setCheckable(True)
        self.sidebar.spectro_display_toggle_btn.setChecked(False)
        self.sidebar.spectro_display_toggle_btn.setFixedHeight(32)
        self.sidebar.spectro_display_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #F2F2F7;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton:checked:hover {"
            "  background: #3A3A3C;"
            "}"
        )
        self.sidebar.spectro_display_toggle_btn.clicked.connect(self.sidebar._on_spectro_display_toggle)
        spectroscopy_section.content_layout.addWidget(self.sidebar.spectro_display_toggle_btn)

        # Graph card (hidden by default)
        self.sidebar.graph_card = QFrame()
        self.sidebar.graph_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        self.sidebar.graph_card.setVisible(False)
        graph_card_layout = QVBoxLayout(self.sidebar.graph_card)
        graph_card_layout.setContentsMargins(12, 10, 12, 10)
        graph_card_layout.setSpacing(10)

        # Build graph toggle and plots
        self._build_graph_toggle(graph_card_layout)
        self._build_transmission_plot(graph_card_layout)
        self._build_raw_data_plot(graph_card_layout)

        # Connect toggle buttons to switch visibility
        self.sidebar.transmission_btn.toggled.connect(self.sidebar._on_spectroscopy_toggle)
        self.sidebar.raw_data_btn.toggled.connect(self.sidebar._on_spectroscopy_toggle)

        spectroscopy_section.add_content_widget(self.sidebar.graph_card)
        tab_layout.addWidget(spectroscopy_section)

    def _build_graph_toggle(self, layout: QVBoxLayout):
        """Build graph toggle buttons (Transmission / Raw Data)."""
        graph_toggle_row = QHBoxLayout()
        graph_toggle_row.setSpacing(0)

        self.sidebar.graph_button_group = QButtonGroup(self.sidebar)
        self.sidebar.graph_button_group.setExclusive(True)

        # Transmission button
        self.sidebar.transmission_btn = QPushButton("Transmission")
        self.sidebar.transmission_btn.setCheckable(True)
        self.sidebar.transmission_btn.setChecked(True)
        self.sidebar.transmission_btn.setFixedHeight(28)
        self.sidebar.transmission_btn.setStyleSheet(self._toggle_button_style(is_left=True))
        self.sidebar.graph_button_group.addButton(self.sidebar.transmission_btn, 0)
        graph_toggle_row.addWidget(self.sidebar.transmission_btn)

        # Raw Data button
        self.sidebar.raw_data_btn = QPushButton("Raw Data")
        self.sidebar.raw_data_btn.setCheckable(True)
        self.sidebar.raw_data_btn.setFixedHeight(28)
        self.sidebar.raw_data_btn.setStyleSheet(self._toggle_button_style(is_left=False))
        self.sidebar.graph_button_group.addButton(self.sidebar.raw_data_btn, 1)
        graph_toggle_row.addWidget(self.sidebar.raw_data_btn)

        graph_toggle_row.addStretch()
        layout.addLayout(graph_toggle_row)

    def _build_transmission_plot(self, layout: QVBoxLayout):
        """Build transmission plot with status frame and 4-channel curves."""
        # Status frame
        self.sidebar.transmission_status_frame = self._create_status_frame("Transmission")
        layout.addWidget(self.sidebar.transmission_status_frame)

        # Transmission plot
        self.sidebar.transmission_plot = pg.PlotWidget()
        self.sidebar.transmission_plot.setBackground('#FFFFFF')
        self.sidebar.transmission_plot.setLabel('left', 'Transmittance (%)', color='#86868B', size='10pt')
        self.sidebar.transmission_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
        self.sidebar.transmission_plot.showGrid(x=True, y=True, alpha=0.15)
        self.sidebar.transmission_plot.setMinimumHeight(200)

        # Legend
        legend = self.sidebar.transmission_plot.addLegend(offset=(10, 10))
        legend.setBrush(pg.mkBrush(255, 255, 255, 200))

        # Style axes
        self.sidebar.transmission_plot.getPlotItem().getAxis('left').setPen(color='#E5E5EA', width=1)
        self.sidebar.transmission_plot.getPlotItem().getAxis('bottom').setPen(color='#E5E5EA', width=1)
        self.sidebar.transmission_plot.getPlotItem().getAxis('left').setTextPen('#86868B')
        self.sidebar.transmission_plot.getPlotItem().getAxis('bottom').setTextPen('#86868B')

        # Create 4-channel curves
        colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
        self.sidebar.transmission_curves = []
        for i, color in enumerate(colors):
            curve = self.sidebar.transmission_plot.plot(
                pen=pg.mkPen(color=color, width=2),
                name=f'Channel {chr(65+i)}'
            )
            self.sidebar.transmission_curves.append(curve)

        self.sidebar.transmission_plot.setVisible(True)
        layout.addWidget(self.sidebar.transmission_plot)

    def _build_raw_data_plot(self, layout: QVBoxLayout):
        """Build raw data (intensity) plot with status frame and 4-channel curves."""
        # Status frame
        self.sidebar.raw_data_status_frame = self._create_status_frame("Raw Data", visible=False)
        layout.addWidget(self.sidebar.raw_data_status_frame)

        # Raw data plot
        self.sidebar.raw_data_plot = pg.PlotWidget()
        self.sidebar.raw_data_plot.setBackground('#FFFFFF')
        self.sidebar.raw_data_plot.setLabel('left', 'Intensity (counts)', color='#86868B', size='10pt')
        self.sidebar.raw_data_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
        self.sidebar.raw_data_plot.showGrid(x=True, y=True, alpha=0.15)
        self.sidebar.raw_data_plot.setMinimumHeight(200)
        self.sidebar.raw_data_plot.setVisible(False)

        # Legend
        legend2 = self.sidebar.raw_data_plot.addLegend(offset=(10, 10))
        legend2.setBrush(pg.mkBrush(255, 255, 255, 200))

        # Style axes
        self.sidebar.raw_data_plot.getPlotItem().getAxis('left').setPen(color='#E5E5EA', width=1)
        self.sidebar.raw_data_plot.getPlotItem().getAxis('bottom').setPen(color='#E5E5EA', width=1)
        self.sidebar.raw_data_plot.getPlotItem().getAxis('left').setTextPen('#86868B')
        self.sidebar.raw_data_plot.getPlotItem().getAxis('bottom').setTextPen('#86868B')

        # Create 4-channel curves
        colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
        self.sidebar.raw_data_curves = []
        for i, color in enumerate(colors):
            curve = self.sidebar.raw_data_plot.plot(
                pen=pg.mkPen(color=color, width=2),
                name=f'Channel {chr(65+i)}'
            )
            self.sidebar.raw_data_curves.append(curve)

        layout.addWidget(self.sidebar.raw_data_plot)

    def _create_status_frame(self, label_text: str, visible: bool = True) -> QFrame:
        """Create status frame with metrics for transmission/raw data plots.

        Args:
            label_text: Status label text ("Transmission" or "Raw Data")
            visible: Whether frame is initially visible

        Returns:
            Configured QFrame with status layout
        """
        status_frame = QFrame()
        status_frame.setStyleSheet(
            "QFrame {"
            "  background: #F2F2F7;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "}"
        )
        status_frame.setVisible(visible)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 6, 8, 6)
        status_layout.setSpacing(4)

        # Status header
        status_header = QHBoxLayout()
        status_label = QLabel(f"{label_text}:")
        status_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        status_header.addWidget(status_label)

        # Status indicator
        status_indicator = QLabel("● Ready")
        status_indicator.setStyleSheet(
            "font-size: 11px;"
            "color: #34C759;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        status_header.addWidget(status_indicator)

        # Store indicator reference on sidebar for updates
        if "transmission" in label_text.lower():
            self.sidebar.transmission_status_indicator = status_indicator
        else:
            self.sidebar.raw_data_status_indicator = status_indicator

        status_header.addStretch()
        status_layout.addLayout(status_header)

        # Metrics row (only for Transmission)
        if "transmission" in label_text.lower():
            metrics_layout = QHBoxLayout()
            metrics_layout.setSpacing(16)

            self.sidebar.transmission_channel_metrics = []
            colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']

            for i, color in enumerate(colors):
                channel_layout = QVBoxLayout()
                channel_layout.setSpacing(2)

                channel_label = QLabel(f"Ch {chr(65+i)}")
                channel_label.setStyleSheet(
                    f"font-size: 10px;"
                    f"font-weight: 600;"
                    f"color: {color};"
                    f"background: transparent;"
                    f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                channel_layout.addWidget(channel_label)

                fwhm_label = QLabel("FWHM: --")
                fwhm_label.setStyleSheet(
                    "font-size: 9px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                )
                channel_layout.addWidget(fwhm_label)

                intensity_label = QLabel("Int: --%")
                intensity_label.setStyleSheet(
                    "font-size: 9px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                )
                channel_layout.addWidget(intensity_label)

                self.sidebar.transmission_channel_metrics.append({
                    'fwhm': fwhm_label,
                    'intensity': intensity_label
                })

                metrics_layout.addLayout(channel_layout)

            metrics_layout.addStretch()
            status_layout.addLayout(metrics_layout)

        return status_frame

    def _build_hardware_configuration(self, tab_layout: QVBoxLayout):
        """Build hardware configuration section with polarizer and LED settings (collapsible, starts expanded)."""
        hardware_section = CollapsibleSection("⚙ Hardware Configuration", is_expanded=True)

        hardware_help = QLabel("Configure polarizer positions and LED intensity for each channel")
        hardware_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        hardware_section.content_layout.addWidget(hardware_help)

        # Card container
        polarizer_led_card = QFrame()
        polarizer_led_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        polarizer_led_card_layout = QVBoxLayout(polarizer_led_card)
        polarizer_led_card_layout.setContentsMargins(12, 8, 12, 8)
        polarizer_led_card_layout.setSpacing(6)

        # Build sections
        self._build_polarizer_settings(polarizer_led_card_layout)
        self._add_separator(polarizer_led_card_layout)
        self._build_led_settings(polarizer_led_card_layout)
        self._add_separator(polarizer_led_card_layout)
        self._build_settings_buttons(polarizer_led_card_layout)

        hardware_section.add_content_widget(polarizer_led_card)
        tab_layout.addWidget(hardware_section)

    def _build_polarizer_settings(self, layout: QVBoxLayout):
        """Build polarizer position settings (S/P positions and toggle button)."""
        polarizer_label = QLabel("Polarizer Positions:")
        polarizer_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(polarizer_label)

        polarizer_row = QHBoxLayout()
        polarizer_row.setSpacing(12)

        # S Position
        s_position_label = QLabel("S:")
        s_position_label.setStyleSheet(self._small_label_style())
        polarizer_row.addWidget(s_position_label)

        self.sidebar.s_position_input = QLineEdit()
        self.sidebar.s_position_input.setPlaceholderText("0-180")
        self.sidebar.s_position_input.setToolTip("Servo position for S polarization mode (0-180 degrees)")
        self.sidebar.s_position_input.setFixedWidth(70)
        self.sidebar.s_position_input.setStyleSheet(self._lineedit_style())
        polarizer_row.addWidget(self.sidebar.s_position_input)

        polarizer_row.addSpacing(16)

        # P Position
        p_position_label = QLabel("P:")
        p_position_label.setStyleSheet(self._small_label_style())
        polarizer_row.addWidget(p_position_label)

        self.sidebar.p_position_input = QLineEdit()
        self.sidebar.p_position_input.setPlaceholderText("0-180")
        self.sidebar.p_position_input.setToolTip("Servo position for P polarization mode (0-180 degrees)")
        self.sidebar.p_position_input.setFixedWidth(70)
        self.sidebar.p_position_input.setStyleSheet(self._lineedit_style())
        polarizer_row.addWidget(self.sidebar.p_position_input)

        # Toggle S/P Button
        self.sidebar.polarizer_toggle_btn = QPushButton("Position: S")
        self.sidebar.polarizer_toggle_btn.setFixedWidth(100)
        self.sidebar.polarizer_toggle_btn.setFixedHeight(28)
        self.sidebar.polarizer_toggle_btn.setToolTip("Click to toggle between S and P polarization modes")
        self.sidebar.polarizer_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        # Track current polarizer position on sidebar
        self.sidebar.current_polarizer_position = 'S'
        polarizer_row.addWidget(self.sidebar.polarizer_toggle_btn)

        polarizer_row.addStretch()
        layout.addLayout(polarizer_row)

    def _build_led_settings(self, layout: QVBoxLayout):
        """Build LED intensity settings for channels A, B, C, D."""
        led_intensity_label = QLabel("LED Intensity per Channel:")
        led_intensity_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(led_intensity_label)

        # Create channel inputs (A, B, C, D)
        channels = ['a', 'b', 'c', 'd']
        for channel in channels:
            channel_row = QHBoxLayout()
            channel_row.setSpacing(10)

            channel_label = QLabel(f"Channel {channel.upper()}:")
            channel_label.setFixedWidth(70)
            channel_label.setStyleSheet(
                "font-size: 12px;"
                "color: #1D1D1F;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            channel_row.addWidget(channel_label)

            channel_input = QLineEdit()
            channel_input.setPlaceholderText("0-255")
            channel_input.setToolTip(f"LED intensity for Channel {channel.upper()} (0-255)")
            channel_input.setFixedWidth(70)
            channel_input.setStyleSheet(self._lineedit_style())
            channel_row.addWidget(channel_input)

            # Store reference on sidebar
            setattr(self.sidebar, f'channel_{channel}_input', channel_input)

            channel_row.addStretch()
            layout.addLayout(channel_row)

    def _build_settings_buttons(self, layout: QVBoxLayout):
        """Build settings action buttons (Load Current, Apply Settings, Advanced)."""
        settings_button_row = QHBoxLayout()
        settings_button_row.setSpacing(8)

        # Load Current Settings button
        self.sidebar.load_current_settings_btn = QPushButton("↻ Load Current")
        self.sidebar.load_current_settings_btn.setFixedHeight(32)
        self.sidebar.load_current_settings_btn.setToolTip("Load current settings from device")
        self.sidebar.load_current_settings_btn.setStyleSheet(
            "QPushButton {"
            "  background: #F2F2F7;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        settings_button_row.addWidget(self.sidebar.load_current_settings_btn)

        # Apply Settings button
        self.sidebar.apply_settings_btn = QPushButton("Apply Settings")
        self.sidebar.apply_settings_btn.setFixedHeight(32)
        self.sidebar.apply_settings_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        settings_button_row.addWidget(self.sidebar.apply_settings_btn)

        # Advanced Settings button (gear icon)
        self.sidebar.advanced_settings_btn = QPushButton("⚙")
        self.sidebar.advanced_settings_btn.setFixedSize(32, 32)
        self.sidebar.advanced_settings_btn.setToolTip("Advanced Settings")
        self.sidebar.advanced_settings_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  font-size: 16px;"
            "  padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #1D1D1F;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
        )
        settings_button_row.addWidget(self.sidebar.advanced_settings_btn)

        layout.addLayout(settings_button_row)

    def _build_calibration_controls(self, tab_layout: QVBoxLayout):
        """Build calibration controls section with Simple, Full, and OEM calibrations (collapsible, starts collapsed)."""
        calibration_section = CollapsibleSection("🔧 Calibration Controls", is_expanded=False)

        calibration_help = QLabel("Perform LED and system calibrations for optimal performance")
        calibration_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_section.content_layout.addWidget(calibration_help)

        # Card container
        calibration_card = QFrame()
        calibration_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        calibration_card_layout = QVBoxLayout(calibration_card)
        calibration_card_layout.setContentsMargins(12, 8, 12, 8)
        calibration_card_layout.setSpacing(6)

        # Simple LED Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Simple LED Calibration",
            description="Quick LED intensity adjustment for all channels",
            button_text="Run Simple Calibration",
            button_ref="simple_led_calibration_btn",
            primary=True
        )

        calibration_card_layout.addSpacing(12)

        # Full System Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Full System Calibration",
            description="Complete calibration including dark reference and LED optimization",
            button_text="Run Full Calibration",
            button_ref="full_calibration_btn",
            primary=False
        )

        calibration_card_layout.addSpacing(12)

        # OEM LED Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="OEM LED Calibration",
            description="Factory-level calibration for LED driver settings (advanced users)",
            button_text="Run OEM Calibration",
            button_ref="oem_led_calibration_btn",
            primary=False
        )

        calibration_section.add_content_widget(calibration_card)
        tab_layout.addWidget(calibration_section)

        # Connect button signals
        self.sidebar.polarizer_toggle_btn.clicked.connect(self.sidebar.toggle_polarizer_position)
        # Note: advanced_settings_btn and other calibration buttons should be connected
        # by the parent window to access the full application context

    def _add_calibration_option(self, layout: QVBoxLayout, title: str, description: str,
                                  button_text: str, button_ref: str, primary: bool = False):
        """Add a calibration option with title, description, and button.

        Args:
            layout: Layout to add to
            title: Calibration title
            description: Calibration description
            button_text: Button label text
            button_ref: Attribute name on sidebar to store button reference
            primary: Whether to use primary (dark) button style
        """
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        layout.addWidget(desc_label)

        # Button
        button = QPushButton(button_text)
        button.setFixedHeight(36)

        if primary:
            button.setStyleSheet(
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #3A3A3C;"
                "}"
                "QPushButton:pressed {"
                "  background: #48484A;"
                "}"
            )
        else:
            button.setStyleSheet(
                "QPushButton {"
                "  background: white;"
                "  color: #1D1D1F;"
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )

        # Store button reference on sidebar
        setattr(self.sidebar, button_ref, button)
        layout.addWidget(button)

    # Helper methods for consistent styling

    def _add_separator(self, layout: QVBoxLayout):
        """Add a horizontal separator line."""
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 4px 0px;"
        )
        layout.addWidget(separator)

    def _small_label_style(self) -> str:
        """Return consistent small label stylesheet."""
        return (
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )

    def _lineedit_style(self) -> str:
        """Return consistent line edit stylesheet."""
        return (
            "QLineEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
            "QLineEdit:focus {"
            "  border: 2px solid #1D1D1F;"
            "  padding: 3px 7px;"
            "}"
        )

    def _toggle_button_style(self, is_left: bool) -> str:
        """Return consistent toggle button stylesheet.

        Args:
            is_left: Whether this is the left button in a group (affects border radius)
        """
        border_radius = (
            "border-top-left-radius: 6px; border-bottom-left-radius: 6px; border-right: none;"
            if is_left else
            "border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        )

        return (
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            f"  {border_radius}"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
