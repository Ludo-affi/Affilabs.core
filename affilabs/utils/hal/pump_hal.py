"""Affipump Hardware Abstraction Layer.

Provides unified interface for Affipump peripheral (Tecan Cavro Centris dual syringe pumps).

Supported Hardware:
- Affipump (2x Tecan Cavro Centris pumps via FTDI serial)

Features:
- Low-level pump commands via send_command()
- High-level operations via CavroPumpManager wrapper
- Consistent HAL pattern with detectors and controllers

Use create_pump_hal() factory function to wrap pump instances.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class PumpHAL(Protocol):
    """Unified pump interface abstracting hardware communication.

    Provides:
    - Low-level command interface (send_command)
    - High-level pump operations (initialize, aspirate, dispense)
    - Valve control
    - Syringe position tracking
    """

    # Low-Level Commands
    def send_command(self, address: int, command: bytes) -> bytes:
        """Send raw command to pump controller.

        Args:
            address: Pump address (0x41 for broadcast, 0x42/0x43 for individual)
            command: Raw command bytes (e.g., b"T" for terminate, b"A0" for absolute move)

        Returns:
            Response bytes from pump

        """
        ...

    def is_available(self) -> bool:
        """Check if pump hardware is available and initialized.

        Returns:
            True if pumps are ready for operation

        """
        ...

    # High-Level Operations
    def initialize_pumps(self) -> bool:
        """Initialize both pumps and prepare for operation.

        Returns:
            True if initialization succeeded

        """
        ...

    def aspirate(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        """Aspirate fluid into syringe.

        Args:
            pump_address: Pump ID (1 or 2)
            volume_ul: Volume to aspirate in microliters
            rate_ul_min: Flow rate in µL/min

        Returns:
            True if command succeeded

        """
        ...

    def dispense(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        """Dispense fluid from syringe.

        Args:
            pump_address: Pump ID (1 or 2)
            volume_ul: Volume to dispense in microliters
            rate_ul_min: Flow rate in µL/min

        Returns:
            True if command succeeded

        """
        ...

    def set_valve_position(self, pump_address: int, port: int) -> bool:
        """Set valve position.

        Args:
            pump_address: Pump ID (1 or 2)
            port: Valve port number (1-9 depending on valve type)

        Returns:
            True if command succeeded

        """
        ...

    def get_syringe_position(self, pump_address: int) -> int | None:
        """Get current syringe position in steps.

        Args:
            pump_address: Pump ID (1 or 2)

        Returns:
            Position in steps, or None if query failed

        """
        ...

    def wait_until_idle(self, pump_address: int, timeout_s: float = 60.0) -> bool:
        """Wait for pump to finish current operation.

        Args:
            pump_address: Pump ID (1 or 2)
            timeout_s: Maximum wait time in seconds

        Returns:
            True if pump became idle, False if timeout

        """
        ...

    # Connection Management
    def close(self) -> None:
        """Close connection to pump hardware."""
        ...


class AffipumpAdapter:
    """Adapter wrapping Affipump (CavroPumpManager) to provide PumpHAL interface."""

    def __init__(self, pump_manager) -> None:
        """Initialize adapter with existing CavroPumpManager instance.

        Args:
            pump_manager: CavroPumpManager instance from affipump package

        """
        self._pump = pump_manager
        self._controller = (
            pump_manager.pump if hasattr(pump_manager, "pump") else None
        )

    # Low-Level Commands
    def send_command(self, address: int, command: bytes) -> bytes:
        """Send raw command via underlying PumpController."""
        if self._controller is None:
            logger.warning("Pump controller not available for send_command")
            return b""
        return self._controller.send_command(address, command)

    def is_available(self) -> bool:
        """Check if pump hardware is available."""
        return self._pump.is_available() if self._pump else False

    # High-Level Operations
    def initialize_pumps(self) -> bool:
        """Initialize both pumps."""
        if not self._pump:
            return False
        return self._pump.initialize_pumps()

    def aspirate(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        """Aspirate fluid into syringe."""
        if not self._pump:
            return False
        try:
            self._pump.aspirate(pump_address, volume_ul, rate_ul_min)
            return True
        except Exception as e:
            logger.error(f"Aspirate failed: {e}")
            return False

    def dispense(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        """Dispense fluid from syringe."""
        if not self._pump:
            return False
        try:
            self._pump.dispense(pump_address, volume_ul, rate_ul_min)
            return True
        except Exception as e:
            logger.error(f"Dispense failed: {e}")
            return False

    def set_valve_position(self, pump_address: int, port: int) -> bool:
        """Set valve position."""
        if not self._pump:
            return False
        try:
            self._pump.set_valve_position(pump_address, port)
            return True
        except Exception as e:
            logger.error(f"Set valve position failed: {e}")
            return False

    def get_syringe_position(self, pump_address: int) -> int | None:
        """Get current syringe position."""
        if not self._pump:
            return None
        return self._pump.get_syringe_position(pump_address)

    def wait_until_idle(self, pump_address: int, timeout_s: float = 60.0) -> bool:
        """Wait for pump to finish current operation."""
        if not self._pump:
            return False
        return self._pump.wait_until_idle(pump_address, timeout_s)

    # Connection Management
    def close(self) -> None:
        """Close connection to pump hardware."""
        if self._controller:
            self._controller.close()


def create_pump_hal(pump_manager) -> PumpHAL:
    """Factory function to create Affipump HAL adapter.

    This is the main entry point for using the Pump HAL. Pass an existing
    CavroPumpManager instance and get back a PumpHAL interface.

    Args:
        pump_manager: CavroPumpManager instance from affipump package

    Returns:
        PumpHAL adapter wrapping the pump manager

    Example:
        from AffiPump import CavroPumpManager, PumpController
        from affilabs.utils.hal.pump_hal import create_pump_hal

        # Connect to hardware
        controller = PumpController.from_first_available()
        pump_manager = CavroPumpManager(controller)

        # Wrap with HAL
        pump = create_pump_hal(pump_manager)

        # Initialize and use
        if pump.initialize_pumps():
            pump.aspirate(1, 100.0, 500.0)  # Pump 1, 100µL at 500µL/min

    """
    return AffipumpAdapter(pump_manager)
