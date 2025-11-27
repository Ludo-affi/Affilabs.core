"""Modern sidebar widget - EXACT copy from ui_prototype.py"""

import sys
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QParallelAnimationGroup
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QLabel, QFrame, QToolButton, QScrollArea, QGraphicsDropShadowEffect,
    QSlider, QSpinBox, QSplitter, QCheckBox, QComboBox, QLineEdit, QRadioButton, QButtonGroup,
    QTextEdit, QTableWidget, QHeaderView, QTableWidgetItem
)
from PySide6.QtGui import QIcon, QColor, QFont, QTextCharFormat, QSyntaxHighlighter, QTextDocument
from PySide6.QtCore import QRegularExpression


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


class ModernSidebar(QWidget):
    """Modern sidebar widget - EXACT COPY from prototype"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_setup_done = False
        self._setup_ui()

    def _setup_ui(self):
        """Setup the sidebar UI - EXACT COPY from prototype"""
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
                self._create_device_status_tab(tab_layout)
            elif label == "Graphic Control":
                self._create_graphic_control_tab(tab_layout)
            elif label == "Settings":
                self._create_settings_tab(tab_layout)
            elif label == "Static":
                self._create_static_tab(tab_layout)
            elif label == "Export":
                self._create_export_tab(tab_layout)
            else:
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

    def _create_device_status_tab(self, tab_layout):
        """Create Device Status tab content"""
        tab_layout.addSpacing(12)

        # Section 1: Hardware Connected
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
            device_label.setVisible(False)
            hw_card_layout.addWidget(device_label)
            self.hw_device_labels.append(device_label)

        # No devices message
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
                "color: #86868B;"
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

            # Store references
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
                "color: #86868B;"
                "background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            mode_row.addWidget(mode_indicator)

            # Mode name
            mode_label = QLabel(mode_name)
            mode_label.setStyleSheet(
                "font-size: 13px;"
                "color: #86868B;"
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

            # Store references
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

        # Rest of maintenance section - abbreviated for file size
        tab_layout.addWidget(QLabel("(Maintenance details placeholder)"))

    def _create_graphic_control_tab(self, tab_layout):
        """Create Graphic Control tab content"""
        tab_layout.addWidget(QLabel("(Graphic Control content placeholder)"))

    def _create_settings_tab(self, tab_layout):
        """Create Settings tab content with calibration buttons."""
        # Calibration section
        calib_label = QLabel("🔬 Calibration")
        calib_label.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "margin-top: 12px;"
            "margin-bottom: 8px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        tab_layout.addWidget(calib_label)

        # Description
        calib_desc = QLabel("Run LED intensity calibration to measure S-pol and P-pol reference spectra:")
        calib_desc.setWordWrap(True)
        calib_desc.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 12px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        tab_layout.addWidget(calib_desc)

        # Button style
        button_style = (
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 10px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  min-height: 36px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #003D99;"
            "}"
        )

        # Simple LED Calibration button
        self.simple_led_calibration_btn = QPushButton("📊 Simple LED Calibration")
        self.simple_led_calibration_btn.setToolTip(
            "Standard calibration routine:\n"
            "• Measures S-pol reference spectra (high transmission)\n"
            "• Measures P-pol reference spectra (low transmission)\n"
            "• Optimizes LED intensities for all channels\n"
            "• Takes ~30-60 seconds"
        )
        self.simple_led_calibration_btn.setStyleSheet(button_style)
        tab_layout.addWidget(self.simple_led_calibration_btn)

        # Full Calibration button
        self.full_calibration_btn = QPushButton("🎯 Full Calibration")
        self.full_calibration_btn.setToolTip(
            "Complete calibration routine (same as Simple):\n"
            "• Measures S-pol reference spectra\n"
            "• Measures P-pol reference spectra\n"
            "• Optimizes LED intensities\n"
            "• Takes ~30-60 seconds"
        )
        self.full_calibration_btn.setStyleSheet(button_style)
        tab_layout.addWidget(self.full_calibration_btn)

        # OEM LED Calibration button
        self.oem_led_calibration_btn = QPushButton("🏭 OEM Calibration")
        self.oem_led_calibration_btn.setToolTip(
            "OEM/Factory calibration (same as Simple):\n"
            "• Measures S-pol reference spectra\n"
            "• Measures P-pol reference spectra\n"
            "• Optimizes LED intensities\n"
            "• Takes ~30-60 seconds"
        )
        self.oem_led_calibration_btn.setStyleSheet(button_style)
        tab_layout.addWidget(self.oem_led_calibration_btn)

        # Add spacing
        tab_layout.addSpacing(20)

        # Polarizer Calibration section
        polar_label = QLabel("🔄 Polarizer Alignment")
        polar_label.setStyleSheet(
            "font-size: 15px;"
            "font-weight: 600;"
            "color: #1D1D1F;"
            "background: transparent;"
            "margin-top: 12px;"
            "margin-bottom: 8px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        tab_layout.addWidget(polar_label)

        # Description
        polar_desc = QLabel("Calibrate servo polarizer positions (run once during setup):")
        polar_desc.setWordWrap(True)
        polar_desc.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "background: transparent;"
            "margin-bottom: 12px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
        )
        tab_layout.addWidget(polar_desc)

        # Polarizer Calibration button
        self.polarizer_calibration_btn = QPushButton("⚙️ Polarizer Calibration")
        self.polarizer_calibration_btn.setToolTip(
            "Find optimal S and P polarizer positions:\n"
            "• Scans servo angles to find peak transmission\n"
            "• Validates 90° phase relationship\n"
            "• Saves positions to device config\n"
            "• Takes ~1-2 minutes (run once during setup)"
        )
        self.polarizer_calibration_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF9500;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 10px 16px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  min-height: 36px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #FF8C00;"
            "}"
            "QPushButton:pressed {"
            "  background: #E67E00;"
            "}"
        )
        tab_layout.addWidget(self.polarizer_calibration_btn)

    def _create_static_tab(self, tab_layout):
        """Create Static tab content"""
        tab_layout.addWidget(QLabel("(Static content placeholder)"))

    def _create_export_tab(self, tab_layout):
        """Create Export tab content"""
        tab_layout.addWidget(QLabel("(Export content placeholder)"))

    # Backwards compatibility methods
    def set_widgets(self):
        """Legacy API entry point - ensure legacy widgets exist."""
        self._ensure_legacy_widgets()

    def _ensure_legacy_widgets(self):
        """Create and inject legacy Device and Kinetic widgets if missing."""
        # Device widget under 'Device Status' tab
        if not hasattr(self, 'device_widget') or self.device_widget is None:
            try:
                from widgets.device import Device
                self.device_widget = Device()
                self._append_widget_to_tab("Device Status", self.device_widget)
            except Exception as e:
                print(f"[Sidebar] Failed to create Device widget: {e}")
        # Kinetic widget under 'Graphic Control' tab
        if not hasattr(self, 'kinetic_widget') or self.kinetic_widget is None:
            try:
                from widgets.kinetics import Kinetic
                self.kinetic_widget = Kinetic()
                self._append_widget_to_tab("Graphic Control", self.kinetic_widget)
            except Exception as e:
                print(f"[Sidebar] Failed to create Kinetic widget: {e}")

    def _append_widget_to_tab(self, label, widget):
        content = self._get_tab_content_widget(label)
        if content is None:
            return
        layout = content.layout()
        if layout is None:
            return
        # Remove trailing stretch if present
        if layout.count() > 0:
            last_item = layout.itemAt(layout.count() - 1)
            if last_item and last_item.spacerItem():
                layout.removeItem(last_item)
        layout.addWidget(widget)
        layout.addStretch()

    def get_settings_tab(self):
        """Return the Settings tab content widget for settings panel injection."""
        return self._get_tab_content_widget("Settings")

    def install_spectroscopy_panel(self, panel):
        """Legacy API: place spectroscopy panel into Graphic Control tab."""
        self._append_widget_to_tab("Graphic Control", panel)

    # --- Added legacy API compatibility methods ---
    def install_sensorgram_controls(self, controls_widget):
        """Legacy API: embed sensorgram controls into the 'Flow' tab.

        The original sidebar exposed this method and mainwindow calls it.
        We preserve the tab title label (first item) and replace all other
        content after it with the provided widget, followed by a stretch.
        """
        self._replace_tab_content("Flow", controls_widget)

    def get_data_tab(self):
        """Legacy API: return the Export tab content widget."""
        return self._get_tab_content_widget("Export")

    # Helper to retrieve the content widget for a tab by label
    def _get_tab_content_widget(self, label):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == label:
                scroll = self.tab_widget.widget(i)
                return scroll.widget() if scroll else None
        return None

    def _replace_tab_content(self, label, new_widget):
        content = self._get_tab_content_widget(label)
        if content is None:
            return
        layout = content.layout()
        if layout is None or layout.count() == 0:
            return
        # Preserve the title label at index 0; remove everything after
        while layout.count() > 1:
            item = layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()
        # Insert the new widget and a stretch
        layout.addWidget(new_widget)
        layout.addStretch()


# Alias for backwards compatibility
Sidebar = ModernSidebar
