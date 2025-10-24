"""Device configuration settings widget for optical fiber and hardware setup.

This widget provides GUI access to device configuration including:
- Optical fiber diameter (100 µm or 200 µm)
- LED PCB model selection
- Hardware detection
- Configuration import/export
"""

from __future__ import annotations

# Python version compatibility
try:
    from typing import Self  # Python 3.11+
except ImportError:
    from typing_extensions import Self  # Python < 3.11

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from utils.device_configuration import DeviceConfiguration
from utils.hardware_detection import HardwareDetector
from utils.security import get_security_manager
from utils.logger import logger


class DeviceSettingsWidget(QWidget):
    """Widget for device configuration settings.

    Provides GUI controls for:
    - Optical fiber diameter selection (100/200 µm)
    - LED PCB model selection
    - Hardware detection
    - Configuration management
    """

    # Signal emitted when configuration changes
    configuration_changed = Signal()

    def __init__(self: Self, parent: Optional[QWidget] = None) -> None:
        """Initialize device settings widget."""
        super().__init__(parent)

        # Load device configuration
        self.config = DeviceConfiguration()
        self.detector = HardwareDetector()

        # Security manager for OEM access control
        self.security = get_security_manager()
        self.oem_mode_active = False

        # Create UI
        self._create_ui()
        self._load_current_settings()
        self._update_security_ui()

    def _create_ui(self: Self) -> None:
        """Create user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # === Optical Fiber Diameter Section ===
        fiber_group = QGroupBox("Optical Fiber Diameter")
        fiber_layout = QVBoxLayout()

        # Info label
        fiber_info = QLabel(
            "Select the diameter of your optical fiber probe.\n"
            "This affects signal strength calculations and frequency limits."
        )
        fiber_info.setWordWrap(True)
        fiber_info.setStyleSheet("color: gray; font-size: 9pt;")
        fiber_layout.addWidget(fiber_info)

        # Radio buttons for fiber diameter
        self.fiber_100um = QRadioButton("100 µm (Higher resolution, lower signal)")
        self.fiber_200um = QRadioButton("200 µm (Higher signal, most common)")

        self.fiber_button_group = QButtonGroup(self)
        self.fiber_button_group.addButton(self.fiber_100um, 100)
        self.fiber_button_group.addButton(self.fiber_200um, 200)

        fiber_layout.addWidget(self.fiber_100um)
        fiber_layout.addWidget(self.fiber_200um)

        fiber_group.setLayout(fiber_layout)
        main_layout.addWidget(fiber_group)

        # === LED PCB Model Section ===
        led_group = QGroupBox("LED PCB Model")
        led_layout = QVBoxLayout()

        # Info label
        led_info = QLabel(
            "Select your LED PCB hardware variant.\n"
            "This affects timing parameters and intensity calibration."
        )
        led_info.setWordWrap(True)
        led_info.setStyleSheet("color: gray; font-size: 9pt;")
        led_layout.addWidget(led_info)

        # Radio buttons for LED model
        self.led_luminus = QRadioButton("Luminus Cool White (Most common)")
        self.led_osram = QRadioButton("Osram Warm White")

        self.led_button_group = QButtonGroup(self)
        self.led_button_group.addButton(self.led_luminus, 0)
        self.led_button_group.addButton(self.led_osram, 1)

        led_layout.addWidget(self.led_luminus)
        led_layout.addWidget(self.led_osram)

        led_group.setLayout(led_layout)
        main_layout.addWidget(led_group)

        # === Calibration Mode Section ===
        calib_mode_group = QGroupBox("Calibration Mode")
        calib_mode_layout = QVBoxLayout()

        # Info label
        calib_mode_info = QLabel(
            "Select calibration approach for optimal spectral performance:\n\n"
            "• Global Mode (Default): Calibrates LED intensities per channel, "
            "uses single integration time. Best for balanced signal levels.\n\n"
            "• Per-Channel Mode (Advanced): All LEDs fixed at 255, "
            "uses per-channel integration times. Optimal for widely varying responses."
        )
        calib_mode_info.setWordWrap(True)
        calib_mode_info.setStyleSheet("color: gray; font-size: 9pt;")
        calib_mode_layout.addWidget(calib_mode_info)

        # Warning label
        calib_mode_warning = QLabel(
            "⚠️ Important: Changing calibration mode requires running a full "
            "calibration before measurements."
        )
        calib_mode_warning.setWordWrap(True)
        calib_mode_warning.setStyleSheet(
            "color: #FF6B00; font-size: 9pt; font-weight: bold; "
            "background-color: #FFF3E0; padding: 8px; border-radius: 3px;"
        )
        calib_mode_layout.addWidget(calib_mode_warning)

        # Radio buttons for calibration mode
        self.calib_mode_global = QRadioButton("Global Mode - Balanced LED intensities (Recommended)")
        self.calib_mode_per_channel = QRadioButton("Per-Channel Mode - Individual integration times (Advanced)")

        self.calib_mode_button_group = QButtonGroup(self)
        self.calib_mode_button_group.addButton(self.calib_mode_global, 0)
        self.calib_mode_button_group.addButton(self.calib_mode_per_channel, 1)

        calib_mode_layout.addWidget(self.calib_mode_global)
        calib_mode_layout.addWidget(self.calib_mode_per_channel)

        calib_mode_group.setLayout(calib_mode_layout)
        main_layout.addWidget(calib_mode_group)

        # === Hardware Detection Section ===
        hardware_group = QGroupBox("Hardware Detection")
        hardware_layout = QVBoxLayout()

        hardware_info = QLabel(
            "Automatically detect connected spectrometer and controller.\n"
            "Serial numbers will be saved to configuration."
        )
        hardware_info.setWordWrap(True)
        hardware_info.setStyleSheet("color: gray; font-size: 9pt;")
        hardware_layout.addWidget(hardware_info)

        # Hardware detection result label
        self.hardware_status = QLabel("Click 'Detect Hardware' to scan devices")
        self.hardware_status.setStyleSheet("font-weight: bold;")
        hardware_layout.addWidget(self.hardware_status)

        # Detect button
        detect_btn = QPushButton("🔍 Detect Hardware")
        detect_btn.clicked.connect(self._detect_hardware)
        hardware_layout.addWidget(detect_btn)

        hardware_group.setLayout(hardware_layout)
        main_layout.addWidget(hardware_group)

        # === OEM Service Mode Section ===
        oem_group = QGroupBox("🔐 OEM Service Mode")
        oem_layout = QHBoxLayout()

        # OEM status label
        self.oem_status_label = QLabel("🔒 Locked - User Mode")
        self.oem_status_label.setStyleSheet(
            "QLabel { color: #f44336; font-weight: bold; padding: 5px; }"
        )
        oem_layout.addWidget(self.oem_status_label)

        oem_layout.addStretch()

        # OEM unlock button
        self.oem_unlock_btn = QPushButton("🔓 Unlock OEM Mode")
        self.oem_unlock_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )
        self.oem_unlock_btn.clicked.connect(self._authenticate_oem)
        oem_layout.addWidget(self.oem_unlock_btn)

        # OEM lock button (hidden initially)
        self.oem_lock_btn = QPushButton("🔒 Lock OEM Mode")
        self.oem_lock_btn.setStyleSheet(
            "QPushButton { background-color: #9E9E9E; color: white; padding: 8px; }"
        )
        self.oem_lock_btn.clicked.connect(self._lock_oem_mode)
        self.oem_lock_btn.setVisible(False)
        oem_layout.addWidget(self.oem_lock_btn)

        oem_group.setLayout(oem_layout)
        main_layout.addWidget(oem_group)

        # === Action Buttons ===
        button_layout = QHBoxLayout()

        # Save button
        save_btn = QPushButton("💾 Save Configuration")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        save_btn.clicked.connect(self._save_configuration)
        button_layout.addWidget(save_btn)

        # Export button
        export_btn = QPushButton("📤 Export")
        export_btn.clicked.connect(self._export_configuration)
        button_layout.addWidget(export_btn)

        # Import button
        import_btn = QPushButton("📥 Import")
        import_btn.clicked.connect(self._import_configuration)
        button_layout.addWidget(import_btn)

        # Reset button
        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.setStyleSheet("QPushButton { color: #f44336; }")
        reset_btn.clicked.connect(self._reset_configuration)
        button_layout.addWidget(reset_btn)

        main_layout.addLayout(button_layout)

        # === Current Configuration Display ===
        info_group = QGroupBox("Current Configuration")
        info_layout = QVBoxLayout()

        self.config_display = QLabel()
        self.config_display.setStyleSheet(
            "QLabel { background-color: #f5f5f5; padding: 10px; "
            "border: 1px solid #ddd; border-radius: 3px; }"
        )
        self.config_display.setTextFormat(Qt.RichText)
        info_layout.addWidget(self.config_display)

        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # Add stretch to push everything to top
        main_layout.addStretch()

        # Connect signals
        self.fiber_button_group.buttonClicked.connect(self._on_settings_changed)
        self.led_button_group.buttonClicked.connect(self._on_settings_changed)
        self.calib_mode_button_group.buttonClicked.connect(self._on_settings_changed)

    def _load_current_settings(self: Self) -> None:
        """Load current configuration and update UI."""
        # Optical fiber diameter
        fiber_diameter = self.config.get_optical_fiber_diameter()
        if fiber_diameter == 100:
            self.fiber_100um.setChecked(True)
        else:
            self.fiber_200um.setChecked(True)

        # LED PCB model
        led_model = self.config.get_led_pcb_model()
        if led_model == 'luminus_cool_white':
            self.led_luminus.setChecked(True)
        else:
            self.led_osram.setChecked(True)

        # Calibration mode
        calib_mode = self.config.get_calibration_mode()
        if calib_mode == 'global':
            self.calib_mode_global.setChecked(True)
        else:
            self.calib_mode_per_channel.setChecked(True)

        # Update display
        self._update_config_display()

    def _on_settings_changed(self: Self) -> None:
        """Handle settings change."""
        self._update_config_display()

    def _update_config_display(self: Self) -> None:
        """Update configuration display."""
        # Get current selections
        fiber_diameter = self.fiber_button_group.checkedId()
        led_model = 'luminus_cool_white' if self.led_button_group.checkedId() == 0 else 'osram_warm_white'
        calib_mode = 'global' if self.calib_mode_button_group.checkedId() == 0 else 'per_channel'
        calib_mode_display = 'Global (Balanced LEDs)' if calib_mode == 'global' else 'Per-Channel (Individual Times)'

        # Get frequency limits
        limits_4led = self.config.get_frequency_limits(4)
        limits_2led = self.config.get_frequency_limits(2)

        # Build display text
        display_text = f"""
        <b>Device Configuration:</b><br>
        <br>
        <b>Optical Fiber:</b> {fiber_diameter} µm<br>
        <b>LED PCB Model:</b> {led_model.replace('_', ' ').title()}<br>
        <b>Calibration Mode:</b> {calib_mode_display}<br>
        <b>Spectrometer S/N:</b> {self.config.get_spectrometer_serial() or 'Not set'}<br>
        <br>
        <b>Frequency Limits:</b><br>
        • 4-LED Mode: Max {limits_4led['max_hz']} Hz (Recommended: {limits_4led['recommended_hz']} Hz)<br>
        • 2-LED Mode: Max {limits_2led['max_hz']} Hz (Recommended: {limits_2led['recommended_hz']} Hz)<br>
        <br>
        <b>Min Integration Time:</b> {self.config.get_min_integration_time()} ms
        """

        self.config_display.setText(display_text)

    def _detect_hardware(self: Self) -> None:
        """Detect connected hardware."""
        try:
            # Show detecting message
            self.hardware_status.setText("🔍 Scanning for devices...")
            self.hardware_status.setStyleSheet("color: blue; font-weight: bold;")
            self.hardware_status.repaint()  # Force UI update

            # Detect hardware
            detected = self.detector.detect_all_hardware()

            # Build status message
            status_parts = []

            if detected['spectrometer']:
                spec = detected['spectrometer']
                status_parts.append(
                    f"✅ Spectrometer: {spec['description']}\n"
                    f"   S/N: {spec['serial_number'] or 'Unknown'}"
                )
                # Update config with serial number
                if spec['serial_number']:
                    self.config.set_spectrometer_serial(spec['serial_number'])
            else:
                status_parts.append("❌ Spectrometer: Not detected")

            if detected['controller']:
                ctrl = detected['controller']
                status_parts.append(
                    f"✅ Controller: {ctrl['description']}"
                )
            else:
                status_parts.append("❌ Controller: Not detected")

            status_text = "\n\n".join(status_parts)
            self.hardware_status.setText(status_text)
            self.hardware_status.setStyleSheet("font-weight: bold;")

            # Update config display
            self._update_config_display()

            # Show success message
            QMessageBox.information(
                self,
                "Hardware Detection",
                "Hardware detection complete.\n\n" + status_text
            )

        except Exception as e:
            logger.error(f"Hardware detection failed: {e}")
            self.hardware_status.setText(f"❌ Detection failed: {e}")
            self.hardware_status.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(
                self,
                "Error",
                f"Hardware detection failed:\n{e}"
            )

    def _save_configuration(self: Self) -> None:
        """Save current configuration."""
        try:
            # Get selections
            fiber_diameter = self.fiber_button_group.checkedId()
            led_model = 'luminus_cool_white' if self.led_button_group.checkedId() == 0 else 'osram_warm_white'
            calib_mode = 'global' if self.calib_mode_button_group.checkedId() == 0 else 'per_channel'

            # Check if calibration mode is changing
            current_mode = self.config.get_calibration_mode()
            if calib_mode != current_mode:
                # Warn user that calibration is required
                from PySide6.QtWidgets import QMessageBox as MB
                reply = MB.warning(
                    self,
                    "Calibration Mode Change",
                    f"You are changing calibration mode from '{current_mode}' to '{calib_mode}'.\n\n"
                    "⚠️ Important: You MUST run a full calibration before taking measurements.\n\n"
                    "The two modes use different LED intensity and integration time strategies, "
                    "so existing calibration data will not be valid.\n\n"
                    "Do you want to proceed with this change?",
                    MB.StandardButton.Yes | MB.StandardButton.No,
                    MB.StandardButton.No
                )

                if reply != MB.StandardButton.Yes:
                    logger.info("Calibration mode change cancelled by user")
                    return

            # Update configuration
            self.config.set_optical_fiber_diameter(fiber_diameter)
            self.config.set_led_pcb_model(led_model)
            self.config.set_calibration_mode(calib_mode)

            # Validate
            is_valid, errors = self.config.validate()
            if not is_valid:
                error_msg = "Configuration validation failed:\n\n" + "\n".join(errors)
                QMessageBox.warning(self, "Validation Error", error_msg)
                return

            # Save
            self.config.save()

            # Emit signal
            self.configuration_changed.emit()

            # Show success
            calib_mode_display = 'Global (Balanced LEDs)' if calib_mode == 'global' else 'Per-Channel (Individual Times)'
            QMessageBox.information(
                self,
                "Success",
                "Configuration saved successfully!\n\n"
                f"Optical Fiber: {fiber_diameter} µm\n"
                f"LED PCB: {led_model}\n"
                f"Calibration Mode: {calib_mode_display}"
            )

            logger.info(f"Device configuration saved: fiber={fiber_diameter}µm, led={led_model}, mode={calib_mode}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save configuration:\n{e}"
            )

    def _export_configuration(self: Self) -> None:
        """Export configuration to file."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Configuration",
                str(Path.home() / "device_config_backup.json"),
                "JSON Files (*.json)"
            )

            if file_path:
                self.config.export_config(file_path)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Configuration exported to:\n{file_path}"
                )
                logger.info(f"Configuration exported to: {file_path}")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    def _import_configuration(self: Self) -> None:
        """Import configuration from file."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Configuration",
                str(Path.home()),
                "JSON Files (*.json)"
            )

            if file_path:
                # Confirm import
                reply = QMessageBox.question(
                    self,
                    "Confirm Import",
                    "This will replace your current configuration.\n"
                    "Are you sure you want to continue?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self.config.import_config(file_path)
                    self._load_current_settings()
                    self.configuration_changed.emit()

                    QMessageBox.information(
                        self,
                        "Success",
                        f"Configuration imported from:\n{file_path}"
                    )
                    logger.info(f"Configuration imported from: {file_path}")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            QMessageBox.critical(self, "Error", f"Import failed:\n{e}")

    def _reset_configuration(self: Self) -> None:
        """Reset configuration to defaults."""
        try:
            reply = QMessageBox.question(
                self,
                "Confirm Reset",
                "This will reset ALL configuration to default values.\n"
                "This action cannot be undone.\n\n"
                "Are you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.config.reset_to_defaults()
                self.config.save()
                self._load_current_settings()
                self.configuration_changed.emit()

                QMessageBox.information(
                    self,
                    "Success",
                    "Configuration reset to defaults"
                )
                logger.info("Device configuration reset to defaults")

        except Exception as e:
            logger.error(f"Reset failed: {e}")
            QMessageBox.critical(self, "Error", f"Reset failed:\n{e}")

    def _authenticate_oem(self: Self) -> None:
        """Authenticate OEM user to unlock service mode."""
        try:
            # Prompt for password
            password, ok = QInputDialog.getText(
                self,
                "🔐 OEM Authentication",
                "Enter OEM password to unlock service mode:\n\n"
                "(Contact Affinite Instruments for OEM access)",
                QLineEdit.Password
            )

            if ok and password:
                # Authenticate with security manager
                if self.security.authenticate_oem(password, username="GUI_USER"):
                    self.oem_mode_active = True
                    self._update_security_ui()

                    # Show success message with session info
                    session_info = self.security.get_session_info()
                    QMessageBox.information(
                        self,
                        "✅ OEM Mode Activated",
                        f"OEM Service Mode activated successfully!\n\n"
                        f"Session timeout: {session_info['timeout_minutes']} minutes\n"
                        f"You can now modify all device configuration settings.\n\n"
                        f"⚠️ Changes to fiber diameter and LED model affect\n"
                        f"   calibration and measurement performance."
                    )
                    logger.info("✅ OEM service mode activated via GUI")
                else:
                    # Authentication failed
                    QMessageBox.critical(
                        self,
                        "❌ Authentication Failed",
                        "Incorrect OEM password.\n\n"
                        "Please contact Affinite Instruments for support."
                    )
                    logger.warning("❌ OEM authentication failed in GUI")

        except Exception as e:
            logger.error(f"OEM authentication error: {e}")
            QMessageBox.critical(self, "Error", f"Authentication error:\n{e}")

    def _lock_oem_mode(self: Self) -> None:
        """Lock OEM service mode."""
        try:
            reply = QMessageBox.question(
                self,
                "🔒 Lock OEM Mode",
                "Exit OEM Service Mode and return to User Mode?\n\n"
                "Critical settings will be locked again.",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.security.end_session()
                self.oem_mode_active = False
                self._update_security_ui()

                QMessageBox.information(
                    self,
                    "🔒 Locked",
                    "OEM Service Mode deactivated.\n"
                    "Critical settings are now locked."
                )
                logger.info("🔒 OEM service mode deactivated via GUI")

        except Exception as e:
            logger.error(f"OEM lock error: {e}")
            QMessageBox.critical(self, "Error", f"Lock error:\n{e}")

    def _update_security_ui(self: Self) -> None:
        """Update UI based on OEM authentication status."""
        # Check if session is still active
        if self.oem_mode_active and not self.security.is_session_active():
            self.oem_mode_active = False
            QMessageBox.warning(
                self,
                "⏱️ Session Expired",
                "OEM session has expired.\n"
                "Critical settings are now locked."
            )

        if self.oem_mode_active:
            # OEM MODE - Everything unlocked
            self.oem_status_label.setText("✅ Unlocked - OEM Service Mode")
            self.oem_status_label.setStyleSheet(
                "QLabel { color: #4CAF50; font-weight: bold; padding: 5px; }"
            )
            self.oem_unlock_btn.setVisible(False)
            self.oem_lock_btn.setVisible(True)

            # Enable all controls
            self.fiber_100um.setEnabled(True)
            self.fiber_200um.setEnabled(True)
            self.led_luminus.setEnabled(True)
            self.led_osram.setEnabled(True)

            logger.debug("🔓 OEM mode: All controls enabled")
        else:
            # USER MODE - Critical settings locked
            self.oem_status_label.setText("🔒 Locked - User Mode")
            self.oem_status_label.setStyleSheet(
                "QLabel { color: #f44336; font-weight: bold; padding: 5px; }"
            )
            self.oem_unlock_btn.setVisible(True)
            self.oem_lock_btn.setVisible(False)

            # Disable critical controls (fiber diameter and LED model)
            self.fiber_100um.setEnabled(False)
            self.fiber_200um.setEnabled(False)
            self.led_luminus.setEnabled(False)
            self.led_osram.setEnabled(False)

            logger.debug("🔒 User mode: Critical controls locked")


if __name__ == "__main__":
    """Test device settings widget."""
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    widget = DeviceSettingsWidget()
    widget.resize(600, 700)
    widget.show()
    app.exec()
