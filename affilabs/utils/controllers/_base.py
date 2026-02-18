from __future__ import annotations

import contextlib
import threading
import time
from platform import system
from typing import Final

import numpy as np
import serial
import serial.tools.list_ports

from affilabs.utils.logger import logger
from settings import (
    ARDUINO_PID,
    ARDUINO_VID,
    BAUD_RATE,
    CP210X_PID,
    CP210X_VID,
    PICO_PID,
    PICO_VID,
)

if system() == "Windows":
    import string

CH_DICT = {"a": 1, "b": 2, "c": 3, "d": 4}


class ControllerBase:
    """Abstract base class for all hardware controllers."""

    def __init__(self, name) -> None:
        self._ser = None
        self.name = name

    def open(self) -> None:
        pass

    def get_info(self) -> None:
        pass

    def turn_on_channel(self, ch="a") -> None:
        pass

    def turn_off_channels(self) -> None:
        pass

    def set_mode(self, mode="s") -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        """Close serial port connection."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                # Log but don't raise - we want cleanup to continue
                logger.exception(f"Error closing serial port: {e}")
            finally:
                self._ser = None

    # EEPROM Configuration Methods
    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        return False  # Override in subclass

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM.

        Returns dict with keys:
            led_pcb_model: 'luminus_cool_white' or 'osram_warm_white'
            controller_type: 'arduino', 'pico_p4spr', 'pico_ezspr'
            fiber_diameter_um: 100 or 200
            polarizer_type: 'barrel' or 'round'
            servo_s_position: 0-180
            servo_p_position: 0-180
            led_intensity_a: 0-255
            led_intensity_b: 0-255
            led_intensity_c: 0-255
            led_intensity_d: 0-255
            integration_time_ms: int
            num_scans: int

        Returns None if no valid config or firmware doesn't support.
        """
        return None  # Override in subclass

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM.

        Args:
            config: Dict with same keys as read_config_from_eeprom()

        Returns:
            True if successful, False otherwise

        """
        return False  # Override in subclass

    @staticmethod
    def _encode_led_model(model: str) -> int:
        """Convert LED model name to byte value."""
        mapping = {
            "luminus_cool_white": 0,
            "osram_warm_white": 1,
        }
        return mapping.get(model.lower(), 255)

    @staticmethod
    def _decode_led_model(value: int) -> str:
        """Convert byte value to LED model name."""
        mapping = {0: "luminus_cool_white", 1: "osram_warm_white"}
        return mapping.get(value)

    @staticmethod
    def _encode_controller_type(controller_type: str) -> int:
        """Convert controller type to byte value."""
        mapping = {
            "arduino": 0,
            "pico_p4spr": 1,
            "pico_ezspr": 2,
        }
        return mapping.get(controller_type.lower(), 255)

    @staticmethod
    def _decode_controller_type(value: int) -> str:
        """Convert byte value to controller type."""
        mapping = {0: "arduino", 1: "pico_p4spr", 2: "pico_ezspr"}
        return mapping.get(value)

    @staticmethod
    def _encode_polarizer_type(polarizer: str) -> int:
        """Convert polarizer type to byte value."""
        mapping = {"barrel": 0, "round": 1}
        return mapping.get(polarizer.lower(), 255)

    @staticmethod
    def _decode_polarizer_type(value: int) -> str:
        """Convert byte value to polarizer type."""
        mapping = {0: "barrel", 1: "round"}
        return mapping.get(value)

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """Calculate XOR checksum of first 16 bytes."""
        checksum = 0
        for byte in data[0:16]:
            checksum ^= byte
        return checksum

    def __del__(self) -> None:
        """Destructor to ensure serial port is closed."""
        try:
            if hasattr(self, "_ser") and self._ser is not None:
                self.close()
        except:
            pass


class StaticController(ControllerBase):
    """Base class for static-mode controllers (P4SPR family).

    Static controllers have detector/spectroscopy capabilities but no pumps or valves.
    They operate by having liquid statically incubate on the sensor surface.

    Hardware: ArduinoController (Gen 1), PicoP4SPR (Gen 2)
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Static controllers do not support flow mode."""
        return False


class FlowController(ControllerBase):
    """Base class for flow-mode controllers (P4PRO, KNX, ezSPR families).

    Flow controllers support liquid handling via pumps and valves for continuous
    flow-based SPR measurements.

    Hardware configurations:
    - P4PRO: P4SPR detector + KNX valves + external AffiPump
    - KNX: Standalone pump/valve unit (no detector)
    - ezSPR/P4PROPlus: P4SPR detector + integrated KNX pumps/valves
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Flow controllers support flow mode."""
        return True
