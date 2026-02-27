"""Acquisition Event Coordinator - Handles acquisition lifecycle events.

This coordinator manages all acquisition-related events including:
- Start/stop acquisition
- Acquisition pause/resume
- Acquisition errors
- Detector configuration
- Integration time and LED setup

Architecture Alignment:
- Layer 3: Coordinator (orchestration between data acquisition and UI)
- Depends on: DataAcquisitionManager (Layer 2), HardwareManager (Layer 1), MainWindow (Layer 4)
- No business logic - pure event coordination
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from affilabs.ui.ui_message import error as ui_error
from affilabs.ui.ui_message import warn as ui_warn
from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from affilabs.affilabs_core_ui import AffilabsMainWindow
    from affilabs.core.data_acquisition_manager import DataAcquisitionManager
    from affilabs.core.hardware_manager import HardwareManager


class AcquisitionEventCoordinator:
    """Coordinates acquisition lifecycle events.

    Responsibilities:
    -----------------
    - Handle start/stop button clicks
    - Configure hardware for acquisition
    - Manage acquisition state transitions
    - Handle acquisition errors
    - Update UI based on acquisition state

    Architecture:
    -------------
    - Pure coordinator - no business logic
    - Bridges acquisition events to UI updates
    - Manages hardware configuration for acquisition
    """

    def __init__(
        self,
        data_mgr: DataAcquisitionManager,
        hardware_mgr: HardwareManager,
        main_window: AffilabsMainWindow,
        app,
    ):
        """Initialize acquisition event coordinator.

        Args:
            data_mgr: Data acquisition manager instance
            hardware_mgr: Hardware manager instance
            main_window: Main window instance
            app: Application instance (for callbacks to other coordinators)
        """
        self._data_mgr = data_mgr
        self._hardware_mgr = hardware_mgr
        self._main_window = main_window
        self._app = app

        # Track live data dialog
        self._live_data_dialog = None

    def on_detector_wait_changed(self, value: int):
        """Update detector wait time for live acquisition.

        Args:
            value: New detector wait time in milliseconds (0-100ms)
        """
        if self._data_mgr:
            self._data_mgr.detector_wait_ms = value
            logger.info(f"[OK] Detector wait time updated to {value}ms")

    def on_start_button_clicked(self):
        """User clicked Start button - begin live data acquisition."""
        logger.info("User requested start - beginning acquisition")

        if self._data_mgr and self._data_mgr._acquiring:
            logger.info("Acquisition already running")
            return

        if not self._validate_hardware():
            return

        integration_time, led_intensities = self._configure_hardware()

        if not self._start_acquisition():
            return

        self._update_ui_after_start()
        logger.info("[OK] Live acquisition started")

    def on_acquisition_started(self):
        """Live data acquisition has started - enable record and pause buttons."""
        logger.info("[OK] Live acquisition started - enabling record/pause buttons")
        self._main_window.enable_controls()

        # Update spectroscopy status to "Running"
        self._update_spectroscopy_status("Running", "#34C759")

        # Reset experiment clock
        self._app.clock.reset()
        logger.debug("Reset experiment clock for new acquisition")

        # Clear data buffers
        self._app.buffer_mgr.clear_all()
        logger.debug("Cleared all data buffers")

        # Clear pause/resume markers
        self._clear_pause_markers()

    def on_acquisition_stopped(self):
        """Live data acquisition has stopped - disable record and pause buttons."""
        logger.debug("Live acquisition stopped - disabling record/pause buttons")
        self._main_window.record_btn.setEnabled(False)
        self._main_window.pause_btn.setEnabled(False)
        self._main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)"
        )
        self._main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)"
        )

        # Uncheck buttons if active
        if self._main_window.record_btn.isChecked():
            self._main_window.record_btn.setChecked(False)
        if self._main_window.pause_btn.isChecked():
            self._main_window.pause_btn.setChecked(False)

        # Update spectroscopy status to "Stopped"
        self._update_spectroscopy_status("Stopped", "#86868B")

        # Stop recording if active
        if self._app.recording_mgr.is_recording:
            logger.info("Stopping recording due to acquisition stop...")
            self._app.recording_mgr.stop_recording()

    def on_acquisition_pause_requested(self, pause: bool):
        """Handle acquisition pause/resume request from UI."""
        if pause:
            logger.info("Pausing live acquisition...")
            self._data_mgr.pause_acquisition()
        else:
            logger.info("Resuming live acquisition...")
            self._data_mgr.resume_acquisition()

    def on_acquisition_error(self, error: str):
        """Data acquisition error."""
        logger.error(f"Acquisition error: {error}")

        # Check if error is due to device disconnect
        if "disconnected" in error.lower():
            logger.error("Spectrometer disconnected during acquisition")

            # Trigger hardware disconnect
            self._hardware_mgr.disconnect()

            # Show user-friendly message
            ui_warn(
                self._main_window,
                "Device Disconnected",
                "Spectrometer was disconnected.\n\n"
                "Please check the USB connection and power on again.",
            )
            return

        # If error indicates hardware failure
        if (
            "Hardware communication lost" in error
            or "stopping acquisition" in error.lower()
        ):
            logger.warning("Hardware error detected - stopping acquisition")

            # Update UI to show error state
            self._main_window.set_power_state("error")

            # Show user-friendly message
            ui_error(
                self._main_window,
                "Hardware Error",
                "Hardware communication lost. Please power off and reconnect the device.",
            )

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _validate_hardware(self) -> bool:
        """Validate hardware connection and calibration.

        Returns:
            True if hardware is ready, False otherwise
        """
        logger.info("PHASE 1: Checking hardware status...")
        try:
            if self._hardware_mgr.ctrl:
                logger.info("   [OK] Controller connected")
            else:
                logger.warning("   No controller found")

            if self._hardware_mgr.usb:
                logger.info("   [OK] Spectrometer connected")
            else:
                logger.warning("   No spectrometer found")

            logger.info("[OK] Hardware validation complete")
            return True

        except Exception as e:
            logger.exception(f"[X] Hardware validation failed: {e}")
            ui_error(
                self._main_window,
                "Hardware Check Failed",
                f"Hardware check failed:\n{e}",
            )
            return False

    def _configure_hardware(self) -> tuple[int, dict]:
        """Configure hardware for acquisition.

        Returns:
            Tuple of (integration_time, led_intensities)
        """
        logger.info("[PHASE 2] Configuring hardware...")

        # Get calibration data
        integration_time = 40
        led_intensities = {"a": 255, "b": 150, "c": 150, "d": 255}

        if (
            self._data_mgr
            and self._data_mgr.calibrated
            and getattr(self._data_mgr, "calibration_data", None)
        ):
            logger.info("   [OK] System calibrated")
            cd = self._data_mgr.calibration_data
            integration_time = (
                getattr(cd, "p_integration_time", None)
                or getattr(cd, "s_mode_integration_time", None)
                or 40
            )
            led_intensities = getattr(cd, "p_mode_intensities", {}) or {}
            logger.info(f"   [STATIC] Using P-mode intensities: {led_intensities}")
        else:
            logger.info(
                "   System not calibrated (using bypass mode defaults)"
            )

        # Configure polarizer
        self._configure_polarizer()

        # Configure integration time
        self._configure_integration_time(integration_time)

        # Configure LED intensities
        self._configure_led_intensities(led_intensities)

        logger.info("[OK] Hardware configuration complete")
        return integration_time, led_intensities

    def _configure_polarizer(self):
        """Configure polarizer to P-mode."""
        try:
            ctrl = self._hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_mode"):
                logger.info("   Setting polarizer to P-mode...")
                ctrl.set_mode("p")

                try:
                    import settings

                    settle_ms = getattr(settings, "POLARIZER_SETTLE_MS", 400)
                except Exception:
                    settle_ms = 400

                time.sleep(max(0, float(settle_ms)) / 1000.0)
                logger.info("   [OK] Polarizer configured")
            else:
                logger.warning("   Controller not available")
        except Exception as e:
            logger.exception(f"[X] Polarizer configuration failed: {e}")

    def _configure_integration_time(self, integration_time: int):
        """Configure spectrometer integration time."""
        try:
            usb = self._hardware_mgr.usb
            if usb and hasattr(usb, "set_integration"):
                logger.info(f"   Setting integration time: {integration_time}ms...")
                usb.set_integration(integration_time)  # API expects milliseconds
                logger.info("   [OK] Integration time configured")
            else:
                logger.warning("   Spectrometer not available")
        except Exception as e:
            logger.exception(f"[X] Integration time configuration failed: {e}")

    def _configure_led_intensities(self, led_intensities: dict):
        """Configure LED intensities."""
        try:
            ctrl = self._hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "set_intensity"):
                logger.info(f"   Setting LED intensities: {led_intensities}...")
                for channel, intensity in led_intensities.items():
                    ctrl.set_intensity(channel, intensity)
                logger.info("   [OK] LED intensities configured")
            else:
                logger.warning("   Controller not available")
        except Exception as e:
            logger.exception(f"[X] LED configuration failed: {e}")

    def _start_acquisition(self) -> bool:
        """Start data acquisition thread.

        Returns:
            True if acquisition started successfully, False otherwise
        """
        logger.info("PHASE 3: Starting data acquisition thread...")
        try:
            self._data_mgr.start_acquisition()
            logger.info("[OK] Data acquisition thread started successfully")
            return True
        except Exception as e:
            logger.exception(f"[X] Failed to start acquisition: {e}")
            from affilabs.widgets.message import show_message

            show_message(f"Failed to start acquisition:\n{e}", msg_type="Error")
            return False

    # REMOVED: _open_live_data_dialog() - duplicate LiveDataDialog window not needed
    # The main UI already has live data visualization capabilities

    def _update_ui_after_start(self):
        """Update UI state after acquisition starts."""
        logger.info("Updating UI state...")
        try:
            self._main_window.enable_controls()
            if hasattr(self._main_window, "sidebar") and hasattr(
                self._main_window.sidebar,
                "start_cycle_btn",
            ):
                self._main_window.sidebar.start_cycle_btn.setEnabled(True)
            self.on_acquisition_started()
            logger.info("[OK] UI state updated")
        except Exception as e:
            logger.exception(f"Failed to update UI: {e}")

    def _update_spectroscopy_status(self, status: str, color: str):
        """Update spectroscopy status indicator.

        Args:
            status: Status text ("Running", "Stopped", etc.)
            color: Color hex code
        """
        if (
            hasattr(self._main_window, "sidebar")
            and hasattr(self._main_window.sidebar, "subunit_status")
            and "Spectroscopy" in self._main_window.sidebar.subunit_status
        ):
            indicator = self._main_window.sidebar.subunit_status["Spectroscopy"][
                "indicator"
            ]
            status_label = self._main_window.sidebar.subunit_status["Spectroscopy"][
                "status_label"
            ]
            indicator.setStyleSheet(
                f"font-size: 10px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            status_label.setText(status)
            status_label.setStyleSheet(
                f"font-size: 13px;"
                f"color: {color};"
                f"background: transparent;"
                f"font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def _clear_pause_markers(self):
        """Clear pause/resume markers from previous runs."""
        try:
            if hasattr(self._main_window, "pause_markers") and hasattr(
                self._main_window,
                "full_timeline_graph",
            ):

                def clear_markers():
                    try:
                        for marker in self._main_window.pause_markers:
                            if "line" in marker:
                                try:
                                    self._main_window.full_timeline_graph.removeItem(
                                        marker["line"]
                                    )
                                except RuntimeError:
                                    pass  # Item already deleted
                        self._main_window.pause_markers = []
                    except Exception as e:
                        logger.debug(f"Could not clear pause markers: {e}")

                # Run in main thread after short delay
                QTimer.singleShot(200, clear_markers)
        except Exception as e:
            logger.debug(f"Pause marker cleanup error: {e}")
