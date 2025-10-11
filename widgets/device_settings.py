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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from utils.device_configuration import DeviceConfiguration
from utils.hardware_detection import HardwareDetector
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

    def __init__(self: Self, parent: QWidget | None = None) -> None:
        """Initialize device settings widget."""
        super().__init__(parent)

        # Load device configuration
        self.config = DeviceConfiguration()
        self.detector = HardwareDetector()

        # Create UI
        self._create_ui()
        self._load_current_settings()

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

        # Get frequency limits
        limits_4led = self.config.get_frequency_limits(4)
        limits_2led = self.config.get_frequency_limits(2)

        # Build display text
        display_text = f"""
        <b>Device Configuration:</b><br>
        <br>
        <b>Optical Fiber:</b> {fiber_diameter} µm<br>
        <b>LED PCB Model:</b> {led_model.replace('_', ' ').title()}<br>
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

            # Update configuration
            self.config.set_optical_fiber_diameter(fiber_diameter)
            self.config.set_led_pcb_model(led_model)

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
            QMessageBox.information(
                self,
                "Success",
                "Configuration saved successfully!\n\n"
                f"Optical Fiber: {fiber_diameter} µm\n"
                f"LED PCB: {led_model}"
            )

            logger.info(f"Device configuration saved: fiber={fiber_diameter}µm, led={led_model}")

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


if __name__ == "__main__":
    """Test device settings widget."""
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    widget = DeviceSettingsWidget()
    widget.resize(600, 700)
    widget.show()
    app.exec()
