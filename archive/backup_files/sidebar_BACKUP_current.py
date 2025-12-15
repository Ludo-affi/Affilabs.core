"""SidebarPrototype extracted from LL_UI_v1_0.py for modularity."""

import pyqtgraph as pg
from plot_helpers import add_channel_curves, create_spectroscopy_plot, create_time_plot
from PySide6.QtCore import Qt
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
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from ui_styles import (
    Colors,
    card_style,
    checkbox_style,
    label_style,
    primary_button_style,
    scrollbar_style,
    section_header_style,
    segmented_button_style,
    spinbox_style,
    title_style,
)

# Colorblind-safe palette (Tol bright scheme)
COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]


class SidebarPrototype(QWidget):
    """Simplified sidebar prototype containing tabbed UI sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self._setup_ui()

    def _setup_ui(self):
        if getattr(self, "_ui_setup_done", False):
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
                padding: 8px 20px;
                margin: 2px 0;
                border: none;
                font-size: 13px;
                font-weight: 500;
                min-height: 32px;
                border-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {Colors.BACKGROUND_WHITE};
                color: {Colors.PRIMARY_TEXT};
            }}
            QTabBar::tab:hover:!selected {{
                background: {Colors.OVERLAY_LIGHT_6};
            }}
        """)

        # Tab definitions with builder method mapping
        tab_definitions = [
            ("Device Status", "Device Status", self._build_device_status_tab),
            ("Graphic Control", "Graphic Control", self._build_graphic_control_tab),
            ("Static", "Static", self._build_static_tab),
            ("Flow", "Flow", self._build_flow_tab),
            ("Export", "Export", self._build_export_tab),
            ("Settings", "Settings", self._build_settings_tab),
        ]

        for label, tooltip, builder_method in tab_definitions:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet(scrollbar_style())

            tab_content = QWidget()
            tab_content.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            title = QLabel(tooltip)
            title.setStyleSheet(title_style())
            tab_layout.addWidget(title)

            # Call specific builder method for tab content
            builder_method(tab_layout)

            self.tab_widget.addTab(scroll_area, label)
            scroll_area.setWidget(tab_content)

        container_layout.addWidget(self.tab_widget)
        # Compatibility alias expected by main code
        self.tabs = self.tab_widget
        main_layout.addWidget(container)
        self.setUpdatesEnabled(True)

    def _build_device_status_tab(self, tab_layout: QVBoxLayout):
        """Build Device Status tab with hardware and subunit indicators."""
        tab_layout.addSpacing(12)
        hw_section = QLabel("HARDWARE CONNECTED")
        hw_section.setStyleSheet(section_header_style())
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
            device_label.setStyleSheet(
                label_style(13, Colors.SUCCESS) + "padding: 4px 0px;",
            )
            device_label.setVisible(False)
            hw_card_layout.addWidget(device_label)
            self.hw_device_labels.append(device_label)

        self.hw_no_devices = QLabel("No hardware detected")
        self.hw_no_devices.setStyleSheet(
            label_style(13, Colors.SECONDARY_TEXT)
            + "padding: 8px 0px;font-style: italic;",
        )
        hw_card_layout.addWidget(self.hw_no_devices)

        self.scan_btn = QPushButton("🔍 Scan for Hardware")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setStyleSheet(primary_button_style())
        hw_card_layout.addWidget(self.scan_btn)

        # Subunit status indicators (original names: Sensor/Optics/Fluidics)
        hw_card_layout.addSpacing(12)
        subunit_section = QLabel("SUBUNIT STATUS")
        subunit_section.setStyleSheet(section_header_style())
        hw_card_layout.addWidget(subunit_section)

        self.subunit_status = {}
        subunit_names = ["Sensor", "Optics", "Fluidics"]
        for idx, name in enumerate(subunit_names):
            if idx > 0:  # Add separator between items
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06); border: none; margin: 4px 0;",
                )
                hw_card_layout.addWidget(separator)

            status_row = QHBoxLayout()
            status_row.setSpacing(8)
            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; font-size: 16px;")
            indicator.setFixedWidth(20)
            status_label = QLabel(f"{name}: Not Ready")
            status_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
            status_row.addWidget(indicator)
            status_row.addWidget(status_label, 1)
            hw_card_layout.addLayout(status_row)
            self.subunit_status[name.lower()] = {
                "indicator": indicator,
                "status_label": status_label,
            }

        tab_layout.addWidget(hw_card)
        tab_layout.addSpacing(16)

        # Operation Modes section
        modes_section = QLabel("OPERATION MODES")
        modes_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(modes_section)
        tab_layout.addSpacing(8)

        modes_card = QFrame()
        modes_card.setStyleSheet(card_style())
        modes_card_layout = QVBoxLayout(modes_card)
        modes_card_layout.setContentsMargins(12, 12, 12, 12)
        modes_card_layout.setSpacing(8)

        self.operation_modes = {}
        for mode_name, mode_label in [("static", "Static"), ("flow", "Flow")]:
            mode_row = QHBoxLayout()
            mode_row.setSpacing(8)
            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; font-size: 16px;")
            indicator.setFixedWidth(20)
            label = QLabel(mode_label)
            label.setStyleSheet(
                label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;",
            )
            status_label = QLabel("Disabled")
            status_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
            mode_row.addWidget(indicator)
            mode_row.addWidget(label)
            mode_row.addStretch()
            mode_row.addWidget(status_label)
            modes_card_layout.addLayout(mode_row)
            self.operation_modes[mode_name] = {
                "indicator": indicator,
                "label": label,
                "status_label": status_label,
            }

        tab_layout.addWidget(modes_card)
        tab_layout.addSpacing(16)

        # Maintenance section
        maint_title = QLabel("Maintenance")
        maint_title.setStyleSheet(
            label_style(15, Colors.PRIMARY_TEXT) + "font-weight: 600; margin-top: 8px;",
        )
        tab_layout.addWidget(maint_title)
        tab_layout.addSpacing(8)

        maint_divider = QFrame()
        maint_divider.setFixedHeight(1)
        maint_divider.setStyleSheet("background: rgba(0, 0, 0, 0.1); border: none;")
        tab_layout.addWidget(maint_divider)
        tab_layout.addSpacing(8)

        maint_card = QFrame()
        maint_card.setStyleSheet(card_style())
        maint_card_layout = QVBoxLayout(maint_card)
        maint_card_layout.setContentsMargins(12, 12, 12, 12)
        maint_card_layout.setSpacing(8)

        # Operation Hours
        hours_row = QHBoxLayout()
        hours_label = QLabel("Operation Hours:")
        hours_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        self.hours_value = QLabel("1,247 hrs")
        self.hours_value.setStyleSheet(
            label_style(12, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        hours_row.addWidget(hours_label)
        hours_row.addStretch()
        hours_row.addWidget(self.hours_value)
        maint_card_layout.addLayout(hours_row)

        # Last Operation
        last_op_row = QHBoxLayout()
        last_op_label = QLabel("Last Operation:")
        last_op_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        self.last_op_value = QLabel("Nov 19, 2025")
        self.last_op_value.setStyleSheet(
            label_style(12, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        last_op_row.addWidget(last_op_label)
        last_op_row.addStretch()
        last_op_row.addWidget(self.last_op_value)
        maint_card_layout.addLayout(last_op_row)

        # Annual Maintenance (with orange warning color)
        next_maint_row = QHBoxLayout()
        next_maint_label = QLabel("Annual Maintenance:")
        next_maint_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        self.next_maintenance_value = QLabel("November 2025")
        self.next_maintenance_value.setStyleSheet(
            label_style(12, Colors.WARNING) + "font-weight: 600;",
        )
        next_maint_row.addWidget(next_maint_label)
        next_maint_row.addStretch()
        next_maint_row.addWidget(self.next_maintenance_value)
        maint_card_layout.addLayout(next_maint_row)

        tab_layout.addWidget(maint_card)
        tab_layout.addSpacing(16)

        # Debug Log Download button (moved from Export tab)
        debug_btn_container = QFrame()
        debug_btn_container.setStyleSheet(card_style())
        debug_btn_layout = QVBoxLayout(debug_btn_container)
        debug_btn_layout.setContentsMargins(12, 12, 12, 12)
        self.debug_log_btn = QPushButton("Download Debug Log")
        self.debug_log_btn.setFixedHeight(36)
        self.debug_log_btn.setStyleSheet(primary_button_style())
        debug_btn_layout.addWidget(self.debug_log_btn)
        tab_layout.addWidget(debug_btn_container)
        tab_layout.addSpacing(16)

        # Software Version
        version_label = QLabel("AffiLabs.core Beta")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-weight: 500;",
        )
        tab_layout.addWidget(version_label)

    def _build_graphic_control_tab(self, tab_layout: QVBoxLayout):
        """Build Graphic Control tab with plots, axes, filters, and accessibility."""
        gc_section = QLabel("PLOT / DISPLAY")
        gc_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(gc_section)

        gc_card = QFrame()
        gc_card.setStyleSheet(card_style())
        gc_layout = QVBoxLayout(gc_card)
        gc_layout.setContentsMargins(12, 12, 12, 12)
        gc_layout.setSpacing(6)

        # Real pyqtgraph plots
        self.transmission_plot = create_time_plot("Transmission (%)", "Time (s)")
        self.transmission_curves = add_channel_curves(self.transmission_plot)
        self.raw_data_plot = create_spectroscopy_plot("Intensity", "Wavelength (nm)")
        self.raw_data_curves = add_channel_curves(self.raw_data_plot)
        gc_layout.addWidget(self.transmission_plot)
        gc_layout.addWidget(self.raw_data_plot)

        # Axis controls
        gc_layout.addSpacing(8)
        axis_row = QHBoxLayout()
        axis_row.setSpacing(8)
        self.x_axis_btn = QPushButton("X Axis Auto")
        self.x_axis_btn.setFixedHeight(32)
        self.x_axis_btn.setStyleSheet(segmented_button_style())
        self.y_axis_btn = QPushButton("Y Axis Auto")
        self.y_axis_btn.setFixedHeight(32)
        self.y_axis_btn.setStyleSheet(segmented_button_style())
        axis_row.addWidget(self.x_axis_btn)
        axis_row.addWidget(self.y_axis_btn)
        gc_layout.addLayout(axis_row)

        self.grid_check = QCheckBox("Grid")
        gc_layout.addWidget(self.grid_check)

        # Axis mode toggle logic
        self._x_auto = True
        self._y_auto = True

        def _apply_axis_mode(axis: str, auto: bool):
            for plot in (self.transmission_plot, self.raw_data_plot):
                plot.getPlotItem().enableAutoRange(axis, auto)
                if auto:
                    plot.getPlotItem().getViewBox().autoRange()

        def _toggle_x():
            self._x_auto = not self._x_auto
            self.x_axis_btn.setText(
                "X Axis Auto" if not self._x_auto else "X Axis Manual",
            )
            _apply_axis_mode("x", self._x_auto)

        def _toggle_y():
            self._y_auto = not self._y_auto
            self.y_axis_btn.setText(
                "Y Axis Auto" if not self._y_auto else "Y Axis Manual",
            )
            _apply_axis_mode("y", self._y_auto)

        self.x_axis_btn.clicked.connect(_toggle_x)
        self.y_axis_btn.clicked.connect(_toggle_y)

        # Grid toggle
        def _toggle_grid(checked: bool):
            for plot in (self.transmission_plot, self.raw_data_plot):
                plot.showGrid(x=checked, y=checked, alpha=0.15 if checked else 0.0)

        self.grid_check.toggled.connect(_toggle_grid)

        # Reference combo
        ref_row = QHBoxLayout()
        ref_row.setSpacing(10)
        ref_label = QLabel("Reference:")
        ref_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        ref_row.addWidget(ref_label)
        self.ref_combo = QComboBox()
        self.ref_combo.addItems(
            ["None", "Channel A", "Channel B", "Channel C", "Channel D"],
        )
        self.ref_combo.setFixedWidth(120)
        ref_row.addWidget(self.ref_combo)
        ref_row.addStretch()
        gc_layout.addLayout(ref_row)

        # Reference info text
        ref_info = QLabel("Selected channel shown as faded dashed line")
        ref_info.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-style: italic;",
        )
        gc_layout.addWidget(ref_info)

        # Wire reference combo
        self.ref_combo.currentIndexChanged.connect(
            lambda idx: print(f"Reference changed to: {self.ref_combo.currentText()}"),
        )

        # Filter controls
        gc_layout.addSpacing(12)
        filter_header = QLabel("Data Filtering")
        filter_header.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        gc_layout.addWidget(filter_header)

        self.filter_enable = QCheckBox("Enable Filter")
        self.filter_slider = QSlider(Qt.Horizontal)
        self.filter_slider.setMinimum(1)
        self.filter_slider.setMaximum(50)
        self.filter_slider.setValue(5)
        self.filter_value_label = QLabel("Filter Size: 5")
        self.filter_slider.valueChanged.connect(
            lambda v: self.filter_value_label.setText(f"Filter Size: {v}"),
        )
        gc_layout.addWidget(self.filter_enable)
        gc_layout.addWidget(self.filter_slider)
        gc_layout.addWidget(self.filter_value_label)

        # Filter method radios
        filter_row = QHBoxLayout()
        self.median_filter_radio = QRadioButton("Median")
        self.kalman_filter_radio = QRadioButton("Kalman")
        self.sg_filter_radio = QRadioButton("SavGol")
        self.median_filter_radio.setChecked(True)
        filter_row.addWidget(self.median_filter_radio)
        filter_row.addWidget(self.kalman_filter_radio)
        filter_row.addWidget(self.sg_filter_radio)
        gc_layout.addLayout(filter_row)

        # Filter enable/disable cohesion
        def _filter_enable_changed(checked: bool):
            self.filter_slider.setEnabled(checked)
            self.filter_value_label.setEnabled(checked)
            for w in (
                self.median_filter_radio,
                self.kalman_filter_radio,
                self.sg_filter_radio,
            ):
                w.setEnabled(checked)

        self.filter_enable.toggled.connect(_filter_enable_changed)
        _filter_enable_changed(False)

        tab_layout.addWidget(gc_card)
        tab_layout.addSpacing(16)

        # Data Pipeline section
        pipeline_section = QLabel("DATA PIPELINE")
        pipeline_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(pipeline_section)
        tab_layout.addSpacing(8)

        pipeline_card = QFrame()
        pipeline_card.setStyleSheet(card_style())
        pipeline_card_layout = QVBoxLayout(pipeline_card)
        pipeline_card_layout.setContentsMargins(12, 10, 12, 10)
        pipeline_card_layout.setSpacing(10)

        pipeline_label = QLabel("Processing:")
        pipeline_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        pipeline_card_layout.addWidget(pipeline_label)

        pipeline_row = QHBoxLayout()
        pipeline_row.setSpacing(10)
        self.pipeline_method_group = QButtonGroup()
        self.pipeline1_radio = QRadioButton("Pipeline 1")
        self.pipeline1_radio.setChecked(True)
        self.pipeline1_radio.setStyleSheet(checkbox_style())
        self.pipeline_method_group.addButton(self.pipeline1_radio, 0)
        pipeline_row.addWidget(self.pipeline1_radio)

        self.pipeline2_radio = QRadioButton("Pipeline 2")
        self.pipeline2_radio.setStyleSheet(checkbox_style())
        self.pipeline_method_group.addButton(self.pipeline2_radio, 1)
        pipeline_row.addWidget(self.pipeline2_radio)
        pipeline_row.addStretch()
        pipeline_card_layout.addLayout(pipeline_row)

        tab_layout.addWidget(pipeline_card)
        tab_layout.addSpacing(16)

        # Graphic Display section (with note)
        display_section = QLabel("GRAPHIC DISPLAY")
        display_section.setStyleSheet(section_header_style())
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

        # Channel selector
        channel_row = QHBoxLayout()
        channel_row.setSpacing(10)
        channel_label = QLabel("Channel:")
        channel_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        channel_row.addWidget(channel_label)

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["All", "A", "B", "C", "D"])
        self.channel_combo.setFixedWidth(70)
        channel_row.addWidget(self.channel_combo)
        channel_row.addStretch()
        display_card_layout.addLayout(channel_row)

        # Marker selector
        marker_row = QHBoxLayout()
        marker_row.setSpacing(10)
        marker_label = QLabel("Markers:")
        marker_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        marker_row.addWidget(marker_label)

        self.marker_combo = QComboBox()
        self.marker_combo.addItems(["Circle", "Triangle", "Square", "Star"])
        self.marker_combo.setFixedWidth(90)
        marker_row.addWidget(self.marker_combo)
        marker_row.addStretch()
        display_card_layout.addLayout(marker_row)

        tab_layout.addWidget(display_card)
        tab_layout.addSpacing(16)

        # Visual Accessibility section
        accessibility_section = QLabel("VISUAL ACCESSIBILITY")
        accessibility_section.setStyleSheet(section_header_style())
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
        accessibility_card_layout.addWidget(self.colorblind_check)

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
            for plot, curves in [
                (self.transmission_plot, self.transmission_curves),
                (self.raw_data_plot, self.raw_data_curves),
            ]:
                for i, curve in enumerate(curves):
                    new_pen = pg.mkPen(color=palette[i], width=2)
                    curve.setPen(new_pen)
                    curve.original_pen = new_pen
                    curve.selected_pen = pg.mkPen(color=palette[i], width=4)

        self.colorblind_check.toggled.connect(_toggle_colorblind)

        tab_layout.addWidget(accessibility_card)

    def _build_static_tab(self, tab_layout: QVBoxLayout):
        """Build Static tab with cycle management controls and queue table."""
        static_section = QLabel("CYCLE MANAGEMENT")
        static_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(static_section)

        static_card = QFrame()
        static_card.setStyleSheet(card_style())
        static_layout = QVBoxLayout(static_card)
        static_layout.setContentsMargins(12, 12, 12, 12)
        static_layout.setSpacing(6)

        self.start_cycle_btn = QPushButton("Start Cycle")
        self.start_cycle_btn.setFixedHeight(36)
        self.start_cycle_btn.setStyleSheet(primary_button_style())
        static_layout.addWidget(self.start_cycle_btn)

        self.add_to_queue_btn = QPushButton("Add to Queue")
        self.add_to_queue_btn.setFixedHeight(36)
        self.add_to_queue_btn.setStyleSheet(primary_button_style())
        static_layout.addWidget(self.add_to_queue_btn)

        self.open_table_btn = QPushButton("Open Full Table")
        self.open_table_btn.setFixedHeight(36)
        self.open_table_btn.setStyleSheet(primary_button_style())
        static_layout.addWidget(self.open_table_btn)

        static_layout.addSpacing(8)

        # Summary table with styling
        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setHorizontalHeaderLabels(
            ["State", "Type", "Start", "Notes"],
        )
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BACKGROUND_WHITE};
                gridline-color: {Colors.OVERLAY_LIGHT_10};
                border: 1px solid {Colors.OVERLAY_LIGHT_10};
                border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: {Colors.BACKGROUND_LIGHT};
                color: {Colors.PRIMARY_TEXT};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 2px solid {Colors.OVERLAY_LIGHT_10};
            }}
        """)
        static_layout.addWidget(self.summary_table)
        tab_layout.addWidget(static_card)

    def _build_flow_tab(self, tab_layout: QVBoxLayout):
        """Build Flow tab with polarizer, channel settings, and calibration."""
        flow_section = QLabel("FLOW / SETTINGS")
        flow_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(flow_section)

        flow_card = QFrame()
        flow_card.setStyleSheet(card_style())
        flow_layout = QVBoxLayout(flow_card)
        flow_layout.setContentsMargins(12, 12, 12, 12)
        flow_layout.setSpacing(6)

        # Polarizer controls
        polarizer_label = QLabel("Polarizer Positions:")
        polarizer_label.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        flow_layout.addWidget(polarizer_label)

        pol_row = QHBoxLayout()
        pol_row.setSpacing(12)

        s_label = QLabel("S:")
        s_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        pol_row.addWidget(s_label)

        self.s_position_input = QSpinBox()
        self.s_position_input.setRange(0, 255)
        self.s_position_input.setValue(0)
        self.s_position_input.setFixedWidth(70)
        self.s_position_input.setStyleSheet(spinbox_style())
        pol_row.addWidget(self.s_position_input)

        pol_row.addSpacing(16)

        p_label = QLabel("P:")
        p_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
        pol_row.addWidget(p_label)

        self.p_position_input = QSpinBox()
        self.p_position_input.setRange(0, 255)
        self.p_position_input.setValue(0)
        self.p_position_input.setFixedWidth(70)
        self.p_position_input.setStyleSheet(spinbox_style())
        pol_row.addWidget(self.p_position_input)

        self.polarizer_toggle_btn = QPushButton("Position: S")
        self.polarizer_toggle_btn.setFixedSize(100, 28)
        self.polarizer_toggle_btn.setStyleSheet(primary_button_style())
        pol_row.addWidget(self.polarizer_toggle_btn)
        pol_row.addStretch()

        flow_layout.addLayout(pol_row)
        flow_layout.addSpacing(12)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            f"background: {Colors.OVERLAY_LIGHT_6}; border: none; margin: 4px 0;",
        )
        flow_layout.addWidget(separator)
        flow_layout.addSpacing(8)

        # Channel inputs
        led_label = QLabel("LED Intensity per Channel:")
        led_label.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        flow_layout.addWidget(led_label)

        self.channel_a_input = QLineEdit()
        self.channel_a_input.setPlaceholderText("0-4095")
        self.channel_b_input = QLineEdit()
        self.channel_b_input.setPlaceholderText("0-4095")
        self.channel_c_input = QLineEdit()
        self.channel_c_input.setPlaceholderText("0-4095")
        self.channel_d_input = QLineEdit()
        self.channel_d_input.setPlaceholderText("0-4095")

        for lbl, w in [
            ("Channel A:", self.channel_a_input),
            ("Channel B:", self.channel_b_input),
            ("Channel C:", self.channel_c_input),
            ("Channel D:", self.channel_d_input),
        ]:
            ch_row = QHBoxLayout()
            ch_row.setSpacing(10)
            ch_label = QLabel(lbl)
            ch_label.setFixedWidth(70)
            ch_label.setStyleSheet(label_style(12, Colors.PRIMARY_TEXT))
            ch_row.addWidget(ch_label)
            w.setFixedWidth(80)
            ch_row.addWidget(w)
            ch_row.addStretch()
            flow_layout.addLayout(ch_row)

        flow_layout.addSpacing(8)

        # Separator
        separator2 = QFrame()
        separator2.setFixedHeight(1)
        separator2.setStyleSheet(
            f"background: {Colors.OVERLAY_LIGHT_6}; border: none; margin: 4px 0;",
        )
        flow_layout.addWidget(separator2)
        flow_layout.addSpacing(8)

        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.setFixedHeight(36)
        self.apply_settings_btn.setStyleSheet(primary_button_style())
        flow_layout.addWidget(self.apply_settings_btn)

        flow_layout.addSpacing(12)

        # Calibration buttons
        calib_label = QLabel("Calibration:")
        calib_label.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600; margin-top: 8px;",
        )
        flow_layout.addWidget(calib_label)

        self.simple_led_calibration_btn = QPushButton("Simple LED Calibration")
        self.simple_led_calibration_btn.setFixedHeight(32)
        self.simple_led_calibration_btn.setStyleSheet(primary_button_style())
        flow_layout.addWidget(self.simple_led_calibration_btn)

        self.full_calibration_btn = QPushButton("Full Calibration")
        self.full_calibration_btn.setFixedHeight(32)
        self.full_calibration_btn.setStyleSheet(primary_button_style())
        flow_layout.addWidget(self.full_calibration_btn)

        self.oem_led_calibration_btn = QPushButton("OEM Calibration")
        self.oem_led_calibration_btn.setFixedHeight(32)
        self.oem_led_calibration_btn.setStyleSheet(primary_button_style())
        flow_layout.addWidget(self.oem_led_calibration_btn)

        tab_layout.addWidget(flow_card)

    def _build_export_tab(self, tab_layout: QVBoxLayout):
        """Build Export tab with quick export and debug log buttons."""
        export_section = QLabel("EXPORT")
        export_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(export_section)

        export_card = QFrame()
        export_card.setStyleSheet(card_style())
        export_layout = QVBoxLayout(export_card)
        export_layout.setContentsMargins(12, 12, 12, 12)
        export_layout.setSpacing(6)

        self.quick_export_csv_btn = QPushButton("Quick CSV Export")
        self.quick_export_csv_btn.setFixedHeight(36)
        self.quick_export_csv_btn.setStyleSheet(primary_button_style())
        export_layout.addWidget(self.quick_export_csv_btn)

        self.quick_export_image_btn = QPushButton("Quick Image Export")
        self.quick_export_image_btn.setFixedHeight(36)
        self.quick_export_image_btn.setStyleSheet(primary_button_style())
        export_layout.addWidget(self.quick_export_image_btn)

        # Note: Debug Log button moved to Device Status tab

        # Placeholder actions
        self.quick_export_csv_btn.clicked.connect(
            lambda: print("CSV export triggered - wire to actual handler"),
        )
        self.quick_export_image_btn.clicked.connect(
            lambda: print("Image export triggered - wire to actual handler"),
        )

        tab_layout.addWidget(export_card)

    def _build_settings_tab(self, tab_layout: QVBoxLayout):
        """Build Settings tab with analysis method and range controls."""
        settings_section = QLabel("ANALYSIS SETTINGS")
        settings_section.setStyleSheet(section_header_style())
        tab_layout.addWidget(settings_section)

        settings_card = QFrame()
        settings_card.setStyleSheet(card_style())
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(6)

        # Pipeline method radios
        self.auto_radio = QRadioButton("Auto")
        self.manual_radio = QRadioButton("Manual")
        self.auto_radio.setChecked(True)
        settings_layout.addWidget(self.auto_radio)
        settings_layout.addWidget(self.manual_radio)

        # Min/max inputs
        self.min_input = QLineEdit()
        self.min_input.setPlaceholderText("Min")
        self.max_input = QLineEdit()
        self.max_input.setPlaceholderText("Max")
        settings_layout.addWidget(self.min_input)
        settings_layout.addWidget(self.max_input)

        tab_layout.addWidget(settings_card)
