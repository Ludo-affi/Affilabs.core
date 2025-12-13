"""Status Presenter

Handles all hardware status UI updates for the sidebar and status displays.
Extracted from AffilabsMainWindow to follow Presenter Pattern and improve testability.
"""

from typing import Optional, Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from affilabs_core_ui import AffilabsMainWindow


class StatusPresenter:
    """Presenter for hardware status updates.

    Manages:
    - Hardware connection status display
    - Subunit readiness indicators (Sensor, Optics, Fluidics)
    - Operation mode availability
    - Scan button state
    - Power button styling
    """

    # Display name mappings for hardware
    CONTROLLER_DISPLAY_NAMES = {
        'PicoP4SPR': 'P4SPR',
        'P4SPR': 'P4SPR',
        'PicoP4PRO': 'P4PRO',
        'P4PRO': 'P4PRO',
        'PicoEZSPR': 'P4PRO',  # PicoEZSPR hardware = P4PRO product
        'EZSPR': 'ezSPR',
        'ezSPR': 'ezSPR'
    }

    KNX_DISPLAY_NAMES = {
        'KNX': 'KNX',
        'KNX2': 'KNX',
        'PicoKNX2': 'KNX'
    }

    def __init__(self, main_window: 'AffilabsMainWindow'):
        """Initialize presenter with reference to main window.

        Args:
            main_window: The AffilabsMainWindow instance containing status widgets
        """
        self.window = main_window

    def update_hardware_status(self, status: Dict[str, Any]) -> None:
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
                - optics_failed_channels: List of failed LED channels
                - optics_maintenance_channels: List of channels needing maintenance
        """
        # Build list of connected devices (P4SPR, P4PRO, ezSPR, KNX, AffiPump)
        devices = []

        # Controller (P4SPR, P4PRO, ezSPR)
        ctrl_type = status.get('ctrl_type')
        if ctrl_type:
            display_name = self.CONTROLLER_DISPLAY_NAMES.get(ctrl_type)
            if display_name:
                devices.append(display_name)
            else:
                from affilabs.utils.logger import logger
                logger.warning(f"⚠️ Unknown controller type '{ctrl_type}' - not displayed")

        # Kinetic Controller (KNX)
        knx_type = status.get('knx_type')
        if knx_type:
            display_name = self.KNX_DISPLAY_NAMES.get(knx_type)
            if display_name:
                devices.append(display_name)
            else:
                from affilabs.utils.logger import logger
                logger.warning(f"⚠️ Unknown kinetic type '{knx_type}' - not displayed")

        # Pump (AffiPump)
        if status.get('pump_connected'):
            devices.append("AffiPump")

        # Update device labels in sidebar
        if hasattr(self.window, 'sidebar'):
            for i, label in enumerate(self.window.sidebar.hw_device_labels):
                if i < len(devices):
                    label.setText(f"• {devices[i]}")
                    label.setVisible(True)
                else:
                    label.setVisible(False)

            # Show/hide "no devices" message
            self.window.sidebar.hw_no_devices.setVisible(len(devices) == 0)

        # Update subunit readiness based on verification
        self.update_subunit_readiness(status)

        # Update operation mode availability
        self.update_operation_modes(status)

    def update_subunit_readiness(self, status: Dict[str, Any]) -> None:
        """Update subunit readiness indicators based on hardware verification.

        Args:
            status: Hardware status dictionary with readiness flags
        """
        from affilabs.utils.logger import logger
        logger.debug(f"🔍 Updating subunit readiness: sensor={status.get('sensor_ready')}, "
                    f"optics={status.get('optics_ready')}, fluidics={status.get('fluidics_ready')}")

        # Sensor readiness
        if 'sensor_ready' in status:
            self.set_subunit_status('Sensor', status['sensor_ready'])

        # Optics readiness (with channel details)
        if 'optics_ready' in status:
            optics_ready = status['optics_ready']
            optics_details = {
                'failed_channels': status.get('optics_failed_channels', []),
                'maintenance_channels': status.get('optics_maintenance_channels', [])
            }
            self.set_subunit_status('Optics', optics_ready, details=optics_details)

        # Fluidics readiness
        if 'fluidics_ready' in status:
            self.set_subunit_status('Fluidics', status['fluidics_ready'])

    def set_subunit_status(self, subunit: str, ready: bool, details: Optional[Dict] = None) -> None:
        """Set readiness status for a specific subunit.

        Args:
            subunit: Subunit name ('Sensor', 'Optics', or 'Fluidics')
            ready: True if subunit is ready, False otherwise
            details: Optional dictionary with additional status details
        """
        if not hasattr(self.window, 'sidebar'):
            return

        # Forward to sidebar's encapsulated method
        self.window.sidebar.set_subunit_status(subunit, ready, details)

    def update_operation_modes(self, status: Dict[str, Any]) -> None:
        """Update operation mode availability based on hardware.

        Args:
            status: Hardware status dictionary
        """
        # Placeholder for operation mode logic
        # Could enable/disable certain UI controls based on connected hardware
        pass

    def set_scan_button_state(self, scanning: bool) -> None:
        """Update scan button state.

        Args:
            scanning: True if scan is in progress, False otherwise
        """
        if hasattr(self.window, 'sidebar'):
            self.window.sidebar.set_scan_state(scanning)

    def update_power_button_state(self, state: str) -> None:
        """Update power button visual state.

        Args:
            state: One of 'disconnected', 'searching', 'connected'
        """
        if not hasattr(self.window, 'power_btn'):
            return

        try:
            # Set property for state-based styling
            self.window.power_btn.setProperty("powerState", state)

            # Call the main window's style update method which has all the correct styling
            if hasattr(self.window, '_update_power_button_style'):
                self.window._update_power_button_style()
            else:
                # Fallback: Force style update manually
                self.window.power_btn.style().unpolish(self.window.power_btn)
                self.window.power_btn.style().polish(self.window.power_btn)
                self.window.power_btn.update()

            # Update checked state based on connection
            if state == 'connected':
                self.window.power_btn.setChecked(True)
            elif state == 'disconnected':
                self.window.power_btn.setChecked(False)

        except Exception as e:
            from affilabs.utils.logger import logger
            logger.error(f"Error updating power button state: {e}")

    def show_afterglow_status(self, afterglow_sec: float) -> None:
        """Display afterglow calibration status.

        Args:
            afterglow_sec: Afterglow duration in seconds, or 0 if not calibrated
        """
        if not hasattr(self.window, 'sidebar'):
            return

        try:
            if afterglow_sec > 0:
                # Show calibrated status with duration
                status_text = f"✓ Calibrated ({afterglow_sec:.1f}s)"
                self.window.sidebar.afterglow_status_label.setText(status_text)
                self.window.sidebar.afterglow_status_label.setStyleSheet(
                    "color: #34C759; font-weight: 600;"
                )
            else:
                # Show not calibrated
                self.window.sidebar.afterglow_status_label.setText("Not calibrated")
                self.window.sidebar.afterglow_status_label.setStyleSheet(
                    "color: #FF9500; font-weight: 600;"
                )
        except Exception as e:
            from affilabs.utils.logger import logger
            logger.error(f"Error updating afterglow status: {e}")

    def enable_recording_controls(self, enable: bool) -> None:
        """Enable or disable recording-related controls.

        Args:
            enable: True to enable controls, False to disable
        """
        if hasattr(self.window, 'record_btn'):
            self.window.record_btn.setEnabled(enable)

        if hasattr(self.window, 'pause_btn'):
            self.window.pause_btn.setEnabled(enable)

    def update_recording_state(self, is_recording: bool) -> None:
        """Update UI to reflect current recording state.

        Args:
            is_recording: True if currently recording, False otherwise
        """
        if hasattr(self.window, 'record_btn'):
            self.window.record_btn.setChecked(is_recording)

    def update_pause_state(self, is_paused: bool) -> None:
        """Update UI to reflect current pause state.

        Args:
            is_paused: True if currently paused, False otherwise
        """
        if hasattr(self.window, 'pause_btn'):
            self.window.pause_btn.setChecked(is_paused)
