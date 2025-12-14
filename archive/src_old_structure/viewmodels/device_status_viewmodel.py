"""Device Status View Model

Manages hardware device status and health monitoring.
Provides structured device state for UI display.

Integrates with Hardware Abstraction Layer (Phase 1.4):
- Uses DeviceManager for device coordination
- Bridges HAL events to Qt signals for UI
- Provides backward-compatible API for existing code
"""

from PySide6.QtCore import QObject, Signal
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

# Hardware Abstraction Layer imports
try:
    # Try relative import first (when running from project root)
    from hardware import (
        DeviceManager,
        SystemState,
        DeviceHealth,
        DeviceInfo,
        IController,
        ISpectrometer,
        IServo
    )
except ImportError:
    # Fall back to absolute import (when running from src directory)
    from src.hardware import (
        DeviceManager,
        SystemState,
        DeviceHealth,
        DeviceInfo,
        IController,
        ISpectrometer,
        IServo
    )

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Device connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class DeviceType(Enum):
    """Device types in the system."""
    CONTROLLER = "controller"
    SPECTROMETER = "spectrometer"
    SERVO = "servo"
    PUMP = "pump"


@dataclass
class DeviceStatus:
    """Status of a single device."""
    device_type: DeviceType
    connection_state: ConnectionState
    is_healthy: bool
    error_count: int = 0
    last_error: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None


