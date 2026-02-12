"""Injection Coordinator - Handles both automated and manual injection flows.

This coordinator manages the injection workflow for experiments, automatically
routing to manual or automated mode based on hardware configuration and user settings.

MODES:
1. Hardware Auto-Detection (legacy):
   - P4SPR without pump → manual injection
   - P4SPR with pump or P4PRO → automated injection

2. Per-Cycle User Selection (new):
   - User explicitly sets cycle.manual_injection_mode = "manual" or "automated"
   - Overrides hardware defaults
   - Enables flexible concentration cycles

CONCENTRATION CYCLES:
- Single cycle with multiple injection points
- Shows schedule dialog upfront
- Prompts at each flag point
- Tracks injection_count progress

ARCHITECTURE:
- Coordinator pattern: Single entry point for all injection requests
- Mode detection: Checks cycle.manual_injection_mode first, then hardware
- Manual mode: Shows dialog, waits for user, controls valves
- Automated mode: Executes pump injection in background thread
- Event logging: Differentiates manual vs automated injections

HARDWARE MODES:
- P4SPR + No Pump → Manual injection (dialog shown)
- P4SPR + AffiPump → Automated injection (pump controlled)
- P4PRO/P4PROPLUS → Automated injection (internal pumps)

USAGE:
    from affilabs.coordinators.injection_coordinator import InjectionCoordinator

    coordinator = InjectionCoordinator(hardware_mgr, pump_mgr, parent=main_window)

    # Execute injection (mode detected automatically or from cycle setting)
    success = coordinator.execute_injection(cycle, flow_rate=100.0, parent_widget=window)

    if success:
        # Injection completed (user confirmed or pump finished)
        continue_cycle()
    else:
        # Injection cancelled or failed
        stop_cycle()
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Signal

from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog
from affilabs.dialogs.concentration_schedule_dialog import ConcentrationScheduleDialog
from affilabs.utils.logger import logger
from affilabs.utils.sample_parser import parse_sample_info

if TYPE_CHECKING:
    from affilabs.core.hardware_manager import HardwareManager
    from affilabs.domain.cycle import Cycle
    from affilabs.managers.pump_manager import PumpManager
    from affilabs.core.data_acquisition_manager import DataAcquisitionManager


class InjectionCoordinator(QObject):
    """Coordinates injection workflows - automated or manual based on hardware.

    Responsibilities:
    - Detect injection mode (manual vs automated)
    - Show manual injection dialog when needed
    - Execute automated injections via PumpManager
    - Handle valve control for manual injections
    - Log injection events differently based on mode

    Signals:
        injection_started: Injection sequence started (arg: injection_type str)
        injection_completed: Injection completed successfully
        injection_cancelled: User cancelled manual injection
        manual_prompt_shown: Manual injection dialog displayed
        auto_detect_injection_requested: Request auto-detection after manual injection (arg: channels str)
    """

    injection_started = Signal(str)  # injection_type
    injection_completed = Signal()
    injection_cancelled = Signal()
    manual_prompt_shown = Signal()
    auto_detect_injection_requested = Signal(str)  # channels

    def __init__(
        self,
        hardware_mgr: HardwareManager,
        pump_mgr: PumpManager,
        buffer_mgr: Optional[DataAcquisitionManager] = None,
        parent=None,
    ):
        """Initialize injection coordinator.

        Args:
            hardware_mgr: Hardware manager for valve control and mode detection
            pump_mgr: Pump manager for automated injections
            buffer_mgr: Data acquisition manager for real-time sensorgram monitoring (optional)
            parent: Parent QObject for Qt hierarchy
        """
        super().__init__(parent)
        self.hardware_mgr = hardware_mgr
        self.pump_mgr = pump_mgr
        self.buffer_mgr = buffer_mgr
        self._current_dialog: Optional[ManualInjectionDialog] = None

    def execute_injection(
        self,
        cycle: Cycle,
        flow_rate: float,
        parent_widget=None,
    ) -> bool:
        """Execute injection for cycle - manual or automated based on hardware and user settings.

        This is the single entry point for all injection requests. The coordinator:
        1. Checks if cycle explicitly sets manual_injection_mode
        2. Falls back to hardware auto-detection (P4SPR without pump = manual)
        3. Shows concentration schedule dialog if cycle has planned_concentrations
        4. Routes to appropriate execution method

        Args:
            cycle: Cycle requiring injection
            flow_rate: Flow rate in µL/min
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if injection initiated/completed successfully, False if cancelled or failed
        """
        # Determine injection mode: explicit setting takes precedence
        is_manual_mode = self._determine_injection_mode(cycle)

        # For concentration cycles in manual mode, show schedule upfront
        if (is_manual_mode and
            cycle.type == "Concentration" and
            cycle.planned_concentrations and
            cycle.injection_count == 0):  # Only show at cycle start

            schedule_dialog = ConcentrationScheduleDialog(cycle, parent_widget)
            if schedule_dialog.exec() != ConcentrationScheduleDialog.DialogCode.Accepted:
                logger.info("User cancelled concentration cycle")
                return False

        # Execute appropriate injection mode
        if is_manual_mode:
            return self._execute_manual_injection(cycle, parent_widget)
        else:
            return self._execute_automated_injection(cycle, flow_rate)

    def _determine_injection_mode(self, cycle: Cycle) -> bool:
        """Determine if manual injection mode should be used.

        Priority order:
        1. Explicit cycle.manual_injection_mode setting
        2. Hardware auto-detection (P4SPR without pump = manual)

        Args:
            cycle: Cycle to check

        Returns:
            True if manual mode, False if automated mode
        """
        # If cycle explicitly sets mode, use that
        if cycle.manual_injection_mode == "manual":
            return True
        elif cycle.manual_injection_mode == "automated":
            return False

        # Fall back to hardware detection
        return self.hardware_mgr.requires_manual_injection

    def _execute_manual_injection(self, cycle: Cycle, parent_widget) -> bool:
        """Show manual injection dialog and wait for user completion.

        This method BLOCKS until user completes or cancels the injection.
        Valve control is automated (open/close for user's convenience).

        For concentration cycles:
        - Shows "Injection X of Y" in dialog
        - Tracks injection_count in cycle
        - User will set flags to trigger next injections

        Args:
            cycle: Cycle requiring injection
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if user completed injection, False if cancelled
        """
        logger.info("=== Manual Injection Mode ===")

        # Parse sample information from cycle metadata
        sample_info = parse_sample_info(cycle)
        logger.info(f"  Sample: {sample_info['sample_id']}")

        # For P4SPR (static optical system), don't show valve channels
        # P4SPR has no 3-way valve routing - channels field should be None
        is_p4spr = self.hardware_mgr._ctrl_type == "PicoP4SPR"
        if is_p4spr:
            sample_info["channels"] = None
            logger.info(f"  Hardware: P4SPR (no valve routing)")
        else:
            logger.info(f"  Channels: {sample_info['channels']}")

        if sample_info["concentration"]:
            logger.info(
                f"  Concentration: {sample_info['concentration']} {sample_info['units']}"
            )

        # Open valves for manual injection (only if not P4SPR)
        if not is_p4spr:
            self._open_valves_for_manual_injection(sample_info["channels"])

        # For concentration cycles, show injection number
        injection_num = None
        total_injections = None
        if cycle.type == "Concentration" and cycle.planned_concentrations:
            injection_num = cycle.injection_count + 1
            total_injections = len(cycle.planned_concentrations)
            logger.info(f"  Concentration Cycle: Injection {injection_num}/{total_injections}")

        # Prepare channels for real-time detection in dialog
        detection_channels = "ABCD" if is_p4spr else (sample_info.get("channels") or "AC")

        # Show dialog and BLOCK until user responds
        # Dialog performs real-time injection detection automatically
        self._current_dialog = ManualInjectionDialog(
            sample_info,
            parent_widget,
            injection_number=injection_num,
            total_injections=total_injections,
            buffer_mgr=self.buffer_mgr,
            channels=detection_channels,
        )
        self.manual_prompt_shown.emit()
        self.injection_started.emit("manual")

        # exec() blocks here until injection detected or user cancels
        result = self._current_dialog.exec()

        if result == ManualInjectionDialog.DialogCode.Accepted:
            logger.info("✓ Manual injection completed (auto-detected or confirmed)")
            # Track injection count for concentration cycles
            if cycle.type == "Concentration" and cycle.planned_concentrations:
                cycle.injection_count += 1
                logger.info(f"  Injection count: {cycle.injection_count}/{len(cycle.planned_concentrations)}")

            self._close_valves_after_manual_injection()

            # Note: Real-time detection happens in the dialog itself
            # Legacy auto_detect signal for backward compatibility
            self.auto_detect_injection_requested.emit(detection_channels)

            self.injection_completed.emit()
            return True
        else:
            logger.info("⚠️ User cancelled manual injection")
            self._close_valves_after_manual_injection()
            self.injection_cancelled.emit()
            return False

    def _execute_automated_injection(self, cycle: Cycle, flow_rate: float) -> bool:
        """Execute automated injection via PumpManager (existing logic).

        Runs in background thread to avoid blocking UI. This preserves the
        existing injection behavior for P4PRO and AffiPump systems.

        Args:
            cycle: Cycle requiring injection
            flow_rate: Flow rate in µL/min

        Returns:
            True if injection initiated successfully (runs async in background)
        """
        logger.info("=== Automated Injection Mode ===")
        self.injection_started.emit(cycle.injection_method or "automated")

        # Run in background thread (existing pattern from main.py)
        def run_injection():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Stop any running pump operation first
                if not self.pump_mgr.is_idle:
                    logger.info("⏹ Stopping pump before injection...")
                    idle_ok = loop.run_until_complete(
                        self.pump_mgr.stop_and_wait_for_idle(timeout=30.0)
                    )
                    if not idle_ok:
                        logger.error("❌ Could not stop pump for injection")
                        return

                # Execute injection with channel selection
                channels = cycle.channels  # None = use default_channels
                if cycle.injection_method == "simple":
                    logger.info(
                        f"💉 AUTO-INJECT: Simple @ {flow_rate} µL/min (channels={channels or 'default'})"
                    )
                    success = loop.run_until_complete(
                        self.pump_mgr.inject_simple(flow_rate, channels=channels)
                    )
                elif cycle.injection_method == "partial":
                    logger.info(
                        f"💉 AUTO-INJECT: Partial @ {flow_rate} µL/min (channels={channels or 'default'})"
                    )
                    success = loop.run_until_complete(
                        self.pump_mgr.inject_partial_loop(flow_rate, channels=channels)
                    )
                else:
                    logger.warning(
                        f"Unknown injection method: {cycle.injection_method}"
                    )
                    success = False

                if success:
                    self.injection_completed.emit()
                else:
                    logger.error("❌ Automated injection failed")

            except Exception as e:
                logger.exception(f"Automated injection error: {e}")
            finally:
                loop.close()

        thread = threading.Thread(
            target=run_injection, daemon=True, name="AutoInjection"
        )
        thread.start()
        return True

    def _open_valves_for_manual_injection(self, channels: str):
        """Open valves to assist manual syringe injection.

        Sets 3-way valves to route flow to the target channels.
        This helps guide the user's manual injection to the correct flow path.

        Args:
            channels: Target channels ("AC" or "BD")
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("No controller - cannot open valves for manual injection")
            return

        try:
            # Set 3-way valves to route to selected channels
            # AC = state 0, BD = state 1
            three_way_state = 1 if channels == "BD" else 0

            # Check if controller supports valve control (FlowController only)
            if hasattr(ctrl, 'knx_three_both'):
                ctrl.knx_three_both(state=three_way_state)
                logger.info(
                    f"✓ Valves opened for manual injection (channels: {channels})"
                )
            else:
                logger.debug(f"Controller {type(ctrl).__name__} doesn't have valve control - manual injection without automated valves")

            # Optionally open 6-port valves to INJECT position
            # This depends on your hardware setup - may or may not be needed
            # Uncomment if 6-port should be open during manual injection:
            # if hasattr(ctrl, 'knx_six_both'):
            #     ctrl.knx_six_both(state=1)

        except Exception as e:
            logger.error(f"Failed to open valves: {e}")

    def _close_valves_after_manual_injection(self):
        """Return valves to default position after manual injection.

        Resets valves to the default channel pair and closes 6-port valves
        to LOAD position for normal buffer flow.
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            return

        try:
            # Return to default channel pair
            default_channels = self.pump_mgr.default_channels if self.pump_mgr else "AC"
            default_state = 1 if default_channels == "BD" else 0

            # Check if controller supports valve control (FlowController only)
            if hasattr(ctrl, 'knx_three_both'):
                ctrl.knx_three_both(state=default_state)
            else:
                logger.debug(f"Controller {type(ctrl).__name__} doesn't have valve control - skipping")

            # Close 6-port valves to LOAD position
            if hasattr(ctrl, 'knx_six_both'):
                ctrl.knx_six_both(state=0)
            else:
                logger.debug(f"Controller {type(ctrl).__name__} doesn't have 6-port valves - skipping")

            logger.info(f"✓ Valves returned to default ({default_channels})")
        except Exception as e:
            logger.error(f"Failed to close valves: {e}")
