"""Hardware Abstraction Layer (HAL) Exception Classes - Python 3.9 Compatible

Custom exceptions for HAL operations with basic types for compatibility.
"""


class HALError(Exception):
    """Base class for all HAL-related exceptions."""

    def __init__(self, message: str, device_info=None) -> None:
        """Initialize HAL error with message and optional device info."""
        super().__init__(message)
        self.device_info = device_info


class HALConnectionError(HALError):
    """Exception raised when device connection fails."""

    def __init__(
        self,
        message: str,
        port=None,
        device_info=None,
        timeout=None,
    ) -> None:
        """Initialize connection error with connection details."""
        super().__init__(message, device_info)
        self.port = port
        self.timeout = timeout


class HALCommunicationError(HALError):
    """Exception raised when device communication fails."""

    def __init__(
        self,
        message: str,
        command: str = "",
        response: str = "",
        device_info=None,
    ) -> None:
        """Initialize communication error with command/response details."""
        super().__init__(message, device_info)
        self.command = command
        self.response = response


class HALConfigurationError(HALError):
    """Exception raised when device configuration is invalid."""

    def __init__(
        self,
        message: str,
        invalid_config=None,
        device_info=None,
    ) -> None:
        """Initialize configuration error with invalid config details."""
        super().__init__(message, device_info)
        self.invalid_config = invalid_config


class HALDeviceNotFoundError(HALError):
    """Exception raised when required device is not found."""

    def __init__(
        self,
        message: str,
        expected_device: str,
        detected_device=None,
        device_info=None,
    ) -> None:
        """Initialize device not found error with device details."""
        super().__init__(message, device_info)
        self.expected_device = expected_device
        self.detected_device = detected_device


class HALOperationError(HALError):
    """Exception raised when device operation fails."""

    def __init__(
        self,
        message: str,
        operation: str,
        device_info=None,
    ) -> None:
        """Initialize operation error with operation details."""
        super().__init__(message, device_info)
        self.operation = operation


class HALTimeoutError(HALError):
    """Exception raised when device operation times out."""

    def __init__(
        self,
        message: str,
        timeout_duration=None,
        device_info=None,
    ) -> None:
        """Initialize timeout error with timeout details."""
        super().__init__(message, device_info)
        self.timeout_duration = timeout_duration


class HALIncompatibleDeviceError(HALError):
    """Exception raised when device is incompatible."""

    def __init__(
        self,
        message: str,
        expected_type=None,
        actual_type=None,
        device_info=None,
    ) -> None:
        """Initialize incompatible device error with type details."""
        super().__init__(message, device_info)
        self.expected_type = expected_type
        self.actual_type = actual_type


# Legacy aliases for backward compatibility
HalError = HALError
HalConnectionError = HALConnectionError
HalCommunicationError = HALCommunicationError
HalConfigurationError = HALConfigurationError
HalDeviceNotFoundError = HALDeviceNotFoundError
HalOperationError = HALOperationError
HalTimeoutError = HALTimeoutError
HalIncompatibleDeviceError = HALIncompatibleDeviceError
