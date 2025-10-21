"""Tecan Cavro Centris Pump Manager
Provides high-level abstraction for dual-pump control with volume tracking,
error handling, and diagnostic features.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from PySide6.QtCore import QObject, Signal

from utils.logger import logger

try:
    from pump_controller import PumpController
    from pump_controller import PumpException as FTDIError
except ImportError:

    class FTDIError(Exception):
        """FTDI pump error stub."""

    PumpController = None


# ============================================================================
# Constants
# ============================================================================


class PumpAddress(IntEnum):
    """Tecan Cavro pump addresses."""

    PUMP_1 = 0x31  # First pump (Channel 1)
    PUMP_2 = 0x32  # Second pump (Channel 2)
    BROADCAST = 0x41  # Both pumps


class ValvePort(IntEnum):
    """Standard valve port positions (1-9)."""

    PORT_1 = 1
    PORT_2 = 2
    PORT_3 = 3
    PORT_4 = 4
    PORT_5 = 5
    PORT_6 = 6
    PORT_7 = 7
    PORT_8 = 8
    PORT_9 = 9


class PumpError(IntEnum):
    """Pump error flags (from ?19 query)."""

    NO_ERROR = 0x00
    INITIALIZATION_ERROR = 0x01
    INVALID_COMMAND = 0x02
    INVALID_OPERAND = 0x03
    EEPROM_ERROR = 0x04
    VALVE_ERROR = 0x06
    PLUNGER_OVERLOAD = 0x07
    VALVE_OVERLOAD = 0x08
    PLUNGER_MOVE_NOT_ALLOWED = 0x09
    COMMAND_OVERFLOW = 0x0A
    LIMIT_SWITCH_ERROR = 0x0B


# Command constants
CMD_QUERY_POSITION = b"?"
CMD_QUERY_VALVE = b"?6"
CMD_QUERY_ERROR = b"?19"
CMD_QUERY_BUSY = b"Q"
CMD_INITIALIZE = b"ZR"
CMD_ENABLE = b"e15R"
CMD_RESET = b"zR"
CMD_CLEAR_ERROR = b"W5R"
CMD_STOP = b"T"
CMD_RUN = b"R"

# Flow rate constants (ml/min)
DEFAULT_FLOW_RATE = 1.0
FLUSH_FLOW_RATE = 100.0
FAST_FLUSH_RATE = 83.333
ULTRA_FAST_FLUSH_RATE = 6000.0

# Timing constants (seconds)
REGENERATION_PREFLOW_TIME = 22.0
FLUSH_PREP_TIME = 9.0
FAST_FLUSH_DURATION = 0.8
FLUSH_CYCLE_DURATION = 4.0
INJECTION_TIME = 80.0

# Syringe constants
DEFAULT_SYRINGE_VOLUME_UL = 5000  # 5 mL syringe
STEPS_PER_STROKE = 3000  # Typical for Centris
MAX_SPEED_STEPS_PER_SEC = 6000
MIN_SPEED_STEPS_PER_SEC = 2

# Ramp time constants (milliseconds)
DEFAULT_START_RAMP_MS = 500
DEFAULT_STOP_RAMP_MS = 500


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SyringeState:
    """Track syringe position and volume."""

    position_steps: int = 0
    max_volume_ul: float = DEFAULT_SYRINGE_VOLUME_UL
    steps_per_ul: float = field(init=False)

    def __post_init__(self) -> None:
        """Calculate steps per microliter."""
        self.steps_per_ul = STEPS_PER_STROKE / self.max_volume_ul

    @property
    def current_volume_ul(self) -> float:
        """Calculate current volume in syringe."""
        return self.position_steps / self.steps_per_ul

    @property
    def remaining_volume_ul(self) -> float:
        """Calculate remaining capacity."""
        return self.max_volume_ul - self.current_volume_ul

    @property
    def is_empty(self) -> bool:
        """Check if syringe is at top (empty)."""
        return self.position_steps <= 0

    @property
    def is_full(self) -> bool:
        """Check if syringe is at bottom (full)."""
        return self.position_steps >= STEPS_PER_STROKE

    def volume_to_steps(self, volume_ul: float) -> int:
        """Convert volume to encoder steps."""
        return int(volume_ul * self.steps_per_ul)

    def steps_to_volume(self, steps: int) -> float:
        """Convert encoder steps to volume."""
        return steps / self.steps_per_ul


@dataclass
class ValveState:
    """Track valve position."""

    current_port: int = 1
    last_move_time: float = 0.0
    move_count: int = 0


@dataclass
class PumpState:
    """Complete state of a single pump."""

    address: int
    syringe: SyringeState = field(default_factory=SyringeState)
    valve: ValveState = field(default_factory=ValveState)
    flow_rate_ml_per_min: float = 0.0
    is_running: bool = False
    last_error: int = PumpError.NO_ERROR
    error_count: int = 0
    total_volume_dispensed_ul: float = 0.0
    total_volume_aspirated_ul: float = 0.0

    @property
    def flow_rate_ml_per_sec(self) -> float:
        """Get flow rate in ml/sec."""
        return abs(self.flow_rate_ml_per_min) / 60.0


# ============================================================================
# Cavro Pump Manager
# ============================================================================


class CavroPumpManager(QObject):
    """Manages Tecan Cavro Centris pumps with high-level operations.

    Features:
    - Volume-based aspirate/dispense
    - Syringe position tracking
    - Valve control and verification
    - Error detection and recovery
    - Speed ramping
    - Multi-step protocols
    - Diagnostic logging
    """

    # Signals
    pump_state_changed = Signal(int, str)  # address, state_description
    valve_position_changed = Signal(int, int)  # address, port
    error_occurred = Signal(int, str)  # address, error_message
    operation_progress = Signal(str, int)  # operation_name, progress_percent

    def __init__(self, pump_controller: Optional[PumpController] = None) -> None:
        """Initialize pump manager.

        Args:
            pump_controller: Hardware controller instance (optional)

        """
        super().__init__()
        self.pump = pump_controller

        # Initialize pump states
        self.pumps: dict[int, PumpState] = {
            PumpAddress.PUMP_1: PumpState(address=PumpAddress.PUMP_1),
            PumpAddress.PUMP_2: PumpState(address=PumpAddress.PUMP_2),
        }

        # Operation tracking
        self._operation_in_progress = False
        self._current_operation = ""

        logger.info("CavroPumpManager initialized")

    # ========================================================================
    # Hardware Communication
    # ========================================================================

    def _send_command(
        self,
        address: int,
        command: bytes,
        retry_count: int = 3,
    ) -> Optional[list[int]]:
        """Send command to pump with retry logic.

        Args:
            address: Pump address (0x31, 0x32, or 0x41)
            command: Command bytes
            retry_count: Number of retries on failure

        Returns:
            Response bytes or None on failure

        """
        if not self.pump:
            logger.warning("Pump controller not available")
            return None

        for attempt in range(retry_count):
            try:
                response = self.pump.send_command(address, command)
                return response
            except FTDIError as e:
                logger.warning(
                    f"Pump command failed (attempt {attempt + 1}/{retry_count}): {e}",
                )
                if attempt < retry_count - 1:
                    time.sleep(0.1)  # Brief delay before retry
                else:
                    logger.error(f"Pump command failed after {retry_count} attempts")
                    self.error_occurred.emit(address, str(e))
                    return None
        return None

    def is_available(self) -> bool:
        """Check if pump hardware is available."""
        return self.pump is not None

    # ========================================================================
    # Initialization and Configuration
    # ========================================================================

    def initialize_pumps(self, pump_addresses: list[int] | None = None) -> bool:
        """Initialize pumps to known state.

        Args:
            pump_addresses: List of pump addresses to initialize (None = all)

        Returns:
            True if successful

        """
        if not self.is_available():
            return False

        addresses = pump_addresses or [PumpAddress.PUMP_1, PumpAddress.PUMP_2]
        success = True

        for address in addresses:
            logger.info(f"Initializing pump {address:#x}")

            # Reset pump
            if not self._send_command(address, CMD_RESET):
                success = False
                continue

            time.sleep(0.5)

            # Enable pump
            if not self._send_command(address, CMD_ENABLE):
                success = False
                continue

            # Initialize syringe (home plunger)
            if not self.initialize_syringe(address):
                success = False
                continue

            # Set default speed ramping
            self.set_speed_ramp(address, DEFAULT_START_RAMP_MS, DEFAULT_STOP_RAMP_MS)

            # Clear any errors
            self.clear_errors(address)

            logger.info(f"Pump {address:#x} initialized successfully")

        if success:
            logger.info("All pumps initialized")
        else:
            logger.warning("Some pumps failed to initialize")

        return success

    def set_syringe_size(self, address: int, volume_ul: float) -> None:
        """Configure syringe size for volume calculations.

        Args:
            address: Pump address
            volume_ul: Syringe volume in microliters

        """
        if address in self.pumps:
            self.pumps[address].syringe.max_volume_ul = volume_ul
            self.pumps[address].syringe.steps_per_ul = STEPS_PER_STROKE / volume_ul
            logger.info(f"Pump {address:#x} syringe size set to {volume_ul} µL")

    def set_speed_ramp(
        self,
        address: int,
        start_ramp_ms: int = DEFAULT_START_RAMP_MS,
        stop_ramp_ms: int = DEFAULT_STOP_RAMP_MS,
    ) -> bool:
        """Set acceleration and deceleration ramps.

        Args:
            address: Pump address
            start_ramp_ms: Start ramp time in milliseconds
            stop_ramp_ms: Stop ramp time in milliseconds

        Returns:
            True if successful

        """
        # Set start ramp
        cmd_start = f"L{start_ramp_ms}R".encode()
        if not self._send_command(address, cmd_start):
            return False

        # Set stop ramp
        cmd_stop = f"h{stop_ramp_ms}R".encode()
        if not self._send_command(address, cmd_stop):
            return False

        logger.debug(
            f"Pump {address:#x} ramps set: start={start_ramp_ms}ms, stop={stop_ramp_ms}ms",
        )
        return True

    def set_backlash(self, address: int, steps: int = 10) -> bool:
        """Set backlash compensation for direction changes.

        Args:
            address: Pump address
            steps: Number of extra steps when reversing

        Returns:
            True if successful

        """
        cmd = f"K{steps}R".encode()
        result = self._send_command(address, cmd) is not None

        if result:
            logger.debug(f"Pump {address:#x} backlash set to {steps} steps")

        return result

    # ========================================================================
    # Syringe Operations
    # ========================================================================

    def initialize_syringe(self, address: int) -> bool:
        """Home syringe plunger (move to top and zero position).

        Args:
            address: Pump address

        Returns:
            True if successful

        """
        result = self._send_command(address, CMD_INITIALIZE)

        if result and address in self.pumps:
            self.pumps[address].syringe.position_steps = 0
            logger.info(f"Pump {address:#x} syringe initialized to home position")

        return result is not None

    def get_syringe_position(self, address: int) -> Optional[int]:
        """Query current plunger position.

        Args:
            address: Pump address

        Returns:
            Position in encoder steps or None on error

        """
        response = self._send_command(address, CMD_QUERY_POSITION)

        if response:
            try:
                # Parse response to extract position
                position = int(bytes(response[1:]).decode().strip())
                if address in self.pumps:
                    self.pumps[address].syringe.position_steps = position
                return position
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse position response: {e}")

        return None

    def move_to_position(
        self,
        address: int,
        position_steps: int,
        speed: float = DEFAULT_FLOW_RATE,
    ) -> bool:
        """Move plunger to absolute position.

        Args:
            address: Pump address
            position_steps: Target position (0 = top, 3000 = bottom)
            speed: Speed in ml/min

        Returns:
            True if successful

        """
        # Validate position
        if not 0 <= position_steps <= STEPS_PER_STROKE:
            logger.error(
                f"Invalid position: {position_steps} (must be 0-{STEPS_PER_STROKE})"
            )
            return False

        speed_ml_per_sec = speed / 60.0
        cmd = f"A{position_steps}V{speed_ml_per_sec:.3f}R".encode()
        result = self._send_command(address, cmd)

        if result and address in self.pumps:
            self.pumps[address].syringe.position_steps = position_steps
            logger.debug(f"Pump {address:#x} moved to position {position_steps}")

        return result is not None

    def aspirate(
        self,
        address: int,
        volume_ul: float,
        speed: float = DEFAULT_FLOW_RATE,
    ) -> bool:
        """Aspirate (pull in) liquid.

        Args:
            address: Pump address
            volume_ul: Volume to aspirate in microliters
            speed: Speed in ml/min

        Returns:
            True if successful

        """
        if address not in self.pumps:
            return False

        pump_state = self.pumps[address]
        steps = pump_state.syringe.volume_to_steps(volume_ul)

        # Check if syringe has capacity
        if pump_state.syringe.remaining_volume_ul < volume_ul:
            logger.error(
                f"Insufficient syringe capacity: need {volume_ul} µL, "
                f"have {pump_state.syringe.remaining_volume_ul:.1f} µL remaining",
            )
            return False

        speed_ml_per_sec = speed / 60.0
        cmd = f"P{steps}V{speed_ml_per_sec:.3f}R".encode()
        result = self._send_command(address, cmd)

        if result:
            pump_state.syringe.position_steps += steps
            pump_state.total_volume_aspirated_ul += volume_ul
            logger.info(f"Pump {address:#x} aspirated {volume_ul} µL")

        return result is not None

    def dispense(
        self,
        address: int,
        volume_ul: float,
        speed: float = DEFAULT_FLOW_RATE,
    ) -> bool:
        """Dispense (push out) liquid.

        Args:
            address: Pump address
            volume_ul: Volume to dispense in microliters
            speed: Speed in ml/min

        Returns:
            True if successful

        """
        if address not in self.pumps:
            return False

        pump_state = self.pumps[address]
        steps = pump_state.syringe.volume_to_steps(volume_ul)

        # Check if syringe has enough liquid
        if pump_state.syringe.current_volume_ul < volume_ul:
            logger.error(
                f"Insufficient liquid in syringe: need {volume_ul} µL, "
                f"have {pump_state.syringe.current_volume_ul:.1f} µL",
            )
            return False

        speed_ml_per_sec = speed / 60.0
        cmd = f"D{steps}V{speed_ml_per_sec:.3f}R".encode()
        result = self._send_command(address, cmd)

        if result:
            pump_state.syringe.position_steps -= steps
            pump_state.total_volume_dispensed_ul += volume_ul
            logger.info(f"Pump {address:#x} dispensed {volume_ul} µL")

        return result is not None

    # ========================================================================
    # Valve Operations
    # ========================================================================

    def set_valve_position(self, address: int, port: int) -> bool:
        """Move valve to specified port.

        Args:
            address: Pump address
            port: Valve port number (1-9)

        Returns:
            True if successful

        """
        if not 1 <= port <= 9:
            logger.error(f"Invalid valve port: {port} (must be 1-9)")
            return False

        cmd = f"I{port}R".encode()
        result = self._send_command(address, cmd)

        if result and address in self.pumps:
            self.pumps[address].valve.current_port = port
            self.pumps[address].valve.last_move_time = time.time()
            self.pumps[address].valve.move_count += 1
            self.valve_position_changed.emit(address, port)
            logger.debug(f"Pump {address:#x} valve moved to port {port}")

        return result is not None

    def get_valve_position(self, address: int) -> Optional[int]:
        """Query current valve position.

        Args:
            address: Pump address

        Returns:
            Valve port number (1-9) or None on error

        """
        response = self._send_command(address, CMD_QUERY_VALVE)

        if response:
            try:
                port = int(bytes(response[1:]).decode().strip())
                if address in self.pumps:
                    self.pumps[address].valve.current_port = port
                return port
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse valve position response: {e}")

        return None

    def verify_valve_position(
        self,
        address: int,
        expected_port: int,
        timeout: float = 5.0,
    ) -> bool:
        """Wait for valve to reach target position.

        Args:
            address: Pump address
            expected_port: Expected port number
            timeout: Maximum wait time in seconds

        Returns:
            True if valve reached position

        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.is_busy(address):
                actual_port = self.get_valve_position(address)
                if actual_port == expected_port:
                    return True
            time.sleep(0.1)

        logger.error(
            f"Pump {address:#x} valve did not reach port {expected_port} "
            f"within {timeout}s",
        )
        return False

    # ========================================================================
    # Flow Control
    # ========================================================================

    def start_flow(
        self,
        address: int,
        rate_ml_per_min: float,
        direction_forward: bool = True,
    ) -> bool:
        """Start continuous flow.

        Args:
            address: Pump address
            rate_ml_per_min: Flow rate in ml/min
            direction_forward: True for forward (dispense), False for reverse

        Returns:
            True if successful

        """
        if address not in self.pumps:
            return False

        rate_ml_per_sec = abs(rate_ml_per_min) / 60.0

        # Build command: set speed then start
        cmd = f"V{rate_ml_per_sec:.3f},1R".encode()
        result = self._send_command(address, cmd)

        if result:
            pump_state = self.pumps[address]
            pump_state.flow_rate_ml_per_min = (
                rate_ml_per_min if direction_forward else -rate_ml_per_min
            )
            pump_state.is_running = True
            self.pump_state_changed.emit(
                address, f"Running at {rate_ml_per_min} ml/min"
            )
            logger.info(f"Pump {address:#x} flow started: {rate_ml_per_min} ml/min")

        return result is not None

    def stop(self, address: Optional[int] = None) -> bool:
        """Stop pump immediately.

        Args:
            address: Pump address (None = broadcast to all)

        Returns:
            True if successful

        """
        target = address if address is not None else PumpAddress.BROADCAST
        result = self._send_command(target, CMD_STOP)

        if result:
            if address and address in self.pumps:
                self.pumps[address].flow_rate_ml_per_min = 0.0
                self.pumps[address].is_running = False
                self.pump_state_changed.emit(address, "Stopped")
            else:
                # Broadcast - update all pumps
                for pump_state in self.pumps.values():
                    pump_state.flow_rate_ml_per_min = 0.0
                    pump_state.is_running = False

            logger.info(f"Pump(s) stopped: {target:#x}")

        return result is not None

    def set_flow_rate(
        self,
        address: int,
        rate_ml_per_min: float,
    ) -> bool:
        """Change flow rate while running.

        Args:
            address: Pump address
            rate_ml_per_min: New flow rate in ml/min

        Returns:
            True if successful

        """
        if address not in self.pumps:
            return False

        rate_ml_per_sec = abs(rate_ml_per_min) / 60.0
        cmd = f"V{rate_ml_per_sec:.3f},1R".encode()
        result = self._send_command(address, cmd)

        if result:
            self.pumps[address].flow_rate_ml_per_min = rate_ml_per_min
            logger.debug(
                f"Pump {address:#x} flow rate changed to {rate_ml_per_min} ml/min"
            )

        return result is not None

    # ========================================================================
    # Status and Diagnostics
    # ========================================================================

    def is_busy(self, address: int) -> bool:
        """Check if pump is executing a command.

        Args:
            address: Pump address

        Returns:
            True if pump is busy

        """
        response = self._send_command(address, CMD_QUERY_BUSY)

        if response:
            try:
                # Bit 5 (0x20) = 1 means idle, 0 means busy
                status = (
                    response[0] if isinstance(response[0], int) else ord(response[0])
                )
                return (status & 0x20) == 0
            except (IndexError, TypeError) as e:
                logger.error(f"Failed to parse busy status: {e}")

        return False

    def wait_until_idle(
        self,
        address: int,
        timeout: float = 30.0,
        check_interval: float = 0.1,
    ) -> bool:
        """Wait for pump to finish current operation.

        Args:
            address: Pump address
            timeout: Maximum wait time in seconds
            check_interval: Status check interval in seconds

        Returns:
            True if pump became idle

        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.is_busy(address):
                return True
            time.sleep(check_interval)

        logger.warning(f"Pump {address:#x} did not become idle within {timeout}s")
        return False

    def get_error_status(self, address: int) -> int:
        """Query pump error status.

        Args:
            address: Pump address

        Returns:
            Error code (see PumpError enum)

        """
        response = self._send_command(address, CMD_QUERY_ERROR)

        if response:
            try:
                error_code = int(bytes(response[1:]).decode().strip())
                if address in self.pumps:
                    self.pumps[address].last_error = error_code
                    if error_code != PumpError.NO_ERROR:
                        self.pumps[address].error_count += 1
                        error_name = (
                            PumpError(error_code).name
                            if error_code in PumpError.__members__.values()
                            else "UNKNOWN"
                        )
                        logger.warning(
                            f"Pump {address:#x} error: {error_name} ({error_code:#x})"
                        )
                        self.error_occurred.emit(address, error_name)
                return error_code
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse error status: {e}")

        return PumpError.NO_ERROR

    def clear_errors(self, address: int) -> bool:
        """Clear pump error state.

        Args:
            address: Pump address

        Returns:
            True if successful

        """
        result = self._send_command(address, CMD_CLEAR_ERROR)

        if result and address in self.pumps:
            self.pumps[address].last_error = PumpError.NO_ERROR
            logger.info(f"Pump {address:#x} errors cleared")

        return result is not None

    def get_pump_state(self, address: int) -> Optional[PumpState]:
        """Get complete state of a pump.

        Args:
            address: Pump address

        Returns:
            PumpState object or None if address invalid

        """
        return self.pumps.get(address)

    def get_diagnostic_info(self, address: int) -> dict[str, Any]:
        """Get comprehensive diagnostic information.

        Args:
            address: Pump address

        Returns:
            Dictionary with diagnostic data

        """
        if address not in self.pumps:
            return {}

        pump_state = self.pumps[address]

        # Update live status
        position = self.get_syringe_position(address)
        valve_port = self.get_valve_position(address)
        error_code = self.get_error_status(address)
        is_busy = self.is_busy(address)

        return {
            "address": f"{address:#x}",
            "syringe_position_steps": position,
            "syringe_volume_ul": pump_state.syringe.current_volume_ul,
            "syringe_capacity_ul": pump_state.syringe.max_volume_ul,
            "syringe_remaining_ul": pump_state.syringe.remaining_volume_ul,
            "valve_port": valve_port,
            "valve_move_count": pump_state.valve.move_count,
            "flow_rate_ml_per_min": pump_state.flow_rate_ml_per_min,
            "is_running": pump_state.is_running,
            "is_busy": is_busy,
            "last_error": error_code,
            "error_count": pump_state.error_count,
            "total_dispensed_ul": pump_state.total_volume_dispensed_ul,
            "total_aspirated_ul": pump_state.total_volume_aspirated_ul,
        }

    # ========================================================================
    # High-Level Protocols
    # ========================================================================

    async def auto_prime(
        self,
        address: int,
        cycles: int = 3,
        volume_per_cycle_ul: float = 4000,
        speed: float = 50.0,
    ) -> bool:
        """Automatically prime pump and tubing.

        Args:
            address: Pump address
            cycles: Number of fill/empty cycles
            volume_per_cycle_ul: Volume to move per cycle
            speed: Flow speed in ml/min

        Returns:
            True if successful

        """
        logger.info(f"Starting auto-prime for pump {address:#x}: {cycles} cycles")
        self._current_operation = "auto_prime"

        try:
            for cycle in range(cycles):
                # Update progress
                progress = int((cycle / cycles) * 100)
                self.operation_progress.emit("Priming", progress)

                # Aspirate
                if not self.aspirate(address, volume_per_cycle_ul, speed):
                    return False
                self.wait_until_idle(address)

                # Dispense
                if not self.dispense(address, volume_per_cycle_ul, speed):
                    return False
                self.wait_until_idle(address)

                logger.debug(f"Prime cycle {cycle + 1}/{cycles} complete")

            self.operation_progress.emit("Priming", 100)
            logger.info(f"Auto-prime complete for pump {address:#x}")
            return True

        except Exception as e:
            logger.exception(f"Auto-prime failed: {e}")
            return False
        finally:
            self._current_operation = ""

    async def purge_line(
        self,
        address: int,
        volume_ul: float = 5000,
        speed: float = FLUSH_FLOW_RATE,
    ) -> bool:
        """Fast flush of pump line.

        Args:
            address: Pump address
            volume_ul: Volume to flush
            speed: Flush speed in ml/min

        Returns:
            True if successful

        """
        logger.info(f"Purging pump {address:#x} line: {volume_ul} µL at {speed} ml/min")

        try:
            # Ensure syringe has liquid
            if self.pumps[address].syringe.current_volume_ul < volume_ul:
                logger.info("Filling syringe before purge")
                if not self.aspirate(address, volume_ul, speed):
                    return False
                self.wait_until_idle(address)

            # Dispense at high speed
            if not self.dispense(address, volume_ul, speed):
                return False
            self.wait_until_idle(address)

            logger.info(f"Line purge complete for pump {address:#x}")
            return True

        except Exception as e:
            logger.exception(f"Line purge failed: {e}")
            return False

    async def regenerate_sequence(
        self,
        contact_time: float = 45.0,
        flow_rate: float = DEFAULT_FLOW_RATE,
        valve_controller: Any = None,
    ) -> bool:
        """Execute regeneration sequence (compatible with existing code).

        Args:
            contact_time: Reagent contact time in seconds
            flow_rate: Flow rate in ml/min
            valve_controller: Optional KNX valve controller

        Returns:
            True if successful

        """
        logger.info("Starting regeneration sequence")
        self._current_operation = "regenerate"

        try:
            # Stop pumps
            self.stop()

            # Build complex command (maintains compatibility)
            rate_ml_per_sec = flow_rate / 60.0
            cmd = (
                "IS15A181490"  # Initial sequence
                "OV4.167,1A0"  # Pre-flow setup
                "IS15A181490"  # Reset
                f"OV{rate_ml_per_sec:.3f},1A0R"  # Set flow rate
            ).encode()

            if not self._send_command(PumpAddress.BROADCAST, cmd):
                return False

            # Progress tracking
            int(67_000 + 1125 * contact_time)
            self.operation_progress.emit("Regenerating", 0)

            # Pre-flow wait
            await asyncio.sleep(REGENERATION_PREFLOW_TIME)
            self.operation_progress.emit("Regenerating", 30)

            # Valve control for contact time
            if valve_controller:
                valve_controller.knx_six(state=1, ch=1)

            await asyncio.sleep(contact_time)
            self.operation_progress.emit("Regenerating", 60)

            if valve_controller:
                valve_controller.knx_six(state=0, ch=1)

            # Fast flush
            fast_rate = FAST_FLUSH_RATE / 60.0
            self._send_command(PumpAddress.BROADCAST, f"V{fast_rate:.3f},1R".encode())
            await asyncio.sleep(FAST_FLUSH_DURATION)
            self.operation_progress.emit("Regenerating", 80)

            # Ultra-fast final flush
            ultra_rate = ULTRA_FAST_FLUSH_RATE
            self._send_command(PumpAddress.BROADCAST, f"V{ultra_rate}R".encode())
            self.operation_progress.emit("Regenerating", 100)

            logger.info("Regeneration sequence complete")
            return True

        except Exception as e:
            logger.exception(f"Regeneration sequence failed: {e}")
            return False
        finally:
            self._current_operation = ""

    async def flush_sequence(
        self,
        flow_rate: float = DEFAULT_FLOW_RATE,
    ) -> bool:
        """Execute flush sequence (compatible with existing code).

        Args:
            flow_rate: Flow rate in ml/min

        Returns:
            True if successful

        """
        logger.info("Starting flush sequence")
        self._current_operation = "flush"

        try:
            # Stop pumps
            self.stop()

            # Build command sequence
            rate_ml_per_sec = flow_rate / 60.0
            cmd = (
                "IS12A181490"  # Initial sequence
                "OS15A0"  # Flush prep
                "IS12A181490"  # Reset
                f"OV{rate_ml_per_sec:.3f},1A0R"  # Set flow rate
            ).encode()

            if not self._send_command(PumpAddress.BROADCAST, cmd):
                return False

            self.operation_progress.emit("Flushing", 0)

            # Preparation wait
            await asyncio.sleep(FLUSH_PREP_TIME)
            self.operation_progress.emit("Flushing", 30)

            # Fast flush cycles
            for cycle in range(2):
                # Fast flush burst
                fast_rate = FAST_FLUSH_RATE / 60.0
                self._send_command(
                    PumpAddress.BROADCAST, f"V{fast_rate:.3f},1R".encode()
                )
                await asyncio.sleep(FAST_FLUSH_DURATION)

                # Ultra-fast flush
                self._send_command(PumpAddress.BROADCAST, b"V9000R")
                await asyncio.sleep(FLUSH_CYCLE_DURATION)

                progress = 30 + (cycle + 1) * 35
                self.operation_progress.emit("Flushing", progress)

            self.operation_progress.emit("Flushing", 100)
            logger.info("Flush sequence complete")
            return True

        except Exception as e:
            logger.exception(f"Flush sequence failed: {e}")
            return False
        finally:
            self._current_operation = ""

    async def inject_sequence(
        self,
        flow_rate: float = DEFAULT_FLOW_RATE,
        injection_time: float = INJECTION_TIME,
        valve_controller: Any = None,
    ) -> bool:
        """Execute injection sequence (compatible with existing code).

        Args:
            flow_rate: Flow rate in ml/min
            injection_time: Injection duration in seconds
            valve_controller: Optional KNX valve controller

        Returns:
            True if successful

        """
        logger.info(f"Starting injection: {flow_rate} ml/min for {injection_time}s")
        self._current_operation = "inject"

        try:
            # Stop pumps
            self.stop()

            # Build injection command
            rate_ml_per_sec = flow_rate / 60.0
            cmd = f"IS15A181490OV{rate_ml_per_sec:.3f},1A0R".encode()

            if not self._send_command(PumpAddress.BROADCAST, cmd):
                return False

            self.operation_progress.emit("Injecting", 0)

            # Control injection valve
            if valve_controller:
                valve_controller.knx_six(state=1, ch=3)

            # Wait for injection time with progress updates
            steps = 10
            for step in range(steps):
                await asyncio.sleep(injection_time / steps)
                progress = int(((step + 1) / steps) * 100)
                self.operation_progress.emit("Injecting", progress)

            # Close injection valve
            if valve_controller:
                valve_controller.knx_six(state=0, ch=3)

            logger.info("Injection sequence complete")
            return True

        except Exception as e:
            logger.exception(f"Injection sequence failed: {e}")
            return False
        finally:
            self._current_operation = ""

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def log_pump_states(self) -> None:
        """Log current state of all pumps."""
        for address, _pump_state in self.pumps.items():
            diag = self.get_diagnostic_info(address)
            logger.info(
                f"Pump {address:#x}: "
                f"Vol={diag['syringe_volume_ul']:.1f}µL, "
                f"Valve=P{diag['valve_port']}, "
                f"Flow={diag['flow_rate_ml_per_min']:.2f}ml/min, "
                f"Running={diag['is_running']}, "
                f"Errors={diag['error_count']}",
            )
