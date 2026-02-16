"""Device Status Tab Builder for AffiLabs.core Sidebar

Builds the Device Status tab as an instrument-style dashboard with LED bar
indicators that light up to show system readiness at a glance.

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
)
from affilabs.services.diagnostic_uploader import DiagnosticUploader

# ── LED colour constants ──────────────────────────────────────────────
_LED_GREEN = "#34C759"
_LED_GREEN_GLOW = "rgba(52, 199, 89, 0.25)"
_LED_AMBER = "#FF9500"
_LED_AMBER_GLOW = "rgba(255, 149, 0, 0.25)"
_LED_RED = "#FF3B30"
_LED_RED_GLOW = "rgba(255, 59, 48, 0.25)"
_LED_OFF = "#D1D1D6"          # soft gray bar when inactive
_LED_OFF_GLOW = "transparent"


def _led_bar_style(color: str, glow: str, height: int = 3) -> str:
    """Return stylesheet for a thin LED bar that glows."""
    return (
        f"background: {color};"
        f"border: 1px solid {glow};"
        f"border-radius: 1px;"
        f"min-height: {height}px;"
        f"max-height: {height}px;"
    )


def _led_dot_style(color: str, glow: str, size: int = 8) -> str:
    """Return stylesheet for a circular LED dot that glows."""
    return (
        f"background: {color};"
        f"border: 2px solid {glow};"
        f"border-radius: {(size + 4) // 2}px;"
        f"min-width: {size}px; max-width: {size}px;"
        f"min-height: {size}px; max-height: {size}px;"
    )


class DeviceStatusTabBuilder:
    """Builds the Device Status tab as an instrument-panel dashboard."""

    def __init__(self, sidebar):
        """Initialize builder.

        Args:
            sidebar: Reference to parent AffilabsSidebar instance

        """
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        """Build Device Status tab as a unified dark instrument panel.

        All indicators live on one surface — no cards-in-cards.
        LED bars light up green/amber/red to show readiness.

        Args:
            tab_layout: QVBoxLayout to add widgets to

        """
        # ── Content flows directly into the sidebar tab ───────────────
        # No wrapper panel — everything blends with the sidebar background.

        # ── 1. Hardware connection row ────────────────────────────────
        self._build_hardware_section(tab_layout)

        tab_layout.addSpacing(20)

        # ── 2. System components — LED bars ───────────────────────────
        self._build_components_section(tab_layout)

        tab_layout.addSpacing(20)

        # ── 3. Operation modes — inline indicators ────────────────────
        self._build_modes_section(tab_layout)

        tab_layout.addSpacing(20)

        # ── 4. Maintenance stats — compact row ────────────────────────
        self._build_maintenance_section(tab_layout)

        tab_layout.addSpacing(20)

        # ── 5. Actions + version ──────────────────────────────────────
        self._build_actions_section(tab_layout)

        tab_layout.addStretch()

    # ── Hardware ──────────────────────────────────────────────────────
    def _build_hardware_section(self, layout: QVBoxLayout):
        # Connection LED bar (full width, glows green when connected)
        self.sidebar.hw_led_bar = QFrame()
        self.sidebar.hw_led_bar.setStyleSheet(_led_bar_style(_LED_OFF, _LED_OFF_GLOW))
        layout.addWidget(self.sidebar.hw_led_bar)
        layout.addSpacing(10)

        # Status line: icon + text
        hw_row = QHBoxLayout()
        hw_row.setContentsMargins(0, 0, 0, 0)
        hw_row.setSpacing(8)

        hw_dot = QLabel()
        hw_dot.setFixedSize(8, 8)
        hw_dot.setStyleSheet(_led_dot_style(_LED_OFF, _LED_OFF_GLOW))
        hw_row.addWidget(hw_dot)
        self.sidebar._hw_dot = hw_dot

        hw_label = QLabel("HARDWARE")
        hw_label.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-size: 12px; font-weight: 700;"
            f"letter-spacing: 0.5px; background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        hw_row.addWidget(hw_label)
        hw_row.addStretch()

        hw_status_text = QLabel("No connection")
        hw_status_text.setStyleSheet(
            f"color: {Colors.SECONDARY_TEXT}; font-size: 12px; font-weight: 500;"
            f"background: transparent; font-family: {Fonts.SYSTEM};"
        )
        hw_row.addWidget(hw_status_text)
        self.sidebar._hw_status_text = hw_status_text

        layout.addLayout(hw_row)

        # Device labels (hidden until devices found)
        self.sidebar.hw_device_labels = []
        for i in range(3):
            device_label = QLabel(f"  ╰ Device {i+1}")
            device_label.setStyleSheet(
                f"font-size: 11px; color: {_LED_GREEN};"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
                f"padding: 2px 0px 0px 16px;"
            )
            device_label.setVisible(False)
            layout.addWidget(device_label)
            self.sidebar.hw_device_labels.append(device_label)

        self.sidebar.hw_no_devices = QLabel("  ⚠  No hardware detected")
        self.sidebar.hw_no_devices.setStyleSheet(
            f"font-size: 11px; color: {_LED_AMBER};"
            f"background: transparent; font-family: {Fonts.SYSTEM};"
            f"padding: 4px 0px 0px 8px;"
        )
        layout.addWidget(self.sidebar.hw_no_devices)

        # Buttons (hidden until needed)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.setSpacing(6)

        self.sidebar.scan_btn = QPushButton("Scan")
        self.sidebar.scan_btn.setProperty("scanning", False)
        self.sidebar.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.scan_btn.setFixedHeight(26)
        self.sidebar.scan_btn.setVisible(False)
        self.sidebar.scan_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {Colors.BUTTON_PRIMARY}; color: white;"
            f"  border: none;"
            f"  border-radius: 6px; padding: 4px 14px;"
            f"  font-size: 11px; font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.BUTTON_PRIMARY_HOVER}; }}"
        )
        btn_row.addWidget(self.sidebar.scan_btn)

        self.sidebar.add_hardware_btn = QPushButton("+ Add Hardware")
        self.sidebar.add_hardware_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.add_hardware_btn.setFixedHeight(26)
        self.sidebar.add_hardware_btn.setVisible(False)
        self.sidebar.add_hardware_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #5856D6; color: white;"
            f"  border: none; border-radius: 6px;"
            f"  padding: 4px 14px; font-size: 11px; font-weight: 600;"
            f"  font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #4745B0; }}"
        )
        btn_row.addWidget(self.sidebar.add_hardware_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── System Components (LED bars) ──────────────────────────────────
    def _build_components_section(self, layout: QVBoxLayout):
        section_label = QLabel("SYSTEM")
        section_label.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-size: 12px; font-weight: 700;"
            f"letter-spacing: 0.5px; background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        layout.addWidget(section_label)
        layout.addSpacing(10)

        self.sidebar.subunit_status = {}
        subunit_info = [("Sensor", "🔬"), ("Optics", "💡"), ("Fluidics", "💧")]

        for subunit_name, icon in subunit_info:
            # Row: LED bar + icon + name + status text
            row_layout = QVBoxLayout()
            row_layout.setSpacing(4)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # LED bar — lights up when ready
            led_bar = QFrame()
            led_bar.setStyleSheet(_led_bar_style(_LED_OFF, _LED_OFF_GLOW))
            row_layout.addWidget(led_bar)

            # Info row below the LED bar
            info_row = QHBoxLayout()
            info_row.setSpacing(6)
            info_row.setContentsMargins(0, 0, 0, 0)

            # Status dot (compatibility: indicator)
            status_indicator = QLabel()
            status_indicator.setFixedSize(8, 8)
            status_indicator.setStyleSheet(_led_dot_style(_LED_OFF, _LED_OFF_GLOW))
            info_row.addWidget(status_indicator)

            name_label = QLabel(f"{icon} {subunit_name}")
            name_label.setStyleSheet(
                f"font-size: 13px; color: {Colors.PRIMARY_TEXT}; font-weight: 500;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            info_row.addWidget(name_label)
            info_row.addStretch()

            status_label = QLabel("Idle")
            status_label.setStyleSheet(
                f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-weight: 600;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            info_row.addWidget(status_label)

            row_layout.addLayout(info_row)

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            container.setLayout(row_layout)
            layout.addWidget(container)
            layout.addSpacing(6)

            self.sidebar.subunit_status[subunit_name] = {
                "indicator": status_indicator,
                "status_label": status_label,
                "led_bar": led_bar,
                "container": container,
            }

    # ── Operation Modes ───────────────────────────────────────────────
    def _build_modes_section(self, layout: QVBoxLayout):
        section_label = QLabel("MODES")
        section_label.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-size: 12px; font-weight: 700;"
            f"letter-spacing: 0.5px; background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        layout.addWidget(section_label)
        layout.addSpacing(10)

        # Both modes in one horizontal row
        modes_row = QHBoxLayout()
        modes_row.setSpacing(16)
        modes_row.setContentsMargins(0, 0, 0, 0)

        self.sidebar.operation_modes = {}
        mode_info = [("static", "Static", "🧪"), ("flow", "Flow", "🌊")]

        for mode_name, mode_label, icon in mode_info:
            # Each mode: vertical mini-card (LED bar on top, dot+label below)
            mode_widget = QVBoxLayout()
            mode_widget.setSpacing(4)
            mode_widget.setContentsMargins(0, 0, 0, 0)

            led_bar = QFrame()
            led_bar.setStyleSheet(_led_bar_style(_LED_OFF, _LED_OFF_GLOW))
            mode_widget.addWidget(led_bar)

            info_row = QHBoxLayout()
            info_row.setSpacing(6)

            indicator = QLabel()
            indicator.setFixedSize(8, 8)
            indicator.setStyleSheet(_led_dot_style(_LED_OFF, _LED_OFF_GLOW))
            info_row.addWidget(indicator)

            label = QLabel(f"{icon} {mode_label}")
            label.setStyleSheet(
                f"font-size: 13px; color: {Colors.PRIMARY_TEXT}; font-weight: 500;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            info_row.addWidget(label)
            info_row.addStretch()

            status_label = QLabel("Off")
            status_label.setStyleSheet(
                f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-weight: 600;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            info_row.addWidget(status_label)

            mode_widget.addLayout(info_row)
            modes_row.addLayout(mode_widget)

            self.sidebar.operation_modes[mode_name] = {
                "indicator": indicator,
                "label": label,
                "status_label": status_label,
                "led_bar": led_bar,
            }

        layout.addLayout(modes_row)

    # ── Maintenance (compact stats) ───────────────────────────────────
    def _build_maintenance_section(self, layout: QVBoxLayout):
        section_label = QLabel("MAINTENANCE")
        section_label.setStyleSheet(
            f"color: {Colors.PRIMARY_TEXT}; font-size: 12px; font-weight: 700;"
            f"letter-spacing: 0.5px; background: transparent;"
            f"font-family: {Fonts.SYSTEM};"
        )
        layout.addWidget(section_label)
        layout.addSpacing(8)

        # Row 1: Hours, Experiments, Users
        stats_row1 = QHBoxLayout()
        stats_row1.setSpacing(0)
        stats_row1.setContentsMargins(0, 0, 0, 0)

        row1_stats = [
            ("⏱", "Hours", "hours_value", "0.0", Colors.PRIMARY_TEXT),
            ("🧪", "Experiments", "experiments_value", "0", Colors.PRIMARY_TEXT),
            ("👤", "Users", "users_count_value", "0", Colors.PRIMARY_TEXT),
        ]

        for i, (icon, title, attr_name, value_text, value_color) in enumerate(row1_stats):
            stat_col = QVBoxLayout()
            stat_col.setSpacing(2)
            stat_col.setContentsMargins(0, 0, 0, 0)

            val = QLabel(f"{icon} {value_text}")
            val.setStyleSheet(
                f"font-size: 13px; color: {value_color}; font-weight: 600;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            val.setAlignment(Qt.AlignmentFlag.AlignLeft)
            stat_col.addWidget(val)

            lbl = QLabel(title)
            lbl.setStyleSheet(
                f"font-size: 10px; color: {Colors.SECONDARY_TEXT}; font-weight: 500;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
                f"letter-spacing: 0.3px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            stat_col.addWidget(lbl)

            setattr(self.sidebar, attr_name, val)
            stats_row1.addLayout(stat_col)

            if i < len(row1_stats) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: rgba(0, 0, 0, 0.08); min-height: 24px;")
                stats_row1.addWidget(sep)

        layout.addLayout(stats_row1)
        layout.addSpacing(8)

        # Row 2: Last Run, Service
        stats_row2 = QHBoxLayout()
        stats_row2.setSpacing(0)
        stats_row2.setContentsMargins(0, 0, 0, 0)

        row2_stats = [
            ("📅", "Last Run", "last_op_value", "Never", Colors.PRIMARY_TEXT),
            ("⚠", "Service", "next_maintenance_value", "—", _LED_AMBER),
        ]

        for i, (icon, title, attr_name, value_text, value_color) in enumerate(row2_stats):
            stat_col = QVBoxLayout()
            stat_col.setSpacing(2)
            stat_col.setContentsMargins(0, 0, 0, 0)

            val = QLabel(f"{icon} {value_text}")
            val.setStyleSheet(
                f"font-size: 13px; color: {value_color}; font-weight: 600;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
            )
            val.setAlignment(Qt.AlignmentFlag.AlignLeft)
            stat_col.addWidget(val)

            lbl = QLabel(title)
            lbl.setStyleSheet(
                f"font-size: 10px; color: {Colors.SECONDARY_TEXT}; font-weight: 500;"
                f"background: transparent; font-family: {Fonts.SYSTEM};"
                f"letter-spacing: 0.3px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            stat_col.addWidget(lbl)

            setattr(self.sidebar, attr_name, val)
            stats_row2.addLayout(stat_col)

            if i < len(row2_stats) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: rgba(0, 0, 0, 0.08); min-height: 24px;")
                stats_row2.addWidget(sep)

        layout.addLayout(stats_row2)

    # ── Actions + Version ─────────────────────────────────────────────
    def _build_actions_section(self, layout: QVBoxLayout):
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self.sidebar.debug_log_btn = QPushButton("Debug Log")
        self.sidebar.debug_log_btn.setFixedHeight(28)
        self.sidebar.debug_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.debug_log_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {Colors.BUTTON_PRIMARY}; color: white;"
            f"  border: none;"
            f"  border-radius: 6px; font-size: 11px; font-weight: 600;"
            f"  padding: 4px 10px; font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: {Colors.BUTTON_PRIMARY_HOVER}; }}"
        )
        btn_row.addWidget(self.sidebar.debug_log_btn)

        self.sidebar.send_diagnostics_btn = QPushButton("Diagnostics")
        self.sidebar.send_diagnostics_btn.setFixedHeight(28)
        self.sidebar.send_diagnostics_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar.send_diagnostics_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: #007AFF; color: white;"
            f"  border: none; border-radius: 6px;"
            f"  font-size: 11px; font-weight: 600;"
            f"  padding: 4px 10px; font-family: {Fonts.SYSTEM};"
            f"}}"
            f"QPushButton:hover {{ background: #0051D5; }}"
        )
        self.sidebar.send_diagnostics_btn.clicked.connect(self._handle_send_diagnostics)
        btn_row.addWidget(self.sidebar.send_diagnostics_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Version label — explicit and clear
        layout.addSpacing(12)
        from version import __version__
        ver = QLabel(f"Affilabs.core v{__version__}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; background: transparent;"
            f"font-weight: 500; font-family: {Fonts.SYSTEM};"
        )
        layout.addWidget(ver)

    # ── Helpers ───────────────────────────────────────────────────────
    def _add_separator(self, layout: QVBoxLayout):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.06);")
        layout.addWidget(sep)

    def _handle_send_diagnostics(self):
        """Handle Send Diagnostic Files button click - creates local bundle for email."""
        import logging
        import os
        from PySide6.QtWidgets import QMessageBox

        logger = logging.getLogger(__name__)
        logger.info("[DIAGNOSTIC BUTTON] Button clicked, starting handler...")

        # Confirm bundle creation
        logger.info("[DIAGNOSTIC BUTTON] Showing confirmation dialog...")
        reply = QMessageBox.question(
            self.sidebar,
            "Create Diagnostic Bundle",
            "This will create a diagnostic bundle containing:\n\n"
            "• Spark AI conversation transcripts\n"
            "• Calibration files and logs\n"
            "• Debug logs\n"
            "• System information\n\n"
            "The bundle will be saved locally and you can email it to:\n"
            "info@affiniteinstruments.com\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            logger.info("[DIAGNOSTIC BUTTON] User cancelled")
            return

        # Show progress
        logger.info("[DIAGNOSTIC BUTTON] Showing progress dialog...")
        progress = QMessageBox(self.sidebar)
        progress.setWindowTitle("Creating Diagnostic Bundle")
        progress.setText("Collecting diagnostic files...\nThis may take a moment...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()

        # Process events to show dialog
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        # Create bundle locally
        logger.info("[DIAGNOSTIC BUTTON] Creating DiagnosticUploader...")
        uploader = DiagnosticUploader()
        logger.info("[DIAGNOSTIC BUTTON] Calling save_diagnostics_locally...")

        try:
            success, message = uploader.save_diagnostics_locally()
            logger.info(f"[DIAGNOSTIC BUTTON] Result: success={success}, message={message}")
        except Exception as e:
            logger.error(f"[DIAGNOSTIC BUTTON] EXCEPTION during bundle creation: {e}", exc_info=True)
            success = False
            message = f"Unexpected error: {str(e)}"

        progress.close()
        logger.info("[DIAGNOSTIC BUTTON] Progress dialog closed")

        # Show result
        if success:
            logger.info("[DIAGNOSTIC BUTTON] Showing success message...")

            # Extract bundle path from message
            bundle_path = message.split('\n')[1] if '\n' in message else "ezcontrol_diagnostics.zip"

            QMessageBox.information(
                self.sidebar,
                "Diagnostic Bundle Created",
                f"{message}\n\n"
                "📧 Next Steps:\n"
                "1. Open your email client\n"
                "2. Attach this file to an email\n"
                "3. Send to: info@affiniteinstruments.com\n"
                "4. Include a description of your issue\n\n"
                "📂 The bundle is in the ezControl-AI folder.\n"
                "Click OK to open the folder."
            )

            # Open folder containing the bundle
            try:
                folder_path = os.path.dirname(os.path.abspath(bundle_path))
                os.startfile(folder_path)
                logger.info(f"[DIAGNOSTIC BUTTON] Opened folder: {folder_path}")
            except Exception as e:
                logger.error(f"[DIAGNOSTIC BUTTON] Could not open folder: {e}")
        else:
            logger.warning(f"[DIAGNOSTIC BUTTON] Showing failure message: {message}")
            QMessageBox.warning(
                self.sidebar,
                "Bundle Creation Failed",
                message + "\n\n"
                "Please contact info@affiniteinstruments.com for assistance."
            )

        logger.info("[DIAGNOSTIC BUTTON] Handler completed")
