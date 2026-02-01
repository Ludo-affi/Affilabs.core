"""Peripheral Event Coordinator.

Manages peripheral device and status events including:
- Pump state changes
- Valve switching
- Pipeline selection changes
- Device status changes (ViewModel integration)

This coordinator handles external peripheral events and status updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application

from affilabs.utils.logger import logger


class PeripheralEventCoordinator:
    """Coordinates peripheral device and status events.

    Handles:
    - Pump state monitoring
    - Valve position monitoring
    - Pipeline configuration changes
    - Device status ViewModel updates
    - Overall system health status

    This is a pure coordinator - it routes events and updates UI,
    but does not contain business logic.
    """

    def __init__(self, app: Application):
        """Initialize peripheral event coordinator.

        Args:
            app: Main application instance for accessing managers and UI

        """
        self.app = app

    # =========================================================================
    # PUMP AND VALVE EVENTS
    # =========================================================================

    def on_pump_state_changed(self, state: dict):
        """Handle pump state changes.

        Args:
            state: Pump state dict with 'channel', 'running', 'flow_rate'

        """
        channel = state.get("channel")
        running = state.get("running")
        flow_rate = state.get("flow_rate")
        logger.info(
            f"Pump {channel}: {'running' if running else 'stopped'} @ {flow_rate} μL/min",
        )
        # TODO: Update UI pump status

    def on_valve_switched(self, valve_info: dict):
        """Handle valve position changes.

        Args:
            valve_info: Valve info dict with 'channel', 'position'

        """
        channel = valve_info.get("channel")
        position = valve_info.get("position")
        logger.info(f"Valve {channel} switched to {position}")
        # TODO: Update UI valve status

    # =========================================================================
    # PIPELINE CONFIGURATION
    # =========================================================================

    def on_pipeline_changed(self, pipeline_id: str):
        """Handle peak finding pipeline selection change.

        Args:
            pipeline_id: Pipeline identifier ('fourier', 'hybrid', 'hybrid_original')

        """
        logger.info(f"[UI] Pipeline changed to: {pipeline_id}")
        try:
            # Update data acquisition manager to use new pipeline
            if hasattr(self.app, "data_mgr") and self.app.data_mgr:
                self.app.data_mgr.set_peak_finding_pipeline(pipeline_id)
                logger.info("[OK] Peak finding pipeline updated successfully")
            else:
                logger.warning("[WARN] Data manager not available")
        except Exception as e:
            logger.error(f"[ERROR] Error changing pipeline: {e}", exc_info=True)

    # =========================================================================
    # DEVICE STATUS VIEWMODEL EVENTS
    # =========================================================================

    def on_vm_status_changed(self, all_connected: bool, all_healthy: bool):
        """Handle overall_status_changed signal from DeviceStatusViewModel.

        Args:
            all_connected: True if all required devices are connected
            all_healthy: True if all devices are healthy (no errors)

        """
        # Status already logged in _update_device_status_ui
        # Future: Could enable/disable features based on system health
        pass
