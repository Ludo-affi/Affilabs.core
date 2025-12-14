"""
Device Status Models

Pure Python data structures for hardware status.
NO Qt dependencies - fully testable.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class DeviceType(Enum):
    """Type of hardware device."""
    CONTROLLER = "controller"  # PicoP4SPR controller
    SPECTROMETER = "spectrometer"  # FLMT09116 spectrometer
    SERVO = "servo"  # Polarizer servo motor


class ConnectionState(Enum):
    """Connection state of a device."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class DeviceStatus:
    """Status information for a hardware device.

    Tracks connection state, errors, and health metrics.
    """
    device_type: DeviceType
    state: ConnectionState

    # Connection info
    port: Optional[str] = None  # COM port or USB address
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None

    # Health metrics
    last_seen: float = field(default_factory=lambda: datetime.now().timestamp())
    error_count: int = 0
    consecutive_errors: int = 0
    last_error: Optional[str] = None

    # Performance
    response_time_ms: float = 0.0  # Last command response time
    uptime_seconds: float = 0.0  # Time since connection

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.state == ConnectionState.CONNECTED

    @property
    def is_healthy(self) -> bool:
        """Check if device is healthy (connected with low error rate)."""
        return (
            self.state == ConnectionState.CONNECTED and
            self.consecutive_errors < 5
        )

    @property
    def last_seen_datetime(self) -> datetime:
        """Last seen timestamp as datetime."""
        return datetime.fromtimestamp(self.last_seen)

    @property
    def time_since_last_seen(self) -> float:
        """Seconds since last communication."""
        return datetime.now().timestamp() - self.last_seen

    def is_responsive(self, timeout_seconds: float = 5.0) -> bool:
        """Check if device has responded recently."""
        return self.time_since_last_seen < timeout_seconds

    def record_success(self):
        """Record successful communication."""
        self.last_seen = datetime.now().timestamp()
        self.consecutive_errors = 0

    def record_error(self, error_message: str):
        """Record communication error."""
        self.last_seen = datetime.now().timestamp()
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_error = error_message

        if self.consecutive_errors >= 5:
            self.state = ConnectionState.ERROR

    def reset_errors(self):
        """Reset error counters (after successful recovery)."""
        self.consecutive_errors = 0
        self.last_error = None
        if self.state == ConnectionState.ERROR:
            self.state = ConnectionState.CONNECTED

    def copy(self) -> 'DeviceStatus':
        """Create a copy of device status."""
        return DeviceStatus(
            device_type=self.device_type,
            state=self.state,
            port=self.port,
            serial_number=self.serial_number,
            firmware_version=self.firmware_version,
            last_seen=self.last_seen,
            error_count=self.error_count,
            consecutive_errors=self.consecutive_errors,
            last_error=self.last_error,
            response_time_ms=self.response_time_ms,
            uptime_seconds=self.uptime_seconds,
            metadata=self.metadata.copy()
        )


@dataclass
class SystemStatus:
    """Overall system status (all devices).

    Provides a unified view of hardware health.
    """
    controller: Optional[DeviceStatus] = None
    spectrometer: Optional[DeviceStatus] = None
    servo: Optional[DeviceStatus] = None

    @property
    def all_connected(self) -> bool:
        """Check if all devices are connected."""
        return (
            self.controller is not None and self.controller.is_connected and
            self.spectrometer is not None and self.spectrometer.is_connected
        )

    @property
    def all_healthy(self) -> bool:
        """Check if all devices are healthy."""
        devices = [self.controller, self.spectrometer, self.servo]
        active_devices = [d for d in devices if d is not None]
        return all(d.is_healthy for d in active_devices)

    @property
    def has_errors(self) -> bool:
        """Check if any device has errors."""
        devices = [self.controller, self.spectrometer, self.servo]
        active_devices = [d for d in devices if d is not None]
        return any(d.consecutive_errors > 0 for d in active_devices)

    def get_error_summary(self) -> str:
        """Get summary of all device errors."""
        errors = []
        if self.controller and self.controller.last_error:
            errors.append(f"Controller: {self.controller.last_error}")
        if self.spectrometer and self.spectrometer.last_error:
            errors.append(f"Spectrometer: {self.spectrometer.last_error}")
        if self.servo and self.servo.last_error:
            errors.append(f"Servo: {self.servo.last_error}")

        return "; ".join(errors) if errors else "No errors"

    def copy(self) -> 'SystemStatus':
        """Create a copy of system status."""
        return SystemStatus(
            controller=self.controller.copy() if self.controller else None,
            spectrometer=self.spectrometer.copy() if self.spectrometer else None,
            servo=self.servo.copy() if self.servo else None
        )
