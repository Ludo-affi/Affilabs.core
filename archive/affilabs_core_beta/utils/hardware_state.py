"""Hardware state management for SPR device.

This module provides a HardwareStateManager class that centralizes all
hardware state information including LED calibration, pump/valve states,
temperature readings, and synchronization status.

Features:
- Centralized state management
- Validation on state updates
- State change callbacks for UI synchronization
- Thread-safe state access
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


class HardwareStateManager:
    """Manages all hardware state and configurations.

    This class centralizes hardware state management, making it easier to
    track, update, and test hardware-related functionality independently
    from UI logic.

    Thread-safe: All state updates are protected by locks.
    """

    def __init__(self: HardwareStateManager) -> None:
        """Initialize hardware state manager with default values."""
        # Thread safety
        self._lock = Lock()

        # State change callbacks
        self._callbacks: dict[str, list[Callable]] = {
            "led_changed": [],
            "pump_changed": [],
            "valve_changed": [],
            "temp_changed": [],
        }

        # LED calibration states
        self.leds_calibrated: dict[str, int] = {
            "a": 170,
            "b": 170,
            "c": 170,
            "d": 170,
        }

        # LED reference intensities
        self.ref_intensity: dict[str, int] = {
            "a": 170,
            "b": 170,
            "c": 170,
            "d": 170,
        }

        # Pump states for each channel
        self.pump_states: dict[str, Literal["Off", "On"]] = {
            "CH1": "Off",
            "CH2": "Off",
        }

        # Valve states for each channel
        self.valve_states: dict[str, Literal["Waste", "Inject"]] = {
            "CH1": "Waste",
            "CH2": "Waste",
        }

        # Temperature monitoring
        self.temp: float = 0.0

        # Synchronization status
        self.synced: bool = False

    def register_callback(
        self: HardwareStateManager,
        event_type: str,
        callback: Callable,
    ) -> None:
        """Register a callback for state change events.

        Args:
            event_type: Type of event ('led_changed', 'pump_changed', etc.)
            callback: Function to call when state changes

        """
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    def _notify_callbacks(
        self: HardwareStateManager,
        event_type: str,
        **kwargs,
    ) -> None:
        """Notify all registered callbacks of a state change.

        Args:
            event_type: Type of event that occurred
            **kwargs: Additional data to pass to callbacks

        """
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(**kwargs)
            except Exception:
                pass  # Don't let callback errors propagate

    def update_led_calibration(
        self: HardwareStateManager,
        channel: str,
        intensity: int,
    ) -> None:
        """Update LED calibration intensity for a specific channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            intensity: LED intensity value (0-255)

        Raises:
            ValueError: If channel is invalid or intensity out of range

        """
        if channel not in self.leds_calibrated:
            msg = f"Invalid channel: {channel}"
            raise ValueError(msg)

        if not 0 <= intensity <= 255:
            msg = f"Invalid intensity: {intensity} (must be 0-255)"
            raise ValueError(msg)

        with self._lock:
            old_value = self.leds_calibrated[channel]
            self.leds_calibrated[channel] = intensity

        # Notify callbacks if value changed
        if old_value != intensity:
            self._notify_callbacks("led_changed", channel=channel, intensity=intensity)

    def update_ref_intensity(
        self: HardwareStateManager,
        channel: str,
        intensity: int,
    ) -> None:
        """Update LED reference intensity for a specific channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            intensity: Reference intensity value (0-255)

        Raises:
            ValueError: If channel is invalid or intensity out of range

        """
        if channel not in self.ref_intensity:
            msg = f"Invalid channel: {channel}"
            raise ValueError(msg)

        if not 0 <= intensity <= 255:
            msg = f"Invalid intensity: {intensity} (must be 0-255)"
            raise ValueError(msg)

        with self._lock:
            self.ref_intensity[channel] = intensity

    def update_pump_state(
        self: HardwareStateManager,
        channel: str,
        state: Literal["Off", "On"],
    ) -> None:
        """Update pump state for a specific channel.

        Args:
            channel: Channel identifier ('CH1', 'CH2')
            state: Pump state ('Off' or 'On')

        """
        if channel in self.pump_states:
            self.pump_states[channel] = state
        else:
            msg = f"Invalid pump channel: {channel}"
            raise ValueError(msg)

    def update_valve_state(
        self: HardwareStateManager,
        channel: str,
        state: Literal["Waste", "Inject"],
    ) -> None:
        """Update valve state for a specific channel.

        Args:
            channel: Channel identifier ('CH1', 'CH2')
            state: Valve state ('Waste' or 'Inject')

        """
        if channel in self.valve_states:
            self.valve_states[channel] = state
        else:
            msg = f"Invalid valve channel: {channel}"
            raise ValueError(msg)

    def update_temperature(
        self: HardwareStateManager,
        temp: float,
    ) -> None:
        """Update temperature reading.

        Args:
            temp: Temperature value in degrees Celsius

        """
        self.temp = temp

    def set_synced(
        self: HardwareStateManager,
        synced: bool,
    ) -> None:
        """Update synchronization status.

        Args:
            synced: Whether pumps are synchronized

        """
        self.synced = synced

    def get_led_intensity(
        self: HardwareStateManager,
        channel: str,
    ) -> int:
        """Get current LED calibration intensity for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        Returns:
            int: Current LED intensity value

        """
        if channel in self.leds_calibrated:
            return self.leds_calibrated[channel]
        msg = f"Invalid channel: {channel}"
        raise ValueError(msg)

    def get_ref_intensity(
        self: HardwareStateManager,
        channel: str,
    ) -> int:
        """Get reference LED intensity for a channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        Returns:
            int: Reference LED intensity value

        """
        if channel in self.ref_intensity:
            return self.ref_intensity[channel]
        msg = f"Invalid channel: {channel}"
        raise ValueError(msg)

    def reset_led_calibration(self: HardwareStateManager) -> None:
        """Reset all LED calibration values to default (170)."""
        for channel in self.leds_calibrated:
            self.leds_calibrated[channel] = 170
            self.ref_intensity[channel] = 170

    def reset_pump_states(self: HardwareStateManager) -> None:
        """Reset all pump states to Off."""
        for channel in self.pump_states:
            self.pump_states[channel] = "Off"

    def reset_valve_states(self: HardwareStateManager) -> None:
        """Reset all valve states to Waste."""
        for channel in self.valve_states:
            self.valve_states[channel] = "Waste"

    def get_all_states(self: HardwareStateManager) -> dict:
        """Get a snapshot of all hardware states.

        Returns:
            dict: Dictionary containing all current hardware states

        """
        return {
            "leds_calibrated": self.leds_calibrated.copy(),
            "ref_intensity": self.ref_intensity.copy(),
            "pump_states": self.pump_states.copy(),
            "valve_states": self.valve_states.copy(),
            "temp": self.temp,
            "synced": self.synced,
        }
