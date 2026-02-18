"""DeviceStatusMixin — device power, hardware scanning, subunit readiness, and status management.

Extracted from affilabs/affilabs_core_ui.py (AffilabsCoreUI class).

Methods (17 + 1 helper):
    _update_power_button_style          — Update power button appearance based on state
    _handle_power_click                 — Handle power button click (connect/disconnect)
    set_power_state                     — Set power button state from external controller
    _set_power_button_state             — Alias for set_power_state (backward compat)
    enable_controls                     — Enable record/pause buttons after calibration
    _reset_subunit_status               — Reset all subunit status indicators
    _handle_scan_hardware               — Handle hardware scan button click
    _on_hardware_scan_complete          — Reset scan button after scan completes
    _handle_add_hardware                — Handle Add Hardware button (peripheral scan)
    update_hardware_status              — Update hardware status display
    _update_subunit_readiness_from_status — Update subunit readiness from status
    _set_subunit_visibility             — Show or hide a subunit status row
    _set_subunit_status                 — Set the status of a specific subunit
    _set_optics_warning                 — Apply warning background to sensorgram
    _clear_optics_warning               — Clear warning background from sensorgram
    _update_operation_modes             — Update available operation modes
    _update_scan_button_style           — Update scan button style (deprecated)
    _handle_debug_log_download          — Download debug log to current directory
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from affilabs.utils.logger import logger


class DeviceStatusMixin:
    """Mixin for device power control, hardware scanning, subunit readiness, and status management.

    Mixed into AffilabsMainWindow. Expects the host class to provide:
    - self.power_btn, self.record_btn, self.pause_btn
    - self.sidebar (AffilabsSidebar with subunit_status, hw_device_labels, etc.)
    - self.full_timeline_graph
    - self.power_on_requested / self.power_off_requested signals
    - self.show_connecting_indicator(bool)
    """

    def _update_power_button_style(self):
        """Update power button appearance based on current state with 3D effect."""
        state = self.power_btn.property("powerState")

        if state == "disconnected":
            # Red - Idle, ready to connect
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FF3B30;"
                "  color: white;"
                "  border: 1px solid #E62817;"
                "  border-radius: 18px;"
                "}"
                "QPushButton:hover {"
                "  background: #E62817;"
                "  border: 1px solid #CC1F12;"
                "}",
            )
            self.power_btn.setToolTip("Power On Device (Ctrl+P)\nRed = Idle, Click to Connect")
        elif state == "searching":
            # Yellow - Searching for device
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: white;"
                "  border: 1px solid #FFB800;"
                "  border-radius: 18px;"
                "}"
                "QPushButton:hover {"
                "  background: #FFD700;"
                "  border: 1px solid #FFC700;"
                "}",
            )
            self.power_btn.setToolTip("Searching for Device...\nClick to CANCEL search")
        elif state == "connected":
            # Green - Device powered and connected
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: 1px solid #2FB350;"
                "  border-radius: 18px;"
                "}"
                "QPushButton:hover {"
                "  background: #30B54A;"
                "  border: 1px solid #299542;"
                "}",
            )
            self.power_btn.setToolTip(
                "Power Off Device (Ctrl+P)\nGreen = Device Connected\nClick to power off",
            )

    def _handle_power_click(self):
        """Handle power button click - connects/disconnects hardware.

        Button behavior:
        - DISCONNECTED (gray): Click to start connection → SEARCHING (yellow)
        - SEARCHING (yellow): Click to cancel search → DISCONNECTED (gray)
        - CONNECTED (green): Click to disconnect → DISCONNECTED (gray)
        """
        current_state = self.power_btn.property("powerState")
        logger.info(f"Power button clicked: current_state={current_state}")

        if current_state == "disconnected":
            # Start hardware connection
            logger.debug("Starting hardware connection...")

            # Update UI state to searching IMMEDIATELY
            self.power_btn.setProperty("powerState", "searching")
            self._update_power_button_style()

            # Show connecting indicator
            self.show_connecting_indicator(True)

            # FORCE immediate visual update (process all pending events)
            from PySide6.QtCore import QCoreApplication

            self.power_btn.repaint()  # Force immediate repaint
            QCoreApplication.processEvents()  # Process all pending UI events

            logger.debug(
                "Power button state: searching",
            )

            # Emit signal to Application layer (clean architecture)
            logger.debug("Emitting power_on_requested signal...")
            self.power_on_requested.emit()
            logger.debug("Signal emitted")

        elif current_state == "searching":
            # Button is inactive while searching - ignore clicks
            logger.debug(
                "Button clicked during search - ignoring",
            )
            return  # Do nothing while hardware search is active

        elif current_state == "connected":
            # Power OFF: Show warning dialog
            from PySide6.QtWidgets import QMessageBox

            warning = QMessageBox(self)
            warning.setWindowTitle("Power Off Device")
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setText("Are you sure you want to disconnect the device?")
            warning.setInformativeText("All hardware connections will be closed.")
            warning.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)

            # Style the warning dialog
            warning.setStyleSheet(
                "QMessageBox {"
                "  background: {Colors.BACKGROUND_WHITE};"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QLabel {"
                "  color: {Colors.PRIMARY_TEXT};"
                "  font-size: 13px;"
                "}"
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 10px;"
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
                "}",
            )

            result = warning.exec()

            if result == QMessageBox.StandardButton.Yes:
                # User confirmed power off
                logger.debug("Power OFF: Disconnecting hardware...")
                self.power_btn.setProperty("powerState", "disconnected")
                self._update_power_button_style()
                self.power_btn.setChecked(False)

                # Reset all subunit status to "Not Ready"
                self._reset_subunit_status()

                # Emit signal to disconnect hardware
                if hasattr(self, "power_off_requested"):
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

        # Show/hide connecting indicator based on state
        self.show_connecting_indicator(state == "searching")

        # Reset subunit status whenever power state is not "connected"
        if state in ["disconnected", "searching"]:
            self._reset_subunit_status()

    def _set_power_button_state(self, state: str):
        """Alias for set_power_state for backward compatibility."""
        self.set_power_state(state)

    def enable_controls(self) -> None:
        """Enable record and pause buttons after calibration completes."""
        try:
            logger.info("✅ Enabling recording controls (calibration complete)")
            self.record_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.record_btn.setToolTip("Start Recording\n(Click to begin saving data)")
            self.pause_btn.setToolTip(
                "Pause Live Acquisition\n(Click to temporarily stop data flow)",
            )
        except Exception as e:
            # Suppress Qt threading warnings that are false positives
            if "QTextDocument" not in str(e) and "different thread" not in str(e):
                raise

    def _reset_subunit_status(self) -> None:
        """Reset all subunit status indicators to 'Not Ready' state."""
        for subunit_name in ["Sensor", "Optics", "Fluidics"]:
            if subunit_name in self.sidebar.subunit_status:
                indicator = self.sidebar.subunit_status[subunit_name]["indicator"]
                status_label = self.sidebar.subunit_status[subunit_name]["status_label"]

                # Gray indicator and "Not Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: {Colors.SECONDARY_TEXT};"  # Gray
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: {Colors.SECONDARY_TEXT};"  # Gray
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )

        # Also disable all operation modes when disconnecting
        # Use empty status dict to indicate no hardware connected
        self._update_operation_modes({})

    def _handle_scan_hardware(self) -> None:
        """Handle hardware scan button click - trigger real hardware scan."""
        # Don't scan if already scanning
        if self.sidebar.scan_btn.property("scanning"):
            return

        logger.info("[SCAN] User requested hardware scan...")
        self.sidebar.set_scan_state(True)  # Use encapsulated method

        # Emit signal to trigger actual hardware scan in Application
        # The Application class will handle the actual hardware manager scan
        if hasattr(self, "app") and self.app:
            self.app.hardware_mgr.scan_and_connect()
        else:
            logger.warning("No application reference - cannot trigger hardware scan")
            # Reset button state after 1 second
            QTimer.singleShot(1000, lambda: self.sidebar.set_scan_state(False))

    def _on_hardware_scan_complete(self) -> None:
        """Called when hardware scan completes - reset scan button."""
        self.sidebar.set_scan_state(False)  # Use encapsulated method
        logger.debug("Hardware scan complete - button reset")

    def _handle_add_hardware(self) -> None:
        """Handle Add Hardware button click - scan for peripheral devices only."""
        logger.info("🔌 User requested peripheral device scan (Affipump)...")

        # Check if application and kinetic manager are available
        if hasattr(self, "app") and self.app:
            if hasattr(self.app, "kinetic_mgr") and self.app.kinetic_mgr:
                try:
                    # Scan for Affipump
                    self.app.kinetic_mgr.scan_for_pump()
                    logger.info("✓ Peripheral scan initiated")
                except Exception as e:
                    logger.error(f"Failed to scan for peripherals: {e}")
                    from affilabs.ui.ui_message import error as ui_error
                    ui_error(
                        self,
                        "Peripheral Scan Error",
                        f"Failed to scan for peripheral devices:\\n\\n{e}",
                    )
            else:
                logger.warning("Kinetic manager not available - peripheral scan unavailable")
                from affilabs.ui.ui_message import warning as ui_warning
                ui_warning(
                    self,
                    "Feature Unavailable",
                    "Peripheral device scanning is not available.\\n\\n"
                    "Kinetic manager is not initialized.",
                )
        else:
            logger.warning("No application reference - cannot scan for peripherals")

    def update_hardware_status(self, status: dict[str, Any]) -> None:
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
        # ONLY show the 5 valid hardware types: P4SPR, P4PRO, ezSPR, KNX, AffiPump
        devices = []

        ctrl_type = status.get("ctrl_type")

        # Map internal names to display names
        # Valid hardware: P4SPR, P4PRO, P4PROPLUS, ezSPR, KNX, AffiPump
        # Common pairings: P4SPR+KNX, P4PRO+AffiPump, P4PROPLUS (internal pumps)
        CONTROLLER_DISPLAY_NAMES = {
            "PicoP4SPR": "P4SPR",
            "P4SPR": "P4SPR",
            "PicoP4PRO": "P4PRO",
            "P4PRO": "P4PRO",
            "P4PROPLUS": "P4PRO+",
            "PicoP4PROPLUS": "P4PRO+",
            "PicoEZSPR": "P4PRO",  # PicoEZSPR hardware = P4PRO product
            "EZSPR": "ezSPR",
            "ezSPR": "ezSPR",
        }

        KNX_DISPLAY_NAMES = {
            "KNX": "KNX",
            "KNX2": "KNX",
            "PicoKNX2": "KNX",
        }

        # Controller (P4SPR, P4PRO, ezSPR)
        if ctrl_type:
            display_name = CONTROLLER_DISPLAY_NAMES.get(ctrl_type)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown controller - log warning but don't display
                logger.warning(
                    f"⚠️ Unknown controller type '{ctrl_type}' - not displayed in Hardware Connected",
                )

        # Kinetic Controller (KNX)
        knx_type = status.get("knx_type")
        if knx_type:
            display_name = KNX_DISPLAY_NAMES.get(knx_type)
            if display_name:
                devices.append(display_name)
            else:
                # Unknown kinetic type - log warning but don't display
                logger.warning(
                    f"⚠️ Unknown kinetic type '{knx_type}' - not displayed in Hardware Connected",
                )

        # Pump (AffiPump) - only show if external pump actually connected
        # Don't show "AffiPump" for P4PROPLUS internal pumps
        if status.get("pump_connected"):
            # Check if this is external AffiPump or P4PROPLUS internal pumps
            # P4PROPLUS sets pump_connected=True but shouldn't display as "AffiPump"
            is_p4proplus_internal = ctrl_type in ["P4PROPLUS", "PicoP4PROPLUS"]
            if not is_p4proplus_internal:
                devices.append("AffiPump")

        # Update device labels
        for i, label in enumerate(self.sidebar.hw_device_labels):
            if i < len(devices):
                label.setText(f"● {devices[i]}")
                label.setVisible(True)
            else:
                label.setVisible(False)

        # Show/hide "no devices" message
        self.sidebar.hw_no_devices.setVisible(len(devices) == 0)

        # Show "Add Hardware" button only when core module is connected (ctrl_type exists)
        # This allows adding peripherals like Affipump after core connection
        self.sidebar.add_hardware_btn.setVisible(bool(ctrl_type))

        # Update subunit readiness based on actual verification
        self._update_subunit_readiness_from_status(status)

        # Update operation mode availability based on hardware
        self._update_operation_modes(status)

    def _update_subunit_readiness_from_status(self, status: dict[str, Any]) -> None:
        """Update subunit readiness based on hardware verification results."""
        # Sensor readiness
        if "sensor_ready" in status:
            self._set_subunit_status("Sensor", status["sensor_ready"])

        # Optics readiness
        if "optics_ready" in status:
            optics_ready = status["optics_ready"]
            optics_details = {
                "failed_channels": status.get("optics_failed_channels", []),
                "maintenance_channels": status.get("optics_maintenance_channels", []),
            }
            self._set_subunit_status("Optics", optics_ready, details=optics_details)

        # Fluidics readiness - only show for flow-capable controllers
        if "fluidics_ready" in status:
            fluidics_ready = status["fluidics_ready"]
            self._set_subunit_status("Fluidics", fluidics_ready)
            # Show the fluidics row
            self._set_subunit_visibility("Fluidics", True)
        else:
            # Hide the fluidics row for static-only controllers (P4SPR)
            self._set_subunit_visibility("Fluidics", False)

    def _set_subunit_visibility(self, subunit_name: str, visible: bool) -> None:
        """Show or hide a subunit status row.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            visible: True to show, False to hide
        """
        if subunit_name in self.sidebar.subunit_status:
            # Get the container widget for the entire row
            container = self.sidebar.subunit_status[subunit_name].get("container")
            if container:
                container.setVisible(visible)

    def _set_subunit_status(
        self,
        subunit_name: str,
        is_ready: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Set the status of a specific subunit.

        Args:
            subunit_name: Name of subunit (Sensor, Optics, Fluidics)
            is_ready: True if ready, False otherwise
            details: Optional dict with 'failed_channels' and 'maintenance_channels' for Optics

        """
        if subunit_name in self.sidebar.subunit_status:
            indicator = self.sidebar.subunit_status[subunit_name]["indicator"]
            status_label = self.sidebar.subunit_status[subunit_name]["status_label"]

            if is_ready:
                # Green indicator and "Ready" text
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    "color: #34C759;"  # Green
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    "color: #34C759;"  # Green
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                # Clear optics warning if it was active
                if subunit_name == "Optics" and hasattr(self, "_optics_warning_active"):
                    self._clear_optics_warning()
            else:
                # Red indicator for Not Ready (all subunits use red for consistency)
                color = "#FF3B30"
                indicator.setStyleSheet(
                    "font-size: 14px;"
                    f"color: {color};"
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                status_label.setText("Not Ready")
                status_label.setStyleSheet(
                    "font-size: 12px;"
                    f"color: {color};"
                    "background: {Colors.TRANSPARENT};"
                    "font-family: {Fonts.SYSTEM};",
                )
                # Store optics status details for warning message
                if subunit_name == "Optics" and details:
                    self._optics_status_details = details

            from affilabs.utils.logger import logger

            logger.debug(f"{subunit_name}: {'Ready' if is_ready else 'Not Ready'}")

    def _set_optics_warning(self) -> None:
        """Apply light red background to live sensorgram when proceeding with unready optics."""
        # Only set warning if we actually have optics issues (not just unverified)
        if (
            not hasattr(self, "_optics_status_details")
            or not self._optics_status_details
        ):
            from affilabs.utils.logger import logger

            logger.debug(
                "_set_optics_warning called but no optics issues detected - skipping red background",
            )
            return

        if hasattr(self, "full_timeline_graph") and self.full_timeline_graph:
            self.full_timeline_graph.setBackground("#FFE5E5")  # Light red
            self._optics_warning_active = True

            # Log warning with details
            if self._optics_status_details:
                failed = self._optics_status_details.get("failed_channels", [])
                maintenance = self._optics_status_details.get(
                    "maintenance_channels",
                    [],
                )

                if failed or maintenance:  # Only warn if there are actual problems
                    failed_str = (
                        ", ".join([ch.upper() for ch in failed]) if failed else "none"
                    )
                    maint_str = (
                        ", ".join([ch.upper() for ch in maintenance])
                        if maintenance
                        else "none"
                    )

                    from affilabs.utils.logger import logger

                    logger.warning(
                        f"⚠️ Optics NOT ready: calibration failed for channels [{failed_str}], maintenance required for channels [{maint_str}]",
                    )
                    logger.warning(
                        "   Live sensorgram background set to light red - please resolve optics issues",
                    )

    def _clear_optics_warning(self) -> None:
        """Clear light red background from live sensorgram when optics become ready."""
        if (
            hasattr(self, "full_timeline_graph")
            and self.full_timeline_graph
            and self._optics_warning_active
        ):
            self.full_timeline_graph.setBackground("#FFFFFF")  # White
            self._optics_warning_active = False
            self._optics_status_details = None

            from affilabs.utils.logger import logger

            logger.debug("Optics ready - sensorgram background restored to normal")

    def _update_operation_modes(self, status: dict[str, Any]) -> None:
        """Update available operation modes based on hardware type."""
        ctrl_type = status.get("ctrl_type", "")
        has_pump = status.get("pump_connected", False)
        detector_ready = status.get("sensor_ready", False)
        pcb_ready = status.get("optics_ready", False)

        from affilabs.utils.logger import logger

        # Determine if static mode should be available
        # Static mode is available if we have detector AND PCB (regardless of pump)
        static_available = detector_ready and pcb_ready

        # Flow mode requires calibration to be completed (not just pump detection)
        # During initial connection, flow indicators stay grey until calibration completes
        # After calibration, flow_available will be set based on pump presence
        # For P4PROPLUS (internal pumps) and other flow controllers, still needs calibration
        flow_available = status.get("flow_calibrated", False)  # Enabled after calibration completes

        logger.debug(f"Operation modes: ctrl={ctrl_type} static={static_available} flow={flow_available} pump={has_pump}")

        # P4SPR static device - only Static mode
        # Update UI indicators
        if hasattr(self.sidebar, "set_operation_mode_availability"):
            self.sidebar.set_operation_mode_availability(static_available, flow_available)

    def _update_scan_button_style(self) -> None:
        """Update scan button style based on scanning state.

        DEPRECATED: State management moved to sidebar.set_scan_state().
        Kept for backward compatibility only.
        """
        is_scanning = self.sidebar.scan_btn.property("scanning")
        self.sidebar.set_scan_state(is_scanning)

    def _handle_debug_log_download(self) -> None:
        """Handle debug log download button click - automatically downloads to current directory."""
        import datetime
        import os
        import shutil

        from PySide6.QtWidgets import QMessageBox

        try:
            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"AffiLabs_debug_log_{timestamp}.txt"

            # Save to current working directory
            dest_path = os.path.join(os.getcwd(), filename)

            # Source log file path (from logger.py configuration)
            from settings import ROOT_DIR
            source_log = os.path.join(ROOT_DIR, "logfile.txt")

            # Copy the actual log file
            if os.path.exists(source_log):
                shutil.copy2(source_log, dest_path)
                logger.info(f"Debug log downloaded to: {dest_path}")
            else:
                # If source log doesn't exist, create a minimal log
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(f"Affilabs.core Debug Log\n")
                    f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Note: Main log file not found at {source_log}\n")
                logger.warning(f"Source log not found, created minimal log at: {dest_path}")

            # Show success message with option to open folder
            msg = QMessageBox(self)
            msg.setWindowTitle("Debug Log Downloaded")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Debug log downloaded successfully")
            msg.setInformativeText(
                f"File saved to:\n{dest_path}\n\n"
                "Click OK to open the folder."
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            msg.setStyleSheet(
                "QMessageBox {"
                "  background: {Colors.BACKGROUND_WHITE};"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QLabel {"
                "  color: {Colors.PRIMARY_TEXT};"
                "  font-size: 13px;"
                "}"
                "QPushButton {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 10px;"
                "  padding: 6px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  min-width: 60px;"
                "  min-height: 28px;"
                "}"
                "QPushButton:hover {"
                "  background: #3A3A3C;"
                "}",
            )
            result = msg.exec()

            # Open folder if user clicked OK
            if result == QMessageBox.StandardButton.Ok:
                try:
                    folder_path = os.path.dirname(os.path.abspath(dest_path))
                    os.startfile(folder_path)
                except Exception as e:
                    logger.error(f"Could not open folder: {e}")

        except Exception as e:
            # Show error message
            error_msg = QMessageBox(self)
            error_msg.setWindowTitle("Error")
            error_msg.setIcon(QMessageBox.Icon.Critical)
            error_msg.setText("Failed to download debug log")
            error_msg.setInformativeText(f"Error: {e!s}")
            error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_msg.setStyleSheet(
                "QMessageBox {"
                "  background: {Colors.BACKGROUND_WHITE};"
                "}"
                "QPushButton {"
                "  background: #FF3B30;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 10px;"
                "  padding: 6px 16px;"
                "}",
            )
            error_msg.exec()

            logger.error(f"Error downloading debug log: {e}")
