"""Kinetic Operations Manager - Handles pump control and kinetic experiments.

This class manages:
- Pump initialization and control
- Flow rate control
- Valve switching sequences
- Kinetic experiment protocols
- Pump state monitoring

All pump operations are coordinated to avoid conflicts.
"""

import time

from PySide6.QtCore import QObject, Signal

from utils.logger import logger


class KineticManager(QObject):
    """Manages pump control and kinetic operations."""

    # Signals for pump state
    pump_initialized = Signal()
    pump_error = Signal(str)  # Error message
    pump_state_changed = Signal(dict)  # {channel: str, running: bool, flow_rate: int}
    valve_switched = Signal(dict)  # {channel: str, position: str}

    def __init__(self, hardware_mgr):
        super().__init__()

        # Reference to hardware manager
        self.hardware_mgr = hardware_mgr

        # Pump state tracking
        self.pump_running = {ch: False for ch in ["a", "b", "c", "d"]}
        self.flow_rates = {ch: 0 for ch in ["a", "b", "c", "d"]}
        self.valve_positions = {ch: "unknown" for ch in ["a", "b", "c", "d"]}

        # Pump settings
        self.default_flow_rate = 100  # μL/min
        self.flush_rate = 500  # μL/min

        # Initialized silently

    def initialize_pump(self):
        """Initialize the pump system."""
        try:
            pump = self.hardware_mgr.pump
            if not pump:
                self.pump_error.emit("Pump not connected")
                return

            logger.info("Initializing pump...")

            # Reset pump
            pump.send_command(0x41, b"zR")
            time.sleep(0.1)

            # Set to 1.5 mL syringe
            pump.send_command(0x41, b"e15R")
            time.sleep(0.1)

            logger.info("✅ Pump initialized")
            self.pump_initialized.emit()

        except Exception as e:
            logger.exception(f"Failed to initialize pump: {e}")
            self.pump_error.emit(f"Pump initialization failed: {e}")

    def set_flow_rate(self, channel: str, flow_rate: int):
        """Set flow rate for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            flow_rate: Flow rate in μL/min

        """
        try:
            if channel not in ["a", "b", "c", "d"]:
                raise ValueError(f"Invalid channel: {channel}")

            self.flow_rates[channel] = flow_rate
            logger.info(f"Flow rate set for channel {channel}: {flow_rate} μL/min")

            # If pump is running, update immediately
            if self.pump_running[channel]:
                self.run_pump(channel, flow_rate)

        except Exception as e:
            logger.error(f"Failed to set flow rate: {e}")
            self.pump_error.emit(f"Failed to set flow rate: {e}")

    def run_pump(self, channel: str, flow_rate: int | None = None):
        """Start pump for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            flow_rate: Optional flow rate (uses stored rate if None)

        """
        try:
            pump = self.hardware_mgr.pump
            if not pump:
                self.pump_error.emit("Pump not connected")
                return

            if channel not in ["a", "b", "c", "d"]:
                raise ValueError(f"Invalid channel: {channel}")

            # Use stored flow rate if not provided
            if flow_rate is None:
                flow_rate = self.flow_rates.get(channel, self.default_flow_rate)
            else:
                self.flow_rates[channel] = flow_rate

            logger.info(f"Starting pump on channel {channel} at {flow_rate} μL/min")

            # Map channel to pump address
            # Assuming channels map to addresses (implementation specific)
            pump_address = self._channel_to_address(channel)

            # Set flow rate and start pump
            # Command format depends on pump protocol
            # Placeholder - actual implementation depends on pump API
            # pump.set_flow_rate(pump_address, flow_rate)
            # pump.start(pump_address)

            self.pump_running[channel] = True

            # Emit state change
            self.pump_state_changed.emit(
                {
                    "channel": channel,
                    "running": True,
                    "flow_rate": flow_rate,
                },
            )

        except Exception as e:
            logger.exception(f"Failed to start pump: {e}")
            self.pump_error.emit(f"Failed to start pump: {e}")

    def stop_pump(self, channel: str):
        """Stop pump for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        """
        try:
            pump = self.hardware_mgr.pump
            if not pump:
                return

            if channel not in ["a", "b", "c", "d"]:
                raise ValueError(f"Invalid channel: {channel}")

            logger.info(f"Stopping pump on channel {channel}")

            pump_address = self._channel_to_address(channel)

            # Stop pump
            # pump.stop(pump_address)

            self.pump_running[channel] = False

            # Emit state change
            self.pump_state_changed.emit(
                {
                    "channel": channel,
                    "running": False,
                    "flow_rate": 0,
                },
            )

        except Exception as e:
            logger.exception(f"Failed to stop pump: {e}")
            self.pump_error.emit(f"Failed to stop pump: {e}")

    def stop_all_pumps(self):
        """Stop all pumps."""
        logger.info("Stopping all pumps...")
        for ch in ["a", "b", "c", "d"]:
            if self.pump_running[ch]:
                self.stop_pump(ch)

    def switch_valve(self, channel: str, position: str):
        """Switch valve position for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            position: Valve position ('input', 'output', 'bypass', etc.)

        """
        try:
            pump = self.hardware_mgr.pump
            if not pump:
                self.pump_error.emit("Pump not connected")
                return

            if channel not in ["a", "b", "c", "d"]:
                raise ValueError(f"Invalid channel: {channel}")

            logger.info(f"Switching valve on channel {channel} to {position}")

            pump_address = self._channel_to_address(channel)

            # Switch valve
            # Implementation depends on pump API
            # pump.set_valve_position(pump_address, position)

            self.valve_positions[channel] = position

            # Emit valve change
            self.valve_switched.emit(
                {
                    "channel": channel,
                    "position": position,
                },
            )

        except Exception as e:
            logger.exception(f"Failed to switch valve: {e}")
            self.pump_error.emit(f"Failed to switch valve: {e}")

    def flush_channel(self, channel: str, duration: float = 10.0):
        """Flush a channel with high flow rate.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            duration: Flush duration in seconds

        """
        try:
            logger.info(
                f"Flushing channel {channel} for {duration}s at {self.flush_rate} μL/min",
            )

            # Start pump at flush rate
            self.run_pump(channel, self.flush_rate)

            # Schedule stop after duration
            from PySide6.QtCore import QTimer

            QTimer.singleShot(int(duration * 1000), lambda: self.stop_pump(channel))

        except Exception as e:
            logger.error(f"Failed to flush channel: {e}")
            self.pump_error.emit(f"Failed to flush channel: {e}")

    def _channel_to_address(self, channel: str) -> int:
        """Map channel letter to pump address.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        Returns:
            Pump address (implementation specific)

        """
        # Placeholder mapping
        mapping = {"a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44}
        return mapping.get(channel, 0x41)

    def get_pump_state(self) -> dict:
        """Get current pump state for all channels."""
        return {
            "running": self.pump_running.copy(),
            "flow_rates": self.flow_rates.copy(),
            "valve_positions": self.valve_positions.copy(),
        }

    def prime_pump(self, channel: str):
        """Prime the pump for a channel (fill tubing).

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        """
        try:
            logger.info(f"Priming pump for channel {channel}")

            # Run at high flow rate briefly
            self.run_pump(channel, self.flush_rate)

            # Stop after 5 seconds
            from PySide6.QtCore import QTimer

            QTimer.singleShot(5000, lambda: self.stop_pump(channel))

        except Exception as e:
            logger.error(f"Failed to prime pump: {e}")
            self.pump_error.emit(f"Failed to prime pump: {e}")
