"""UI Adapter - Clean interface between Application and UI layers.

This adapter provides a clean API for the Application class to interact with
the UI without coupling to specific UI implementation details. If UI changes,
only this adapter needs updating.

Usage in main_simplified.py:
    from ui_adapter import UIAdapter

    # In Application.__init__():
    self.ui = UIAdapter(self.main_window)

    # Use adapter methods instead of calling UI directly:
    self.ui.set_power_state('connected')
    self.ui.update_device_status('spectrometer', True)
"""

from typing import Any

from PySide6.QtCore import QObject, Signal


class UIAdapter(QObject):
    """Adapter class to manage UI updates and prevent tight coupling.

    This class provides a stable API for the Application layer to interact
    with the UI, insulating business logic from UI implementation changes.
    """

    # UI request signals - forwarded from main window
    power_on_requested = Signal()
    power_off_requested = Signal()
    recording_start_requested = Signal()
    recording_stop_requested = Signal()
    export_requested = Signal()
    acquisition_pause_requested = Signal(bool)  # True=pause, False=resume

    def __init__(self, main_window):
        """Initialize adapter with reference to main window.

        Args:
            main_window: Instance of AffilabsMainWindow

        """
        super().__init__()
        self.ui = main_window

        # Forward main window signals through adapter
        if hasattr(self.ui, "power_on_requested"):
            self.ui.power_on_requested.connect(self.power_on_requested.emit)
        if hasattr(self.ui, "power_off_requested"):
            self.ui.power_off_requested.connect(self.power_off_requested.emit)
        if hasattr(self.ui, "recording_start_requested"):
            self.ui.recording_start_requested.connect(
                self.recording_start_requested.emit,
            )
        if hasattr(self.ui, "recording_stop_requested"):
            self.ui.recording_stop_requested.connect(self.recording_stop_requested.emit)
        if hasattr(self.ui, "export_requested"):
            self.ui.export_requested.connect(self.export_requested.emit)
        if hasattr(self.ui, "acquisition_pause_requested"):
            self.ui.acquisition_pause_requested.connect(
                self.acquisition_pause_requested.emit,
            )
        self.ui = main_window

    # ==================== Power & Connection Control ====================

    def set_power_state(self, state: str) -> None:
        """Update power button visual state.

        Args:
            state: One of 'disconnected', 'searching', 'connected'

        """
        self.ui.status_presenter.update_power_button_state(state)

    def get_power_state(self) -> str:
        """Get current power button state.

        Returns:
            Current state: 'disconnected', 'searching', or 'connected'

        """
        if hasattr(self.ui, "power_btn") and self.ui.power_btn:
            return self.ui.power_btn.property("powerState") or "disconnected"
        return "disconnected"

    def set_power_button_checked(self, checked: bool) -> None:
        """Set power button checked state programmatically.

        Args:
            checked: True to check, False to uncheck

        """
        self.ui.power_btn.setChecked(checked)

    # ==================== Device Status Updates ====================

    def update_device_status(
        self,
        subunit: str,
        ready: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update device subunit status indicator.

        Args:
            subunit: Subunit name (e.g., 'spectrometer', 'led', 'polarizer', 'pump')
            ready: True if ready, False if not ready
            details: Optional dict with additional status information

        """
        self.ui.status_presenter.set_subunit_status(subunit, ready, details)

    def update_afterglow_status(self, afterglow_seconds: float) -> None:
        """Update afterglow correction status display.

        Args:
            afterglow_seconds: Afterglow time in seconds

        """
        self.ui.update_afterglow_status(afterglow_seconds)

    def update_hardware_status(self, status: dict[str, Any]) -> None:
        """Update hardware status display with real hardware information.

        Args:
            status: Dict with keys:
                - ctrl_type: Controller type (P4SPR, PicoP4SPR, etc.)
                - knx_type: Kinetic controller type (KNX2, etc.)
                - pump_connected: Boolean
                - spectrometer: Boolean
                - spectrometer_serial: Device serial number
                - sensor_ready: Boolean
                - optics_ready: Boolean
                - optics_failed_channels: List of failed LED channels
                - optics_maintenance_channels: Channels needing maintenance
                - fluidics_ready: Boolean

        """
        self.ui.status_presenter.update_hardware_status(status)
        self.ui.status_presenter.update_subunit_readiness(status)

    def refresh_intelligence_bar(self) -> None:
        """Trigger an immediate refresh of the Intelligence Bar display.

        This manually updates the Intelligence Bar with the current system state
        from SystemIntelligence. The UI also refreshes automatically every 5 seconds.
        """
        self.ui._refresh_intelligence_bar()

    # ==================== Recording Control ====================

    def set_recording_state(self, is_recording: bool) -> None:
        """Update recording button state and UI indicators.

        Args:
            is_recording: True if recording, False if stopped

        """
        self.ui.status_presenter.update_recording_state(is_recording)

    def enable_recording_controls(self) -> None:
        """Enable recording and pause buttons (called after calibration)."""
        self.ui.status_presenter.enable_recording_controls(True)

    def disable_recording_controls(self) -> None:
        """Disable recording and pause buttons."""
        self.ui.status_presenter.enable_recording_controls(False)

    # ==================== Calibration Progress ====================

    def show_calibration_dialog(
        self,
        title: str = "Calibrating",
        message: str = "Please wait...",
    ) -> Any:
        """Show calibration progress dialog.

        Args:
            title: Dialog title
            message: Initial message to display

        Returns:
            Reference to the dialog for progress updates

        """
        from affilabs_core_ui import StartupCalibProgressDialog

        dialog = StartupCalibProgressDialog(
            parent=self.ui,
            title=title,
            message=message,
            show_start_button=False,
        )
        dialog.show()
        return dialog

    # ==================== Graph Data Updates ====================

    def update_timeline_graph_data(self, channel_idx: int, x_data, y_data) -> None:
        """Update full timeline graph for a channel.

        Args:
            channel_idx: Channel index (0=A, 1=B, 2=C, 3=D)
            x_data: X-axis data (time)
            y_data: Y-axis data (signal)

        """
        channel_data = {channel_idx: y_data}
        self.ui.sensogram_presenter.update_timeline_data(channel_data, x_data)

    def update_cycle_graph_data(self, channel_idx: int, x_data, y_data) -> None:
        """Update cycle of interest graph for a channel.

        Args:
            channel_idx: Channel index (0=A, 1=B, 2=C, 3=D)
            x_data: X-axis data (time)
            y_data: Y-axis data (signal)

        """
        channel_data = {channel_idx: y_data}
        self.ui.sensogram_presenter.update_cycle_data(channel_data, x_data)

    def update_transmission_plot(
        self,
        channel_idx: int,
        wavelengths,
        transmission,
    ) -> None:
        """Update spectroscopy transmission plot.

        Args:
            channel_idx: Channel index (0=A, 1=B, 2=C, 3=D)
            wavelengths: Wavelength array
            transmission: Transmission percentage array

        """
        if hasattr(self.ui, "transmission_curves") and 0 <= channel_idx < len(
            self.ui.transmission_curves,
        ):
            self.ui.transmission_curves[channel_idx].setData(wavelengths, transmission)

    def clear_graphs(self) -> None:
        """Clear all graph data."""
        self.ui.sensogram_presenter.clear_all_graph_data()

    # ==================== Channel Visibility Control ====================

    def set_channel_visibility(self, channel_idx: int, visible: bool) -> None:
        """Show or hide a specific channel on graphs.

        Args:
            channel_idx: Channel index (0=A, 1=B, 2=C, 3=D)
            visible: True to show, False to hide

        """
        channel_letter = chr(65 + channel_idx)  # 0->A, 1->B, etc.
        self.ui.sensogram_presenter.toggle_channel_visibility(channel_letter, visible)

    # ==================== Settings Access ====================

    def get_filter_enabled(self) -> bool:
        """Get current filter enabled state.

        Returns:
            True if filter is enabled

        """
        return (
            self.ui.filter_enable.isChecked()
            if hasattr(self.ui, "filter_enable")
            else False
        )

    def get_filter_strength(self) -> float:
        """Get current filter strength value.

        Returns:
            Filter strength (0.0 - 1.0)

        """
        if hasattr(self.ui, "filter_slider"):
            return self.ui.filter_slider.value() / 100.0
        return 0.5

    def get_reference_channel(self) -> str | None:
        """Get currently selected reference channel for subtraction.

        Returns:
            Channel letter ('a', 'b', 'c', 'd') or None

        """
        if hasattr(self.ui, "ref_combo"):
            text = self.ui.ref_combo.currentText().lower()
            if text and text != "none":
                return text
        return None

    def get_y_axis_mode(self) -> str:
        """Get Y-axis scaling mode.

        Returns:
            'auto' or 'manual'

        """
        if hasattr(self.ui, "auto_radio") and self.ui.auto_radio.isChecked():
            return "auto"
        return "manual"

    def get_y_axis_range(self) -> tuple[float, float]:
        """Get manual Y-axis range if set.

        Returns:
            Tuple of (min, max) values

        """
        try:
            min_val = (
                float(self.ui.min_input.text())
                if hasattr(self.ui, "min_input")
                else -100.0
            )
            max_val = (
                float(self.ui.max_input.text())
                if hasattr(self.ui, "max_input")
                else 100.0
            )
            return (min_val, max_val)
        except (ValueError, AttributeError):
            return (-100.0, 100.0)

    # ==================== LED Control Settings ====================

    def get_led_intensities(self) -> dict[str, int]:
        """Get LED intensity values from all channel inputs.

        Returns:
            Dict with keys 'a', 'b', 'c', 'd' and intensity values (0-255)

        """
        intensities = {}
        for channel in ["a", "b", "c", "d"]:
            input_widget = getattr(self.ui, f"channel_{channel}_input", None)
            if input_widget:
                try:
                    intensities[channel] = int(input_widget.text() or 0)
                except ValueError:
                    intensities[channel] = 0
        return intensities

    def set_led_intensity(self, channel: str, intensity: int) -> None:
        """Set LED intensity value for a channel.

        Args:
            channel: Channel letter ('a', 'b', 'c', 'd')
            intensity: Intensity value (0-255)

        """
        input_widget = getattr(self.ui, f"channel_{channel}_input", None)
        if input_widget:
            input_widget.setText(str(intensity))

    def get_polarizer_positions(self) -> dict[str, int]:
        """Get S and P polarizer positions.

        Returns:
            Dict with keys 's' and 'p' and position values (0-255)

        """
        positions = {}
        try:
            positions["s"] = int(self.ui.s_position_input.text() or 0)
            positions["p"] = int(self.ui.p_position_input.text() or 0)
        except (ValueError, AttributeError):
            positions["s"] = 0
            positions["p"] = 0
        return positions

    # ==================== Status Bar / Messages ====================

    def show_status_message(self, message: str, duration: int = 5000) -> None:
        """Show temporary message in status bar.

        Args:
            message: Message to display
            duration: Duration in milliseconds (0 = permanent)

        """
        if hasattr(self.ui, "statusBar"):
            self.ui.statusBar().showMessage(message, duration)

    def clear_status_message(self) -> None:
        """Clear status bar message."""
        if hasattr(self.ui, "statusBar"):
            self.ui.statusBar().clearMessage()

    # ==================== Window State ====================

    def show_window(self) -> None:
        """Show and raise main window."""
        self.ui.show()
        self.ui.raise_()
        self.ui.activateWindow()

    def is_visible(self) -> bool:
        """Check if window is visible.

        Returns:
            True if window is visible

        """
        return self.ui.isVisible()

    def close_window(self) -> None:
        """Close main window."""
        self.ui.close()

    # ==================== Direct UI Access (use sparingly) ====================

    def get_main_window(self):
        """Get direct reference to main window.

        Use this sparingly - prefer adapter methods for better decoupling.

        Returns:
            MainWindowPrototype instance

        """
        return self.ui
