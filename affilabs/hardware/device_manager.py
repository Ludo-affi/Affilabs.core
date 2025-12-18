"""Device Manager

Coordinates multiple hardware devices with lifecycle management, health monitoring,
and automatic reconnection.

Provides high-level device orchestration:
- Connect/disconnect all devices
- Health monitoring
- Automatic reconnection on failure
- Device discovery
- Synchronized state management
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .device_interface import (
    DeviceInfo,
    IController,
    IServo,
    ISpectrometer,
)

# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================


class SystemState(Enum):
    """Overall system state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PARTIAL = "partial"  # Some devices connected
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class DeviceHealth:
    """Health status for a device."""

    device_type: str  # "controller", "spectrometer", "servo"
    connected: bool
    responsive: bool
    error_count: int = 0
    last_error: str | None = None
    info: DeviceInfo | None = None


@dataclass
class SystemHealth:
    """Overall system health."""

    state: SystemState
    controller: DeviceHealth | None = None
    spectrometer: DeviceHealth | None = None
    servo: DeviceHealth | None = None

    def is_ready(self) -> bool:
        """Check if system is ready for operation."""
        return (
            self.controller
            and self.controller.connected
            and self.spectrometer
            and self.spectrometer.connected
        )

    def all_healthy(self) -> bool:
        """Check if all connected devices are healthy."""
        devices = [self.controller, self.spectrometer, self.servo]
        connected_devices = [d for d in devices if d and d.connected]
        return all(d.responsive and d.error_count == 0 for d in connected_devices)


# ============================================================================
# DEVICE MANAGER
# ============================================================================


