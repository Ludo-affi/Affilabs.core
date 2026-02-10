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
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from affilabs.diagnostics_dialog import DiagnosticsDialog
from affilabs.ui_styles import (
    Colors,
    divider_style,
    label_style,
    segmented_button_style,
    spinbox_style,
    title_style,
)
from affilabs.utils.logger import logger


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
            "}",
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

        # LED ON Period (ms) - RANKBATCH firmware cycle timing (250ms per channel)
        led_on_label = QLabel("LED ON Period:")
        led_on_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.led_on_input = QSpinBox()
        self.led_on_input.setRange(10, 500)
        self.led_on_input.setValue(250)  # RANKBATCH firmware: 250ms per channel
        self.led_on_input.setSuffix(" ms")
        self.led_on_input.setFixedWidth(120)
        self.led_on_input.setStyleSheet(spinbox_style())
        self.led_on_input.setToolTip(
            "RANKBATCH: How long each LED stays ON (250ms cycle)",
        )
        form.addRow(led_on_label, self.led_on_input)

        # LED OFF Period (ms) - Gap between channel cycles (normally 0ms, next LED auto-turns off previous)
        led_off_label = QLabel("LED OFF Period:")
        led_off_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.led_off_input = QSpinBox()
        self.led_off_input.setRange(0, 100)
        self.led_off_input.setValue(
            0,
        )  # RANKBATCH firmware: 0ms between channels (automatic turnoff)
        self.led_off_input.setSuffix(" ms")
        self.led_off_input.setFixedWidth(120)
        self.led_off_input.setStyleSheet(spinbox_style())
        self.led_off_input.setToolTip(
            "RANKBATCH: Gap between channels (0ms = next LED immediately turns off previous)",
        )
        form.addRow(led_off_label, self.led_off_input)

        # Integration Time (ms) - Detector exposure time (rankbatch detector on time budget)
        integration_label = QLabel("Integration Time:")
        integration_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))

        # Container for integration time with source indicator
        integration_container = QWidget()
        integration_layout = QHBoxLayout(integration_container)
        integration_layout.setContentsMargins(0, 0, 0, 0)
        integration_layout.setSpacing(8)

        self.detector_on_input = QSpinBox()
        self.detector_on_input.setRange(5, 200)
        self.detector_on_input.setValue(50)  # Default integration time
        self.detector_on_input.setSuffix(" ms")
        self.detector_on_input.setFixedWidth(120)
        self.detector_on_input.setStyleSheet(spinbox_style())
        self.detector_on_input.setToolTip(
            "Detector exposure/integration time\n\nThis value will be used for live acquisition.\nIt's initially loaded from calibration but can be overridden.",
        )
        integration_layout.addWidget(self.detector_on_input)

        # Source indicator label
        self.integration_source_label = QLabel("")
        self.integration_source_label.setStyleSheet(
            label_style(11, Colors.SECONDARY_TEXT, 400) + "font-style: italic;",
        )
        integration_layout.addWidget(self.integration_source_label)
        integration_layout.addStretch()

        form.addRow(integration_label, integration_container)

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
            "V2.4: Software offsets are 50ms(A), 300ms(B), 550ms(C), 800ms(D) + this wait.",
        )
        form.addRow(detector_wait_label, self.detector_wait_input)

        # Pipeline Selection - HIDDEN (Fourier is default and only option)
        # Keeping code for reference but not displaying in UI
        # pipeline_label = QLabel("Data Pipeline:")
        # pipeline_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.pipeline_combo = QComboBox()  # Keep for compatibility
        self.pipeline_combo.addItems(["Fourier (Standard)"])
        self.pipeline_combo.setCurrentIndex(0)
        self.pipeline_combo.setVisible(False)  # Hide from UI
        # form.addRow(pipeline_label, self.pipeline_combo)  # Not added to UI

        # Separator for pump corrections section
        separator_pump = QFrame()
        separator_pump.setFrameShape(QFrame.Shape.HLine)
        separator_pump.setStyleSheet(divider_style())
        form.addRow(separator_pump)

        # Pump Corrections Section Header
        pump_section_label = QLabel("Internal Pump Corrections")
        pump_section_label.setStyleSheet(title_style(15) + "margin-top: 8px; margin-bottom: 8px;")
        form.addRow(pump_section_label)

        # Pump 1 Correction
        from PySide6.QtWidgets import QDoubleSpinBox
        pump1_label = QLabel("Pump 1 Correction:")
        pump1_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.pump1_correction_spin = QDoubleSpinBox()
        self.pump1_correction_spin.setRange(0.1, 2.0)
        self.pump1_correction_spin.setSingleStep(0.01)
        self.pump1_correction_spin.setDecimals(2)
        self.pump1_correction_spin.setValue(1.0)
        self.pump1_correction_spin.setFixedWidth(120)
        self.pump1_correction_spin.setStyleSheet(spinbox_style())
        self.pump1_correction_spin.setToolTip(
            "Flowrate correction factor for Pump 1\n"
            "Multiplier applied to commanded flowrate to correct for pump calibration.\n"
            "Example: 1.0 = no correction, 0.65 = 65% of commanded rate"
        )
        form.addRow(pump1_label, self.pump1_correction_spin)

        # Pump 2 Correction
        pump2_label = QLabel("Pump 2 Correction:")
        pump2_label.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 600))
        self.pump2_correction_spin = QDoubleSpinBox()
        self.pump2_correction_spin.setRange(0.1, 2.0)
        self.pump2_correction_spin.setSingleStep(0.01)
        self.pump2_correction_spin.setDecimals(2)
        self.pump2_correction_spin.setValue(1.0)
        self.pump2_correction_spin.setFixedWidth(120)
        self.pump2_correction_spin.setStyleSheet(spinbox_style())
        self.pump2_correction_spin.setToolTip(
            "Flowrate correction factor for Pump 2\n"
            "Multiplier applied to commanded flowrate to correct for pump calibration.\n"
            "Example: 1.0 = no correction, 0.65 = 65% of commanded rate"
        )
        form.addRow(pump2_label, self.pump2_correction_spin)

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

        # Calibration Date
        cal_date_label = QLabel("Calibration Date:")
        cal_date_label.setStyleSheet(label_style(13, Colors.SECONDARY_TEXT))
        self.cal_date_value = QLabel("N/A")
        self.cal_date_value.setStyleSheet(label_style(13, Colors.PRIMARY_TEXT, 500))
        device_info.addRow(cal_date_label, self.cal_date_value)

        main_layout.addLayout(device_info)

        main_layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
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

        # Diagnostics button removed - no longer needed

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
                "}",
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
            import settings
            from affilabs.utils.processing_pipeline import get_pipeline_registry

            logger.info("🔧 Applying Advanced Settings...")

            # Apply Unit Selection
            if self.ru_btn.isChecked():
                settings.DEFAULT_UNIT = "RU"
                logger.info("  Unit: RU")
            else:
                settings.DEFAULT_UNIT = "nm"
                logger.info("  Unit: nm")

            # Apply Timing Parameters (firmware and software parameters)
            settings.LED_ON_TIME_MS = (
                self.led_on_input.value()
            )  # Firmware: LED ON duration
            settings.LED_OFF_TIME_MS = (
                self.led_off_input.value()
            )  # Firmware: LED OFF duration
            settings.DETECTOR_ON_TIME_MS = (
                self.detector_on_input.value()
            )  # Integration time
            settings.DETECTOR_WAIT_MS = (
                self.detector_wait_input.value()
            )  # Software: wait after CYCLE_START
            logger.info(
                f"  LED ON Time: {settings.LED_ON_TIME_MS} ms (firmware timing base)",
            )
            logger.info(
                f"  LED OFF Time: {settings.LED_OFF_TIME_MS} ms (firmware parameter)",
            )
            logger.info(f"  Integration Time: {settings.DETECTOR_ON_TIME_MS} ms")
            logger.info(
                f"  Detector Wait: {settings.DETECTOR_WAIT_MS} ms (software offset)",
            )

            # Apply detector wait to running data acquisition manager (if available)
            if hasattr(self.parent(), "app") and hasattr(self.parent().app, "data_mgr"):
                data_mgr = self.parent().app.data_mgr
                if data_mgr:
                    data_mgr.detector_wait_ms = settings.DETECTOR_WAIT_MS
                    logger.info(
                        f"  ✓ Updated data manager detector_wait_ms = {settings.DETECTOR_WAIT_MS} ms",
                    )

            # Apply Pipeline Selection
            pipeline_idx = self.pipeline_combo.currentIndex()
            registry = get_pipeline_registry()

            pipeline_map = {
                0: "fourier",  # Fourier (Standard - 17.98 RU)
                1: "hybrid_original",  # Hybrid Original (First attempt - 8.82 RU)
                2: "hybrid",  # Hybrid Optimized (90% reduction - 1.81 RU)
            }

            if pipeline_idx in pipeline_map:
                pipeline_id = pipeline_map[pipeline_idx]
                registry.set_active_pipeline(pipeline_id)
                active_pipeline = registry.get_active_pipeline()
                pipeline_name = getattr(active_pipeline, 'pipeline_id', pipeline_id)
                logger.info(f"  Pipeline: {pipeline_name}")

            logger.info("✅ Settings applied successfully!")

            # Save pump corrections to device config and controller EEPROM
            try:
                pump1_corr = self.pump1_correction_spin.value()
                pump2_corr = self.pump2_correction_spin.value()

                # Use stored hardware_mgr from load_pump_corrections
                if hasattr(self, '_hardware_mgr') and self._hardware_mgr:
                    device_config = getattr(self._hardware_mgr, 'device_config', None)
                    ctrl = getattr(self._hardware_mgr, '_ctrl_raw', None)

                    # Save to device config JSON
                    if device_config and hasattr(device_config, 'set_pump_corrections'):
                        device_config.set_pump_corrections(pump1_corr, pump2_corr)
                        device_config.save()
                        logger.info(f"💾 Pump corrections saved to device config: P1={pump1_corr:.3f}, P2={pump2_corr:.3f}")

                    # Save to controller EEPROM (if supported by firmware)
                    if ctrl and hasattr(ctrl, 'set_pump_corrections'):
                        success = ctrl.set_pump_corrections(pump1_corr, pump2_corr)
                        if success:
                            logger.info(f"✓ Pump corrections written to controller EEPROM: P1={pump1_corr:.3f}, P2={pump2_corr:.3f}")
                        else:
                            logger.warning("⚠ Controller EEPROM write failed - firmware version may not support pump corrections (need V1.4+)")
                    else:
                        if not ctrl:
                            logger.warning("⚠ Controller not connected - pump corrections saved to config only")
                        else:
                            logger.warning("⚠ Controller does not have set_pump_corrections method")
                else:
                    logger.warning("⚠ Hardware manager not available - pump corrections not saved to controller")

            except Exception as e:
                logger.warning(f"Could not save pump corrections: {e}")

            # Notify parent window if it has an update method
            if hasattr(self.parent(), "on_settings_changed"):
                self.parent().on_settings_changed()

        except Exception as e:
            logger.error(f"❌ Error applying settings: {e}")

        # Close dialog
        super().accept()

    def load_calibration_params(self, calibration_data):
        """Load parameters from calibration data into Advanced Settings.

        Args:
            calibration_data: CalibrationData object with integration_time, num_scans, etc.

        """
        if not calibration_data:
            return

        try:
            # Load P-mode integration time from calibration (preferred)
            integration_time_p = getattr(calibration_data, "integration_time_p", None)
            integration_time_s = getattr(calibration_data, "integration_time_s", None)
            integration_time_legacy = getattr(calibration_data, "integration_time", None)

            # Prefer P-mode integration time (used during live acquisition)
            integration_time = integration_time_p or integration_time_legacy

            if integration_time:
                self.detector_on_input.setValue(int(integration_time))
                self.integration_source_label.setText("(from P-mode calibration)")
                logger.info(
                    f"  Loaded integration time from calibration: P-mode={integration_time}ms, S-mode={integration_time_s}ms",
                )
            elif integration_time_s:
                # Fallback to S-mode if P-mode not available
                self.detector_on_input.setValue(int(integration_time_s))
                self.integration_source_label.setText("(from S-mode calibration)")
                logger.info(
                    f"  Loaded integration time from S-mode calibration: {integration_time_s}ms",
                )

            # Load LED timing if available
            pre_led_delay = getattr(calibration_data, "pre_led_delay_ms", None)
            post_led_delay = getattr(calibration_data, "post_led_delay_ms", None)

            if pre_led_delay is not None:
                logger.info(f"  Calibration PRE LED delay: {pre_led_delay}ms")
            if post_led_delay is not None:
                logger.info(f"  Calibration POST LED delay: {post_led_delay}ms")

        except Exception as e:
            logger.warning(
                f"Could not load calibration params into Advanced Settings: {e}",
            )

    def load_device_info(
        self,
        serial="Not detected",
        cal_date=None,
    ):
        """Load device information into the dialog.

        Args:
            serial: Device serial number
            cal_date: Calibration date (string or datetime)

        """
        self.serial_value.setText(serial if serial else "Not detected")

        if cal_date:
            if isinstance(cal_date, str):
                self.cal_date_value.setText(cal_date)
            else:
                self.cal_date_value.setText(cal_date.strftime("%Y-%m-%d %H:%M"))
        else:
            self.cal_date_value.setText("N/A")

    def load_pump_corrections(self, hardware_mgr):
        """Load pump correction values from device config and controller EEPROM.

        Args:
            hardware_mgr: Hardware manager instance to access device config and controller
        """
        # Store hardware_mgr for later use in save
        self._hardware_mgr = hardware_mgr

        try:
            # Try to get corrections from device config first
            device_config = getattr(hardware_mgr, 'device_config', None)
            if device_config and hasattr(device_config, 'get_pump_corrections'):
                corrections = device_config.get_pump_corrections()
                if corrections and isinstance(corrections, dict):
                    pump1_corr = corrections.get("pump_1", 1.0)
                    pump2_corr = corrections.get("pump_2", 1.0)
                    self.pump1_correction_spin.setValue(pump1_corr)
                    self.pump2_correction_spin.setValue(pump2_corr)
                    logger.info(f"📖 Loaded pump corrections from device config: P1={pump1_corr:.3f}, P2={pump2_corr:.3f}")
                    return

            # Fallback: try to get from controller EEPROM
            ctrl = getattr(hardware_mgr, '_ctrl_raw', None)
            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                corrections = ctrl.get_pump_corrections()
                if corrections:
                    if isinstance(corrections, tuple) and len(corrections) == 2:
                        pump1_corr, pump2_corr = corrections
                    elif isinstance(corrections, dict):
                        pump1_corr = corrections.get(1, 1.0)
                        pump2_corr = corrections.get(2, 1.0)
                    else:
                        logger.warning(f"Unexpected pump corrections format: {corrections}")
                        return

                    self.pump1_correction_spin.setValue(pump1_corr)
                    self.pump2_correction_spin.setValue(pump2_corr)
                    logger.info(f"📖 Loaded pump corrections from controller EEPROM: P1={pump1_corr:.3f}, P2={pump2_corr:.3f}")

        except Exception as e:
            logger.debug(f"Could not load pump corrections: {e}")
            # Keep default values (1.0, 1.0)
