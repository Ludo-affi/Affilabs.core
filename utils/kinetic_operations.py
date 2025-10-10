from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from settings import FLUSH_RATE
from utils.cavro_pump_manager import PumpAddress
from utils.logger import logger


class KineticOperations:
    """High-level kinetic operations (regenerate, flush, inject) that orchestrate
    PumpManager + Kinetic/Valve controller with minimal UI coupling via callbacks.

    Also handles individual pump control operations for UI handlers.

    This class intentionally avoids any flow SENSOR usage (temperature only system).
    """

    def __init__(
        self,
        *,
        pump_manager: Any | None,
        kinetic_manager: Any | None,
        knx: Any | None,
        start_progress_bar: Callable[[int], None],
        show_message: Callable[[str], None],
        set_inject_enabled: Callable[[bool], None],
        new_segment: Callable[[], None],
        set_flow_rate_now: Callable[[str], None],
        update_pump_display: Callable[[dict, bool], None],
        update_valve_display: Callable[[dict, bool], None],
    ) -> None:
        self.pump_manager = pump_manager
        self.kinetic_manager = kinetic_manager
        self.knx = knx
        self.start_progress_bar = start_progress_bar
        self.show_message = show_message
        self.set_inject_enabled = set_inject_enabled
        self.new_segment = new_segment
        self.set_flow_rate_now = set_flow_rate_now
        self.update_pump_display = update_pump_display
        self.update_valve_display = update_valve_display

    async def regenerate(
        self, *, contact_time_s: float, flow_rate_ml_min: float
    ) -> None:
        """Run regeneration sequence using pump manager."""
        if not self.pump_manager:
            logger.warning("Regenerate called but pump manager not available")
            self.show_message("Pump system not available")
            return
        try:
            # 67 s base + ~18.75 s per minute of contact time (1125 ms/s)
            self.start_progress_bar(int(67_000 + 1125 * contact_time_s))
            await self.pump_manager.regenerate_sequence(
                contact_time=contact_time_s,
                flow_rate=flow_rate_ml_min,
                valve_controller=self.knx,
            )
            logger.info("Regeneration sequence completed")
        except Exception as e:
            logger.exception(f"Error during regeneration: {e}")
            self.show_message(f"Regeneration error: {e}")

    async def flush(self, *, flow_rate_ml_min: float) -> None:
        """Run flush sequence using pump manager."""
        if not self.pump_manager:
            logger.warning("Flush called but pump manager not available")
            self.show_message("Pump system not available")
            return
        try:
            self.start_progress_bar(29_000)
            await self.pump_manager.flush_sequence(flow_rate=flow_rate_ml_min)
            logger.info("Flush sequence completed")
        except Exception as e:
            logger.exception(f"Error during flush: {e}")
            self.show_message(f"Flush error: {e}")

    async def inject(self, *, flow_rate_ml_min: float, injection_time_s: float) -> None:
        """Run injection sequence using pump manager or KNX fallback."""
        try:
            # UI updates
            self.set_flow_rate_now(f"{flow_rate_ml_min:.1f}")
            self.start_progress_bar(int(injection_time_s * 1000))
            self.new_segment()
            self.set_inject_enabled(False)

            if self.pump_manager:
                await self.pump_manager.inject_sequence(
                    flow_rate=flow_rate_ml_min,
                    injection_time=injection_time_s,
                    valve_controller=self.knx,
                )
            elif self.knx:
                # Fallback valve open/close (channel 3 injection)
                self.knx.knx_six(state=1, ch=3)
                await asyncio.sleep(injection_time_s)
                self.knx.knx_six(state=0, ch=3)

            self.set_inject_enabled(True)
            logger.info("Injection completed")
        except Exception as e:
            logger.exception(f"Error during injection: {e}")
            self.set_inject_enabled(True)
            self.show_message(f"Injection error: {e}")

    def cancel_injection(self) -> None:
        """Cancel ongoing injection by closing valve and stopping pumps."""
        try:
            if self.knx:
                self.knx.knx_six(state=0, ch=3)
            if self.pump_manager:
                self.pump_manager.stop()
            logger.info("Injection cancelled")
        except Exception as e:
            logger.exception(f"Error cancelling injection: {e}")

    # Individual pump control methods for UI handlers
    def run_pump(self, ch: str, rate: int, pump_states: dict, synced: bool) -> dict:
        """Start or change pump flow via pump manager."""
        try:
            # Update flow rate display
            self.set_flow_rate_now(str(rate))

            if self.pump_manager:
                addr = PumpAddress.PUMP_1 if ch == "CH1" else PumpAddress.PUMP_2
                self.pump_manager.start_flow(addr, float(rate), True)
                # Optimistically update state; pump manager will emit actual state
                pump_states[ch] = "Flushing" if rate == FLUSH_RATE else "Running"
            else:
                # No hardware: just update UI state
                pump_states[ch] = "Flushing" if rate == FLUSH_RATE else "Running"

            self.update_pump_display(pump_states, synced)
            return pump_states
        except Exception as e:
            logger.exception(f"Error starting pump {ch} at rate {rate}: {e}")
            return pump_states

    def stop_pump(self, ch: str, pump_states: dict, synced: bool) -> dict:
        """Stop a pump using KNX or pump manager."""
        if self.knx is not None:
            try:
                log1 = False
                log2 = True
                if ch == "CH1":
                    log1 = True
                    if synced:
                        log2 = True
                        self.knx.knx_stop(3)
                        pump_states["CH2"] = "Off"
                        if hasattr(self.knx, "version") and self.knx.version == "1.1":
                            self.knx.knx_led("x", 3)
                    else:
                        self.knx.knx_stop(1)
                        if hasattr(self.knx, "version") and self.knx.version == "1.1":
                            self.knx.knx_led("x", 1)
                elif ch == "CH2":
                    log2 = True
                    self.knx.knx_stop(2)
                    if hasattr(self.knx, "version") and self.knx.version == "1.1":
                        self.knx.knx_led("x", 2)

                pump_states[ch] = "Off"
                logger.debug(f"Pump {ch} stopped")

                # Log pump stop events using kinetic manager
                if self.kinetic_manager:
                    if log1:
                        self.kinetic_manager.log_event("CH1", "pump_stop")
                    if log2:
                        self.kinetic_manager.log_event("CH2", "pump_stop")

                self.update_pump_display(pump_states, synced)
            except Exception as e:
                logger.exception(f"Error stopping pump {ch}: {e}")

        return pump_states

    def initialize_pumps(self) -> bool:
        """Initialize the pumps using pump manager."""
        if self.pump_manager:
            try:
                if self.pump_manager.initialize_pumps():
                    logger.info("Pumps reinitialized successfully")
                    self.show_message("Pumps initialized")
                    return True
                logger.warning("Pump reinitialization failed")
                self.show_message("Pump initialization failed")
                return False
            except Exception as e:
                logger.exception(f"Error reinitializing pumps: {e}")
                self.show_message(f"Pump error: {e}")
                return False
        else:
            logger.warning("Initialize pumps called but pump manager not available")
            self.show_message("Pump system not available")
            return False

    def handle_speed_change(
        self, ch: str, new_rate: int, pump_states: dict, synced: bool
    ) -> dict:
        """Handle pump speed changes from UI spinbox."""
        try:
            if pump_states.get(ch) == "Running":
                # Pump is running, so change its speed
                return self.run_pump(ch, new_rate, pump_states, synced)
            # Pump is not running, just update the display value
            self.set_flow_rate_now(str(new_rate))
            return pump_states
        except Exception as e:
            logger.exception(f"Error handling speed change for {ch}: {e}")
            return pump_states

    def handle_valve_control(
        self, valve_id: int, state: int, valve_states: dict
    ) -> dict:
        """Handle valve control operations."""
        try:
            if self.knx:
                self.knx.knx_six(state=state, ch=valve_id)
                valve_states[f"valve_{valve_id}"] = "Open" if state else "Closed"
                logger.debug(f"Valve {valve_id} set to {'open' if state else 'closed'}")
                self.update_valve_display(
                    valve_states, False
                )  # Valves not typically synced
            return valve_states
        except Exception as e:
            logger.exception(f"Error controlling valve {valve_id}: {e}")
            return valve_states
