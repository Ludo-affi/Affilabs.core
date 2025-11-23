"""Standalone UI prototype for main window design."""

import sys
from pathlib import Path
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QParallelAnimationGroup, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame, QToolButton, QScrollArea, QGraphicsDropShadowEffect,
    QSlider, QSpinBox, QSplitter, QMenu, QMessageBox, QCheckBox, QDialog, QLineEdit, QComboBox,
    QRadioButton, QButtonGroup, QFormLayout, QDialogButtonBox
)
from PySide6.QtGui import QIcon, QColor, QFont, QAction

# Add Old software to path for imports
old_software = Path(__file__).parent
sys.path.insert(0, str(old_software))

from utils.logger import logger
from datetime import datetime


class ElementInspector:
    """Utility to inspect UI elements and copy their information."""

    @staticmethod
    def get_element_info(widget):
        """Extract detailed information about a widget."""
        info_parts = []

        # Widget class and object name
        info_parts.append(f"Class: {widget.__class__.__name__}")
        if widget.objectName():
            info_parts.append(f"ObjectName: {widget.objectName()}")

        # Text content (if applicable)
        if hasattr(widget, 'text') and callable(widget.text):
            text = widget.text()
            if text:
                info_parts.append(f"Text: {text}")

        # Window title (if applicable)
        if hasattr(widget, 'windowTitle') and callable(widget.windowTitle):
            title = widget.windowTitle()
            if title:
                info_parts.append(f"WindowTitle: {title}")

        # Geometry
        geo = widget.geometry()
        info_parts.append(f"Geometry: x={geo.x()}, y={geo.y()}, w={geo.width()}, h={geo.height()}")

        # Size
        size = widget.size()
        info_parts.append(f"Size: {size.width()}x{size.height()}")

        # Visibility
        info_parts.append(f"Visible: {widget.isVisible()}")
        info_parts.append(f"Enabled: {widget.isEnabled()}")

        # Parent hierarchy
        parent_chain = []
        parent = widget.parent()
        while parent and len(parent_chain) < 5:
            parent_name = parent.__class__.__name__
            if parent.objectName():
                parent_name += f" ({parent.objectName()})"
            parent_chain.append(parent_name)
            parent = parent.parent()

        if parent_chain:
            info_parts.append(f"Parent Chain: {' > '.join(parent_chain)}")

        # Stylesheet (first 200 chars)
        stylesheet = widget.styleSheet()
        if stylesheet:
            preview = stylesheet[:200].replace('\n', ' ')
            if len(stylesheet) > 200:
                preview += "..."
            info_parts.append(f"StyleSheet: {preview}")

        return "\n".join(info_parts)

    @staticmethod
    def install_inspector(widget):
        """Install right-click inspector on a widget and all its children."""
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos: ElementInspector.show_inspector_menu(widget, pos)
        )

        # Recursively install on all children
        for child in widget.findChildren(QWidget):
            if not child.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent):
                child.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                child.customContextMenuRequested.connect(
                    lambda pos, w=child: ElementInspector.show_inspector_menu(w, pos)
                )

    @staticmethod
    def show_inspector_menu(widget, pos):
        """Show context menu with inspect option."""
        menu = QMenu(widget)

        # Inspect action
        inspect_action = QAction("🔍 Copy Element Info", menu)
        inspect_action.triggered.connect(
            lambda: ElementInspector.copy_element_info(widget)
        )
        menu.addAction(inspect_action)

        # Show menu at cursor position
        menu.exec(widget.mapToGlobal(pos))

    @staticmethod
    def copy_element_info(widget):
        """Copy element information to clipboard."""
        info = ElementInspector.get_element_info(widget)
        clipboard = QApplication.clipboard()
        clipboard.setText(info)

        # Visual feedback
        print("📋 Element info copied to clipboard:")
        print(info)
        print("-" * 60)


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

                # Upcoming Maintenance (Annual reminder - every November)
                upcoming_row = QHBoxLayout()
                upcoming_row.setSpacing(8)
                upcoming_label = QLabel("Annual Maintenance:")
                upcoming_label.setStyleSheet(
                    "font-size: 13px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                upcoming_row.addWidget(upcoming_label)

                self.next_maintenance_value = QLabel("November 2025")
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF9500;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                upcoming_row.addWidget(self.next_maintenance_value)
                upcoming_row.addStretch()
                stats_layout.addLayout(upcoming_row)

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

                tab_layout.addSpacing(16)

                # Software Version
                version_label = QLabel("AffiLabs.core Beta")
                version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                version_label.setStyleSheet(
                    "font-size: 11px;"
                    "font-weight: 500;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(version_label)

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
                self.filter_enable = QCheckBox("Enable data filtering")
                self.filter_enable.setChecked(True)  # Enabled by default (matches old software)
                self.filter_enable.setStyleSheet(
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
                filter_card_layout.addWidget(self.filter_enable)

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

                self.filter_slider = QSlider(Qt.Horizontal)
                self.filter_slider.setRange(1, 10)
                self.filter_slider.setValue(1)  # Default: 1 = window 3 (matches MED_FILT_WIN)
                self.filter_slider.setEnabled(True)  # Enabled since checkbox is checked
                self.filter_slider.setStyleSheet(
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
                param_row.addWidget(self.filter_slider)

                self.filter_value_label = QLabel("1")
                self.filter_value_label.setFixedWidth(20)
                self.filter_value_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                param_row.addWidget(self.filter_value_label)

                filter_card_layout.addLayout(param_row)

                # Filter method selection
                method_row = QHBoxLayout()
                method_row.setSpacing(10)
                method_label = QLabel("Method:")
                method_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                method_row.addWidget(method_label)

                from PySide6.QtWidgets import QRadioButton, QButtonGroup
                self.filter_method_group = QButtonGroup()

                self.median_filter_radio = QRadioButton("Filter 1")
                self.median_filter_radio.setChecked(True)
                self.median_filter_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 4px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 7px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 3px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                self.filter_method_group.addButton(self.median_filter_radio, 0)
                method_row.addWidget(self.median_filter_radio)

                self.kalman_filter_radio = QRadioButton("Filter 2")
                self.kalman_filter_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 4px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 7px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 3px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                self.filter_method_group.addButton(self.kalman_filter_radio, 1)
                method_row.addWidget(self.kalman_filter_radio)

                self.sg_filter_radio = QRadioButton("Filter 3")
                self.sg_filter_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 4px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 7px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 3px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                self.filter_method_group.addButton(self.sg_filter_radio, 2)
                method_row.addWidget(self.sg_filter_radio)
                method_row.addStretch()

                filter_card_layout.addLayout(method_row)

                # Connect filter slider to enable/disable and value display
                self.filter_enable.toggled.connect(self.filter_slider.setEnabled)
                self.filter_slider.valueChanged.connect(
                    lambda v: self.filter_value_label.setText(str(v))
                )

                tab_layout.addWidget(filter_card)
                tab_layout.addSpacing(16)

                # Section 1b: Data Pipeline
                pipeline_section = QLabel("Data Pipeline")
                pipeline_section.setStyleSheet(
                    "font-size: 15px;"
                    "font-weight: 600;"
                    "color: #1D1D1F;"
                    "background: transparent;"
                    "margin-top: 8px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                tab_layout.addWidget(pipeline_section)

                tab_layout.addSpacing(8)

                pipeline_divider = QFrame()
                pipeline_divider.setFixedHeight(1)
                pipeline_divider.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.1);"
                )
                tab_layout.addWidget(pipeline_divider)

                tab_layout.addSpacing(12)

                # Pipeline Selection Card
                pipeline_card = QWidget()
                pipeline_card.setStyleSheet(
                    "QWidget {"
                    "  background: white;"
                    "  border-radius: 8px;"
                    "}"
                )
                pipeline_card_layout = QVBoxLayout(pipeline_card)
                pipeline_card_layout.setContentsMargins(16, 16, 16, 16)
                pipeline_card_layout.setSpacing(12)

                # Pipeline method selection
                pipeline_method_row = QHBoxLayout()
                pipeline_method_row.setSpacing(10)
                pipeline_method_label = QLabel("Processing:")
                pipeline_method_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                pipeline_method_row.addWidget(pipeline_method_label)

                self.pipeline_method_group = QButtonGroup()

                self.pipeline1_radio = QRadioButton("Pipeline 1")
                self.pipeline1_radio.setChecked(True)
                self.pipeline1_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 4px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 7px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 3px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                self.pipeline_method_group.addButton(self.pipeline1_radio, 0)
                pipeline_method_row.addWidget(self.pipeline1_radio)

                self.pipeline2_radio = QRadioButton("Pipeline 2")
                self.pipeline2_radio.setStyleSheet(
                    "QRadioButton {"
                    "  font-size: 12px;"
                    "  color: #1D1D1F;"
                    "  background: transparent;"
                    "  spacing: 4px;"
                    "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                    "QRadioButton::indicator {"
                    "  width: 14px;"
                    "  height: 14px;"
                    "  border: 1px solid rgba(0, 0, 0, 0.2);"
                    "  border-radius: 7px;"
                    "  background: white;"
                    "}"
                    "QRadioButton::indicator:checked {"
                    "  background: #1D1D1F;"
                    "  border: 3px solid white;"
                    "  outline: 1px solid #1D1D1F;"
                    "}"
                )
                self.pipeline_method_group.addButton(self.pipeline2_radio, 1)
                pipeline_method_row.addWidget(self.pipeline2_radio)
                pipeline_method_row.addStretch()

                pipeline_card_layout.addLayout(pipeline_method_row)

                # Connect pipeline selection to backend
                self.pipeline_method_group.buttonClicked.connect(self.on_pipeline_changed)

                tab_layout.addWidget(pipeline_card)
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

                self.ref_combo = QComboBox()
                self.ref_combo.addItems(["None", "Channel A", "Channel B", "Channel C", "Channel D"])
                self.ref_combo.setFixedWidth(120)
                self.ref_combo.setStyleSheet(
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
                ref_channel_row.addWidget(self.ref_combo)
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
                self.axis_button_group = QButtonGroup(self)
                self.axis_button_group.setExclusive(True)

                self.x_axis_btn = QPushButton("X-Axis")
                self.x_axis_btn.setCheckable(True)
                self.x_axis_btn.setChecked(True)
                self.x_axis_btn.setFixedHeight(28)
                self.x_axis_btn.setStyleSheet(
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
                self.axis_button_group.addButton(self.x_axis_btn, 0)
                axis_selector_row.addWidget(self.x_axis_btn)

                self.y_axis_btn = QPushButton("Y-Axis")
                self.y_axis_btn.setCheckable(True)
                self.y_axis_btn.setFixedHeight(28)
                self.y_axis_btn.setStyleSheet(
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
                self.axis_button_group.addButton(self.y_axis_btn, 1)
                axis_selector_row.addWidget(self.y_axis_btn)

                axis_selector_row.addSpacing(16)

                # Grid toggle next to axis selector
                self.grid_check = QCheckBox("Grid")
                self.grid_check.setChecked(True)
                self.grid_check.setStyleSheet(
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
                axis_selector_row.addWidget(self.grid_check)

                axis_selector_row.addStretch()

                display_card_layout.addLayout(axis_selector_row)

                # Unified Axis Scaling controls (will update based on selection)
                scale_radio_group = QButtonGroup()
                scale_radio_group.setExclusive(True)

                self.auto_radio = QRadioButton("Autoscale")
                self.auto_radio.setChecked(True)
                self.auto_radio.setStyleSheet(
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
                scale_radio_group.addButton(self.auto_radio, 0)
                display_card_layout.addWidget(self.auto_radio)

                # Manual scaling container
                manual_container = QWidget()
                manual_layout = QVBoxLayout(manual_container)
                manual_layout.setContentsMargins(0, 0, 0, 0)
                manual_layout.setSpacing(6)

                self.manual_radio = QRadioButton("Manual")
                self.manual_radio.setStyleSheet(
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
                scale_radio_group.addButton(self.manual_radio, 1)
                manual_layout.addWidget(self.manual_radio)

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

                self.min_input = QLineEdit()
                self.min_input.setPlaceholderText("0")
                self.min_input.setFixedWidth(60)
                self.min_input.setEnabled(False)
                self.min_input.setStyleSheet(
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
                inputs_row.addWidget(self.min_input)

                max_label = QLabel("Max:")
                max_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                inputs_row.addWidget(max_label)

                self.max_input = QLineEdit()
                self.max_input.setPlaceholderText("100")
                self.max_input.setFixedWidth(60)
                self.max_input.setEnabled(False)
                self.max_input.setStyleSheet(
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
                inputs_row.addWidget(self.max_input)
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
                self.colorblind_check = QCheckBox("Enable colour-blind friendly palette")
                self.colorblind_check.setStyleSheet(
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
                accessibility_card_layout.addWidget(self.colorblind_check)

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
                # Section 1: Spectroscopy (Transmission and Raw Data graphs)
                graph_section = QLabel("Spectroscopy")
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

                self.graph_button_group = QButtonGroup(self)
                self.graph_button_group.setExclusive(True)  # Only one can be selected at a time

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

                # Transmission plot (shown by default)
                import pyqtgraph as pg
                self.transmission_plot = pg.PlotWidget()
                self.transmission_plot.setBackground('#FFFFFF')
                self.transmission_plot.setLabel('left', 'Transmittance (%)', color='#86868B', size='10pt')
                self.transmission_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
                self.transmission_plot.showGrid(x=True, y=True, alpha=0.15)
                self.transmission_plot.setMinimumHeight(200)

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

                graph_card_layout.addWidget(self.transmission_plot)

                # Raw data (intensity) plot (hidden by default)
                self.raw_data_plot = pg.PlotWidget()
                self.raw_data_plot.setBackground('#FFFFFF')
                self.raw_data_plot.setLabel('left', 'Intensity (counts)', color='#86868B', size='10pt')
                self.raw_data_plot.setLabel('bottom', 'Wavelength (nm)', color='#86868B', size='10pt')
                self.raw_data_plot.showGrid(x=True, y=True, alpha=0.15)
                self.raw_data_plot.setMinimumHeight(200)
                self.raw_data_plot.setVisible(False)  # Hidden by default

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

                self.s_position_input = QLineEdit()
                self.s_position_input.setPlaceholderText("0-255")
                self.s_position_input.setFixedWidth(60)
                self.s_position_input.setStyleSheet(
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
                self.p_position_input.setPlaceholderText("0-255")
                self.p_position_input.setFixedWidth(60)
                self.p_position_input.setStyleSheet(
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
                polarizer_row.addWidget(self.p_position_input)

                # Toggle S/P Button - shows current position
                self.polarizer_toggle_btn = QPushButton("Position: S")
                self.polarizer_toggle_btn.setFixedWidth(100)
                self.polarizer_toggle_btn.setFixedHeight(28)
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
                self.channel_a_input.setFixedWidth(60)
                self.channel_a_input.setStyleSheet(
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
                self.channel_b_input.setFixedWidth(60)
                self.channel_b_input.setStyleSheet(
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
                self.channel_c_input.setFixedWidth(60)
                self.channel_c_input.setStyleSheet(
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
                self.channel_d_input.setFixedWidth(60)
                self.channel_d_input.setStyleSheet(
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

                # Apply Settings Button Row with Advanced Settings icon
                settings_button_row = QHBoxLayout()
                settings_button_row.setSpacing(8)

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
                self.advanced_settings_btn.clicked.connect(self.open_advanced_settings)
                settings_button_row.addWidget(self.advanced_settings_btn)

                polarizer_led_card_layout.addLayout(settings_button_row)

                # Connect polarizer toggle button
                self.polarizer_toggle_btn.clicked.connect(self.toggle_polarizer_position)

                tab_layout.addWidget(polarizer_led_card)

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

                # Simple LED Calibration Button (moved to top)
                self.simple_led_calibration_btn = QPushButton("Simple LED Calibration")
                self.simple_led_calibration_btn.setFixedHeight(32)
                self.simple_led_calibration_btn.setStyleSheet(
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
                calibration_card_layout.addWidget(self.simple_led_calibration_btn)

                # Full Calibration Button (moved to middle)
                self.full_calibration_btn = QPushButton("Full Calibration")
                self.full_calibration_btn.setFixedHeight(32)
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

                # OEM LED Calibration Button (with afterglow)
                self.oem_led_calibration_btn = QPushButton("OEM LED Calibration")
                self.oem_led_calibration_btn.setFixedHeight(32)
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

                tab_layout.addWidget(calibration_card)

                tab_layout.addSpacing(20)

            # Static Tab Content with Collapsible Sections
            elif label == "Static":
                # Signal Intel Bar (compact status indicators without card background)
                signal_bar = QWidget()
                signal_bar.setStyleSheet("background: transparent;")
                signal_layout = QHBoxLayout(signal_bar)
                signal_layout.setContentsMargins(16, 12, 16, 8)
                signal_layout.setSpacing(12)

                # Good status indicator
                good_status = QLabel("✓ Good")
                good_status.setStyleSheet(
                    "font-size: 12px;"
                    "font-weight: 700;"
                    "color: #34C759;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                signal_layout.addWidget(good_status)

                # Separator
                separator = QLabel("•")
                separator.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"
                    "background: transparent;"
                )
                signal_layout.addWidget(separator)

                # Ready for injection indicator
                ready_status = QLabel("→ Ready for injection")
                ready_status.setStyleSheet(
                    "font-size: 12px;"
                    "font-weight: 600;"
                    "color: #007AFF;"
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                signal_layout.addWidget(ready_status)

                # Countdown (close to ready status)
                countdown_label = QLabel("00:30")
                countdown_label.setStyleSheet(
                    "font-size: 11px;"
                    "color: #1D1D1F;"
                    "background: rgba(0, 0, 0, 0.06);"
                    "padding: 2px 8px;"
                    "border-radius: 4px;"
                    "font-weight: 700;"
                    "font-family: -apple-system, 'SF Mono', 'Menlo', monospace;"
                )
                signal_layout.addWidget(countdown_label)

                signal_layout.addStretch()

                tab_layout.addWidget(signal_bar)
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

                # Start Cycle Button (Sequential mode)
                self.start_cycle_btn = QPushButton("▶ Start Cycle")
                self.start_cycle_btn.setFixedSize(120, 36)
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

                # Add to Queue Button (Batch mode)
                self.add_to_queue_btn = QPushButton("+ Add to Queue")
                self.add_to_queue_btn.setFixedSize(140, 36)
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

                # Help text
                help_text = QLabel("▶ Start Cycle: Begin this cycle immediately | + Add to Queue: Plan multiple cycles (up to 5)")
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
                self.summary_table = QTableWidget(5, 4)  # Added State column
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

                # Populate with empty data (will be filled by queue operations)
                from PySide6.QtWidgets import QTableWidgetItem

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

                # Open Full Data Table Button (compact, right-aligned)
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

                self.export_channel_checkboxes = []
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
                self.export_channel_checkboxes.append(ch_check)
                channel_row.addWidget(ch_check)

                channel_row.addStretch()
                channel_card_layout.addLayout(channel_row)

                # Select All button
                self.select_all_channels_btn = QPushButton("Select All")
                self.select_all_channels_btn.setFixedHeight(28)
                self.select_all_channels_btn.setFixedWidth(100)
                self.select_all_channels_btn.setStyleSheet(
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
                self.select_all_channels_btn.clicked.connect(self.toggle_all_channels)
                channel_card_layout.addWidget(self.select_all_channels_btn)

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

                self.export_filename_input = QLineEdit()
                self.export_filename_input.setPlaceholderText("experiment_20251120_143022")
                self.export_filename_input.setStyleSheet(
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
                file_card_layout.addWidget(self.export_filename_input)

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

                self.export_dest_input = QLineEdit()
                self.export_dest_input.setPlaceholderText("C:/Users/Documents/Experiments")
                self.export_dest_input.setStyleSheet(
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
                dest_row.addWidget(self.export_dest_input)

                self.export_browse_btn = QPushButton("Browse...")
                self.export_browse_btn.setFixedHeight(32)
                self.export_browse_btn.setFixedWidth(90)
                self.export_browse_btn.setStyleSheet(
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
                self.export_browse_btn.clicked.connect(self.browse_export_destination)
                dest_row.addWidget(self.export_browse_btn)
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
                self.export_data_btn = QPushButton("📁 Export Data")
                self.export_data_btn.setFixedHeight(40)
                self.export_data_btn.setStyleSheet(
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
                self.export_data_btn.clicked.connect(self.export_data)
                file_card_layout.addWidget(self.export_data_btn)

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

    def _on_spectroscopy_toggle(self, checked: bool):
        """Toggle between transmission and raw data plots."""
        if not checked:  # Button was unchecked (another button was selected)
            return

        # Show the selected plot and hide the other
        if self.transmission_btn.isChecked():
            self.transmission_plot.setVisible(True)
            self.raw_data_plot.setVisible(False)
        elif self.raw_data_btn.isChecked():
            self.transmission_plot.setVisible(False)
            self.raw_data_plot.setVisible(True)

    def on_pipeline_changed(self, button):
        """Handle pipeline selection change in Graphic Control tab."""
        from utils.processing_pipeline import get_pipeline_registry
        registry = get_pipeline_registry()

        pipeline_id = self.pipeline_method_group.checkedId()
        if pipeline_id == 0:
            registry.set_active_pipeline('fourier')
            logger.info("Switched to Pipeline 1 (Fourier Weighted)")
        elif pipeline_id == 1:
            registry.set_active_pipeline('adaptive')
            logger.info("Switched to Pipeline 2 (Adaptive Multi-Feature)")

    def toggle_polarizer_position(self):
        """Toggle polarizer between S and P positions and update button text."""
        if self.current_polarizer_position == 'S':
            self.current_polarizer_position = 'P'
            self.polarizer_toggle_btn.setText("Position: P")
        else:
            self.current_polarizer_position = 'S'
            self.polarizer_toggle_btn.setText("Position: S")

        # This method can be called from main_simplified to actually move the polarizer
        # and will return the new position
        return self.current_polarizer_position

    def set_polarizer_position(self, position: str):
        """Set polarizer position (S or P) and update button text.

        Args:
            position: 'S' or 'P'
        """
        position = position.upper()
        if position in ['S', 'P']:
            self.current_polarizer_position = position
            self.polarizer_toggle_btn.setText(f"Position: {position}")

    def open_advanced_settings(self):
        """Open the advanced settings dialog."""
        dialog = AdvancedSettingsDialog(self)

        # Load current settings
        dialog.ru_btn.setChecked(self.ru_btn.isChecked() if hasattr(self, 'ru_btn') else True)
        dialog.nm_btn.setChecked(self.nm_btn.isChecked() if hasattr(self, 'nm_btn') else False)

        # Load LED delays from settings
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from settings import settings
            pre_led_delay = settings.PRE_LED_DELAY_MS
            post_led_delay = settings.POST_LED_DELAY_MS
            dialog.led_delay_input.setValue(int(pre_led_delay))
            dialog.post_led_delay_input.setValue(int(post_led_delay))
        except Exception as e:
            logger.warning(f"Could not load LED delays, using defaults: {e}")
            dialog.led_delay_input.setValue(45)  # Default PRE LED
            dialog.post_led_delay_input.setValue(5)  # Default POST LED

        # Load current pipeline
        from utils.processing_pipeline import get_pipeline_registry
        registry = get_pipeline_registry()
        current_pipeline = registry.active_pipeline_id
        if current_pipeline == 'fourier':
            dialog.pipeline_combo.setCurrentIndex(0)
        elif current_pipeline == 'adaptive':
            dialog.pipeline_combo.setCurrentIndex(1)
        else:
            dialog.pipeline_combo.setCurrentIndex(0)  # Default to fourier

        # Set filter method from Graphic Control tab
        if hasattr(self, 'filter_method_group'):
            checked_id = self.filter_method_group.checkedId()
            if checked_id >= 0:
                dialog.filter_method_group.button(checked_id).setChecked(True)

        # Load device info (TODO: Get from actual device)
        dialog.load_device_info(
            serial="FLMT09788",  # TODO: Get from device config
            afterglow_cal=False,  # TODO: Check if afterglow calibration exists
            cal_date=None  # TODO: Load from calibration file
        )

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply settings
            if hasattr(self, 'ru_btn'):
                self.ru_btn.setChecked(dialog.ru_btn.isChecked())
                self.nm_btn.setChecked(dialog.nm_btn.isChecked())

            # Update filter method in Graphic Control tab
            if hasattr(self, 'filter_method_group'):
                checked_id = dialog.filter_method_group.checkedId()
                if checked_id >= 0:
                    self.filter_method_group.button(checked_id).setChecked(True)

            # Switch pipeline based on selection
            from utils.processing_pipeline import get_pipeline_registry
            registry = get_pipeline_registry()
            pipeline_idx = dialog.pipeline_combo.currentIndex()
            if pipeline_idx == 0:
                registry.set_active_pipeline('fourier')
                logger.info("Switched to Pipeline 1 (Fourier Weighted)")
                # Update Graphic Control tab pipeline selection
                if hasattr(self, 'pipeline_method_group'):
                    self.pipeline_method_group.button(0).setChecked(True)
            elif pipeline_idx == 1:
                registry.set_active_pipeline('adaptive')
                logger.info("Switched to Pipeline 2 (Adaptive Multi-Feature)")
                # Update Graphic Control tab pipeline selection
                if hasattr(self, 'pipeline_method_group'):
                    self.pipeline_method_group.button(1).setChecked(True)

            # Apply LED delay settings
            pre_led_delay = dialog.led_delay_input.value()
            post_led_delay = dialog.post_led_delay_input.value()

            # Update PRE_LED_DELAY_MS and POST_LED_DELAY_MS in settings
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from settings import settings
                settings.PRE_LED_DELAY_MS = float(pre_led_delay)
                settings.POST_LED_DELAY_MS = float(post_led_delay)
                logger.info(f"PRE_LED_DELAY_MS updated to {pre_led_delay}ms")
                logger.info(f"POST_LED_DELAY_MS updated to {post_led_delay}ms")
            except Exception as e:
                logger.warning(f"Could not update LED delays: {e}")

            # Update data acquisition manager LED delay
            if hasattr(self, 'data_acq_mgr') and self.data_acq_mgr is not None:
                self.data_acq_mgr._led_delay_ms = pre_led_delay
                logger.info(f"Data acquisition LED delay updated: {pre_led_delay}ms")
            else:
                logger.info(f"LED delays saved: PRE={pre_led_delay}ms, POST={post_led_delay}ms (will apply when hardware connects)")

            # Apply filter method
            filter_id = dialog.filter_method_group.checkedId()
            if hasattr(self, 'temporal_filter') and self.temporal_filter is not None:
                # Filter methods: 0=Kalman, 1=Moving Average, 2=Exponential
                filter_names = ['Kalman', 'Moving Average', 'Exponential']
                if 0 <= filter_id < len(filter_names):
                    logger.info(f"Filter method updated: {filter_names[filter_id]}")

            logger.info(f"Advanced settings applied successfully")

    def toggle_all_channels(self):
        """Toggle all channel checkboxes between selected and deselected."""
        # Check if all are currently checked
        all_checked = all(cb.isChecked() for cb in self.export_channel_checkboxes)

        # Toggle: if all checked, uncheck all; otherwise check all
        new_state = not all_checked

        for cb in self.export_channel_checkboxes:
            cb.setChecked(new_state)

        # Update button text
        self.select_all_channels_btn.setText("Deselect All" if new_state else "Select All")

    def browse_export_destination(self):
        """Open directory picker for export destination."""
        from PySide6.QtWidgets import QFileDialog

        current_dir = self.export_dest_input.text() or ""

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Export Destination",
            current_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            self.export_dest_input.setText(directory)

    def export_data(self):
        """Export data with current settings - will be handled by MainWindowPrototype."""
        # This will be connected to main_simplified handler
        # For now, just show a placeholder message
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Export Data",
            "Export functionality will be connected to data export handler.\n\n"
            f"Would export to: {self.export_dest_input.text()}\n"
            f"Filename: {self.export_filename_input.text()}"
        )

    def _on_apply_settings(self):
        """Apply polarizer and LED settings to hardware and flash to EEPROM."""
        # This will be connected to main_simplified handler
        pass

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units."""
        # This will be connected to main_simplified handler
        pass


class AdvancedSettingsDialog(QDialog):
    """Advanced Settings Dialog for power users."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        self.setMinimumWidth(550)

        # Style
        self.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "}"
            "QLabel {"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  color: #1D1D1F;"
            "}"
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Title
        title = QLabel("Advanced Settings")
        title.setStyleSheet(
            "font-size: 20px;"
            "font-weight: 700;"
            "color: #1D1D1F;"
            "margin-bottom: 8px;"
        )
        main_layout.addWidget(title)

        # Form layout
        form = QFormLayout()
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Unit Selection (moved from Settings tab)
        unit_label = QLabel("Unit:")
        unit_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        unit_container = QWidget()
        unit_layout = QHBoxLayout(unit_container)
        unit_layout.setContentsMargins(0, 0, 0, 0)
        unit_layout.setSpacing(0)

        self.unit_button_group = QButtonGroup()
        self.unit_button_group.setExclusive(True)

        self.ru_btn = QPushButton("RU")
        self.ru_btn.setCheckable(True)
        self.ru_btn.setChecked(True)
        self.ru_btn.setFixedHeight(28)
        self.ru_btn.setStyleSheet(
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
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        self.unit_button_group.addButton(self.ru_btn, 0)
        unit_layout.addWidget(self.ru_btn)

        self.nm_btn = QPushButton("nm")
        self.nm_btn.setCheckable(True)
        self.nm_btn.setFixedHeight(28)
        self.nm_btn.setStyleSheet(
            "QPushButton {"
            "  background: white;"
            "  color: #86868B;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-top-right-radius: 6px;"
            "  border-bottom-right-radius: 6px;"
            "  padding: 4px 16px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        self.unit_button_group.addButton(self.nm_btn, 1)
        unit_layout.addWidget(self.nm_btn)
        unit_layout.addStretch()

        form.addRow(unit_label, unit_container)

        # PRE LED Delay (ms) - Pre-LED delay before measurement
        led_delay_label = QLabel("PRE LED Delay:")
        led_delay_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.led_delay_input = QSpinBox()
        self.led_delay_input.setRange(0, 200)
        self.led_delay_input.setValue(45)  # Default from PRE_LED_DELAY_MS
        self.led_delay_input.setSuffix(" ms")
        self.led_delay_input.setFixedWidth(120)
        self.led_delay_input.setStyleSheet(
            "QSpinBox {"
            "  padding: 6px 8px;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  background: white;"
            "  font-size: 13px;"
            "}"
        )
        form.addRow(led_delay_label, self.led_delay_input)

        # POST LED Delay (ms) - Post-LED delay after turn-off
        post_led_delay_label = QLabel("POST LED Delay:")
        post_led_delay_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.post_led_delay_input = QSpinBox()
        self.post_led_delay_input.setRange(0, 100)
        self.post_led_delay_input.setValue(5)  # Default from POST_LED_DELAY_MS
        self.post_led_delay_input.setSuffix(" ms")
        self.post_led_delay_input.setFixedWidth(120)
        self.post_led_delay_input.setStyleSheet(
            "QSpinBox {"
            "  padding: 6px 8px;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  background: white;"
            "  font-size: 13px;"
            "}"
        )
        form.addRow(post_led_delay_label, self.post_led_delay_input)

        # Pipeline Selection
        pipeline_label = QLabel("Data Pipeline:")
        pipeline_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.pipeline_combo = QComboBox()
        self.pipeline_combo.addItems([
            "Pipeline 1 (Fourier Weighted)",
            "Pipeline 2 (Adaptive Multi-Feature)"
        ])
        self.pipeline_combo.setFixedWidth(300)
        self.pipeline_combo.setStyleSheet(
            "QComboBox {"
            "  padding: 6px 8px;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 6px;"
            "  background: white;"
            "  font-size: 13px;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 30px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 5px solid #86868B;"
            "  margin-right: 8px;"
            "}"
        )
        form.addRow(pipeline_label, self.pipeline_combo)

        # Data Filtering Options (moved from Graphic Control tab)
        filter_label = QLabel("Data Filtering:")
        filter_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        filter_container = QWidget()
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        self.filter_method_group = QButtonGroup()

        self.filter1_radio = QRadioButton("Filter 1")
        self.filter1_radio.setChecked(True)
        self.filter1_radio.setStyleSheet(
            "QRadioButton {"
            "  font-size: 12px;"
            "  spacing: 4px;"
            "}"
            "QRadioButton::indicator {"
            "  width: 14px;"
            "  height: 14px;"
            "  border: 1px solid rgba(0, 0, 0, 0.2);"
            "  border-radius: 7px;"
            "  background: white;"
            "}"
            "QRadioButton::indicator:checked {"
            "  background: #1D1D1F;"
            "  border: 3px solid white;"
            "  outline: 1px solid #1D1D1F;"
            "}"
        )
        self.filter_method_group.addButton(self.filter1_radio, 0)
        filter_layout.addWidget(self.filter1_radio)

        self.filter2_radio = QRadioButton("Filter 2")
        self.filter2_radio.setStyleSheet(self.filter1_radio.styleSheet())
        self.filter_method_group.addButton(self.filter2_radio, 1)
        filter_layout.addWidget(self.filter2_radio)

        self.filter3_radio = QRadioButton("Filter 3")
        self.filter3_radio.setStyleSheet(self.filter1_radio.styleSheet())
        self.filter_method_group.addButton(self.filter3_radio, 2)
        filter_layout.addWidget(self.filter3_radio)

        filter_layout.addStretch()

        form.addRow(filter_label, filter_container)

        main_layout.addLayout(form)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.1); max-height: 1px;")
        main_layout.addWidget(separator)

        # Device Information Section
        info_section = QLabel("Device Information")
        info_section.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "margin-top: 4px;"
        )
        main_layout.addWidget(info_section)

        # Device info layout
        device_info = QFormLayout()
        device_info.setSpacing(12)
        device_info.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Serial Number
        serial_label = QLabel("Serial Number:")
        serial_label.setStyleSheet("font-size: 13px; color: #86868B;")
        self.serial_value = QLabel("Not detected")
        self.serial_value.setStyleSheet("font-size: 13px; color: #1D1D1F; font-weight: 500;")
        device_info.addRow(serial_label, self.serial_value)

        # Afterglow Calibration Status
        afterglow_label = QLabel("Afterglow Calibration:")
        afterglow_label.setStyleSheet("font-size: 13px; color: #86868B;")
        self.afterglow_value = QLabel("Not calibrated")
        self.afterglow_value.setStyleSheet("font-size: 13px; color: #1D1D1F; font-weight: 500;")
        device_info.addRow(afterglow_label, self.afterglow_value)

        # Calibration Date
        cal_date_label = QLabel("Calibration Date:")
        cal_date_label.setStyleSheet("font-size: 13px; color: #86868B;")
        self.cal_date_value = QLabel("N/A")
        self.cal_date_value.setStyleSheet("font-size: 13px; color: #1D1D1F; font-weight: 500;")
        device_info.addRow(cal_date_label, self.cal_date_value)

        main_layout.addLayout(device_info)

        main_layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.setStyleSheet(
            "QPushButton {"
            "  padding: 8px 20px;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  min-width: 80px;"
            "}"
            "QPushButton[text='OK'] {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "}"
            "QPushButton[text='OK']:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton[text='Cancel'] {"
            "  background: white;"
            "  color: #1D1D1F;"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton[text='Cancel']:hover {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def load_device_info(self, serial="Not detected", afterglow_cal=False, cal_date=None):
        """Load device information into the dialog."""
        self.serial_value.setText(serial if serial else "Not detected")

        if afterglow_cal:
            self.afterglow_value.setText("✓ Calibrated")
            self.afterglow_value.setStyleSheet("font-size: 13px; color: #34C759; font-weight: 600;")
        else:
            self.afterglow_value.setText("Not calibrated")
            self.afterglow_value.setStyleSheet("font-size: 13px; color: #FF9500; font-weight: 600;")

        if cal_date:
            if isinstance(cal_date, str):
                self.cal_date_value.setText(cal_date)
            else:
                self.cal_date_value.setText(cal_date.strftime("%Y-%m-%d %H:%M"))
        else:
            self.cal_date_value.setText("N/A")


class MainWindowPrototype(QMainWindow):
    """Prototype of the main window UI."""

    # Signals for power button
    power_on_requested = Signal()
    power_off_requested = Signal()

    # Signals for recording
    recording_start_requested = Signal()
    recording_stop_requested = Signal()

    # Signals for recording
    recording_start_requested = Signal()
    recording_stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ezControl UI Prototype")
        self.setGeometry(100, 100, 1400, 900)
        self.nav_buttons = []
        self.is_recording = False
        self.recording_indicator = None
        self.record_button = None

        # Device configuration and maintenance tracking
        self.device_config = None
        self.led_start_time = None
        self.last_powered_on = None

        # Live data flag (default enabled)
        self.live_data_enabled = True

        self._setup_ui()
        self._connect_signals()

        # Initialize device configuration after UI is set up
        self._init_device_config()
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
        self.sidebar.setMaximumWidth(900)  # Maximum width for sidebar
        self.splitter.addWidget(self.sidebar)
        self.splitter.setCollapsible(0, False)  # Prevent sidebar from collapsing

        # Forward sidebar control references to main window for easy access
        self.grid_check = self.sidebar.grid_check
        self.auto_radio = self.sidebar.auto_radio
        self.manual_radio = self.sidebar.manual_radio
        self.min_input = self.sidebar.min_input
        self.max_input = self.sidebar.max_input
        self.x_axis_btn = self.sidebar.x_axis_btn
        self.y_axis_btn = self.sidebar.y_axis_btn
        self.colorblind_check = self.sidebar.colorblind_check
        self.ref_combo = self.sidebar.ref_combo
        self.filter_enable = self.sidebar.filter_enable
        self.filter_slider = self.sidebar.filter_slider
        self.filter_value_label = self.sidebar.filter_value_label
        self.median_filter_radio = self.sidebar.median_filter_radio

        # Initialize unit buttons (will be set from advanced settings)
        self.ru_btn = QPushButton("RU")
        self.ru_btn.setCheckable(True)
        self.ru_btn.setChecked(True)
        self.nm_btn = QPushButton("nm")
        self.nm_btn.setCheckable(True)
        self.nm_btn.setChecked(False)

        # Connect unit toggle
        self.ru_btn.toggled.connect(self._on_unit_changed)
        self.nm_btn.toggled.connect(self._on_unit_changed)
        self.kalman_filter_radio = self.sidebar.kalman_filter_radio
        self.sg_filter_radio = self.sidebar.sg_filter_radio
        # Forward spectroscopy plots
        self.transmission_plot = self.sidebar.transmission_plot
        self.transmission_curves = self.sidebar.transmission_curves
        self.raw_data_plot = self.sidebar.raw_data_plot
        self.raw_data_curves = self.sidebar.raw_data_curves
        # Forward settings controls
        self.s_position_input = self.sidebar.s_position_input
        self.p_position_input = self.sidebar.p_position_input
        self.polarizer_toggle_btn = self.sidebar.polarizer_toggle_btn
        self.channel_a_input = self.sidebar.channel_a_input
        self.channel_b_input = self.sidebar.channel_b_input
        self.channel_c_input = self.sidebar.channel_c_input
        self.channel_d_input = self.sidebar.channel_d_input
        self.apply_settings_btn = self.sidebar.apply_settings_btn

        # Forward calibration buttons
        self.simple_led_calibration_btn = self.sidebar.simple_led_calibration_btn
        self.full_calibration_btn = self.sidebar.full_calibration_btn
        self.oem_led_calibration_btn = self.sidebar.oem_led_calibration_btn

        right_widget = QWidget()
        right_widget.setMinimumWidth(300)  # Allow main content to compress so sidebar can expand more
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

        # Set initial sizes: 520px for sidebar (more space due to wide Static section), rest for main content
        self.splitter.setSizes([520, 880])

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
        self.full_timeline_graph, top_graph = self._create_graph_container(
            "Live Sensorgram",
            height=200,
            show_delta_spr=False
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        self.cycle_of_interest_graph, bottom_graph = self._create_graph_container(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True
        )

        # Connect cursor signals for region selection
        if self.full_timeline_graph.start_cursor and self.full_timeline_graph.stop_cursor:
            self.full_timeline_graph.start_cursor.sigDragged.connect(self._on_cursor_dragged)
            self.full_timeline_graph.stop_cursor.sigDragged.connect(self._on_cursor_dragged)
            self.full_timeline_graph.start_cursor.sigPositionChangeFinished.connect(self._on_cursor_moved)
            self.full_timeline_graph.stop_cursor.sigPositionChangeFinished.connect(self._on_cursor_moved)

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
        """Create header with channel toggle controls and live data checkbox."""
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
        self.channel_toggles = {}
        for ch, color in [("A", "#1D1D1F"), ("B", "#FF3B30"), ("C", "#007AFF"), ("D", "#34C759")]:
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

            # Store reference and connect to visibility toggle
            self.channel_toggles[ch] = ch_btn
            ch_btn.toggled.connect(lambda checked, channel=ch: self._toggle_channel_visibility(channel, checked))

            header_layout.addWidget(ch_btn)

        header_layout.addStretch()

        # Live Data checkbox
        self.live_data_checkbox = QCheckBox("Live Data")
        self.live_data_checkbox.setChecked(True)
        self.live_data_checkbox.setStyleSheet(
            "QCheckBox {"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "  spacing: 6px;"
            "}"
            "QCheckBox::indicator {"
            "  width: 18px;"
            "  height: 18px;"
            "  border: 2px solid #86868B;"
            "  border-radius: 4px;"
            "  background: white;"
            "}"
            "QCheckBox::indicator:checked {"
            "  background: #007AFF;"
            "  border-color: #007AFF;"
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEwLjUgMS41TDQgOEwxLjUgNS41IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);"
            "}"
            "QCheckBox::indicator:hover {"
            "  border-color: #007AFF;"
            "}"
        )
        self.live_data_checkbox.toggled.connect(self._toggle_live_data)
        header_layout.addWidget(self.live_data_checkbox)

        return header

    def _toggle_live_data(self, enabled):
        """Toggle live data updates for graphs."""
        self.live_data_enabled = enabled
        if enabled:
            print("Live data updates enabled")
        else:
            print("Live data updates disabled - graph frozen")

    def _toggle_channel_visibility(self, channel, visible):
        """Toggle visibility of a channel on both graphs."""
        channel_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[channel]

        # Update full timeline graph
        if hasattr(self, 'full_timeline_graph'):
            curve = self.full_timeline_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

        # Update cycle of interest graph
        if hasattr(self, 'cycle_of_interest_graph'):
            curve = self.cycle_of_interest_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

    def _create_graph_container(self, title, height, show_delta_spr=False):
        """Create a graph container with title and controls."""
        import pyqtgraph as pg

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
        delta_display = None
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

        layout.addLayout(title_row)

        # Create PyQtGraph PlotWidget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('#FFFFFF')

        # Configure axes based on graph type
        if show_delta_spr:
            # Bottom graph: Δ SPR in RU units
            plot_widget.setLabel('left', 'Δ SPR (RU)', color='#86868B', size='11pt')
        else:
            # Top graph: λ in nm units (lambda symbol only)
            plot_widget.setLabel('left', 'λ (nm)', color='#86868B', size='11pt')

        plot_widget.setLabel('bottom', 'Time (seconds)', color='#86868B', size='11pt')

        # Enable grid with subtle styling
        plot_widget.showGrid(x=True, y=True, alpha=0.15)

        # Configure plot appearance
        plot_widget.getPlotItem().getAxis('left').setPen(color='#E5E5EA', width=1)
        plot_widget.getPlotItem().getAxis('bottom').setPen(color='#E5E5EA', width=1)
        plot_widget.getPlotItem().getAxis('left').setTextPen('#86868B')
        plot_widget.getPlotItem().getAxis('bottom').setTextPen('#86868B')

        # Create plot curves for 4 channels with distinct colors
        # Ch A: Black, Ch B: Red, Ch C: Blue, Ch D: Green
        # Standard colors (will be updated if colorblind mode enabled)
        colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
        curves = []
        for i, color in enumerate(colors):
            curve = plot_widget.plot(
                pen=pg.mkPen(color=color, width=2),
                name=f'Channel {chr(65+i)}'  # A, B, C, D
            )
            curves.append(curve)

        # Add Start/Stop cursors for Full Experiment Timeline (top graph)
        start_cursor = None
        stop_cursor = None
        if not show_delta_spr:  # Only for FET graph
            # Start cursor (black with horizontal label centered on line)
            start_cursor = pg.InfiniteLine(
                pos=0,
                angle=90,
                pen=pg.mkPen(color='#1D1D1F', width=2),
                movable=True,
                label='Start: {value:.1f}s',
                labelOpts={
                    'position': 0.5,  # Center of graph
                    'color': '#1D1D1F',
                    'fill': '#FFFFFF',
                    'movable': False,
                    'rotateAxis': (1, 0)  # Rotate 180 degrees total (horizontal)
                }
            )
            plot_widget.addItem(start_cursor)

            # Stop cursor (black with horizontal label centered on line)
            stop_cursor = pg.InfiniteLine(
                pos=100,
                angle=90,
                pen=pg.mkPen(color='#1D1D1F', width=2),
                movable=True,
                label='Stop: {value:.1f}s',
                labelOpts={
                    'position': 0.5,  # Center of graph
                    'color': '#1D1D1F',
                    'fill': '#FFFFFF',
                    'movable': False,
                    'rotateAxis': (1, 0)  # Rotate 180 degrees total (horizontal)
                }
            )
            plot_widget.addItem(stop_cursor)

        # Store references to curves and cursors on the plot widget
        plot_widget.curves = curves
        plot_widget.delta_display = delta_display
        plot_widget.start_cursor = start_cursor
        plot_widget.stop_cursor = stop_cursor
        plot_widget.flag_markers = []  # Store flag marker items

        # Add zoom/reset functionality
        plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode)

        layout.addWidget(plot_widget, 1)

        return plot_widget, container

    def _toggle_channel_visibility(self, channel, visible):
        """Toggle visibility of a channel on both graphs."""
        channel_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[channel]

        # Update full timeline graph
        if hasattr(self, 'full_timeline_graph'):
            curve = self.full_timeline_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

        # Update cycle of interest graph
        if hasattr(self, 'cycle_of_interest_graph'):
            curve = self.cycle_of_interest_graph.curves[channel_idx]
            if visible:
                curve.show()
            else:
                curve.hide()

    def _on_cursor_dragged(self):
        """Handle cursor dragging - update label format dynamically."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        start_cursor = self.full_timeline_graph.start_cursor
        stop_cursor = self.full_timeline_graph.stop_cursor

        if start_cursor and stop_cursor:
            # Update labels with current positions
            start_pos = start_cursor.value()
            stop_pos = stop_cursor.value()

            # Ensure start is always less than stop
            if start_pos > stop_pos:
                start_pos, stop_pos = stop_pos, start_pos

            # Update label text dynamically
            start_cursor.label.setFormat(f'Start: {start_pos:.1f}s')
            stop_cursor.label.setFormat(f'Stop: {stop_pos:.1f}s')

    def _on_cursor_moved(self):
        """Handle cursor movement finished - update selected region."""
        if not hasattr(self, 'full_timeline_graph'):
            return

        start_cursor = self.full_timeline_graph.start_cursor
        stop_cursor = self.full_timeline_graph.stop_cursor

        if start_cursor and stop_cursor:
            start_time = start_cursor.value()
            stop_time = stop_cursor.value()

            # Ensure start is always before stop
            if start_time > stop_time:
                start_time, stop_time = stop_time, start_time
                # Swap cursor positions
                start_cursor.setValue(start_time)
                stop_cursor.setValue(stop_time)

            print(f"Cursor region selected: {start_time:.2f}s to {stop_time:.2f}s")
            # TODO: Update cycle of interest graph to show selected region

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

        # Master-Detail Pattern: Top table (Master) + Bottom detail panel
        # Temporarily simplified for debugging
        from PySide6.QtWidgets import QTableWidget, QHeaderView

        self.cycle_data_table = QTableWidget(10, 6)
        self.cycle_data_table.setHorizontalHeaderLabels(["Type", "Start", "End", "Units", "Notes", "Flags"])
        self.cycle_data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cycle_data_table.setColumnWidth(3, 80)  # Fixed width for Units column
        self.cycle_data_table.verticalHeader().setVisible(True)  # Show row numbers as ID
        self.cycle_data_table.setStyleSheet(
            "QTableWidget {"
            "  background: #FFFFFF;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 8px;"
            "  font-size: 12px;"
            "}"
        )

        table_layout.addWidget(self.cycle_data_table, 1)

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
        """Handle power button toggle - connects/disconnects hardware."""
        current_state = self.power_btn.property("powerState")

        if current_state == "disconnected" and checked:
            # Power ON clicked: Start hardware connection
            print("[UI] Power ON: Starting hardware connection...")
            self.power_btn.setProperty("powerState", "searching")
            self._update_power_button_style()

            # Emit signal to trigger hardware connection (handled by Application class)
            if hasattr(self, 'power_on_requested'):
                self.power_on_requested.emit()

        elif current_state == "searching":
            # Ignore clicks while searching - connection is in progress
            # User must wait for connection to succeed or fail
            print("[UI] Hardware connection in progress - please wait...")
            self.power_btn.setChecked(True)  # Keep button checked

        elif current_state == "connected" and not checked:
            # Power OFF: Show warning dialog
            from PySide6.QtWidgets import QMessageBox

            warning = QMessageBox(self)
            warning.setWindowTitle("Power Off Device")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Are you sure you want to disconnect the device?")
            warning.setInformativeText("All hardware connections will be closed.")
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
                print("[UI] Power OFF: Disconnecting hardware...")
                self.power_btn.setProperty("powerState", "disconnected")
                self._update_power_button_style()
                self.power_btn.setChecked(False)

                # Reset all subunit status to "Not Ready"
                self._reset_subunit_status()

                # Emit signal to disconnect hardware
                if hasattr(self, 'power_off_requested'):
                    self.power_off_requested.emit()
            else:
                # User cancelled, revert button state
                self.power_btn.setChecked(True)
                print("[UI] Power OFF cancelled by user")

    def set_power_state(self, state: str):
        """Set power button state from external controller.

        Args:
            state: 'disconnected', 'searching', or 'connected'
        """
        self.power_btn.setProperty("powerState", state)
        self._update_power_button_style()

        if state == "connected":
            self.power_btn.setChecked(True)
            # Don't update subunit readiness here - it will be updated by update_hardware_status()
        elif state == "disconnected":
            self.power_btn.setChecked(False)
            self._reset_subunit_status()
        elif state == "searching":
            self.power_btn.setChecked(True)

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
        """Handle hardware scan button click - trigger real hardware scan."""
        # Don't scan if already scanning
        if self.sidebar.scan_btn.property("scanning"):
            return

        logger.info("[SCAN] User requested hardware scan...")
        self.sidebar.scan_btn.setProperty("scanning", True)
        self._update_scan_button_style()

        # Emit signal to trigger actual hardware scan in Application
        # The Application class will handle the actual hardware manager scan
        if hasattr(self, 'app') and self.app:
            self.app.hardware_mgr.scan_and_connect()
        else:
            logger.warning("No application reference - cannot trigger hardware scan")
            # Reset button state after 1 second
            QTimer.singleShot(1000, lambda: (
                self.sidebar.scan_btn.setProperty("scanning", False),
                self._update_scan_button_style()
            ))

    def _on_hardware_scan_complete(self):
        """Called when hardware scan completes - reset scan button."""
        self.sidebar.scan_btn.setProperty("scanning", False)
        self._update_scan_button_style()
        logger.info("[SCAN] Hardware scan complete - button reset")

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

    def update_hardware_status(self, status: dict):
        """Update hardware status display with real hardware information.

        Args:
            status: Dict with keys:
                - ctrl_type: Controller type (P4SPR, PicoP4SPR, etc.)
                - knx_type: Kinetic controller type (KNX2, etc.)
                - pump_connected: Boolean
                - spectrometer: Boolean
                - sensor_ready: Boolean
                - optics_ready: Boolean
                - fluidics_ready: Boolean
        """
        # Build list of connected devices
        devices = []

        ctrl_type = status.get('ctrl_type')
        spectrometer = status.get('spectrometer')

        # Determine device name based on what's connected
        if ctrl_type and spectrometer:
            # Both controller and spectrometer = show controller type
            devices.append(f"Device: {ctrl_type}")
        elif ctrl_type:
            # Only controller = show controller type
            devices.append(f"Device: {ctrl_type}")
        elif spectrometer:
            # Only spectrometer = show as P4SPR device
            devices.append("Device: P4SPR")

        if status.get('knx_type'):
            devices.append(f"Kinetic Controller: {status['knx_type']}")

        if status.get('pump_connected'):
            devices.append("Pump: Connected")

        # Update device labels
        for i, label in enumerate(self.sidebar.hw_device_labels):
            if i < len(devices):
                label.setText(f"• {devices[i]}")
                label.setVisible(True)
            else:
                label.setVisible(False)

        # Show/hide "no devices" message
        self.sidebar.hw_no_devices.setVisible(len(devices) == 0)

        # Update subunit readiness based on actual verification
        self._update_subunit_readiness_from_status(status)

        # Update operation mode availability based on hardware
        self._update_operation_modes(status)

    def _update_subunit_readiness_from_status(self, status: dict):
        """Update subunit readiness based on hardware verification results."""
        # Sensor readiness
        if 'sensor_ready' in status:
            self._set_subunit_status('Sensor', status['sensor_ready'])

        # Optics readiness
        if 'optics_ready' in status:
            self._set_subunit_status('Optics', status['optics_ready'])

        # Fluidics readiness
        if 'fluidics_ready' in status:
            self._set_subunit_status('Fluidics', status['fluidics_ready'])

    def _set_subunit_status(self, subunit_name: str, is_ready: bool):
        """Set the status of a specific subunit.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            is_ready: True if ready, False otherwise
        """
        if subunit_name in self.sidebar.subunit_status:
            indicator = self.sidebar.subunit_status[subunit_name]['indicator']
            status_label = self.sidebar.subunit_status[subunit_name]['status_label']

            if is_ready:
                # Green indicator and "Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"  # Green
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                # Gray indicator and "Not Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #86868B;"  # Gray
                    "background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

            from utils.logger import logger
            logger.info(f"{subunit_name}: {'Ready' if is_ready else 'Not Ready'}")

    def _update_operation_modes(self, status: dict):
        """Update available operation modes based on hardware type."""
        ctrl_type = status.get('ctrl_type', '')
        has_pump = status.get('pump_connected', False)

        from utils.logger import logger

        # P4SPR static device - only Static mode
        if ctrl_type in ['P4SPR', 'PicoP4SPR']:
            logger.info("P4SPR device detected - Static mode available")
            # Static mode always available for P4SPR
            # Flow mode only if pump is connected
            if has_pump:
                logger.info("Pump detected - Flow mode also available")
            else:
                logger.info("No pump - Flow mode disabled")

        # EZSPR or other devices
        elif ctrl_type in ['EZSPR', 'PicoEZSPR']:
            logger.info("EZSPR device detected - Static and Flow modes available")

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
        default_filename = f"AffiLabs_debug_log_{timestamp}.txt"

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
        """Toggle recording state - emit signal for Application to handle."""
        # Emit signal based on current recording state
        if not self.is_recording:
            # Request to start recording - emit signal
            if hasattr(self, 'recording_start_requested'):
                self.recording_start_requested.emit()
        else:
            # Request to stop recording - emit signal
            if hasattr(self, 'recording_stop_requested'):
                self.recording_stop_requested.emit()

    def set_recording_state(self, is_recording: bool, filename: str = ""):
        """Update recording UI state from external controller.

        Args:
            is_recording: True if recording is active
            filename: Name of the recording file (if recording)
        """
        self.is_recording = is_recording
        self.record_btn.setChecked(is_recording)

        if is_recording:
            # Update recording indicator to show active state
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #FF3B30;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            display_name = Path(filename).name if filename else "data.csv"
            self.rec_status_text.setText(f"Recording to: {display_name}")
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

    def _init_device_config(self):
        """Initialize device configuration for maintenance tracking."""
        try:
            from utils.device_configuration import DeviceConfiguration
            self.device_config = DeviceConfiguration()

            # Initialize tracking variables
            self.led_start_time = None
            self.last_powered_on = None

            # Update UI with current values
            self._update_maintenance_display()

            logger.info("Device configuration initialized for maintenance tracking")
        except Exception as e:
            logger.error(f"Failed to initialize device configuration: {e}")
            self.device_config = None

    def _update_maintenance_display(self):
        """Update the maintenance section with current values from device config."""
        if self.device_config is None:
            return

        try:
            import datetime

            # Update operation hours
            led_hours = self.device_config.config['maintenance']['led_on_hours']
            self.hours_value.setText(f"{led_hours:,.1f} hrs")

            # Update last operation date
            if self.last_powered_on:
                last_op_str = self.last_powered_on.strftime("%b %d, %Y")
                self.last_op_value.setText(last_op_str)
            else:
                self.last_op_value.setText("Never")

            # Calculate next maintenance (November of current or next year)
            now = datetime.datetime.now()
            current_year = now.year
            current_month = now.month

            # If we're past November, schedule for next year
            if current_month >= 11:
                next_maintenance_year = current_year + 1
            else:
                next_maintenance_year = current_year

            self.next_maintenance_value.setText(f"November {next_maintenance_year}")

            # Highlight if maintenance is due this month
            if current_month == 11:
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF3B30;"  # Red for urgent
                    "background: transparent;"
                    "font-weight: 700;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
            else:
                self.next_maintenance_value.setStyleSheet(
                    "font-size: 13px;"
                    "color: #FF9500;"  # Orange for scheduled
                    "background: transparent;"
                    "font-weight: 600;"
                    "margin-top: 6px;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
        except Exception as e:
            logger.error(f"Failed to update maintenance display: {e}")

    def start_led_operation_tracking(self):
        """Start tracking LED operation time (call when acquisition starts)."""
        if self.device_config is None:
            return

        import datetime
        self.led_start_time = datetime.datetime.now()
        self.last_powered_on = self.led_start_time

        logger.info("LED operation tracking started")
        self._update_maintenance_display()

    def stop_led_operation_tracking(self):
        """Stop tracking LED operation time and add elapsed time to total (call when acquisition stops)."""
        if self.device_config is None or self.led_start_time is None:
            return

        try:
            import datetime

            # Calculate elapsed time in hours
            elapsed = datetime.datetime.now() - self.led_start_time
            elapsed_hours = elapsed.total_seconds() / 3600.0

            # Add to device configuration
            self.device_config.add_led_on_time(elapsed_hours)
            self.device_config.save()

            logger.info(f"LED operation stopped. Added {elapsed_hours:.2f} hours to total")

            # Reset start time
            self.led_start_time = None

            # Update display
            self._update_maintenance_display()
        except Exception as e:
            logger.error(f"Failed to stop LED operation tracking: {e}")

    def update_last_power_on(self):
        """Update the last power-on timestamp (call when device powers on)."""
        if self.device_config is None:
            return

        import datetime
        self.last_powered_on = datetime.datetime.now()

        logger.info(f"Device powered on at {self.last_powered_on.strftime('%Y-%m-%d %H:%M:%S')}")
        self._update_maintenance_display()

    def open_full_cycle_table(self):
        """Open the full cycle data table in the Edits tab."""
        # Find the Edits tab and switch to it
        for i in range(self.sidebar.tabs.count()):
            if self.sidebar.tabs.tabText(i) == "Edits":
                self.sidebar.tabs.setCurrentIndex(i)
                break

    def add_cycle_to_queue(self):
        """Add current cycle form values to the queue."""
        if len(self.cycle_queue) >= self.max_queue_size:
            QMessageBox.warning(self, "Queue Full",
                              f"Maximum queue size ({self.max_queue_size}) reached. Start a cycle to free up space.")
            return

        # TODO: Extract values from cycle settings form widgets
        # For now, using placeholder data
        cycle_data = {
            "type": "Concentration",  # Get from cycle type combo box
            "start": "00:00:00",  # Get from start time input
            "end": "00:05:00",  # Get from end time input or calculate
            "notes": "Queue entry",  # Get from notes input
            "state": "queued"  # Initial state
        }

        self.cycle_queue.append(cycle_data)
        self._update_queue_display()

        # Disable Add to Queue if at capacity
        if len(self.cycle_queue) >= self.max_queue_size:
            self.add_to_queue_btn.setEnabled(False)

    def start_cycle(self):
        """Start next cycle from queue or use current form values."""
        if self.cycle_queue:
            # Consume first queued item
            cycle_data = self.cycle_queue.pop(0)
            cycle_data["state"] = "completed"

            # TODO: Create actual cycle/segment object here
            # For now, just update display
            print(f"Starting cycle: {cycle_data}")

            # Update queue display to show next item as ready
            self._update_queue_display()

            # Re-enable Add to Queue button
            if len(self.cycle_queue) < self.max_queue_size:
                self.add_to_queue_btn.setEnabled(True)
        else:
            # No queue items - use current form values
            # TODO: Extract form values and create cycle
            print("Starting immediate cycle from form values")

    def _update_queue_display(self):
        """Update the summary table to reflect current queue state."""
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor

        # Clear table
        for row in range(5):
            for col in range(4):
                self.summary_table.setItem(row, col, QTableWidgetItem(""))
                self.summary_table.item(row, col).setBackground(QColor(255, 255, 255))

        # Populate with queue data
        for row, cycle in enumerate(self.cycle_queue[:5]):
            state = cycle["state"]

            # State indicator with emoji
            state_text = ""
            state_color = QColor(255, 255, 255)

            if state == "queued":
                if row == 0:
                    # First item is ready to start
                    state_text = "▶️ Ready"
                    state_color = QColor(227, 242, 253)  # Light blue
                else:
                    state_text = "🟡 Queued"
                    state_color = QColor(245, 245, 245)  # Light gray
            elif state == "completed":
                state_text = "✓ Done"
                state_color = QColor(232, 245, 233)  # Light green

            # Set cell values
            state_item = QTableWidgetItem(state_text)
            state_item.setBackground(state_color)
            self.summary_table.setItem(row, 0, state_item)

            self.summary_table.setItem(row, 1, QTableWidgetItem(cycle["type"]))
            self.summary_table.setItem(row, 2, QTableWidgetItem(cycle["start"]))
            self.summary_table.setItem(row, 3, QTableWidgetItem(cycle["notes"]))

            # Apply background color to entire row
            for col in range(1, 4):
                self.summary_table.item(row, col).setBackground(state_color)

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units."""
        # This will be connected to main_simplified handler
        if checked and self.ru_btn.isChecked():
            logger.info("Unit changed to RU")
        elif checked and self.nm_btn.isChecked():
            logger.info("Unit changed to nm")

    def _connect_signals(self):
        """Connect UI signals."""
        self.sidebar.scan_btn.clicked.connect(self._handle_scan_hardware)
        self.sidebar.debug_log_btn.clicked.connect(self._handle_debug_log_download)

        # Connect cycle management buttons
        self.sidebar.start_cycle_btn.clicked.connect(self.start_cycle)
        self.sidebar.add_to_queue_btn.clicked.connect(self.add_cycle_to_queue)
        self.sidebar.open_table_btn.clicked.connect(self.open_full_cycle_table)

        # Install element inspector for right-click inspection
        ElementInspector.install_inspector(self)


# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindowPrototype()
    window.show()
    sys.exit(app.exec())


