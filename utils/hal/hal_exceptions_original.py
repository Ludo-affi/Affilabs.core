"""Hardware Abstraction Layer (HAL) Exception Classes

Custom exceptions for HAL operations with specific error types
for better error handling and debugging.
"""

from typing import Any


class HALError(Exception):
    """Base exception for all HAL-related errors."""

    def __init__(self, message: str, device_info=None) -> None:
        """Initialize HAL error.

        Args:
            message: Error description
            device_info: Optional device information for debugging

        """
        super().__init__(message)
        self.device_info = device_info or {}


class HALConnectionError(HALError):
    """Raised when device connection fails or is lost."""

    def __init__(
        self,
        message: str,
        port=None,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize connection error.

        Args:
            message: Error description
            port: Port/address where connection failed
            device_info: Optional device information

        """
        super().__init__(message, device_info)
        self.port = port


class HALTimeoutError(HALError):
    """Raised when device operations timeout."""

    def __init__(
        self,
        message: str,
        timeout_duration: float | None = None,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize timeout error.

        Args:
            message: Error description
            timeout_duration: Duration of timeout in seconds
            device_info: Optional device information

        """
        super().__init__(message, device_info)
        self.timeout_duration = timeout_duration


class HALConfigurationError(HALError):
    """Raised when device configuration is invalid or fails."""

    def __init__(
        self,
        message: str,
        invalid_config: dict[str, Any] | None = None,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize configuration error.

        Args:
            message: Error description
            invalid_config: Configuration that caused the error
            device_info: Optional device information

        """
        super().__init__(message, device_info)
        self.invalid_config = invalid_config or {}


class HALDeviceNotFoundError(HALConnectionError):
    """Raised when expected device cannot be found or identified."""


class HALIncompatibleDeviceError(HALError):
    """Raised when device is detected but incompatible with the HAL implementation."""

    def __init__(
        self,
        message: str,
        expected_device: str,
        detected_device=None,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize incompatible device error.

        Args:
            message: Error description
            expected_device: Expected device type/model
            detected_device: Detected device type/model
            device_info: Optional device information

        """
        super().__init__(message, device_info)
        self.expected_device = expected_device
        self.detected_device = detected_device


class HALOperationError(HALError):
    """Raised when a device operation fails."""

    def __init__(
        self, message: str, operation: str, device_info: dict[str, Any] | None = None
    ) -> None:
        """Initialize operation error.

        Args:
            message: Error description
            operation: Name of the operation that failed
            device_info: Optional device information

        """
        super().__init__(message, device_info)
        self.operation = operation
