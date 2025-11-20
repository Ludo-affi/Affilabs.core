"""Standalone UI prototype for main window design."""

import sys
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QParallelAnimationGroup
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame, QToolButton, QScrollArea, QGraphicsDropShadowEffect,
    QSlider, QSpinBox, QSplitter
)
from PySide6.QtGui import QIcon, QColor, QFont


class CollapsibleSection(QWidget):
    """A collapsible section widget with header and content."""

    def __init__(self, title, parent=None, is_expanded=True):
        super().__init__(parent)
        self.is_expanded = is_expanded
        self.animation_duration = 200

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton(f"{'▼' if is_expanded else '▶'} {title}")
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(is_expanded)
        self.header_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 10px 12px;"
            "  text-align: left;"
            "  font-size: 14px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
            "QPushButton:checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "}"
        )
        self.header_btn.clicked.connect(self.toggle)
        main_layout.addWidget(self.header_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(8)

        main_layout.addWidget(self.content_widget)

        # Set initial state
        self.content_widget.setVisible(is_expanded)

    def toggle(self):
        """Toggle the section expanded/collapsed state."""
        self.is_expanded = not self.is_expanded

        # Update arrow
        title_text = self.header_btn.text()[2:]  # Remove arrow
        self.header_btn.setText(f"{'▼' if self.is_expanded else '▶'} {title_text}")

        # Animate content visibility
        self.content_widget.setVisible(self.is_expanded)

    def add_content_widget(self, widget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        """Add a layout to the content area."""
        self.content_layout.addLayout(layout)


class SidebarPrototype(QWidget):
    """Simplified sidebar prototype."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self._setup_ui()

    def _setup_ui(self):
        """Setup the sidebar UI."""
        if getattr(self, '_ui_setup_done', False):
            return
        self._ui_setup_done = True
        self.setStyleSheet("background: #F5F5F7;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # Tab widget with West position (vertical tabs on left)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(False)
        # Add tabs
        tab_definitions = [
            ("Device Status", "Device Status"),
            ("Graphic Control", "Graphic Control"),
            ("Static", "Static"),
            ("Flow", "Flow"),
            ("Export", "Export"),
            ("Settings", "Settings"),
        ]
        for label, tooltip in tab_definitions:
            # Create scroll area for tab content
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet(
                "QScrollArea {"
                "  background: #FFFFFF;"
                "  border: none;"
                "}"
                "QScrollBar:vertical {"
                "  background: #F5F5F7;"
                "  width: 10px;"
                "  border-radius: 5px;"
                "}"
                "QScrollBar::handle:vertical {"
                "  background: rgba(0, 0, 0, 0.2);"
                "  border-radius: 5px;"
                "  min-height: 20px;"
                "}"
                "QScrollBar::handle:vertical:hover {"
                "  background: rgba(0, 0, 0, 0.3);"
                "}"
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
                "  height: 0px;"
                "}"
            )

            tab_content = QWidget()
            tab_content.setStyleSheet("background: #FFFFFF;")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setContentsMargins(20, 20, 20, 20)
            tab_layout.setSpacing(12)

            # Title
            title = QLabel(f"{tooltip}")
            title.setStyleSheet(
                "font-size: 20px;"
                "font-weight: 600;"
                "color: #1D1D1F;"
                "background: transparent;"
                "line-height: 1.2;"
                "letter-spacing: -0.3px;"
                "font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            )
            tab_layout.addWidget(title)

            # Device Status specific content
            if label == "Device Status":
                tab_layout.addSpacing(12)

                # Section 1: Hardware Connected
                # Section header
                hw_section = QLabel("HARDWARE CONNECTED")
                hw_section.setStyleSheet(
                    "font-size: 11px;"
                    "font-weight: 700;"
                    "color: #86868B;"
                    "background: transparent;"
                    "letter-spacing: 0.5px;"
                    "margin-left: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(hw_section)

                tab_layout.addSpacing(8)

                # Card container for hardware section
                hw_card = QFrame()
                hw_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                hw_card_layout = QVBoxLayout(hw_card)
                hw_card_layout.setContentsMargins(12, 12, 12, 12)
                hw_card_layout.setSpacing(6)

                # Container for connected devices (max 3)
                self.hw_device_labels = []
                for i in range(3):
                    device_label = QLabel(f"• Device {i+1}: Not connected")
                    device_label.setStyleSheet(
                        "font-size: 13px;"
                        "color: #34C759;"
                        "background: transparent;"
                        "padding: 4px 0px;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    device_label.setVisible(False)  # Hidden by default until devices are found
                    hw_card_layout.addWidget(device_label)
                    self.hw_device_labels.append(device_label)

                # No devices message (shown when no devices connected)
                self.hw_no_devices = QLabel("No hardware detected")
                self.hw_no_devices.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "padding: 8px 0px;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                hw_card_layout.addWidget(self.hw_no_devices)

                hw_card_layout.addSpacing(4)

                # Scan button
                self.scan_btn = QPushButton("🔍 Scan for Hardware")
                self.scan_btn.setProperty("scanning", False)
                self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self.scan_btn.setFixedHeight(36)
                self.scan_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: #1D1D1F;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 8px;"
                    "  padding: 0px 16px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "  text-align: center;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #3A3A3C;"
                    "}"
                    "QPushButton:pressed {"
                    "  background: #48484A;"
                    "}"
                )
                hw_card_layout.addWidget(self.scan_btn)

                tab_layout.addWidget(hw_card)

                tab_layout.addSpacing(16)

                # Section 2: Subunit Readiness
                subunit_section = QLabel("SUBUNIT READINESS")
                subunit_section.setStyleSheet(
                    "font-size: 11px;"
                    "font-weight: 700;"
                    "color: #86868B;"
                    "background: transparent;"
                    "letter-spacing: 0.5px;"
                    "margin-left: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(subunit_section)

                tab_layout.addSpacing(8)

                # Card container for subunits
                subunit_card = QFrame()
                subunit_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                subunit_card_layout = QVBoxLayout(subunit_card)
                subunit_card_layout.setContentsMargins(12, 10, 12, 10)
                subunit_card_layout.setSpacing(8)

                # Three subunits: Sensor, Optics, Fluidics
                self.subunit_status = {}
                subunit_names = ["Sensor", "Optics", "Fluidics"]

                for i, subunit_name in enumerate(subunit_names):
                    # Container for each subunit
                    subunit_row = QHBoxLayout()
                    subunit_row.setSpacing(10)
                    subunit_row.setContentsMargins(0, 0, 0, 0)

                    # Status indicator (circle)
                    status_indicator = QLabel("●")
                    status_indicator.setFixedWidth(12)
                    status_indicator.setStyleSheet(
                        "font-size: 14px;"
                        "color: #86868B;"  # Gray for not ready
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    subunit_row.addWidget(status_indicator)

                    # Subunit name
                    name_label = QLabel(subunit_name)
                    name_label.setStyleSheet(
                        "font-size: 13px;"
                        "color: #1D1D1F;"
                        "background: transparent;"
                        "font-weight: 500;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    subunit_row.addWidget(name_label)

                    subunit_row.addStretch()

                    # Status text
                    status_label = QLabel("Not Ready")
                    status_label.setStyleSheet(
                        "font-size: 12px;"
                        "color: #86868B;"
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    subunit_row.addWidget(status_label)

                    # Store references for later updates
                    self.subunit_status[subunit_name] = {
                        'indicator': status_indicator,
                        'status_label': status_label
                    }

                    # Add to card layout
                    subunit_container = QWidget()
                    subunit_container.setLayout(subunit_row)
                    subunit_card_layout.addWidget(subunit_container)

                    # Add separator between items (not after last)
                    if i < len(subunit_names) - 1:
                        separator = QFrame()
                        separator.setFrameShape(QFrame.Shape.HLine)
                        separator.setStyleSheet(
                            "background: rgba(0, 0, 0, 0.06);"
                            "max-height: 1px;"
                            "margin: 4px 0px;"
                        )
                        subunit_card_layout.addWidget(separator)

                tab_layout.addWidget(subunit_card)

                tab_layout.addSpacing(16)

                # Section 3: Operation Modes
                mode_section = QLabel("OPERATION MODES")
                mode_section.setStyleSheet(
                    "font-size: 11px;"
                    "font-weight: 700;"
                    "color: #86868B;"
                    "background: transparent;"
                    "letter-spacing: 0.5px;"
                    "margin-left: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(mode_section)

                tab_layout.addSpacing(8)

                # Card container for operation modes
                mode_card = QFrame()
                mode_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                mode_card_layout = QVBoxLayout(mode_card)
                mode_card_layout.setContentsMargins(12, 10, 12, 10)
                mode_card_layout.setSpacing(8)

                # Operation Modes Container
                self.operation_modes = {}
                mode_names = ["Static", "Flow"]

                for i, mode_name in enumerate(mode_names):
                    # Container for each mode
                    mode_row = QHBoxLayout()
                    mode_row.setSpacing(10)
                    mode_row.setContentsMargins(0, 0, 0, 0)

                    # Status indicator (circle)
                    mode_indicator = QLabel("●")
                    mode_indicator.setFixedWidth(12)
                    mode_indicator.setStyleSheet(
                        "font-size: 14px;"
                        "color: #86868B;"  # Gray for disabled
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    mode_row.addWidget(mode_indicator)

                    # Mode name
                    mode_label = QLabel(mode_name)
                    mode_label.setStyleSheet(
                        "font-size: 13px;"
                        "color: #86868B;"  # Gray when disabled
                        "background: transparent;"
                        "font-weight: 500;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    mode_row.addWidget(mode_label)

                    mode_row.addStretch()

                    # Status text
                    status_label = QLabel("Disabled")
                    status_label.setStyleSheet(
                        "font-size: 12px;"
                        "color: #86868B;"
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    mode_row.addWidget(status_label)

                    # Store references for later updates
                    self.operation_modes[mode_name] = {
                        'indicator': mode_indicator,
                        'label': mode_label,
                        'status_label': status_label
                    }

                    mode_card_layout.addLayout(mode_row)

                tab_layout.addWidget(mode_card)
                tab_layout.addSpacing(16)

                # Section 4: Maintenance
                maint_section = QLabel("Maintenance")
                maint_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(maint_section)

                tab_layout.addSpacing(8)

                # Section divider line
                maint_divider = QFrame()
                maint_divider.setFixedHeight(1)
                maint_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(maint_divider)

                tab_layout.addSpacing(8)

                # Card container for operational stats
                stats_card = QFrame()
                stats_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )

                # Operational Statistics Container
                stats_container = QWidget()
                stats_layout = QVBoxLayout(stats_container)
                stats_layout.setContentsMargins(12, 10, 12, 10)
                stats_layout.setSpacing(10)

                # Operation Hours
                hours_row = QHBoxLayout()
                hours_row.setSpacing(8)
                hours_label = QLabel("Operation Hours:")
                hours_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                hours_row.addWidget(hours_label)

                self.hours_value = QLabel("1,247 hrs")
                self.hours_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                hours_row.addWidget(self.hours_value)
                hours_row.addStretch()
                stats_layout.addLayout(hours_row)

                # Last Operation Date
                last_op_row = QHBoxLayout()
                last_op_row.setSpacing(8)
                last_op_label = QLabel("Last Operation:")
                last_op_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                last_op_row.addWidget(last_op_label)

                self.last_op_value = QLabel("Nov 19, 2025")
                self.last_op_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                last_op_row.addWidget(self.last_op_value)
                last_op_row.addStretch()
                stats_layout.addLayout(last_op_row)

                # Upcoming Maintenance
                upcoming_label = QLabel("Upcoming Maintenance:")
                upcoming_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                stats_layout.addWidget(upcoming_label)

                # Maintenance items list
                self.maintenance_items = []
                maintenance_steps = [
                    ("Clean optics", "at 1,500 hrs"),
                    ("Replace flow cell", "at 2,000 hrs"),
                    ("Calibration check", "every 250 hrs")
                ]

                for step, timing in maintenance_steps:
                    item_row = QHBoxLayout()
                    item_row.setSpacing(6)
                    item_row.setContentsMargins(8, 2, 0, 2)

                    bullet = QLabel("•")
                    bullet.setStyleSheet(
                        "font-size: 13px;"
                        "color: #1D1D1F;"
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    item_row.addWidget(bullet)

                    step_label = QLabel(step)
                    step_label.setStyleSheet(
                        "font-size: 12px;"
                        "color: #1D1D1F;"
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    item_row.addWidget(step_label)

                    timing_label = QLabel(timing)
                    timing_label.setStyleSheet(
                        "font-size: 11px;"
                        "color: #86868B;"
                        "background: transparent;"
                        "font-style: italic;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    item_row.addWidget(timing_label)
                    item_row.addStretch()

                    stats_layout.addLayout(item_row)

                stats_card.setLayout(stats_layout)
                tab_layout.addWidget(stats_card)

                tab_layout.addSpacing(12)

                # Debug Log Download Button
                debug_btn_container = QFrame()
                debug_btn_container.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                debug_btn_layout = QVBoxLayout(debug_btn_container)
                debug_btn_layout.setContentsMargins(12, 10, 12, 10)

                self.debug_log_btn = QPushButton("📥 Download Debug Log")
                self.debug_log_btn.setFixedHeight(36)
                self.debug_log_btn.setStyleSheet(
                    "QPushButton {"
                    "    background: #1D1D1F;"
                    "    border: none;"
                    "    border-radius: 6px;"
                    "    padding: 0px 16px;"
                    "    font-size: 13px;"
                    "    color: white;"
                    "    font-weight: 600;"
                    "    font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QPushButton:hover {"
                    "    background: #3A3A3C;"
                    "}"
                    "QPushButton:pressed {"
                    "    background: #48484A;"
                    "}"
                )
                debug_btn_layout.addWidget(self.debug_log_btn)
                tab_layout.addWidget(debug_btn_container)

            # Graphic Control Tab Content
            elif label == "Graphic Control":
                # Section 1: Data Filtering
                filter_section = QLabel("Data Filtering")
                filter_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(filter_section)

                tab_layout.addSpacing(8)

                # Section divider
                filter_divider = QFrame()
                filter_divider.setFixedHeight(1)
                filter_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(filter_divider)

                tab_layout.addSpacing(8)

                # Card container for filtering options
                filter_card = QFrame()
                filter_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                filter_card_layout = QVBoxLayout(filter_card)
                filter_card_layout.setContentsMargins(12, 10, 12, 10)
                filter_card_layout.setSpacing(10)

                # Enable filtering checkbox
                from PySide6.QtWidgets import QCheckBox, QSlider
                filter_enable = QCheckBox("Enable data filtering")
                filter_enable.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                filter_card_layout.addWidget(filter_enable)

                # Filtering parameter slider
                param_row = QHBoxLayout()
                param_row.setSpacing(10)
                param_label = QLabel("Filter strength:")
                param_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                param_row.addWidget(param_label)

                filter_slider = QSlider(Qt.Horizontal)
                filter_slider.setRange(1, 10)
                filter_slider.setValue(5)
                filter_slider.setEnabled(False)  # Disabled until checkbox is checked
                filter_slider.setStyleSheet(
                    "QSlider::groove:horizontal {"
                    "  background: rgba(0, 0, 0, 0.1);"
                    "  height: 4px;"
                    "  border-radius: 2px;"
                    "}"
                    "QSlider::handle:horizontal {"
                    "  background: #1D1D1F;"
                    "  border: none;"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border-radius: 8px;"
                    "  margin: -6px 0;"
                    "}"
                    "QSlider::handle:horizontal:hover {"
                    "  background: #3A3A3C;"
                    "}"
                    "QSlider::handle:horizontal:disabled {"
                    "  background: #86868B;"
                    "}"
                )
                param_row.addWidget(filter_slider)

                param_value = QLabel("5")
                param_value.setFixedWidth(20)
                param_value.setStyleSheet(
                    "font-size: 12px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                param_row.addWidget(param_value)

                filter_card_layout.addLayout(param_row)

                # Connect signals (would need to be implemented in real code)
                # filter_enable.toggled.connect(filter_slider.setEnabled)
                # filter_slider.valueChanged.connect(lambda v: param_value.setText(str(v)))

                tab_layout.addWidget(filter_card)
                tab_layout.addSpacing(16)

                # Section 2: Reference
                ref_section = QLabel("Reference")
                ref_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(ref_section)

                tab_layout.addSpacing(8)

                ref_divider = QFrame()
                ref_divider.setFixedHeight(1)
                ref_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(ref_divider)

                tab_layout.addSpacing(8)

                # Card container for reference options
                ref_card = QFrame()
                ref_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                ref_card_layout = QVBoxLayout(ref_card)
                ref_card_layout.setContentsMargins(12, 10, 12, 10)
                ref_card_layout.setSpacing(10)

                # Description text
                ref_desc = QLabel("Select a channel to subtract from others")
                ref_desc.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                ref_card_layout.addWidget(ref_desc)

                # Reference Channel selection
                from PySide6.QtWidgets import QComboBox
                ref_channel_row = QHBoxLayout()
                ref_channel_row.setSpacing(10)
                ref_channel_label = QLabel("Reference:")
                ref_channel_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 500;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                ref_channel_row.addWidget(ref_channel_label)
                ref_channel_row.addStretch()

                ref_combo = QComboBox()
                ref_combo.addItems(["None", "Channel A", "Channel B", "Channel C", "Channel D"])
                ref_combo.setFixedWidth(120)
                ref_combo.setStyleSheet(
                    "QComboBox {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 6px;"
                    "  padding: 4px 8px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QComboBox:hover {"
                    "  border: 1px solid rgba(0, 0, 0, 0.15);"
                    "}"
                    "QComboBox::drop-down {"
                    "  border: none;"
                    "  width: 20px;"
                    "}"
                    "QComboBox QAbstractItemView {"
                    "  background-color: white;"
                    "  color: #1D1D1F;"
                    "  selection-background-color: #1D1D1F;"
                    "  selection-color: white;"
                    "  outline: none;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "}"
                )
                ref_channel_row.addWidget(ref_combo)
                ref_card_layout.addLayout(ref_channel_row)

                # Info label
                ref_info = QLabel("Selected channel shown as faded dashed line")
                ref_info.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                ref_card_layout.addWidget(ref_info)

                tab_layout.addWidget(ref_card)
                tab_layout.addSpacing(16)

                # Section 3: Graphic Display
                tab_layout.addWidget(ref_card)
                tab_layout.addSpacing(16)

                # Section 3: Graphic Display
                display_section = QLabel("Graphic Display")
                display_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(display_section)

                # Note about cycle of interest
                display_note = QLabel("Applied to cycle of interest")
                display_note.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-top: 2px;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(display_note)

                tab_layout.addSpacing(8)

                display_divider = QFrame()
                display_divider.setFixedHeight(1)
                display_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(display_divider)

                tab_layout.addSpacing(8)

                # Card container for display options
                display_card = QFrame()
                display_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                display_card_layout = QVBoxLayout(display_card)
                display_card_layout.setContentsMargins(12, 10, 12, 10)
                display_card_layout.setSpacing(10)

                # Axis selector (segmented control)
                axis_selector_row = QHBoxLayout()
                axis_selector_row.setSpacing(0)

                from PySide6.QtWidgets import QComboBox, QLineEdit, QRadioButton, QButtonGroup
                axis_button_group = QButtonGroup()
                axis_button_group.setExclusive(True)

                x_axis_btn = QPushButton("X-Axis")
                x_axis_btn.setCheckable(True)
                x_axis_btn.setChecked(True)
                x_axis_btn.setFixedHeight(28)
                x_axis_btn.setStyleSheet(
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
                axis_button_group.addButton(x_axis_btn, 0)
                axis_selector_row.addWidget(x_axis_btn)

                y_axis_btn = QPushButton("Y-Axis")
                y_axis_btn.setCheckable(True)
                y_axis_btn.setFixedHeight(28)
                y_axis_btn.setStyleSheet(
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
                axis_button_group.addButton(y_axis_btn, 1)
                axis_selector_row.addWidget(y_axis_btn)

                axis_selector_row.addSpacing(16)

                # Grid toggle next to axis selector
                grid_check = QCheckBox("Grid")
                grid_check.setChecked(True)
                grid_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                axis_selector_row.addWidget(grid_check)

                axis_selector_row.addStretch()

                display_card_layout.addLayout(axis_selector_row)

                # Unified Axis Scaling controls (will update based on selection)
                scale_radio_group = QButtonGroup()
                scale_radio_group.setExclusive(True)

                auto_radio = QRadioButton("Autoscale")
                auto_radio.setChecked(True)
                auto_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 4px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                scale_radio_group.addButton(auto_radio, 0)
                display_card_layout.addWidget(auto_radio)

                # Manual scaling container
                manual_container = QWidget()
                manual_layout = QVBoxLayout(manual_container)
                manual_layout.setContentsMargins(0, 0, 0, 0)
                manual_layout.setSpacing(6)

                manual_radio = QRadioButton("Manual")
                manual_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 4px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                scale_radio_group.addButton(manual_radio, 1)
                manual_layout.addWidget(manual_radio)

                # Manual input fields
                inputs_row = QHBoxLayout()
                inputs_row.setSpacing(8)
                inputs_row.setContentsMargins(24, 0, 0, 0)

                min_label = QLabel("Min:")
                min_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                inputs_row.addWidget(min_label)

                min_input = QLineEdit()
                min_input.setPlaceholderText("0")
                min_input.setFixedWidth(60)
                min_input.setEnabled(False)
                min_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                    "QLineEdit:disabled {"
                    "  background: rgba(0, 0, 0, 0.02);"
                    "  color: #86868B;"
                    "}"
                )
                inputs_row.addWidget(min_input)

                max_label = QLabel("Max:")
                max_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                inputs_row.addWidget(max_label)

                max_input = QLineEdit()
                max_input.setPlaceholderText("100")
                max_input.setFixedWidth(60)
                max_input.setEnabled(False)
                max_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                    "QLineEdit:disabled {"
                    "  background: rgba(0, 0, 0, 0.02);"
                    "  color: #86868B;"
                    "}"
                )
                inputs_row.addWidget(max_input)
                inputs_row.addStretch()

                manual_layout.addLayout(inputs_row)
                display_card_layout.addWidget(manual_container)

                # Separator
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "border: none;"
                    "margin: 8px 0px;"
                )
                display_card_layout.addWidget(separator)

                # Trace Style options row
                options_row = QHBoxLayout()
                options_row.setSpacing(12)

                # Channel selection
                channel_label = QLabel("Channel:")
                channel_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                options_row.addWidget(channel_label)

                channel_combo = QComboBox()
                channel_combo.addItems(["All", "A", "B", "C", "D"])
                channel_combo.setFixedWidth(70)
                channel_combo.setStyleSheet(
                    "QComboBox {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 2px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QComboBox:hover {"
                    "  border: 1px solid rgba(0, 0, 0, 0.15);"
                    "}"
                    "QComboBox::drop-down {"
                    "  border: none;"
                    "  width: 16px;"
                    "}"
                    "QComboBox QAbstractItemView {"
                    "  background-color: white;"
                    "  color: #1D1D1F;"
                    "  selection-background-color: #1D1D1F;"
                    "  selection-color: white;"
                    "  outline: none;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "}"
                )
                options_row.addWidget(channel_combo)

                # Markers
                marker_label = QLabel("Markers:")
                marker_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                options_row.addWidget(marker_label)

                marker_combo = QComboBox()
                marker_combo.addItems(["Circle", "Triangle", "Square", "Star"])
                marker_combo.setFixedWidth(90)
                marker_combo.setStyleSheet(
                    "QComboBox {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 2px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QComboBox:hover {"
                    "  border: 1px solid rgba(0, 0, 0, 0.15);"
                    "}"
                    "QComboBox::drop-down {"
                    "  border: none;"
                    "  width: 16px;"
                    "}"
                    "QComboBox QAbstractItemView {"
                    "  background-color: white;"
                    "  color: #1D1D1F;"
                    "  selection-background-color: #1D1D1F;"
                    "  selection-color: white;"
                    "  outline: none;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "}"
                )
                options_row.addWidget(marker_combo)

                options_row.addStretch()

                display_card_layout.addLayout(options_row)

                tab_layout.addWidget(display_card)
                tab_layout.addSpacing(16)

                # Section 4: Visual Accessibility (moved from Colour Palette)
                accessibility_section = QLabel("Visual Accessibility")
                accessibility_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(accessibility_section)

                tab_layout.addSpacing(8)

                accessibility_divider = QFrame()
                accessibility_divider.setFixedHeight(1)
                accessibility_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(accessibility_divider)

                tab_layout.addSpacing(8)

                # Card container for accessibility
                accessibility_card = QFrame()
                accessibility_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                accessibility_card_layout = QVBoxLayout(accessibility_card)
                accessibility_card_layout.setContentsMargins(12, 10, 12, 10)
                accessibility_card_layout.setSpacing(10)

                # Colorblind-friendly palette toggle
                colorblind_check = QCheckBox("Enable colour-blind friendly palette")
                colorblind_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                accessibility_card_layout.addWidget(colorblind_check)

                # Info text about colorblind palette
                colorblind_info = QLabel("Uses optimized colors for deuteranopia and protanopia")
                colorblind_info.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                accessibility_card_layout.addWidget(colorblind_info)

                tab_layout.addWidget(accessibility_card)

            # Settings Tab Content
            elif label == "Settings":
                # Section 1: Transmission and Raw Data (with graph toggle)
                graph_section = QLabel("Transmission and Raw Data")
                graph_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(graph_section)

                tab_layout.addSpacing(8)

                graph_divider = QFrame()
                graph_divider.setFixedHeight(1)
                graph_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(graph_divider)

                tab_layout.addSpacing(8)

                # Card container for graph display
                graph_card = QFrame()
                graph_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                graph_card_layout = QVBoxLayout(graph_card)
                graph_card_layout.setContentsMargins(12, 10, 12, 10)
                graph_card_layout.setSpacing(10)

                # Graph toggle (Transmission / Raw Data)
                graph_toggle_row = QHBoxLayout()
                graph_toggle_row.setSpacing(0)

                graph_button_group = QButtonGroup()

                transmission_btn = QPushButton("Transmission")
                transmission_btn.setCheckable(True)
                transmission_btn.setChecked(True)
                transmission_btn.setFixedHeight(28)
                transmission_btn.setStyleSheet(
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
                graph_button_group.addButton(transmission_btn, 0)
                graph_toggle_row.addWidget(transmission_btn)

                raw_data_btn = QPushButton("Raw Data")
                raw_data_btn.setCheckable(True)
                raw_data_btn.setFixedHeight(28)
                raw_data_btn.setStyleSheet(
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
                graph_button_group.addButton(raw_data_btn, 1)
                graph_toggle_row.addWidget(raw_data_btn)
                graph_toggle_row.addStretch()

                graph_card_layout.addLayout(graph_toggle_row)

                # Placeholder for graph display
                graph_placeholder = QLabel("[ Graph Display Area ]")
                graph_placeholder.setFixedHeight(120)
                graph_placeholder.setAlignment(Qt.AlignCenter)
                graph_placeholder.setStyleSheet(
                    "background: white;"
                    "border: 1px dashed rgba(0, 0, 0, 0.2);"
                    "border-radius: 6px;"
                    "color: #86868B;"
                    "font-size: 12px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                graph_card_layout.addWidget(graph_placeholder)

                tab_layout.addWidget(graph_card)

                tab_layout.addSpacing(16)

                # Section 2: Polarizer and LED Settings
                polarizer_led_section = QLabel("Polarizer and LED Settings")
                polarizer_led_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(polarizer_led_section)

                tab_layout.addSpacing(8)

                polarizer_led_divider = QFrame()
                polarizer_led_divider.setFixedHeight(1)
                polarizer_led_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(polarizer_led_divider)

                tab_layout.addSpacing(8)

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

                s_position_input = QLineEdit()
                s_position_input.setPlaceholderText("0-255")
                s_position_input.setFixedWidth(60)
                s_position_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                polarizer_row.addWidget(s_position_input)

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

                p_position_input = QLineEdit()
                p_position_input.setPlaceholderText("0-255")
                p_position_input.setFixedWidth(60)
                p_position_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                polarizer_row.addWidget(p_position_input)

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

                channel_a_input = QLineEdit()
                channel_a_input.setPlaceholderText("0-255")
                channel_a_input.setFixedWidth(60)
                channel_a_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                channel_a_row.addWidget(channel_a_input)
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

                channel_b_input = QLineEdit()
                channel_b_input.setPlaceholderText("0-255")
                channel_b_input.setFixedWidth(60)
                channel_b_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                channel_b_row.addWidget(channel_b_input)
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

                channel_c_input = QLineEdit()
                channel_c_input.setPlaceholderText("0-255")
                channel_c_input.setFixedWidth(60)
                channel_c_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                channel_c_row.addWidget(channel_c_input)
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

                channel_d_input = QLineEdit()
                channel_d_input.setPlaceholderText("0-255")
                channel_d_input.setFixedWidth(60)
                channel_d_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 4px 6px;"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                channel_d_row.addWidget(channel_d_input)
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

                # Apply Settings Button
                apply_settings_btn = QPushButton("Apply Settings")
                apply_settings_btn.setFixedHeight(32)
                apply_settings_btn.setStyleSheet(
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
                polarizer_led_card_layout.addWidget(apply_settings_btn)

                tab_layout.addWidget(polarizer_led_card)

                tab_layout.addSpacing(12)

                # Section 3: Unit Selection
                unit_section = QLabel("Unit Selection")
                unit_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(unit_section)

                tab_layout.addSpacing(8)

                unit_divider = QFrame()
                unit_divider.setFixedHeight(1)
                unit_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(unit_divider)

                tab_layout.addSpacing(8)

                # Card container for unit selection
                unit_card = QFrame()
                unit_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                unit_card_layout = QVBoxLayout(unit_card)
                unit_card_layout.setContentsMargins(12, 8, 12, 8)
                unit_card_layout.setSpacing(6)

                # Unit toggle (RU / nm)
                unit_toggle_row = QHBoxLayout()
                unit_toggle_row.setSpacing(0)

                unit_button_group = QButtonGroup()
                unit_button_group.setExclusive(True)

                ru_btn = QPushButton("RU")
                ru_btn.setCheckable(True)
                ru_btn.setChecked(True)
                ru_btn.setFixedHeight(28)
                ru_btn.setStyleSheet(
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
                unit_button_group.addButton(ru_btn, 0)
                unit_toggle_row.addWidget(ru_btn)

                nm_btn = QPushButton("nm")
                nm_btn.setCheckable(True)
                nm_btn.setFixedHeight(28)
                nm_btn.setStyleSheet(
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
                unit_button_group.addButton(nm_btn, 1)
                unit_toggle_row.addWidget(nm_btn)
                unit_toggle_row.addStretch()

                unit_card_layout.addLayout(unit_toggle_row)

                tab_layout.addWidget(unit_card)

                tab_layout.addSpacing(12)

                # Section 4: Advanced Calibrations
                calibration_section = QLabel("Advanced Calibrations")
                calibration_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(calibration_section)

                tab_layout.addSpacing(8)

                calibration_divider = QFrame()
                calibration_divider.setFixedHeight(1)
                calibration_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(calibration_divider)

                tab_layout.addSpacing(8)

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

                # Full Calibration Button
                full_calibration_btn = QPushButton("Full Calibration")
                full_calibration_btn.setFixedHeight(32)
                full_calibration_btn.setStyleSheet(
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
                calibration_card_layout.addWidget(full_calibration_btn)

                # Simple LED Calibration Button
                simple_led_calibration_btn = QPushButton("Simple LED Calibration")
                simple_led_calibration_btn.setFixedHeight(32)
                simple_led_calibration_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid #636366;"
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
                calibration_card_layout.addWidget(simple_led_calibration_btn)

                # OEM LED Calibration Button
                oem_led_calibration_btn = QPushButton("OEM LED Calibration")
                oem_led_calibration_btn.setFixedHeight(32)
                oem_led_calibration_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid #636366;"
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
                calibration_card_layout.addWidget(oem_led_calibration_btn)

                tab_layout.addWidget(calibration_card)

            # Static Tab Content with Collapsible Sections
            elif label == "Static":
                # Signal Assessment & Guidance (Always visible at top)
                signal_card = QFrame()
                signal_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "  padding: 12px;"
                    "}"
                )
                signal_layout = QVBoxLayout(signal_card)
                signal_layout.setContentsMargins(12, 12, 12, 12)
                signal_layout.setSpacing(8)

                signal_title = QLabel("Signal Assessment & Guidance")
                signal_title.setStyleSheet(
                    "font-size: 13px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                signal_layout.addWidget(signal_title)

                # Signal quality indicator
                signal_status_layout = QHBoxLayout()
                signal_status_layout.setSpacing(8)

                signal_status = QLabel("✓ Good")
                signal_status.setStyleSheet(
                    "font-size: 12px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: rgba(0, 0, 0, 0.06);"
                    "padding: 4px 12px;"
                    "border-radius: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                signal_status_layout.addWidget(signal_status)
                signal_status_layout.addStretch()
                signal_layout.addLayout(signal_status_layout)

                # Next step with countdown
                next_step_layout = QHBoxLayout()
                next_step_layout.setSpacing(8)

                next_step_label = QLabel("→ Ready for injection")
                next_step_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 500;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                next_step_layout.addWidget(next_step_label)
                next_step_layout.addStretch()

                countdown_label = QLabel("00:30")
                countdown_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #1D1D1F;"
                    "background: rgba(0, 0, 0, 0.06);"
                    "padding: 3px 8px;"
                    "border-radius: 4px;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                )
                next_step_layout.addWidget(countdown_label)

                signal_layout.addLayout(next_step_layout)

                tab_layout.addWidget(signal_card)
                tab_layout.addSpacing(8)

                # Section 1: Cycle Settings (Expanded by default)
                cycle_settings_section = CollapsibleSection("Cycle Settings", is_expanded=True)

                # Card container for cycle settings
                cycle_settings_card = QFrame()
                cycle_settings_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                cycle_settings_card_layout = QVBoxLayout(cycle_settings_card)
                cycle_settings_card_layout.setContentsMargins(10, 6, 10, 6)
                cycle_settings_card_layout.setSpacing(6)

                # Type
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

                from PySide6.QtWidgets import QComboBox
                type_combo = QComboBox()
                type_combo.addItems(["Auto-read", "Baseline", "Immobilization", "Concentration"])
                type_combo.setCurrentIndex(0)
                type_combo.setFixedWidth(140)
                type_combo.setStyleSheet(
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
                type_row.addWidget(type_combo)
                type_row.addStretch()

                cycle_settings_card_layout.addLayout(type_row)

                # Length
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

                length_combo = QComboBox()
                length_combo.addItems(["2 min", "5 min", "15 min", "30 min", "60 min"])
                length_combo.setCurrentIndex(1)
                length_combo.setFixedWidth(100)
                length_combo.setStyleSheet(
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
                length_row.addWidget(length_combo)
                length_row.addStretch()

                cycle_settings_card_layout.addLayout(length_row)

                # Note with tag-based channel system
                note_label = QLabel("Note:")
                note_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 500;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                cycle_settings_card_layout.addWidget(note_label)

                from PySide6.QtWidgets import QTextEdit
                from PySide6.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter, QTextDocument
                from PySide6.QtCore import QRegularExpression

                # Custom syntax highlighter for channel tags with concentration support
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

                        # Highlight [A], [B], [C], [D], [ALL] tags without concentration (blue)
                        tag_pattern = QRegularExpression(r"\[(A|B|C|D|ALL)\]")
                        iterator = tag_pattern.globalMatch(text)
                        while iterator.hasNext():
                            match = iterator.next()
                            # Only highlight if not already highlighted as concentration
                            start = match.capturedStart()
                            if self.format(start).foreground().color() != QColor("#34C759"):
                                self.setFormat(start, match.capturedLength(), self.tag_format)

                note_input = QTextEdit()
                note_input.setPlaceholderText("Use tags: [A] [B] [C] [D] [ALL] or with concentration [A:10] [ALL:50]  (max 250 chars)")
                note_input.setMaximumHeight(60)
                note_input.setStyleSheet(
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

                # Apply syntax highlighter to detect and highlight channel tags
                highlighter = ChannelTagHighlighter(note_input.document())

                # Character counter for note
                def update_note_counter():
                    text = note_input.toPlainText()
                    if len(text) > 250:
                        note_input.setPlainText(text[:250])
                        note_input.moveCursor(note_input.textCursor().End)
                    char_count_label.setText(f"{len(note_input.toPlainText())}/250 characters")

                note_input.textChanged.connect(update_note_counter)
                cycle_settings_card_layout.addWidget(note_input)

                # Character count and tag help
                note_info_row = QHBoxLayout()
                note_info_row.setSpacing(10)

                char_count_label = QLabel("0/250 characters")
                char_count_label.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                note_info_row.addWidget(char_count_label)
                note_info_row.addStretch()

                tag_help_label = QLabel("💡 [A] [B] [C] [D] [ALL] channels | [A:10] [ALL:50] with concentration")
                tag_help_label.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                note_info_row.addWidget(tag_help_label)

                cycle_settings_card_layout.addLayout(note_info_row)

                # Units (applies to concentrations in tags)
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

                from PySide6.QtWidgets import QComboBox
                units_combo = QComboBox()
                units_combo.addItems(["M (Molar)", "mM (Millimolar)", "µM (Micromolar)", "nM (Nanomolar)", "pM (Picomolar)", "mg/mL", "µg/mL", "ng/mL"])
                units_combo.setCurrentIndex(3)  # Default to nM
                units_combo.setFixedWidth(140)
                units_combo.setStyleSheet(
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
                units_row.addWidget(units_combo)
                units_row.addStretch()

                # Info about units applying to tags
                units_info = QLabel("Units apply to concentrations in tags (e.g., [A:10] = 10 nM)")
                units_info.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "margin-top: 2px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                cycle_settings_card_layout.addLayout(units_row)
                cycle_settings_card_layout.addWidget(units_info)

                # Separator before start button
                start_separator = QFrame()
                start_separator.setFixedHeight(1)
                start_separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "border: none;"
                    "margin: 8px 0px;"
                )
                cycle_settings_card_layout.addWidget(start_separator)

                # Action Buttons (Hybrid workflow)
                buttons_row = QHBoxLayout()
                buttons_row.setSpacing(8)

                # Start Now Button (Sequential mode)
                start_now_btn = QPushButton("▶ Start Now")
                start_now_btn.setFixedSize(120, 36)
                start_now_btn.setStyleSheet(
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
                buttons_row.addWidget(start_now_btn)

                # Add to Queue Button (Batch mode)
                add_to_queue_btn = QPushButton("+ Add to Queue")
                add_to_queue_btn.setFixedSize(140, 36)
                add_to_queue_btn.setStyleSheet(
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
                buttons_row.addWidget(add_to_queue_btn)
                buttons_row.addStretch()

                cycle_settings_card_layout.addLayout(buttons_row)

                # Help text
                help_text = QLabel("▶ Start Now: Begin this cycle immediately | + Add to Queue: Plan multiple cycles (up to 5)")
                help_text.setWordWrap(True)
                help_text.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "margin-top: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                cycle_settings_card_layout.addWidget(help_text)

                cycle_settings_section.add_content_widget(cycle_settings_card)
                tab_layout.addWidget(cycle_settings_section)

                tab_layout.addSpacing(8)

                # Section 2: Cycle History & Queue (Expanded by default)
                summary_section = CollapsibleSection("Cycle History & Queue", is_expanded=True)

                # Start Run Button (shown when queue has items)
                start_run_btn = QPushButton("▶ Start Queued Run")
                start_run_btn.setFixedHeight(36)
                start_run_btn.setStyleSheet(
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
                start_run_btn.setVisible(False)  # Hidden by default, shown when queue has items
                tab_layout.addWidget(start_run_btn)

                # Queue status label
                queue_status_label = QLabel("Queue: 0 cycles | Click 'Add to Queue' to plan batch runs")
                queue_status_label.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-bottom: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(queue_status_label)

                # Card container for summary table
                summary_card = QFrame()
                summary_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                summary_card_layout = QVBoxLayout(summary_card)
                summary_card_layout.setContentsMargins(12, 8, 12, 8)
                summary_card_layout.setSpacing(8)

                # Summary table
                from PySide6.QtWidgets import QTableWidget, QHeaderView
                summary_table = QTableWidget(5, 3)
                summary_table.setHorizontalHeaderLabels(["Type", "Note", "Start Time"])
                summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                summary_table.setMaximumHeight(200)
                summary_table.setStyleSheet(
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

                # Populate with sample data
                from PySide6.QtWidgets import QTableWidgetItem
                sample_data = [
                    ("Baseline", "Initial baseline [A][B][C][D]", "00:00:00"),
                    ("Concentration", "Sample A 10nM [A][B]", "00:02:30"),
                    ("Concentration", "Sample B 50nM [C][D]", "00:18:45"),
                    ("", "", ""),
                    ("", "", ""),
                ]

                for row, (cycle_type, note, start_time) in enumerate(sample_data):
                    summary_table.setItem(row, 0, QTableWidgetItem(cycle_type))
                    summary_table.setItem(row, 1, QTableWidgetItem(note))
                    summary_table.setItem(row, 2, QTableWidgetItem(start_time))

                summary_card_layout.addWidget(summary_table)

                # Table footer with info and button
                table_footer_row = QHBoxLayout()
                table_footer_row.setSpacing(10)

                # Info legend
                info_legend = QLabel("Showing last 5 cycles | Use tags [A] [B] [C] [D] [ALL] or [A:10] [B:50] [ALL:20] with concentrations")
                info_legend.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                table_footer_row.addWidget(info_legend)
                table_footer_row.addStretch()

                # Open Full Data Table Button (compact, right-aligned)
                open_table_btn = QPushButton("📊 View All Cycles")
                open_table_btn.setFixedHeight(28)
                open_table_btn.setStyleSheet(
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
                table_footer_row.addWidget(open_table_btn)

                summary_card_layout.addLayout(table_footer_row)

                summary_section.add_content_widget(summary_card)
                tab_layout.addWidget(summary_section)

            # Export Tab Content
            elif label == "Export":
                # Section 1: Data Selection
                data_selection_section = QLabel("Data Selection")
                data_selection_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(data_selection_section)

                tab_layout.addSpacing(8)

                data_selection_divider = QFrame()
                data_selection_divider.setFixedHeight(1)
                data_selection_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(data_selection_divider)

                tab_layout.addSpacing(8)

                # Card container for data selection
                data_selection_card = QFrame()
                data_selection_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                data_selection_card_layout = QVBoxLayout(data_selection_card)
                data_selection_card_layout.setContentsMargins(12, 10, 12, 10)
                data_selection_card_layout.setSpacing(8)

                # Data type checkboxes
                raw_data_check = QCheckBox("Raw Sensorgram Data")
                raw_data_check.setChecked(True)
                raw_data_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                data_selection_card_layout.addWidget(raw_data_check)

                processed_data_check = QCheckBox("Processed Data (filtered/smoothed)")
                processed_data_check.setChecked(True)
                processed_data_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                data_selection_card_layout.addWidget(processed_data_check)

                cycle_segments_check = QCheckBox("Cycle Segments (with metadata)")
                cycle_segments_check.setChecked(True)
                cycle_segments_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                data_selection_card_layout.addWidget(cycle_segments_check)

                summary_table_check = QCheckBox("Summary Table")
                summary_table_check.setChecked(True)
                summary_table_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                data_selection_card_layout.addWidget(summary_table_check)

                # Time range selection
                time_separator = QFrame()
                time_separator.setFixedHeight(1)
                time_separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06);"
                    "border: none;"
                    "margin: 4px 0px;"
                )
                data_selection_card_layout.addWidget(time_separator)

                time_range_label = QLabel("Time Range:")
                time_range_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                data_selection_card_layout.addWidget(time_range_label)

                time_range_combo = QComboBox()
                time_range_combo.addItems(["Full Experiment", "Current View", "Selected Cycles", "Custom Range..."])
                time_range_combo.setStyleSheet(
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
                data_selection_card_layout.addWidget(time_range_combo)

                tab_layout.addWidget(data_selection_card)

                tab_layout.addSpacing(16)

                # Section 2: Channel Selection
                channel_section = QLabel("Channel Selection")
                channel_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(channel_section)

                tab_layout.addSpacing(8)

                channel_divider = QFrame()
                channel_divider.setFixedHeight(1)
                channel_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(channel_divider)

                tab_layout.addSpacing(8)

                # Card container for channel selection
                channel_card = QFrame()
                channel_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                channel_card_layout = QVBoxLayout(channel_card)
                channel_card_layout.setContentsMargins(12, 10, 12, 10)
                channel_card_layout.setSpacing(8)

                # Channel checkboxes in horizontal layout
                channel_row = QHBoxLayout()
                channel_row.setSpacing(12)

                for ch in ["A", "B", "C", "D"]:
                    ch_check = QCheckBox(f"Ch {ch}")
                    ch_check.setChecked(True)
                    ch_check.setStyleSheet(
                        "QCheckBox {"
                        "  font-size: 13px;"
                        "  color: #1D1D1F;"
                        "  background: transparent;"
                        "  spacing: 6px;"
                        "  font-weight: 500;"
                        "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                        "}"
                        "QCheckBox::indicator {"
                        "  width: 16px;"
                        "  height: 16px;"
                        "  border: 1px solid rgba(0, 0, 0, 0.2);"
                        "  border-radius: 4px;"
                        "  background: white;"
                        "}"
                        "QCheckBox::indicator:checked {"
                        "  background: #1D1D1F;"
                        "  border: 1px solid #1D1D1F;"
                        "}"
                    )
                    channel_row.addWidget(ch_check)

                channel_row.addStretch()
                channel_card_layout.addLayout(channel_row)

                # Select All button
                select_all_btn = QPushButton("Select All")
                select_all_btn.setFixedHeight(28)
                select_all_btn.setFixedWidth(100)
                select_all_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid #636366;"
                    "  border-radius: 6px;"
                    "  padding: 4px 12px;"
                    "  font-size: 11px;"
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
                channel_card_layout.addWidget(select_all_btn)

                tab_layout.addWidget(channel_card)

                tab_layout.addSpacing(16)

                # Section 3: Export Format
                format_section = QLabel("Export Format")
                format_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(format_section)

                tab_layout.addSpacing(8)

                format_divider = QFrame()
                format_divider.setFixedHeight(1)
                format_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(format_divider)

                tab_layout.addSpacing(8)

                # Card container for format selection
                format_card = QFrame()
                format_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                format_card_layout = QVBoxLayout(format_card)
                format_card_layout.setContentsMargins(12, 10, 12, 10)
                format_card_layout.setSpacing(6)

                # Format radio buttons
                from PySide6.QtWidgets import QRadioButton, QButtonGroup
                format_group = QButtonGroup()

                excel_radio = QRadioButton("Excel (.xlsx) - Multi-tab workbook")
                excel_radio.setChecked(True)
                excel_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                format_group.addButton(excel_radio)
                format_card_layout.addWidget(excel_radio)

                csv_radio = QRadioButton("CSV (.csv) - Single or multiple files")
                csv_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                format_group.addButton(csv_radio)
                format_card_layout.addWidget(csv_radio)

                json_radio = QRadioButton("JSON (.json) - Structured data")
                json_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                format_group.addButton(json_radio)
                format_card_layout.addWidget(json_radio)

                hdf5_radio = QRadioButton("HDF5 (.h5) - Large datasets")
                hdf5_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 8px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                format_group.addButton(hdf5_radio)
                format_card_layout.addWidget(hdf5_radio)

                tab_layout.addWidget(format_card)

                tab_layout.addSpacing(16)

                # Section 4: Export Options
                options_section = QLabel("Export Options")
                options_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(options_section)

                tab_layout.addSpacing(8)

                options_divider = QFrame()
                options_divider.setFixedHeight(1)
                options_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(options_divider)

                tab_layout.addSpacing(8)

                # Card container for export options
                options_card = QFrame()
                options_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                options_card_layout = QVBoxLayout(options_card)
                options_card_layout.setContentsMargins(12, 10, 12, 10)
                options_card_layout.setSpacing(8)

                # Options checkboxes
                metadata_check = QCheckBox("Include Metadata (instrument settings, calibration)")
                metadata_check.setChecked(True)
                metadata_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                options_card_layout.addWidget(metadata_check)

                events_check = QCheckBox("Include Event Markers (injection/wash/spike)")
                events_check.setChecked(False)
                events_check.setStyleSheet(
                    "QCheckBox {"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 6px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QCheckBox::indicator {"
                    "  width: 16px;"
                    "  height: 16px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 4px;"
                    "  background: white;"
                    "}"
                    "QCheckBox::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 1px solid #1D1D1F;"
                    "}"
                )
                options_card_layout.addWidget(events_check)

                # Decimal precision
                precision_row = QHBoxLayout()
                precision_row.setSpacing(10)

                precision_label = QLabel("Decimal Precision:")
                precision_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                precision_row.addWidget(precision_label)

                precision_combo = QComboBox()
                precision_combo.addItems(["2", "3", "4", "5"])
                precision_combo.setCurrentIndex(2)  # Default to 4
                precision_combo.setFixedWidth(80)
                precision_combo.setStyleSheet(
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
                precision_row.addWidget(precision_combo)
                precision_row.addStretch()
                options_card_layout.addLayout(precision_row)

                # Timestamp format
                timestamp_row = QHBoxLayout()
                timestamp_row.setSpacing(10)

                timestamp_label = QLabel("Timestamp Format:")
                timestamp_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "  background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                timestamp_row.addWidget(timestamp_label)

                timestamp_combo = QComboBox()
                timestamp_combo.addItems(["Relative (00:00:00)", "Absolute (datetime)", "Elapsed seconds"])
                timestamp_combo.setFixedWidth(180)
                timestamp_combo.setStyleSheet(
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
                timestamp_row.addWidget(timestamp_combo)
                timestamp_row.addStretch()
                options_card_layout.addLayout(timestamp_row)

                tab_layout.addWidget(options_card)

                tab_layout.addSpacing(16)

                # Section 5: File Settings & Export
                file_section = QLabel("File Settings & Export")
                file_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(file_section)

                tab_layout.addSpacing(8)

                file_divider = QFrame()
                file_divider.setFixedHeight(1)
                file_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                    "border: none;"
                )
                tab_layout.addWidget(file_divider)

                tab_layout.addSpacing(8)

                # Card container for file settings
                file_card = QFrame()
                file_card.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border-radius: 8px;"
                    "}"
                )
                file_card_layout = QVBoxLayout(file_card)
                file_card_layout.setContentsMargins(12, 10, 12, 10)
                file_card_layout.setSpacing(10)

                # File name
                filename_label = QLabel("File Name:")
                filename_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                file_card_layout.addWidget(filename_label)

                filename_input = QLineEdit()
                filename_input.setPlaceholderText("experiment_20251120_143022")
                filename_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 6px 8px;"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 2px solid #1D1D1F;"
                    "}"
                )
                file_card_layout.addWidget(filename_input)

                # Destination folder
                dest_label = QLabel("Destination:")
                dest_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                file_card_layout.addWidget(dest_label)

                dest_row = QHBoxLayout()
                dest_row.setSpacing(8)

                dest_input = QLineEdit()
                dest_input.setPlaceholderText("C:/Users/Documents/Experiments")
                dest_input.setStyleSheet(
                    "QLineEdit {"
                    "  background: white;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 4px;"
                    "  padding: 6px 8px;"
                    "  font-size: 13px;"
                    "  color: #1D1D1F;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLineEdit:focus {"
                    "  border: 2px solid #1D1D1F;"
                    "}"
                )
                dest_row.addWidget(dest_input)

                browse_btn = QPushButton("Browse...")
                browse_btn.setFixedHeight(32)
                browse_btn.setFixedWidth(90)
                browse_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid #636366;"
                    "  border-radius: 6px;"
                    "  padding: 4px 12px;"
                    "  font-size: 12px;"
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
                dest_row.addWidget(browse_btn)
                file_card_layout.addLayout(dest_row)

                # Estimated file size
                filesize_label = QLabel("Estimated file size: ~2.4 MB")
                filesize_label.setStyleSheet(
                    "font-size: 11px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-style: italic;"
                    "margin-top: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                file_card_layout.addWidget(filesize_label)

                # Export button
                export_btn = QPushButton("📁 Export Data")
                export_btn.setFixedHeight(40)
                export_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: #1D1D1F;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 8px;"
                    "  padding: 8px 16px;"
                    "  font-size: 14px;"
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
                file_card_layout.addWidget(export_btn)

                tab_layout.addWidget(file_card)

                tab_layout.addSpacing(16)

                # Quick Export Presets section
                presets_label = QLabel("Quick Export Presets")
                presets_label.setStyleSheet(
                    "font-size: 13px;"
                    "font-weight: 600;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-top: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(presets_label)

                tab_layout.addSpacing(4)

                # Preset buttons
                preset_row = QHBoxLayout()
                preset_row.setSpacing(8)

                quick_csv_btn = QPushButton("Quick CSV")
                quick_csv_btn.setFixedHeight(32)
                quick_csv_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 6px;"
                    "  padding: 4px 12px;"
                    "  font-size: 12px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QPushButton:hover {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border: 1px solid #636366;"
                    "}"
                    "QPushButton:pressed {"
                    "  background: rgba(0, 0, 0, 0.06);"
                    "}"
                )
                preset_row.addWidget(quick_csv_btn)

                analysis_btn = QPushButton("Analysis Ready")
                analysis_btn.setFixedHeight(32)
                analysis_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 6px;"
                    "  padding: 4px 12px;"
                    "  font-size: 12px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QPushButton:hover {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border: 1px solid #636366;"
                    "}"
                    "QPushButton:pressed {"
                    "  background: rgba(0, 0, 0, 0.06);"
                    "}"
                )
                preset_row.addWidget(analysis_btn)

                publication_btn = QPushButton("Publication")
                publication_btn.setFixedHeight(32)
                publication_btn.setStyleSheet(
                    "QPushButton {"
                    "  background: white;"
                    "  color: #636366;"
                    "  border: 1px solid rgba(0, 0, 0, 0.1);"
                    "  border-radius: 6px;"
                    "  padding: 4px 12px;"
                    "  font-size: 12px;"
                    "  font-weight: 500;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QPushButton:hover {"
                    "  background: rgba(0, 0, 0, 0.03);"
                    "  border: 1px solid #636366;"
                    "}"
                    "QPushButton:pressed {"
                    "  background: rgba(0, 0, 0, 0.06);"
                    "}"
                )
                preset_row.addWidget(publication_btn)
                preset_row.addStretch()

                tab_layout.addLayout(preset_row)

            # Only add placeholder content for remaining tabs
            elif label not in ["Device Status", "Graphic Control", "Settings", "Static", "Export"]:
                # Placeholder content for other tabs
                placeholder = QLabel("(Placeholder content)")
                placeholder.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-top: 20px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(placeholder)

            tab_layout.addStretch()
            scroll_area.setWidget(tab_content)
            self.tab_widget.addTab(scroll_area, label)
            self.tab_widget.setTabToolTip(self.tab_widget.count() - 1, tooltip)
        # Apply sidebar tab style (vertical, upright text)
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane {"
            "  border: none;"
            "  border-radius: 12px;"
            "  background: #FFFFFF;"
            "  margin-left: 8px;"
            "}"
            "QTabWidget::tab-bar {"
            "  left: 8px;"
            "}"
            "QTabBar::tab {"
            "  background: transparent;"
            "  color: #86868B;"
            "  border: none;"
            "  padding: 8px 20px;"
            "  margin: 2px 0;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  min-height: 32px;"
            "  border-radius: 6px;"
            "}"
            "QTabBar::tab:selected {"
            "  background: #FFFFFF;"
            "  color: #1D1D1F;"
            "  font-weight: 600;"
            "}"
            "QTabBar::tab:hover:!selected {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "}"
        )
        main_layout.addWidget(self.tab_widget, 1)
        main_layout.setSpacing(0)

class MainWindowPrototype(QMainWindow):
    """Prototype of the main window UI."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ezControl UI Prototype")
        self.setGeometry(100, 100, 1400, 900)
        self.nav_buttons = []
        self.is_recording = False
        self.recording_indicator = None
        self.record_button = None
        self._setup_ui()
        self._connect_signals()
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable sidebar
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet(
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
        )

        self.sidebar = SidebarPrototype()
        self.sidebar.setMinimumWidth(55)  # Allow window to resize very small
        self.sidebar.setMaximumWidth(800)  # Maximum width to keep it reasonable
        self.splitter.addWidget(self.sidebar)
        self.splitter.setCollapsible(0, False)  # Prevent sidebar from collapsing

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        nav_bar = self._create_navigation_bar()
        right_layout.addWidget(nav_bar)

        # Stacked widget to hold different content pages
        from PySide6.QtWidgets import QStackedWidget
        self.content_stack = QStackedWidget()

        # Create content for each tab
        self.content_stack.addWidget(self._create_sensorgram_content())  # Index 0
        self.content_stack.addWidget(self._create_blank_content("Edits"))  # Index 1
        self.content_stack.addWidget(self._create_blank_content("Analyze"))  # Index 2
        self.content_stack.addWidget(self._create_blank_content("Report"))  # Index 3

        right_layout.addWidget(self.content_stack, 1)
        self.splitter.addWidget(right_widget)

        # Set initial sizes: 450px for sidebar, rest for main content
        self.splitter.setSizes([450, 950])

        main_layout.addWidget(self.splitter)

    def _create_navigation_bar(self):
        """Create the pill-shaped navigation bar."""
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: #FFFFFF;")
        nav_widget.setFixedHeight(60)

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        nav_layout.setSpacing(12)

        # Navigation buttons
        nav_button_configs = [
            ("Sensorgram", 0),
            ("Edits", 1),
            ("Analyze", 2),
            ("Report", 3),
        ]

        for i, (label, page_index) in enumerate(nav_button_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(120)
            btn.setCheckable(True)
            btn.setChecked(i == 0)  # First button selected by default

            # Store button reference
            self.nav_buttons.append(btn)

            # Update style based on checked state
            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(46, 48, 227, 0.1);"
                "  color: rgb(46, 48, 227);"
                "  border: none;"
                "  border-radius: 20px;"
                "  padding: 8px 24px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(46, 48, 227, 0.2);"
                "}"
                "QPushButton:checked {"
                "  background: rgba(46, 48, 227, 1.0);"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )

            # Connect to switch page
            btn.clicked.connect(lambda checked, idx=page_index: self._switch_page(idx))

            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Recording timer (hidden by default, shows when recording)
        timer_label = QLabel("00:00:00")
        timer_label.setStyleSheet(
            "QLabel {"
            "  color: #FF3B30;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  background: rgba(255, 59, 48, 0.1);"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
        )
        timer_label.setVisible(False)  # Hidden until recording starts
        nav_layout.addWidget(timer_label)

        # Add 16px separation before control buttons
        nav_layout.addSpacing(16)

        # Recording status indicator (next to record button)
        self.recording_indicator = QFrame()
        self.recording_indicator.setFixedSize(200, 32)
        indicator_layout = QHBoxLayout(self.recording_indicator)
        indicator_layout.setContentsMargins(10, 6, 10, 6)
        indicator_layout.setSpacing(8)

        self.rec_status_dot = QLabel("●")
        self.rec_status_dot.setStyleSheet(
            "QLabel {"
            "  color: #86868B;"
            "  font-size: 16px;"
            "  background: transparent;"
            "}"
        )
        indicator_layout.addWidget(self.rec_status_dot)

        self.rec_status_text = QLabel("Viewing (not saved)")
        self.rec_status_text.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "}"
        )
        indicator_layout.addWidget(self.rec_status_text)
        indicator_layout.addStretch()

        self.recording_indicator.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border-radius: 6px;"
            "}"
        )
        nav_layout.addWidget(self.recording_indicator)

        nav_layout.addSpacing(8)

        # Record button
        self.record_btn = QPushButton("●")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(40, 40)
        self.record_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 16px;"
            "  font-weight: 400;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton:checked {"
            "  background: #FF3B30;"
            "  color: white;"
            "}"
            "QPushButton:hover:checked {"
            "  background: #E6342A;"
            "}"
        )
        self.record_btn.setToolTip("Start/Stop Recording (Ctrl+R)")
        self.record_btn.clicked.connect(self._toggle_recording)
        nav_layout.addWidget(self.record_btn)

        # Power button (indicates power AND connection status)
        self.power_btn = QPushButton("⏻")
        self.power_btn.setCheckable(True)
        self.power_btn.setFixedSize(40, 40)
        self.power_btn.setProperty("powerState", "disconnected")  # Track state: disconnected, searching, connected
        self._update_power_button_style()
        self.power_btn.setToolTip("Power On Device (Ctrl+P)\nGray = Disconnected | Yellow = Searching | Green = Connected")
        self.power_btn.clicked.connect(self._handle_power_toggle)
        nav_layout.addWidget(self.power_btn)

        return nav_widget

    def _create_sensorgram_content(self):
        """Create the Sensorgram tab content with dual-graph layout (master-detail pattern)."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(8)

        # Graph header with controls
        header = self._create_graph_header()
        content_layout.addWidget(header)

        # Create QSplitter for resizable graph panels (30/70 split)
        from PySide6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # Top graph (Navigation/Overview) - 30%
        top_graph = self._create_graph_container(
            "Full Experiment Timeline",
            height=200,
            show_delta_spr=False
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        bottom_graph = self._create_graph_container(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True
        )

        splitter.addWidget(top_graph)
        splitter.addWidget(bottom_graph)

        # Set initial sizes (30% / 70%)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Style the splitter handle
        splitter.setStyleSheet(
            "QSplitter {"
            "  background-color: transparent;"
            "  spacing: 8px;"
            "}"
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  border: none;"
            "  border-radius: 4px;"
            "  margin: 0px 16px;"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: #1D1D1F;"
            "}"
        )

        content_layout.addWidget(splitter, 1)
        return content_widget

    def _create_graph_header(self):
        """Create header with channel toggle controls."""
        header = QWidget()
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Channel selection label
        channels_label = QLabel("Channels:")
        channels_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "}"
        )
        header_layout.addWidget(channels_label)

        # Channel toggles - consistent colors (Black, Red, Blue, Green)
        for ch, color in [("A", "#1D1D1F"), ("B", "#FF3B30"), ("C", "#1D1D1F"), ("D", "#34C759")]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(56, 32)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            header_layout.addWidget(ch_btn)

        header_layout.addStretch()

        return header

    def _create_graph_container(self, title, height, show_delta_spr=False):
        """Create a graph container with title and controls."""
        container = QFrame()
        container.setMinimumHeight(height)
        container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title row with controls
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        title_row.addWidget(title_label)

        title_row.addStretch()

        # Delta SPR signal display (only for Cycle of Interest graph)
        if show_delta_spr:
            delta_display = QLabel("Δ SPR: Ch A: 0.0 nm  |  Ch B: 0.0 nm  |  Ch C: 0.0 nm  |  Ch D: 0.0 nm")
            delta_display.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 12px;"
                "  font-size: 11px;"
                "  color: #1D1D1F;"
                "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                "  font-weight: 500;"
                "}"
            )
            title_row.addWidget(delta_display)

        # Zoom/Reset controls
        control_buttons = [
            ("↻", "Reset View (Double-click)"),
            ("+", "Zoom In (Scroll or drag box)")
        ]
        for icon, tooltip in control_buttons:
            control_btn = QPushButton(icon)
            control_btn.setFixedSize(32, 24)
            control_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 14px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.14);"
                "}"
            )
            control_btn.setToolTip(tooltip)
            title_row.addWidget(control_btn)

        layout.addLayout(title_row)

        # Graph placeholder with axis labels
        graph_area = QFrame()
        graph_area.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        graph_layout = QVBoxLayout(graph_area)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        graph_layout.setSpacing(0)

        # Graph canvas area with axes
        canvas_container = QWidget()
        canvas_layout = QHBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(4)

        # Y-axis label (vertical)
        y_axis_label = QLabel("Δ Wavelength Shift (nm)")
        y_axis_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        y_axis_label.setMaximumWidth(20)
        y_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_layout.addWidget(y_axis_label)

        # Main graph area
        graph_placeholder = QLabel(
            "[PyQtGraph Canvas]\n\n"
            "Grid: rgba(0,0,0,0.06)\n"
            "Data lines: 2px width\n"
            "Ch A (Black), Ch B (Red)\n"
            "Ch C (Blue), Ch D (Green)"
        )
        graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #C7C7CC;"
            "  line-height: 1.5;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        canvas_layout.addWidget(graph_placeholder, 1)

        graph_layout.addWidget(canvas_container, 1)

        # X-axis label (horizontal)
        x_axis_container = QWidget()
        x_axis_layout = QHBoxLayout(x_axis_container)
        x_axis_layout.setContentsMargins(24, 4, 0, 0)
        x_axis_layout.setSpacing(0)

        x_axis_label = QLabel("Time (seconds)" if not show_delta_spr else "Time (seconds) - Cycle View")
        x_axis_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        x_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x_axis_layout.addWidget(x_axis_label)

        graph_layout.addWidget(x_axis_container)

        layout.addWidget(graph_area, 1)

        return container

    def _create_blank_content(self, tab_name):
        """Create a blank page for tabs that don't have content yet."""
        # Special handling for different tabs
        if tab_name == "Edits":
            return self._create_edits_content()
        elif tab_name == "Analyze":
            return self._create_analyze_content()
        elif tab_name == "Report":
            return self._create_report_content()

        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Empty state message
        empty_icon = QLabel("📑")
        empty_icon.setStyleSheet(
            "QLabel {"
            "  font-size: 64px;"
            "  background: transparent;"
            "}"
        )
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_icon)

        empty_title = QLabel(f"{tab_name} Page")
        empty_title.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  margin-top: 16px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_title)

        empty_desc = QLabel(f"Content for the {tab_name} tab will appear here.")
        empty_desc.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  margin-top: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(empty_desc)

        return content_widget

    def _create_edits_content(self):
        """Create the Edits tab content with cycle data table and graph editing tools."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Cycle Data Table + Tools
        left_panel = self._create_edits_left_panel()
        content_layout.addWidget(left_panel, 2)

        # Right side: Primary Graph + Thumbnail Selector
        right_panel = self._create_edits_right_panel()
        content_layout.addWidget(right_panel, 3)

        return content_widget

    def _create_edits_left_panel(self):
        """Create left panel with cycle data table and editing tools."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Cycle Data Table
        table_container = QFrame()
        table_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        table_container.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.setSpacing(12)

        # Table header
        table_header = QHBoxLayout()
        table_title = QLabel("Cycle Data")
        table_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        table_header.addWidget(table_title)
        table_header.addStretch()

        # Search/Filter button
        filter_btn = QPushButton("🔍 Filter")
        filter_btn.setFixedHeight(28)
        filter_btn.setMinimumWidth(80)
        filter_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        table_header.addWidget(filter_btn)

        table_layout.addLayout(table_header)

        # Table placeholder
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        table = QTableWidget(10, 4)
        table.setHorizontalHeaderLabels(["Cycle", "Time", "Status", "Notes"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet(
            "QTableWidget {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  color: #1D1D1F;"
            "}"
            "QTableWidget::item:selected {"
            "  background: rgba(0, 0, 0, 0.08);"
            "  color: #1D1D1F;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #86868B;"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}"
        )

        # Populate with sample data
        for row in range(10):
            from PySide6.QtWidgets import QTableWidgetItem
            table.setItem(row, 0, QTableWidgetItem(f"Cycle {row + 1}"))
            table.setItem(row, 1, QTableWidgetItem(f"{row * 30}s"))
            table.setItem(row, 2, QTableWidgetItem("Active" if row % 3 != 0 else "Flagged"))
            table.setItem(row, 3, QTableWidgetItem(""))

        table_layout.addWidget(table, 1)

        panel_layout.addWidget(table_container, 3)

        # Editing Tools Box
        tools_container = QFrame()
        tools_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        tools_container.setGraphicsEffect(shadow)

        tools_layout = QVBoxLayout(tools_container)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.setSpacing(12)

        # Tools header
        tools_title = QLabel("Editing Tools")
        tools_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        tools_layout.addWidget(tools_title)

        # Tool buttons grid
        tools_grid = QHBoxLayout()
        tools_grid.setSpacing(8)

        tool_buttons = [
            ("Cut Spikes", "✂️"),
            ("Align", "⇄"),
            ("Redefine Segment", "⬚"),
            ("Smooth", "〰"),
        ]

        for tool_name, icon in tool_buttons:
            tool_btn = QPushButton(f"{icon} {tool_name}")
            tool_btn.setFixedHeight(36)
            tool_btn.setMinimumWidth(100)
            tool_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}"
            )
            tools_grid.addWidget(tool_btn)

        tools_layout.addLayout(tools_grid)

        # Action buttons
        action_buttons = QHBoxLayout()
        action_buttons.setSpacing(8)

        apply_btn = QPushButton("Apply Changes")
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 0px 16px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}"
        )
        action_buttons.addWidget(apply_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setFixedHeight(36)
        reset_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  padding: 0px 16px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
        )
        action_buttons.addWidget(reset_btn)

        tools_layout.addLayout(action_buttons)

        panel_layout.addWidget(tools_container, 1)

        return panel

    def _create_edits_right_panel(self):
        """Create right panel with primary graph and thumbnail selectors."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Primary Graph Container
        primary_graph = QFrame()
        primary_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        primary_graph.setGraphicsEffect(shadow)

        primary_layout = QVBoxLayout(primary_graph)
        primary_layout.setContentsMargins(16, 16, 16, 16)
        primary_layout.setSpacing(12)

        # Graph header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Primary Cycle View")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # Channel toggles (compact)
        for ch, color in [("A", "#1D1D1F"), ("B", "#FF3B30"), ("C", "#1D1D1F"), ("D", "#34C759")]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "}"
            )
            graph_header.addWidget(ch_btn)

        primary_layout.addLayout(graph_header)

        # Graph canvas placeholder
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        graph_canvas_layout = QVBoxLayout(graph_canvas)
        graph_placeholder = QLabel(
            "[Primary Graph Canvas]\n\n"
            "Selected cycle data displayed here\n"
            "Interactive editing enabled"
        )
        graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_canvas_layout.addWidget(graph_placeholder)

        primary_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(primary_graph, 4)

        # Thumbnail Graph Selector
        thumbnails_container = QFrame()
        thumbnails_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        thumbnails_container.setGraphicsEffect(shadow)

        thumbnails_layout = QVBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(12, 12, 12, 12)
        thumbnails_layout.setSpacing(8)

        # Thumbnails label
        thumb_label = QLabel("Quick View")
        thumb_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        thumbnails_layout.addWidget(thumb_label)

        # Three thumbnail placeholders
        thumb_grid = QHBoxLayout()
        thumb_grid.setSpacing(8)

        for i in range(3):
            thumb = QPushButton(f"Cycle {i + 2}")
            thumb.setFixedHeight(80)
            thumb.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: #86868B;"
                "  border: 1px solid rgba(0, 0, 0, 0.08);"
                "  border-radius: 8px;"
                "  font-size: 11px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  border-color: #1D1D1F;"
                "  color: #1D1D1F;"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 122, 255, 0.2);"
                "}"
            )
            thumb_grid.addWidget(thumb)

        thumbnails_layout.addLayout(thumb_grid)

        panel_layout.addWidget(thumbnails_container, 1)

        return panel

    def _create_analyze_content(self):
        """Create the Analyze tab content with processed data graph, statistics, and kinetic analysis."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Graphs (Processed Data + Statistics)
        left_panel = self._create_analyze_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Model Selection + Data Table + Export
        right_panel = self._create_analyze_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_analyze_left_panel(self):
        """Create left panel with processed data and statistics graphs."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Main Processed Data Graph
        main_graph = QFrame()
        main_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        main_graph.setGraphicsEffect(shadow)

        main_graph_layout = QVBoxLayout(main_graph)
        main_graph_layout.setContentsMargins(16, 16, 16, 16)
        main_graph_layout.setSpacing(12)

        # Header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Processed Data")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # View options
        view_btns = ["Fitted", "Residuals", "Overlay"]
        for i, btn_text in enumerate(view_btns):
            view_btn = QPushButton(btn_text)
            view_btn.setCheckable(True)
            view_btn.setChecked(i == 0)
            view_btn.setFixedHeight(28)
            view_btn.setMinimumWidth(72)
            view_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            graph_header.addWidget(view_btn)

        main_graph_layout.addLayout(graph_header)

        # Graph canvas
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        canvas_layout = QVBoxLayout(graph_canvas)
        canvas_placeholder = QLabel(
            "[Processed Data Graph]\n\n"
            "Fitted curves with model overlay\n"
            "Interactive zoom and pan enabled"
        )
        canvas_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        canvas_layout.addWidget(canvas_placeholder)
        main_graph_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(main_graph, 3)

        # Statistics / Goodness of Fit Graph
        stats_graph = QFrame()
        stats_graph.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        stats_graph.setGraphicsEffect(shadow)

        stats_layout = QVBoxLayout(stats_graph)
        stats_layout.setContentsMargins(16, 16, 16, 16)
        stats_layout.setSpacing(12)

        # Header
        stats_header = QHBoxLayout()
        stats_title = QLabel("Goodness of Fit Analysis")
        stats_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        stats_header.addWidget(stats_title)
        stats_header.addStretch()

        # R² display
        r_squared = QLabel("R² = 0.9987")
        r_squared.setStyleSheet(
            "QLabel {"
            "  background: rgba(52, 199, 89, 0.1);"
            "  color: #34C759;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
            "}"
        )
        stats_header.addWidget(r_squared)

        stats_layout.addLayout(stats_header)

        # Stats canvas
        stats_canvas = QFrame()
        stats_canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "}"
        )
        stats_canvas_layout = QVBoxLayout(stats_canvas)
        stats_placeholder = QLabel(
            "[Residuals / Chi-Square Plot]\n\n"
            "Statistical analysis visualization\n"
            "Chi² = 1.23e-4, RMSE = 0.012"
        )
        stats_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        stats_canvas_layout.addWidget(stats_placeholder)
        stats_layout.addWidget(stats_canvas, 1)

        panel_layout.addWidget(stats_graph, 2)

        return panel

    def _create_analyze_right_panel(self):
        """Create right panel with model selection, data table, and export options."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Mathematical Model Selection
        model_container = QFrame()
        model_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        model_container.setGraphicsEffect(shadow)

        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(16, 16, 16, 16)
        model_layout.setSpacing(12)

        # Header
        model_title = QLabel("Mathematical Model")
        model_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(model_title)

        # Model selection dropdown
        from PySide6.QtWidgets import QComboBox
        model_dropdown = QComboBox()
        model_dropdown.addItems([
            "Langmuir 1:1",
            "Two-State Binding",
            "Bivalent Analyte",
            "Mass Transport Limited",
            "Heterogeneous Ligand",
            "Custom Model"
        ])
        model_dropdown.setFixedHeight(36)
        model_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 12px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QComboBox:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border: none;"
            "}"
        )
        model_layout.addWidget(model_dropdown)

        # Fit button
        fit_btn = QPushButton("Run Fitting Analysis")
        fit_btn.setFixedHeight(36)
        fit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
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
        model_layout.addWidget(fit_btn)

        # Model parameters info
        params_label = QLabel("Model Parameters")
        params_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  margin-top: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(params_label)

        params_info = QLabel(
            "ka: Association rate constant\n"
            "kd: Dissociation rate constant\n"
            "KD: Equilibrium constant\n"
            "Rmax: Maximum response"
        )
        params_info.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  line-height: 1.6;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        model_layout.addWidget(params_info)

        panel_layout.addWidget(model_container)

        # Kinetic Data Table
        data_container = QFrame()
        data_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        data_container.setGraphicsEffect(shadow)

        data_layout = QVBoxLayout(data_container)
        data_layout.setContentsMargins(16, 16, 16, 16)
        data_layout.setSpacing(12)

        # Header
        data_header = QHBoxLayout()
        data_title = QLabel("Kinetic Results")
        data_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        data_header.addWidget(data_title)
        data_header.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedHeight(28)
        copy_btn.setMinimumWidth(72)
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        data_header.addWidget(copy_btn)

        data_layout.addLayout(data_header)

        # Data table
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        data_table = QTableWidget(4, 2)
        data_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        data_table.setStyleSheet(
            "QTableWidget {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  color: #1D1D1F;"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: #86868B;"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}"
        )

        # Sample data
        from PySide6.QtWidgets import QTableWidgetItem
        results = [
            ("ka (M⁻¹s⁻¹)", "1.23e5 ± 0.04e5"),
            ("kd (s⁻¹)", "3.45e-4 ± 0.12e-4"),
            ("KD (M)", "2.80e-9 ± 0.15e-9"),
            ("Δ SPR (nm)", "0.45 ± 0.02")
        ]

        for row, (param, value) in enumerate(results):
            data_table.setItem(row, 0, QTableWidgetItem(param))
            data_table.setItem(row, 1, QTableWidgetItem(value))

        data_layout.addWidget(data_table, 1)

        panel_layout.addWidget(data_container, 1)

        # Export/Save Section
        export_container = QFrame()
        export_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        export_container.setGraphicsEffect(shadow)

        export_layout = QVBoxLayout(export_container)
        export_layout.setContentsMargins(16, 16, 16, 16)
        export_layout.setSpacing(12)

        export_title = QLabel("Export Data")
        export_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        export_layout.addWidget(export_title)

        # Export buttons
        export_btns = QHBoxLayout()
        export_btns.setSpacing(8)

        csv_btn = QPushButton("Save CSV")
        csv_btn.setFixedHeight(36)
        csv_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
        )
        export_btns.addWidget(csv_btn)

        json_btn = QPushButton("Save JSON")
        json_btn.setFixedHeight(36)
        json_btn.setStyleSheet(csv_btn.styleSheet())
        export_btns.addWidget(json_btn)

        export_layout.addLayout(export_btns)

        panel_layout.addWidget(export_container)

        panel_layout.addStretch()

        return panel

    def _create_report_content(self):
        """Create the Report tab content for generating PDF reports with graphs, tables, and notes."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Left side: Report Canvas/Preview
        left_panel = self._create_report_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Tools and Content Library
        right_panel = self._create_report_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_report_left_panel(self):
        """Create left panel with report preview canvas."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Report header with export
        header = QHBoxLayout()

        report_title = QLabel("Report Preview")
        report_title.setStyleSheet(
            "QLabel {"
            "  font-size: 17px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        header.addWidget(report_title)
        header.addStretch()

        # Generate PDF button
        pdf_btn = QPushButton("📄 Generate PDF")
        pdf_btn.setFixedHeight(40)
        pdf_btn.setMinimumWidth(140)
        pdf_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 0px 20px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #E6342A;"
            "}"
            "QPushButton:pressed {"
            "  background: #CC2E25;"
            "}"
        )
        header.addWidget(pdf_btn)

        panel_layout.addLayout(header)

        # Report canvas/preview area
        canvas = QFrame()
        canvas.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        canvas.setGraphicsEffect(shadow)

        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(24, 24, 24, 24)
        canvas_layout.setSpacing(16)

        # Report content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea {"
            "  border: none;"
            "  background: transparent;"
            "}"
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(20)

        # Sample report elements
        # Title
        title_edit = QLabel("Kinetic Analysis Report")
        title_edit.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 700;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(title_edit)

        # Date/Info
        info_label = QLabel("Date: November 20, 2025\nExperiment ID: EXP-2025-001")
        info_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  padding: 4px 8px;"
            "  line-height: 1.6;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(info_label)

        # Placeholder for graph
        graph_placeholder = QFrame()
        graph_placeholder.setFixedHeight(250)
        graph_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 122, 255, 0.05);"
            "  border: 2px dashed rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "}"
        )
        graph_label = QLabel("[Graph Element]\n\nClick to insert graph")
        graph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  border: none;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        graph_layout = QVBoxLayout(graph_placeholder)
        graph_layout.addWidget(graph_label)
        scroll_layout.addWidget(graph_placeholder)

        # Notes section
        notes_label = QLabel("Notes:")
        notes_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(notes_label)

        from PySide6.QtWidgets import QTextEdit
        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add experiment notes, observations, or conclusions...")
        notes_edit.setFixedHeight(120)
        notes_edit.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  padding: 12px;"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        scroll_layout.addWidget(notes_edit)

        # Table placeholder
        table_placeholder = QFrame()
        table_placeholder.setFixedHeight(180)
        table_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(52, 199, 89, 0.05);"
            "  border: 2px dashed rgba(52, 199, 89, 0.3);"
            "  border-radius: 8px;"
            "}"
        )
        table_label = QLabel("[Table Element]\n\nClick to insert data table")
        table_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #34C759;"
            "  background: transparent;"
            "  border: none;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        table_layout = QVBoxLayout(table_placeholder)
        table_layout.addWidget(table_label)
        scroll_layout.addWidget(table_placeholder)

        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        canvas_layout.addWidget(scroll_area, 1)

        panel_layout.addWidget(canvas, 1)

        return panel

    def _create_report_right_panel(self):
        """Create right panel with report tools and content library."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Insert Elements Section
        elements_container = QFrame()
        elements_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        elements_container.setGraphicsEffect(shadow)

        elements_layout = QVBoxLayout(elements_container)
        elements_layout.setContentsMargins(16, 16, 16, 16)
        elements_layout.setSpacing(12)

        elements_title = QLabel("Insert Elements")
        elements_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        elements_layout.addWidget(elements_title)

        # Element buttons
        element_btns = [
            ("📊 Graph", "Insert saved graph"),
            ("📈 Bar Chart", "Create bar chart"),
            ("📋 Table", "Insert data table"),
            ("📝 Text Box", "Add text section"),
            ("🖼️ Image", "Insert image"),
        ]

        for icon_text, tooltip in element_btns:
            elem_btn = QPushButton(icon_text)
            elem_btn.setFixedHeight(36)
            elem_btn.setToolTip(tooltip)
            elem_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}"
            )
            elements_layout.addWidget(elem_btn)

        panel_layout.addWidget(elements_container)

        # Chart Builder Tool
        chart_container = QFrame()
        chart_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        chart_container.setGraphicsEffect(shadow)

        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_layout.setSpacing(12)

        chart_title = QLabel("Chart Builder")
        chart_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(chart_title)

        # Chart type selector
        chart_types = QHBoxLayout()
        chart_types.setSpacing(6)

        for chart_type in ["Bar", "Line", "Scatter"]:
            type_btn = QPushButton(chart_type)
            type_btn.setCheckable(True)
            type_btn.setChecked(chart_type == "Bar")
            type_btn.setFixedHeight(32)
            type_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )
            chart_types.addWidget(type_btn)

        chart_layout.addLayout(chart_types)

        # Data source
        source_label = QLabel("Data Source:")
        source_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(source_label)

        from PySide6.QtWidgets import QComboBox
        source_dropdown = QComboBox()
        source_dropdown.addItems([
            "Kinetic Results",
            "Cycle Statistics",
            "Custom Data"
        ])
        source_dropdown.setFixedHeight(32)
        source_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        chart_layout.addWidget(source_dropdown)

        # Create chart button
        create_chart_btn = QPushButton("Create Chart")
        create_chart_btn.setFixedHeight(36)
        create_chart_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
        )
        chart_layout.addWidget(create_chart_btn)

        panel_layout.addWidget(chart_container)

        # Saved Content Library
        library_container = QFrame()
        library_container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        library_container.setGraphicsEffect(shadow)

        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(16, 16, 16, 16)
        library_layout.setSpacing(12)

        library_title = QLabel("Content Library")
        library_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        library_layout.addWidget(library_title)

        # Saved items list
        saved_items = [
            "📊 Sensorgram_ChA",
            "📈 Kinetic_Fit_Plot",
            "📋 Results_Table_1",
        ]

        for item in saved_items:
            item_btn = QPushButton(item)
            item_btn.setFixedHeight(32)
            item_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 12px;"
                "  font-weight: 400;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}"
            )
            library_layout.addWidget(item_btn)

        panel_layout.addWidget(library_container, 1)

        panel_layout.addStretch()

        return panel

    def _switch_page(self, page_index):
        """Switch to the selected page and update button states."""
        self.content_stack.setCurrentIndex(page_index)

        # Update button checked states (radio button behavior)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == page_index)

    def _update_power_button_style(self):
        """Update power button appearance based on current state."""
        state = self.power_btn.property("powerState")

        if state == "disconnected":
            # Gray - No device connected
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            self.power_btn.setToolTip("Power On Device (Ctrl+P)\nGray = Disconnected")
        elif state == "searching":
            # Yellow - Searching for device
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #E6B800;"
                "}"
            )
            self.power_btn.setToolTip("Searching for Device...\nYellow = Device Not Found\nClick to cancel")
        elif state == "connected":
            # Green - Device powered and connected
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #2EAF4F;"
                "}"
            )
            self.power_btn.setToolTip("Power Off Device (Ctrl+P)\nGreen = Device Connected\nClick to power off")

    def _handle_power_toggle(self, checked):
        """Handle power button toggle with device search and warning dialog on power off."""
        current_state = self.power_btn.property("powerState")

        if current_state == "disconnected" and checked:
            # Power ON clicked: Start searching for device
            print("[PROTOTYPE] Power ON: Searching for device...")
            self.power_btn.setProperty("powerState", "searching")
            self._update_power_button_style()

            # Simulate device search with timer (in real implementation, this would be async device detection)
            from PySide6.QtCore import QTimer
            self.device_search_timer = QTimer()
            self.device_search_timer.setSingleShot(True)
            self.device_search_timer.timeout.connect(self._simulate_device_search)
            self.device_search_timer.start(2000)  # Simulate 2 second search

        elif current_state == "searching" and not checked:
            # Cancel search if user clicks while searching
            print("[PROTOTYPE] Device search cancelled by user")
            if hasattr(self, 'device_search_timer'):
                self.device_search_timer.stop()
            self.power_btn.setProperty("powerState", "disconnected")
            self._update_power_button_style()
            self.power_btn.setChecked(False)

        elif current_state == "connected" and not checked:
            # Power OFF: Show warning dialog
            from PySide6.QtWidgets import QMessageBox

            warning = QMessageBox(self)
            warning.setWindowTitle("Power Off Device")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Are you sure you want to power off the device?")
            warning.setInformativeText("The software will exit gracefully and the device will be powered down.")
            warning.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)

            # Style the warning dialog
            warning.setStyleSheet(
                "QMessageBox {"
                "  background: #FFFFFF;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QLabel {"
                "  color: #1D1D1F;"
                "  font-size: 13px;"
                "}"
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 16px;"
                "  font-size: 13px;"
                "  min-width: 60px;"
                "  min-height: 28px;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
                "QPushButton:default {"
                "  background: #FF3B30;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:default:hover {"
                "  background: #E6342A;"
                "}"
            )

            result = warning.exec()

            if result == QMessageBox.StandardButton.Yes:
                # User confirmed power off
                print("[PROTOTYPE] Power OFF: Gracefully shutting down device...")
                self.power_btn.setProperty("powerState", "disconnected")
                self._update_power_button_style()
                self.power_btn.setChecked(False)

                # Reset all subunit status to "Not Ready"
                self._reset_subunit_status()
            else:
                # User cancelled, revert button state
                self.power_btn.setChecked(True)
                print("[PROTOTYPE] Power OFF cancelled by user")

    def _simulate_device_search(self):
        """Simulate device search result (for prototype demonstration)."""
        import random

        # Randomly simulate device found or not found (50/50)
        device_found = random.choice([True, False])

        if device_found:
            # Device found - transition to connected (green)
            print("[PROTOTYPE] Device found! Connection established.")
            self.power_btn.setProperty("powerState", "connected")
            self._update_power_button_style()
            self.power_btn.setChecked(True)

            # Check subunit readiness after device connection
            self._update_subunit_readiness()
        else:
            # Device not found - return to gray (disconnected)
            print("[PROTOTYPE] Device not found. Returning to disconnected state.")
            self.power_btn.setProperty("powerState", "disconnected")
            self._update_power_button_style()
            self.power_btn.setChecked(False)

            # Reset all subunit status
            self._reset_subunit_status()

    def _reset_subunit_status(self):
        """Reset all subunit status indicators to 'Not Ready' state."""
        for subunit_name in ["Sensor", "Optics", "Fluidics"]:
            if subunit_name in self.sidebar.subunit_status:
                indicator = self.sidebar.subunit_status[subunit_name]['indicator']
                status_label = self.sidebar.subunit_status[subunit_name]['status_label']

                # Gray indicator and "Not Ready" text
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        # Also disable all operation modes when disconnecting
        self._update_operation_modes(has_detector=False, has_pump=False)

        print("[PROTOTYPE] All subunits reset to Not Ready")

    def _update_operation_modes(self, has_detector, has_pump):
        """Update operation mode availability based on connected hardware.

        Args:
            has_detector: True if a detector/spectrometer is connected
            has_pump: True if a pump controller is connected
        """
        # Static mode: Enabled when detector is connected
        if "Static" in self.sidebar.operation_modes:
            static_enabled = has_detector
            indicator = self.sidebar.operation_modes["Static"]['indicator']
            label = self.sidebar.operation_modes["Static"]['label']
            status_label = self.sidebar.operation_modes["Static"]['status_label']

            if static_enabled:
                # Green indicator and "Enabled" text
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"  # Black when enabled
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Enabled")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                # Gray indicator and "Disabled" text
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray when disabled
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Disabled")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        # Flow mode: Enabled when BOTH detector AND pump are connected
        if "Flow" in self.sidebar.operation_modes:
            flow_enabled = has_detector and has_pump
            indicator = self.sidebar.operation_modes["Flow"]['indicator']
            label = self.sidebar.operation_modes["Flow"]['label']
            status_label = self.sidebar.operation_modes["Flow"]['status_label']

            if flow_enabled:
                # Green indicator and "Enabled" text
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #1D1D1F;"  # Black when enabled
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Enabled")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                # Gray indicator and "Disabled" text (or show reason)
                indicator.setStyleSheet(
                    "font-size: 10px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray when disabled
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                # Show specific reason if detector is present but pump is missing
                if has_detector and not has_pump:
                    status_label.setText("No Pump")
                else:
                    status_label.setText("Disabled")
                status_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        print(f"[PROTOTYPE] Operation Modes - Static: {'Enabled' if has_detector else 'Disabled'}, "
              f"Flow: {'Enabled' if has_detector and has_pump else 'Disabled'}")

    def _handle_scan_hardware(self):
        """Handle hardware scan button click."""
        # Don't scan if already scanning
        if self.sidebar.scan_btn.property("scanning"):
            return

        print("[PROTOTYPE] Scanning for hardware...")
        self.sidebar.scan_btn.setProperty("scanning", True)
        self._update_scan_button_style()

        # Simulate hardware scan with timer
        self.hardware_scan_timer = QTimer()
        self.hardware_scan_timer.setSingleShot(True)
        self.hardware_scan_timer.timeout.connect(self._simulate_hardware_scan)
        self.hardware_scan_timer.start(1500)  # Simulate 1.5 second scan

    def _simulate_hardware_scan(self):
        """Simulate hardware scan result (for prototype demonstration)."""
        import random

        # Randomly find 0-3 devices
        num_devices = random.randint(0, 3)
        device_types = ["Spectrometer", "Pump Controller", "Temperature Sensor", "Flow Meter"]

        # Track what types of devices are connected
        has_detector = False
        has_pump = False

        # Update device labels
        for i in range(3):
            if i < num_devices:
                device_type = random.choice(device_types)
                device_id = f"SN{random.randint(1000, 9999)}"

                # Track device types for operation mode logic
                if device_type == "Spectrometer":
                    has_detector = True
                elif device_type == "Pump Controller":
                    has_pump = True

                self.sidebar.hw_device_labels[i].setText(f"• {device_type} ({device_id})")
                self.sidebar.hw_device_labels[i].setStyleSheet(
                    "font-size: 13px;"
                    "color: #34C759;"  # Green for connected
                    "background: transparent;"
                    "margin-left: 12px;"
                    "margin-top: 4px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                self.sidebar.hw_device_labels[i].setVisible(True)
            else:
                self.sidebar.hw_device_labels[i].setVisible(False)

        # Show/hide "no devices" message
        self.sidebar.hw_no_devices.setVisible(num_devices == 0)

        # Reset scan button
        self.sidebar.scan_btn.setProperty("scanning", False)
        self._update_scan_button_style()

        print(f"[PROTOTYPE] Scan complete: Found {num_devices} device(s)")

        # Update operation modes based on connected hardware
        self._update_operation_modes(has_detector, has_pump)

        # Update subunit readiness after hardware scan
        if num_devices > 0:
            self._update_subunit_readiness()

    def _update_subunit_readiness(self):
        """Update subunit readiness status based on simulated signal thresholds."""
        import random

        # Simulate checking each subunit
        subunits = ["Sensor", "Optics", "Fluidics"]

        for subunit_name in subunits:
            # Simulate random readiness (in real app, check actual signal thresholds)
            is_ready = random.choice([True, False])

            if subunit_name in self.sidebar.subunit_status:
                indicator = self.sidebar.subunit_status[subunit_name]['indicator']
                status_label = self.sidebar.subunit_status[subunit_name]['status_label']

                if is_ready:
                    # Green indicator and "Ready" text
                    indicator.setStyleSheet(
                        "font-size: 10px;"
                        "color: #34C759;"  # Green
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    status_label.setText("Ready")
                    status_label.setStyleSheet(
                        "font-size: 13px;"
                        "color: #34C759;"  # Green
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                else:
                    # Gray indicator and "Not Ready" text
                    indicator.setStyleSheet(
                        "font-size: 10px;"
                        "color: #86868B;"  # Gray
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )
                    status_label.setText("Not Ready")
                    status_label.setStyleSheet(
                        "font-size: 13px;"
                        "color: #86868B;"  # Gray
                        "background: transparent;"
                        "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    )

                print(f"[PROTOTYPE] {subunit_name}: {'Ready' if is_ready else 'Not Ready'}")

    def _update_scan_button_style(self):
        """Update scan button style based on scanning state."""
        is_scanning = self.sidebar.scan_btn.property("scanning")

        if is_scanning:
            # Scanning state (yellow/disabled)
            self.sidebar.scan_btn.setText("Scanning...")
            self.sidebar.scan_btn.setEnabled(False)
            self.sidebar.scan_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: #1D1D1F;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 8px 12px;"
                "  font-size: 13px;"
                "  text-align: center;"
                "  margin-left: 12px;"
                "  margin-top: 8px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )
        else:
            # Normal state (blue/clickable)
            self.sidebar.scan_btn.setText("Scan for Hardware")
            self.sidebar.scan_btn.setEnabled(True)
            self.sidebar.scan_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 8px 12px;"
                "  font-size: 13px;"
                "  text-align: center;"
                "  margin-left: 12px;"
                "  margin-top: 8px;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #3A3A3C;"
                "}"
                "QPushButton:pressed {"
                "  background: #48484A;"
                "}"
            )

    def _handle_debug_log_download(self):
        """Handle debug log download button click."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import datetime

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"ezControl_debug_log_{timestamp}.txt"

        # Open file save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Debug Log",
            default_filename,
            "Log Files (*.txt *.log);;All Files (*.*)"
        )

        if file_path:
            try:
                # In real app, this would collect actual debug log data
                # For prototype, create a sample debug log
                debug_content = f"""ezControl Debug Log
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
================================================

SYSTEM INFORMATION
------------------
Software Version: 4.0.0-prototype
Python Version: 3.12.0
Qt Version: 6.10.0
Operating System: Windows 11

HARDWARE STATUS
------------------
Connected Devices: 1
  - Device Type: SPR Sensor
  - Serial Number: SPR-2025-001
  - Firmware Version: 2.3.1
  - Connection: USB 3.0

SUBUNIT STATUS
------------------
Sensor: Ready
Optics: Ready
Fluidics: Not Ready

OPERATIONAL LOG
------------------
[2025-11-20 14:23:15] Device powered on
[2025-11-20 14:23:16] Hardware scan initiated
[2025-11-20 14:23:17] Device SPR-2025-001 detected
[2025-11-20 14:23:18] Subunit readiness check completed
[2025-11-20 14:23:20] Calibration loaded
[2025-11-20 14:24:00] Recording started - Cycle 1
[2025-11-20 14:29:00] Recording stopped

PERFORMANCE METRICS
------------------
Total Operation Hours: 1,247 hrs
Last Operation: Nov 19, 2025
Average Session Duration: 3.2 hrs
Total Cycles Recorded: 8,432

ERROR LOG
------------------
[2025-11-19 10:15:23] WARNING: Temperature drift detected (23.2°C -> 23.8°C)
[2025-11-18 15:42:10] INFO: Fluidics pump recalibrated
[2025-11-17 08:30:05] WARNING: LED intensity below threshold, auto-adjusted

MAINTENANCE REMINDERS
------------------
• Clean optics - Due at 1,500 hrs (253 hrs remaining)
• Replace flow cell - Due at 2,000 hrs (753 hrs remaining)
• Calibration check - Due every 250 hrs (Next: 3 hrs)

================================================
End of Debug Log
"""

                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(debug_content)

                # Show success message
                msg = QMessageBox(self)
                msg.setWindowTitle("Debug Log Saved")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText("Debug log saved successfully")
                msg.setInformativeText(f"File saved to:\n{file_path}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.setStyleSheet(
                    "QMessageBox {"
                    "  background: #FFFFFF;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QLabel {"
                    "  color: #1D1D1F;"
                    "  font-size: 13px;"
                    "}"
                    "QPushButton {"
                    "  background: #1D1D1F;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 6px 16px;"
                    "  font-size: 13px;"
                    "  font-weight: 600;"
                    "  min-width: 60px;"
                    "  min-height: 28px;"
                    "}"
                    "QPushButton:hover {"
                    "  background: #3A3A3C;"
                    "}"
                )
                msg.exec()

                print(f"[PROTOTYPE] Debug log saved to: {file_path}")

            except Exception as e:
                # Show error message
                error_msg = QMessageBox(self)
                error_msg.setWindowTitle("Error")
                error_msg.setIcon(QMessageBox.Icon.Critical)
                error_msg.setText("Failed to save debug log")
                error_msg.setInformativeText(f"Error: {str(e)}")
                error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_msg.setStyleSheet(
                    "QMessageBox {"
                    "  background: #FFFFFF;"
                    "}"
                    "QPushButton {"
                    "  background: #FF3B30;"
                    "  color: white;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 6px 16px;"
                    "}"
                )
                error_msg.exec()

                print(f"[PROTOTYPE] Error saving debug log: {e}")

    def _toggle_recording(self):
        """Toggle recording state with file save dialog."""
        if not self.is_recording:
            # User pressed Record - show save dialog
            from PySide6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Recording As",
                "experiment_data.h5",
                "HDF5 Files (*.h5);;CSV Files (*.csv);;All Files (*.*)"
            )

            if file_path:
                # User selected a file - start recording
                self.is_recording = True
                self.record_btn.setChecked(True)

                # Update recording indicator
                self.rec_status_dot.setStyleSheet(
                    "QLabel {"
                    "  color: #FF3B30;"
                    "  font-size: 16px;"
                    "  background: transparent;"
                    "}"
                )
                self.rec_status_text.setText(f"Recording to: {file_path.split('/')[-1]}")
                self.rec_status_text.setStyleSheet(
                    "QLabel {"
                    "  font-size: 12px;"
                    "  color: #FF3B30;"
                    "  background: transparent;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "  font-weight: 600;"
                    "}"
                )
                self.recording_indicator.setStyleSheet(
                    "QFrame {"
                    "  background: rgba(255, 59, 48, 0.1);"
                    "  border: 1px solid rgba(255, 59, 48, 0.3);"
                    "  border-radius: 6px;"
                    "}"
                )
            else:
                # User cancelled - uncheck the button
                self.record_btn.setChecked(False)
        else:
            # User pressed Stop - stop recording
            self.is_recording = False
            self.record_btn.setChecked(False)

            # Update recording indicator back to viewing mode
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #86868B;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            self.rec_status_text.setText("Viewing (not saved)")
            self.rec_status_text.setStyleSheet(
                "QLabel {"
                "  font-size: 12px;"
                "  color: #86868B;"
                "  background: transparent;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "  font-weight: 500;"
                "}"
            )
            self.recording_indicator.setStyleSheet(
                "QFrame {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border-radius: 6px;"
                "}"
            )

    def _connect_signals(self):
        """Connect UI signals."""
        self.sidebar.scan_btn.clicked.connect(self._handle_scan_hardware)
        self.sidebar.debug_log_btn.clicked.connect(self._handle_debug_log_download)


# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindowPrototype()
    window.show()
    sys.exit(app.exec())


