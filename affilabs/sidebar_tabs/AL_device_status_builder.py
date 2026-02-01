"""Device Status Tab Builder for AffiLabs.core Sidebar

Builds the Device Status tab showing:
- Hardware connection status
- Subunit readiness indicators
- Operation modes availability
- Maintenance information
- Debug log download

Extracted from sidebar.py to improve modularity.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import (
    Colors,
    Fonts,
    card_style,
    label_style,
    primary_button_style,
)
from affilabs.services.diagnostic_uploader import DiagnosticUploader


class DeviceStatusTabBuilder:
    """Builds the Device Status tab content."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build Device Status tab with hardware and subunit indicators.

        Args:
            tab_layout: QVBoxLayout to add widgets to

        """
        # Section 1: Hardware Connected
        hw_section = QLabel("HARDWARE CONNECTED")
        hw_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};",
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
        self.sidebar.hw_device_labels = []
        for i in range(3):
            device_label = QLabel(f"• Device {i+1}: Not connected")
            device_label.setStyleSheet(
                label_style(13, Colors.SUCCESS) + "padding: 4px 0px;",
            )
            device_label.setVisible(False)
            hw_card_layout.addWidget(device_label)
            self.sidebar.hw_device_labels.append(device_label)

        self.sidebar.hw_no_devices = QLabel("No hardware detected")
        self.sidebar.hw_no_devices.setStyleSheet(
            label_style(13, Colors.SECONDARY_TEXT)
            + "padding: 8px 0px;font-style: italic;",
        )
        hw_card_layout.addWidget(self.sidebar.hw_no_devices)

        hw_card_layout.addSpacing(4)

        self.sidebar.scan_btn = QPushButton("[SEARCH] Scan for Hardware")
        self.sidebar.scan_btn.setProperty("scanning", False)
        self.sidebar.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.scan_btn.setFixedHeight(36)
        self.sidebar.scan_btn.setVisible(False)  # Hidden until hardware connected
        self.sidebar.scan_btn.setStyleSheet(primary_button_style())
        self.sidebar.scan_btn.setToolTip(
            "Search for connected hardware devices (optics, sensors, pumps)",
        )
        hw_card_layout.addWidget(self.sidebar.scan_btn)

        # Add Hardware button (for peripherals only)
        self.sidebar.add_hardware_btn = QPushButton("🔌 Add Hardware")
        self.sidebar.add_hardware_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.add_hardware_btn.setFixedHeight(36)
        self.sidebar.add_hardware_btn.setVisible(False)  # Hidden until core module connected
        self.sidebar.add_hardware_btn.setStyleSheet("""
            QPushButton {
                background: #5856D6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: #4745B0;
            }
            QPushButton:pressed {
                background: #3634A3;
            }
            QPushButton:disabled {
                background: #E5E5EA;
                color: #86868B;
            }
        """)
        self.sidebar.add_hardware_btn.setToolTip(
            "Scan for peripheral devices (Affipump, etc.) when core module is connected",
        )
        hw_card_layout.addWidget(self.sidebar.add_hardware_btn)

        tab_layout.addWidget(hw_card)
        tab_layout.addSpacing(16)

        # Section 2: Subunit Readiness
        self._build_subunit_readiness(tab_layout)

        # Section 3: Operation Modes
        self._build_operation_modes(tab_layout)

        # Section 4: Maintenance
        self._build_maintenance_section(tab_layout)

        tab_layout.addStretch()

    def _build_subunit_readiness(self, tab_layout: QVBoxLayout):
        """Build subunit readiness indicators."""
        subunit_section = QLabel("SUBUNIT READINESS")
        subunit_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};",
        )
        subunit_section.setToolTip(
            "Initialization status of critical system components",
        )
        tab_layout.addWidget(subunit_section)
        tab_layout.addSpacing(8)

        subunit_card = QFrame()
        subunit_card.setStyleSheet(card_style())
        subunit_card_layout = QVBoxLayout(subunit_card)
        subunit_card_layout.setContentsMargins(12, 10, 12, 10)
        subunit_card_layout.setSpacing(8)

        self.sidebar.subunit_status = {}
        subunit_names = ["Sensor", "Optics", "Fluidics"]

        for i, subunit_name in enumerate(subunit_names):
            subunit_row = QHBoxLayout()
            subunit_row.setSpacing(10)
            subunit_row.setContentsMargins(0, 0, 0, 0)

            # Status indicator
            status_indicator = QLabel("●")
            status_indicator.setFixedWidth(12)
            status_indicator.setStyleSheet(
                f"font-size: 14px; color: {Colors.SECONDARY_TEXT}; background: transparent;",
            )
            subunit_row.addWidget(status_indicator)

            # Subunit name
            name_label = QLabel(subunit_name)
            name_label.setStyleSheet(
                label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 500;",
            )
            subunit_row.addWidget(name_label)

            subunit_row.addStretch()

            # Status text
            status_label = QLabel("Not Ready")
            status_label.setStyleSheet(label_style(12, Colors.SECONDARY_TEXT))
            subunit_row.addWidget(status_label)

            # Create container widget for the row
            subunit_container = QWidget()
            subunit_container.setLayout(subunit_row)
            subunit_card_layout.addWidget(subunit_container)

            # Store references including the container for visibility control
            self.sidebar.subunit_status[subunit_name] = {
                "indicator": status_indicator,
                "status_label": status_label,
                "container": subunit_container,
            }

            # Add separator between items (not after last)
            if i < len(subunit_names) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setStyleSheet(
                    "background: rgba(0, 0, 0, 0.06); max-height: 1px; margin: 4px 0px;",
                )
                subunit_card_layout.addWidget(separator)

        tab_layout.addWidget(subunit_card)
        tab_layout.addSpacing(16)

    def _build_operation_modes(self, tab_layout: QVBoxLayout):
        """Build operation modes section."""
        modes_section = QLabel("OPERATION MODES")
        modes_section.setStyleSheet(
            f"font-size: 11px;"
            f"font-weight: 700;"
            f"color: {Colors.SECONDARY_TEXT};"
            f"background: transparent;"
            f"letter-spacing: 0.5px;"
            f"margin-left: 4px;"
            f"font-family: {Fonts.SYSTEM};",
        )
        modes_section.setToolTip(
            "Available operation modes based on installed hardware",
        )
        tab_layout.addWidget(modes_section)
        tab_layout.addSpacing(8)

        modes_card = QFrame()
        modes_card.setStyleSheet(card_style())
        modes_card_layout = QVBoxLayout(modes_card)
        modes_card_layout.setContentsMargins(12, 12, 12, 12)
        modes_card_layout.setSpacing(8)

        self.sidebar.operation_modes = {}
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
            self.sidebar.operation_modes[mode_name] = {
                "indicator": indicator,
                "label": label,
                "status_label": status_label,
            }

        tab_layout.addWidget(modes_card)
        tab_layout.addSpacing(16)

    def _build_maintenance_section(self, tab_layout: QVBoxLayout):
        """Build maintenance information section."""
        # Section 4: Maintenance
        maint_section = QLabel("Maintenance")
        maint_section.setStyleSheet(
            label_style(15, Colors.PRIMARY_TEXT) + "font-weight: 600; margin-top: 8px;",
        )
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
        self.sidebar.hours_value = QLabel("1,247 hrs")
        self.sidebar.hours_value.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        hours_row.addWidget(hours_label)
        hours_row.addWidget(self.sidebar.hours_value)
        hours_row.addStretch()
        stats_layout.addLayout(hours_row)

        # Last Operation
        last_op_row = QHBoxLayout()
        last_op_row.setSpacing(8)
        last_op_label = QLabel("Last Operation:")
        last_op_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        last_op_label.setToolTip("Date of most recent experiment or measurement")
        self.sidebar.last_op_value = QLabel("Nov 19, 2025")
        self.sidebar.last_op_value.setStyleSheet(
            label_style(13, Colors.PRIMARY_TEXT) + "font-weight: 600;",
        )
        last_op_row.addWidget(last_op_label)
        last_op_row.addWidget(self.sidebar.last_op_value)
        last_op_row.addStretch()
        stats_layout.addLayout(last_op_row)

        # Annual Maintenance
        upcoming_row = QHBoxLayout()
        upcoming_row.setSpacing(8)
        upcoming_label = QLabel("Annual Maintenance:")
        upcoming_label.setStyleSheet(
            label_style(13, Colors.SECONDARY_TEXT) + "margin-top: 6px;",
        )
        upcoming_label.setToolTip(
            "Scheduled date for next annual service and calibration",
        )
        self.sidebar.next_maintenance_value = QLabel("November 2025")
        self.sidebar.next_maintenance_value.setStyleSheet(
            label_style(13, "#FF9500") + "font-weight: 600; margin-top: 6px;",
        )
        upcoming_row.addWidget(upcoming_label)
        upcoming_row.addWidget(self.sidebar.next_maintenance_value)
        upcoming_row.addStretch()
        stats_layout.addLayout(upcoming_row)

        tab_layout.addWidget(stats_card)
        tab_layout.addSpacing(12)

        # Debug Log Download Button
        debug_btn_container = QFrame()
        debug_btn_container.setStyleSheet(card_style())
        debug_btn_layout = QVBoxLayout(debug_btn_container)
        debug_btn_layout.setContentsMargins(12, 10, 12, 10)

        self.sidebar.debug_log_btn = QPushButton("📥 Download Debug Log")
        self.sidebar.debug_log_btn.setFixedHeight(36)
        self.sidebar.debug_log_btn.setStyleSheet(primary_button_style())
        self.sidebar.debug_log_btn.setToolTip(
            "Export system logs for troubleshooting and technical support",
        )
        debug_btn_layout.addWidget(self.sidebar.debug_log_btn)
        tab_layout.addWidget(debug_btn_container)

        tab_layout.addSpacing(8)

        # Send Diagnostic Files Button
        diagnostic_btn_container = QFrame()
        diagnostic_btn_container.setStyleSheet(card_style())
        diagnostic_btn_layout = QVBoxLayout(diagnostic_btn_container)
        diagnostic_btn_layout.setContentsMargins(12, 10, 12, 10)

        self.sidebar.send_diagnostics_btn = QPushButton("📤 Send Diagnostic Files to AffiLabs")
        self.sidebar.send_diagnostics_btn.setFixedHeight(36)
        self.sidebar.send_diagnostics_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF; "
            "  color: white; "
            "  border: none; "
            "  border-radius: 6px; "
            "  font-size: 13px; "
            "  font-weight: 600; "
            "  padding: 0px 16px;"
            "}"
            "QPushButton:hover { background: #0051D5; }"
            "QPushButton:pressed { background: #003D99; }"
        )
        self.sidebar.send_diagnostics_btn.setToolTip(
            "Upload diagnostic bundle (Spark transcripts, calibration files, debug logs) to AffiLabs OEM database",
        )
        self.sidebar.send_diagnostics_btn.clicked.connect(self._handle_send_diagnostics)
        diagnostic_btn_layout.addWidget(self.sidebar.send_diagnostics_btn)
        tab_layout.addWidget(diagnostic_btn_container)

        tab_layout.addSpacing(16)

        # Software Version
        from version import __version__
        version_label = QLabel(__version__)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT) + "font-weight: 500;",
        )
        tab_layout.addWidget(version_label)

    def _handle_send_diagnostics(self):
        """Handle Send Diagnostic Files button click."""
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        
        # Confirm upload
        reply = QMessageBox.question(
            self.sidebar,
            "Report Issue & Send Diagnostics",
            "This will:\n\n"
            "1. Sync Spark AI data to cloud (backup)\n"
            "2. Upload diagnostic files to SharePoint\n"
            "3. Open ticket form in your browser\n\n"
            "Files included:\n"
            "• Spark AI conversation transcripts\n"
            "• Calibration files and logs\n"
            "• Debug logs\n"
            "• System information\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Optional: ask for email
        email, ok = QInputDialog.getText(
            self.sidebar,
            "Your Email (Optional)",
            "Email address (for ticket updates and follow-up):",
        )
        
        # Show progress
        progress = QMessageBox(self.sidebar)
        progress.setWindowTitle("Uploading Diagnostics")
        progress.setText("Syncing database to cloud...\nCollecting diagnostic files...\nThis may take a moment...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        
        # Process events to show dialog
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Upload and open form
        uploader = DiagnosticUploader()
        success, message = uploader.send_diagnostics_and_open_form(
            user_email=email if email else None
        )
        
        progress.close()
        
        # Show result
        if success:
            QMessageBox.information(
                self.sidebar,
                "Diagnostics Uploaded",
                message + "\n\n"
                "Please complete the ticket form that opened in your browser.\n\n"
                "Your Spark AI data has been backed up to the cloud.\n\n"
                "We'll respond to your ticket within 24 hours!"
            )
        else:
            QMessageBox.warning(
                self.sidebar,
                "Upload Issue",
                message + "\n\n"
                "You can manually send the diagnostic bundle to:\n"
                "support@affinitylabs.com"
            )
