"""Injection Coordinator - Handles both automated and manual injection flows.

This coordinator manages the injection workflow for experiments, automatically
routing to manual or automated mode based on hardware configuration and user settings.

MODES:
1. Hardware Auto-Detection (legacy):
   - P4SPR without pump → manual injection
   - P4SPR with pump or P4PRO → automated injection

2. Per-Cycle User Selection:
   - User explicitly sets cycle.manual_injection_mode = "manual" or "automated"
   - Overrides hardware defaults

MANUAL INJECTION FLOW:
- ManualInjectionDialog.exec() blocks but Qt events keep processing
- Dialog handles 60-second detection window with per-channel LED feedback
- Auto-detects injection peaks on all monitored channels
- Shows 3-second success display when all channels detected
- Returns detection results (channel, time, confidence) to coordinator

HARDWARE MODES:
- P4SPR + No Pump → Manual injection (dialog shown)
- P4SPR + AffiPump → Automated injection (pump controlled)
- P4PRO/P4PROPLUS → Automated injection (internal pumps)

USAGE:
    from affilabs.coordinators.injection_coordinator import InjectionCoordinator

    coordinator = InjectionCoordinator(hardware_mgr, pump_mgr, parent=main_window)
    coordinator.execute_injection(cycle, flow_rate=100.0, parent_widget=window)

    coordinator.injection_completed.connect(on_injection_done)
    coordinator.injection_cancelled.connect(on_injection_cancelled)
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Signal

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
    - Show ManualInjectionDialog for manual injection with real-time detection
    - Execute automated injections via PumpManager
    - Handle valve control for manual injections
    - Log injection events differently based on mode

    Signals:
        injection_started: Injection sequence started (arg: injection_type str)
        injection_completed: Injection completed successfully
        injection_cancelled: User cancelled manual injection
        injection_flag_requested: Place injection flag (args: channel, injection_time, confidence)
    """

    injection_started = Signal(str)  # injection_type
    injection_completed = Signal()
    injection_cancelled = Signal()
    injection_flag_requested = Signal(str, float, float)  # channel, injection_time, confidence

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

        # State for manual injection flow
        self._window_start_time: Optional[float] = None
        self._detection_channels: str = "ABCD"
        self._current_cycle: Optional[Cycle] = None
        self._is_p4spr: bool = False

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

        NOTE: Manual mode is NON-BLOCKING. The method returns True immediately and
        the actual result comes via injection_completed / injection_cancelled signals.

        Args:
            cycle: Cycle requiring injection
            flow_rate: Flow rate in µL/min
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if injection initiated successfully, False if cancelled at schedule stage
        """
        # Determine injection mode: explicit setting takes precedence
        is_manual_mode = self._determine_injection_mode(cycle)

        # NOTE: Schedule dialog (ConcentrationScheduleDialog) is now shown earlier
        # in main.py _schedule_injection() with a 20s countdown, so we skip it here.

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
        """Execute manual injection — shows blocking ManualInjectionDialog.

        This method:
        1. Opens valves for manual injection (non-P4SPR only)
        2. Shows ManualInjectionDialog.exec() which blocks but keeps Qt events processing
        3. Dialog handles 60s detection window with per-channel LED feedback
        4. Processes detection results and updates cycle state

        Args:
            cycle: Cycle requiring injection
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if injection completed (detected or timed out), False if cancelled
        """
        logger.info("=== Manual Injection Mode (Non-Blocking) ===")

        # Parse sample information from cycle metadata
        sample_info = parse_sample_info(cycle)
        logger.info(f"  Sample: {sample_info['sample_id']}")

        # For P4SPR (static optical system), don't show valve channels
        self._is_p4spr = self.hardware_mgr._ctrl_type == "PicoP4SPR"
        if self._is_p4spr:
            sample_info["channels"] = None
            logger.info(f"  Hardware: P4SPR (no valve routing)")
        else:
            logger.info(f"  Channels: {sample_info['channels']}")

        if sample_info["concentration"]:
            logger.info(
                f"  Concentration: {sample_info['concentration']} {sample_info['units']}"
            )

        # Open valves for manual injection (only if not P4SPR)
        if not self._is_p4spr:
            self._open_valves_for_manual_injection(sample_info["channels"])

        # For binding/kinetic cycles, show injection number
        # NOTE: planned_concentrations groups parallel channels into ONE entry,
        # so len() correctly reflects actual injection events (not channel count)
        injection_num = None
        total_injections = None
        if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
            injection_num = cycle.injection_count + 1
            total_injections = len(cycle.planned_concentrations)
            logger.info(f"  {cycle.type} Cycle: Injection {injection_num}/{total_injections}")

        # Prepare channels for real-time detection
        # Use cycle's target_channels if explicitly set, otherwise derive from concentrations or fall back to hardware default
        if getattr(cycle, 'target_channels', None):
            self._detection_channels = cycle.target_channels
        elif getattr(cycle, 'concentrations', None):
            # Auto-derive from concentrations dict (e.g., {"A": 50, "C": 40} → "AC")
            self._detection_channels = "".join(sorted(cycle.concentrations.keys()))
        else:
            self._detection_channels = "ABCD" if self._is_p4spr else (sample_info.get("channels") or "AC")

        # Save current cycle for detection completion
        self._current_cycle = cycle

        self.injection_started.emit("manual")

        # Check method mode - only show dialog for manual injections
        method_mode = getattr(cycle, 'method_mode', None)
        
        # Skip dialog for pump/semi-automated modes (injection is automatic)
        if method_mode in ['pump', 'semi-automated']:
            logger.info(f"Pump mode ({method_mode}) - skipping manual injection dialog")
            # Auto-complete for pump modes (detection happens in background)
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
            return True

        # ── Show BLOCKING dialog for manual injections ──
        # ManualInjectionDialog.exec() blocks but still processes Qt events
        # (acquisition, graph updates continue). Dialog handles its own 60s
        # detection window.
        from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog

        dialog = ManualInjectionDialog(
            sample_info,
            parent=parent_widget,
            injection_number=injection_num,
            total_injections=total_injections,
            buffer_mgr=self.buffer_mgr,
            channels=self._detection_channels,
            detection_priority=getattr(cycle, 'detection_priority', 'auto'),
            method_mode=method_mode,
        )

        result = dialog.exec()  # Blocks until user acts or 60s expires

        accepted = result == ManualInjectionDialog.DialogCode.Accepted
        if accepted:
            self._process_detection_results(dialog, cycle)
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
        else:
            logger.info("❌ Injection cancelled by user")
            self._close_valves_after_manual_injection()
            self.injection_cancelled.emit()

        return accepted

    def _process_detection_results(self, dialog, cycle: Cycle) -> None:
        """Process detection results from ManualInjectionDialog after it closes.

        Handles three cases:
        1. Dialog auto-detected injection → emit flag + store per-channel results
        2. Dialog detected but no per-channel results → retroactive scan
        3. No detection (timeout) → just increment injection count

        Args:
            dialog: Closed ManualInjectionDialog instance with detection results
            cycle: Current cycle to update with injection data
        """
        from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog

        if dialog.detected_injection_time is not None:
            # Dialog auto-detected injection — place flag for primary channel
            logger.info(
                f"✓ Injection auto-detected: channel {dialog.detected_channel.upper()} "
                f"at t={dialog.detected_injection_time:.1f}s "
                f"(confidence: {dialog.detected_confidence:.0%})"
            )
            self.injection_flag_requested.emit(
                dialog.detected_channel,
                dialog.detected_injection_time,
                dialog.detected_confidence,
            )

            # Use dialog's per-channel results (already scanned during grace period)
            if dialog._detected_channels_results:
                cycle.injection_time_by_channel = {
                    ch: r['time'] for ch, r in dialog._detected_channels_results.items()
                }
                cycle.injection_confidence_by_channel = {
                    ch: r['confidence'] for ch, r in dialog._detected_channels_results.items()
                }
                logger.info(
                    f"Per-channel injection times from dialog: "
                    f"{list(cycle.injection_time_by_channel.keys())} "
                    f"(confidences: {cycle.injection_confidence_by_channel})"
                )
            else:
                # Fallback: retroactive scan if dialog didn't capture per-channel
                self._window_start_time = dialog.window_start_time
                self._scan_all_channels_for_injection()

            # Track injection count for binding/kinetic cycles
            if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                cycle.injection_count += 1
                logger.info(
                    f"  Injection count: {cycle.injection_count}/"
                    f"{len(cycle.planned_concentrations)}"
                )
        else:
            # Timeout — no injection detected, still count
            logger.warning("60s window expired — no injection peak detected")
            if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                cycle.injection_count += 1

    # ------------------------------------------------------------------
    # Per-channel injection scan
    # ------------------------------------------------------------------

    def _scan_all_channels_for_injection(self):
        """Retroactively scan all 4 channels for injection points.

        Uses the detection window (window_start → now) to find per-channel
        injection times. Stores results on the current cycle and flags any
        channels that detected injection but are not in the cycle's active
        channel set (potential mislabeling).
        """
        cycle = self._current_cycle
        if not cycle or not self.buffer_mgr or self._window_start_time is None:
            return

        try:
            import numpy as np
            from affilabs.utils.spr_signal_processing import detect_injection_all_channels

            # Determine window end = current latest time
            window_end = self._window_start_time + 60.0  # max window
            for ch in ['a', 'b', 'c', 'd']:
                if ch in self.buffer_mgr.timeline_data:
                    ch_data = self.buffer_mgr.timeline_data[ch]
                    if ch_data and len(ch_data.time) > 0:
                        window_end = max(window_end, float(np.array(ch_data.time)[-1]))
                        break

            result = detect_injection_all_channels(
                self.buffer_mgr.timeline_data,
                self._window_start_time,
                window_end,
                min_confidence=0.70,
            )

            # Store per-channel injection times on cycle
            cycle.injection_time_by_channel = result['times']
            cycle.injection_confidence_by_channel = result['confidences']

            detected_channels = list(result['times'].keys())
            logger.info(
                f"Per-channel injection scan: detected on {detected_channels} "
                f"(confidences: {result['confidences']})"
            )

            # --- Mislabel detection ---
            # Determine expected active channels from cycle settings
            active_ch_str = (cycle.channels or "ABCD").upper()
            active_channels = set(active_ch_str)

            mislabel_flags = {}
            for ch, conf in result['confidences'].items():
                if ch not in active_channels:
                    mislabel_flags[ch] = 'inactive_channel'
                    logger.warning(
                        f"⚠ Mislabel warning: Channel {ch} detected injection "
                        f"(confidence: {conf:.0%}) but is not in active set "
                        f"({active_ch_str}). Signal may be optical artifact."
                    )
            cycle.injection_mislabel_flags = mislabel_flags

        except Exception as e:
            logger.warning(f"Per-channel injection scan failed: {e}")

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
            if hasattr(ctrl, 'knx_six_both'):
                ctrl.knx_six_both(state=0)
        except Exception as e:
            logger.error(f"Failed to close valves: {e}")
