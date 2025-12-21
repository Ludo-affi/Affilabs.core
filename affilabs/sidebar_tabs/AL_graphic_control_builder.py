"""Graphic Control Tab Builder for AffiLabs.core Sidebar

Builds the Graphic Control tab with:
- Data filtering controls
- Reference channel selection
- Axis scaling (X/Y with auto/manual)
- Grid and trace style options
- Visual accessibility (colorblind palette)

Extracted from sidebar.py to improve modularity.
"""

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    checkbox_style,
    label_style,
    section_header_style,
)

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


class GraphicControlTabBuilder:
    """Builds the Graphic Control tab content."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build Graphic Control tab with plots, axes, filters, and accessibility.

        Args:
            tab_layout: QVBoxLayout to add widgets to

        """
        self._build_data_filtering(tab_layout)
        self._build_reference_section(tab_layout)
        self._build_graphic_display(tab_layout)
        self._build_visual_accessibility(tab_layout)
        tab_layout.addStretch()

    def _build_data_filtering(self, tab_layout: QVBoxLayout):
        """Build EMA live display filtering controls section."""
        filter_section = QLabel("DATA FILTERING")
        filter_section.setStyleSheet(section_header_style())
        filter_section.setToolTip(
            "Smooth live sensorgram display using EMA (Exponential Moving Average)",
        )
        tab_layout.addWidget(filter_section)
        tab_layout.addSpacing(8)

        gc_card = QFrame()
        gc_card.setStyleSheet(card_style())
        gc_layout = QVBoxLayout(gc_card)
        gc_layout.setContentsMargins(12, 12, 12, 12)
        gc_layout.setSpacing(12)

        # Description
        desc_label = QLabel(
            "EMA filtering for live display (does not affect saved data):",
        )
        desc_label.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT))
        desc_label.setWordWrap(True)
        gc_layout.addWidget(desc_label)

        # EMA Filter Options
        self.sidebar.filter_method_group = QButtonGroup()

        radio_style = (
            f"QRadioButton {{"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-size: 12px;"
            f"  spacing: 6px;"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border: 2px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 8px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: 3px solid white;"
            f"  outline: 2px solid {Colors.PRIMARY_TEXT};"
            f"}}"
        )

        # Option 1: None (Raw) - DEFAULT
        self.sidebar.filter_none_radio = QRadioButton("None (Raw) ⭐")
        self.sidebar.filter_none_radio.setChecked(True)  # Default
        self.sidebar.filter_none_radio.setStyleSheet(radio_style)
        self.sidebar.filter_none_radio.setToolTip(
            "No filtering - Raw data display\n"
            "• Baseline noise: ~5.7 RU\n"
            "• Use for: Maximum fidelity, debugging",
        )
        self.sidebar.filter_method_group.addButton(self.sidebar.filter_none_radio, 0)
        gc_layout.addWidget(self.sidebar.filter_none_radio)

        # Option 2: EMA Light (α=0.50)
        self.sidebar.filter_light_radio = QRadioButton("EMA Light (α=0.50)")
        self.sidebar.filter_light_radio.setStyleSheet(radio_style)
        self.sidebar.filter_light_radio.setToolTip(
            "Light smoothing filter - Reduces noise while maintaining fast response\n"
            "• Minimal lag during sharp changes\n"
            "• Less curvature overshoot\n"
            "• Use for: General data smoothing, reducing baseline noise",
        )
        self.sidebar.filter_method_group.addButton(self.sidebar.filter_light_radio, 1)
        gc_layout.addWidget(self.sidebar.filter_light_radio)

        # Info note
        info_label = QLabel(
            "💡 EMA filtering is applied point-by-point to the live display only. "
            "Saved data remains unfiltered. Applied after peak finding.",
        )
        info_label.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-size: 10px;"
            f"font-style: italic;"
            f"padding: 8px;"
            f"background: {Colors.OVERLAY_LIGHT_4};"
            f"border-radius: 4px;",
        )
        info_label.setWordWrap(True)
        gc_layout.addWidget(info_label)

        tab_layout.addWidget(gc_card)
        tab_layout.addSpacing(16)

        # PHASE 1: Live Cycle Timeframe controls (non-functional, visual only)
        self._build_live_cycle_timeframe(tab_layout)

    def _build_live_cycle_timeframe(self, tab_layout: QVBoxLayout):
        """PHASE 1: Build Live Cycle timeframe controls (parallel to cursors)."""
        section_label = QLabel("LIVE CYCLE WINDOW")
        section_label.setStyleSheet(section_header_style())
        section_label.setToolTip(
            "Configure Live Cycle display timeframe (Phase 1: Visual only)",
        )
        tab_layout.addWidget(section_label)
        tab_layout.addSpacing(8)

        timeframe_card = QFrame()
        timeframe_card.setStyleSheet(card_style())
        timeframe_layout = QVBoxLayout(timeframe_card)
        timeframe_layout.setContentsMargins(12, 12, 12, 12)
        timeframe_layout.setSpacing(12)

        # Timeframe selection
        timeframe_label = QLabel("Timeframe:")
        timeframe_label.setStyleSheet(label_style(12, Colors.PRIMARY_TEXT))
        timeframe_layout.addWidget(timeframe_label)

        self.sidebar.timeframe_combo = QComboBox()
        self.sidebar.timeframe_combo.addItems(
            ["2 minutes", "5 minutes", "15 minutes", "30 minutes", "60 minutes"],
        )
        self.sidebar.timeframe_combo.setCurrentIndex(1)  # Default to 5 minutes
        self.sidebar.timeframe_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 6px;"
            f"  padding: 6px 10px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"}}"
            f"QComboBox:hover {{"
            f"  border: 1px solid rgba(0, 0, 0, 0.15);"
            f"}}",
        )
        timeframe_layout.addWidget(self.sidebar.timeframe_combo)

        # Mode selection
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(label_style(12, Colors.PRIMARY_TEXT))
        timeframe_layout.addWidget(mode_label)

        # Radio button group
        self.sidebar.timeframe_mode_group = QButtonGroup()

        radio_style = (
            f"QRadioButton {{"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-size: 13px;"
            f"  spacing: 8px;"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"}}"
        )

        # Moving mode (default)
        self.sidebar.mode_moving_radio = QRadioButton("Moving (last N minutes)")
        self.sidebar.mode_moving_radio.setChecked(True)
        self.sidebar.mode_moving_radio.setStyleSheet(radio_style)
        self.sidebar.mode_moving_radio.setToolTip(
            "Scrolling window showing the most recent data\\n"
            "New points enter at 4/5 from left (80%)\\n"
            "Like an oscilloscope or chart recorder",
        )
        self.sidebar.timeframe_mode_group.addButton(self.sidebar.mode_moving_radio, 0)
        timeframe_layout.addWidget(self.sidebar.mode_moving_radio)

        # Fixed mode
        self.sidebar.mode_fixed_radio = QRadioButton("Fixed (0 to N minutes)")
        self.sidebar.mode_fixed_radio.setStyleSheet(radio_style)
        self.sidebar.mode_fixed_radio.setToolTip(
            "Fixed window from t=0 to selected time\\n"
            "Perfect for watching a complete cycle\\n"
            "Frame stays locked, data fills in",
        )
        self.sidebar.timeframe_mode_group.addButton(self.sidebar.mode_fixed_radio, 1)
        timeframe_layout.addWidget(self.sidebar.mode_fixed_radio)

        # Info note
        info_label = QLabel(
            "💡 Phase 1: Visual controls only. Cursor system still active.\\n"
            "This will replace cursors in future phases.",
        )
        info_label.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT};"
            f"font-size: 10px;"
            f"font-style: italic;"
            f"padding: 8px;"
            f"background: {Colors.OVERLAY_LIGHT_4};"
            f"border-radius: 4px;",
        )
        info_label.setWordWrap(True)
        timeframe_layout.addWidget(info_label)

        tab_layout.addWidget(timeframe_card)
        tab_layout.addSpacing(16)

    def _build_reference_section(self, tab_layout: QVBoxLayout):
        """Build reference channel selection section."""
        ref_section = QLabel("REFERENCE")
        ref_section.setStyleSheet(section_header_style())
        ref_section.setToolTip(
            "Subtract a reference channel from all others for baseline correction",
        )
        tab_layout.addWidget(ref_section)
        tab_layout.addSpacing(8)

        ref_card = QFrame()
        ref_card.setStyleSheet(card_style())
        ref_layout = QVBoxLayout(ref_card)
        ref_layout.setContentsMargins(12, 10, 12, 10)
        ref_layout.setSpacing(8)

        ref_desc = QLabel("Select a channel to subtract from others")
        ref_desc.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        ref_layout.addWidget(ref_desc)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(10)
        ref_label = QLabel("Reference:")
        ref_label.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;",
        )
        ref_row.addWidget(ref_label)
        ref_row.addStretch()

        self.sidebar.ref_combo = QComboBox()
        self.sidebar.ref_combo.addItems(
            ["None", "Channel A", "Channel B", "Channel C", "Channel D"],
        )
        self.sidebar.ref_combo.setFixedWidth(120)
        self.sidebar.ref_combo.setToolTip(
            "Select channel to use as baseline reference (shown as dashed line)",
        )
        self.sidebar.ref_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 6px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox:hover {{"
            f"  border: 1px solid rgba(0, 0, 0, 0.15);"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 20px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  selection-background-color: {Colors.PRIMARY_TEXT};"
            f"  selection-color: white;"
            f"  outline: none;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}",
        )
        ref_row.addWidget(self.sidebar.ref_combo)
        ref_layout.addLayout(ref_row)

        ref_info = QLabel("Selected channel shown as faded dashed line")
        ref_info.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;",
        )
        ref_layout.addWidget(ref_info)

        # Wire reference combo
        self.sidebar.ref_combo.currentIndexChanged.connect(
            lambda idx: print(
                f"Reference changed to: {self.sidebar.ref_combo.currentText()}",
            ),
        )

        tab_layout.addWidget(ref_card)
        tab_layout.addSpacing(16)

    def _build_graphic_display(self, tab_layout: QVBoxLayout):
        """Build graphic display configuration section."""
        # Graphic Display section (with note)
        display_section = QLabel("GRAPHIC DISPLAY")
        display_section.setStyleSheet(section_header_style())
        display_section.setToolTip("Configure axis scaling, grid, and trace appearance")
        tab_layout.addWidget(display_section)

        display_note = QLabel("Applied to cycle of interest")
        display_note.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT)
            + "font-style: italic; margin-top: 2px;",
        )
        tab_layout.addWidget(display_note)
        tab_layout.addSpacing(8)

        display_card = QFrame()
        display_card.setStyleSheet(card_style())
        display_card_layout = QVBoxLayout(display_card)
        display_card_layout.setContentsMargins(12, 10, 12, 10)
        display_card_layout.setSpacing(10)

        # Axis selector (segmented control)
        self._build_axis_selector(display_card_layout)

        # Axis scaling controls
        self._build_axis_scaling(display_card_layout)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06); border: none; margin: 8px 0px;",
        )
        display_card_layout.addWidget(separator)

        # Trace Style options
        self._build_trace_options(display_card_layout)

        tab_layout.addWidget(display_card)
        tab_layout.addSpacing(16)

    def _build_axis_selector(self, parent_layout: QVBoxLayout):
        """Build axis selector (X/Y axis toggle with grid)."""
        axis_selector_container = QVBoxLayout()
        axis_selector_container.setSpacing(6)

        axis_selector_label = QLabel("Configure:")
        axis_selector_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        axis_selector_container.addWidget(axis_selector_label)

        axis_selector_row = QHBoxLayout()
        axis_selector_row.setSpacing(0)

        self.sidebar.axis_button_group = QButtonGroup(self.sidebar)
        self.sidebar.axis_button_group.setExclusive(True)

        self.sidebar.x_axis_btn = QPushButton("X-Axis")
        self.sidebar.x_axis_btn.setCheckable(True)
        self.sidebar.x_axis_btn.setChecked(True)
        self.sidebar.x_axis_btn.setFixedHeight(28)
        self.sidebar.x_axis_btn.setToolTip("Configure horizontal axis (time) scaling")
        self.sidebar.x_axis_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-top-left-radius: 6px;"
            f"  border-bottom-left-radius: 6px;"
            f"  border-right: none;"
            f"  padding: 4px 16px;"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  color: white;"
            f"}}"
            f"QPushButton:hover:!checked {{"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"}}",
        )
        self.sidebar.axis_button_group.addButton(self.sidebar.x_axis_btn, 0)
        axis_selector_row.addWidget(self.sidebar.x_axis_btn)

        self.sidebar.y_axis_btn = QPushButton("Y-Axis")
        self.sidebar.y_axis_btn.setCheckable(True)
        self.sidebar.y_axis_btn.setFixedHeight(28)
        self.sidebar.y_axis_btn.setToolTip(
            "Configure vertical axis (signal intensity) scaling",
        )
        self.sidebar.y_axis_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-top-right-radius: 6px;"
            f"  border-bottom-right-radius: 6px;"
            f"  padding: 4px 16px;"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  color: white;"
            f"}}"
            f"QPushButton:hover:!checked {{"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"}}",
        )
        self.sidebar.axis_button_group.addButton(self.sidebar.y_axis_btn, 1)
        axis_selector_row.addWidget(self.sidebar.y_axis_btn)

        axis_selector_row.addSpacing(16)

        # Grid toggle next to axis selector
        self.sidebar.grid_check = QCheckBox("Grid")
        self.sidebar.grid_check.setChecked(True)
        self.sidebar.grid_check.setToolTip("Show/hide grid lines on plot background")
        self.sidebar.grid_check.setStyleSheet(
            f"QCheckBox {{"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  background: transparent;"
            f"  spacing: 6px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QCheckBox::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 4px;"
            f"  background: white;"
            f"}}"
            f"QCheckBox::indicator:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: 1px solid {Colors.PRIMARY_TEXT};"
            f"}}",
        )
        axis_selector_row.addWidget(self.sidebar.grid_check)
        axis_selector_row.addStretch()

        axis_selector_container.addLayout(axis_selector_row)
        parent_layout.addLayout(axis_selector_container)

    def _build_axis_scaling(self, parent_layout: QVBoxLayout):
        """Build axis scaling controls (auto/manual)."""
        scale_radio_group = QButtonGroup()
        scale_radio_group.setExclusive(True)

        self.sidebar.auto_radio = QRadioButton("Autoscale")
        self.sidebar.auto_radio.setChecked(True)
        self.sidebar.auto_radio.setToolTip(
            "Automatically adjust axis range to fit all data",
        )
        self.sidebar.auto_radio.setStyleSheet(
            f"QRadioButton {{"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  background: transparent;"
            f"  spacing: 6px;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 8px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: 4px solid white;"
            f"  outline: 1px solid {Colors.PRIMARY_TEXT};"
            f"}}",
        )
        scale_radio_group.addButton(self.sidebar.auto_radio, 0)
        parent_layout.addWidget(self.sidebar.auto_radio)

        # Manual scaling container
        manual_container = QWidget()
        manual_layout = QVBoxLayout(manual_container)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)

        self.sidebar.manual_radio = QRadioButton("Manual")
        self.sidebar.manual_radio.setToolTip(
            "Set fixed axis range for consistent scaling",
        )
        self.sidebar.manual_radio.setStyleSheet(
            f"QRadioButton {{"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  background: transparent;"
            f"  spacing: 6px;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 8px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: 4px solid white;"
            f"  outline: 1px solid {Colors.PRIMARY_TEXT};"
            f"}}",
        )
        scale_radio_group.addButton(self.sidebar.manual_radio, 1)
        manual_layout.addWidget(self.sidebar.manual_radio)

        # Manual input fields
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(8)
        inputs_row.setContentsMargins(24, 0, 0, 0)

        min_label = QLabel("Min:")
        min_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        inputs_row.addWidget(min_label)

        self.sidebar.min_input = QLineEdit()
        self.sidebar.min_input.setPlaceholderText("0")
        self.sidebar.min_input.setFixedWidth(60)
        self.sidebar.min_input.setEnabled(False)
        self.sidebar.min_input.setToolTip("Minimum value for axis range")
        self.sidebar.min_input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 6px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 1px solid {Colors.PRIMARY_TEXT};"
            f"}}"
            f"QLineEdit:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_3};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}",
        )
        inputs_row.addWidget(self.sidebar.min_input)

        max_label = QLabel("Max:")
        max_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        inputs_row.addWidget(max_label)

        self.sidebar.max_input = QLineEdit()
        self.sidebar.max_input.setPlaceholderText("100")
        self.sidebar.max_input.setFixedWidth(60)
        self.sidebar.max_input.setEnabled(False)
        self.sidebar.max_input.setToolTip("Maximum value for axis range")
        self.sidebar.max_input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 6px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 1px solid {Colors.PRIMARY_TEXT};"
            f"}}"
            f"QLineEdit:disabled {{"
            f"  background: {Colors.OVERLAY_LIGHT_3};"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"}}",
        )
        inputs_row.addWidget(self.sidebar.max_input)
        inputs_row.addStretch()

        manual_layout.addLayout(inputs_row)
        parent_layout.addWidget(manual_container)

        # Connect manual radio to enable inputs
        self.sidebar.manual_radio.toggled.connect(self.sidebar.min_input.setEnabled)
        self.sidebar.manual_radio.toggled.connect(self.sidebar.max_input.setEnabled)

    def _build_trace_options(self, parent_layout: QVBoxLayout):
        """Build trace style options (channel and marker selection)."""
        options_row = QHBoxLayout()
        options_row.setSpacing(12)

        # Channel selection
        channel_label = QLabel("Channel:")
        channel_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        options_row.addWidget(channel_label)

        self.sidebar.channel_combo = QComboBox()
        self.sidebar.channel_combo.addItems(["All", "A", "B", "C", "D"])
        self.sidebar.channel_combo.setFixedWidth(70)
        self.sidebar.channel_combo.setToolTip("Select which channel(s) to display")
        self.sidebar.channel_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 2px 6px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox:hover {{"
            f"  border: 1px solid rgba(0, 0, 0, 0.15);"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 16px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  selection-background-color: {Colors.PRIMARY_TEXT};"
            f"  selection-color: white;"
            f"  outline: none;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}",
        )
        options_row.addWidget(self.sidebar.channel_combo)

        # Markers
        marker_label = QLabel("Markers:")
        marker_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        options_row.addWidget(marker_label)

        self.sidebar.marker_combo = QComboBox()
        self.sidebar.marker_combo.addItems(["Circle", "Triangle", "Square", "Star"])
        self.sidebar.marker_combo.setFixedWidth(90)
        self.sidebar.marker_combo.setToolTip("Choose marker shape for data points")
        self.sidebar.marker_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 2px 6px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox:hover {{"
            f"  border: 1px solid rgba(0, 0, 0, 0.15);"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"  width: 16px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  selection-background-color: {Colors.PRIMARY_TEXT};"
            f"  selection-color: white;"
            f"  outline: none;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}",
        )
        options_row.addWidget(self.sidebar.marker_combo)
        options_row.addStretch()

        parent_layout.addLayout(options_row)

    def _build_visual_accessibility(self, tab_layout: QVBoxLayout):
        """Build visual accessibility section (colorblind palette)."""
        accessibility_section = QLabel("VISUAL ACCESSIBILITY")
        accessibility_section.setStyleSheet(section_header_style())
        accessibility_section.setToolTip("Options to improve visibility for all users")
        tab_layout.addWidget(accessibility_section)
        tab_layout.addSpacing(8)

        accessibility_card = QFrame()
        accessibility_card.setStyleSheet(card_style())
        accessibility_card_layout = QVBoxLayout(accessibility_card)
        accessibility_card_layout.setContentsMargins(12, 10, 12, 10)
        accessibility_card_layout.setSpacing(8)

        # Colorblind-friendly palette toggle
        self.sidebar.colorblind_check = QCheckBox(
            "Enable colour-blind friendly palette",
        )
        self.sidebar.colorblind_check.setStyleSheet(checkbox_style())
        self.sidebar.colorblind_check.setToolTip(
            "Use optimized colors for deuteranopia and protanopia (affects all channels)",
        )
        accessibility_card_layout.addWidget(self.sidebar.colorblind_check)

        # Info text about colorblind palette
        colorblind_info = QLabel(
            "Uses optimized colors for deuteranopia and protanopia",
        )
        colorblind_info.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;",
        )
        accessibility_card_layout.addWidget(colorblind_info)

        # Colorblind palette toggle logic
        def _toggle_colorblind(checked: bool):
            palette = (
                COLORBLIND_PALETTE
                if checked
                else ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]
            )
            # Note: Plot references removed - this would apply to main window plots
            print(f"Colorblind palette toggled: {checked}")

        self.sidebar.colorblind_check.toggled.connect(_toggle_colorblind)

        tab_layout.addWidget(accessibility_card)
