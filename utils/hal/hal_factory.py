"""Hardware Abstraction Layer Factory

Provides factory methods for creating appropriate HAL implementations
based on device detection, configuration, or user preferences.
"""

from __future__ import annotations

from typing import Any

from utils.logger import logger

# Import USB4000 implementation from utils module
from ..usb4000_oceandirect import USB4000OceanDirect
from .hal_exceptions import HALDeviceNotFoundError, HALError, HALIncompatibleDeviceError
from .kinetic_hal import KineticHAL
from .pico_ezspr_hal import PicoEZSPRHAL
from .pico_p4spr_hal import PicoP4SPRHAL
from .spectrometer_hal import SpectrometerHAL
from .spr_controller_hal import SPRControllerHAL

# USB4000OceanDirect is the only supported spectrometer implementation


class HALFactory:
    """Factory for creating Hardware Abstraction Layer implementations.

    Provides methods to automatically detect and create appropriate HAL
    instances based on connected hardware or configuration requirements.
    """

    # Registry of available controller implementations
    _controller_registry: dict[str, type[SPRControllerHAL]] = {
        "PicoP4SPR": PicoP4SPRHAL,
        "pico_p4spr": PicoP4SPRHAL,
        "PicoEZSPR": PicoEZSPRHAL,
        "pico_ezspr": PicoEZSPRHAL,
        # Add more controllers here as they're implemented
        # "CustomController": CustomControllerHAL,  # Future implementation
    }

    # Registry of available spectrometer implementations
    _spectrometer_registry: dict[str, type[SpectrometerHAL]] = {
        "USB4000": USB4000OceanDirect,  # Use Ocean Direct API implementation
        "usb4000": USB4000OceanDirect,
        "OceanOptics": USB4000OceanDirect,  # Alias for USB4000
        "USB4000-OceanDirect": USB4000OceanDirect,
        "usb4000-oceandirect": USB4000OceanDirect,
        # Future spectrometer implementations:
        # "USB2000": USB2000HAL,
        # "QE65000": QE65000HAL,
        # "Avantes": AvantesHAL,
        # "StellarNet": StellarNetHAL,
    }

    # Registry of available kinetic controller implementations
    _kinetic_registry: dict[str, type] = {
        "KNX2": KineticHAL,
        "knx2": KineticHAL,
        "KNX1": KineticHAL,
        "knx1": KineticHAL,
        "KineticController": KineticHAL,
        "kinetic_controller": KineticHAL,
    }

    @classmethod
    def create_controller(
        cls,
        device_type: str | None = None,
        auto_detect: bool = True,
        connection_params: dict[str, Any] | None = None,
    ) -> SPRControllerHAL:
        """Create and connect to an SPR controller.

        Args:
            device_type: Specific device type to create (e.g., "PicoP4SPR")
                        If None, will attempt auto-detection
            auto_detect: Whether to attempt automatic device detection
            connection_params: Optional connection parameters to pass to the HAL

        Returns:
            Connected SPRControllerHAL instance

        Raises:
            HALDeviceNotFoundError: If no compatible device found
            HALIncompatibleDeviceError: If device type not supported
            HALError: If connection fails

        """
        connection_params = connection_params or {}

        # If specific device type requested, try to create it directly
        if device_type:
            return cls._create_specific_controller(device_type, connection_params)

        # Auto-detection mode
        if auto_detect:
            return cls._auto_detect_controller(connection_params)

        raise HALDeviceNotFoundError(
            "No device type specified and auto-detection disabled",
            expected_device="SPRController",
        )

    @classmethod
    def get_available_controllers(cls) -> list[str]:
        """Get list of available controller types.

        Returns:
            List of supported controller type names

        """
        return list(cls._controller_registry.keys())

    @classmethod
    def register_controller(
        cls,
        device_type: str,
        hal_class: type[SPRControllerHAL],
    ) -> None:
        """Register a new controller HAL implementation.

        Args:
            device_type: Device type identifier
            hal_class: HAL implementation class

        """
        cls._controller_registry[device_type] = hal_class
        logger.info(f"Registered HAL for device type: {device_type}")

    @classmethod
    def is_controller_supported(cls, device_type: str) -> bool:
        """Check if a controller type is supported.

        Args:
            device_type: Device type to check

        Returns:
            True if supported, False otherwise

        """
        return device_type in cls._controller_registry

    @classmethod
    def detect_connected_devices(cls) -> list[dict[str, Any]]:
        """Detect all connected SPR devices.

        Returns:
            List of device information dictionaries

        """
        detected_devices = []

        # Try each registered controller type
        for device_type, hal_class in cls._controller_registry.items():
            try:
                # Create temporary instance for detection - use device_type as name
                hal_instance = hal_class()

                # Try to connect and get device info
                if hal_instance.connect():
                    device_info = hal_instance.get_device_info()
                    device_info["hal_type"] = device_type
                    device_info["hal_class"] = hal_class.__name__
                    detected_devices.append(device_info)
                    hal_instance.disconnect()

            except Exception as e:
                logger.debug(f"Detection failed for {device_type}: {e}")
                continue

        return detected_devices

    @classmethod
    def _create_specific_controller(
        cls,
        device_type: str,
        connection_params: dict[str, Any],
    ) -> SPRControllerHAL:
        """Create specific controller type."""
        if device_type not in cls._controller_registry:
            available = ", ".join(cls._controller_registry.keys())
            raise HALIncompatibleDeviceError(
                f"Unsupported device type: {device_type}. Available: {available}",
                expected_device=device_type,
            )

        hal_class = cls._controller_registry[device_type]
        controller = hal_class()  # Constructor sets device name automatically

        # Attempt connection
        try:
            if controller.connect(**connection_params):
                logger.info(
                    f"Successfully created and connected {device_type} controller",
                )
                return controller
            raise HALError(f"Failed to connect to {device_type}")

        except Exception as e:
            # Cleanup on failure
            try:
                controller.disconnect()
            except Exception:
                pass
            raise HALError(f"Failed to create {device_type} controller: {e}")

    @classmethod
    def _auto_detect_controller(
        cls,
        connection_params: dict[str, Any],
    ) -> SPRControllerHAL:
        """Auto-detect and create controller."""
        logger.info("Auto-detecting SPR controller...")

        last_error = None

        # Try each registered controller type in priority order
        # PicoP4SPR has highest priority for now
        priority_order = ["PicoP4SPR", "pico_p4spr"]
        remaining_types = [
            t for t in cls._controller_registry.keys() if t not in priority_order
        ]

        for device_type in priority_order + remaining_types:
            try:
                logger.debug(f"Trying to detect {device_type}...")
                controller = cls._create_specific_controller(
                    device_type,
                    connection_params,
                )
                logger.info(f"Auto-detected controller: {device_type}")
                return controller

            except Exception as e:
                logger.debug(f"Auto-detection failed for {device_type}: {e}")
                last_error = e
                continue

        # No devices detected
        error_msg = f"No compatible SPR controllers detected. Last error: {last_error}"
        raise HALDeviceNotFoundError(error_msg, expected_device="SPRController")

    @classmethod
    def create_controller_from_config(cls, config: dict[str, Any]) -> SPRControllerHAL:
        """Create controller from configuration dictionary.

        Args:
            config: Configuration dictionary with keys:
                   - device_type: Controller type
                   - connection: Connection parameters
                   - auto_detect: Whether to auto-detect if type fails

        Returns:
            Connected SPRControllerHAL instance

        """
        device_type = config.get("device_type")
        connection_params = config.get("connection", {})
        auto_detect = config.get("auto_detect", True)

        return cls.create_controller(
            device_type=device_type,
            auto_detect=auto_detect,
            connection_params=connection_params,
        )

    @classmethod
    def get_controller_capabilities(cls, device_type: str) -> dict[str, Any] | None:
        """Get capabilities for a specific controller type without connecting.

        Args:
            device_type: Controller type to query

        Returns:
            Capabilities dictionary or None if not supported

        """
        if device_type not in cls._controller_registry:
            return None

        try:
            # Create temporary instance to get capabilities
            hal_class = cls._controller_registry[device_type]
            temp_instance = hal_class()  # Constructor sets device name automatically
            capabilities = temp_instance.get_capabilities()

            # Convert to dictionary for serialization
            return {
                "supported_channels": [
                    ch.value for ch in capabilities.supported_channels
                ],
                "max_channels": capabilities.max_channels,
                "supports_led_control": capabilities.supports_led_control,
                "led_intensity_range": capabilities.led_intensity_range,
                "supports_temperature": capabilities.supports_temperature,
                "temperature_range": capabilities.temperature_range,
                "connection_type": capabilities.connection_type,
                "device_model": capabilities.device_model,
                "supports_variable_timing": capabilities.supports_variable_timing,
                "min_integration_time": capabilities.min_integration_time,
                "max_integration_time": capabilities.max_integration_time,
            }

        except Exception as e:
            logger.warning(f"Failed to get capabilities for {device_type}: {e}")
            return None

    # ============================================================================
    # SPECTROMETER FACTORY METHODS
    # ============================================================================

    @classmethod
    def create_spectrometer(
        cls,
        device_type: str | None = None,
        auto_detect: bool = True,
        connection_params: dict[str, Any] | None = None,
    ) -> SpectrometerHAL:
        """Create and connect to a spectrometer.

        Args:
            device_type: Specific device type to create (e.g., "USB4000")
                        If None, will attempt auto-detection
            auto_detect: Whether to attempt automatic device detection
            connection_params: Optional connection parameters to pass to the HAL

        Returns:
            Connected SpectrometerHAL instance

        Raises:
            HALError: If device creation fails
            HALDeviceNotFoundError: If no compatible devices found

        """
        connection_params = connection_params or {}

        logger.info(
            f"Creating spectrometer: device_type={device_type}, auto_detect={auto_detect}",
        )

        if device_type and device_type in cls._spectrometer_registry:
            # Try specific device type first
            try:
                return cls._create_specific_spectrometer(device_type, connection_params)
            except Exception as e:
                if not auto_detect:
                    raise
                logger.warning(
                    f"Failed to create {device_type}: {e}, attempting auto-detection",
                )

        if auto_detect:
            return cls._auto_detect_spectrometer(connection_params)

        # No auto-detection, but device_type was invalid
        if device_type:
            raise HALError(f"Unsupported spectrometer type: {device_type}")
        raise HALError("No device type specified and auto-detection disabled")

    @classmethod
    def _create_specific_spectrometer(
        cls,
        device_type: str,
        connection_params: dict[str, Any],
    ) -> SpectrometerHAL:
        """Create specific spectrometer type."""
        logger.debug(f"Creating {device_type} spectrometer")

        hal_class = cls._spectrometer_registry[device_type]

        # Try to create the HAL instance
        try:
            spectrometer = hal_class()  # Constructor will use default device name
        except Exception as init_e:
            error_msg = f"Failed to create {device_type} spectrometer: {init_e}"
            raise HALError(error_msg) from init_e

        # Attempt connection
        try:
            if spectrometer.connect(**connection_params):
                logger.info(
                    f"Successfully created and connected {device_type} spectrometer",
                )
                return spectrometer
            raise HALError(f"Failed to connect to {device_type}")

        except Exception as e:
            # Cleanup on failure
            try:
                spectrometer.disconnect()
            except Exception:
                pass

            error_msg = f"Failed to create {device_type} spectrometer: {e}"
            raise HALError(error_msg) from e

    @classmethod
    def _auto_detect_spectrometer(
        cls,
        connection_params: dict[str, Any],
    ) -> SpectrometerHAL:
        """Auto-detect and create spectrometer."""
        logger.info("Auto-detecting spectrometer...")

        last_error = None

        # Try each registered spectrometer type in priority order
        # USB4000 has highest priority for now
        priority_order = ["USB4000", "usb4000"]
        remaining_types = [
            t for t in cls._spectrometer_registry.keys() if t not in priority_order
        ]

        for device_type in priority_order + remaining_types:
            try:
                logger.debug(f"Trying to detect {device_type}...")
                spectrometer = cls._create_specific_spectrometer(
                    device_type,
                    connection_params,
                )
                logger.info(f"Auto-detected spectrometer: {device_type}")
                return spectrometer

            except Exception as e:
                logger.debug(f"Auto-detection failed for {device_type}: {e}")
                last_error = e
                continue

        # No devices detected
        error_msg = f"No compatible spectrometers detected. Last error: {last_error}"
        raise HALDeviceNotFoundError(error_msg, expected_device="Spectrometer")

    @classmethod
    def register_spectrometer(
        cls,
        device_type: str,
        hal_class: type[SpectrometerHAL],
    ) -> None:
        """Register a new spectrometer HAL implementation.

        Args:
            device_type: Device type identifier
            hal_class: HAL implementation class

        """
        cls._spectrometer_registry[device_type] = hal_class
        logger.info(
            f"Registered spectrometer HAL: {device_type} -> {hal_class.__name__}",
        )

    @classmethod
    def get_supported_spectrometers(cls) -> list[str]:
        """Get list of supported spectrometer types."""
        return list(cls._spectrometer_registry.keys())

    @classmethod
    def is_spectrometer_supported(cls, device_type: str) -> bool:
        """Check if a spectrometer type is supported.

        Args:
            device_type: Device type to check

        Returns:
            True if supported, False otherwise

        """
        return device_type in cls._spectrometer_registry

    @classmethod
    def get_spectrometer_capabilities(cls, device_type: str) -> dict[str, Any] | None:
        """Get capabilities for a specific spectrometer type.

        Args:
            device_type: Spectrometer type to query

        Returns:
            Capabilities dictionary or None if unavailable

        """
        if device_type not in cls._spectrometer_registry:
            return None

        try:
            # Create temporary instance to get capabilities
            hal_class = cls._spectrometer_registry[device_type]
            temp_instance = hal_class()  # Constructor will use default device name
            capabilities = temp_instance.get_capabilities()

            # Convert to dictionary for serialization
            return {
                "wavelength_range": capabilities.wavelength_range,
                "wavelength_resolution": capabilities.wavelength_resolution,
                "min_integration_time": capabilities.min_integration_time,
                "max_integration_time": capabilities.max_integration_time,
                "supports_dark_current_correction": capabilities.supports_dark_current_correction,
                "supports_reference_correction": capabilities.supports_reference_correction,
                "supports_averaging": capabilities.supports_averaging,
                "max_averages": capabilities.max_averages,
                "pixel_count": capabilities.pixel_count,
                "bit_depth": capabilities.bit_depth,
                "connection_type": capabilities.connection_type,
                "device_model": capabilities.device_model,
            }

        except Exception as e:
            logger.warning(f"Failed to get capabilities for {device_type}: {e}")
            return None

    @classmethod
    def create_spectrometer_from_config(cls, config: dict[str, Any]) -> SpectrometerHAL:
        """Create spectrometer from configuration dictionary.

        Args:
            config: Configuration dictionary with keys:
                   - device_type: Spectrometer type
                   - connection: Connection parameters
                   - auto_detect: Whether to auto-detect if type fails

        Returns:
            Connected SpectrometerHAL instance

        """
        device_type = config.get("device_type")
        connection_params = config.get("connection", {})
        auto_detect = config.get("auto_detect", True)

        return cls.create_spectrometer(
            device_type=device_type,
            auto_detect=auto_detect,
            connection_params=connection_params,
        )

    # ========================================================================
    # Kinetic Controller Factory Methods
    # ========================================================================

    @classmethod
    def create_kinetic_controller(
        cls,
        device_type: str | None = None,
        auto_detect: bool = True,
        connection_params: dict[str, Any] | None = None,
    ) -> Any:
        """Create kinetic controller HAL instance.

        Args:
            device_type: Specific kinetic controller type ("KNX2", "KNX1", etc.)
            auto_detect: Whether to auto-detect if type not specified/found
            connection_params: Device-specific connection parameters

        Returns:
            Connected kinetic controller HAL instance

        Raises:
            HALDeviceNotFoundError: If no suitable device found
            HALIncompatibleDeviceError: If device incompatible

        """
        logger.info("Creating kinetic controller HAL...")

        # Try specific device type first
        if device_type:
            try:
                hal_class = cls._kinetic_registry.get(device_type)
                if hal_class:
                    logger.debug(f"Creating {device_type} kinetic controller")
                    kinetic = hal_class(device_name=f"{device_type} Kinetic Controller")

                    if kinetic.connect(**(connection_params or {})):
                        logger.info(
                            f"Successfully connected to {device_type} kinetic controller",
                        )
                        return kinetic
                    logger.warning(
                        f"Failed to connect to {device_type} kinetic controller",
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to create {device_type} kinetic controller: {e}",
                )

        # Auto-detection if enabled
        if auto_detect:
            logger.debug("Auto-detecting kinetic controller...")

            # Try each registered kinetic controller type
            for name, hal_class in cls._kinetic_registry.items():
                if name.endswith("-Test") or name == "test":
                    continue  # Skip test implementations in auto-detection

                try:
                    logger.debug(f"Trying {name} kinetic controller")
                    kinetic = hal_class(device_name=f"{name} Kinetic Controller")

                    if kinetic.connect(**(connection_params or {})):
                        logger.info(
                            f"Auto-detected and connected to {name} kinetic controller",
                        )
                        return kinetic
                    kinetic.disconnect()

                except Exception as e:
                    logger.debug(f"Failed to connect to {name}: {e}")
                    continue

        raise HALDeviceNotFoundError(
            "No kinetic controller found",
            expected_device="KineticController",
        )

    @classmethod
    def detect_kinetic_controllers(cls) -> list[dict[str, Any]]:
        """Detect available kinetic controllers.

        Returns:
            List of detected kinetic controller information

        """
        detected = []

        for name, hal_class in cls._kinetic_registry.items():
            if name.endswith("-Test") or name == "test":
                continue  # Skip test implementations

            try:
                logger.debug(f"Checking for {name} kinetic controller")
                kinetic = hal_class(device_name=f"{name} Kinetic Controller")

                if kinetic.connect():
                    device_info = kinetic.get_device_info()
                    detected.append(
                        {
                            "type": name,
                            "status": "available",
                            "info": device_info,
                            "capabilities": kinetic.get_capabilities(),
                        },
                    )
                    kinetic.disconnect()
                else:
                    detected.append(
                        {
                            "type": name,
                            "status": "not_found",
                            "info": {},
                            "capabilities": [],
                        },
                    )

            except Exception as e:
                logger.debug(f"Error detecting {name}: {e}")
                detected.append(
                    {
                        "type": name,
                        "status": "error",
                        "error": str(e),
                        "info": {},
                        "capabilities": [],
                    },
                )

        return detected

    @classmethod
    def get_supported_kinetic_controllers(cls) -> list[str]:
        """Get list of supported kinetic controller types.

        Returns:
            List of supported kinetic controller names

        """
        # Filter out test implementations for external API
        return [
            name
            for name in cls._kinetic_registry.keys()
            if not name.endswith("-Test") and name != "test"
        ]

    @classmethod
    def get_kinetic_controller_capabilities(
        cls,
        device_type: str,
    ) -> dict[str, Any] | None:
        """Get capabilities for a specific kinetic controller type.

        Args:
            device_type: Kinetic controller type

        Returns:
            Capabilities dictionary or None if not supported

        """
        try:
            hal_class = cls._kinetic_registry.get(device_type)
            if not hal_class:
                return None

            # Create temporary instance to get capabilities
            kinetic = hal_class(device_name=f"{device_type} Kinetic Controller")
            capabilities = kinetic.get_capabilities()

            # Return as dictionary
            return {"capabilities": capabilities}

        except Exception as e:
            logger.warning(f"Failed to get capabilities for {device_type}: {e}")
            return None

    @classmethod
    def create_kinetic_controller_from_config(cls, config: dict[str, Any]) -> Any:
        """Create kinetic controller from configuration dictionary.

        Args:
            config: Configuration dictionary with keys:
                   - device_type: Kinetic controller type
                   - connection: Connection parameters
                   - auto_detect: Whether to auto-detect if type fails

        Returns:
            Connected kinetic controller HAL instance

        """
        device_type = config.get("device_type")
        connection_params = config.get("connection", {})
        auto_detect = config.get("auto_detect", True)

        return cls.create_kinetic_controller(
            device_type=device_type,
            auto_detect=auto_detect,
            connection_params=connection_params,
        )
