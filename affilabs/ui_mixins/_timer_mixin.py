"""Timer mixin for AffilabsCoreUI.

Extracted from affilabs/affilabs_core_ui.py — manual timer, pop-out timer window,
alarm loop, wash acknowledgement, and automatic wash flag placement.

Methods included:
    - update_timer_button
    - clear_timer_button
    - _auto_show_timer_window
    - _on_timer_button_clicked
    - _on_popout_timer_ready
    - _show_popout_timer
    - _on_popout_closed
    - _on_popout_shown
    - _on_popout_hidden
    - _on_pause_manual_timer
    - _on_resume_manual_timer
    - _on_timer_time_edited
    - _start_manual_timer_countdown
    - _on_manual_timer_tick
    - _on_wash_acknowledged
    - _play_timer_sound
    - _start_alarm_loop
    - _place_automatic_wash_flags
    - _stop_alarm_loop
    - _on_clear_manual_timer
    - _on_restart_manual_timer
"""

from PySide6.QtCore import QTimer

from affilabs.utils.logger import logger


class TimerMixin:
    """Mixin providing manual timer, pop-out timer window, alarm loop,
    wash acknowledgement, and automatic wash flag placement for AffilabsCoreUI."""

    def update_timer_button(self, cycle_type: str, remaining_seconds: float, is_manual: bool = False) -> None:
        """Update the Timer button above Live Sensorgram with countdown.

        NOTE: This timer is ONLY for manual user-set timers, NOT for cycle countdowns.
        Cycle countdown is shown in the intelligence bar at the bottom.

        Args:
            cycle_type: Type of timer (label for manual timers)
            remaining_seconds: Seconds remaining in timer
            is_manual: Must be True - only manual timers are displayed
        """
        # ONLY update for manual user timers, never for cycle countdowns
        if is_manual and hasattr(self, 'timer_button'):
            self.timer_button.update_countdown(cycle_type, remaining_seconds, is_manual=is_manual)

    def clear_timer_button(self) -> None:
        """Clear the Timer button display when no cycle is running."""
        if hasattr(self, 'timer_button'):
            self.timer_button.clear()

    def _auto_show_timer_window(self, label: str, total_seconds: int):
        """Auto-show PopOutTimerWindow for contact timers.

        Args:
            label: Timer label
            total_seconds: Timer duration in seconds
        """
        from affilabs.widgets.popout_timer_window import PopOutTimerWindow
        from affilabs.utils.logger import logger

        # Create window if needed
        if not hasattr(self, '_popout_timer') or self._popout_timer is None:
            self._popout_timer = PopOutTimerWindow(parent=None)
            self._popout_timer.timer_ready.connect(self._on_popout_timer_ready)
            self._popout_timer.clear_requested.connect(self._on_clear_manual_timer)
            self._popout_timer.restart_requested.connect(self._on_restart_manual_timer)
            self._popout_timer.pause_requested.connect(self._on_pause_manual_timer)
            self._popout_timer.resume_requested.connect(self._on_resume_manual_timer)
            self._popout_timer.closed.connect(self._on_popout_closed)
            self._popout_timer.alarm_stopped.connect(self._stop_alarm_loop)
            self._popout_timer.time_edited_while_paused.connect(self._on_timer_time_edited)
            self._popout_timer.window_shown.connect(self._on_popout_shown)
            self._popout_timer.window_hidden.connect(self._on_popout_hidden)

        # Put window into running display state WITHOUT emitting timer_ready.
        # The QTimer countdown is already managed by _start_manual_timer_countdown;
        # calling set_running() would re-emit timer_ready → _on_popout_timer_ready
        # → _start_manual_timer_countdown → _auto_show_timer_window → infinite loop.
        self._popout_timer.show_running_state(total_seconds, label)

        # Show the window
        self._popout_timer.show()
        self._popout_timer.raise_()
        self._popout_timer.activateWindow()

    def _on_timer_button_clicked(self):
        """Handle Timer button click - open PopOutTimerWindow or stop alarm.

        If wash alert is active (alarm ringing), clicking stops the alarm.
        If no timer is running, opens in configurable mode.
        If a timer is already running/paused, syncs window state and brings to focus.
        """
        from affilabs.utils.logger import logger

        # If wash alert is active, clicking stops the alarm
        if hasattr(self, 'timer_button') and self.timer_button.wash_alert_active:
            logger.debug("Wash acknowledged via timer button click")
            self._on_wash_acknowledged()
            return

        # Create pop-out timer window if it doesn't exist
        if not hasattr(self, '_popout_timer') or self._popout_timer is None:
            from affilabs.widgets.popout_timer_window import PopOutTimerWindow
            self._popout_timer = PopOutTimerWindow(parent=None)
            # Connect timer_ready signal to start the countdown
            self._popout_timer.timer_ready.connect(self._on_popout_timer_ready)
            # Connect control signals
            self._popout_timer.clear_requested.connect(self._on_clear_manual_timer)
            self._popout_timer.restart_requested.connect(self._on_restart_manual_timer)
            self._popout_timer.pause_requested.connect(self._on_pause_manual_timer)
            self._popout_timer.resume_requested.connect(self._on_resume_manual_timer)
            self._popout_timer.closed.connect(self._on_popout_closed)
            self._popout_timer.alarm_stopped.connect(self._stop_alarm_loop)
            self._popout_timer.time_edited_while_paused.connect(self._on_timer_time_edited)
            # Connect window visibility signals to highlight timer button
            self._popout_timer.window_shown.connect(self._on_popout_shown)
            self._popout_timer.window_hidden.connect(self._on_popout_hidden)

        # Check current timer state
        timer_active = (
            hasattr(self, '_manual_timer')
            and self._manual_timer
            and (self._manual_timer.isActive()
                 or (hasattr(self, '_manual_timer_remaining')
                     and self._manual_timer_remaining > 0))
        )
        alarm_active = (
            hasattr(self, '_popout_timer')
            and self._popout_timer
            and self._popout_timer._alarm_active
        )

        if alarm_active:
            # Alarm is ringing - just show the window with stop button
            logger.info("Showing alarm window (alarm active)")
            self._popout_timer.timer_finished(self._manual_timer_label)
        elif timer_active:
            # Timer is running/paused - sync the window state
            is_paused = (
                hasattr(self, '_manual_timer')
                and self._manual_timer
                and not self._manual_timer.isActive()
                and self._manual_timer_remaining > 0
            )

            logger.debug(f"Syncing timer window (running={'paused' if is_paused else 'active'})")

            # Update window with current timer state
            self._popout_timer.update_countdown(
                self._manual_timer_label,
                self._manual_timer_remaining
            )
            self._popout_timer.set_paused(is_paused)
        else:
            # No timer running — open in configurable mode
            # Use last-set time if available; otherwise fall back to current cycle's contact_time
            if hasattr(self, '_last_timer_minutes'):
                last_minutes = self._last_timer_minutes
                last_seconds = getattr(self, '_last_timer_seconds', 0)
            else:
                # Pre-populate from the active cycle's contact_time (if set)
                current_cycle = getattr(getattr(self, 'app', None), '_current_cycle', None)
                if current_cycle and getattr(current_cycle, 'contact_time', None) and current_cycle.contact_time > 0:
                    ct = int(current_cycle.contact_time)
                    last_minutes = ct // 60
                    last_seconds = ct % 60
                else:
                    last_minutes = 5
                    last_seconds = 0
            last_label = getattr(self, '_last_timer_label', "Timer")

            self._popout_timer.set_configurable(
                minutes=last_minutes,
                seconds=last_seconds,
                label=last_label,
                sound_enabled=True,
                rolling_numbers=False,
            )
            logger.debug("Timer window opened in config mode")

        # Show and focus the window
        self._popout_timer.show()
        self._popout_timer.raise_()
        self._popout_timer.activateWindow()

    def _on_popout_timer_ready(self, total_seconds: int, label: str):
        """Handle timer ready signal from PopOutTimerWindow.

        Called when user confirms timer settings and starts countdown.
        """
        from affilabs.utils.logger import logger

        logger.debug(f"Timer started: {label} ({total_seconds//60}:{total_seconds%60:02d})")

        # Save last used settings for next open
        self._last_timer_minutes = total_seconds // 60
        self._last_timer_seconds = total_seconds % 60
        self._last_timer_label = label

        # Update timer button
        self.update_timer_button(label, total_seconds, is_manual=True)

        # Clear next_action for generic manual timers (not auto-started from injection)
        self._manual_timer_next_action = ""

        # Start countdown for manual timer
        self._start_manual_timer_countdown(label, total_seconds, sound_enabled=True)

    # ------------------------------------------------------------------
    #  Pop-out timer window helpers
    # ------------------------------------------------------------------
    def _show_popout_timer(self, label: str, total_seconds: int):
        """Update the pop-out countdown window with new values.

        Args:
            label: Timer label text
            total_seconds: Starting countdown in seconds
        """
        if hasattr(self, '_popout_timer') and self._popout_timer:
            self._popout_timer.update_countdown(label, total_seconds)

    def _on_popout_closed(self):
        """Handle pop-out window closed by user (don't stop the timer)."""
        pass  # Timer keeps running; user can reopen via timer button

    def _on_popout_shown(self):
        """Handle popout timer window shown - highlight the timer button."""
        if hasattr(self, 'timer_button'):
            self.timer_button.set_bright_style(True)

    def _on_popout_hidden(self):
        """Handle popout timer window hidden - remove button highlight."""
        if hasattr(self, 'timer_button'):
            self.timer_button.set_bright_style(False)

    def _on_pause_manual_timer(self):
        """Pause the manual countdown timer."""
        from affilabs.utils.logger import logger

        if hasattr(self, '_manual_timer') and self._manual_timer:
            if self._manual_timer.isActive():
                self._manual_timer.stop()
                logger.debug("⏸ Timer paused")

            # Always update window state to ensure sync
            if hasattr(self, '_popout_timer') and self._popout_timer:
                self._popout_timer.set_paused(True)

    def _on_resume_manual_timer(self):
        """Resume the manual countdown timer."""
        from affilabs.utils.logger import logger

        if hasattr(self, '_manual_timer') and self._manual_timer:
            if not self._manual_timer.isActive():
                if hasattr(self, '_manual_timer_remaining') and self._manual_timer_remaining > 0:
                    self._manual_timer.start(1000)
                    logger.debug("▶ Timer resumed")

            # Always update window state to ensure sync
            if hasattr(self, '_popout_timer') and self._popout_timer:
                self._popout_timer.set_paused(False)

    def _on_timer_time_edited(self, new_remaining_seconds: int):
        """Handle timer time being edited while paused.

        When user edits the time in the popout timer while paused, sync the new
        value back to the main timer state so resume uses the edited value.
        """
        from affilabs.utils.logger import logger

        if hasattr(self, '_manual_timer_remaining'):
            old_value = self._manual_timer_remaining
            self._manual_timer_remaining = new_remaining_seconds
            logger.debug(f"Timer adjusted while paused: {old_value}s → {new_remaining_seconds}s")

    def _start_manual_timer_countdown(self, label: str, total_seconds: int, sound_enabled: bool):
        """Start countdown timer for manual timers.

        Args:
            label: Timer label
            total_seconds: Duration in seconds
            sound_enabled: Whether to play sound on completion
        """
        from PySide6.QtCore import QTimer
        from affilabs.utils.logger import logger

        # Stop any existing manual timer
        if hasattr(self, '_manual_timer') and self._manual_timer:
            self._manual_timer.stop()

        # Create timer state (save initial duration for restart functionality)
        self._manual_timer_remaining = total_seconds
        self._manual_timer_label = label
        self._manual_timer_sound = sound_enabled
        self._manual_timer_initial_duration = total_seconds  # Save original duration for restart

        # Create QTimer for countdown
        self._manual_timer = QTimer(self)
        self._manual_timer.timeout.connect(self._on_manual_timer_tick)
        self._manual_timer.start(1000)  # Update every second

        # Auto-open PopOutTimerWindow for contact timers (helps user track critical timing)
        if "Contact" in label:
            self._auto_show_timer_window(label, total_seconds)

    def _on_manual_timer_tick(self):
        """Handle manual timer countdown tick."""
        from affilabs.utils.logger import logger

        self._manual_timer_remaining -= 1

        if self._manual_timer_remaining > 0:
            # Update timer button in navigation bar
            self.update_timer_button(self._manual_timer_label, self._manual_timer_remaining, is_manual=True)

            # Update pop-out window if open
            if hasattr(self, '_popout_timer') and self._popout_timer and self._popout_timer.isVisible():
                self._popout_timer.update_countdown(self._manual_timer_label, self._manual_timer_remaining)

            # Update contact timer overlay on cycle graph if active
            if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr'):
                self.app.flag_mgr.update_contact_timer_display()
        else:
            # Timer completed
            self._manual_timer.stop()
            logger.debug(f"Manual timer '{self._manual_timer_label}' completed!")

            # Show WASH NOW alert on timer button (click to stop alarm)
            if hasattr(self, 'timer_button'):
                self.timer_button.show_wash_alert()

            # Update pop-out window with finished state
            next_action = getattr(self, '_manual_timer_next_action', "")
            if hasattr(self, '_popout_timer') and self._popout_timer and self._popout_timer.isVisible():
                self._popout_timer.timer_finished(self._manual_timer_label, next_action)

            # Clear contact timer overlay from cycle graph
            if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr'):
                self.app.flag_mgr.clear_contact_timer_overlay()

            # Automatically place wash flags for all channels with injection flags
            self._place_automatic_wash_flags()

            # Start looping alarm sound if enabled
            if self._manual_timer_sound:
                self._start_alarm_loop()

    def _on_wash_acknowledged(self):
        """Handle wash acknowledged — stop alarm."""
        from affilabs.utils.logger import logger

        logger.info("Wash acknowledged — stopping alarm")
        self._stop_alarm_loop()

    def _play_timer_sound(self):
        """Play professional synthesized alarm tone (ascending alert)."""
        from affilabs.utils.alarm_sound import get_alarm_player

        try:
            alarm = get_alarm_player()
            # Play ascending alert (professional 3-tone notification sound)
            success = alarm.play_alarm(style="ascending", repeats=1)
            if not success:
                logger.debug("Alarm playback failed, no sound output available")
        except Exception as e:
            logger.debug(f"Could not play timer sound: {e}")

    def _start_alarm_loop(self):
        """Start looping alarm sound (ascending tone) until user stops it."""
        # Create alarm loop timer if it doesn't exist
        if not hasattr(self, '_alarm_loop_timer'):
            self._alarm_loop_timer = QTimer(self)
            self._alarm_loop_timer.timeout.connect(self._play_timer_sound)

        # Play immediately
        self._play_timer_sound()

        # Loop every 1.5 seconds (quick repeating alert)
        self._alarm_loop_timer.start(1500)
        logger.debug("Alarm loop started (ascending tone every 1.5s)")

    def _place_automatic_wash_flags(self):
        """Automatically place wash flags when contact time expires.

        Places wash flags on all channels that have injection flags.
        Wash time = injection_flag.time + contact_time (cycle-relative display coords).

        Uses FlagManager (self.app.flag_mgr) — the single source of truth for flags.
        """
        from affilabs.utils.logger import logger

        try:
            app = getattr(self, 'app', None)
            if not app:
                return

            flag_mgr = getattr(app, 'flag_mgr', None)
            if not flag_mgr:
                logger.debug("No FlagManager available - skipping automatic wash flags")
                return

            buffer_mgr = getattr(app, 'buffer_mgr', None)
            clock = getattr(app, 'clock', None)
            if not buffer_mgr or not clock:
                logger.debug("No buffer_mgr or clock - skipping automatic wash flags")
                return

            # Read injection flags from FlagManager (Flag domain model instances)
            from affilabs.domain.flag import InjectionFlag
            injection_flags = [
                f for f in flag_mgr._flag_markers if isinstance(f, InjectionFlag)
            ]

            if not injection_flags:
                logger.debug("No injection flags found - skipping automatic wash flags")
                return

            # Get current cycle display time for wash position
            # The wash time = now in cycle-relative display coordinates
            if not hasattr(self, 'full_timeline_graph'):
                return
            timeline = self.full_timeline_graph
            if not hasattr(timeline, 'stop_cursor') or not hasattr(timeline, 'start_cursor'):
                return

            from affilabs.core.experiment_clock import TimeBase
            stop_display = timeline.stop_cursor.value()
            start_display = timeline.start_cursor.value()
            start_raw = clock.convert(start_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED)
            stop_raw = clock.convert(stop_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED)
            # Wash time in cycle-relative display coords (same coords the injection flag uses)
            wash_display_time = stop_raw - start_raw

            import numpy as np

            # Place wash flag on each channel that has an injection flag
            for inj_flag in injection_flags:
                ch = inj_flag.channel.lower()
                try:
                    if ch not in buffer_mgr.cycle_data:
                        continue

                    channel_data = buffer_mgr.cycle_data[ch]
                    if len(channel_data.time) == 0 or len(channel_data.spr) == 0:
                        continue

                    # Look up SPR value at wash time (raw elapsed coords in buffer)
                    time_idx = np.argmin(np.abs(channel_data.time - stop_raw))
                    spr_val = channel_data.spr[time_idx]

                    # Place wash flag via FlagManager (modern path)
                    flag_mgr.add_flag_marker(
                        channel=ch,
                        time_val=wash_display_time,
                        spr_val=spr_val,
                        flag_type='wash'
                    )
                    logger.info(
                        f"🧼 Automatic wash flag placed on channel {ch.upper()} "
                        f"at display t={wash_display_time:.1f}s (SPR={spr_val:.1f})"
                    )

                except Exception as e:
                    logger.debug(f"Could not place wash flag on channel {ch}: {e}")

            # Also draw a single wash event line on the live sensorgram (full_timeline_graph)
            # stop_display is already in DISPLAY coords (the stop cursor position)
            try:
                import pyqtgraph as pg
                from PySide6.QtCore import Qt
                wash_line = pg.InfiniteLine(
                    pos=stop_display,
                    angle=90,
                    pen=pg.mkPen(color=(30, 144, 255), width=2, style=Qt.PenStyle.DashLine),
                    movable=False,
                    label='🧼 Wash',
                    labelOpts={
                        'position': 0.92,
                        'color': (30, 144, 255),
                        'fill': (255, 255, 255, 180),
                    }
                )
                timeline.addItem(wash_line)
                if not hasattr(self, '_wash_timeline_lines'):
                    self._wash_timeline_lines = []
                self._wash_timeline_lines.append(wash_line)
                logger.debug(f"🧼 Wash line added to live sensorgram at display={stop_display:.1f}s")
            except Exception as e:
                logger.debug(f"Could not add wash line to live sensorgram: {e}")

        except Exception as e:
            logger.debug(f"Could not place automatic wash flags: {e}")

    def _stop_alarm_loop(self):
        """Stop the looping alarm sound and clean up timer state."""
        from affilabs.utils.alarm_sound import get_alarm_player

        # Stop alarm loop timer
        if hasattr(self, '_alarm_loop_timer') and self._alarm_loop_timer.isActive():
            self._alarm_loop_timer.stop()

        # Stop pygame alarm playback
        try:
            alarm = get_alarm_player()
            alarm.stop_alarm()
        except Exception as e:
            logger.debug(f"Could not stop pygame alarm: {e}")

        # Stop the countdown timer if still active
        if hasattr(self, '_manual_timer') and self._manual_timer:
            self._manual_timer.stop()

        # Clear timer state so re-click opens config mode
        if hasattr(self, '_manual_timer_remaining'):
            self._manual_timer_remaining = 0

        # Clear timer button display
        self.clear_timer_button()

        logger.debug("🔇 Alarm stopped and timer cleared")

    def _on_clear_manual_timer(self):
        """Handle request to clear manual timer (from context menu)."""
        from affilabs.utils.logger import logger

        # Stop the manual timer if running
        if hasattr(self, '_manual_timer') and self._manual_timer:
            self._manual_timer.stop()
            logger.debug(f"Manual timer cleared by user")

        # Clear the timer button display
        self.clear_timer_button()

        # Clear timer overlay from graph
        if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr'):
            self.app.flag_mgr.clear_contact_timer_overlay()

        # Hide pop-out window
        if hasattr(self, '_popout_timer') and self._popout_timer:
            self._popout_timer.hide()

    def _on_restart_manual_timer(self):
        """Handle request to restart manual timer (from context menu)."""
        from affilabs.utils.logger import logger

        # Check if we have a timer to restart
        if not hasattr(self, '_manual_timer_initial_duration'):
            logger.warning("No manual timer to restart")
            return

        # Get saved timer settings
        initial_duration = self._manual_timer_initial_duration
        label = self._manual_timer_label
        sound_enabled = self._manual_timer_sound

        logger.debug(f"↻ Restarting manual timer '{label}' ({initial_duration}s)")

        # Stop any alarm that might be playing
        self._stop_alarm_loop()

        # Restart timer with original settings
        self._start_manual_timer_countdown(label, initial_duration, sound_enabled)

        # Recreate contact timer overlay on graph
        if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr'):
            self.app.flag_mgr.create_contact_timer_overlay(initial_duration)

        # Update display immediately
        self.update_timer_button(label, initial_duration, is_manual=True)

        # Update pop-out window and ensure it's in running state (not paused or alarm)
        if hasattr(self, '_popout_timer') and self._popout_timer:
            # Reset alarm state flag
            self._popout_timer._alarm_active = False
            self._popout_timer._stop_alarm_btn.setVisible(False)
            # Set to running state
            self._popout_timer.set_paused(False)
            self._popout_timer.update_countdown(label, initial_duration)
            # Show control buttons (pause/restart visible, start hidden)
            self._popout_timer._pause_btn.setVisible(True)
            self._popout_timer._restart_btn.setVisible(True)
            self._popout_timer._start_btn.setVisible(False)
            logger.debug(f"Timer window state reset: alarm=False, paused=False")