class DeviceManager:
    """Manages lifecycle of multiple hardware devices.

    Features:
    - Centralized device coordination
    - Health monitoring
    - Automatic reconnection
    - Thread-safe operations
    - Event callbacks for status changes
    """

    def __init__(self):
        """Initialize device manager."""
        # Device references
        self._controller: IController | None = None
        self._spectrometer: ISpectrometer | None = None
        self._servo: IServo | None = None

        # State
        self._state = SystemState.DISCONNECTED
        self._lock = threading.RLock()

        # Health tracking
        self._controller_health = DeviceHealth("controller", False, False)
        self._spectrometer_health = DeviceHealth("spectrometer", False, False)
        self._servo_health = DeviceHealth("servo", False, False)

        # Reconnection
        self._auto_reconnect = False
        self._reconnect_thread: threading.Thread | None = None
        self._stop_reconnect = threading.Event()

        # Callbacks
        self._on_state_changed: Callable[[SystemState], None] | None = None
        self._on_device_connected: Callable[[str, DeviceInfo], None] | None = None
        self._on_device_disconnected: Callable[[str], None] | None = None
        self._on_error: Callable[[str, str], None] | None = None

    # ========================================================================
    # DEVICE REGISTRATION
    # ========================================================================

    def register_controller(self, controller: IController) -> None:
        """Register controller device.

        Args:
            controller: Controller implementation (real or mock)

        """
        with self._lock:
            self._controller = controller

    def register_spectrometer(self, spectrometer: ISpectrometer) -> None:
        """Register spectrometer device.

        Args:
            spectrometer: Spectrometer implementation (real or mock)

        """
        with self._lock:
            self._spectrometer = spectrometer

    def register_servo(self, servo: IServo) -> None:
        """Register servo device.

        Args:
            servo: Servo implementation (real or mock)

        """
        with self._lock:
            self._servo = servo

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect_all(
        self,
        require_controller: bool = True,
        require_spectrometer: bool = True,
        require_servo: bool = False,
    ) -> bool:
        """Connect all registered devices.

        Args:
            require_controller: Fail if controller connection fails
            require_spectrometer: Fail if spectrometer connection fails
            require_servo: Fail if servo connection fails

        Returns:
            True if all required devices connected successfully

        """
        with self._lock:
            self._set_state(SystemState.CONNECTING)

            success = True

            # Connect controller
            if self._controller:
                try:
                    if self._controller.connect():
                        self._controller_health.connected = True
                        self._controller_health.responsive = True
                        self._controller_health.info = self._controller.get_info()
                        self._notify_device_connected(
                            "controller",
                            self._controller_health.info,
                        )
                    elif require_controller:
                        success = False
                        self._handle_error("controller", "Connection failed")
                except Exception as e:
                    if require_controller:
                        success = False
                    self._handle_error("controller", str(e))
            elif require_controller:
                success = False

            # Connect spectrometer
            if self._spectrometer:
                try:
                    if self._spectrometer.connect():
                        self._spectrometer_health.connected = True
                        self._spectrometer_health.responsive = True
                        self._spectrometer_health.info = self._spectrometer.get_info()
                        self._notify_device_connected(
                            "spectrometer",
                            self._spectrometer_health.info,
                        )
                    elif require_spectrometer:
                        success = False
                        self._handle_error("spectrometer", "Connection failed")
                except Exception as e:
                    if require_spectrometer:
                        success = False
                    self._handle_error("spectrometer", str(e))
            elif require_spectrometer:
                success = False

            # Connect servo (requires controller)
            if self._servo and self._controller and self._controller_health.connected:
                try:
                    if self._servo.connect(self._controller):
                        self._servo_health.connected = True
                        self._servo_health.responsive = True
                        self._servo_health.info = self._servo.get_info()
                        self._notify_device_connected("servo", self._servo_health.info)
                    elif require_servo:
                        success = False
                        self._handle_error("servo", "Connection failed")
                except Exception as e:
                    if require_servo:
                        success = False
                    self._handle_error("servo", str(e))
            elif require_servo:
                success = False

            # Update state
            if success:
                self._set_state(SystemState.CONNECTED)
            else:
                # Check if any devices connected
                any_connected = (
                    self._controller_health.connected
                    or self._spectrometer_health.connected
                    or self._servo_health.connected
                )
                self._set_state(
                    SystemState.PARTIAL if any_connected else SystemState.ERROR,
                )

            return success

    def disconnect_all(self) -> None:
        """Disconnect all devices."""
        with self._lock:
            # Stop auto-reconnect
            self.stop_auto_reconnect()

            # Disconnect servo first (depends on controller)
            if self._servo:
                try:
                    self._servo.disconnect()
                    self._servo_health.connected = False
                    self._notify_device_disconnected("servo")
                except Exception:
                    pass

            # Disconnect controller
            if self._controller:
                try:
                    self._controller.disconnect()
                    self._controller_health.connected = False
                    self._notify_device_disconnected("controller")
                except Exception:
                    pass

            # Disconnect spectrometer
            if self._spectrometer:
                try:
                    self._spectrometer.disconnect()
                    self._spectrometer_health.connected = False
                    self._notify_device_disconnected("spectrometer")
                except Exception:
                    pass

            self._set_state(SystemState.DISCONNECTED)

    # ========================================================================
    # HEALTH MONITORING
    # ========================================================================

    def get_health(self) -> SystemHealth:
        """Get current system health status.

        Returns:
            SystemHealth with status of all devices

        """
        with self._lock:
            return SystemHealth(
                state=self._state,
                controller=self._controller_health,
                spectrometer=self._spectrometer_health,
                servo=self._servo_health,
            )

    def check_health(self) -> SystemHealth:
        """Actively check health of all connected devices.

        Tests each device's responsiveness and updates health status.
        """
        with self._lock:
            # Check controller
            if self._controller and self._controller_health.connected:
                try:
                    self._controller_health.responsive = self._controller.is_connected()
                except Exception as e:
                    self._controller_health.responsive = False
                    self._handle_error("controller", str(e))

            # Check spectrometer
            if self._spectrometer and self._spectrometer_health.connected:
                try:
                    self._spectrometer_health.responsive = self._spectrometer.is_connected()
                except Exception as e:
                    self._spectrometer_health.responsive = False
                    self._handle_error("spectrometer", str(e))

            # Check servo
            if self._servo and self._servo_health.connected:
                try:
                    self._servo_health.responsive = self._servo.is_connected()
                except Exception as e:
                    self._servo_health.responsive = False
                    self._handle_error("servo", str(e))

            return self.get_health()

    # ========================================================================
    # AUTO-RECONNECTION
    # ========================================================================

    def start_auto_reconnect(self, interval: float = 5.0) -> None:
        """Start automatic reconnection monitoring.

        Args:
            interval: Check interval in seconds

        """
        if self._auto_reconnect:
            return

        self._auto_reconnect = True
        self._stop_reconnect.clear()

        def reconnect_loop():
            while not self._stop_reconnect.is_set():
                time.sleep(interval)

                if self._stop_reconnect.is_set():
                    break

                # Check health
                health = self.check_health()

                # Attempt reconnection if needed
                if not health.is_ready():
                    with self._lock:
                        self._set_state(SystemState.RECONNECTING)

                    try:
                        self.connect_all(
                            require_controller=True,
                            require_spectrometer=True,
                            require_servo=False,
                        )
                    except Exception as e:
                        self._handle_error("system", f"Reconnection failed: {e}")

        self._reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def stop_auto_reconnect(self) -> None:
        """Stop automatic reconnection monitoring."""
        if not self._auto_reconnect:
            return

        self._auto_reconnect = False
        self._stop_reconnect.set()

        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2.0)
            self._reconnect_thread = None

    # ========================================================================
    # DEVICE ACCESS
    # ========================================================================

    @property
    def controller(self) -> IController | None:
        """Get controller device."""
        return self._controller

    @property
    def spectrometer(self) -> ISpectrometer | None:
        """Get spectrometer device."""
        return self._spectrometer

    @property
    def servo(self) -> IServo | None:
        """Get servo device."""
        return self._servo

    @property
    def state(self) -> SystemState:
        """Get current system state."""
        return self._state

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    def set_on_state_changed(self, callback: Callable[[SystemState], None]) -> None:
        """Set callback for state changes."""
        self._on_state_changed = callback

    def set_on_device_connected(
        self,
        callback: Callable[[str, DeviceInfo], None],
    ) -> None:
        """Set callback for device connections."""
        self._on_device_connected = callback

    def set_on_device_disconnected(self, callback: Callable[[str], None]) -> None:
        """Set callback for device disconnections."""
        self._on_device_disconnected = callback

    def set_on_error(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _set_state(self, new_state: SystemState) -> None:
        """Update system state and notify."""
        if self._state != new_state:
            self._state = new_state
            if self._on_state_changed:
                try:
                    self._on_state_changed(new_state)
                except Exception:
                    pass

    def _notify_device_connected(self, device_type: str, info: DeviceInfo) -> None:
        """Notify device connected."""
        if self._on_device_connected:
            try:
                self._on_device_connected(device_type, info)
            except Exception:
                pass

    def _notify_device_disconnected(self, device_type: str) -> None:
        """Notify device disconnected."""
        if self._on_device_disconnected:
            try:
                self._on_device_disconnected(device_type)
            except Exception:
                pass

    def _handle_error(self, device_type: str, error: str) -> None:
        """Handle device error."""
        # Update health
        if device_type == "controller":
            self._controller_health.error_count += 1
            self._controller_health.last_error = error
        elif device_type == "spectrometer":
            self._spectrometer_health.error_count += 1
            self._spectrometer_health.last_error = error
        elif device_type == "servo":
            self._servo_health.error_count += 1
            self._servo_health.last_error = error

        # Notify
        if self._on_error:
            try:
                self._on_error(device_type, error)
            except Exception:
                pass
