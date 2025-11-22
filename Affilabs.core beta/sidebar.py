"""SidebarPrototype extracted from LL_UI_v1_0.py for modularity."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QScrollArea, QFrame, QLabel,
    QHBoxLayout, QPushButton, QButtonGroup, QCheckBox, QTableWidget,
    QTableWidgetItem, QSpinBox, QLineEdit, QSlider, QComboBox, QRadioButton,
    QTextEdit, QHeaderView
)
from ui_styles import (
    Colors, Fonts, label_style, section_header_style, title_style, card_style,
    primary_button_style, status_indicator_style, divider_style,
    separator_style, segmented_button_style, checkbox_style, spinbox_style,
    scrollbar_style
)
from sections import CollapsibleSection
from cycle_table_dialog import CycleTableDialog
from plot_helpers import create_time_plot, create_spectroscopy_plot, add_channel_curves
import pyqtgraph as pg

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ['#4477AA', '#EE6677', '#228833', '#CCBB44']

class SidebarPrototype(QWidget):
    """Simplified sidebar prototype containing tabbed UI sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self.cycle_table_dialog = None  # Will be created on first open
        self._setup_ui()

    def _setup_ui(self):
        if getattr(self, '_ui_setup_done', False):
            return
        self._ui_setup_done = True
        self.setStyleSheet(f"background: {Colors.BACKGROUND_LIGHT};")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setUpdatesEnabled(False)

        container = QWidget()
        container.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(False)

        # Style the tab widget with compact vertical tabs (original design)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {Colors.BACKGROUND_WHITE};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {Colors.SECONDARY_TEXT};
                padding: 12px 20px;
                margin: 2px 0;
                border: none;
                font-size: 13px;
                font-weight: 500;
                min-height: 50px;
                border-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {Colors.BACKGROUND_WHITE};
                color: {Colors.PRIMARY_TEXT};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {Colors.OVERLAY_LIGHT_6};
            }}
            QTabBar::tab:disabled {{
                background: transparent;
                color: {Colors.OVERLAY_LIGHT_20};
            }}
            QTabBar::tab:selected:!disabled {{
                border-left: 3px solid {Colors.PRIMARY_TEXT};
                padding-left: 17px;
            }}
        """)

        # Tab definitions with builder method mapping and subtitles
        tab_definitions = [
            ("Device Status", "Device Status", "Hardware readiness check", self._build_device_status_tab),
            ("Graphic Control", "Display Setup", "Configure cycle of interest graph", self._build_graphic_control_tab),
            ("Static", "Cycle Control", "Start and manage experiments", self._build_static_tab),
            ("Flow", "Flow Control", "Fluidics experiments", self._build_flow_tab),
            ("Export", "Export Data", "Save and export experiment results", self._build_export_tab),
            ("Settings", "Settings & Diagnostics", "Calibration and maintenance", self._build_settings_tab),
        ]

        # Store tab references for dynamic control
        self.tab_indices = {}
        tab_index = 0

        for label, title_text, subtitle_text, builder_method in tab_definitions:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet(scrollbar_style())

            tab_content = QWidget()
            tab_content.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            # Title with subtitle
            title = QLabel(title_text)
            title.setStyleSheet(title_style())
            tab_layout.addWidget(title)

            tab_layout.addSpacing(4)

            # Subtitle helper text
            subtitle = QLabel(subtitle_text)
            subtitle.setWordWrap(True)
            subtitle.setStyleSheet(
                f"font-size: 11px;"
                f"color: {Colors.SECONDARY_TEXT};"
                f"background: transparent;"
                f"font-style: italic;"
                f"font-family: {Fonts.SYSTEM};"
            )
            tab_layout.addWidget(subtitle)

            tab_layout.addSpacing(12)

            # Call specific builder method for tab content
            builder_method(tab_layout)

            self.tab_widget.addTab(scroll_area, label)
            scroll_area.setWidget(tab_content)

            # Store tab index for later reference
            self.tab_indices[label] = tab_index
            tab_index += 1

        container_layout.addWidget(self.tab_widget)
        # Compatibility alias expected by main code
        self.tabs = self.tab_widget
        main_layout.addWidget(container)
        self.setUpdatesEnabled(True)

    def set_operation_mode(self, mode: str):
        """Set the active operation mode (static or flow) and update tab states."""
        if mode.lower() == 'static':
            # Enable Static, disable Flow
            self.tab_widget.setTabEnabled(self.tab_indices['Static'], True)
            self.tab_widget.setTabEnabled(self.tab_indices['Flow'], False)
            self.tab_widget.setTabToolTip(self.tab_indices['Flow'],
                                          "Flow mode unavailable - requires pump hardware")
        elif mode.lower() == 'flow':
            # Enable Flow, disable Static
            self.tab_widget.setTabEnabled(self.tab_indices['Flow'], True)
            self.tab_widget.setTabEnabled(self.tab_indices['Static'], False)
            self.tab_widget.setTabToolTip(self.tab_indices['Static'],
                                          "Static mode unavailable - flow mode active")
        else:
            # Enable both (default fallback)
            self.tab_widget.setTabEnabled(self.tab_indices['Static'], True)
            self.tab_widget.setTabEnabled(self.tab_indices['Flow'], True)

    def _build_device_status_tab(self, tab_layout: QVBoxLayout):
        """Build Device Status tab with hardware and subunit indicators."""
        # Section 1: Hardware Connected
        hw_section = QLabel("HARDWARE CONNECTED")
        hw_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};"
        )
        hw_section.setToolTip("Physical hardware devices detected on system")
        tab_layout.addWidget(hw_section)
        tab_layout.addSpacing(8)

        hw_card = QFrame()
        hw_card.setStyleSheet(card_style())
        hw_card_layout = QVBoxLayout(hw_card)
        hw_card_layout.setContentsMargins(12, 12, 12, 12)
        hw_card_layout.setSpacing(6)

        # Hardware device labels
        self.hw_device_labels = []
        for i in range(3):
            device_label = QLabel(f"• Device {i+1}: Not connected")
            device_label.setStyleSheet(label_style(13, Colors.SUCCESS) + "padding: 4px 0px;")
            device_label.setVisible(False)
            hw_card_layout.addWidget(device_label)
            self.hw_device_labels.append(device_label)

        self.hw_no_devices = QLabel("No hardware detected")
        self.hw_no_devices.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT) + "padding: 8px 0px;font-style: italic;")
        hw_card_layout.addWidget(self.hw_no_devices)

        hw_card_layout.addSpacing(4)

        self.scan_btn = QPushButton("🔍 Scan for Hardware")
        self.scan_btn.setProperty("scanning", False)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setStyleSheet(primary_button_style())
        self.scan_btn.setToolTip("Search for connected hardware devices (optics, sensors, pumps)")
        hw_card_layout.addWidget(self.scan_btn)

        tab_layout.addWidget(hw_card)
        tab_layout.addSpacing(16)

        # Section 2: Subunit Readiness
        subunit_section = QLabel("SUBUNIT READINESS")
        subunit_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};"
        )
        subunit_section.setToolTip("Initialization status of critical system components")
        tab_layout.addWidget(subunit_section)
        tab_layout.addSpacing(8)

        subunit_card = QFrame()
        subunit_card.setStyleSheet(card_style())
        subunit_card_layout = QVBoxLayout(subunit_card)
        subunit_card_layout.setContentsMargins(12, 10, 12, 10)
        subunit_card_layout.setSpacing(8)

        self.subunit_status = {}
        subunit_names = ['Sensor', 'Optics', 'Fluidics']

        for i, subunit_name in enumerate(subunit_names):
            subunit_row = QHBoxLayout()
            subunit_row.setSpacing(10)
            subunit_row.setContentsMargins(0, 0, 0, 0)

            # Status indicator
            status_indicator = QLabel("●")
            status_indicator.setFixedWidth(12)
            status_indicator.setStyleSheet(f"font-size: 14px; color: {Colors.SECONDARY_TEXT}; background: transparent;")
            subunit_row.addWidget(status_indicator)

            # Subunit name
            name_label = QLabel(subunit_name)
            name_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;")
            subunit_row.addWidget(name_label)

            subunit_row.addStretch()

            # Status text
            status_label = QLabel("Not Ready")
            status_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
            subunit_row.addWidget(status_label)

            # Store references
            self.subunit_status[subunit_name] = {
                'indicator': status_indicator,
                'status_label': status_label
            }

            subunit_container = QWidget()
            subunit_container.setLayout(subunit_row)
            subunit_card_layout.addWidget(subunit_container)

            # Add separator between items (not after last)
            if i < len(subunit_names) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet("background: rgba(0, 0, 0, 0.06); max-height: 1px; margin: 4px 0px;")
                subunit_card_layout.addWidget(separator)

        tab_layout.addWidget(subunit_card)
        tab_layout.addSpacing(16)

        # Operation Modes section
        modes_section = QLabel("OPERATION MODES")
        modes_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};"
        )
        modes_section.setToolTip("Available operation modes based on installed hardware")
        tab_layout.addWidget(modes_section)
        tab_layout.addSpacing(8)

        modes_card = QFrame()
        modes_card.setStyleSheet(card_style())
        modes_card_layout = QVBoxLayout(modes_card)
        modes_card_layout.setContentsMargins(12, 12, 12, 12)
        modes_card_layout.setSpacing(8)

        self.operation_modes = {}
        for mode_name, mode_label in [('static', 'Static'), ('flow', 'Flow')]:
            mode_row = QHBoxLayout()
            mode_row.setSpacing(8)
            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; font-size: 16px;")
            indicator.setFixedWidth(20)
            label = QLabel(mode_label)
            label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;")
            status_label = QLabel("Disabled")
            status_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
            mode_row.addWidget(indicator)
            mode_row.addWidget(label)
            mode_row.addStretch()
            mode_row.addWidget(status_label)
            modes_card_layout.addLayout(mode_row)
            self.operation_modes[mode_name] = {
                'indicator': indicator,
                'label': label,
                'status_label': status_label
            }

        tab_layout.addWidget(modes_card)
        tab_layout.addSpacing(16)

        # Section 4: Maintenance
        maint_section = QLabel("Maintenance")
        maint_section.setStyleSheet(label_style(15, Colors.PRIMARY_TEXT) + "font-weight: 600; margin-top: 8px;")
        tab_layout.addWidget(maint_section)
        tab_layout.addSpacing(8)

        maint_divider = QFrame()
        maint_divider.setFixedHeight(1)
        maint_divider.setStyleSheet("background: rgba(0, 0, 0, 0.1); border: none;")
        tab_layout.addWidget(maint_divider)
        tab_layout.addSpacing(8)

        # Operational Statistics Card
        stats_card = QFrame()
        stats_card.setStyleSheet(card_style())
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(10)

        # Operation Hours
        hours_row = QHBoxLayout()
        hours_row.setSpacing(8)
        hours_label = QLabel("Operation Hours:")
        hours_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        hours_label.setToolTip("Total operational time accumulated by the system")
        self.hours_value = QLabel("1,247 hrs")
        self.hours_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;")
        hours_row.addWidget(hours_label)
        hours_row.addWidget(self.hours_value)
        hours_row.addStretch()
        stats_layout.addLayout(hours_row)

        # Last Operation
        last_op_row = QHBoxLayout()
        last_op_row.setSpacing(8)
        last_op_label = QLabel("Last Operation:")
        last_op_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        last_op_label.setToolTip("Date of most recent experiment or measurement")
        self.last_op_value = QLabel("Nov 19, 2025")
        self.last_op_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;")
        last_op_row.addWidget(last_op_label)
        last_op_row.addWidget(self.last_op_value)
        last_op_row.addStretch()
        stats_layout.addLayout(last_op_row)

        # Annual Maintenance
        upcoming_row = QHBoxLayout()
        upcoming_row.setSpacing(8)
        upcoming_label = QLabel("Annual Maintenance:")
        upcoming_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT) + "margin-top: 6px;")
        upcoming_label.setToolTip("Scheduled date for next annual service and calibration")
        self.next_maintenance_value = QLabel("November 2025")
        self.next_maintenance_value.setStyleSheet(label_style(13, "#FF9500") + "font-weight: 600; margin-top: 6px;")
        upcoming_row.addWidget(upcoming_label)
        upcoming_row.addWidget(self.next_maintenance_value)
        upcoming_row.addStretch()
        stats_layout.addLayout(upcoming_row)

        tab_layout.addWidget(stats_card)
        tab_layout.addSpacing(12)

        # Debug Log Download Button
        debug_btn_container = QFrame()
        debug_btn_container.setStyleSheet(card_style())
        debug_btn_layout = QVBoxLayout(debug_btn_container)
        debug_btn_layout.setContentsMargins(12, 10, 12, 10)

        self.debug_log_btn = QPushButton("📥 Download Debug Log")
        self.debug_log_btn.setFixedHeight(36)
        self.debug_log_btn.setStyleSheet(primary_button_style())
        self.debug_log_btn.setToolTip("Export system logs for troubleshooting and technical support")
        debug_btn_layout.addWidget(self.debug_log_btn)
        tab_layout.addWidget(debug_btn_container)

        tab_layout.addSpacing(16)

        # Software Version
        version_label = QLabel("AffiLabs.core Beta")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT) + "font-weight: 500;")
        tab_layout.addWidget(version_label)

        tab_layout.addStretch()

    def _build_graphic_control_tab(self, tab_layout: QVBoxLayout):
        """Build Graphic Control tab with plots, axes, filters, and accessibility."""
        # Data Filtering section
        filter_section = QLabel("DATA FILTERING")
        filter_section.setStyleSheet(section_header_style())
        filter_section.setToolTip("Smooth noisy data using configurable filters")
        tab_layout.addWidget(filter_section)
        tab_layout.addSpacing(8)

        gc_card = QFrame()
        gc_card.setStyleSheet(card_style())
        gc_layout = QVBoxLayout(gc_card)
        gc_layout.setContentsMargins(12, 12, 12, 12)
        gc_layout.setSpacing(10)

        # Enable filtering checkbox
        self.filter_enable = QCheckBox("Enable data filtering")
        self.filter_enable.setChecked(True)
        self.filter_enable.setStyleSheet(checkbox_style())
        self.filter_enable.setToolTip("Apply smoothing filter to reduce noise in real-time data")
        gc_layout.addWidget(self.filter_enable)

        # Filter strength slider
        filter_strength_row = QHBoxLayout()
        filter_strength_row.setSpacing(10)
        filter_label = QLabel("Filter strength:")
        filter_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        filter_label.setToolTip("Higher values = more smoothing (1=light, 10=heavy)")
        filter_strength_row.addWidget(filter_label)

        self.filter_slider = QSlider(Qt.Horizontal)
        self.filter_slider.setRange(1, 10)
        self.filter_slider.setValue(1)
        self.filter_slider.setEnabled(True)
        self.filter_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{"
            f"  background: {Colors.OVERLAY_LIGHT_10};"
            f"  height: 4px;"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::handle:horizontal {{"
            f"  background: {Colors.PRIMARY_TEXT};"
            f"  border: none;"
            f"  width: 16px;"
            f"  height: 16px;"
            f"  border-radius: 8px;"
            f"  margin: -6px 0;"
            f"}}"
            f"QSlider::handle:horizontal:hover {{"
            f"  background: {Colors.BUTTON_PRIMARY_HOVER};"
            f"}}"
            f"QSlider::handle:horizontal:disabled {{"
            f"  background: {Colors.BUTTON_DISABLED};"
            f"}}"
        )
        filter_strength_row.addWidget(self.filter_slider)

        self.filter_value_label = QLabel("1")
        self.filter_value_label.setFixedWidth(20)
        self.filter_value_label.setStyleSheet(label_style(12, Colors.PRIMARY_TEXT) + "font-weight: 600;")
        filter_strength_row.addWidget(self.filter_value_label)

        gc_layout.addLayout(filter_strength_row)

        # Connect filter controls
        self.filter_enable.toggled.connect(self.filter_slider.setEnabled)
        self.filter_enable.toggled.connect(self.filter_value_label.setEnabled)
        self.filter_slider.valueChanged.connect(
            lambda v: self.filter_value_label.setText(str(v))
        )

        tab_layout.addWidget(gc_card)
        tab_layout.addSpacing(16)

        # Reference section (moved out of plot card)
        ref_section = QLabel("REFERENCE")
        ref_section.setStyleSheet(section_header_style())
        ref_section.setToolTip("Subtract a reference channel from all others for baseline correction")
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
        ref_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;")
        ref_row.addWidget(ref_label)
        ref_row.addStretch()

        self.ref_combo = QComboBox()
        self.ref_combo.addItems(["None", "Channel A", "Channel B", "Channel C", "Channel D"])
        self.ref_combo.setFixedWidth(120)
        self.ref_combo.setToolTip("Select channel to use as baseline reference (shown as dashed line)")
        self.ref_combo.setStyleSheet(
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
            f"}}"
        )
        ref_row.addWidget(self.ref_combo)
        ref_layout.addLayout(ref_row)

        ref_info = QLabel("Selected channel shown as faded dashed line")
        ref_info.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;")
        ref_layout.addWidget(ref_info)

        # Wire reference combo
        self.ref_combo.currentIndexChanged.connect(
            lambda idx: print(f"Reference changed to: {self.ref_combo.currentText()}")
        )

        tab_layout.addWidget(ref_card)
        tab_layout.addSpacing(16)

        # Graphic Display section (with note)
        display_section = QLabel("GRAPHIC DISPLAY")
        display_section.setStyleSheet(section_header_style())
        display_section.setToolTip("Configure axis scaling, grid, and trace appearance")
        tab_layout.addWidget(display_section)

        display_note = QLabel("Applied to cycle of interest")
        display_note.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic; margin-top: 2px;")
        tab_layout.addWidget(display_note)
        tab_layout.addSpacing(8)

        display_card = QFrame()
        display_card.setStyleSheet(card_style())
        display_card_layout = QVBoxLayout(display_card)
        display_card_layout.setContentsMargins(12, 10, 12, 10)
        display_card_layout.setSpacing(10)

        # Axis selector (segmented control)
        axis_selector_container = QVBoxLayout()
        axis_selector_container.setSpacing(6)

        axis_selector_label = QLabel("Configure:")
        axis_selector_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        axis_selector_container.addWidget(axis_selector_label)

        axis_selector_row = QHBoxLayout()
        axis_selector_row.setSpacing(0)

        self.axis_button_group = QButtonGroup(self)
        self.axis_button_group.setExclusive(True)

        self.x_axis_btn = QPushButton("X-Axis")
        self.x_axis_btn.setCheckable(True)
        self.x_axis_btn.setChecked(True)
        self.x_axis_btn.setFixedHeight(28)
        self.x_axis_btn.setToolTip("Configure horizontal axis (time) scaling")
        self.x_axis_btn.setStyleSheet(
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
            f"}}"
        )
        self.axis_button_group.addButton(self.x_axis_btn, 0)
        axis_selector_row.addWidget(self.x_axis_btn)

        self.y_axis_btn = QPushButton("Y-Axis")
        self.y_axis_btn.setCheckable(True)
        self.y_axis_btn.setFixedHeight(28)
        self.y_axis_btn.setToolTip("Configure vertical axis (signal intensity) scaling")
        self.y_axis_btn.setStyleSheet(
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
            f"}}"
        )
        self.axis_button_group.addButton(self.y_axis_btn, 1)
        axis_selector_row.addWidget(self.y_axis_btn)

        axis_selector_row.addSpacing(16)

        # Grid toggle next to axis selector
        self.grid_check = QCheckBox("Grid")
        self.grid_check.setChecked(True)
        self.grid_check.setToolTip("Show/hide grid lines on plot background")
        self.grid_check.setStyleSheet(
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
            f"}}"
        )
        axis_selector_row.addWidget(self.grid_check)
        axis_selector_row.addStretch()

        axis_selector_container.addLayout(axis_selector_row)
        display_card_layout.addLayout(axis_selector_container)

        # Unified Axis Scaling controls
        scale_radio_group = QButtonGroup()
        scale_radio_group.setExclusive(True)

        self.auto_radio = QRadioButton("Autoscale")
        self.auto_radio.setChecked(True)
        self.auto_radio.setToolTip("Automatically adjust axis range to fit all data")
        self.auto_radio.setStyleSheet(
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
            f"}}"
        )
        scale_radio_group.addButton(self.auto_radio, 0)
        display_card_layout.addWidget(self.auto_radio)

        # Manual scaling container
        manual_container = QWidget()
        manual_layout = QVBoxLayout(manual_container)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)

        self.manual_radio = QRadioButton("Manual")
        self.manual_radio.setToolTip("Set fixed axis range for consistent scaling")
        self.manual_radio.setStyleSheet(
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
            f"}}"
        )
        scale_radio_group.addButton(self.manual_radio, 1)
        manual_layout.addWidget(self.manual_radio)

        # Manual input fields
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(8)
        inputs_row.setContentsMargins(24, 0, 0, 0)

        min_label = QLabel("Min:")
        min_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        inputs_row.addWidget(min_label)

        self.min_input = QLineEdit()
        self.min_input.setPlaceholderText("0")
        self.min_input.setFixedWidth(60)
        self.min_input.setEnabled(False)
        self.min_input.setToolTip("Minimum value for axis range")
        self.min_input.setStyleSheet(
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
            f"}}"
        )
        inputs_row.addWidget(self.min_input)

        max_label = QLabel("Max:")
        max_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        inputs_row.addWidget(max_label)

        self.max_input = QLineEdit()
        self.max_input.setPlaceholderText("100")
        self.max_input.setFixedWidth(60)
        self.max_input.setEnabled(False)
        self.max_input.setToolTip("Maximum value for axis range")
        self.max_input.setStyleSheet(
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
            f"}}"
        )
        inputs_row.addWidget(self.max_input)
        inputs_row.addStretch()

        manual_layout.addLayout(inputs_row)
        display_card_layout.addWidget(manual_container)

        # Connect manual radio to enable inputs
        self.manual_radio.toggled.connect(self.min_input.setEnabled)
        self.manual_radio.toggled.connect(self.max_input.setEnabled)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.06); border: none; margin: 8px 0px;")
        display_card_layout.addWidget(separator)

        # Trace Style options row
        options_row = QHBoxLayout()
        options_row.setSpacing(12)

        # Channel selection
        channel_label = QLabel("Channel:")
        channel_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        options_row.addWidget(channel_label)

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["All", "A", "B", "C", "D"])
        self.channel_combo.setFixedWidth(70)
        self.channel_combo.setToolTip("Select which channel(s) to display")
        self.channel_combo.setStyleSheet(
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
            f"}}"
        )
        options_row.addWidget(self.channel_combo)

        # Markers
        marker_label = QLabel("Markers:")
        marker_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        options_row.addWidget(marker_label)

        self.marker_combo = QComboBox()
        self.marker_combo.addItems(["Circle", "Triangle", "Square", "Star"])
        self.marker_combo.setFixedWidth(90)
        self.marker_combo.setToolTip("Choose marker shape for data points")
        self.marker_combo.setStyleSheet(
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
            f"}}"
        )
        options_row.addWidget(self.marker_combo)
        options_row.addStretch()

        display_card_layout.addLayout(options_row)

        tab_layout.addWidget(display_card)
        tab_layout.addSpacing(16)

        # Visual Accessibility section
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
        self.colorblind_check = QCheckBox("Enable colour-blind friendly palette")
        self.colorblind_check.setStyleSheet(checkbox_style())
        self.colorblind_check.setToolTip("Use optimized colors for deuteranopia and protanopia (affects all channels)")
        accessibility_card_layout.addWidget(self.colorblind_check)

        # Info text about colorblind palette
        colorblind_info = QLabel("Uses optimized colors for deuteranopia and protanopia")
        colorblind_info.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;")
        accessibility_card_layout.addWidget(colorblind_info)

        # Colorblind palette toggle logic
        def _toggle_colorblind(checked: bool):
            palette = COLORBLIND_PALETTE if checked else ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
            # Note: Plot references removed - this would apply to main window plots
            print(f"Colorblind palette toggled: {checked}")
        self.colorblind_check.toggled.connect(_toggle_colorblind)

        tab_layout.addWidget(accessibility_card)
        tab_layout.addStretch()

    def _build_static_tab(self, tab_layout: QVBoxLayout):
        """Build Static tab with Signal Intel Bar, cycle management controls and queue table."""
        # Intelligence Bar section
        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setStyleSheet(section_header_style())
        intel_section.setToolTip("Real-time system status and guidance powered by AI diagnostics")
        tab_layout.addWidget(intel_section)
        tab_layout.addSpacing(8)

        # ==================== Signal Intel Bar ====================
        intel_bar = QFrame()
        intel_bar.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(16, 12, 16, 8)
        intel_bar_layout.setSpacing(12)

        # Status indicators
        self.intel_status_label = QLabel("✓ Good")
        self.intel_status_label.setStyleSheet(
            "font-size: 12px;"
            "color: #34C759;"
            "background: transparent;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        intel_bar_layout.addWidget(self.intel_status_label)

        # Separator bullet
        self.intel_separator = QLabel("•")
        self.intel_separator.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
        )
        intel_bar_layout.addWidget(self.intel_separator)

        self.intel_message_label = QLabel("→ Ready for injection")
        self.intel_message_label.setStyleSheet(
            "font-size: 12px;"
            "color: #007AFF;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        intel_bar_layout.addWidget(self.intel_message_label)

        # Countdown timer
        self.countdown_label = QLabel("00:30")
        self.countdown_label.setStyleSheet(
            "font-size: 11px;"
            "color: #1D1D1F;"
            "background: rgba(0, 0, 0, 0.06);"
            "padding: 2px 8px;"
            "border-radius: 4px;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
        )
        intel_bar_layout.addWidget(self.countdown_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

        # ==================== Section 1: Cycle Settings (Collapsible) ====================
        cycle_settings_section = CollapsibleSection("⚙ Configure Next Cycle", is_expanded=True)

        # Card container for cycle settings
        cycle_settings_card = QFrame()
        cycle_settings_card.setStyleSheet(card_style(background="transparent"))
        cycle_settings_card_layout = QVBoxLayout(cycle_settings_card)
        cycle_settings_card_layout.setContentsMargins(10, 8, 10, 8)
        cycle_settings_card_layout.setSpacing(8)

        # Type row
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_label = QLabel("Type:")
        type_label.setFixedWidth(70)
        type_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        type_row.addWidget(type_label)

        self.cycle_type_combo = QComboBox()
        self.cycle_type_combo.addItems(["Auto-read", "Baseline", "Immobilization", "Concentration"])
        self.cycle_type_combo.setCurrentIndex(0)
        self.cycle_type_combo.setToolTip("Select experiment type: Auto-read (automatic), Baseline (reference), Immobilization (binding), or Concentration (dose-response)")
        self.cycle_type_combo.setFixedWidth(140)
        self.cycle_type_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        type_row.addWidget(self.cycle_type_combo)
        type_row.addStretch()
        cycle_settings_card_layout.addLayout(type_row)

        # Length row
        length_row = QHBoxLayout()
        length_row.setSpacing(8)
        length_label = QLabel("Length:")
        length_label.setFixedWidth(70)
        length_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        length_row.addWidget(length_label)

        self.cycle_length_combo = QComboBox()
        self.cycle_length_combo.addItems(["2 min", "5 min", "15 min", "30 min", "60 min"])
        self.cycle_length_combo.setCurrentIndex(1)
        self.cycle_length_combo.setToolTip("Duration of the experiment cycle")
        self.cycle_length_combo.setFixedWidth(100)
        self.cycle_length_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        length_row.addWidget(self.cycle_length_combo)
        length_row.addStretch()
        cycle_settings_card_layout.addLayout(length_row)

        # Note input with syntax highlighter
        note_label = QLabel("Note:")
        note_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        cycle_settings_card_layout.addWidget(note_label)

        # ChannelTagHighlighter class for syntax highlighting
        class ChannelTagHighlighter(QSyntaxHighlighter):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.tag_format = QTextCharFormat()
                self.tag_format.setForeground(QColor("#1D1D1F"))
                self.tag_format.setFontWeight(700)

                self.conc_format = QTextCharFormat()
                self.conc_format.setForeground(QColor("#34C759"))
                self.conc_format.setFontWeight(700)

            def highlightBlock(self, text):
                # Highlight [A:10], [B:50], [ALL:20] concentration tags (green)
                conc_pattern = QRegularExpression(r"\[(A|B|C|D|ALL):(\d+\.?\d*)\]")
                iterator = conc_pattern.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    self.setFormat(match.capturedStart(), match.capturedLength(), self.conc_format)

                # Highlight [A], [B], [C], [D], [ALL] tags without concentration (dark)
                tag_pattern = QRegularExpression(r"\[(A|B|C|D|ALL)\]")
                iterator = tag_pattern.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    # Only highlight if not already highlighted as concentration
                    start = match.capturedStart()
                    if self.format(start).foreground().color() != QColor("#34C759"):
                        self.setFormat(start, match.capturedLength(), self.tag_format)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Use tags: [A] [B] [C] [D] [ALL] or with concentration [A:10] [ALL:50]  (max 250 chars)")
        self.note_input.setMaximumHeight(60)
        self.note_input.setStyleSheet(
            "QTextEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 6px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTextEdit:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
        )

        # Apply syntax highlighter
        self.note_highlighter = ChannelTagHighlighter(self.note_input.document())

        # Character counter
        self.char_count_label = QLabel("0/250 characters")
        self.char_count_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )

        def update_note_counter():
            text = self.note_input.toPlainText()
            if len(text) > 250:
                self.note_input.setPlainText(text[:250])
                self.note_input.moveCursor(self.note_input.textCursor().End)
            self.char_count_label.setText(f"{len(self.note_input.toPlainText())}/250 characters")

        self.note_input.textChanged.connect(update_note_counter)
        cycle_settings_card_layout.addWidget(self.note_input)

        # Character count and tag help
        note_info_row = QHBoxLayout()
        note_info_row.setSpacing(10)
        note_info_row.addWidget(self.char_count_label)
        note_info_row.addStretch()

        tag_help_label = QLabel("💡 Tip: Tag channels with concentrations")
        tag_help_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        note_info_row.addWidget(tag_help_label)
        cycle_settings_card_layout.addLayout(note_info_row)

        # Units row
        units_row = QHBoxLayout()
        units_row.setSpacing(8)
        units_label = QLabel("Units:")
        units_label.setFixedWidth(70)
        units_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        units_row.addWidget(units_label)

        self.units_combo = QComboBox()
        self.units_combo.addItems(["M (Molar)", "mM (Millimolar)", "µM (Micromolar)", "nM (Nanomolar)", "pM (Picomolar)", "mg/mL", "µg/mL", "ng/mL"])
        self.units_combo.setCurrentIndex(3)  # Default to nM
        self.units_combo.setToolTip("Concentration units for tagged channels (applies to [A:10] style tags)")
        self.units_combo.setFixedWidth(140)
        self.units_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        units_row.addWidget(self.units_combo)
        units_row.addStretch()

        # Info about units applying to tags
        units_info = QLabel("Units apply to concentrations in tags (e.g., [A:10] = 10 nM)")
        units_info.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        cycle_settings_card_layout.addWidget(units_info)

        # Separator before execution section
        execution_separator = QFrame()
        execution_separator.setFixedHeight(1)
        execution_separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;"
        )
        cycle_settings_card_layout.addWidget(execution_separator)

        # Execution section header
        execution_header = QLabel("🚀 Execution")
        execution_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        cycle_settings_card_layout.addWidget(execution_header)

        # Action Buttons (Hybrid workflow)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        # Start Cycle Button
        self.start_cycle_btn = QPushButton("▶ Start Cycle")
        self.start_cycle_btn.setFixedSize(120, 36)
        self.start_cycle_btn.setToolTip("Begin experiment immediately with current settings")
        self.start_cycle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
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
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}"
        )
        buttons_row.addWidget(self.start_cycle_btn)

        # Add to Queue Button
        self.add_to_queue_btn = QPushButton("+ Add to Queue")
        self.add_to_queue_btn.setFixedSize(140, 36)
        self.add_to_queue_btn.setToolTip("Add cycle to queue for batch execution (max 5 cycles)")
        self.add_to_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}"
        )
        buttons_row.addWidget(self.add_to_queue_btn)
        buttons_row.addStretch()

        cycle_settings_card_layout.addLayout(buttons_row)

        # Improved help text with clearer workflow explanation
        help_text = QLabel("💡 Start Cycle: Begin immediately  |  Add to Queue: Plan batch runs (max 5 cycles)")
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: rgba(0, 122, 255, 0.06);"
            "border-radius: 4px;"
            "padding: 6px 8px;"
            "margin-top: 6px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        cycle_settings_card_layout.addWidget(help_text)

        cycle_settings_section.add_content_widget(cycle_settings_card)
        tab_layout.addWidget(cycle_settings_section)

        tab_layout.addSpacing(8)

        # ==================== Section 2: Cycle History & Queue (Collapsible) ====================
        summary_section = CollapsibleSection("Cycle History & Queue", is_expanded=True)

        # Start Run Button (hidden by default)
        self.start_run_btn = QPushButton("▶ Start Queued Run")
        self.start_run_btn.setFixedHeight(36)
        self.start_run_btn.setToolTip("Execute all cycles in queue sequentially")
        self.start_run_btn.setStyleSheet(
            "QPushButton {"
            "  background: #3A3A3C;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #48484A;"
            "}"
            "QPushButton:pressed {"
            "  background: #636366;"
            "}"
        )
        self.start_run_btn.setVisible(False)  # Hidden until queue has items
        tab_layout.addWidget(self.start_run_btn)

        # Queue status row with Clear button
        queue_status_row = QHBoxLayout()
        queue_status_row.setSpacing(12)

        self.queue_status_label = QLabel("Queue: 0 cycles | Click 'Add to Queue' to plan batch runs")
        self.queue_status_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        queue_status_row.addWidget(self.queue_status_label)

        # Clear Queue button
        self.clear_queue_btn = QPushButton("🗑 Clear Queue")
        self.clear_queue_btn.setFixedHeight(24)
        self.clear_queue_btn.setVisible(False)  # Hidden when queue is empty
        self.clear_queue_btn.setToolTip("Remove all cycles from queue")
        self.clear_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #FF3B30;"
            "  border: 1px solid rgba(255, 59, 48, 0.3);"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 59, 48, 0.1);"
            "  border-color: #FF3B30;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255, 59, 48, 0.2);"
            "}"
        )
        queue_status_row.addWidget(self.clear_queue_btn)

        queue_status_row.addStretch()

        tab_layout.addLayout(queue_status_row)

        tab_layout.addSpacing(8)

        # Card container for summary table
        summary_card = QFrame()
        summary_card.setStyleSheet(card_style())
        summary_card_layout = QVBoxLayout(summary_card)
        summary_card_layout.setContentsMargins(12, 8, 12, 8)
        summary_card_layout.setSpacing(8)

        # Summary table
        self.summary_table = QTableWidget(5, 4)
        self.summary_table.setHorizontalHeaderLabels(["State", "Type", "Start", "Notes"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.summary_table.setColumnWidth(0, 80)  # Fixed width for State column
        self.summary_table.setMaximumHeight(200)
        self.summary_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 6px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 6px;"
            "  color: #1D1D1F;"
            "}"
            "QTableWidget::item:selected {"
            "  background: rgba(0, 0, 0, 0.08);"
            "  color: #1D1D1F;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #86868B;"
            "  padding: 6px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}"
        )

        # Populate with empty data
        for row in range(5):
            for col in range(4):
                self.summary_table.setItem(row, col, QTableWidgetItem(""))

        summary_card_layout.addWidget(self.summary_table)

        # Table footer with info and button
        table_footer_row = QHBoxLayout()
        table_footer_row.setSpacing(10)

        # Info legend
        info_legend = QLabel("Showing last 5 cycles")
        info_legend.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        table_footer_row.addWidget(info_legend)
        table_footer_row.addStretch()

        # View All Cycles Button
        self.open_table_btn = QPushButton("📊 View All Cycles")
        self.open_table_btn.setFixedHeight(28)
        self.open_table_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
        )
        table_footer_row.addWidget(self.open_table_btn)

        summary_card_layout.addLayout(table_footer_row)

        summary_section.add_content_widget(summary_card)
        tab_layout.addWidget(summary_section)

        # Connect button signal
        self.open_table_btn.clicked.connect(self._open_cycle_table_dialog)

    def _open_cycle_table_dialog(self):
        """Open the full cycle table dialog."""
        if self.cycle_table_dialog is None:
            self.cycle_table_dialog = CycleTableDialog(self)

            # Load sample/demo data matching SegmentDataFrame structure
            # TODO: Connect to actual data source
            sample_data = [
                {
                    "seg_id": 0,
                    "name": "1",
                    "start": 0.0,
                    "end": 300.0,
                    "ref_ch": None,
                    "unit": "RU",
                    "shift_a": 0.0,
                    "shift_b": 0.0,
                    "shift_c": 0.0,
                    "shift_d": 0.0,
                    "cycle_type": "Baseline",
                    "cycle_time": 5,
                    "note": "Initial baseline",
                    "flags": None,
                    "error": None,
                },
                {
                    "seg_id": 1,
                    "name": "2",
                    "start": 300.0,
                    "end": 600.0,
                    "ref_ch": "a",
                    "unit": "nM",
                    "shift_a": 0.125,
                    "shift_b": 0.143,
                    "shift_c": 0.098,
                    "shift_d": 0.112,
                    "cycle_type": "Concentration",
                    "cycle_time": 5,
                    "note": "[A:50] Binding test",
                    "flags": "ChA: 2",
                    "error": None,
                },
            ]
            self.cycle_table_dialog.load_cycles(sample_data)

        self.cycle_table_dialog.show()
        self.cycle_table_dialog.raise_()
        self.cycle_table_dialog.activateWindow()

    def _build_flow_tab(self, tab_layout: QVBoxLayout):
        """Build Flow tab with pump controls and cycle management (similar to Static)."""
        # Intelligence Bar section
        intel_section = QLabel("INTELLIGENCE BAR")
        intel_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(intel_section)
        tab_layout.addSpacing(8)

        # Intelligence Bar (same as Static)
        intel_bar = QFrame()
        intel_bar.setFixedHeight(36)
        intel_bar.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 6px;"
            "  border: 1px solid rgba(0, 0, 0, 0.06);"
            "}"
        )
        intel_bar_layout = QHBoxLayout(intel_bar)
        intel_bar_layout.setContentsMargins(12, 0, 12, 0)
        intel_bar_layout.setSpacing(8)

        # Status indicators
        good_status = QLabel("✓ System Ready")
        good_status.setStyleSheet(
            "font-size: 12px;"
            "color: #34C759;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        intel_bar_layout.addWidget(good_status)

        # Separator bullet
        separator = QLabel("•")
        separator.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
        )
        intel_bar_layout.addWidget(separator)

        ready_status = QLabel("→ Ready for injection")
        ready_status.setStyleSheet(
            "font-size: 12px;"
            "color: #007AFF;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        intel_bar_layout.addWidget(ready_status)

        # Countdown timer
        self.flow_countdown_label = QLabel("00:30")
        self.flow_countdown_label.setStyleSheet(
            "font-size: 11px;"
            "color: #1D1D1F;"
            "background: rgba(0, 0, 0, 0.06);"
            "padding: 2px 8px;"
            "border-radius: 4px;"
            "font-weight: 700;"
            "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
        )
        intel_bar_layout.addWidget(self.flow_countdown_label)

        intel_bar_layout.addStretch()

        tab_layout.addWidget(intel_bar)
        tab_layout.addSpacing(8)

        # ==================== Section 1: Cycle Settings (Collapsible) ====================
        flow_cycle_settings_section = CollapsibleSection("⚙ Configure Next Cycle", is_expanded=True)

        # Card container for cycle settings
        flow_cycle_settings_card = QFrame()
        flow_cycle_settings_card.setStyleSheet(card_style())
        flow_cycle_settings_card_layout = QVBoxLayout(flow_cycle_settings_card)
        flow_cycle_settings_card_layout.setContentsMargins(10, 8, 10, 8)
        flow_cycle_settings_card_layout.setSpacing(8)

        # Type row (same as Static)
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_label = QLabel("Type:")
        type_label.setFixedWidth(70)
        type_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        type_row.addWidget(type_label)

        self.flow_cycle_type_combo = QComboBox()
        self.flow_cycle_type_combo.addItems(["Auto-read", "Baseline", "Immobilization", "Concentration"])
        self.flow_cycle_type_combo.setCurrentIndex(0)
        self.flow_cycle_type_combo.setFixedWidth(140)
        self.flow_cycle_type_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        type_row.addWidget(self.flow_cycle_type_combo)
        type_row.addStretch()
        flow_cycle_settings_card_layout.addLayout(type_row)

        # Length row (same as Static)
        length_row = QHBoxLayout()
        length_row.setSpacing(8)
        length_label = QLabel("Length:")
        length_label.setFixedWidth(70)
        length_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        length_row.addWidget(length_label)

        self.flow_cycle_length_combo = QComboBox()
        self.flow_cycle_length_combo.addItems(["2 min", "5 min", "15 min", "30 min", "60 min"])
        self.flow_cycle_length_combo.setCurrentIndex(1)
        self.flow_cycle_length_combo.setFixedWidth(100)
        self.flow_cycle_length_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        length_row.addWidget(self.flow_cycle_length_combo)
        length_row.addStretch()
        flow_cycle_settings_card_layout.addLayout(length_row)

        # Note input (same as Static)
        note_label = QLabel("Note:")
        note_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_cycle_settings_card_layout.addWidget(note_label)

        # Note highlighter for Flow tab
        class FlowChannelTagHighlighter(QSyntaxHighlighter):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.tag_format = QTextCharFormat()
                self.tag_format.setForeground(QColor("#1D1D1F"))
                self.tag_format.setFontWeight(700)

                self.conc_format = QTextCharFormat()
                self.conc_format.setForeground(QColor("#34C759"))
                self.conc_format.setFontWeight(700)

            def highlightBlock(self, text):
                # Highlight [A:10], [B:50], [ALL:20] concentration tags (green)
                conc_pattern = QRegularExpression(r"\[(A|B|C|D|ALL):(\d+\.?\d*)\]")
                iterator = conc_pattern.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    self.setFormat(match.capturedStart(), match.capturedLength(), self.conc_format)

                # Highlight [A], [B], [C], [D], [ALL] tags without concentration (dark)
                tag_pattern = QRegularExpression(r"\[(A|B|C|D|ALL)\]")
                iterator = tag_pattern.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    # Only highlight if not already highlighted as concentration
                    start = match.capturedStart()
                    if self.format(start).foreground().color() != QColor("#34C759"):
                        self.setFormat(start, match.capturedLength(), self.tag_format)

        self.flow_note_input = QTextEdit()
        self.flow_note_input.setPlaceholderText("Use tags: [A] [B] [C] [D] [ALL] or with concentration [A:10] [ALL:50]  (max 250 chars)")
        self.flow_note_input.setMaximumHeight(60)
        self.flow_note_input.setStyleSheet(
            "QTextEdit {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 6px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTextEdit:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
        )

        # Apply syntax highlighter
        self.flow_note_highlighter = FlowChannelTagHighlighter(self.flow_note_input.document())

        # Character counter
        self.flow_char_count_label = QLabel("0/250 characters")
        self.flow_char_count_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )

        def update_flow_note_counter():
            text = self.flow_note_input.toPlainText()
            if len(text) > 250:
                self.flow_note_input.setPlainText(text[:250])
                self.flow_note_input.moveCursor(self.flow_note_input.textCursor().End)
            self.flow_char_count_label.setText(f"{len(self.flow_note_input.toPlainText())}/250 characters")

        self.flow_note_input.textChanged.connect(update_flow_note_counter)
        flow_cycle_settings_card_layout.addWidget(self.flow_note_input)

        # Character count and tag help
        note_info_row = QHBoxLayout()
        note_info_row.setSpacing(10)
        note_info_row.addWidget(self.flow_char_count_label)
        note_info_row.addStretch()

        tag_help_label = QLabel("💡 Tip: Tag channels with concentrations")
        tag_help_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        note_info_row.addWidget(tag_help_label)
        flow_cycle_settings_card_layout.addLayout(note_info_row)

        # Units row (same as Static)
        units_row = QHBoxLayout()
        units_row.setSpacing(8)
        units_label = QLabel("Units:")
        units_label.setFixedWidth(70)
        units_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        units_row.addWidget(units_label)

        self.flow_units_combo = QComboBox()
        self.flow_units_combo.addItems(["M (Molar)", "mM (Millimolar)", "µM (Micromolar)", "nM (Nanomolar)", "pM (Picomolar)", "mg/mL", "µg/mL", "ng/mL"])
        self.flow_units_combo.setCurrentIndex(3)  # Default to nM
        self.flow_units_combo.setFixedWidth(140)
        self.flow_units_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:focus {"
            "  border: 2px solid #1D1D1F;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox QAbstractItemView {"
            "  background-color: white;"
            "  color: #1D1D1F;"
            "  selection-background-color: rgba(0, 0, 0, 0.1);"
            "  selection-color: #1D1D1F;"
            "  outline: none;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
        )
        units_row.addWidget(self.flow_units_combo)
        units_row.addStretch()
        flow_cycle_settings_card_layout.addLayout(units_row)

        # Info about units applying to tags
        units_info = QLabel("Units apply to concentrations in tags (e.g., [A:10] = 10 nM)")
        units_info.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_cycle_settings_card_layout.addWidget(units_info)

        # Separator before execution section
        execution_separator = QFrame()
        execution_separator.setFixedHeight(1)
        execution_separator.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;"
        )
        flow_cycle_settings_card_layout.addWidget(execution_separator)

        # ==================== FLOW-SPECIFIC: Pump Controls ====================
        pump_header = QLabel("💧 Pump Controls")
        pump_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_cycle_settings_card_layout.addWidget(pump_header)

        # Toggle Polarizer button
        self.polarizer_toggle_btn = QPushButton("Toggle Polarizer")
        self.polarizer_toggle_btn.setFixedHeight(32)
        self.polarizer_toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
        )
        flow_cycle_settings_card_layout.addWidget(self.polarizer_toggle_btn)

        # Another separator before execution buttons
        execution_separator2 = QFrame()
        execution_separator2.setFixedHeight(1)
        execution_separator2.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 12px 0px 8px 0px;"
        )
        flow_cycle_settings_card_layout.addWidget(execution_separator2)

        # Execution section header
        execution_header = QLabel("🚀 Execution")
        execution_header.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_cycle_settings_card_layout.addWidget(execution_header)

        # Action Buttons (same as Static)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        # Start Cycle Button
        self.flow_start_cycle_btn = QPushButton("▶ Start Cycle")
        self.flow_start_cycle_btn.setFixedSize(120, 36)
        self.flow_start_cycle_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
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
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}"
        )
        buttons_row.addWidget(self.flow_start_cycle_btn)

        # Add to Queue Button
        self.flow_add_to_queue_btn = QPushButton("+ Add to Queue")
        self.flow_add_to_queue_btn.setFixedSize(140, 36)
        self.flow_add_to_queue_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
            "QPushButton:disabled {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  color: #86868B;"
            "}"
        )
        buttons_row.addWidget(self.flow_add_to_queue_btn)
        buttons_row.addStretch()

        flow_cycle_settings_card_layout.addLayout(buttons_row)

        # Help text with workflow explanation
        help_text = QLabel("💡 Start Cycle: Begin immediately  |  Add to Queue: Plan batch runs (max 5 cycles)")
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: rgba(0, 122, 255, 0.06);"
            "border-radius: 4px;"
            "padding: 6px 8px;"
            "margin-top: 6px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_cycle_settings_card_layout.addWidget(help_text)

        flow_cycle_settings_section.add_content_widget(flow_cycle_settings_card)
        tab_layout.addWidget(flow_cycle_settings_section)

        tab_layout.addSpacing(8)

        # ==================== Section 2: Cycle History & Queue (same as Static) ====================
        flow_summary_section = CollapsibleSection("Cycle History & Queue", is_expanded=True)

        # Start Run Button (hidden by default)
        self.flow_start_run_btn = QPushButton("▶ Start Queued Run")
        self.flow_start_run_btn.setFixedHeight(36)
        self.flow_start_run_btn.setStyleSheet(
            "QPushButton {"
            "  background: #3A3A3C;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #48484A;"
            "}"
            "QPushButton:pressed {"
            "  background: #636366;"
            "}"
        )
        self.flow_start_run_btn.setVisible(False)  # Hidden until queue has items
        flow_summary_section.content_layout.addWidget(self.flow_start_run_btn)

        # Queue status label (reuse from Static concept)
        self.flow_queue_status_label = QLabel("No cycles queued")
        self.flow_queue_status_label.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "font-style: italic;"
            "margin: 4px 0px 8px 0px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        flow_summary_section.content_layout.addWidget(self.flow_queue_status_label)

        # Cycle summary card (mini table)
        flow_summary_card = QFrame()
        flow_summary_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        flow_summary_card_layout = QVBoxLayout(flow_summary_card)
        flow_summary_card_layout.setContentsMargins(10, 8, 10, 8)
        flow_summary_card_layout.setSpacing(6)

        # Table with 3 recent cycles
        self.flow_cycle_mini_table = QTableWidget(3, 4)
        self.flow_cycle_mini_table.setHorizontalHeaderLabels(["#", "Type", "Time", "Note"])
        self.flow_cycle_mini_table.horizontalHeader().setStretchLastSection(True)
        self.flow_cycle_mini_table.verticalHeader().setVisible(False)
        self.flow_cycle_mini_table.setMaximumHeight(120)
        self.flow_cycle_mini_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 4px;"
            "  font-size: 11px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 4px;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  padding: 4px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.1);"
            "  font-weight: 600;"
            "  font-size: 10px;"
            "  color: #86868B;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        flow_summary_card_layout.addWidget(self.flow_cycle_mini_table)

        # Table footer with legend and View All button
        table_footer_row = QHBoxLayout()
        table_footer_row.setSpacing(8)

        info_legend = QLabel("📊 Showing last 3 cycles")
        info_legend.setStyleSheet(
            "font-size: 10px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        table_footer_row.addWidget(info_legend)
        table_footer_row.addStretch()

        # View All Cycles Button
        self.flow_open_table_btn = QPushButton("📊 View All Cycles")
        self.flow_open_table_btn.setFixedHeight(28)
        self.flow_open_table_btn.setStyleSheet(
            "QPushButton {"
            "  background: #636366;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #7C7C80;"
            "}"
            "QPushButton:pressed {"
            "  background: #8E8E93;"
            "}"
        )
        table_footer_row.addWidget(self.flow_open_table_btn)

        flow_summary_card_layout.addLayout(table_footer_row)

        flow_summary_section.add_content_widget(flow_summary_card)
        tab_layout.addWidget(flow_summary_section)

        # Connect button signal (reuse same dialog handler)
        self.flow_open_table_btn.clicked.connect(self._open_cycle_table_dialog)

    def _build_export_tab(self, tab_layout: QVBoxLayout):
        """Build Export tab with data export options."""
        # Section 1: Data Selection
        data_selection_section = QLabel("DATA SELECTION")
        data_selection_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(data_selection_section)
        tab_layout.addSpacing(8)

        data_selection_card = QFrame()
        data_selection_card.setStyleSheet(card_style())
        data_selection_card_layout = QVBoxLayout(data_selection_card)
        data_selection_card_layout.setContentsMargins(12, 10, 12, 10)
        data_selection_card_layout.setSpacing(8)

        # Data type checkboxes - store as instance attributes for access
        self.raw_data_check = QCheckBox("Raw Sensorgram Data")
        self.raw_data_check.setChecked(True)
        self.raw_data_check.setStyleSheet(checkbox_style())
        self.raw_data_check.setToolTip("Export unprocessed sensorgram data (time-series wavelength shifts)")
        data_selection_card_layout.addWidget(self.raw_data_check)

        self.processed_data_check = QCheckBox("Processed Data (filtered/smoothed)")
        self.processed_data_check.setChecked(True)
        self.processed_data_check.setStyleSheet(checkbox_style())
        self.processed_data_check.setToolTip("Export data with filtering and smoothing applied")
        data_selection_card_layout.addWidget(self.processed_data_check)

        self.cycle_segments_check = QCheckBox("Cycle Segments (with metadata)")
        self.cycle_segments_check.setChecked(True)
        self.cycle_segments_check.setStyleSheet(checkbox_style())
        data_selection_card_layout.addWidget(self.cycle_segments_check)

        self.summary_table_check = QCheckBox("Summary Table")
        self.summary_table_check.setChecked(True)
        self.summary_table_check.setStyleSheet(checkbox_style())
        data_selection_card_layout.addWidget(self.summary_table_check)

        tab_layout.addWidget(data_selection_card)
        tab_layout.addSpacing(16)

        # Section 2: Channel Selection
        channel_section = QLabel("CHANNEL SELECTION")
        channel_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(channel_section)
        tab_layout.addSpacing(8)

        channel_card = QFrame()
        channel_card.setStyleSheet(card_style())
        channel_card_layout = QVBoxLayout(channel_card)
        channel_card_layout.setContentsMargins(12, 10, 12, 10)
        channel_card_layout.setSpacing(8)

        # Channel checkboxes in horizontal layout
        channel_row = QHBoxLayout()
        channel_row.setSpacing(12)

        self.export_channel_checkboxes = []
        for ch in ["A", "B", "C", "D"]:
            ch_check = QCheckBox(f"Ch {ch}")
            ch_check.setChecked(True)
            ch_check.setStyleSheet(checkbox_style())
            self.export_channel_checkboxes.append(ch_check)
            channel_row.addWidget(ch_check)

        channel_row.addStretch()
        channel_card_layout.addLayout(channel_row)

        # Select All button
        self.select_all_channels_btn = QPushButton("Select All")
        self.select_all_channels_btn.setFixedHeight(28)
        self.select_all_channels_btn.setFixedWidth(100)
        self.select_all_channels_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.SECONDARY_TEXT};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 11px;"
            f"  font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.OVERLAY_LIGHT_6};"
            f"}}"
        )
        self.select_all_channels_btn.clicked.connect(self._toggle_all_channels)
        channel_card_layout.addWidget(self.select_all_channels_btn)

        tab_layout.addWidget(channel_card)
        tab_layout.addSpacing(16)

        # Section 3: Export Format
        format_section = QLabel("EXPORT FORMAT")
        format_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(format_section)
        tab_layout.addSpacing(8)

        format_card = QFrame()
        format_card.setStyleSheet(card_style())
        format_card_layout = QVBoxLayout(format_card)
        format_card_layout.setContentsMargins(12, 10, 12, 10)
        format_card_layout.setSpacing(6)

        # Format radio buttons
        self.format_group = QButtonGroup()

        self.excel_radio = QRadioButton("Excel (.xlsx) - Multi-tab workbook")
        self.excel_radio.setChecked(True)
        self.excel_radio.setStyleSheet(
            f"QRadioButton {{"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  background: transparent;"
            f"  spacing: 6px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QRadioButton::indicator {{"
            f"  width: 18px;"
            f"  height: 18px;"
            f"  border: 1.5px solid {Colors.OVERLAY_LIGHT_20};"
            f"  border-radius: 9px;"
            f"  background: white;"
            f"}}"
            f"QRadioButton::indicator:hover {{"
            f"  border-color: {Colors.OVERLAY_LIGHT_30};"
            f"}}"
            f"QRadioButton::indicator:checked {{"
            f"  background: {Colors.BUTTON_PRIMARY};"
            f"  border-color: {Colors.BUTTON_PRIMARY};"
            f"}}"
        )
        self.format_group.addButton(self.excel_radio)
        format_card_layout.addWidget(self.excel_radio)

        self.csv_radio = QRadioButton("CSV (.csv) - Single or multiple files")
        self.csv_radio.setStyleSheet(self.excel_radio.styleSheet())
        self.format_group.addButton(self.csv_radio)
        format_card_layout.addWidget(self.csv_radio)

        self.json_radio = QRadioButton("JSON (.json) - Structured data")
        self.json_radio.setStyleSheet(self.excel_radio.styleSheet())
        self.format_group.addButton(self.json_radio)
        format_card_layout.addWidget(self.json_radio)

        self.hdf5_radio = QRadioButton("HDF5 (.h5) - Large datasets")
        self.hdf5_radio.setStyleSheet(self.excel_radio.styleSheet())
        self.format_group.addButton(self.hdf5_radio)
        format_card_layout.addWidget(self.hdf5_radio)

        tab_layout.addWidget(format_card)
        tab_layout.addSpacing(16)

        # Section 4: Export Options
        options_section = QLabel("EXPORT OPTIONS")
        options_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(options_section)
        tab_layout.addSpacing(8)

        options_card = QFrame()
        options_card.setStyleSheet(card_style())
        options_card_layout = QVBoxLayout(options_card)
        options_card_layout.setContentsMargins(12, 10, 12, 10)
        options_card_layout.setSpacing(8)

        # Options checkboxes
        self.metadata_check = QCheckBox("Include Metadata (instrument settings, calibration)")
        self.metadata_check.setChecked(True)
        self.metadata_check.setStyleSheet(checkbox_style())
        options_card_layout.addWidget(self.metadata_check)

        self.events_check = QCheckBox("Include Event Markers (injection/wash/spike)")
        self.events_check.setChecked(False)
        self.events_check.setStyleSheet(checkbox_style())
        options_card_layout.addWidget(self.events_check)

        # Decimal precision
        precision_row = QHBoxLayout()
        precision_row.setSpacing(10)

        precision_label = QLabel("Decimal Precision:")
        precision_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        precision_row.addWidget(precision_label)

        self.precision_combo = QComboBox()
        self.precision_combo.addItems(["2", "3", "4", "5"])
        self.precision_combo.setCurrentIndex(2)
        self.precision_combo.setFixedWidth(80)
        self.precision_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  selection-background-color: {Colors.OVERLAY_LIGHT_10};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}"
        )
        precision_row.addWidget(self.precision_combo)
        precision_row.addStretch()
        options_card_layout.addLayout(precision_row)

        # Timestamp format
        timestamp_row = QHBoxLayout()
        timestamp_row.setSpacing(10)

        timestamp_label = QLabel("Timestamp Format:")
        timestamp_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        timestamp_row.addWidget(timestamp_label)

        self.timestamp_combo = QComboBox()
        self.timestamp_combo.addItems(["Relative (00:00:00)", "Absolute (datetime)", "Elapsed seconds"])
        self.timestamp_combo.setFixedWidth(180)
        self.timestamp_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"  font-size: 12px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: white;"
            f"  selection-background-color: {Colors.OVERLAY_LIGHT_10};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"}}"
        )
        timestamp_row.addWidget(self.timestamp_combo)
        timestamp_row.addStretch()
        options_card_layout.addLayout(timestamp_row)

        tab_layout.addWidget(options_card)
        tab_layout.addSpacing(16)

        # Section 5: File Settings & Export
        file_section = QLabel("FILE SETTINGS & EXPORT")
        file_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(file_section)
        tab_layout.addSpacing(8)

        file_card = QFrame()
        file_card.setStyleSheet(card_style())
        file_card_layout = QVBoxLayout(file_card)
        file_card_layout.setContentsMargins(12, 10, 12, 10)
        file_card_layout.setSpacing(10)

        # File name
        filename_label = QLabel("File Name:")
        filename_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(filename_label)

        self.export_filename_input = QLineEdit()
        self.export_filename_input.setPlaceholderText("experiment_20251120_143022")
        self.export_filename_input.setToolTip("Base filename (extension will be added automatically based on format)")
        self.export_filename_input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 6px 8px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QLineEdit:focus {{ border: 2px solid {Colors.PRIMARY_TEXT}; }}"
        )
        file_card_layout.addWidget(self.export_filename_input)

        # Destination folder
        dest_label = QLabel("Destination:")
        dest_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        file_card_layout.addWidget(dest_label)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)

        self.export_dest_input = QLineEdit()
        self.export_dest_input.setPlaceholderText("C:/Users/Documents/Experiments")
        self.export_dest_input.setToolTip("Default export directory (can browse or type path)")
        self.export_dest_input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: white;"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 4px;"
            f"  padding: 6px 8px;"
            f"  font-size: 13px;"
            f"  color: {Colors.PRIMARY_TEXT};"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QLineEdit:focus {{ border: 2px solid {Colors.PRIMARY_TEXT}; }}"
        )
        dest_row.addWidget(self.export_dest_input)

        self.export_browse_btn = QPushButton("Browse...")
        self.export_browse_btn.setFixedHeight(32)
        self.export_browse_btn.setFixedWidth(90)
        self.export_browse_btn.setStyleSheet(
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
        self.export_browse_btn.clicked.connect(self._browse_export_destination)
        dest_row.addWidget(self.export_browse_btn)
        file_card_layout.addLayout(dest_row)

        # Estimated file size - store as instance attribute for dynamic updates
        self.export_filesize_label = QLabel("Estimated file size: Calculating...")
        self.export_filesize_label.setStyleSheet(label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic; margin-top: 4px;")
        file_card_layout.addWidget(self.export_filesize_label)

        # Export button
        self.export_data_btn = QPushButton("📁 Export Data")
        self.export_data_btn.setFixedHeight(40)
        self.export_data_btn.setStyleSheet(primary_button_style())
        # Note: Connected in affilabs_core_ui.py to _on_export_data
        file_card_layout.addWidget(self.export_data_btn)

        tab_layout.addWidget(file_card)
        tab_layout.addSpacing(16)

        # Quick Export Presets section
        presets_label = QLabel("Quick Export Presets")
        presets_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT) + "font-weight: 600; margin-top: 4px;")
        tab_layout.addWidget(presets_label)
        tab_layout.addSpacing(4)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)

        self.quick_csv_btn = QPushButton("Quick CSV")
        self.quick_csv_btn.setFixedHeight(32)
        self.quick_csv_btn.setToolTip("Fast CSV export with all data, no metadata (ideal for quick review)")
        self.quick_csv_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: white;"
            f"  color: {Colors.SECONDARY_TEXT};"
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: 12px;"
            f"  font-weight: 500;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )
        preset_row.addWidget(self.quick_csv_btn)

        self.analysis_btn = QPushButton("Analysis Ready")
        self.analysis_btn.setFixedHeight(32)
        self.analysis_btn.setToolTip("Excel export with processed data, summary table, and metadata (ideal for analysis software)")
        self.analysis_btn.setStyleSheet(self.quick_csv_btn.styleSheet())
        preset_row.addWidget(self.analysis_btn)

        self.publication_btn = QPushButton("Publication")
        self.publication_btn.setFixedHeight(32)
        self.publication_btn.setToolTip("High-precision Excel export with all metadata (ideal for publications)")
        self.publication_btn.setStyleSheet(self.quick_csv_btn.styleSheet())
        preset_row.addWidget(self.publication_btn)

        preset_row.addStretch()
        tab_layout.addLayout(preset_row)

    def _toggle_all_channels(self):
        """Toggle all channel checkboxes."""
        all_checked = all(cb.isChecked() for cb in self.export_channel_checkboxes)
        for cb in self.export_channel_checkboxes:
            cb.setChecked(not all_checked)

    def _browse_export_destination(self):
        """Open directory picker for export destination."""
        from PySide6.QtWidgets import QFileDialog
        directory = QFileDialog.getExistingDirectory(self, "Select Export Destination")
        if directory:
            self.export_dest_input.setText(directory)

    def update_export_filesize_estimate(self, num_data_points: int, num_channels: int):
        """Update the file size estimation label based on data size.

        Args:
            num_data_points: Total number of data points across all time series
            num_channels: Number of channels selected for export
        """
        if num_data_points == 0:
            self.export_filesize_label.setText("Estimated file size: No data")
            return

        # Rough estimates per format (bytes per data point)
        bytes_per_point = {
            'csv': 20,      # Text-based, ~20 bytes per number
            'excel': 16,    # Binary, more efficient
            'json': 30,     # Text with structure overhead
            'hdf5': 12      # Most efficient binary format
        }

        # Determine selected format
        format_type = 'excel'  # Default
        if hasattr(self, 'csv_radio') and self.csv_radio.isChecked():
            format_type = 'csv'
        elif hasattr(self, 'json_radio') and self.json_radio.isChecked():
            format_type = 'json'
        elif hasattr(self, 'hdf5_radio') and self.hdf5_radio.isChecked():
            format_type = 'hdf5'

        # Calculate estimate
        bytes_estimate = num_data_points * num_channels * bytes_per_point.get(format_type, 16)

        # Add metadata overhead if enabled
        if hasattr(self, 'metadata_check') and self.metadata_check.isChecked():
            bytes_estimate += 10 * 1024  # ~10 KB for metadata

        # Format size string
        if bytes_estimate < 1024:
            size_str = f"{bytes_estimate} B"
        elif bytes_estimate < 1024 * 1024:
            size_str = f"{bytes_estimate / 1024:.1f} KB"
        elif bytes_estimate < 1024 * 1024 * 1024:
            size_str = f"{bytes_estimate / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{bytes_estimate / (1024 * 1024 * 1024):.2f} GB"

        self.export_filesize_label.setText(f"Estimated file size: ~{size_str}")

    def _build_settings_tab(self, tab_layout: QVBoxLayout):
        """Build Settings tab with organized sections: Diagnostics, Hardware Config, Calibration, Advanced."""
        # ==================== Section 1: Spectroscopy Diagnostics (Collapsible, starts collapsed) ====================
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
        self.spectro_display_toggle_btn = QPushButton("▶ Show Graphs")
        self.spectro_display_toggle_btn.setCheckable(True)
        self.spectro_display_toggle_btn.setChecked(False)
        self.spectro_display_toggle_btn.setFixedHeight(32)
        self.spectro_display_toggle_btn.setStyleSheet(
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
        self.spectro_display_toggle_btn.clicked.connect(self._on_spectro_display_toggle)
        spectroscopy_section.content_layout.addWidget(self.spectro_display_toggle_btn)

        # Card container for graph display (hidden by default)
        self.graph_card = QFrame()
        self.graph_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border-radius: 8px;"
            "}"
        )
        self.graph_card.setVisible(False)  # Hidden by default
        graph_card_layout = QVBoxLayout(self.graph_card)
        graph_card_layout.setContentsMargins(12, 10, 12, 10)
        graph_card_layout.setSpacing(10)

        # Graph toggle (Transmission / Raw Data)
        graph_toggle_row = QHBoxLayout()
        graph_toggle_row.setSpacing(0)

        self.graph_button_group = QButtonGroup(self)
        self.graph_button_group.setExclusive(True)

        self.transmission_btn = QPushButton("Transmission")
        self.transmission_btn.setCheckable(True)
        self.transmission_btn.setChecked(True)
        self.transmission_btn.setFixedHeight(28)
        self.transmission_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-top-left-radius: 6px;"
            "  border-bottom-left-radius: 6px;"
            "  border-right: none;"
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
        self.graph_button_group.addButton(self.transmission_btn, 0)
        graph_toggle_row.addWidget(self.transmission_btn)

        self.raw_data_btn = QPushButton("Raw Data")
        self.raw_data_btn.setCheckable(True)
        self.raw_data_btn.setFixedHeight(28)
        self.raw_data_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-top-right-radius: 6px;"
            "  border-bottom-right-radius: 6px;"
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
        self.graph_button_group.addButton(self.raw_data_btn, 1)
        graph_toggle_row.addWidget(self.raw_data_btn)
        graph_toggle_row.addStretch()

        graph_card_layout.addLayout(graph_toggle_row)

        # Status overlay for Transmission
        self.transmission_status_frame = QFrame()
        self.transmission_status_frame.setStyleSheet(
            "QFrame {"
            "  background: #F2F2F7;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "}"
        )
        transmission_status_layout = QVBoxLayout(self.transmission_status_frame)
        transmission_status_layout.setContentsMargins(8, 6, 8, 6)
        transmission_status_layout.setSpacing(4)

        # Status header
        transmission_status_header = QHBoxLayout()
        transmission_status_label = QLabel("Transmission:")
        transmission_status_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        transmission_status_header.addWidget(transmission_status_label)

        self.transmission_status_indicator = QLabel("● Ready")
        self.transmission_status_indicator.setStyleSheet(
            "font-size: 11px;"
            "color: #34C759;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        transmission_status_header.addWidget(self.transmission_status_indicator)
        transmission_status_header.addStretch()
        transmission_status_layout.addLayout(transmission_status_header)

        # Metrics row (FWHM and Intensity for all 4 channels)
        transmission_metrics_layout = QHBoxLayout()
        transmission_metrics_layout.setSpacing(16)

        # Create labels for each channel
        self.transmission_channel_metrics = []
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

            self.transmission_channel_metrics.append({
                'fwhm': fwhm_label,
                'intensity': intensity_label
            })

            transmission_metrics_layout.addLayout(channel_layout)

        transmission_metrics_layout.addStretch()
        transmission_status_layout.addLayout(transmission_metrics_layout)

        graph_card_layout.addWidget(self.transmission_status_frame)

        # Transmission plot (shown by default when graphs are visible)
        self.transmission_plot = pg.PlotWidget()
        self.transmission_plot.setBackground('#FFFFFF')
        self.transmission_plot.setLabel('left', 'Transmittance (%)', color='#86868B', size='10pt')
        self.transmission_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
        self.transmission_plot.showGrid(x=True, y=True, alpha=0.15)
        self.transmission_plot.setMinimumHeight(200)

        # Add legend
        legend = self.transmission_plot.addLegend(offset=(10, 10))
        legend.setBrush(pg.mkBrush(255, 255, 255, 200))  # Semi-transparent white background

        # Style axes
        self.transmission_plot.getPlotItem().getAxis('left').setPen(color='#E5E5EA', width=1)
        self.transmission_plot.getPlotItem().getAxis('bottom').setPen(color='#E5E5EA', width=1)
        self.transmission_plot.getPlotItem().getAxis('left').setTextPen('#86868B')
        self.transmission_plot.getPlotItem().getAxis('bottom').setTextPen('#86868B')

        # Create curves for 4 channels
        colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
        self.transmission_curves = []
        for i, color in enumerate(colors):
            curve = self.transmission_plot.plot(
                pen=pg.mkPen(color=color, width=2),
                name=f'Channel {chr(65+i)}'
            )
            self.transmission_curves.append(curve)

        self.transmission_plot.setVisible(True)
        graph_card_layout.addWidget(self.transmission_plot)

        # Status overlay for Raw Data
        self.raw_data_status_frame = QFrame()
        self.raw_data_status_frame.setStyleSheet(
            "QFrame {"
            "  background: #F2F2F7;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "}"
        )
        self.raw_data_status_frame.setVisible(False)  # Hidden initially
        raw_data_status_layout = QVBoxLayout(self.raw_data_status_frame)
        raw_data_status_layout.setContentsMargins(8, 6, 8, 6)
        raw_data_status_layout.setSpacing(4)

        # Status header
        raw_data_status_header = QHBoxLayout()
        raw_data_status_label = QLabel("Raw Data:")
        raw_data_status_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        raw_data_status_header.addWidget(raw_data_status_label)

        self.raw_data_status_indicator = QLabel("● Ready")
        self.raw_data_status_indicator.setStyleSheet(
            "font-size: 11px;"
            "color: #34C759;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        raw_data_status_header.addWidget(self.raw_data_status_indicator)
        raw_data_status_header.addStretch()
        raw_data_status_layout.addLayout(raw_data_status_header)

        graph_card_layout.addWidget(self.raw_data_status_frame)

        # Raw data (intensity) plot (hidden by default)
        self.raw_data_plot = pg.PlotWidget()
        self.raw_data_plot.setBackground('#FFFFFF')
        self.raw_data_plot.setLabel('left', 'Intensity (counts)', color='#86868B', size='10pt')
        self.raw_data_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
        self.raw_data_plot.showGrid(x=True, y=True, alpha=0.15)
        self.raw_data_plot.setMinimumHeight(200)
        self.raw_data_plot.setVisible(False)

        # Add legend
        legend2 = self.raw_data_plot.addLegend(offset=(10, 10))
        legend2.setBrush(pg.mkBrush(255, 255, 255, 200))  # Semi-transparent white background

        # Style axes
        self.raw_data_plot.getPlotItem().getAxis('left').setPen(color='#E5E5EA', width=1)
        self.raw_data_plot.getPlotItem().getAxis('bottom').setPen(color='#E5E5EA', width=1)
        self.raw_data_plot.getPlotItem().getAxis('left').setTextPen('#86868B')
        self.raw_data_plot.getPlotItem().getAxis('bottom').setTextPen('#86868B')

        # Create curves for 4 channels
        self.raw_data_curves = []
        for i, color in enumerate(colors):
            curve = self.raw_data_plot.plot(
                pen=pg.mkPen(color=color, width=2),
                name=f'Channel {chr(65+i)}'
            )
            self.raw_data_curves.append(curve)

        graph_card_layout.addWidget(self.raw_data_plot)

        # Connect toggle buttons to switch visibility
        self.transmission_btn.toggled.connect(self._on_spectroscopy_toggle)
        self.raw_data_btn.toggled.connect(self._on_spectroscopy_toggle)

        spectroscopy_section.add_content_widget(self.graph_card)
        tab_layout.addWidget(spectroscopy_section)

        tab_layout.addSpacing(12)

        # ==================== Section 2: Hardware Configuration (Collapsible, starts expanded) ====================
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

        # Card container for polarizer and LED options
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

        # Polarizer Positions
        polarizer_label = QLabel("Polarizer Positions:")
        polarizer_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        polarizer_led_card_layout.addWidget(polarizer_label)

        polarizer_row = QHBoxLayout()
        polarizer_row.setSpacing(12)

        # S Position
        s_position_label = QLabel("S:")
        s_position_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        polarizer_row.addWidget(s_position_label)

        self.s_position_input = QLineEdit()
        self.s_position_input.setPlaceholderText("0-180")
        self.s_position_input.setToolTip("Servo position for S polarization mode (0-180 degrees)")
        self.s_position_input.setFixedWidth(70)
        self.s_position_input.setStyleSheet(
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
        polarizer_row.addWidget(self.s_position_input)

        polarizer_row.addSpacing(16)

        # P Position
        p_position_label = QLabel("P:")
        p_position_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        polarizer_row.addWidget(p_position_label)

        self.p_position_input = QLineEdit()
        self.p_position_input.setPlaceholderText("0-180")
        self.p_position_input.setToolTip("Servo position for P polarization mode (0-180 degrees)")
        self.p_position_input.setFixedWidth(70)
        self.p_position_input.setStyleSheet(
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
        polarizer_row.addWidget(self.p_position_input)

        # Toggle S/P Button - shows current position
        self.polarizer_toggle_btn = QPushButton("Position: S")
        self.polarizer_toggle_btn.setFixedWidth(100)
        self.polarizer_toggle_btn.setFixedHeight(28)
        self.polarizer_toggle_btn.setToolTip("Click to toggle between S and P polarization modes")
        self.polarizer_toggle_btn.setStyleSheet(
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
        # Track current polarizer position
        self.current_polarizer_position = 'S'
        polarizer_row.addWidget(self.polarizer_toggle_btn)

        polarizer_row.addStretch()

        polarizer_led_card_layout.addLayout(polarizer_row)

        # Separator
        separator1 = QFrame()
        separator1.setFixedHeight(1)
        separator1.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 2px 0px;"
        )
        polarizer_led_card_layout.addWidget(separator1)

        # LED Intensity per Channel
        led_intensity_label = QLabel("LED Intensity per Channel:")
        led_intensity_label.setStyleSheet(
            "font-size: 13px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 500;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        polarizer_led_card_layout.addWidget(led_intensity_label)

        # Channel A
        channel_a_row = QHBoxLayout()
        channel_a_row.setSpacing(10)

        channel_a_label = QLabel("Channel A:")
        channel_a_label.setFixedWidth(70)
        channel_a_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        channel_a_row.addWidget(channel_a_label)

        self.channel_a_input = QLineEdit()
        self.channel_a_input.setPlaceholderText("0-255")
        self.channel_a_input.setToolTip("LED intensity for Channel A (0-255)")
        self.channel_a_input.setFixedWidth(70)
        self.channel_a_input.setStyleSheet(
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
        channel_a_row.addWidget(self.channel_a_input)
        channel_a_row.addStretch()

        polarizer_led_card_layout.addLayout(channel_a_row)

        # Channel B
        channel_b_row = QHBoxLayout()
        channel_b_row.setSpacing(10)

        channel_b_label = QLabel("Channel B:")
        channel_b_label.setFixedWidth(70)
        channel_b_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        channel_b_row.addWidget(channel_b_label)

        self.channel_b_input = QLineEdit()
        self.channel_b_input.setPlaceholderText("0-255")
        self.channel_b_input.setToolTip("LED intensity for Channel B (0-255)")
        self.channel_b_input.setFixedWidth(70)
        self.channel_b_input.setStyleSheet(
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
        channel_b_row.addWidget(self.channel_b_input)
        channel_b_row.addStretch()

        polarizer_led_card_layout.addLayout(channel_b_row)

        # Channel C
        channel_c_row = QHBoxLayout()
        channel_c_row.setSpacing(10)

        channel_c_label = QLabel("Channel C:")
        channel_c_label.setFixedWidth(70)
        channel_c_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        channel_c_row.addWidget(channel_c_label)

        self.channel_c_input = QLineEdit()
        self.channel_c_input.setPlaceholderText("0-255")
        self.channel_c_input.setToolTip("LED intensity for Channel C (0-255)")
        self.channel_c_input.setFixedWidth(70)
        self.channel_c_input.setStyleSheet(
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
        channel_c_row.addWidget(self.channel_c_input)
        channel_c_row.addStretch()

        polarizer_led_card_layout.addLayout(channel_c_row)

        # Channel D
        channel_d_row = QHBoxLayout()
        channel_d_row.setSpacing(10)

        channel_d_label = QLabel("Channel D:")
        channel_d_label.setFixedWidth(70)
        channel_d_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        channel_d_row.addWidget(channel_d_label)

        self.channel_d_input = QLineEdit()
        self.channel_d_input.setPlaceholderText("0-255")
        self.channel_d_input.setToolTip("LED intensity for Channel D (0-255)")
        self.channel_d_input.setFixedWidth(70)
        self.channel_d_input.setStyleSheet(
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
        channel_d_row.addWidget(self.channel_d_input)
        channel_d_row.addStretch()

        polarizer_led_card_layout.addLayout(channel_d_row)

        # Separator
        separator2 = QFrame()
        separator2.setFixedHeight(1)
        separator2.setStyleSheet(
            "background: rgba(0, 0, 0, 0.06);"
            "border: none;"
            "margin: 4px 0px;"
        )
        polarizer_led_card_layout.addWidget(separator2)

        # Apply Settings Button Row with Load Current and Advanced Settings icon
        settings_button_row = QHBoxLayout()
        settings_button_row.setSpacing(8)

        # Load Current Settings button
        self.load_current_settings_btn = QPushButton("↻ Load Current")
        self.load_current_settings_btn.setFixedHeight(32)
        self.load_current_settings_btn.setToolTip("Load current settings from device")
        self.load_current_settings_btn.setStyleSheet(
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
        settings_button_row.addWidget(self.load_current_settings_btn)

        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.setFixedHeight(32)
        self.apply_settings_btn.setStyleSheet(
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
        settings_button_row.addWidget(self.apply_settings_btn)

        # Advanced Settings Button (cogs icon) - inline with Apply Settings
        from PySide6.QtWidgets import QToolButton
        self.advanced_settings_btn = QPushButton("⚙")
        self.advanced_settings_btn.setFixedSize(32, 32)
        self.advanced_settings_btn.setToolTip("Advanced Settings")
        self.advanced_settings_btn.setStyleSheet(
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
        settings_button_row.addWidget(self.advanced_settings_btn)

        polarizer_led_card_layout.addLayout(settings_button_row)

        hardware_section.add_content_widget(polarizer_led_card)
        tab_layout.addWidget(hardware_section)

        tab_layout.addSpacing(12)

        # ==================== Section 3: Calibration Controls (Collapsible, starts collapsed) ====================
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

        # Card container for calibration buttons
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
        simple_led_label = QLabel("Simple LED Calibration")
        simple_led_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(simple_led_label)

        simple_led_desc = QLabel("Quick LED intensity adjustment for all channels")
        simple_led_desc.setWordWrap(True)
        simple_led_desc.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(simple_led_desc)

        self.simple_led_calibration_btn = QPushButton("Run Simple Calibration")
        self.simple_led_calibration_btn.setFixedHeight(36)
        self.simple_led_calibration_btn.setStyleSheet(
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
        calibration_card_layout.addWidget(self.simple_led_calibration_btn)

        # Spacer
        calibration_card_layout.addSpacing(12)

        # Full Calibration
        full_calib_label = QLabel("Full System Calibration")
        full_calib_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(full_calib_label)

        full_calib_desc = QLabel("Complete calibration including dark reference and LED optimization")
        full_calib_desc.setWordWrap(True)
        full_calib_desc.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(full_calib_desc)

        self.full_calibration_btn = QPushButton("Run Full Calibration")
        self.full_calibration_btn.setFixedHeight(36)
        self.full_calibration_btn.setStyleSheet(
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
        calibration_card_layout.addWidget(self.full_calibration_btn)

        # Spacer
        calibration_card_layout.addSpacing(12)

        # OEM LED Calibration
        oem_led_label = QLabel("OEM LED Calibration")
        oem_led_label.setStyleSheet(
            "font-size: 12px;"
            "color: #1D1D1F;"
            "background: transparent;"
            "font-weight: 600;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(oem_led_label)

        oem_led_desc = QLabel("Factory-level calibration for LED driver settings (advanced users)")
        oem_led_desc.setWordWrap(True)
        oem_led_desc.setStyleSheet(
            "font-size: 11px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 4px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        calibration_card_layout.addWidget(oem_led_desc)

        self.oem_led_calibration_btn = QPushButton("Run OEM Calibration")
        self.oem_led_calibration_btn.setFixedHeight(36)
        self.oem_led_calibration_btn.setStyleSheet(
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
        calibration_card_layout.addWidget(self.oem_led_calibration_btn)

        calibration_section.add_content_widget(calibration_card)
        tab_layout.addWidget(calibration_section)

        tab_layout.addSpacing(20)

        # Connect button signals
        self.polarizer_toggle_btn.clicked.connect(self.toggle_polarizer_position)
        # Note: advanced_settings_btn and other calibration buttons should be connected
        # by the parent window to access the full application context

    def _on_spectro_display_toggle(self, checked):
        """Toggle visibility of spectroscopy graphs."""
        self.graph_card.setVisible(checked)
        if checked:
            self.spectro_display_toggle_btn.setText("▼ Hide Graphs")
        else:
            self.spectro_display_toggle_btn.setText("▶ Show Graphs")

    def _on_spectroscopy_toggle(self, checked):
        """Toggle between transmission and raw data plots."""
        if not checked:  # Button was unchecked (another button was selected)
            return

        # Show the selected plot/status and hide the other
        if self.transmission_btn.isChecked():
            self.transmission_plot.setVisible(True)
            self.transmission_status_frame.setVisible(True)
            self.raw_data_plot.setVisible(False)
            self.raw_data_status_frame.setVisible(False)
        elif self.raw_data_btn.isChecked():
            self.transmission_plot.setVisible(False)
            self.transmission_status_frame.setVisible(False)
            self.raw_data_plot.setVisible(True)
            self.raw_data_status_frame.setVisible(True)

    def toggle_polarizer_position(self):
        """Toggle polarizer between S and P positions and update button text."""
        if self.current_polarizer_position == 'S':
            self.current_polarizer_position = 'P'
            self.polarizer_toggle_btn.setText("Position: P")
        else:
            self.current_polarizer_position = 'S'
            self.polarizer_toggle_btn.setText("Position: S")

        # This method can be called from main window to actually move the polarizer
        # and will return the new position
        return self.current_polarizer_position

    def set_polarizer_position(self, position: str):
        """Set polarizer position (S or P) and update button text.

        Args:
            position: 'S' or 'P'
        """
        position = position.upper()
        if position not in ['S', 'P']:
            return

        self.current_polarizer_position = position
        self.polarizer_toggle_btn.setText(f"Position: {position}")

    def update_transmission_metrics(self, channel: int, fwhm: float | None = None, intensity: float | None = None):
        """Update transmission metrics for a specific channel.

        Args:
            channel: Channel index (0-3)
            fwhm: Full width at half maximum in nm (optional)
            intensity: Peak intensity as percentage (optional)
        """
        if not hasattr(self, 'transmission_channel_metrics'):
            return

        if 0 <= channel < len(self.transmission_channel_metrics):
            metrics = self.transmission_channel_metrics[channel]

            if fwhm is not None:
                metrics['fwhm'].setText(f"FWHM: {fwhm:.1f}nm")

            if intensity is not None:
                metrics['intensity'].setText(f"Int: {intensity:.0f}%")

    def update_spectroscopy_status(self, status: str, color: str = "#34C759"):
        """Update spectroscopy status indicator.

        Args:
            status: Status text (e.g., "Ready", "Acquiring", "Error")
            color: Color code for status indicator (default: green)
        """
        if hasattr(self, 'transmission_status_indicator'):
            self.transmission_status_indicator.setText(f"● {status}")
            self.transmission_status_indicator.setStyleSheet(
                f"font-size: 11px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

        if hasattr(self, 'raw_data_status_indicator'):
            self.raw_data_status_indicator.setText(f"● {status}")
            self.raw_data_status_indicator.setStyleSheet(
                f"font-size: 11px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def load_hardware_settings(self, s_pos: int = None, p_pos: int = None,
                               led_a: int = None, led_b: int = None,
                               led_c: int = None, led_d: int = None):
        """Load hardware settings into the input fields.

        Args:
            s_pos: S-mode servo position (0-180)
            p_pos: P-mode servo position (0-180)
            led_a: Channel A LED intensity (0-255)
            led_b: Channel B LED intensity (0-255)
            led_c: Channel C LED intensity (0-255)
            led_d: Channel D LED intensity (0-255)
        """
        if s_pos is not None and hasattr(self, 's_position_input'):
            self.s_position_input.setText(str(s_pos))

        if p_pos is not None and hasattr(self, 'p_position_input'):
            self.p_position_input.setText(str(p_pos))

        if led_a is not None and hasattr(self, 'channel_a_input'):
            self.channel_a_input.setText(str(led_a))

        if led_b is not None and hasattr(self, 'channel_b_input'):
            self.channel_b_input.setText(str(led_b))

        if led_c is not None and hasattr(self, 'channel_c_input'):
            self.channel_c_input.setText(str(led_c))

        if led_d is not None and hasattr(self, 'channel_d_input'):
            self.channel_d_input.setText(str(led_d))

    def update_queue_status(self, count: int):
        """Update queue status display and button visibility.

        Args:
            count: Number of cycles currently in queue (0-5)
        """
        if hasattr(self, 'queue_status_label'):
            if count == 0:
                self.queue_status_label.setText("Queue: 0 cycles | Click 'Add to Queue' to plan batch runs")
            else:
                self.queue_status_label.setText(f"Queue: {count} cycle{'s' if count > 1 else ''} ready")

        if hasattr(self, 'clear_queue_btn'):
            self.clear_queue_btn.setVisible(count > 0)

        if hasattr(self, 'start_run_btn'):
            self.start_run_btn.setVisible(count > 0)

    def update_operation_hours(self, hours: int):
        """Update the operation hours display."""
        if hasattr(self, 'hours_value'):
            self.hours_value.setText(f"{hours:,} hrs")

    def update_last_operation(self, date_str: str):
        """Update the last operation date display."""
        if hasattr(self, 'last_op_value'):
            self.last_op_value.setText(date_str)

    def update_next_maintenance(self, date_str: str, is_overdue: bool = False):
        """Update the next maintenance date display.

        Args:
            date_str: Date string to display
            is_overdue: If True, display in red warning color
        """
        if hasattr(self, 'next_maintenance_value'):
            color = "#FF3B30" if is_overdue else "#FF9500"
            self.next_maintenance_value.setText(date_str)
            self.next_maintenance_value.setStyleSheet(
                label_style(13, color) + "font-weight: 600; margin-top: 6px;"
            )

    def show_settings_applied_feedback(self):
        """Provide visual feedback when settings are successfully applied."""
        if hasattr(self, 'apply_settings_btn'):
            # Store original style
            original_style = self.apply_settings_btn.styleSheet()

            # Change to success style temporarily
            self.apply_settings_btn.setText("✓ Applied")
            self.apply_settings_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )

            # Reset after 2 seconds
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self._reset_apply_button(original_style))

    def _reset_apply_button(self, original_style: str):
        """Reset the apply button to its original state."""
        if hasattr(self, 'apply_settings_btn'):
            self.apply_settings_btn.setText("Apply Settings")
            self.apply_settings_btn.setStyleSheet(original_style)
