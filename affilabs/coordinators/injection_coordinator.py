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
- Manual mode: NON-BLOCKING — updates UnifiedCycleBar inline, runs detection in background
- Automated mode: Executes pump injection in background thread
- Event logging: Differentiates manual vs automated injections

NON-BLOCKING MANUAL INJECTION (v2 — Unified Cycle Bar):
- Instead of showing a blocking modal dialog (.exec()), the coordinator:
  1. Emits injection_ui_requested to show INJECT state in the unified bar
  2. Starts background detection timer (200ms polling)
  3. When injection detected or 60s expires → emits injection_completed
  4. User clicks Done → coordinator continues detection 10s then completes
  5. User clicks Cancel → coordinator stops and emits injection_cancelled

HARDWARE MODES:
- P4SPR + No Pump → Manual injection (unified bar shown)
- P4SPR + AffiPump → Automated injection (pump controlled)
- P4PRO/P4PROPLUS → Automated injection (internal pumps)

USAGE:
    from affilabs.coordinators.injection_coordinator import InjectionCoordinator

    coordinator = InjectionCoordinator(hardware_mgr, pump_mgr, parent=main_window)

    # Execute injection (mode detected automatically or from cycle setting)
    # Manual mode is NON-BLOCKING — result comes via signals
    coordinator.execute_injection(cycle, flow_rate=100.0, parent_widget=window)

    # Connect to results:
    coordinator.injection_completed.connect(on_injection_done)
    coordinator.injection_cancelled.connect(on_injection_cancelled)
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QTimer, Signal

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
    - Display manual injection state in UnifiedCycleBar (non-blocking)
    - Run real-time injection detection in background
    - Execute automated injections via PumpManager
    - Handle valve control for manual injections
    - Log injection events differently based on mode

    Signals:
        injection_started: Injection sequence started (arg: injection_type str)
        injection_completed: Injection completed successfully
        injection_cancelled: User cancelled manual injection
        manual_prompt_shown: Manual injection prompt displayed (in unified bar)
        injection_flag_requested: Place injection flag (args: channel, injection_time, confidence)
        injection_ui_requested: Request unified bar to show INJECT state
            (args: sample_info dict, injection_num or None, total_injections or None)
        injection_detection_tick: Detection countdown update (arg: remaining_seconds int)
        injection_auto_detected: Injection peak detected
            (args: channel str, time float, confidence float)
        injection_window_expired: 60-second detection window expired
    """

    injection_started = Signal(str)  # injection_type
    injection_completed = Signal()
    injection_cancelled = Signal()
    manual_prompt_shown = Signal()
    injection_flag_requested = Signal(str, float, float)  # channel, injection_time, confidence

    # Non-blocking manual injection signals (v2)
    injection_ui_requested = Signal(object, object, object)  # sample_info, inj_num, total
    injection_detection_tick = Signal(int)  # remaining_seconds
    injection_auto_detected = Signal(str, float, float)  # channel, time, confidence
    injection_window_expired = Signal()

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

        # Detection state (for non-blocking manual injection)
        self._detection_active = False
        self._detection_timer: Optional[QTimer] = None
        self._status_timer: Optional[QTimer] = None
        self._window_start_time: Optional[float] = None
        self._detection_start_wall: Optional[float] = None
        self._detection_channels: str = "ABCD"
        self._user_done: bool = False
        self._done_timestamp: Optional[float] = None
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
        """Start non-blocking manual injection — shows INJECT state in unified bar.

        Instead of showing a blocking modal dialog, this method:
        1. Opens valves for manual injection
        2. Emits injection_ui_requested to show INJECT state in unified bar
        3. Starts background injection detection (200ms polling)
        4. Returns immediately — result delivered via signals

        User interactions from the unified bar:
        - Done Injecting → on_user_done_injecting() → continues detection 10s
        - Cancel → on_user_cancelled_injection() → stops and emits injection_cancelled

        Args:
            cycle: Cycle requiring injection
            parent_widget: Parent widget (unused in non-blocking mode)

        Returns:
            True always (non-blocking — actual result via signals)
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

        if result == ManualInjectionDialog.DialogCode.Accepted:
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

            # Close valves and emit completed (triggers contact countdown)
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
        else:
            # User cancelled
            logger.info("❌ Injection cancelled by user")
            self._close_valves_after_manual_injection()
            self.injection_cancelled.emit()

        return result == ManualInjectionDialog.DialogCode.Accepted

    # ------------------------------------------------------------------
    # Non-blocking injection detection
    # ------------------------------------------------------------------

    def _start_injection_detection(self):
        """Start background monitoring for injection within 60-second window.

        Polls buffer_mgr every 200ms using auto_detect_injection_point.
        Emits injection_detection_tick(remaining) every second for UI updates.
        """
        if not self.buffer_mgr or not self.buffer_mgr.timeline_data:
            logger.warning("Cannot start detection - no data available")
            # Complete immediately without detection
            self._complete_injection(detected=False)
            return

        # Get current time as window start
        first_channel = self._detection_channels[0].lower()
        if first_channel in self.buffer_mgr.timeline_data:
            channel_data = self.buffer_mgr.timeline_data[first_channel]
            if channel_data and len(channel_data.time) > 0:
                import numpy as np
                times = np.array(channel_data.time)
                self._window_start_time = times[-1]
            else:
                logger.warning("No time data available in channel")
                self._complete_injection(detected=False)
                return
        else:
            logger.warning(f"Channel {first_channel} not found in timeline data")
            self._complete_injection(detected=False)
            return

        self._detection_active = True
        self._user_done = False
        self._done_timestamp = None
        self._detection_start_wall = time.time()

        logger.info(f"Detection started - monitoring channels: {self._detection_channels}")

        # 200ms detection timer
        self._detection_timer = QTimer(self)
        self._detection_timer.timeout.connect(self._check_for_injection)
        self._detection_timer.start(200)

        # 1s status update timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_detection_status)
        self._status_timer.start(1000)

    def _check_for_injection(self):
        """Check for injection peak in current data window (200ms polling).

        Hard timeout: 60 seconds total from detection start.
        After user clicks Done: continues detection for 10 more seconds.
        """
        if not self._detection_active or not self.buffer_mgr or self._window_start_time is None:
            return

        try:
            from affilabs.utils.spr_signal_processing import auto_detect_injection_point
            import numpy as np

            # Hard 60-second limit
            elapsed = time.time() - self._detection_start_wall
            if elapsed >= 60.0:
                self._on_detection_timeout()
                return

            # If user clicked Done, allow 10 more seconds then accept
            if self._user_done and self._done_timestamp:
                since_done = time.time() - self._done_timestamp
                if since_done >= 10.0:
                    logger.info("10s post-Done window expired — completing injection")
                    self._complete_injection(detected=False)
                    return

            # Try each channel in priority order
            for channel_letter in self._detection_channels.lower():
                if channel_letter not in self.buffer_mgr.timeline_data:
                    continue

                channel_data = self.buffer_mgr.timeline_data[channel_letter]
                if not channel_data or len(channel_data.time) < 10:
                    continue

                times = np.array(channel_data.time)
                wavelengths = np.array(channel_data.wavelength)

                if len(times) < 10 or len(wavelengths) < 10:
                    continue

                current_time = times[-1]

                # Data within detection window
                window_mask = (times >= self._window_start_time) & (times <= current_time)
                window_times = times[window_mask]
                window_wl = wavelengths[window_mask]

                if len(window_times) < 10:
                    continue

                # Convert wavelength to RU
                baseline = window_wl[0] if len(window_wl) > 0 else 0
                window_ru = (window_wl - baseline) * 355.0

                result = auto_detect_injection_point(window_times, window_ru)

                # Accept detection if confidence > 70%
                if result['injection_time'] is not None and result['confidence'] > 0.70:
                    self._on_injection_detected(
                        result['injection_time'],
                        result['confidence'],
                        channel_letter,
                    )
                    return

        except Exception as e:
            logger.debug(f"Detection check error: {e}")

    def _update_detection_status(self):
        """Emit detection countdown for unified bar (called every 1 second)."""
        if not self._detection_active or not self._detection_start_wall:
            return
        elapsed = time.time() - self._detection_start_wall
        remaining = max(0, 60 - int(elapsed))
        self.injection_detection_tick.emit(remaining)

    def _on_injection_detected(self, injection_time: float, confidence: float, channel: str):
        """Injection peak detected — scan all channels, place flag, and complete.

        After initial detection on one channel, retroactively scans all four
        channels to find per-channel injection times. This is critical because
        channels may have slightly different injection times due to flow path
        geometry. Results stored on cycle for delta SPR calculation.
        """
        if not self._detection_active:
            return
        self._stop_detection()

        logger.info(
            f"✓ Injection detected at {injection_time:.2f}s "
            f"(confidence: {confidence:.0%}) on channel {channel}"
        )

        # Emit detection for unified bar visual feedback
        self.injection_auto_detected.emit(channel, injection_time, confidence)

        # Place injection flag
        self.injection_flag_requested.emit(channel, injection_time, confidence)

        # --- Per-channel injection scan ---
        self._scan_all_channels_for_injection()

        # Track injection count for binding/kinetic cycles
        cycle = self._current_cycle
        if cycle and cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
            cycle.injection_count += 1

        # Close valves
        self._close_valves_after_manual_injection()

        # 3-second delay for user to see all detection results before transitioning
        QTimer.singleShot(3000, self.injection_completed.emit)

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

    def _log_detection_success(self):
        """Placeholder - detection success already shown in unified bar UI.
        
        Suppressed to reduce verbose logging. The injection flag and detection
        results are already displayed in the cycle bar and detection dialog.
        """
        pass

    def _on_detection_timeout(self):
        """60-second detection window expired without clear detection."""
        if not self._detection_active:
            return

        logger.warning("⚠ 60-second injection window expired — no clear peak detected")
        self.injection_window_expired.emit()
        self._complete_injection(detected=False)

    def _complete_injection(self, detected: bool):
        """Finalize manual injection (detected or not).

        Args:
            detected: True if injection was auto-detected (flag already placed)
        """
        self._stop_detection()

        cycle = self._current_cycle
        if cycle and not detected:
            # Track injection count even without detection
            if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                cycle.injection_count += 1
                logger.info(f"  Injection count: {cycle.injection_count}/{len(cycle.planned_concentrations)}")

        self._close_valves_after_manual_injection()
        self.injection_completed.emit()

    def _stop_detection(self):
        """Stop all detection timers."""
        self._detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
            self._detection_timer = None
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer = None

    # ------------------------------------------------------------------
    # User actions from unified bar
    # ------------------------------------------------------------------

    def on_user_done_injecting(self):
        """Handle 'Done Injecting' click from unified bar.

        Marks injection as user-confirmed. Detection continues for 10 more
        seconds to find the injection peak, then completes regardless.
        """
        self._user_done = True
        self._done_timestamp = time.time()
        logger.info("User marked injection as done — continuing detection for 10s")

    def on_user_cancelled_injection(self):
        """Handle 'Cancel' click from unified bar."""
        logger.info("⚠️ User cancelled manual injection")
        self._stop_detection()
        self._close_valves_after_manual_injection()
        self.injection_cancelled.emit()

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
