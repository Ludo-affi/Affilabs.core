"""Pump and Injection Control Mixin for Affilabs.core

This mixin provides pump control, valve management, and injection sequencing
functionality for the main application. Extracted from main.py for modularity.

Methods (42 total):
===================
Pump Lifecycle:
    - _stop_pump_for_cycle_transition
    - _schedule_injection
    - _execute_injection
    - _trigger_simple_injection
    - _trigger_partial_injection
    - _on_injection_cancelled
    - _place_injection_flag

Pump Manager Callbacks:
    - _on_pump_initialized
    - _on_pump_error
    - _on_pump_state_changed
    - _on_valve_switched
    - _on_pump_operation_started
    - _on_pump_operation_progress
    - _on_pump_operation_completed
    - _on_pump_status_updated

Valve Control:
    - _poll_valve_positions
    - _on_valve_sync_toggled
    - _on_loop_valve_switched
    - _on_channel_valve_switched

Flow Tab UI Handlers:
    - _on_pump_prime_clicked
    - _on_pump_cleanup_clicked
    - _on_inject_simple_clicked
    - _on_inject_partial_clicked
    - _on_home_pumps_clicked
    - _on_flow_rate_changed

Internal Pump Control (P4PROPLUS):
    - _update_internal_pump_visibility
    - _on_internal_pump1_toggle
    - _on_synced_pump_toggle
    - _on_internal_pump_inject_30s
    - _close_inject_valve
    - _save_pump_corrections
    - _update_internal_pump_status
    - _sync_pump_button_states
    - _on_synced_flowrate_changed
    - _on_pump1_rpm_changed
    - _update_pump1_rpm
    - _on_internal_pump_sync_toggled
    - _on_internal_pump_flowrate_changed
    - _create_injection_alignment_line

Background Task Classes:
    - _PumpStartTask
    - _PumpStopTask

Dependencies:
    - threading, time, asyncio (async pump operations)
    - PySide6.QtCore (QTimer, QRunnable, QThreadPool)
    - PySide6.QtWidgets (QMessageBox)
    - numpy (array operations)
    - logger (application logger)
    - Colors (UI styling constants)
    - show_message (message dialog helper)
    - TimeBase (time conversion utilities)

Last Updated: 2026-02-17
"""

import threading
import time

import numpy as np
from PySide6.QtCore import QTimer, QRunnable, QThreadPool
from PySide6.QtWidgets import QMessageBox

from affilabs.ui_styles import Colors
from affilabs.widgets.message import show_message
from affilabs.core.experiment_clock import TimeBase

