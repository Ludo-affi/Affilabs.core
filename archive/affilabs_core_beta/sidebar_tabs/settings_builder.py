"""Settings Tab Builder

Handles building the Settings tab UI with hardware config and calibration controls.

Author: Affilabs
"""

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

# Import sections from central location
from sections import CollapsibleSection
from ui_styles import section_header_style


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
        self._build_intelligence_bar(tab_layout)
        self._build_hardware_configuration(tab_layout)
        tab_layout.addSpacing(12)

        self._build_calibration_controls(tab_layout)
        tab_layout.addSpacing(20)

    def _build_intelligence_bar(self, tab_layout: QVBoxLayout):
        """Build intelligence bar section."""
        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setFixedHeight(15)
        intel_section.setStyleSheet(section_header_style())
        intel_section.setToolTip(
            "Real-time system status and guidance powered by AI diagnostics",
        )
        tab_layout.addWidget(intel_section)
        tab_layout.addSpacing(8)

        intel_bar = QFrame()
        intel_bar.setGeometry(20, 142, 411, 37)
        intel_bar.setStyleSheet(
            "QFrame {  background: transparent;  border: none;}",
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(16, 12, 16, 8)
        intel_bar_layout.setSpacing(12)

        # Status indicators
        self.sidebar.settings_intel_status_label = QLabel("✓ Good")
        self.sidebar.settings_intel_status_label.setStyleSheet(
            "font-size: 12px;"
            "color: #34C759;"
            "background: transparent;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_status_label)

        # Separator bullet
        self.sidebar.settings_intel_separator = QLabel("•")
        self.sidebar.settings_intel_separator.setStyleSheet(
            "font-size: 12px;color: #86868B;background: transparent;",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_separator)

        self.sidebar.settings_intel_message_label = QLabel("→ Hardware configured")
        self.sidebar.settings_intel_message_label.setFixedHeight(20)
        self.sidebar.settings_intel_message_label.setStyleSheet(
            "font-size: 12px;"
            "color: #007AFF;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        intel_bar_layout.addWidget(self.sidebar.settings_intel_message_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

    def _build_hardware_configuration(self, tab_layout: QVBoxLayout):
        """Build hardware configuration section with polarizer and LED settings (collapsible, starts expanded)."""
        hardware_section = CollapsibleSection(
            "⚙ Hardware Configuration",
            is_expanded=True,
        )

        hardware_help = QLabel(
            "Configure polarizer positions and LED intensity for each channel",
        )
        hardware_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        hardware_section.content_layout.addWidget(hardware_help)

        # Card container
        polarizer_led_card = QFrame()
        polarizer_led_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
        )
        polarizer_led_card_layout = QVBoxLayout(polarizer_led_card)
        polarizer_led_card_layout.setContentsMargins(12, 8, 12, 8)
        polarizer_led_card_layout.setSpacing(6)

        # Build sections
        self._build_polarizer_settings(polarizer_led_card_layout)
        self._add_separator(polarizer_led_card_layout)
        self._build_pipeline_selector(polarizer_led_card_layout)
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
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
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
        self.sidebar.s_position_input.setToolTip(
            "Servo position for S polarization mode (0-180 degrees)",
        )
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
        self.sidebar.p_position_input.setToolTip(
            "Servo position for P polarization mode (0-180 degrees)",
        )
        self.sidebar.p_position_input.setFixedWidth(70)
        self.sidebar.p_position_input.setStyleSheet(self._lineedit_style())
        polarizer_row.addWidget(self.sidebar.p_position_input)

        # Toggle S/P Button
        self.sidebar.polarizer_toggle_btn = QPushButton("Position: S")
        self.sidebar.polarizer_toggle_btn.setFixedWidth(100)
        self.sidebar.polarizer_toggle_btn.setFixedHeight(28)
        self.sidebar.polarizer_toggle_btn.setToolTip(
            "Click to toggle between S and P polarization modes",
        )
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
            "}",
        )
        # Track current polarizer position on sidebar
        self.sidebar.current_polarizer_position = "S"
        polarizer_row.addWidget(self.sidebar.polarizer_toggle_btn)

        polarizer_row.addSpacing(16)

        # Spectrum Button
        self.sidebar.spectrum_btn = QPushButton("📊 Spectrum")
        self.sidebar.spectrum_btn.setFixedWidth(110)
        self.sidebar.spectrum_btn.setFixedHeight(28)
        self.sidebar.spectrum_btn.setToolTip(
            "Show live transmission spectrum for all channels",
        )
        self.sidebar.spectrum_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #0071E3;"
            "}"
            "QPushButton:pressed {"
            "  background: #0063CC;"
            "}",
        )
        polarizer_row.addWidget(self.sidebar.spectrum_btn)

        polarizer_row.addStretch()
        layout.addLayout(polarizer_row)

    def _build_pipeline_selector(self, layout: QVBoxLayout):
        """Build processing pipeline selector."""
        pipeline_label = QLabel("Processing Pipeline:")
        pipeline_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(pipeline_label)

        pipeline_row = QHBoxLayout()
        pipeline_row.setSpacing(12)

        # Pipeline selector dropdown
        self.sidebar.pipeline_selector = QComboBox()
        self.sidebar.pipeline_selector.setFixedHeight(32)
        self.sidebar.pipeline_selector.setMinimumWidth(200)
        self.sidebar.pipeline_selector.setToolTip(
            "Select data processing pipeline method",
        )
        self.sidebar.pipeline_selector.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:hover {"
            "  border: 1px solid rgba(0, 122, 255, 0.5);"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 5px solid #86868B;"
            "  margin-right: 8px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  selection-background-color: #007AFF;"
            "  selection-color: white;"
            "  padding: 4px;"
            "}",
        )

        # Add pipeline options
        self.sidebar.pipeline_selector.addItem("Fourier Transform (Default)", "fourier")
        self.sidebar.pipeline_selector.addItem("Centroid Detection", "centroid")
        self.sidebar.pipeline_selector.addItem("Polynomial Fit", "polynomial")
        self.sidebar.pipeline_selector.addItem("Adaptive Multi-Feature", "adaptive")
        self.sidebar.pipeline_selector.addItem("Consensus", "consensus")

        # Set default to Fourier
        self.sidebar.pipeline_selector.setCurrentIndex(0)

        pipeline_row.addWidget(self.sidebar.pipeline_selector)
        pipeline_row.addStretch()

        layout.addLayout(pipeline_row)

        # Add description label
        self.sidebar.pipeline_description = QLabel(
            "Fourier Transform: Uses DST/IDCT for derivative zero-crossing detection. Established method for SPR.",
        )
        self.sidebar.pipeline_description.setWordWrap(True)
        self.sidebar.pipeline_description.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(self.sidebar.pipeline_description)

    def _build_led_settings(self, layout: QVBoxLayout):
        """Build LED intensity settings for channels A, B, C, D."""
        led_intensity_label = QLabel("LED Intensity per Channel:")
        led_intensity_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        layout.addWidget(led_intensity_label)

        # Create channel inputs (A, B, C, D)
        channels = ["a", "b", "c", "d"]
        for channel in channels:
            channel_row = QHBoxLayout()
            channel_row.setSpacing(10)

            channel_label = QLabel(f"Channel {channel.upper()}:")
            channel_label.setFixedWidth(70)
            channel_label.setStyleSheet(
                "font-size: 12px;"
                "color: #1D1D1F;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
            )
            channel_row.addWidget(channel_label)

            channel_input = QLineEdit()
            channel_input.setPlaceholderText("0-255")
            channel_input.setToolTip(
                f"LED intensity for Channel {channel.upper()} (0-255)",
            )
            channel_input.setFixedWidth(70)
            channel_input.setStyleSheet(self._lineedit_style())
            channel_row.addWidget(channel_input)

            # Store reference on sidebar
            setattr(self.sidebar, f"channel_{channel}_input", channel_input)

            channel_row.addStretch()
            layout.addLayout(channel_row)

    def _build_settings_buttons(self, layout: QVBoxLayout):
        """Build settings action buttons (Load Current, Apply Settings, Advanced)."""
        settings_button_row = QHBoxLayout()
        settings_button_row.setSpacing(8)

        # Load Current Settings button
        self.sidebar.load_current_settings_btn = QPushButton("↻ Load Current")
        self.sidebar.load_current_settings_btn.setFixedHeight(32)
        self.sidebar.load_current_settings_btn.setToolTip(
            "Load current settings from device",
        )
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
            "}",
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
            "}",
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
            "}",
        )
        settings_button_row.addWidget(self.sidebar.advanced_settings_btn)

        layout.addLayout(settings_button_row)

    def _build_calibration_controls(self, tab_layout: QVBoxLayout):
        """Build calibration controls section with Simple, Full, and OEM calibrations (collapsible, starts collapsed)."""
        calibration_section = CollapsibleSection(
            "🔧 Calibration Controls",
            is_expanded=False,
        )

        calibration_help = QLabel(
            "Perform LED and system calibrations for optimal performance",
        )
        calibration_help.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
        )
        calibration_section.content_layout.addWidget(calibration_help)

        # Card container
        calibration_card = QFrame()
        calibration_card.setStyleSheet(
            "QFrame {  background: rgba(0, 0, 0, 0.03);  border-radius: 8px;}",
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
            primary=True,
        )

        calibration_card_layout.addSpacing(12)

        # Full System Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="Full System Calibration",
            description="Complete calibration including dark reference and LED optimization",
            button_text="Run Full Calibration",
            button_ref="full_calibration_btn",
            primary=False,
        )

        calibration_card_layout.addSpacing(12)

        # OEM LED Calibration
        self._add_calibration_option(
            calibration_card_layout,
            title="OEM LED Calibration",
            description="Factory-level calibration for LED driver settings (advanced users)",
            button_text="Run OEM Calibration",
            button_ref="oem_led_calibration_btn",
            primary=False,
        )

        calibration_section.add_content_widget(calibration_card)
        tab_layout.addWidget(calibration_section)

        # Note: polarizer_toggle_btn.clicked and calibration buttons should be connected
        # by the parent window (main_simplified.py) to access the full application context
        # and handle hardware communication properly

    def _add_calibration_option(
        self,
        layout: QVBoxLayout,
        title: str,
        description: str,
        button_text: str,
        button_ref: str,
        primary: bool = False,
    ):
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
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
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
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;",
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
                "}",
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
                "}",
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
            "background: rgba(0, 0, 0, 0.06);border: none;margin: 4px 0px;",
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
            if is_left
            else "border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
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
