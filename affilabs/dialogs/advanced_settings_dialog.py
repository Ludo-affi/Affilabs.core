"""Advanced Settings Dialog - Application-wide settings and device configuration.

This dialog provides access to:
- Unit selection (RU/nm)
- LED and detector timing parameters
- Data processing pipeline selection
- Device information display
- Diagnostics (dev mode only)
"""

import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFormLayout, QSpinBox, QComboBox, QFrame, QButtonGroup,
    QDialogButtonBox, QScrollArea, QTextEdit, QGroupBox, QGridLayout, QTabWidget, QWidget
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from affilabs.utils.logger import logger
from ui_styles import (
    Colors,
    label_style, title_style,
    segmented_button_style, spinbox_style, divider_style, group_box_style
)
from diagnostics_dialog import DiagnosticsDialog


class AdvancedSettingsDialog(QDialog):
    """Dialog for advanced application settings and device information."""

    def __init__(self, parent=None, unlocked=False):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.advanced_params_unlocked = unlocked

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
        title.setStyleSheet(title_style(20) + "margin-bottom: 8px;")
        main_layout.addWidget(title)

        # Tab widget for Settings and Diagnostics (if DEV mode)
        self.tabs = QTabWidget()
        tab_widget_style = (
            "QTabWidget::pane { border: none; }"
            "QTabBar::tab { padding: 8px 20px; margin-right: 4px; "
            f"background: {Colors.BACKGROUND_LIGHT}; border-top-left-radius: 6px; "
            "border-top-right-radius: 6px; font-size: 13px; font-weight: 500; }"
            f"QTabBar::tab:selected {{ background: white; color: {Colors.PRIMARY_TEXT}; }}"
            f"QTabBar::tab:!selected {{ color: {Colors.SECONDARY_TEXT}; }}"
        )
        self.tabs.setStyleSheet(tab_widget_style)

        # Settings tab (main content)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 16, 0, 0)

        # Form layout for settings
        form = QFormLayout()
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Unit Selection (moved from Settings tab)
        unit_label = QLabel("Unit:")
        unit_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))

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
        self.ru_btn.setStyleSheet(segmented_button_style("left"))
        self.unit_button_group.addButton(self.ru_btn, 0)
        unit_layout.addWidget(self.ru_btn)

        self.nm_btn = QPushButton("nm")
        self.nm_btn.setCheckable(True)
        self.nm_btn.setFixedHeight(28)
        self.nm_btn.setStyleSheet(segmented_button_style("right"))
        self.unit_button_group.addButton(self.nm_btn, 1)
        unit_layout.addWidget(self.nm_btn)
        unit_layout.addStretch()

        form.addRow(unit_label, unit_container)

        # LED ON Time (ms) - How long LED stays ON per channel (rankbatch parameter)
        led_on_label = QLabel("LED ON Time:")
        led_on_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.led_on_input = QSpinBox()
        self.led_on_input.setRange(10, 500)
        self.led_on_input.setValue(250)  # RANKBATCH firmware: 250ms per channel
        self.led_on_input.setSuffix(" ms")
        self.led_on_input.setFixedWidth(120)
        self.led_on_input.setStyleSheet(spinbox_style())
        self.led_on_input.setToolTip("Duration LED stays ON per channel (firmware RANKBATCH timing base)")
        form.addRow(led_on_label, self.led_on_input)

        # LED OFF Time (ms) - How long LED stays OFF between channels (rankbatch parameter)
        led_off_label = QLabel("LED OFF Time:")
        led_off_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.led_off_input = QSpinBox()
        self.led_off_input.setRange(0, 100)
        self.led_off_input.setValue(0)  # RANKBATCH firmware: 0ms between channels
        self.led_off_input.setSuffix(" ms")
        self.led_off_input.setFixedWidth(120)
        self.led_off_input.setStyleSheet(spinbox_style())
        self.led_off_input.setToolTip("Duration LED stays OFF between channels (firmware RANKBATCH parameter)")
        form.addRow(led_off_label, self.led_off_input)

        # Integration Time (ms) - Detector exposure time (rankbatch detector on time budget)
        integration_label = QLabel("Integration Time:")
        integration_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.detector_on_input = QSpinBox()
        self.detector_on_input.setRange(5, 200)
        self.detector_on_input.setValue(50)  # Default integration time
        self.detector_on_input.setSuffix(" ms")
        self.detector_on_input.setFixedWidth(120)
        self.detector_on_input.setStyleSheet(spinbox_style())
        self.detector_on_input.setToolTip("Detector exposure/integration time (rankbatch detector on time budget)")
        form.addRow(integration_label, self.detector_on_input)

        # Detector Wait Time (ms) - Software delay after CYCLE_START before reading detector
        detector_wait_label = QLabel("Detector Wait:")
        detector_wait_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.detector_wait_input = QSpinBox()
        self.detector_wait_input.setRange(0, 100)
        self.detector_wait_input.setValue(60)  # Software waits 60ms after CYCLE_START
        self.detector_wait_input.setSuffix(" ms")
        self.detector_wait_input.setFixedWidth(120)
        self.detector_wait_input.setStyleSheet(spinbox_style())
        self.detector_wait_input.setToolTip(
            "Software delay after receiving CYCLE_START before reading detector.\n"
            "Allows LED to stabilize before measurement.\n"
            "V2.4: Software offsets are 50ms(A), 300ms(B), 550ms(C), 800ms(D) + this wait."
        )
        form.addRow(detector_wait_label, self.detector_wait_input)

        # Pipeline Selection
        pipeline_label = QLabel("Data Pipeline:")
        pipeline_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.pipeline_combo = QComboBox()
        self.pipeline_combo.addItems([
            "Fourier (Standard - 17.98 RU)",
            "Hybrid Original (First attempt - 8.82 RU)",
            "Hybrid Optimized (90% reduction - 1.81 RU)",
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

        main_layout.addLayout(form)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(divider_style())
        main_layout.addWidget(separator)

        # Device Information Section
        info_section = QLabel("Device Information")
        info_section.setStyleSheet(title_style(15) + "margin-top: 4px;")
        main_layout.addWidget(info_section)

        # Device info layout
        device_info = QFormLayout()
        device_info.setSpacing(12)
        device_info.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Serial Number
        serial_label = QLabel("Serial Number:")
        serial_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.serial_value = QLabel("Not detected")
        self.serial_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(serial_label, self.serial_value)

        # Afterglow Calibration Status
        afterglow_label = QLabel("Afterglow Calibration:")
        afterglow_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.afterglow_value = QLabel("Not calibrated")
        self.afterglow_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(afterglow_label, self.afterglow_value)

        # Calibration Date
        cal_date_label = QLabel("Calibration Date:")
        cal_date_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.cal_date_value = QLabel("N/A")
        self.cal_date_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(cal_date_label, self.cal_date_value)

        main_layout.addLayout(device_info)

        main_layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dialog_button_style = (
            "QPushButton { padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 600; min-width: 80px; }"
            f"QPushButton[text='OK'] {{ background: {Colors.PRIMARY_TEXT}; color: white; border: none; }}"
            "QPushButton[text='OK']:hover { background: #3A3A3C; }"
            f"QPushButton[text='Cancel'] {{ background: white; color: {Colors.PRIMARY_TEXT}; border: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
            f"QPushButton[text='Cancel']:hover {{ background: {Colors.OVERLAY_LIGHT_6}; }}"
        )
        button_box.setStyleSheet(dialog_button_style)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # === Add Diagnostics Tab (hidden unless DEV mode) ===
        self._setup_diagnostics_tab()

    def _setup_diagnostics_tab(self):
        """Setup diagnostics tab that shows all QC details and calibration data.

        This tab is hidden in user mode and only visible in dev/support mode or when unlocked.
        """
        try:
            # Check if DEV mode is enabled
            from settings import DEV
            dev_mode = DEV
        except ImportError:
            dev_mode = False

        # Show diagnostics if DEV mode is enabled OR if unlocked via Control+10-click
        if not dev_mode and not self.advanced_params_unlocked:
            return  # Don't create diagnostics tab in user mode

        # Add diagnostics button
        self._setup_diagnostics_button()

    def _setup_diagnostics_button(self):
        """Add a diagnostics button to show the diagnostics window."""
        # Find the button box and add our button before it
        button_box = self.findChild(QDialogButtonBox)
        if button_box:
            # Add diagnostics button to the left side
            diag_btn = QPushButton("🔧 Diagnostics")
            diag_btn.setStyleSheet(
                "QPushButton {"
                "  background: #F5F5F7;"
                "  color: #1D1D1F;"
                "  border: 1px solid rgba(0, 0, 0, 0.1);"
                "  border-radius: 6px;"
                "  padding: 8px 20px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  min-width: 120px;"
                "}"
                "QPushButton:hover {"
                "  background: #E8E8EA;"
                "}"
            )
            diag_btn.clicked.connect(self._show_diagnostics)
            button_box.addButton(diag_btn, QDialogButtonBox.ButtonRole.ActionRole)

    def _show_diagnostics(self):
        """Show diagnostics window with all QC data."""
        diag_dialog = DiagnosticsDialog(self)
        diag_dialog.load_diagnostics_data(self.parent())
        diag_dialog.exec()

    def accept(self):
        """Apply settings when OK is clicked."""
        try:
            from affilabs.utils.processing_pipeline import get_pipeline_registry
            import settings

            logger.info("🔧 Applying Advanced Settings...")

            # Apply Unit Selection
            if self.ru_btn.isChecked():
                settings.DEFAULT_UNIT = 'RU'
                logger.info("  Unit: RU")
            else:
                settings.DEFAULT_UNIT = 'nm'
                logger.info("  Unit: nm")

            # Apply Timing Parameters (firmware and software parameters)
            settings.LED_ON_TIME_MS = self.led_on_input.value()  # Firmware: LED ON duration
            settings.LED_OFF_TIME_MS = self.led_off_input.value()  # Firmware: LED OFF duration
            settings.DETECTOR_ON_TIME_MS = self.detector_on_input.value()  # Integration time
            settings.DETECTOR_WAIT_MS = self.detector_wait_input.value()  # Software: wait after CYCLE_START
            logger.info(f"  LED ON Time: {settings.LED_ON_TIME_MS} ms (firmware timing base)")
            logger.info(f"  LED OFF Time: {settings.LED_OFF_TIME_MS} ms (firmware parameter)")
            logger.info(f"  Integration Time: {settings.DETECTOR_ON_TIME_MS} ms")
            logger.info(f"  Detector Wait: {settings.DETECTOR_WAIT_MS} ms (software offset)")
            
            # Apply detector wait to running data acquisition manager (if available)
            if hasattr(self.parent(), 'app') and hasattr(self.parent().app, 'data_mgr'):
                data_mgr = self.parent().app.data_mgr
                if data_mgr:
                    data_mgr.detector_wait_ms = settings.DETECTOR_WAIT_MS
                    logger.info(f"  ✓ Updated data manager detector_wait_ms = {settings.DETECTOR_WAIT_MS} ms")

            # Apply Pipeline Selection
            pipeline_idx = self.pipeline_combo.currentIndex()
            registry = get_pipeline_registry()

            pipeline_map = {
                0: 'fourier',         # Fourier (Standard - 17.98 RU)
                1: 'hybrid_original', # Hybrid Original (First attempt - 8.82 RU)
                2: 'hybrid',          # Hybrid Optimized (90% reduction - 1.81 RU)
            }

            if pipeline_idx in pipeline_map:
                pipeline_id = pipeline_map[pipeline_idx]
                registry.set_active_pipeline(pipeline_id)
                logger.info(f"  Pipeline: {registry.get_active_pipeline().name}")

            logger.info("✅ Settings applied successfully!")

            # Notify parent window if it has an update method
            if hasattr(self.parent(), 'on_settings_changed'):
                self.parent().on_settings_changed()

        except Exception as e:
            logger.error(f"❌ Error applying settings: {e}")

        # Close dialog
        super().accept()

    def load_device_info(self, serial="Not detected", afterglow_cal=False, cal_date=None):
        """Load device information into the dialog.

        Args:
            serial: Device serial number
            afterglow_cal: Whether afterglow calibration is present
            cal_date: Calibration date (string or datetime)
        """
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
