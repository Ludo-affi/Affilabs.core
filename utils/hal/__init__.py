"""
Hardware Abstraction Layer (HAL) for SPR Instruments

This package provides hardware abstraction interfaces for SPR instruments,
enabling device-agnostic code and simplified hardware integration.
"""

from .spr_controller_hal import SPRControllerHAL, ControllerCapabilities, ChannelID
from .spectrometer_hal import SpectrometerHAL, SpectrometerCapabilities
from .kinetic_system_hal import KineticSystemHAL, KineticCapabilities
from .hal_factory import HALFactory
from .hal_exceptions import HALError, HALConnectionError, HALTimeoutError, HALConfigurationError

from .pico_p4spr_hal import PicoP4SPRHAL
from .pico_ezspr_hal import PicoEZSPRHAL
from .usb4000_test_hal import USB4000TestHAL
from .kinetic_hal import KineticHAL
from .kinetic_test_hal import KineticTestHAL

__all__ = [
    # Core HAL interfaces
    "SPRControllerHAL",
    "SpectrometerHAL", 
    "KineticSystemHAL",
    
    # Enums and data types
    "ChannelID",
    
    # Capability descriptors
    "ControllerCapabilities",
    "SpectrometerCapabilities",
    "KineticCapabilities",
    
    # Factory
    "HALFactory",
    
    # Exceptions
    "HALError",
    "HALConnectionError", 
    "HALTimeoutError",
    "HALConfigurationError",
    
    # HAL implementations
    "PicoP4SPRHAL",
    "PicoEZSPRHAL",
    "USB4000TestHAL",
    "KineticHAL",
    "KineticTestHAL",
]