class DeviceStatusViewModel(QObject):
    """View model for device status and health monitoring.

    Integrates Hardware Abstraction Layer (DeviceManager) with Qt UI signals.

    Responsibilities:
    - Track connection status for all devices
    - Monitor device health (error counts, timeouts)
    - Emit signals for status changes
    - Provide structured status data for UI
    - Bridge HAL DeviceManager to Qt signal/slot pattern

    Signals emitted:
    - device_connected: Device connected (device_type, serial_number)
    - device_disconnected: Device disconnected (device_type)
    - device_error: Device error occurred (device_type, error_message)
    - overall_status_changed: System-wide status changed (all_connected, all_healthy)
    - system_state_changed: HAL system state changed (state_name)
    """

    # Signals
    device_connected = Signal(str, str)  # device_type, serial_number
    device_disconnected = Signal(str)  # device_type
    device_error = Signal(str, str)  # device_type, error_message
    overall_status_changed = Signal(bool, bool)  # all_connected, all_healthy
    system_state_changed = Signal(str)  # system_state (from HAL)

    def __init__(self, device_manager: Optional[DeviceManager] = None):
        """Initialize device status view model.

        Args:
            device_manager: Optional DeviceManager instance (created if None)
        """
        super().__init__()

        # Hardware Abstraction Layer device manager
        self._device_manager = device_manager or DeviceManager()

        # Connect HAL callbacks to Qt signals
        self._setup_device_manager_callbacks()

        # Device status tracking (backward compatibility)
        self._device_status: Dict[DeviceType, DeviceStatus] = {}

        # Initialize all devices as disconnected
        for device_type in DeviceType:
            self._device_status[device_type] = DeviceStatus(
                device_type=device_type,
                connection_state=ConnectionState.DISCONNECTED,
                is_healthy=False
            )

    def update_device_status(
        self,
        device_type: DeviceType,
        connection_state: ConnectionState,
        is_healthy: bool = True,
        serial_number: Optional[str] = None,
        firmware_version: Optional[str] = None
    ):
        """Update device status.

        Args:
            device_type: Type of device
            connection_state: Current connection state
            is_healthy: Whether device is functioning properly
            serial_number: Device serial number (optional)
            firmware_version: Firmware version (optional)
        """
        status = self._device_status.get(device_type)
        if status is None:
            status = DeviceStatus(
                device_type=device_type,
                connection_state=connection_state,
                is_healthy=is_healthy,
                serial_number=serial_number,
                firmware_version=firmware_version
            )
            self._device_status[device_type] = status
        else:
            old_state = status.connection_state
            status.connection_state = connection_state
            status.is_healthy = is_healthy
            if serial_number:
                status.serial_number = serial_number
            if firmware_version:
                status.firmware_version = firmware_version

            # Emit connection signals
            if old_state != ConnectionState.CONNECTED and connection_state == ConnectionState.CONNECTED:
                self.device_connected.emit(device_type.value, serial_number or "unknown")
                logger.info(f"{device_type.value} connected: {serial_number}")
            elif old_state == ConnectionState.CONNECTED and connection_state != ConnectionState.CONNECTED:
                self.device_disconnected.emit(device_type.value)
                logger.warning(f"{device_type.value} disconnected")

        # Check overall status
        self._check_overall_status()

    def record_device_error(self, device_type: DeviceType, error_message: str):
        """Record device error.

        Args:
            device_type: Type of device
            error_message: Error description
        """
        status = self._device_status.get(device_type)
        if status:
            status.error_count += 1
            status.last_error = error_message
            status.is_healthy = False

            self.device_error.emit(device_type.value, error_message)
            logger.error(f"{device_type.value} error (count={status.error_count}): {error_message}")

            # Update overall status
            self._check_overall_status()

    def reset_device_errors(self, device_type: DeviceType):
        """Reset error count for device.

        Args:
            device_type: Type of device
        """
        status = self._device_status.get(device_type)
        if status:
            status.error_count = 0
            status.last_error = None
            status.is_healthy = True
            logger.debug(f"{device_type.value} errors reset")

            self._check_overall_status()

    def get_device_status(self, device_type: DeviceType) -> Optional[DeviceStatus]:
        """Get status for specific device.

        Args:
            device_type: Type of device

        Returns:
            DeviceStatus or None
        """
        return self._device_status.get(device_type)

    def is_device_connected(self, device_type: DeviceType) -> bool:
        """Check if device is connected.

        Args:
            device_type: Type of device

        Returns:
            True if connected
        """
        status = self._device_status.get(device_type)
        return status is not None and status.connection_state == ConnectionState.CONNECTED

    def is_device_healthy(self, device_type: DeviceType) -> bool:
        """Check if device is healthy.

        Args:
            device_type: Type of device

        Returns:
            True if healthy
        """
        status = self._device_status.get(device_type)
        return status is not None and status.is_healthy

    def are_all_devices_connected(self, required_devices=None) -> bool:
        """Check if all required devices are connected.

        Args:
            required_devices: List of required DeviceTypes (None = all)

        Returns:
            True if all required devices connected
        """
        if required_devices is None:
            required_devices = [DeviceType.CONTROLLER, DeviceType.SPECTROMETER]

        for device_type in required_devices:
            if not self.is_device_connected(device_type):
                return False
        return True

    def are_all_devices_healthy(self, required_devices=None) -> bool:
        """Check if all required devices are healthy.

        Args:
            required_devices: List of required DeviceTypes (None = all)

        Returns:
            True if all required devices healthy
        """
        if required_devices is None:
            required_devices = [DeviceType.CONTROLLER, DeviceType.SPECTROMETER]

        for device_type in required_devices:
            if not self.is_device_healthy(device_type):
                return False
        return True

    def get_system_status_summary(self) -> Dict:
        """Get overall system status summary.

        Returns:
            Dictionary with status information
        """
        connected_count = sum(
            1 for status in self._device_status.values()
            if status.connection_state == ConnectionState.CONNECTED
        )
        healthy_count = sum(
            1 for status in self._device_status.values()
            if status.is_healthy
        )
        total_errors = sum(
            status.error_count for status in self._device_status.values()
        )

        return {
            'connected_devices': connected_count,
            'total_devices': len(self._device_status),
            'healthy_devices': healthy_count,
            'total_errors': total_errors,
            'all_connected': connected_count == len(self._device_status),
            'all_healthy': healthy_count == len(self._device_status)
        }

    def get_device_list(self) -> Dict[str, DeviceStatus]:
        """Get all device statuses.

        Returns:
            Dictionary mapping device_type.value to DeviceStatus
        """
        return {
            device_type.value: status
            for device_type, status in self._device_status.items()
        }

    def _check_overall_status(self):
        """Check and emit overall system status."""
        required_devices = [DeviceType.CONTROLLER, DeviceType.SPECTROMETER]
        all_connected = self.are_all_devices_connected(required_devices)
        all_healthy = self.are_all_devices_healthy(required_devices)

        self.overall_status_changed.emit(all_connected, all_healthy)

    def reset_all(self):
        """Reset all device statuses to disconnected."""
        for device_type in DeviceType:
            self._device_status[device_type] = DeviceStatus(
                device_type=device_type,
                connection_state=ConnectionState.DISCONNECTED,
                is_healthy=False
            )
        logger.info("All device statuses reset")
        self._check_overall_status()

    # ========================================================================
    # HARDWARE ABSTRACTION LAYER INTEGRATION
    # ========================================================================

    def _setup_device_manager_callbacks(self):
        """Connect DeviceManager callbacks to Qt signals."""
        self._device_manager.set_on_state_changed(self._on_hal_state_changed)
        self._device_manager.set_on_device_connected(self._on_hal_device_connected)
        self._device_manager.set_on_device_disconnected(self._on_hal_device_disconnected)
        self._device_manager.set_on_error(self._on_hal_error)
        logger.debug("DeviceManager callbacks connected")

    def _on_hal_state_changed(self, state: SystemState):
        """Handle HAL system state changes.

        Args:
            state: New SystemState from DeviceManager
        """
        logger.info(f"HAL system state changed: {state.value}")
        self.system_state_changed.emit(state.value)

        # Update overall status based on HAL state
        if state == SystemState.CONNECTED:
            self.overall_status_changed.emit(True, True)
        elif state == SystemState.DISCONNECTED:
            self.overall_status_changed.emit(False, False)
        elif state == SystemState.PARTIAL:
            self.overall_status_changed.emit(False, False)

    def _on_hal_device_connected(self, device_type_str: str, info: DeviceInfo):
        """Handle HAL device connection.

        Args:
            device_type_str: Device type string ("controller", "spectrometer", etc.)
            info: DeviceInfo from HAL
        """
        # Map HAL device type to viewmodel DeviceType
        device_type_map = {
            'controller': DeviceType.CONTROLLER,
            'spectrometer': DeviceType.SPECTROMETER,
            'servo': DeviceType.SERVO,
            'pump': DeviceType.PUMP
        }

        device_type = device_type_map.get(device_type_str)
        if device_type:
            # Update internal status
            self.update_device_status(
                device_type=device_type,
                connection_state=ConnectionState.CONNECTED,
                is_healthy=True,
                serial_number=info.serial_number,
                firmware_version=info.firmware_version
            )

            logger.info(f"HAL device connected: {device_type_str} ({info.model})")

    def _on_hal_device_disconnected(self, device_type_str: str):
        """Handle HAL device disconnection.

        Args:
            device_type_str: Device type string
        """
        device_type_map = {
            'controller': DeviceType.CONTROLLER,
            'spectrometer': DeviceType.SPECTROMETER,
            'servo': DeviceType.SERVO,
            'pump': DeviceType.PUMP
        }

        device_type = device_type_map.get(device_type_str)
        if device_type:
            self.update_device_status(
                device_type=device_type,
                connection_state=ConnectionState.DISCONNECTED,
                is_healthy=False
            )

            logger.warning(f"HAL device disconnected: {device_type_str}")

    def _on_hal_error(self, device_type_str: str, error: str):
        """Handle HAL device error.

        Args:
            device_type_str: Device type string
            error: Error message
        """
        device_type_map = {
            'controller': DeviceType.CONTROLLER,
            'spectrometer': DeviceType.SPECTROMETER,
            'servo': DeviceType.SERVO,
            'pump': DeviceType.PUMP,
            'system': None  # System-wide errors
        }

        device_type = device_type_map.get(device_type_str)
        if device_type:
            self.record_device_error(device_type, error)
        else:
            logger.error(f"HAL system error: {error}")

    # ========================================================================
    # DEVICE MANAGER ACCESS (HAL)
    # ========================================================================

    @property
    def device_manager(self) -> DeviceManager:
        """Get underlying DeviceManager (HAL).

        Provides direct access to Hardware Abstraction Layer for:
        - Registering devices
        - Connecting/disconnecting
        - Health monitoring
        - Auto-reconnection

        Returns:
            DeviceManager instance
        """
        return self._device_manager

    def register_controller(self, controller: IController):
        """Register controller with device manager.

        Args:
            controller: IController implementation (real or mock)
        """
        self._device_manager.register_controller(controller)
        logger.debug("Controller registered with DeviceManager")

    def register_spectrometer(self, spectrometer: ISpectrometer):
        """Register spectrometer with device manager.

        Args:
            spectrometer: ISpectrometer implementation (real or mock)
        """
        self._device_manager.register_spectrometer(spectrometer)
        logger.debug("Spectrometer registered with DeviceManager")

    def register_servo(self, servo: IServo):
        """Register servo with device manager.

        Args:
            servo: IServo implementation (real or mock)
        """
        self._device_manager.register_servo(servo)
        logger.debug("Servo registered with DeviceManager")

    def connect_all_devices(
        self,
        require_controller: bool = True,
        require_spectrometer: bool = True,
        require_servo: bool = False
    ) -> bool:
        """Connect all registered devices via DeviceManager.

        Args:
            require_controller: Fail if controller connection fails
            require_spectrometer: Fail if spectrometer connection fails
            require_servo: Fail if servo connection fails

        Returns:
            True if all required devices connected
        """
        logger.info("Connecting all devices via DeviceManager...")
        success = self._device_manager.connect_all(
            require_controller=require_controller,
            require_spectrometer=require_spectrometer,
            require_servo=require_servo
        )
        logger.info(f"Device connection result: {success}")
        return success

    def disconnect_all_devices(self):
        """Disconnect all devices via DeviceManager."""
        logger.info("Disconnecting all devices via DeviceManager...")
        self._device_manager.disconnect_all()

    def start_auto_reconnect(self, interval: float = 5.0):
        """Start automatic device reconnection monitoring.

        Args:
            interval: Check interval in seconds
        """
        self._device_manager.start_auto_reconnect(interval=interval)
        logger.info(f"Auto-reconnect started (interval={interval}s)")

    def stop_auto_reconnect(self):
        """Stop automatic device reconnection monitoring."""
        self._device_manager.stop_auto_reconnect()
        logger.info("Auto-reconnect stopped")

    def get_controller(self) -> Optional[IController]:
        """Get controller device from DeviceManager.

        Returns:
            IController or None
        """
        return self._device_manager.controller

    def get_spectrometer(self) -> Optional[ISpectrometer]:
        """Get spectrometer device from DeviceManager.

        Returns:
            ISpectrometer or None
        """
        return self._device_manager.spectrometer

    def get_servo(self) -> Optional[IServo]:
        """Get servo device from DeviceManager.

        Returns:
            IServo or None
        """
        return self._device_manager.servo

    def check_device_health(self):
        """Actively check health of all devices and update status."""
        health = self._device_manager.check_health()

        # Update internal status based on health check
        if health.controller:
            device_type = DeviceType.CONTROLLER
            state = ConnectionState.CONNECTED if health.controller.connected else ConnectionState.DISCONNECTED
            self.update_device_status(
                device_type=device_type,
                connection_state=state,
                is_healthy=health.controller.responsive
            )

        if health.spectrometer:
            device_type = DeviceType.SPECTROMETER
            state = ConnectionState.CONNECTED if health.spectrometer.connected else ConnectionState.DISCONNECTED
            self.update_device_status(
                device_type=device_type,
                connection_state=state,
                is_healthy=health.spectrometer.responsive
            )

        if health.servo:
            device_type = DeviceType.SERVO
            state = ConnectionState.CONNECTED if health.servo.connected else ConnectionState.DISCONNECTED
            self.update_device_status(
                device_type=device_type,
                connection_state=state,
                is_healthy=health.servo.responsive
            )

        logger.debug(f"Health check complete - Ready: {health.is_ready()}, Healthy: {health.all_healthy()}")
