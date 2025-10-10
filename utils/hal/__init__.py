"""Hardware Abstraction Layer (HAL) for SPR Instruments

This package provides hardware abstraction interfaces for SPR instruments,
enabling device-agnostic code and simplified hardware integration.
"""

from .hal_exceptions import (
    HALConfigurationError,
    HALConnectionError,
    HALError,
    HALTimeoutError,
)
from .hal_factory import HALFactory
from .kinetic_hal import KineticHAL
from .kinetic_system_hal import KineticCapabilities, KineticSystemHAL
from .pico_ezspr_hal import PicoEZSPRHAL
from .pico_p4spr_hal import PicoP4SPRHAL
from .spectrometer_hal import SpectrometerCapabilities, SpectrometerHAL
from .spr_controller_hal import ChannelID, ControllerCapabilities, SPRControllerHAL

# USB4000OceanDirectHAL removed - using direct USB4000OceanDirect class instead

# Legacy HAL implementations removed for cleaner architecture

__all__ = [
    # Core HAL interfaces
    "KineticSystemHAL",
    "SpectrometerHAL",
    "SPRControllerHAL",
    # Enums and data types
    "ChannelID",
    # Capability descriptors
    "ControllerCapabilities",
    "KineticCapabilities",
    "SpectrometerCapabilities",
    # Factory
    "HALFactory",
    # Exceptions
    "HALConfigurationError",
    "HALConnectionError",
    "HALError",
    "HALTimeoutError",
    # HAL implementations
    "KineticHAL",
    "PicoEZSPRHAL",
    "PicoP4SPRHAL",
]
