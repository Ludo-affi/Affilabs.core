"""Device Configuration Dialog

Extracted from affilabs_core_ui.py for better modularity.

Dialog to collect device configuration information (LED model, controller type,
fiber diameter, polarizer type, device ID) with optional EEPROM sync.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

class DeviceConfigDialog(QDialog):
    """Dialog to collect missing device configuration information."""

    def __init__(
        self,
        parent: QWidget | None = None,
        device_serial: str | None = None,
        controller_type: str = "",
        controller=None,
        device_config=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Device Configuration Required")
        self.setFixedWidth(500)
        self.setModal(True)
        self.controller_type = controller_type
        self.controller = controller  # For EEPROM sync
        self.device_config = device_config  # DeviceConfiguration instance

        # Apply modern styling with visible border
        self.setStyleSheet(
            "QDialog {"
            "  background: #FFFFFF;"
            "  border: 3px solid #007AFF;"
            "  border-radius: 12px;"
            "}"
            "QLabel {"
            "  color: #1D1D1F;"
            "  font-size: 13px;"
            "}",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Title
        title = QLabel("⚙️ Device Configuration")
        title.setStyleSheet(
            "font-size: 20px;font-weight: 600;color: #1D1D1F;",
        )
        layout.addWidget(title)

        # Description
        desc = QLabel(
            f"Please provide the following information for device:\n<b>{device_serial or 'Unknown'}</b>",
        )
        desc.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        desc.setStyleSheet(
            "font-size: 13px;color: #86868B;",
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Config source indicator (EEPROM vs JSON)
        self.config_source_label = QLabel()
        self.config_source_label.setStyleSheet(
            "font-size: 12px;"
            "color: #86868B;"
            "padding: 8px 12px;"
            "background: #F5F5F7;"
            "",
        )
        self._update_config_source_indicator()
        layout.addWidget(self.config_source_label)

        # Form layout
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Shared combo box styling
        combo_style = (
            "QComboBox {"
            "  padding: 8px 12px;"
            "  border: 1px solid rgba(0, 0, 0, 0.15);"
            "  border-radius: 8px;"
            "  background: #FFFFFF;"
            "  font-size: 13px;"
            "  color: #1D1D1F;"
            "  min-height: 20px;"
            "}"
            "QComboBox:hover {"
            "  border: 1px solid #007AFF;"
            "}"
            "QComboBox:focus {"
            "  border: 1px solid #007AFF;"
            "}"
            "QComboBox:disabled {"
            "  background: #F5F5F7;"
            "  color: #86868B;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 30px;"
            "  subcontrol-origin: padding;"
            "  subcontrol-position: center right;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 5px solid transparent;"
            "  border-right: 5px solid transparent;"
            "  border-top: 6px solid #86868B;"
            "  width: 0;"
            "  height: 0;"
            "}"
            "QComboBox QAbstractItemView {"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "  background: #FFFFFF;"
            "  selection-background-color: #007AFF;"
            "  selection-color: #FFFFFF;"
            "  padding: 4px;"
            "  outline: none;"
            "}"
            "QComboBox QAbstractItemView::item {"
            "  padding: 8px 12px;"
            "  border-radius: 4px;"
            "  color: #1D1D1F;"
            "  min-height: 24px;"
            "}"
            "QComboBox QAbstractItemView::item:hover {"
            "  background: #F5F5F7;"
            "}"
            "QComboBox QAbstractItemView::item:selected {"
            "  background: #007AFF;"
            "  color: #FFFFFF;"
            "}"
        )

        # Shared input styling
        input_style = (
            "QLineEdit {"
            "  padding: 6px 12px;"
            "  border: 1px solid rgba(0, 0, 0, 0.15);"
            "  border-radius: 8px;"
            "  background: #FFFFFF;"
            "  font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #007AFF;"
            "}"
        )

        # LED Model (LCW or OWW)
        self.led_model_combo = QComboBox()
        self.led_model_combo.addItems(["LCW", "OWW"])
        self.led_model_combo.setStyleSheet(combo_style)
        form.addRow("LED Model:", self.led_model_combo)

        # Controller Options (hardware types excluding pumps)
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["Arduino", "PicoP4SPR", "PicoEZSPR"])
        self.controller_combo.setStyleSheet(combo_style)

        # Pre-select based on detected controller type
        if self.controller_type in ["Arduino", "PicoP4SPR", "PicoEZSPR"]:
            index = self.controller_combo.findText(self.controller_type)
            if index >= 0:
                self.controller_combo.setCurrentIndex(index)

        # Connect change to update polarizer
        self.controller_combo.currentTextChanged.connect(self._on_controller_changed)
        form.addRow("Controller:", self.controller_combo)

        # Fiber Diameter (A=100, B=200)
        self.fiber_diameter_combo = QComboBox()
        self.fiber_diameter_combo.addItems(["A (100 µm)", "B (200 µm)"])
        self.fiber_diameter_combo.setStyleSheet(combo_style)
        form.addRow("Fiber Diameter:", self.fiber_diameter_combo)

        # Polarizer Type (barrel or circle, default circle for Arduino/PicoP4SPR)
        self.polarizer_type_combo = QComboBox()
        self.polarizer_type_combo.addItems(["circle", "barrel"])
        self.polarizer_type_combo.setStyleSheet(combo_style)

        # Set default based on controller
        self._update_polarizer_default()

        form.addRow("Polarizer:", self.polarizer_type_combo)

        # Device ID (detector serial number)
        self.device_id_input = QLineEdit()
        self.device_id_input.setPlaceholderText("Enter detector serial number")
        self.device_id_input.setText(
            device_serial or "",
        )  # Pre-fill with detected serial
        self.device_id_input.setStyleSheet(input_style)
        form.addRow("Device ID:", self.device_id_input)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  padding: 8px 20px;"
            "  background: #F5F5F7;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  color: #1D1D1F;"
            "}"
            "QPushButton:hover {"
            "  background: #E5E5E7;"
            "}",
        )
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Push to EEPROM button (only show if controller connected)
        if self.controller is not None:
            eeprom_btn = QPushButton("Push to EEPROM")
            eeprom_btn.setStyleSheet(
                "QPushButton {"
                "  padding: 8px 20px;"
                "  background: #FF9500;"
                "  border: none;"
                "  border-radius: 10px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  color: #FFFFFF;"
                "}"
                "QPushButton:hover {"
                "  background: #FF8000;"
                "}"
                "QPushButton:disabled {"
                "  background: #E5E5E7;"
                "  color: #86868B;"
                "}",
            )
            eeprom_btn.setToolTip(
                "Save configuration to device EEPROM for portable backup",
            )
            eeprom_btn.clicked.connect(self._on_push_to_eeprom)
            button_layout.addWidget(eeprom_btn)

        save_btn = QPushButton("Save Configuration")
        save_btn.setStyleSheet(
            "QPushButton {"
            "  padding: 8px 20px;"
            "  background: #007AFF;"
            "  border: none;"
            "  border-radius: 10px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: #FFFFFF;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}",
        )
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Add shadow effect (reduced blur to preserve border visibility)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 35))
        self.setGraphicsEffect(shadow)

    def _on_controller_changed(self, controller_text: str) -> None:
        """Update polarizer default when controller changes."""
        self.controller_type = controller_text
        self._update_polarizer_default()

    def _update_polarizer_default(self) -> None:
        """Set polarizer default based on controller type."""
        if self.controller_type in ["Arduino", "PicoP4SPR"]:
            self.polarizer_type_combo.setCurrentText("circle")
        elif self.controller_type == "PicoEZSPR":
            self.polarizer_type_combo.setCurrentText("barrel")

    def _update_config_source_indicator(self) -> None:
        """Update the config source indicator label."""
        if self.device_config is None:
            self.config_source_label.setText("ℹ️ New configuration")
            return

        if (
            hasattr(self.device_config, "loaded_from_eeprom")
            and self.device_config.loaded_from_eeprom
        ):
            self.config_source_label.setText("📦 Configuration loaded from EEPROM")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #FF9500;"
                "padding: 8px 12px;"
                "background: #FFF3E0;"
                "",
            )
        else:
            self.config_source_label.setText("💾 Configuration loaded from JSON file")
            self.config_source_label.setStyleSheet(
                "font-size: 12px;"
                "color: #34C759;"
                "padding: 8px 12px;"
                "background: #E8F5E9;"
                "",
            )

    def _on_push_to_eeprom(self) -> None:
        """Push current form configuration to EEPROM."""
        if self.controller is None:
            QMessageBox.warning(
                self,
                "No Controller",
                "Cannot push to EEPROM: No controller connected.",
            )
            return

        # Update device_config with current form values (if it exists)
        if self.device_config is not None:
            config_data = self.get_config_data()
            self.device_config.set_hardware_config(
                led_pcb_model=config_data["led_pcb_model"],
                optical_fiber_diameter_um=config_data["optical_fiber_diameter_um"],
                polarizer_type=config_data["polarizer_type"],
            )

        # Sync to EEPROM
        from affilabs.utils.logger import logger

        logger.info("Pushing configuration to EEPROM...")

        if self.device_config is not None:
            success = self.device_config.sync_to_eeprom(self.controller)
        else:
            # No device_config yet - create temporary EEPROM config from form
            QMessageBox.information(
                self,
                "Save First",
                "Please save the configuration to JSON first, then push to EEPROM.",
            )
            return

        # Show result
        if success:
            QMessageBox.information(
                self,
                "EEPROM Sync Complete",
                "✓ Configuration successfully pushed to device EEPROM.\n\n"
                "The device can now be used on other computers without reconfiguration.",
            )
            logger.info("✓ EEPROM sync successful")
        else:
            QMessageBox.warning(
                self,
                "EEPROM Sync Failed",
                "Failed to push configuration to EEPROM.\n\n"
                "Check the logs for details.",
            )
            logger.error("✗ EEPROM sync failed")

    def get_config_data(self) -> dict[str, Any]:
        """Get the configuration data from the form."""
        # Map LED model abbreviations to full names
        led_model_map = {
            "LCW": "luminus_cool_white",
            "OWW": "osram_warm_white",
        }

        # Extract fiber diameter from selection (e.g., "A (100 µm)" -> 100)
        fiber_text = self.fiber_diameter_combo.currentText()
        if "A" in fiber_text:
            fiber_diameter = 100
        elif "B" in fiber_text:
            fiber_diameter = 200
        else:
            fiber_diameter = 200  # Default

        # Get controller type
        controller_type = self.controller_combo.currentText()

        # Determine controller model name from type
        controller_model = "Raspberry Pi Pico P4SPR"  # Default
        if controller_type == "Arduino":
            controller_model = "Arduino P4SPR"
        elif controller_type == "PicoP4SPR":
            controller_model = "Raspberry Pi Pico P4SPR"
        elif controller_type == "PicoEZSPR":
            controller_model = "Raspberry Pi Pico EZSPR"

        return {
            "led_pcb_model": led_model_map.get(
                self.led_model_combo.currentText(),
                "luminus_cool_white",
            ),
            "optical_fiber_diameter_um": fiber_diameter,
            "polarizer_type": self.polarizer_type_combo.currentText(),
            "device_id": self.device_id_input.text().strip() or None,
            "controller_model": controller_model,
            "controller_type": controller_type,
        }