# Logger is assumed to be available at module level in main.py context
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class PumpMixin:
    """Mixin providing pump control and injection sequencing functionality.
    
    This mixin is intended to be mixed into the main application class.
    It assumes the following attributes are available:
        - self.pump_mgr: PumpManager instance
        - self.hardware_mgr: HardwareManager instance
        - self.injection_coordinator: InjectionCoordinator instance
        - self.main_window: Main window instance with UI elements
        - self.clock: ExperimentClock instance
        - self.buffer_mgr: BufferManager instance
        - self.flag_mgr: FlagManager instance (optional)
        - self.recording_mgr: RecordingManager instance (optional)
    """

    # =========================================================================
    # PUMP LIFECYCLE & INJECTION CONTROL
    # =========================================================================

    def _stop_pump_for_cycle_transition(self):
        """Stop any running pump operation for cycle transition (runs in background)."""
        def run_stop():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.stop_and_wait_for_idle(timeout=15.0))
            finally:
                loop.close()

        thread = threading.Thread(target=run_stop, daemon=True, name="StopPumpForCycle")
        thread.start()

    def _schedule_injection(self, cycle):
        """Pre-announce injection on Contact Monitor then execute on a background thread.

        For binding cycles in manual mode, shows the Contact Monitor bar with
        sample info. InjectionCoordinator + _InjectionMonitor handle detection.
        Always spawns a thread — _execute_manual_injection blocks on done_event.wait()
        and must never run on the main thread.
        """
        is_manual_mode = self.hardware_mgr.requires_manual_injection

        if (is_manual_mode and
                cycle.type in ("Binding", "Kinetic", "Concentration") and
                getattr(cycle, 'injection_count', 0) == 0):

            # Pre-announce on the Contact Monitor bar
            units = getattr(cycle, 'units', 'nM') or 'nM'
            if cycle.concentrations:
                active_chs  = "".join(sorted(cycle.concentrations.keys()))
                chs_display = ", ".join(sorted(cycle.concentrations.keys()))
                vals        = list(cycle.concentrations.values())
                _label      = f"Ch {chs_display} · {vals[0]}{units}" if vals else f"Ch {chs_display}"
            elif cycle.planned_concentrations:
                _label     = cycle.planned_concentrations[0]
                active_chs = "ABCD"
            else:
                _label     = cycle.name or "Binding"
                active_chs = "ABCD"
            if cycle.contact_time:
                _label += f" · {int(cycle.contact_time)}s"

            _bar = getattr(getattr(self.main_window, 'sidebar', None), 'injection_action_bar', None)
            if _bar is not None:
                _bar.set_upcoming(_label, active_chs)

            threading.Thread(
                target=self._execute_injection,
                args=(cycle,),
                daemon=True,
                name="ManualInjectionExec",
            ).start()
        else:
            # Delayed injection (automated or 2nd+ binding)
            delay_ms = int(cycle.injection_delay * 1000)
            logger.info(f"Injection scheduled in {cycle.injection_delay}s ({cycle.injection_method})")
            def _start_delayed_injection():
                threading.Thread(
                    target=self._execute_injection,
                    args=(cycle,),
                    daemon=True,
                    name="ManualInjectionExec",
                ).start()
            QTimer.singleShot(delay_ms, _start_delayed_injection)

    def _execute_injection(self, cycle):
        """Execute injection for cycle — delegates to InjectionCoordinator.

        Runs on a background thread. InjectionCoordinator.execute_injection blocks
        on done_event.wait() for the full injection lifecycle (detection + contact time).
        """
        has_affipump = self.pump_mgr.is_available
        has_internal = (
            self.hardware_mgr.ctrl
            and hasattr(self.hardware_mgr.ctrl, "has_internal_pumps")
            and self.hardware_mgr.ctrl.has_internal_pumps()
        )
        is_manual_mode = self.hardware_mgr.requires_manual_injection

        if not has_affipump and not has_internal and not is_manual_mode:
            logger.error("❌ Injection failed - no pump or manual injection available")
            self.main_window.set_intel_message(
                "❌ Injection failed - no hardware", "#FF3B30"
            )
            return

        # Get flow rate (cycle.flow_rate takes priority over UI spin)
        if cycle.flow_rate is not None and cycle.flow_rate > 0:
            assay_rate = cycle.flow_rate
            logger.info(
                f"Using cycle flow_rate: {assay_rate} µL/min (from method definition)"
            )
        else:
            assay_rate = 100.0
            if spin := self._sidebar_widget("pump_assay_spin"):
                assay_rate = float(spin.value())
            logger.info(f"Using UI assay rate: {assay_rate} µL/min (no cycle flow_rate set)")

        success = self.injection_coordinator.execute_injection(
            cycle, assay_rate, parent_widget=self.main_window
        )

        if not success:
            logger.warning("Injection was cancelled at schedule stage")

    def _trigger_simple_injection(self, assay_rate: float):
        """Trigger simple injection (reuse existing code).

        Args:
            assay_rate: Flow rate in µL/min
        """
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_simple(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="AutoInjectSimple")
        thread.start()

    def _trigger_partial_injection(self, assay_rate: float):
        """Trigger partial injection (reuse existing code).

        Args:
            assay_rate: Flow rate in µL/min
        """
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_partial_loop(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="AutoInjectPartial")
        thread.start()

    def _on_injection_cancelled(self):
        """Handle user cancellation of injection — remove stale marker and log."""
        logger.info("❌ Injection cancelled by user")
        if self._contact_time_marker is not None:
            try:
                graph = self.main_window.cycle_of_interest_graph
                graph.removeItem(self._contact_time_marker)
            except Exception:
                pass
            self._contact_time_marker = None

    def _show_contact_time_marker(self):
        """No-op — contact end marker removed. Timer is managed by the Contact Monitor."""
        pass

    def _place_injection_flag(self, channel: str, injection_time: float, confidence: float):
        """Place injection flag directly from dialog's pre-detected result.

        Called when the ManualInjectionDialog's real-time detection found the
        injection point. Places a flag marker without re-running detection.

        Args:
            channel: Channel letter where injection was detected (e.g., "a")
            injection_time: Injection time in raw elapsed seconds
            confidence: Detection confidence (0.0 - 1.0)
        """
        import numpy as np

        try:
            ch = channel.lower()
            logger.info(
                f"📍 Placing injection flag from dialog detection: "
                f"Channel {ch.upper()} at t={injection_time:.2f}s (confidence: {confidence:.0%})"
            )

            if not hasattr(self, 'flag_mgr'):
                logger.warning("⚠️ FlagManager not available, could not place flag")
                return

            # Convert raw timeline time → Active Cycle display coordinates
            from affilabs.core.experiment_clock import TimeBase
            start_cursor_display = self.main_window.full_timeline_graph.start_cursor.value()
            start_time_raw = self.clock.convert(start_cursor_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED)
            injection_display_time = injection_time - start_time_raw

            if injection_display_time < 0:
                # Auto-detection fired just before cycle start — clamp to 0 so the
                # flag still appears at the cycle boundary rather than raising.
                logger.debug(
                    f"Injection display time was {injection_display_time:.2f}s (pre-cycle); clamped to 0."
                )
                injection_display_time = 0.0

            # Get SPR value from cycle_data (matches what's displayed on graph)
            spr_val = 0
            if (ch in self.buffer_mgr.cycle_data and
                    len(self.buffer_mgr.cycle_data[ch].time) > 0):
                cycle_time = self.buffer_mgr.cycle_data[ch].time
                cycle_spr = self.buffer_mgr.cycle_data[ch].spr
                if len(cycle_spr) > 0:
                    inj_idx = np.argmin(np.abs(cycle_time - injection_time))
                    spr_val = cycle_spr[inj_idx]

            self.flag_mgr.add_flag_marker(
                channel=ch,
                time_val=injection_display_time,
                spr_val=spr_val,
                flag_type='injection'
            )
            # Store for binding stats and timer reference
            self._last_injection_display_time = injection_display_time

            # Set ΔSPR baseline on Contact Monitor — spr_val is time-matched to t_fire
            # so the STATUS column shows 0 RU at injection and grows with binding response
            try:
                bar = getattr(self.main_window, 'injection_action_bar', None)
                if bar is not None:
                    bar.set_injection_baseline(ch, spr_val)
            except Exception:
                pass
            logger.info(
                f"✓ Injection flag placed on Channel {ch.upper()} "
                f"at display t={injection_display_time:.2f}s (SPR={spr_val:.1f} RU)"
            )

            # ── Live binding stats: pre-baseline + scheduled slope/anchor freeze ──
            try:
                from affilabs.utils.live_binding_stats import compute_pre_baseline
                from PySide6.QtCore import QTimer

                cycle_num = getattr(self._current_cycle, 'cycle_num', 0) if self._current_cycle else 0

                if (ch in self.buffer_mgr.cycle_data
                        and len(self.buffer_mgr.cycle_data[ch].time) > 0):
                    _ct = np.asarray(self.buffer_mgr.cycle_data[ch].time)
                    _cs = np.asarray(self.buffer_mgr.cycle_data[ch].wavelength)
                    pre_bl = compute_pre_baseline(_ct, _cs, injection_time)
                else:
                    pre_bl = None

                # Initialise stats entry for this channel
                if not hasattr(self, '_injection_stats'):
                    self._injection_stats = {}
                self._injection_stats[(cycle_num, ch)] = {
                    'injection_time': injection_time,
                    'pre_baseline_nm': pre_bl,
                    'slope_nm_per_s': None,
                    'slope_frozen': False,
                    'anchor_nm': None,
                    'anchor_frozen': False,
                    'post_baseline_nm': None,
                    'delta_spr_ru': None,
                }
                logger.debug(
                    f"📊 Injection stats init: cycle={cycle_num} ch={ch.upper()} "
                    f"pre_bl={pre_bl:.4f}nm" if pre_bl is not None else
                    f"📊 Injection stats init: cycle={cycle_num} ch={ch.upper()} pre_bl=None"
                )

                # Freeze slope at t + 15 s
                def _freeze_slope(c=cycle_num, channel=ch, inj_t=injection_time):
                    try:
                        from affilabs.utils.live_binding_stats import compute_slope
                        entry = self._injection_stats.get((c, channel))
                        if entry is None or entry['slope_frozen']:
                            return
                        if channel in self.buffer_mgr.cycle_data:
                            _t = np.asarray(self.buffer_mgr.cycle_data[channel].time)
                            _s = np.asarray(self.buffer_mgr.cycle_data[channel].wavelength)
                            entry['slope_nm_per_s'] = compute_slope(_t, _s, inj_t)
                        entry['slope_frozen'] = True
                        logger.debug(f"📊 Slope frozen: cycle={c} ch={channel.upper()} "
                                     f"slope={entry['slope_nm_per_s']}")
                    except Exception as _e:
                        logger.debug(f"slope freeze error: {_e}")

                QTimer.singleShot(15_000, _freeze_slope)

                # Freeze anchor at t + 20 s
                def _freeze_anchor(c=cycle_num, channel=ch, inj_t=injection_time):
                    try:
                        from affilabs.utils.live_binding_stats import compute_anchor
                        entry = self._injection_stats.get((c, channel))
                        if entry is None or entry['anchor_frozen']:
                            return
                        if channel in self.buffer_mgr.cycle_data:
                            _t = np.asarray(self.buffer_mgr.cycle_data[channel].time)
                            _s = np.asarray(self.buffer_mgr.cycle_data[channel].wavelength)
                            entry['anchor_nm'] = compute_anchor(_t, _s, inj_t)
                        entry['anchor_frozen'] = True
                        logger.debug(f"📊 Anchor frozen: cycle={c} ch={channel.upper()} "
                                     f"anchor={entry['anchor_nm']}")
                    except Exception as _e:
                        logger.debug(f"anchor freeze error: {_e}")

                QTimer.singleShot(20_000, _freeze_anchor)

            except Exception as _stats_err:
                logger.debug(f"Could not init injection stats: {_stats_err}")
            # ── end live binding stats ─────────────────────────────────────────

            # Start contact timer ONCE if cycle has contact_time defined
            # Guard: only start if no manual timer is already running (avoids restart
            # when injection_flag_requested fires for each detected channel)
            timer_already_running = (
                hasattr(self.main_window, '_manual_timer')
                and self.main_window._manual_timer
                and self.main_window._manual_timer.isActive()
            )
            if (not timer_already_running
                    and hasattr(self, '_current_cycle') and self._current_cycle
                    and hasattr(self._current_cycle, 'contact_time')
                    and self._current_cycle.contact_time
                    and self._current_cycle.contact_time > 0):
                contact_seconds = int(self._current_cycle.contact_time)
                logger.info(f"⏱ Starting contact timer: {contact_seconds}s")

                # Drive the inline queue-table countdown
                try:
                    tbl = self.sidebar.summary_table
                    tbl.start_contact_countdown(contact_seconds)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ Error placing injection flag: {e}")
            logger.exception(e)

    # =========================================================================
    # PUMP MANAGER EVENT HANDLERS
    # =========================================================================

    def _on_pump_initialized(self):
        """Pump initialized successfully."""
        logger.debug("✓ Pump initialized")
        # TODO: Enable pump controls in UI

    def _on_pump_error(self, error: str):
        """Pump error occurred - show message and update intelligence bar."""
        logger.error(f"Pump error: {error}")

        # Update intelligence bar with error
        self.main_window.set_intel_message(f"❌ Pump: {error}", "#FF3B30")

        from affilabs.widgets.message import show_message

        show_message(error, "Pump Error")

    def _on_pump_state_changed(self, state: dict):
        """Pump state changed."""
        self.peripheral_events.on_pump_state_changed(state)

    def _on_valve_switched(self, valve_info: dict):
        """Valve position changed."""
        self.peripheral_events.on_valve_switched(valve_info)

    # === PUMP MANAGER STATUS HANDLERS ===

    def _on_pump_operation_started(self, operation: str):
        """Handle pump operation started - update status board + intelligence bar."""
        logger.info(f"🔧 Pump operation started: {operation}")
        display_name = operation.replace('_', ' ').title()

        # Update intelligence bar
        self.main_window.set_intel_message(f"⚡ Pump: {display_name}", "#007AFF")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(display_name)
        if hasattr(ui, 'flow_pump_status_icon'):
            ui.flow_pump_status_icon.setStyleSheet(
                "font-size: 12px; color: #34C759; background: transparent;"
            )

    def _on_pump_operation_progress(self, operation: str, progress: int, message: str):
        """Handle pump operation progress - update status board + intelligence bar."""
        display_name = operation.replace('_', ' ').title()

        # Update intelligence bar with progress
        self.main_window.set_intel_message(f"⚡ Pump: {display_name} ({progress}%)", "#007AFF")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(f"{display_name} ({progress}%)")

    def _on_pump_operation_completed(self, operation: str, success: bool):
        """Handle pump operation completed - reset status board + intelligence bar."""
        status_icon = "✓" if success else "✗"
        display_name = operation.replace('_', ' ').title()
        logger.info(f"🔧 Pump operation completed: {operation} {status_icon}")

        # Update intelligence bar with result
        if success:
            self.main_window.set_intel_message(f"✓ Pump: {display_name} complete", "#34C759")
        else:
            self.main_window.set_intel_message(f"✗ Pump: {display_name} failed", "#FF3B30")

        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText("Idle")
        if hasattr(ui, 'flow_pump_status_icon'):
            ui.flow_pump_status_icon.setStyleSheet(
                "font-size: 12px; color: #86868B; background: transparent;"
            )
        if hasattr(ui, 'flow_current_rate'):
            ui.flow_current_rate.setText("0")

        # Always reset buffer button text when any pump operation completes
        # (buffer may have been stopped by cycle transition or injection)
        if btn := self._sidebar_widget('start_buffer_btn'):
            btn.setText("Start Buffer")

    def _on_pump_status_updated(self, status: str, flow_rate: float, plunger_pos: float, contact_time_current: float, contact_time_expected: float):
        """Handle real-time pump status update - update all status board values."""
        ui = self.main_window.sidebar
        if hasattr(ui, 'flow_pump_status_label'):
            ui.flow_pump_status_label.setText(status)
        if hasattr(ui, 'flow_pump_status_icon'):
            color = Colors.SUCCESS if status != "Idle" else Colors.SECONDARY_TEXT
            ui.flow_pump_status_icon.setStyleSheet(
                f"font-size: 12px; color: {color}; background: transparent;"
            )
        if hasattr(ui, 'flow_current_rate'):
            ui.flow_current_rate.setText(f"{flow_rate:.0f}")
        if hasattr(ui, 'flow_plunger_position'):
            ui.flow_plunger_position.setText(f"{plunger_pos:.0f}")
        if hasattr(ui, 'flow_contact_time'):
            # Display as "current / expected" format (e.g., "22 / 120")
            if contact_time_expected > 0:
                ui.flow_contact_time.setText(f"{contact_time_current:.0f} / {contact_time_expected:.0f}")
            else:
                ui.flow_contact_time.setText(f"{contact_time_current:.1f}")

    # =========================================================================
    # VALVE CONTROL
    # =========================================================================

    def _poll_valve_positions(self):
        """Poll valve positions every 3 seconds and sync UI to hardware state."""
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            return

        try:
            # Only poll valves if controller supports them (P4PRO has 6-port valves, P4SPR doesn't)
            if not hasattr(ctrl, 'knx_six_state'):
                return

            # Valve state is tracked by controller based on last command sent
            # We update UI when commands are sent, so polling just ensures consistency
            kc1_loop = ctrl.knx_six_state(1)
            kc2_loop = ctrl.knx_six_state(2)
            kc1_channel = ctrl.knx_three_state(1)
            kc2_channel = ctrl.knx_three_state(2)

            ui = self.main_window.sidebar

            # Update UI only if we have a cached state
            if kc1_loop is not None and hasattr(ui, 'kc1_loop_btn_load'):
                ui.kc1_loop_btn_load.blockSignals(True)
                ui.kc1_loop_btn_sensor.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc1_loop_btn_load.setChecked(False)
                ui.kc1_loop_btn_sensor.setChecked(False)
                if kc1_loop == 0:
                    ui.kc1_loop_btn_load.setChecked(True)
                else:
                    ui.kc1_loop_btn_sensor.setChecked(True)
                ui.kc1_loop_btn_load.blockSignals(False)
                ui.kc1_loop_btn_sensor.blockSignals(False)

            if kc2_loop is not None and hasattr(ui, 'kc2_loop_btn_load'):
                ui.kc2_loop_btn_load.blockSignals(True)
                ui.kc2_loop_btn_sensor.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc2_loop_btn_load.setChecked(False)
                ui.kc2_loop_btn_sensor.setChecked(False)
                if kc2_loop == 0:
                    ui.kc2_loop_btn_load.setChecked(True)
                else:
                    ui.kc2_loop_btn_sensor.setChecked(True)
                ui.kc2_loop_btn_load.blockSignals(False)
                ui.kc2_loop_btn_sensor.blockSignals(False)

            # Update KC1 Channel (A/B)
            # state=0: A active, state=1: B active
            if kc1_channel is not None and hasattr(ui, 'kc1_channel_btn_a'):
                ui.kc1_channel_btn_a.blockSignals(True)
                ui.kc1_channel_btn_b.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc1_channel_btn_a.setChecked(False)
                ui.kc1_channel_btn_b.setChecked(False)
                if kc1_channel == 0:
                    ui.kc1_channel_btn_a.setChecked(True)
                else:
                    ui.kc1_channel_btn_b.setChecked(True)
                ui.kc1_channel_btn_a.blockSignals(False)
                ui.kc1_channel_btn_b.blockSignals(False)

            # Update KC2 Channel (C/D)
            # state=0: C active, state=1: D active
            if kc2_channel is not None and hasattr(ui, 'kc2_channel_btn_c'):
                ui.kc2_channel_btn_c.blockSignals(True)
                ui.kc2_channel_btn_d.blockSignals(True)
                # Uncheck both first to prevent overlap, then set correct state
                ui.kc2_channel_btn_c.setChecked(False)
                ui.kc2_channel_btn_d.setChecked(False)
                if kc2_channel == 0:
                    ui.kc2_channel_btn_c.setChecked(True)
                else:
                    ui.kc2_channel_btn_d.setChecked(True)
                ui.kc2_channel_btn_c.blockSignals(False)
                ui.kc2_channel_btn_d.blockSignals(False)

        except Exception as e:
            logger.debug(f"Valve poll error: {e}")

    # === FLOW TAB HANDLERS ===

    def _on_pump_prime_clicked(self):
        """User clicked Prime Pump button - run prime sequence via PumpManager."""
        logger.info("🔧 Prime Pump requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Read prime speed from UI spinbox if available
        prime_speed = 24000.0  # default µL/min
        ui = self.main_window.sidebar
        if hasattr(ui, 'prime_spin'):
            prime_speed = ui.prime_spin.value()
            logger.info(f"Using prime speed from UI: {prime_speed} µL/min")

        # Run prime pump in background
        def run_prime():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.prime_pump(
                    aspirate_speed=prime_speed,
                    dispense_speed=min(prime_speed, 5000.0),
                ))
            finally:
                loop.close()

        thread = threading.Thread(target=run_prime, daemon=True, name="PrimePump")
        thread.start()

    def _on_pump_cleanup_clicked(self):
        """User clicked Clean Pump button - run cleanup sequence via PumpManager."""
        logger.info("🧹 Pump Cleanup requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Run cleanup in background
        def run_cleanup():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.cleanup_pump())
            finally:
                loop.close()

        thread = threading.Thread(target=run_cleanup, daemon=True, name="CleanupPump")
        thread.start()

    def _on_inject_simple_clicked(self):
        """User clicked Simple Inject button - run simple injection via PumpManager."""
        logger.info("💉 Simple Injection requested")

        # Check for EITHER AffiPump OR P4PROPLUS internal pumps
        has_affipump = self.pump_mgr.is_available
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if not has_affipump and not has_internal:
            from affilabs.widgets.message import show_message
            show_message("No pump available. Connect AffiPump or use P4PROPLUS with internal pumps.", "Warning")
            return

        # If using AffiPump, check if it's idle
        if has_affipump and not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get assay rate from UI (default 100 µL/min if not available)
        assay_rate = 100.0
        if spin := self._sidebar_widget('pump_assay_spin'):
            assay_rate = float(spin.value())

        logger.info(f"  Using assay rate: {assay_rate} uL/min")

        # Run simple inject in background
        def run_inject():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_simple(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject, daemon=True, name="InjectSimple")
        thread.start()

    def _on_inject_partial_clicked(self):
        """User clicked Partial Loop Inject button - run partial loop injection via PumpManager."""
        logger.info("💉 Partial Loop Injection requested")

        # Check for EITHER AffiPump OR P4PROPLUS internal pumps
        has_affipump = self.pump_mgr.is_available
        has_internal = (self.hardware_mgr.ctrl and
                       hasattr(self.hardware_mgr.ctrl, 'has_internal_pumps') and
                       self.hardware_mgr.ctrl.has_internal_pumps())

        if not has_affipump and not has_internal:
            from affilabs.widgets.message import show_message
            show_message("No pump available. Connect AffiPump or use P4PROPLUS with internal pumps.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        # Get assay rate from UI (default 100 µL/min if not available)
        assay_rate = 100.0
        if spin := self._sidebar_widget('pump_assay_spin'):
            assay_rate = float(spin.value())

        logger.info(f"  Using assay rate: {assay_rate} uL/min")

        # Run partial loop inject in background
        def run_inject_partial():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.inject_partial_loop(assay_rate))
            finally:
                loop.close()

        thread = threading.Thread(target=run_inject_partial, daemon=True, name="InjectPartialLoop")
        thread.start()

    def _on_home_pumps_clicked(self):
        """User clicked Home Pumps button - home both pumps to zero position."""
        logger.info("🏠 Home Pumps requested")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion or use STOP button.", "Warning")
            return

        # Home both pumps
        def run_home():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.home_pumps())
            finally:
                loop.close()

        thread = threading.Thread(target=run_home, daemon=True, name="HomePumps")
        thread.start()

    def _on_flow_rate_changed(self, rate_name: str, value: float):
        """User changed a flow rate spinbox - apply on-the-fly if pump is running.

        Args:
            rate_name: Name of the rate that changed (Setup, Functionalization, Assay)
            value: New flow rate value in µL/min
        """
        if not self.pump_mgr.is_available:
            return

        # If pump is currently running, apply on-the-fly change
        if not self.pump_mgr.is_idle:
            logger.info(f"💧 {rate_name} flow rate changed to {value} uL/min (pump running - applying on-the-fly)")
            self.pump_mgr.change_flow_rate_on_the_fly(value)
        else:
            logger.debug(f"{rate_name} flow rate set to {value} uL/min (pump idle - will use on next operation)")

    # =========================================================================
    # Internal Pump Background Task Classes (Reusable)
    # =========================================================================

    class _PumpStartTask:
        """Background task for starting internal pumps without UI blocking."""
        def __init__(self, ctrl, flow_rate, channel, callback):
            self._runnable = self._create_runnable(ctrl, flow_rate, channel, callback)

        @staticmethod
        def _create_runnable(ctrl, flow_rate, channel, callback):
            from PySide6.QtCore import QRunnable

            class _Runnable(QRunnable):
                def __init__(self):
                    super().__init__()
                    self.ctrl = ctrl
                    self.flow_rate = flow_rate
                    self.channel = channel
                    self.callback = callback

                def run(self):
                    try:
                        success = self.ctrl.pump_start(rate_ul_min=self.flow_rate, ch=self.channel)
                    except Exception as e:
                        # Ensure pump errors never crash the UI thread
                        try:
                            logger.error(f"Error starting internal pump {self.channel}: {e}")
                        except Exception:
                            pass
                        success = False

                    try:
                        self.callback(success)
                    except Exception:
                        # Callback errors should not crash the thread pool
                        pass

            return _Runnable()

        def start(self):
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self._runnable)

    class _PumpStopTask:
        """Background task for stopping internal pumps without UI blocking."""
        def __init__(self, ctrl, channel, callback):
            self._runnable = self._create_runnable(ctrl, channel, callback)

        @staticmethod
        def _create_runnable(ctrl, channel, callback):
            from PySide6.QtCore import QRunnable

            class _Runnable(QRunnable):
                def __init__(self):
                    super().__init__()
                    self.ctrl = ctrl
                    self.channel = channel
                    self.callback = callback

                def run(self):
                    try:
                        success = self.ctrl.pump_stop(ch=self.channel)
                    except Exception as e:
                        # Ensure pump errors never crash the UI thread
                        try:
                            logger.error(f"Error stopping internal pump {self.channel}: {e}")
                        except Exception:
                            pass
                        success = False

                    try:
                        self.callback(success)
                    except Exception:
                        # Callback errors should not crash the thread pool
                        pass

            return _Runnable()

        def start(self):
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self._runnable)

    # =========================================================================
    # Internal Pump Toggle Handlers
    # =========================================================================

    def _update_internal_pump_visibility(self):
        """Show/hide internal pump control section based on P4PROPLUS detection."""
        try:
            # Check if we have internal pumps - use hardware manager's raw controller
            has_internal = False

            # Try hardware manager's raw controller first (most reliable)
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                if hasattr(self.hardware_mgr, '_ctrl_raw') and self.hardware_mgr._ctrl_raw:
                    raw_ctrl = self.hardware_mgr._ctrl_raw
                    if hasattr(raw_ctrl, 'firmware_id'):
                        has_internal = 'p4proplus' in raw_ctrl.firmware_id.lower()
                    elif hasattr(raw_ctrl, 'has_internal_pumps'):
                        has_internal = raw_ctrl.has_internal_pumps()

            # Fallback to self.ctrl (HAL adapter)
            if not has_internal and hasattr(self, 'ctrl') and self.ctrl:
                if hasattr(self.ctrl, 'has_internal_pumps'):
                    has_internal = self.ctrl.has_internal_pumps()

            # Show/hide section
            if section := self._sidebar_widget('internal_pump_section'):
                if has_internal:
                    section.show()
                    logger.info("P4PROPLUS detected - Internal Pump Control visible")
                else:
                    section.hide()
        except Exception as e:
            logger.error(f"Error updating internal pump visibility: {e}")

    def _on_internal_pump1_toggle(self, checked: bool):
        """Toggle internal pump 1 on/off.

        Args:
            checked: True = start pump, False = stop pump
        """
        if not (spin := self._sidebar_widget('pump1_rpm_spin')):
            logger.error("Pump 1 RPM spinbox not found")
            return

        if checked:
            # Start pump
            rpm = spin.value()
            correction = getattr(self.main_window.sidebar.pump1_correction_spin, 'value', lambda: 1.0)()
            rpm_corrected = rpm * correction
            logger.debug(f"[PUMP CMD] Pump 1 Start - Spinbox: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl:
                from affilabs.widgets.message import show_message
                show_message("Controller not connected", "Warning")
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                return

            if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                rpm_corrected = rpm * correction

                logger.info(f"▶ Starting internal pump 1: {rpm_corrected:.1f} RPM (correction: {correction})")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.setText("Stop")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status(f"Pump 1: {rpm_corrected:.0f} RPM", running=True)

                # Run hardware command in background thread to prevent UI blocking
                def on_start_complete(success):
                    if success:
                        logger.info(f"✓ Started pump 1 at {rpm_corrected:.1f} RPM")
                        self._pump1_running = True  # Track state
                    else:
                        logger.error("✗ Failed to start internal pump")
                        self._pump1_running = False
                        # Revert button state on failure (block signals to prevent toggle loop)
                        btn.blockSignals(True)
                        btn.setChecked(False)
                        btn.blockSignals(False)
                        btn.setText("Start")
                        btn.style().unpolish(btn)
                        btn.style().polish(btn)
                        self._update_internal_pump_status("Idle", running=False)

                # ALWAYS channel 1 for pump1 (not affected by sync mode)
                task = self._PumpStartTask(ctrl, rpm_corrected, 1, on_start_complete)
                task.start()
            else:
                from affilabs.widgets.message import show_message
                show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        else:
            # Stop pump
            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                logger.info("■ Stopping internal pump 1")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.pump1_toggle_btn
                btn.setText("Start")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status("Idle", running=False)

                # Run hardware command in background thread
                def on_stop_complete(success):
                    if success:
                        logger.info("✓ Stopped pump 1")
                        self._pump1_running = False  # Track state
                    else:
                        logger.error("✗ Failed to stop pump 1")
                        # Keep state as running if stop failed
                        logger.warning("Pump 1 may still be running!")

                task = self._PumpStopTask(ctrl, 1, on_stop_complete)
                task.start()

    def _on_synced_pump_toggle(self, checked: bool):
        """Toggle synced pumps (both pumps) on/off.

        Args:
            checked: True = start both pumps, False = stop both pumps
        """
        if not (combo := self._sidebar_widget('synced_flowrate_combo')):
            logger.error("Synced flowrate combo not found")
            return

        if checked:
            # Start both pumps
            # Get flowrate from combo box
            flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
            idx = combo.currentIndex()
            flow_rate = flowrate_map.get(idx, 50)

            # Get pump corrections from controller EEPROM
            correction_p1 = 1.0
            correction_p2 = 1.0

            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                try:
                    corrections = ctrl.get_pump_corrections()
                    if corrections and isinstance(corrections, dict):
                        correction_p1 = corrections.get(1, 1.0)
                        correction_p2 = corrections.get(2, 1.0)
                        logger.debug(f"✓ Loaded pump corrections from EEPROM: P1={correction_p1:.3f}, P2={correction_p2:.3f}")
                    elif corrections and isinstance(corrections, tuple) and len(corrections) == 2:
                        correction_p1, correction_p2 = corrections
                        logger.debug(f"✓ Loaded pump corrections from EEPROM: P1={correction_p1:.3f}, P2={correction_p2:.3f}")
                except Exception as e:
                    logger.debug(f"Could not read pump corrections from EEPROM, using defaults: {e}")

            logger.debug(f"[PUMP CMD] Synced flowrate: {flow_rate} uL/min, P1 correction: {correction_p1:.3f}, P2 correction: {correction_p2:.3f}")

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl:
                from affilabs.widgets.message import show_message
                show_message("Controller not connected", "Warning")
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                return

            if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                # Apply individual corrections
                rpm_p1 = flow_rate * correction_p1
                rpm_p2 = flow_rate * correction_p2

                logger.info(f"▶ Starting both pumps: P1={rpm_p1:.1f} µL/min (×{correction_p1:.3f}), P2={rpm_p2:.1f} µL/min (×{correction_p2:.3f})")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.setText("Stop")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status(f"Both Pumps: P1={rpm_p1:.0f} P2={rpm_p2:.0f} µL/min", running=True)

                # Start both pumps with individual corrections
                success_p1 = ctrl.pump_start(rate_ul_min=rpm_p1, ch=1)
                success_p2 = ctrl.pump_start(rate_ul_min=rpm_p2, ch=2)
                success = success_p1 and success_p2

                if success:
                    logger.info(f"✓ Started both pumps: P1={rpm_p1:.1f} µL/min, P2={rpm_p2:.1f} µL/min")
                    self._synced_pumps_running = True
                    self._pump1_running = True
                    self._pump2_running = True
                else:
                    logger.error(f"✗ Failed to start synced pumps (P1={success_p1}, P2={success_p2})")
                    self._synced_pumps_running = False
                    # Revert button state on failure
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
                    btn.setText("Start")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    self._update_internal_pump_status("Idle", running=False)
            else:
                from affilabs.widgets.message import show_message
                show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        else:
            # Stop both pumps
            ctrl = self.hardware_mgr._ctrl_raw
            if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
                logger.info("■ Stopping both internal pumps")

                # Update UI immediately to prevent lag
                btn = self.main_window.sidebar.synced_toggle_btn
                btn.setText("Start")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                self._update_internal_pump_status("Idle", running=False)

                # Run hardware command in background thread
                def on_stop_complete(success):
                    if success:
                        logger.info("✓ Stopped both pumps")
                        self._synced_pumps_running = False  # Track state
                        self._pump1_running = False
                        self._pump2_running = False
                    else:
                        logger.error("✗ Failed to stop both pumps")
                        logger.warning("Pumps may still be running!")

                task = self._PumpStopTask(ctrl, 3, on_stop_complete)
                task.start()

    def _on_internal_pump_inject_30s(self):
        """Run inject sequence using internal pumps with user-selected contact time.

        In Manual mode: Toggle valve open/close without automatic timer
        In Auto mode: Use contact time with automatic valve close
        """

        # Check if Manual mode is enabled
        manual_mode = False
        if chk := self._sidebar_widget('synced_manual_time_check'):
            manual_mode = chk.isChecked()

        # MANUAL MODE: Toggle valve open/close
        if manual_mode:
            # Check if valve is currently open
            valve_open = getattr(self, '_manual_valve_open', False)

            ctrl = self.hardware_mgr._ctrl_raw
            if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
                from affilabs.widgets.message import show_message
                show_message("Controller not connected or internal pumps unavailable", "Warning")
                return

            # Check if valve sync is enabled
            valve_sync_enabled = False
            if btn := self._sidebar_widget('sync_valve_btn'):
                valve_sync_enabled = btn.isChecked()

            channel_text = "KC1 & KC2" if valve_sync_enabled else "KC1"

            if not valve_open:
                # Open valves
                try:
                    if valve_sync_enabled:
                        valve_success = ctrl.knx_six_both(state=1, timeout_seconds=None)
                    else:
                        valve_success = ctrl.knx_six(state=1, ch=1, timeout_seconds=None)

                    if valve_success:
                        self._manual_valve_open = True
                        self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - MANUAL", running=True)
                        logger.info(f"✓ Manual mode: {channel_text} valve(s) OPENED")

                        # Update button to manual open state
                        if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                            btn.setText("⬇ Close Valve")
                            btn.setProperty("injection_state", "manual")
                            btn.setToolTip("🔄 Click to close valve")
                            btn.style().unpolish(btn)
                            btn.style().polish(btn)
                    else:
                        logger.warning(f"Failed to open {channel_text} valve(s)")
                except Exception as e:
                    logger.error(f"Error opening valves: {e}")
            else:
                # Close valves
                try:
                    if valve_sync_enabled:
                        valve_success = ctrl.knx_six_both(state=0, timeout_seconds=None)
                    else:
                        valve_success = ctrl.knx_six(state=0, ch=1, timeout_seconds=None)

                    if valve_success:
                        self._manual_valve_open = False
                        self._update_internal_pump_status("Idle", running=False)
                        logger.info(f"✓ Manual mode: {channel_text} valve(s) CLOSED")

                        # Update button back to ready state
                        if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                            btn.setText("Inject")
                            btn.setProperty("injection_state", "ready")
                            btn.setToolTip("✅ Ready to inject")
                            btn.style().unpolish(btn)
                            btn.style().polish(btn)
                    else:
                        logger.warning(f"Failed to close {channel_text} valve(s)")
                except Exception as e:
                    logger.error(f"Error closing valves: {e}")

            return  # Exit early in manual mode

        # AUTO MODE: Original behavior with contact time
        # Get contact time from spinbox (preset modes only)
        contact_time_s = 60  # Default fallback
        if spin := self._sidebar_widget('synced_contact_time_spin'):
            contact_time_s = spin.value()
        elif spin := self._sidebar_widget('pump2_contact_time_spin'):
            contact_time_s = spin.value()

        logger.info(f"💉 Starting inject sequence ({contact_time_s}s contact time, internal pumps)")

        # Get flowrate from combo box
        flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
        idx = 1  # Default to 50
        if combo := self._sidebar_widget('synced_flowrate_combo'):
            idx = combo.currentIndex()
        rpm = flowrate_map.get(idx, 50)

        # Warning: For P4PRO+ internal pump, when flowrate is 25 µL/min,
        # contact time should be >= 180 seconds for proper operation.
        # User can choose to proceed with shorter times for development/testing.
        try:
            ctrl = self.hardware_mgr._ctrl_raw
        except Exception:
            ctrl = None
        if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            if float(rpm) == 25.0 and contact_time_s < 180:
                logger.warning(f"⚠️  Contact time ({contact_time_s}s) is below recommended 180s for 25 µL/min (P4PRO+ internal pump). This may cause incomplete injection or pump errors.")

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            from affilabs.widgets.message import show_message
            show_message("Controller not connected", "Warning")
            return

        if hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            # FLUSH PULSE: Start both pumps at 220 µL/min for first 6 seconds,
            # then reduce both to the selected target flowrate.
            # Apply individual pump corrections from controller EEPROM
            flush_rate = 220.0
            target_rate = float(rpm)

            # Get pump corrections from controller EEPROM
            correction_p1 = 1.0
            correction_p2 = 1.0

            if ctrl and hasattr(ctrl, 'get_pump_corrections'):
                try:
                    corrections = ctrl.get_pump_corrections()
                    if corrections and isinstance(corrections, dict):
                        correction_p1 = corrections.get(1, 1.0)
                        correction_p2 = corrections.get(2, 1.0)
                    elif corrections and isinstance(corrections, tuple) and len(corrections) == 2:
                        correction_p1, correction_p2 = corrections
                except Exception as e:
                    logger.debug(f"Could not read pump corrections from EEPROM, using defaults: {e}")

            flush_p1 = flush_rate * correction_p1
            flush_p2 = flush_rate * correction_p2

            logger.info(
                f"💉 Inject (synced): FLUSH P1={flush_p1:.1f} P2={flush_p2:.1f} µL/min (6s) → target {target_rate:.1f} µL/min "
                f"with {contact_time_s}s valve contact time"
            )

            # Start BOTH pumps at FLUSH rate first (channels 1 and 2) with corrections
            success_p1 = ctrl.pump_start(rate_ul_min=flush_p1, ch=1)
            success_p2 = ctrl.pump_start(rate_ul_min=flush_p2, ch=2)
            success = bool(success_p1 and success_p2)

            if success:
                logger.info(f"✓ Pumps started at FLUSH rate {flush_rate:.1f} µL/min")

                # Update internal state flags - pumps are now running
                self._pump1_running = True
                self._pump2_running = True
                self._synced_pumps_running = True

                # Update status bar immediately to show pumps starting
                self._update_internal_pump_status(f"FLUSH: P1={flush_p1:.0f} P2={flush_p2:.0f} µL/min (6s)", running=True)

                # Update inject button to busy state during injection
                if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                    btn.setEnabled(False)
                    btn.setProperty("injection_state", "busy")
                    btn.setText("⏳ Injecting...")
                    btn.setToolTip("⏳ Injection in progress - please wait")
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)

                # Update pump toggle buttons to reflect running state
                if btn := self._sidebar_widget('pump1_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                if btn := self._sidebar_widget('pump2_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                if btn := self._sidebar_widget('synced_toggle_btn'):
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.setText("Stop")
                    btn.setEnabled(False)  # Disable during injection
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.blockSignals(False)

                # Check if valve sync is enabled
                valve_sync_enabled = False
                if btn := self._sidebar_widget('sync_valve_btn'):
                    valve_sync_enabled = btn.isChecked()

                # Determine channel text for status display
                channel_text = "KC1 & KC2" if valve_sync_enabled else "KC1"
                # Remember which valve(s) are open so the countdown text can
                # include the correct channels (matches the status style the
                # user sees in the UI).
                self._injection_channel_text = channel_text

                # Turn on 6-port valve(s) for contact time
                # Use both valves if sync enabled, otherwise just KC1
                try:
                    import time
                    if valve_sync_enabled:
                        # Control both valves simultaneously: state=1 (inject position)
                        valve_success = ctrl.knx_six_both(state=1, timeout_seconds=None)
                        if valve_success:
                            # Record valve open timestamp for delta calculation
                            self._injection_valve_open_time = self.main_window._get_elapsed_time() if hasattr(self.main_window, '_get_elapsed_time') else 0
                            self._injection_start_time = time.time()
                            self._injection_total_time = contact_time_s
                            self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - FLUSH - {contact_time_s}.0s", running=True)
                            logger.info(f"✓ Both 6-port valves → INJECT - {contact_time_s}s contact time started (t={self._injection_valve_open_time:.2f}s)")
                        else:
                            logger.warning("Failed to activate both 6-port valves")
                            self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)
                    else:
                        # Control KC1 only: state=1 (inject position), channel=1
                        valve_success = ctrl.knx_six(state=1, ch=1, timeout_seconds=None)
                        if valve_success:
                            # Record valve open timestamp for delta calculation
                            self._injection_valve_open_time = self.main_window._get_elapsed_time() if hasattr(self.main_window, '_get_elapsed_time') else 0
                            self._injection_start_time = time.time()
                            self._injection_total_time = contact_time_s
                            self._update_internal_pump_status(f"VALVE OPEN ({channel_text}) - FLUSH - {contact_time_s}.0s", running=True)
                            logger.info(f"✓ KC1 6-port valve → INJECT - {contact_time_s}s contact time started (t={self._injection_valve_open_time:.2f}s)")
                        else:
                            logger.warning("Failed to activate KC1 6-port valve")
                            self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)
                    time.sleep(0.1)  # Brief settle time

                except Exception as e:
                    logger.warning(f"Could not activate 6-port valve: {e}")
                    self._update_internal_pump_status(f"Injecting: {flush_rate:.0f} µL/min", running=True)

                # After 6 seconds, reduce BOTH pumps to target flowrate with corrections
                # This runs REGARDLESS of valve success to ensure pumps don't stay at flush rate
                from PySide6.QtCore import QTimer
                def reduce_to_target_flow():
                    target_p1 = target_rate * correction_p1
                    target_p2 = target_rate * correction_p2
                    success_reduce_p1 = ctrl.pump_start(rate_ul_min=target_p1, ch=1)
                    success_reduce_p2 = ctrl.pump_start(rate_ul_min=target_p2, ch=2)
                    if success_reduce_p1 and success_reduce_p2:
                        logger.info(f"✓ Reduced both pumps to target: P1={target_p1:.1f} P2={target_p2:.1f} µL/min")
                        # Update status to show target flowrate (countdown timer will overwrite with valve info)
                        self._update_internal_pump_status(f"TARGET: P1={target_p1:.0f} P2={target_p2:.0f} µL/min", running=True)
                    else:
                        logger.warning("✗ Failed to reduce both pumps to target flowrate")

                QTimer.singleShot(6000, reduce_to_target_flow)  # Reduce after 6 seconds

                # Schedule valve close after contact time
                # NOTE: Pumps continue running after valve closes - user must stop manually
                from PySide6.QtCore import QTimer
                QTimer.singleShot(contact_time_s * 1000, lambda: self._close_inject_valve())
            else:
                logger.error("✗ Failed to start inject sequence")
        else:
            from affilabs.widgets.message import show_message
            show_message("Internal pumps not available. P4PRO+ V2.3+ required.", "Warning")

    def _close_inject_valve(self):
        """Close 6-port valve after 30-second contact time ends.

        NOTE: Pumps continue running - this only closes the valve.
        User must manually stop pumps using toggle buttons.
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if ctrl and hasattr(ctrl, 'has_internal_pumps') and ctrl.has_internal_pumps():
            # Check if valve sync is enabled
            valve_sync_enabled = False
            if btn := self._sidebar_widget('sync_valve_btn'):
                valve_sync_enabled = btn.isChecked()

            # Turn off 6-port valve(s) (end of 30s contact time)
            try:
                if valve_sync_enabled:
                    # Return both valves to LOAD position (state=0)
                    valve_success = ctrl.knx_six_both(state=0, timeout_seconds=None)
                    if valve_success:
                        # Record valve close timestamp for wash delta calculation
                        self._wash_valve_close_time = self._get_elapsed_time()
                        logger.info(f"✓ Both 6-port valves → LOAD - contact time complete (t={self._wash_valve_close_time:.2f}s, pumps still running)")
                    else:
                        logger.warning("Failed to return both 6-port valves to LOAD")
                else:
                    # Return KC1 to LOAD position (state=0, channel=1)
                    valve_success = ctrl.knx_six(state=0, ch=1, timeout_seconds=None)
                    if valve_success:
                        # Record valve close timestamp for wash delta calculation
                        self._wash_valve_close_time = self._get_elapsed_time()
                        logger.info(f"✓ KC1 6-port valve → LOAD - contact time complete (t={self._wash_valve_close_time:.2f}s, pumps still running)")
                    else:
                        logger.warning("Failed to return KC1 6-port valve to LOAD")
            except Exception as e:
                logger.warning(f"Could not close 6-port valve: {e}")

            # Update status to show pumps are still running but contact time is over
            self._update_internal_pump_status("Pumps running (contact complete)", running=True)

            # Re-enable inject button and restore ready state
            if btn := self._sidebar_widget('internal_pump_inject_30s_btn'):
                btn.setEnabled(True)
                btn.setProperty("injection_state", "ready")
                btn.setText("Inject")
                btn.setToolTip("✅ Ready to inject")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            # Re-enable pump toggle buttons (pumps still running, user can stop them)
            if btn := self._sidebar_widget('pump1_toggle_btn'):
                btn.setEnabled(True)
            if btn := self._sidebar_widget('pump2_toggle_btn'):
                btn.setEnabled(True)
            if btn := self._sidebar_widget('synced_toggle_btn'):
                btn.setEnabled(True)

            # Sync button states with current running flags
            self._sync_pump_button_states()

    def _save_pump_corrections(self):
        """Save current pump correction factors to device config and controller EEPROM."""
        try:
            if not hasattr(self, 'hardware_mgr') or not self.hardware_mgr:
                return

            if not hasattr(self.hardware_mgr, 'device_config') or not self.hardware_mgr.device_config:
                return

            device_config = self.hardware_mgr.device_config

            # Get current correction values from spinboxes
            pump1_corr = 1.0
            pump2_corr = 1.0

            if spin := self._sidebar_widget('pump1_correction_spin'):
                pump1_corr = spin.value()
            if spin := self._sidebar_widget('pump2_correction_spin'):
                pump2_corr = spin.value()

            # Get currently saved values
            saved_corrections = device_config.get_pump_corrections()
            saved_pump1 = saved_corrections.get("pump_1", 1.0)
            saved_pump2 = saved_corrections.get("pump_2", 1.0)

            # Only save if values have changed
            if abs(pump1_corr - saved_pump1) > 0.001 or abs(pump2_corr - saved_pump2) > 0.001:
                # Save to device config JSON
                device_config.set_pump_corrections(pump1_corr, pump2_corr)
                device_config.save()
                logger.info(f"💾 Pump corrections saved to device config: Pump 1={pump1_corr:.3f}, Pump 2={pump2_corr:.3f}")

                # Also save to controller EEPROM (if supported by firmware)
                ctrl = self.hardware_mgr._ctrl_raw
                if ctrl and hasattr(ctrl, 'set_pump_corrections'):
                    try:
                        success = ctrl.set_pump_corrections(pump1_corr, pump2_corr)
                        if success:
                            logger.info("✓ Pump corrections written to controller EEPROM")
                        else:
                            logger.warning("⚠ Controller EEPROM write failed (firmware may not support this feature)")
                    except Exception as e:
                        logger.warning(f"Could not write pump corrections to EEPROM: {e}")
        except Exception as e:
            logger.warning(f"Could not save pump corrections: {e}")

    def _update_internal_pump_status(self, text: str, running: bool = False):
        """Update internal pump status display.

        Args:
            text: Status text to display
            running: True if pumps are running (green), False if idle (grey)
        """
        if lbl := self._sidebar_widget('internal_pump_status_label'):
            lbl.setText(text)
        if icon := self._sidebar_widget('internal_pump_status_icon'):
            color = Colors.SUCCESS if running else Colors.SECONDARY_TEXT
            icon.setStyleSheet(
                f"color: {color}; font-size: 14px; background: transparent;"
            )

    def _sync_pump_button_states(self):
        """Sync pump button UI states with tracked running state.

        Called after hardware reconnection or when UI needs to reflect actual pump state.
        """
        # Pump 1 button
        if btn := self._sidebar_widget('pump1_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._pump1_running)
            btn.setText("Stop" if self._pump1_running else "Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

        # Pump 2 button
        if btn := self._sidebar_widget('pump2_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._pump2_running)
            btn.setText("Stop" if self._pump2_running else "Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

        # Synced pumps button
        if btn := self._sidebar_widget('synced_toggle_btn'):
            btn.blockSignals(True)
            btn.setChecked(self._synced_pumps_running)
            btn.setText("Stop" if self._synced_pumps_running else "Start")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.blockSignals(False)

    def _on_synced_flowrate_changed(self):
        """Handle flowrate change in synced controls - update running pumps in real-time.

        Uses 300ms debouncing to prevent rapid command flooding that could
        violate the firmware's 150ms command spacing requirement.
        """
        # Cancel any pending update timer
        if hasattr(self, '_synced_rpm_timer') and self._synced_rpm_timer is not None:
            self._synced_rpm_timer.stop()
            self._synced_rpm_timer = None

        # Schedule update after 300ms of no changes (debouncing)
        from PySide6.QtCore import QTimer
        self._synced_rpm_timer = QTimer()
        self._synced_rpm_timer.setSingleShot(True)
        self._synced_rpm_timer.timeout.connect(self._update_synced_rpm)
        self._synced_rpm_timer.start(300)

    def _update_synced_rpm(self):
        """Actually update synced pump RPM (called after debounce delay)."""
        # Only update if pumps are currently running
        if not (btn := self._sidebar_widget('synced_toggle_btn')):
            return

        is_running = btn.isChecked()
        if not is_running:
            return  # Pump not running, no need to update

        # Get new flowrate value from combo
        if not (combo := self._sidebar_widget('synced_flowrate_combo')):
            return

        flowrate_map = {0: 25, 1: 50, 2: 100, 3: 200, 4: 220}
        idx = combo.currentIndex()
        rpm = flowrate_map.get(idx, 50)
        correction = 1.0  # No correction for synced mode
        rpm_corrected = rpm * correction

        logger.debug(f"[PUMP CMD] Synced Speed Update - Flowrate: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

        # Save correction factor to device config if changed
        self._save_pump_corrections()

        # Update running pumps with new RPM
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
            return

        logger.info(f"🔄 Updating synced pump speed: {rpm_corrected:.1f} uL/min")

        # P4PROPLUS allows changing speed while running - just send new start command
        success = ctrl.pump_start(rate_ul_min=rpm_corrected, ch=3)
        if success:
            logger.info(f"✓ Synced pumps speed updated to {rpm_corrected:.1f} uL/min")
            self._update_internal_pump_status(f"Both Pumps: {rpm_corrected:.0f} µL/min", running=True)
        else:
            logger.error("✗ Failed to update synced pump speed")

    def _on_pump1_rpm_changed(self):
        """Handle RPM change for pump 1 - update if currently running.

        Uses 300ms debouncing to prevent rapid command flooding that could
        violate the firmware's 150ms command spacing requirement.
        """
        # Cancel any pending update timer
        if hasattr(self, '_pump1_rpm_timer') and self._pump1_rpm_timer is not None:
            self._pump1_rpm_timer.stop()
            self._pump1_rpm_timer = None

        # Schedule update after 300ms of no changes (debouncing)
        from PySide6.QtCore import QTimer
        self._pump1_rpm_timer = QTimer()
        self._pump1_rpm_timer.setSingleShot(True)
        self._pump1_rpm_timer.timeout.connect(self._update_pump1_rpm)
        self._pump1_rpm_timer.start(300)

    def _update_pump1_rpm(self):
        """Actually update pump 1 RPM (called after debounce delay)."""
        if not (btn := self._sidebar_widget('pump1_toggle_btn')):
            logger.debug("pump1_rpm_changed: toggle_btn not found")
            return

        is_running = btn.isChecked()
        logger.debug(f"pump1_rpm_changed: is_running={is_running}")
        if not is_running:
            return  # Pump not running, no need to update

        if not (spin := self._sidebar_widget('pump1_rpm_spin')):
            logger.debug("pump1_rpm_changed: rpm_spin not found")
            return

        rpm = spin.value()
        correction = getattr(self.main_window.sidebar.pump1_correction_spin, 'value', lambda: 1.0)()
        rpm_corrected = rpm * correction

        logger.debug(f"[PUMP CMD] Pump 1 Speed Update - Spinbox: {rpm} uL/min, Correction: {correction:.3f}, Sending: {rpm_corrected:.1f} uL/min")

        # Save correction factor to device config if changed
        self._save_pump_corrections()

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl or not hasattr(ctrl, 'has_internal_pumps') or not ctrl.has_internal_pumps():
            logger.debug("pump1_rpm_changed: no internal pumps available")
            return

        logger.info(f"🔄 Updating pump 1 speed: {rpm_corrected:.1f} uL/min (from spinbox value {rpm})")

        success = ctrl.pump_start(rate_ul_min=rpm_corrected, ch=1)
        if success:
            logger.info(f"✓ Pump 1 speed updated to {rpm_corrected:.1f} uL/min")
            self._update_internal_pump_status(f"Pump 1: {rpm_corrected:.0f} µL/min", running=True)
        else:
            logger.error("✗ Failed to update pump 1 speed")

    def _on_valve_sync_toggled(self, checked: bool):
        """User toggled valve synchronization.

        When enabled, KC1 and KC2 valve switches mirror each other.

        Args:
            checked: True = sync enabled, False = independent control
        """
        mode = "SYNCHRONIZED" if checked else "INDEPENDENT"
        logger.info(f"🔄 Valve control mode → {mode}")

        # If sync is enabled, mirror current KC1 state to KC2
        if checked:
            if (sw1 := self._sidebar_widget('kc1_loop_switch')) and (sw2 := self._sidebar_widget('kc2_loop_switch')):
                kc1_state = sw1.isChecked()
                sw2.setChecked(kc1_state)
                logger.info(f"✓ Synced KC2 loop valve to match KC1 ({kc1_state})")

    def _on_loop_valve_switched(self, channel: int, position: str):
        """User clicked loop valve button - simple ON/OFF control.

        The valve has ONE command: power ON (1) or OFF (0)
        - state=0 (OFF): Load position (de-energized, normal state)
        - state=1 (ON): Sensor position (energized)

        Injection sequence:
        - During filling: Valves in LOAD (state=0) - loop fills from sample
        - During injection: Valves switch to INJECT/Sensor (state=1) - loop content to sensor
        - After contact time: Valves return to LOAD (state=0)

        Args:
            channel: 1 for KC1, 2 for KC2
            position: 'Load' or 'Sensor'
        """
        # Simple: Sensor/INJECT=OPEN(1), Load=CLOSED(0)
        state = 1 if position == 'Sensor' else 0

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("Controller not connected")
            return

        ui = self.main_window.sidebar
        sync_enabled = hasattr(ui, 'sync_valve_btn') and ui.sync_valve_btn.isChecked()

        try:
            # Check if sync mode is enabled - use broadcast command for both valves
            if sync_enabled:
                # Use broadcast command v631/v630 to control both valves simultaneously
                success = ctrl.knx_six_both(state)

                if success:
                    # Update both KC1 and KC2 UI buttons
                    ui.kc1_loop_btn_load.blockSignals(True)
                    ui.kc1_loop_btn_sensor.blockSignals(True)
                    ui.kc1_loop_btn_load.setChecked(state == 0)
                    ui.kc1_loop_btn_sensor.setChecked(state == 1)
                    ui.kc1_loop_btn_load.blockSignals(False)
                    ui.kc1_loop_btn_sensor.blockSignals(False)

                    ui.kc2_loop_btn_load.blockSignals(True)
                    ui.kc2_loop_btn_sensor.blockSignals(True)
                    ui.kc2_loop_btn_load.setChecked(state == 0)
                    ui.kc2_loop_btn_sensor.setChecked(state == 1)
                    ui.kc2_loop_btn_load.blockSignals(False)
                    ui.kc2_loop_btn_sensor.blockSignals(False)

                    logger.info(f"✓ BOTH Loop valves (SYNC): {position} (state={state})")
                else:
                    logger.error("BOTH Loop valves command failed (SYNC mode)")
            else:
                # Independent mode - control only the clicked channel
                success = ctrl.knx_six(state, channel)

                if success:
                    # Update only the clicked channel's UI
                    if channel == 1:
                        ui.kc1_loop_btn_load.blockSignals(True)
                        ui.kc1_loop_btn_sensor.blockSignals(True)
                        ui.kc1_loop_btn_load.setChecked(state == 0)
                        ui.kc1_loop_btn_sensor.setChecked(state == 1)
                        ui.kc1_loop_btn_load.blockSignals(False)
                        ui.kc1_loop_btn_sensor.blockSignals(False)
                    else:
                        ui.kc2_loop_btn_load.blockSignals(True)
                        ui.kc2_loop_btn_sensor.blockSignals(True)
                        ui.kc2_loop_btn_load.setChecked(state == 0)
                        ui.kc2_loop_btn_sensor.setChecked(state == 1)
                        ui.kc2_loop_btn_load.blockSignals(False)
                        ui.kc2_loop_btn_sensor.blockSignals(False)

                    logger.info(f"✓ KC{channel} Loop valve: {position} (state={state})")
                else:
                    logger.error(f"KC{channel} Loop valve command failed")
        except Exception as e:
            logger.error(f"Loop valve error: {e}")

    def _on_channel_valve_switched(self, channel: int, selected_channel: str):
        """User clicked channel valve button - simple OPEN/CLOSED control.

        3-way valve states (NO WASTE):
        - state=0 (CLOSED): KC1→A, KC2→C (de-energized)
        - state=1 (OPEN): KC1→B, KC2→D (energized)

        Args:
            channel: 1 for KC1, 2 for KC2
            selected_channel: 'A', 'B', 'C', or 'D'
        """
        # B/D=OPEN(1), A/C=CLOSED(0)
        state = 1 if selected_channel in ['B', 'D'] else 0

        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("Controller not connected")
            return

        ui = self.main_window.sidebar
        sync_enabled = hasattr(ui, 'sync_valve_btn') and ui.sync_valve_btn.isChecked()

        try:
            # Check if sync mode is enabled - use broadcast command for both valves
            if sync_enabled:
                # Use broadcast command v3B1/v3B0 to control both valves simultaneously
                success = ctrl.knx_three_both(state)

                if success:
                    # Update both KC1 and KC2 UI buttons
                    # state=0: A/C active, state=1: B/D active
                    ui.kc1_channel_btn_a.blockSignals(True)
                    ui.kc1_channel_btn_b.blockSignals(True)
                    ui.kc1_channel_btn_a.setChecked(state == 0)
                    ui.kc1_channel_btn_b.setChecked(state == 1)
                    ui.kc1_channel_btn_a.blockSignals(False)
                    ui.kc1_channel_btn_b.blockSignals(False)

                    ui.kc2_channel_btn_c.blockSignals(True)
                    ui.kc2_channel_btn_d.blockSignals(True)
                    ui.kc2_channel_btn_c.setChecked(state == 0)
                    ui.kc2_channel_btn_d.setChecked(state == 1)
                    ui.kc2_channel_btn_c.blockSignals(False)
                    ui.kc2_channel_btn_d.blockSignals(False)

                    logger.info(f"✓ BOTH Channel valves (SYNC): {selected_channel} (state={state})")
                else:
                    logger.error("BOTH Channel valves command failed (SYNC mode)")
            else:
                # Independent mode - control only the clicked channel
                success = ctrl.knx_three(state, channel)

                if success:
                    # Update only the clicked channel's UI
                    # state=0: A/C active, state=1: B/D active
                    if channel == 1:
                        ui.kc1_channel_btn_a.blockSignals(True)
                        ui.kc1_channel_btn_b.blockSignals(True)
                        ui.kc1_channel_btn_a.setChecked(state == 0)
                        ui.kc1_channel_btn_b.setChecked(state == 1)
                        ui.kc1_channel_btn_a.blockSignals(False)
                        ui.kc1_channel_btn_b.blockSignals(False)
                    else:
                        ui.kc2_channel_btn_c.blockSignals(True)
                        ui.kc2_channel_btn_d.blockSignals(True)
                        ui.kc2_channel_btn_c.setChecked(state == 0)
                        ui.kc2_channel_btn_d.setChecked(state == 1)
                        ui.kc2_channel_btn_c.blockSignals(False)
                        ui.kc2_channel_btn_d.blockSignals(False)

                    logger.info(f"✓ KC{channel} Channel valve: {selected_channel} (state={state})")
                else:
                    logger.error(f"KC{channel} Channel valve command failed")
        except Exception as e:
            logger.error(f"KC{channel} Channel valve error: {e}")
            show_message(f"Failed to switch valve: {e}", "Error")

    # === INTERNAL PUMP HANDLERS (RPi Peristaltic Pumps - Separate from AffiPump) ===

    def _on_internal_pump_sync_toggled(self, checked: bool):
        """User toggled internal pump synchronization.

        When enabled, both KC1 and KC2 pumps run together at same flow rate.

        Args:
            checked: True = sync enabled (both pumps), False = single channel control
        """
        mode = "SYNCHRONIZED (Both KC1 & KC2)" if checked else "INDEPENDENT (Single Channel)"
        logger.info(f"🔄 Internal pump mode → {mode}")

        # Apply current flow rate to both pumps if sync enabled
        if checked:
            if combo := self._sidebar_widget('internal_pump_flowrate_combo'):
                flowrate_text = combo.currentText()
                logger.info(f"✓ Sync enabled - applying flow rate '{flowrate_text}' to both pumps")
                # Trigger flow rate change which will handle synced operation
                self._on_internal_pump_flowrate_changed(flowrate_text)

    def _on_internal_pump_flowrate_changed(self, flowrate_text: str):
        """User changed internal pump flow rate.

        Args:
            flowrate_text: Selected flow rate ('50', '100', '200', or 'Flush')
        """
        ctrl = self.hardware_mgr.controller
        if not ctrl:
            return

        # Parse flow rate
        if flowrate_text == "Flush":
            rate = 500  # Flush rate
        else:
            try:
                rate = int(flowrate_text)
            except ValueError:
                logger.warning(f"Invalid flow rate: {flowrate_text}")
                return

        # Get selected channel (1 or 2) or both if sync is on
        sync_enabled = False
        if btn := self._sidebar_widget('internal_pump_sync_btn'):
            sync_enabled = btn.isChecked()

        if sync_enabled:
            # Control both channels together
            logger.info(f"🔄 Internal pumps (both KC1 & KC2) → {rate} µL/min (synced)")
            try:
                ctrl.knx_start(rate, 1)  # KC1
                ctrl.knx_start(rate, 2)  # KC2
                logger.info(f"✓ Both internal pumps started at {rate} µL/min")
            except Exception as e:
                logger.error(f"Failed to start synced pumps: {e}")
                from affilabs.widgets.message import show_message
                show_message(f"Failed to start pumps: {e}", "Error")
        else:
            # Control only selected channel
            channel = 1
            if btn := self._sidebar_widget('internal_pump_channel_btn_2'):
                if btn.isChecked():
                    channel = 2

            logger.info(f"🔄 Internal pump KC{channel} → {rate} µL/min")
            try:
                ctrl.knx_start(rate, channel)
                logger.info(f"✓ Internal pump KC{channel} started at {rate} µL/min")
            except Exception as e:
                logger.error(f"Failed to start pump KC{channel}: {e}")
                from affilabs.widgets.message import show_message
                show_message(f"Failed to start pump: {e}", "Error")

    def _create_injection_alignment_line(self, time_val: float):
        """Create vertical line at injection start time for alignment."""
        import pyqtgraph as pg
        from PySide6.QtCore import Qt

        # Create vertical line spanning the graph
        self._injection_alignment_line = pg.InfiniteLine(
            pos=time_val,
            angle=90,  # Vertical
            pen=pg.mkPen(color=(255, 50, 50, 100), width=2, style=Qt.PenStyle.DashLine),
            movable=False,
            label='Injection Started'
        )
        self.main_window.cycle_of_interest_graph.addItem(self._injection_alignment_line)

    # ------------------------------------------------------------------ #
    # Polling timers (called by QTimer in _finalize_and_show)             #
    # ------------------------------------------------------------------ #

    def _poll_plunger_position(self):
        """Poll plunger position every 5 seconds and update flow status board."""
        if not self.pump_mgr or not self.pump_mgr.is_available:
            return
        try:
            pump = self.hardware_mgr.pump
            if pump and hasattr(pump, '_pump') and pump._pump and hasattr(pump._pump, 'pump'):
                p1_pos = pump._pump.pump.get_plunger_position(1) or 0.0
                p2_pos = pump._pump.pump.get_plunger_position(2) or 0.0
                avg_pos = (p1_pos + p2_pos) / 2.0
                ui = self.main_window.sidebar
                if hasattr(ui, 'flow_plunger_position'):
                    ui.flow_plunger_position.setText(f"{avg_pos:.0f}")
                if self.pump_mgr.is_idle:
                    logger.debug(f"Plunger Poll: Pump1={p1_pos:.1f}µL, Pump2={p2_pos:.1f}µL")
        except Exception as e:
            logger.debug(f"Plunger poll error: {e}")

    def _poll_valve_positions(self):
        """Poll valve positions every 3 seconds and sync UI to hardware state."""
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            return
        try:
            kc1_loop = ctrl.knx_six_state(1)
            kc2_loop = ctrl.knx_six_state(2)
            kc1_channel = ctrl.knx_three_state(1)
            kc2_channel = ctrl.knx_three_state(2)
            ui = self.main_window.sidebar

            def _set_exclusive(btn_a, btn_b, state_a):
                if btn_a is None:
                    return
                btn_a.blockSignals(True)
                btn_b.blockSignals(True)
                btn_a.setChecked(state_a)
                btn_b.setChecked(not state_a)
                btn_a.blockSignals(False)
                btn_b.blockSignals(False)

            if kc1_loop is not None and hasattr(ui, 'kc1_loop_btn_load'):
                _set_exclusive(ui.kc1_loop_btn_load, ui.kc1_loop_btn_sensor, kc1_loop == 0)
            if kc2_loop is not None and hasattr(ui, 'kc2_loop_btn_load'):
                _set_exclusive(ui.kc2_loop_btn_load, ui.kc2_loop_btn_sensor, kc2_loop == 0)
            if kc1_channel is not None and hasattr(ui, 'kc1_channel_btn_a'):
                _set_exclusive(ui.kc1_channel_btn_a, ui.kc1_channel_btn_b, kc1_channel == 1)
            if kc2_channel is not None and hasattr(ui, 'kc2_channel_btn_c'):
                _set_exclusive(ui.kc2_channel_btn_c, ui.kc2_channel_btn_d, kc2_channel == 1)
        except Exception as e:
            logger.debug(f"Valve poll error: {e}")

    # ------------------------------------------------------------------ #
    # Pump UI handlers (connected by main.py with hasattr guards)         #
    # ------------------------------------------------------------------ #

    def _on_synced_rpm_changed(self):
        """Synced correction RPM spin changed — update pump RPM accordingly."""
        try:
            ui = self.main_window.sidebar
            if hasattr(ui, 'synced_correction_spin'):
                correction = float(ui.synced_correction_spin.value())
                self._update_synced_rpm(correction)
        except Exception as e:
            logger.debug(f"_on_synced_rpm_changed error: {e}")

    def _on_start_buffer_clicked(self):
        """User clicked Start Buffer button — toggle continuous buffer flow."""
        import threading

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if self.pump_mgr.current_operation == self.PumpOperation.RUNNING_BUFFER:
            logger.info("Stopping buffer flow...")
            self.pump_mgr.cancel_operation()
            if hasattr(self.main_window.sidebar, 'start_buffer_btn'):
                self.main_window.sidebar.start_buffer_btn.setText("▶ Start Buffer")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        flow_rate = 25.0
        if hasattr(self.main_window.sidebar, 'pump_setup_spin'):
            flow_rate = float(self.main_window.sidebar.pump_setup_spin.value())

        if hasattr(self.main_window.sidebar, 'start_buffer_btn'):
            self.main_window.sidebar.start_buffer_btn.setText("⏹ Stop Buffer")

        def run_buffer_flow():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=0, duration_min=0, volume_ul=1000.0, flow_rate=flow_rate
                ))
            finally:
                loop.close()

        threading.Thread(target=run_buffer_flow, daemon=True, name="BufferFlow").start()

    def _on_flush_loop_clicked(self):
        """User clicked Flush Loop button — flush sample loop with buffer."""
        import threading

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected. Connect pump to use this feature.", "Warning")
            return

        if not self.pump_mgr.is_idle:
            from affilabs.widgets.message import show_message
            show_message(f"Pump is currently {self.pump_mgr.current_operation.name}. Wait for completion.", "Warning")
            return

        flush_rate = 5000.0
        if hasattr(self.main_window.sidebar, 'pump_flush_rate'):
            flush_rate = float(self.main_window.sidebar.pump_flush_rate)

        def run_flush():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=3, duration_min=0, volume_ul=1000.0, flow_rate=flush_rate
                ))
            finally:
                loop.close()

        threading.Thread(target=run_flush, daemon=True, name="FlushLoop").start()

    def _on_emergency_stop_clicked(self):
        """User clicked Emergency Stop button — immediately terminate all operations."""
        import threading

        logger.warning("EMERGENCY STOP requested by user")

        if not self.pump_mgr.is_available:
            from affilabs.widgets.message import show_message
            show_message("AffiPump not connected.", "Warning")
            return

        def run_emergency_stop():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.emergency_stop())
            finally:
                loop.close()

        threading.Thread(target=run_emergency_stop, daemon=True, name="EmergencyStop").start()

    def _start_buffer_for_cycle(self, flow_rate: float):
        """Start continuous buffer flow at the given rate for a cycle."""
        import threading

        if not self.pump_mgr or not self.pump_mgr.is_available:
            logger.warning("No pump available for buffer flow")
            return

        def run_buffer():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pump_mgr.run_buffer(
                    cycles=0, duration_min=0, volume_ul=1000.0, flow_rate=flow_rate
                ))
            finally:
                loop.close()

        threading.Thread(target=run_buffer, daemon=True, name="CycleBuffer").start()
        logger.info(f"Buffer flow started at {flow_rate} µL/min for cycle")

    def _on_build_method(self):
        """Build Method button clicked — open method builder dialog (non-modal, reused)."""
        import traceback

        try:
            from affilabs.widgets.method_builder_dialog import MethodBuilderDialog
        except ImportError as e:
            logger.error(f"MethodBuilderDialog import failed: {e}\n{traceback.format_exc()}")
            return

        try:
            # Reuse existing dialog instance (keeps local cycles between opens)
            if not hasattr(self, '_method_builder_dialog') or not self._method_builder_dialog:
                user_mgr = getattr(self, 'user_profile_manager', None)
                self._method_builder_dialog = MethodBuilderDialog(
                    self.main_window,
                    user_manager=user_mgr,
                    app=self,
                )
                self._method_builder_dialog.method_ready.connect(self._on_method_ready)
                self._method_builder_dialog.method_saved.connect(self._on_method_saved)

            # Configure for currently connected hardware
            try:
                hw_name = self._detect_hw_name()
                has_pump = (hasattr(self, 'pump_mgr') and self.pump_mgr
                            and getattr(self.pump_mgr, 'is_available', False))
                self._method_builder_dialog.configure_for_hardware(hw_name, has_affipump=has_pump)
            except Exception:
                pass  # Hardware detection failure is non-fatal

            self._method_builder_dialog.show()
            self._method_builder_dialog.raise_()
            self._method_builder_dialog.activateWindow()

        except Exception as e:
            logger.error(f"_on_build_method error: {e}\n{traceback.format_exc()}")

    def _detect_hw_name(self) -> str:
        """Return hardware identifier string from connected controller."""
        try:
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                ctrl_type = getattr(self.hardware_mgr, '_ctrl_type', None)
                if ctrl_type == "PicoP4SPR":
                    return "P4SPR"
                elif ctrl_type == "PicoP4PRO":
                    raw = getattr(self.hardware_mgr, '_ctrl_raw', None)
                    if raw and hasattr(raw, 'firmware_id'):
                        fwid = raw.firmware_id.lower()
                        if 'p4proplus' in fwid or 'pro+' in fwid:
                            return "P4PROPLUS"
                    return "P4PRO"
        except Exception:
            pass
        return "P4SPR"  # Safe fallback

    def _on_method_ready(self, action: str, method_name: str, cycles: list):
        """Handle method push from Method Builder dialog.

        Args:
            action: 'queue' (add to queue) or 'start' (queue and start immediately)
            method_name: Display name for the method
            cycles: List of Cycle objects to queue
        """
        if not cycles:
            logger.warning("_on_method_ready: empty cycle list, ignoring")
            return

        logger.info(f"Method ready: '{method_name}' with {len(cycles)} cycles (action={action})")

        # Clear stale cycle markers from any previous run
        try:
            self._clear_all_cycle_markers()
        except Exception:
            pass

        # Tag all cycles with source method name
        for cycle in cycles:
            cycle.source_method = method_name

        # Add all cycles to queue as a batch (single undo removes entire method)
        try:
            self.queue_presenter.add_method(cycles, method_name)
        except Exception as e:
            logger.error(f"_on_method_ready: add method failed: {e}")
            return

        if hasattr(self, 'main_window') and hasattr(self.main_window, 'stage_bar'):
            try:
                _chip = self.main_window.transport_bar.step_chip
                # Only advance to "method" if already connected (calibrate=1 or higher)
                if _chip._completed_idx >= 0:
                    self.main_window.stage_bar.advance_to("method")
            except Exception:
                self.main_window.stage_bar.advance_to("method")

        # Refresh summary table
        try:
            tbl = getattr(getattr(self.main_window, 'sidebar', None), 'summary_table', None)
            if tbl:
                tbl.refresh()
        except Exception:
            pass

        # Expand queue panel so user sees the table immediately
        try:
            self.main_window.expand_queue_panel()
        except Exception as e:
            logger.debug(f"expand_queue_panel after method queue: {e}")

        # Start immediately if requested (one-click "build and run")
        if action == "start":
            logger.info(f"Auto-starting acquisition after queueing method '{method_name}'")
            try:
                # Check if acquisition coordinator exists
                if hasattr(self, 'acq_coordinator'):
                    # Start acquisition (will begin first cycle automatically)
                    success = self.acq_coordinator._start_acquisition()
                    if success:
                        self.acq_coordinator._update_ui_after_start()
                        logger.info(f"✅ Auto-start successful for method '{method_name}'")
                    else:
                        logger.error("Auto-start failed: acquisition coordinator returned False")
                else:
                    logger.warning("Auto-start skipped: acquisition coordinator not available")
            except Exception as e:
                logger.error(f"Auto-start failed: {e}", exc_info=True)
            try:
                self._on_start_button_clicked()
            except Exception as e:
                logger.error(f"_on_method_ready: start failed: {e}")

    def _on_method_saved(self, method_name: str, file_path: str):
        """Handle method save from Method Builder dialog.

        Expands the Run Queue panel so the user can see the queue after saving.

        Args:
            method_name: Name of the saved method
            file_path: Full path to the saved .json file
        """
        logger.info(f"Method saved: '{method_name}' → {file_path}")
        try:
            self.main_window.expand_queue_panel()
        except Exception as e:
            logger.error(f"Failed to expand queue panel on method save: {e}")

    def _on_save_preset(self):
        """Save current cycle queue as a preset file."""
        try:
            from affilabs.utils.cycle_preset_helpers import CyclePresetHelpers
            CyclePresetHelpers.save_preset(self)
        except ImportError:
            logger.warning("CyclePresetHelpers not available — save_preset not implemented")
        except Exception as e:
            logger.error(f"_on_save_preset error: {e}")

    def _on_load_preset(self):
        """Load a preset file into the cycle queue."""
        try:
            from affilabs.utils.cycle_preset_helpers import CyclePresetHelpers
            CyclePresetHelpers.load_preset(self)
        except ImportError:
            logger.warning("CyclePresetHelpers not available — load_preset not implemented")
        except Exception as e:
            logger.error(f"_on_load_preset error: {e}")

    def _on_toggle_pause_queue(self):
        """Pause or resume the automatic cycle queue."""
        if getattr(self, '_queue_paused', False):
            self._queue_paused = False
            logger.info("Cycle queue resumed")
            if hasattr(self.main_window.sidebar, 'pause_queue_btn'):
                self.main_window.sidebar.pause_queue_btn.setText("⏸ Pause Queue")
        else:
            self._queue_paused = True
            logger.info("Cycle queue paused")
            if hasattr(self.main_window.sidebar, 'pause_queue_btn'):
                self.main_window.sidebar.pause_queue_btn.setText("▶ Resume Queue")
