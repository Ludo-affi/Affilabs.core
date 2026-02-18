"""SettingsMixin — Hardware settings, advanced parameters, and polarizer control.

Extracted from affilabs/affilabs_core_ui.py (MainWindowPrototype).

Methods included (9 total):
    Unit toggle:
        _on_unit_changed                  — toggles between RU and nm units

    Settings load/apply:
        _load_current_settings            — loads servo/LED settings from config to UI
        _apply_settings                   — validates and emits settings to application layer

    Advanced settings:
        open_advanced_settings            — opens AdvancedSettingsDialog with current params
        eventFilter                       — detects Control+10-click on advanced settings button
        _reset_click_count                — resets click counter after inactivity
        _unlock_advanced_params           — unlocks advanced parameters and dev mode for 60 min
        _lock_advanced_params             — locks advanced parameters after timeout

    Polarizer control:
        _toggle_polarizer_mode            — toggles polarizer between S and P modes
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QDialog, QMessageBox

from affilabs.dialogs.advanced_settings_dialog import AdvancedSettingsDialog

logger = logging.getLogger(__name__)


class SettingsMixin:
    """Mixin providing hardware settings, advanced parameters, and polarizer control.

    Expects the host class to provide:
        - self.device_config          (DeviceConfig)
        - self.hardware_mgr           (HardwareManager)
        - self.sidebar                (AffilabsSidebar)
        - self.app                    (Application)
        - self.ru_btn, self.nm_btn    (QRadioButton)
        - self.s_position_input, self.p_position_input  (QLineEdit)
        - self.channel_a/b/c/d_input  (QLineEdit)
        - self.polarizer_toggle_btn   (QPushButton)
        - self.apply_led_settings_requested  (Signal(dict))
        - self.advanced_params_click_count   (int)
        - self.advanced_params_unlocked      (bool)
        - self.advanced_params_timer         (QTimer | None)
        - self.click_reset_timer             (QTimer)
        - self._init_pipeline_selector()     (method)
    """

    def _on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units."""
        # This will be connected to main_simplified handler
        if checked and self.ru_btn.isChecked():
            logger.info("Unit changed to RU")
        elif checked and self.nm_btn.isChecked():
            logger.info("Unit changed to nm")

    def _load_current_settings(self, show_warnings: bool = True):
        """Load current hardware settings into Hardware Configuration.

        Loads:
        - Servo positions (S/P) from device_config (immutable, set at init)
        - LED brightness (A/B/C/D) preferring calibrated P-mode final brightness,
          falling back to current hardware state or device config

        Args:
            show_warnings: If True, show warning dialogs when config unavailable.
                          Set to False during UI init to avoid spurious warnings.
        """
        try:
            if not self.device_config:
                # Silent return during init; only warn if explicitly requested
                if show_warnings:
                    logger.warning(
                        "Device config not available - cannot load current settings",
                    )
                    QMessageBox.warning(
                        self,
                        "Settings Not Available",
                        "Device configuration is not available. Please connect to hardware first.",
                    )
                return

            # Load servo positions from device_config (set at hardware init)
            servo_positions = self.device_config.get_servo_positions()
            s_pos = servo_positions.get("s", 0)
            p_pos = servo_positions.get("p", 0)

            # Prefer calibrated P-mode final intensities when available
            led_intensities = {"a": 0, "b": 0, "c": 0, "d": 0}
            source = ""
            try:
                if hasattr(self, "app") and self.app and hasattr(self.app, "data_mgr") and self.app.data_mgr:
                    cd = getattr(self.app.data_mgr, "calibration_data", None)
                    if cd and hasattr(cd, "p_mode_intensities") and cd.p_mode_intensities:
                        led_intensities = dict(cd.p_mode_intensities)
                        source = "calibration"
            except Exception as e:
                logger.warning(f"Failed to read calibrated P-mode brightness: {e}")

            # Fallback to current hardware or device config
            if not source:
                if self.hardware_mgr and self.hardware_mgr.ctrl:
                    try:
                        led_intensities = self.hardware_mgr.ctrl.get_all_led_intensities()
                        source = "hardware"
                    except Exception as e:
                        logger.warning(
                            f"Failed to query LED brightness from hardware: {e} - using config values",
                        )
                        led_intensities = self.device_config.get_led_intensities()
                        source = "config"
                else:
                    logger.info("Hardware not connected - loading LED brightness from config")
                    led_intensities = self.device_config.get_led_intensities()
                    source = "config"

            # Populate UI fields
            self.sidebar.load_hardware_settings(
                s_pos=s_pos,
                p_pos=p_pos,
                led_a=led_intensities.get("a", 0),
                led_b=led_intensities.get("b", 0),
                led_c=led_intensities.get("c", 0),
                led_d=led_intensities.get("d", 0),
            )

            logger.debug(
                f"Loaded current settings: S={s_pos}, P={p_pos}, LEDs={led_intensities} (source={source})",
            )

            # Initialize pipeline selector to current configuration
            self._init_pipeline_selector()

        except Exception as e:
            logger.error(f"Error loading current settings: {e}")
            QMessageBox.critical(
                self,
                "Error Loading Settings",
                f"Failed to load current settings: {e!s}",
            )

    def eventFilter(self, obj, event):
        """Event filter to detect Control+10-click on advanced settings button."""
        if (
            obj == self.sidebar.advanced_settings_btn
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            # Check if Control key is held
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.advanced_params_click_count += 1

                # Reset click count after 2 seconds of inactivity
                self.click_reset_timer.start(2000)

                if self.advanced_params_click_count >= 10:
                    self._unlock_advanced_params()
                    self.advanced_params_click_count = 0
                    return True  # Consume the event

        return super().eventFilter(obj, event)

    def _reset_click_count(self):
        """Reset the click counter after inactivity."""
        self.advanced_params_click_count = 0

    def _unlock_advanced_params(self):
        """Unlock advanced parameters and enable dev mode for 60 minutes."""
        import os

        self.advanced_params_unlocked = True

        # Enable dev mode environment variable
        os.environ["AFFILABS_DEV"] = "1"

        # Show confirmation message
        QMessageBox.information(
            self,
            "Advanced Parameters Unlocked",
            "Advanced parameters tab and developer mode are now enabled for 60 minutes.",
        )

        # Set timer to lock after 60 minutes
        if self.advanced_params_timer is None:
            self.advanced_params_timer = QTimer()
            self.advanced_params_timer.setSingleShot(True)
            self.advanced_params_timer.timeout.connect(self._lock_advanced_params)

        self.advanced_params_timer.start(60 * 60 * 1000)  # 60 minutes in milliseconds

        logger.info("Advanced parameters and dev mode unlocked for 60 minutes")

    def _lock_advanced_params(self):
        """Lock advanced parameters and disable dev mode after timeout."""
        import os

        self.advanced_params_unlocked = False

        # Disable dev mode environment variable
        if "AFFILABS_DEV" in os.environ:
            del os.environ["AFFILABS_DEV"]

        logger.info("Advanced parameters and dev mode locked after timeout")

    def open_advanced_settings(self):
        """Open the advanced settings dialog."""
        try:
            dialog = AdvancedSettingsDialog(
                self,
                unlocked=getattr(self, "advanced_params_unlocked", False),
            )
        except Exception as e:
            logger.error(f"Failed to create AdvancedSettingsDialog: {e}")
            return

        # Load current settings
        if hasattr(dialog, "ru_btn"):
            dialog.ru_btn.setChecked(
                self.ru_btn.isChecked() if hasattr(self, "ru_btn") else True,
            )
        if hasattr(dialog, "nm_btn"):
            dialog.nm_btn.setChecked(
                self.nm_btn.isChecked() if hasattr(self, "nm_btn") else False,
            )

        # Load calibration parameters if available
        if hasattr(self, "app") and self.app and hasattr(self.app, "data_mgr") and self.app.data_mgr:
            calibration_data = getattr(self.app.data_mgr, "calibration_data", None)
            if calibration_data:
                dialog.load_calibration_params(calibration_data)
                logger.info("✓ Loaded calibration parameters into Advanced Settings")

        # Load device info if available
        if self.device_config:
            device_serial = self.device_config.get_serial_number() if hasattr(self.device_config, "get_serial_number") else "Not detected"
            dialog.load_device_info(serial=device_serial)

        # Load pump corrections if available
        if hasattr(self, "app") and self.app and hasattr(self.app, "hardware_mgr"):
            if hasattr(dialog, "load_pump_corrections"):
                dialog.load_pump_corrections(self.app.hardware_mgr)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply settings
            if hasattr(self, "ru_btn"):
                self.ru_btn.setChecked(dialog.ru_btn.isChecked())
                self.nm_btn.setChecked(dialog.nm_btn.isChecked())

            logger.info("Advanced settings applied")

    def _toggle_polarizer_mode(self):
        """Toggle polarizer between S and P modes."""
        try:
            if not hasattr(self, "app") or not self.app:
                logger.warning("Application not connected")
                return

            if not self.app.hardware_mgr or not self.app.hardware_mgr.ctrl:
                logger.warning("Controller not connected")
                return

            ctrl = self.app.hardware_mgr.ctrl

            # Get current mode from button text
            current_text = self.polarizer_toggle_btn.text()

            if "S" in current_text:
                # Currently in S, switch to P
                ctrl.set_mode("p")
                self.polarizer_toggle_btn.setText("Position: P")
                logger.info("✅ Switched to P-mode")
            else:
                # Currently in P, switch to S
                ctrl.set_mode("s")
                self.polarizer_toggle_btn.setText("Position: S")
                logger.info("✅ Switched to S-mode")

        except Exception as e:
            logger.error(f"Failed to toggle polarizer: {e}")
            QMessageBox.warning(self, "Error", f"Failed to toggle polarizer: {e}")

    def _apply_settings(self):
        """Apply polarizer and LED settings from the Settings tab.

        ARCHITECTURE: Signal-based communication (UI → Application)
        UI validates input and emits signal with settings dict.
        Application layer handles business logic (hardware access, config save).
        """
        try:
            logger.info("🔧 UI: Parsing settings...")

            # Get polarizer positions
            s_pos_text = self.s_position_input.text()
            p_pos_text = self.p_position_input.text()

            # Get LED intensities
            led_a_text = self.channel_a_input.text()
            led_b_text = self.channel_b_input.text()
            led_c_text = self.channel_c_input.text()
            led_d_text = self.channel_d_input.text()

            # Parse and validate
            try:
                s_pos = int(s_pos_text) if s_pos_text else None
                p_pos = int(p_pos_text) if p_pos_text else None
                led_a = int(led_a_text) if led_a_text else None
                led_b = int(led_b_text) if led_b_text else None
                led_c = int(led_c_text) if led_c_text else None
                led_d = int(led_d_text) if led_d_text else None
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Please enter valid integers: {e}",
                )
                return

            # Validate ranges
            if s_pos is not None and not (0 <= s_pos <= 255):
                QMessageBox.warning(self, "Invalid Range", "S position must be 0-255")
                return
            if p_pos is not None and not (0 <= p_pos <= 255):
                QMessageBox.warning(self, "Invalid Range", "P position must be 0-255")
                return

            for led_val, name in [
                (led_a, "A"),
                (led_b, "B"),
                (led_c, "C"),
                (led_d, "D"),
            ]:
                if led_val is not None and not (0 <= led_val <= 255):
                    QMessageBox.warning(
                        self,
                        "Invalid Range",
                        f"LED {name} must be 0-255",
                    )
                    return

            # Build settings dict (UI layer responsibility: parse and validate)
            settings = {
                "s_pos": s_pos,
                "p_pos": p_pos,
                "led_a": led_a,
                "led_b": led_b,
                "led_c": led_c,
                "led_d": led_d,
            }

            # Emit signal - Application layer handles business logic
            # This respects HAL architecture: UI → Application → Hardware
            logger.info("🔧 UI: Emitting apply_led_settings_requested signal")
            self.apply_led_settings_requested.emit(settings)
            logger.info("✅ Settings saved to device config")

            # Note: Message boxes removed - visual feedback now via button style change only
            # LED brightness updates are now live (no need for confirmation dialogs)

        except Exception as e:
            logger.error(f"❌ Failed to apply settings: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to apply settings: {e}")
