from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Final

from affilabs.utils.logger import logger


class ValveCycleMixin:
    """Mixin for controllers with 6-port and 3-way valve cycle tracking.

    Provides:
    - Session and lifetime cycle counting
    - JSON file persistence (~/.affilabs/valve_cycles_<device>.json)
    - Safety timeout timers for 6-port valves
    - State tracking for all valve channels

    Subclasses must set before calling _init_valve_tracking():
    - self.name (str)
    - self.firmware_id (str)
    - self._ser (serial port or None)

    Subclasses may override:
    - VALVE_SAFETY_TIMEOUT_SECONDS (class-level constant)
    """

    VALVE_SAFETY_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes

    def _init_valve_tracking(self) -> None:
        """Initialize all valve tracking state. Call from subclass __init__."""
        self._valve_six_cycles_session = {1: 0, 2: 0}
        self._valve_three_cycles_session = {1: 0, 2: 0}
        self._valve_six_cycles_lifetime = {1: 0, 2: 0}
        self._valve_three_cycles_lifetime = {1: 0, 2: 0}
        self._valve_six_state = {1: None, 2: None}
        self._valve_three_state = {1: None, 2: None}
        self._valve_six_timers = {1: None, 2: None}
        self._valve_six_lock = threading.Lock()

    def _get_valve_cycles_file(self) -> Path:
        """Get path to device-specific valve cycles persistence file."""
        home = Path.home()
        affilabs_dir = home / ".affilabs"
        affilabs_dir.mkdir(exist_ok=True)

        fw = getattr(self, "firmware_id", "") or ""
        port = getattr(getattr(self, "_ser", None), "port", "") or ""
        base = self.name.replace(' ', '_').replace('/', '_')
        suffix = "_".join([p for p in [fw, port] if p])
        device_id = f"{base}{('_' + suffix) if suffix else ''}"
        return affilabs_dir / f"valve_cycles_{device_id}.json"

    def _load_valve_cycles(self) -> None:
        """Load lifetime valve cycle counts from persistent storage."""
        try:
            cycles_file = self._get_valve_cycles_file()
            if cycles_file.exists():
                with open(cycles_file, 'r') as f:
                    data = json.load(f)
                    six_data = data.get('valve_six', {})
                    three_data = data.get('valve_three', {})
                    self._valve_six_cycles_lifetime = {int(k): v for k, v in six_data.items()} if six_data else {1: 0, 2: 0}
                    self._valve_three_cycles_lifetime = {int(k): v for k, v in three_data.items()} if three_data else {1: 0, 2: 0}
                    logger.info(f"📊 Loaded lifetime valve cycles: 6-port V1={self._valve_six_cycles_lifetime[1]}, V2={self._valve_six_cycles_lifetime[2]}, 3-way V1={self._valve_three_cycles_lifetime[1]}, V2={self._valve_three_cycles_lifetime[2]}")
        except Exception as e:
            logger.warning(f"Could not load valve cycle history: {e}")

    def _save_valve_cycles(self) -> None:
        """Save lifetime valve cycle counts to persistent storage."""
        try:
            cycles_file = self._get_valve_cycles_file()
            data = {
                'valve_six': self._valve_six_cycles_lifetime,
                'valve_three': self._valve_three_cycles_lifetime,
            }
            with open(cycles_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save valve cycle history: {e}")

    def reset_valve_cycles(self, valve_type=None, channel=None) -> None:
        """Reset valve cycle counts (for maintenance/valve replacement).

        Args:
            valve_type: 'six' or 'three' (None = reset all)
            channel: 1 or 2 (None = reset both channels)
        """
        try:
            if valve_type is None or valve_type == 'six':
                if channel is None:
                    for ch in [1, 2]:
                        self._valve_six_cycles_session[ch] = 0
                        self._valve_six_cycles_lifetime[ch] = 0
                    logger.info("✅ Reset all 6-port valve cycles to 0")
                else:
                    self._valve_six_cycles_session[channel] = 0
                    self._valve_six_cycles_lifetime[channel] = 0
                    logger.info(f"✅ Reset 6-port valve CH{channel} cycles to 0")

            if valve_type is None or valve_type == 'three':
                if channel is None:
                    for ch in [1, 2]:
                        self._valve_three_cycles_session[ch] = 0
                        self._valve_three_cycles_lifetime[ch] = 0
                    logger.info("✅ Reset all 3-way valve cycles to 0")
                else:
                    self._valve_three_cycles_session[channel] = 0
                    self._valve_three_cycles_lifetime[channel] = 0
                    logger.info(f"✅ Reset 3-way valve CH{channel} cycles to 0")

            self._save_valve_cycles()
            logger.info(f"🔧 Valve cycle reset complete for device {self.name}")
        except Exception as e:
            logger.error(f"Error resetting valve cycles: {e}")

    def _cancel_valve_timer(self, ch):
        """Cancel existing safety timer for valve channel."""
        with self._valve_six_lock:
            if self._valve_six_timers[ch] is not None:
                self._valve_six_timers[ch].cancel()
                self._valve_six_timers[ch] = None
                logger.debug(f"Cancelled safety timer for 6-port valve {ch}")

    def _auto_shutoff_valve(self, ch):
        """Auto-shutoff callback for 6-port valve safety timeout."""
        logger.warning(f"⚠️ SAFETY TIMEOUT: 6-port valve {ch} auto-shutoff after {self.VALVE_SAFETY_TIMEOUT_SECONDS}s")
        try:
            if self._ser is not None or self.open():
                cmd = f"v6{ch}0\n"
                self._ser.write(cmd.encode())
                self._ser.read()
                self._valve_six_state[ch] = 0
                logger.info(f"✓ KC{ch} 6-port valve auto-closed (LOAD position)")
        except Exception as e:
            logger.error(f"Error during auto-shutoff for valve {ch}: {e}")
        finally:
            with self._valve_six_lock:
                self._valve_six_timers[ch] = None

    def knx_six_state(self, ch):
        """Get current state of 6-port valve (0=load, 1=inject, None=unknown)."""
        return self._valve_six_state.get(ch)

    def knx_three_state(self, ch):
        """Get current state of 3-way valve (0=waste, 1=load, None=unknown)."""
        return self._valve_three_state.get(ch)

    def get_valve_cycles(self):
        """Get valve cycle counts (session + lifetime) for health monitoring."""
        return {
            "six_port_session": dict(self._valve_six_cycles_session),
            "three_way_session": dict(self._valve_three_cycles_session),
            "six_port_lifetime": dict(self._valve_six_cycles_lifetime),
            "three_way_lifetime": dict(self._valve_three_cycles_lifetime),
            "total_six_session": sum(self._valve_six_cycles_session.values()),
            "total_three_session": sum(self._valve_three_cycles_session.values()),
            "total_six_lifetime": sum(self._valve_six_cycles_lifetime.values()),
            "total_three_lifetime": sum(self._valve_three_cycles_lifetime.values()),
        }
