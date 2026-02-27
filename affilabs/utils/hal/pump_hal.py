"""Pump Hardware Abstraction Layer.

Provides unified interface for Cavro-protocol syringe pumps (Tecan Centris, XP 3000).

Supported Hardware:
- AffiPump bundle (2× Tecan Cavro Centris via FTDI serial, 38400 baud)
- Tecan Cavro XP 3000 (direct FTDI serial, 9600 baud, steps-based)

Features:
- Runtime auto-detection via detect_cavro_pump()
- Low-level command interface via send_command()
- High-level operations via adapter classes
- Consistent HAL pattern with detectors and controllers

Use detect_cavro_pump() to identify connected hardware, then create_pump_hal() to get a
PumpHAL adapter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Pump detection
# ---------------------------------------------------------------------------

# FTDI USB-Serial chip VID used by both AffiPump bundle and direct-connected Cavro pumps
_FTDI_VID = 0x0403
_FTDI_PIDS = {0x6001, 0x6010, 0x6011, 0x6014, 0x6015}  # FT232, FT2232, FT4232, FT232H, FT230X

# Cavro query command — same for both Centris and XP 3000
_CAVRO_STATUS_CMD = b"/1?\r"

# XP 3000 always has exactly 3000 steps full-stroke; position response ≤ 3000
_XP3000_MAX_STEPS = 3000

# Baud rates to probe, in order. Centris = 38400; XP = 9600.
_BAUD_CANDIDATES = [38400, 9600]


@dataclass
class PumpDetectionResult:
    """Result of a pump auto-detection scan."""
    pump_type: str          # "centris" | "xp3000" | "unknown"
    port: str               # e.g. "COM8"
    baud_rate: int          # confirmed baud rate
    num_pumps: int          # number of responding addresses (1 or 2)
    description: str        # human-readable summary


def _probe_port(port: str, baud: int, timeout: float = 0.5) -> tuple[bool, str]:
    """Send a Cavro status query to port at baud. Returns (responded, raw_response)."""
    try:
        import serial
        with serial.Serial(port, baud, timeout=timeout) as s:
            s.reset_input_buffer()
            s.write(_CAVRO_STATUS_CMD)
            time.sleep(0.15)
            raw = s.read(64)
        if not raw:
            return False, ""
        text = raw.decode("ascii", errors="ignore")
        # Valid Cavro response contains the echo of the command and a status byte
        if "/1?" in text or "/0" in text or "`" in text:
            return True, text
        return False, text
    except Exception:
        return False, ""


def _classify_pump(response: str, baud: int) -> str:
    """Determine pump model from response text and baud rate.

    Centris: baud 38400, position reported in µL (can be >3000)
    XP 3000: baud 9600, position in steps (0–3000)
    """
    if baud == 9600:
        return "xp3000"
    if baud == 38400:
        return "centris"
    # Fallback: try to parse position value from response
    # Centris response example: /0`12500\x03  (µL position, can exceed 3000)
    # XP response example:      /0`2400\x03   (steps, always ≤ 3000)
    try:
        import re
        m = re.search(r"`(\d+)", response)
        if m:
            pos = int(m.group(1))
            return "xp3000" if pos <= _XP3000_MAX_STEPS else "centris"
    except Exception:
        pass
    return "unknown"


def detect_cavro_pump(timeout: float = 0.5) -> PumpDetectionResult | None:
    """Auto-detect a connected Cavro-protocol pump on any available serial port.

    Strategy:
    1. List all serial ports with FTDI VID (0x0403) — both AffiPump and direct Cavro pumps
       use FTDI USB-serial chips.
    2. For each candidate port, try 38400 baud (Centris) then 9600 baud (XP 3000).
    3. First port+baud that returns a valid Cavro response is returned.
    4. Pump type inferred from baud rate (38400 → Centris, 9600 → XP 3000).

    Args:
        timeout: Per-port probe timeout in seconds.

    Returns:
        PumpDetectionResult if a pump is found, None if nothing responds.
    """
    try:
        import serial.tools.list_ports
    except ImportError:
        logger.error("pyserial not installed — cannot scan for pumps")
        return None

    ports = list(serial.tools.list_ports.comports())

    # Prioritise FTDI VID ports; fall back to all ports if none found
    ftdi_ports = [p for p in ports if p.vid == _FTDI_VID and (p.pid in _FTDI_PIDS)]
    candidates = ftdi_ports if ftdi_ports else ports

    logger.info(f"[PumpDetect] Scanning {len(candidates)} port(s): "
                f"{[p.device for p in candidates]}")

    for port_info in candidates:
        port = port_info.device
        for baud in _BAUD_CANDIDATES:
            logger.debug(f"[PumpDetect] Probing {port} @ {baud} baud…")
            responded, response = _probe_port(port, baud, timeout=timeout)
            if responded:
                pump_type = _classify_pump(response, baud)
                # Check if address /2 also responds (dual-pump AffiPump bundle)
                num_pumps = 1
                try:
                    import serial as _serial
                    with _serial.Serial(port, baud, timeout=timeout) as s:
                        s.reset_input_buffer()
                        s.write(b"/2?\r")
                        time.sleep(0.15)
                        raw2 = s.read(32)
                    if raw2 and (b"/0" in raw2 or b"`" in raw2):
                        num_pumps = 2
                except Exception:
                    pass

                desc = (f"{pump_type.upper()} × {num_pumps} on {port} @ {baud} baud"
                        f" [{port_info.description}]")
                logger.info(f"[PumpDetect] Found: {desc}")
                return PumpDetectionResult(
                    pump_type=pump_type,
                    port=port,
                    baud_rate=baud,
                    num_pumps=num_pumps,
                    description=desc,
                )

    logger.warning("[PumpDetect] No responding Cavro pump found on any port")
    return None


# ---------------------------------------------------------------------------
# XP 3000 adapter
# ---------------------------------------------------------------------------

class XP3000Adapter:
    """PumpHAL adapter for the Tecan Cavro XP 3000 syringe pump.

    XP 3000 uses steps-based encoding (3000 steps = full stroke).
    Syringe volume must be specified to convert µL ↔ steps.

    Baud rate: 9600 (fixed in XP 3000 firmware).
    Protocol: Cavro ASCII, same command structure as Centris but different units.
    """

    _BAUD     = 9600
    _STEPS    = 3000      # full-stroke steps for XP 3000
    # Speed codes: 0 (fastest ~6000 steps/s) to 40 (slowest ~64 steps/s)
    # Approximate: steps_per_s ≈ 6000 / (code + 1)
    _MIN_CODE = 0
    _MAX_CODE = 40

    def __init__(self, port: str, syringe_ul: float = 1000.0, address: int = 1) -> None:
        """Initialise XP 3000 adapter.

        Args:
            port: COM port, e.g. "COM9"
            syringe_ul: Installed syringe volume in µL (critical for steps↔µL conversion)
            address: Pump address (1–15). Default 1.
        """
        import serial as _serial
        self._serial = _serial.Serial(port, self._BAUD, timeout=1.0)
        self._steps_per_ul = self._STEPS / syringe_ul
        self._ul_per_step  = syringe_ul / self._STEPS
        self._addr = address
        self._port = port

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ul_to_steps(self, ul: float) -> int:
        return max(0, min(self._STEPS, round(ul * self._steps_per_ul)))

    def _speed_code(self, ul_s: float) -> int:
        """Convert µL/s to XP 3000 speed code (0=fastest, 40=slowest)."""
        steps_per_s = max(1.0, ul_s * self._steps_per_ul)
        code = round(6000 / steps_per_s) - 1
        return max(self._MIN_CODE, min(self._MAX_CODE, code))

    def _send(self, cmd: str) -> str:
        full = f"/{self._addr}{cmd}\r"
        self._serial.reset_input_buffer()
        self._serial.write(full.encode("ascii"))
        time.sleep(0.05)
        raw = self._serial.read(64)
        return raw.decode("ascii", errors="ignore")

    # ------------------------------------------------------------------
    # PumpHAL interface
    # ------------------------------------------------------------------

    def send_command(self, address: int, command: bytes) -> bytes:
        cmd_str = command.decode("ascii") if isinstance(command, bytes) else str(command)
        addr = chr(address) if address >= 0x41 else str(address)
        full = f"/{addr}{cmd_str}\r"
        self._serial.reset_input_buffer()
        self._serial.write(full.encode("ascii"))
        time.sleep(0.05)
        return self._serial.read(64)

    def is_available(self) -> bool:
        try:
            resp = self._send("?")
            return "/0" in resp or "`" in resp
        except Exception:
            return False

    def initialize_pumps(self) -> bool:
        """Initialize XP 3000 (home syringe, valve to input)."""
        try:
            # W4 = initialize, move plunger to 0, valve to input side
            resp = self._send("W4R")
            self.wait_until_idle(1, timeout_s=30.0)
            return True
        except Exception as e:
            logger.error(f"[XP3000] Initialize failed: {e}")
            return False

    def aspirate(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        try:
            steps = self._ul_to_steps(volume_ul)
            v = self._speed_code(rate_ul_min / 60.0)  # rate_ul_min → µL/s
            resp = self._send(f"V{v}P{steps}R")
            return "/0" in resp or "`" in resp
        except Exception as e:
            logger.error(f"[XP3000] Aspirate failed: {e}")
            return False

    def dispense(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        try:
            steps = self._ul_to_steps(volume_ul)
            v = self._speed_code(rate_ul_min / 60.0)
            resp = self._send(f"V{v}D{steps}R")
            return "/0" in resp or "`" in resp
        except Exception as e:
            logger.error(f"[XP3000] Dispense failed: {e}")
            return False

    def set_valve_position(self, pump_address: int, port: int) -> bool:
        # XP 3000: I = input (left), O = output (right), B = bypass
        valve_map = {0: "I", 1: "O", 2: "B"}
        cmd = valve_map.get(port, "I")
        try:
            resp = self._send(f"{cmd}R")
            return "/0" in resp or "`" in resp
        except Exception as e:
            logger.error(f"[XP3000] Valve set failed: {e}")
            return False

    def get_syringe_position(self, pump_address: int) -> int | None:
        try:
            import re
            resp = self._send("?")
            m = re.search(r"`(\d+)", resp)
            if m:
                steps = int(m.group(1))
                return round(steps * self._ul_per_step)  # return in µL for HAL consistency
            return None
        except Exception:
            return None

    def wait_until_idle(self, pump_address: int, timeout_s: float = 60.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                resp = self._send("Q")   # Q = poll status without busy-wait
                if "/0" in resp:         # 0x60 = idle
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def close(self) -> None:
        try:
            self._serial.close()
        except Exception:
            pass


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
        """Send raw command via underlying PumpController.

        Converts HAL-style (address, command_bytes) to the AffipumpController
        string format: "/{address_char}{command_str}" (e.g., 0x41, b"TR" → "/ATR").
        """
        if self._controller is None:
            logger.warning("Pump controller not available for send_command")
            return b""
        # Convert integer address + bytes command to Cavro command string
        # Address 0x41='A' (broadcast), 0x42='1' (pump 1), 0x43='2' (pump 2)
        addr_char = chr(address) if address >= 0x41 else str(address)
        cmd_str = command.decode('ascii') if isinstance(command, bytes) else str(command)
        full_cmd = f"/{addr_char}{cmd_str}"
        result = self._controller.send_command(full_cmd)
        return result if isinstance(result, bytes) else (result.encode() if result else b"")

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


def create_pump_hal(
    pump_manager=None,
    detection: PumpDetectionResult | None = None,
    syringe_ul: float = 1000.0,
) -> PumpHAL:
    """Factory function to create the correct PumpHAL adapter.

    Two usage modes:

    Mode 1 — Auto-detect (recommended):
        result = detect_cavro_pump()
        if result:
            pump = create_pump_hal(detection=result)

    Mode 2 — Legacy (existing AffiPump CavroPumpManager):
        pump = create_pump_hal(pump_manager=manager)

    Args:
        pump_manager: Existing CavroPumpManager instance (legacy, AffiPump bundle only).
        detection: PumpDetectionResult from detect_cavro_pump().
        syringe_ul: Syringe volume in µL — required for XP 3000 steps↔µL conversion.

    Returns:
        PumpHAL adapter for the detected or provided hardware.

    Raises:
        ValueError: If neither pump_manager nor detection is provided.
    """
    if detection is not None:
        if detection.pump_type == "xp3000":
            logger.info(f"[PumpHAL] Creating XP3000Adapter on {detection.port} "
                        f"(syringe={syringe_ul} µL)")
            return XP3000Adapter(
                port=detection.port,
                syringe_ul=syringe_ul,
            )
        elif detection.pump_type == "centris":
            # Re-use AffiPump bundle via its own PumpController
            logger.info(f"[PumpHAL] Creating AffipumpAdapter on {detection.port}")
            try:
                from AffiPump.affipump_controller import AffipumpController
                controller = AffipumpController(port=detection.port,
                                                baudrate=detection.baud_rate)
                controller.open()
                # Wrap in a minimal shim that provides the CavroPumpManager interface
                return _AffiPumpDirectAdapter(controller)
            except Exception as e:
                logger.error(f"[PumpHAL] Could not open AffiPump: {e}")
                raise
        else:
            raise ValueError(f"Unsupported pump type from detection: {detection.pump_type}")

    if pump_manager is not None:
        logger.info("[PumpHAL] Creating AffipumpAdapter (legacy pump_manager)")
        return AffipumpAdapter(pump_manager)

    raise ValueError("Provide either pump_manager or detection result to create_pump_hal()")


class _AffiPumpDirectAdapter(AffipumpAdapter):
    """Thin subclass that wraps an AffipumpController directly (no CavroPumpManager)."""

    def __init__(self, controller) -> None:
        # Bypass AffipumpAdapter.__init__ — we have the controller directly
        self._pump = controller
        self._controller = controller
        if self._controller is None:
            raise ValueError("_AffiPumpDirectAdapter requires a live AffipumpController")

    def is_available(self) -> bool:
        return self._controller is not None

    def initialize_pumps(self) -> bool:
        ctrl = self._controller
        if ctrl is None:
            return False
        try:
            ctrl.initialize_pumps()
            return True
        except Exception as e:
            logger.error(f"[AffiPumpDirect] Initialize failed: {e}")
            return False

    def aspirate(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        ctrl = self._controller
        if ctrl is None:
            return False
        try:
            ctrl.aspirate(pump_num=pump_address,
                          volume_ul=volume_ul,
                          speed_ul_s=rate_ul_min / 60.0)
            return True
        except Exception as e:
            logger.error(f"[AffiPumpDirect] Aspirate failed: {e}")
            return False

    def dispense(self, pump_address: int, volume_ul: float, rate_ul_min: float) -> bool:
        ctrl = self._controller
        if ctrl is None:
            return False
        try:
            ctrl.dispense(pump_num=pump_address,
                          speed_ul_s=rate_ul_min / 60.0)
            return True
        except Exception as e:
            logger.error(f"[AffiPumpDirect] Dispense failed: {e}")
            return False

    def close(self) -> None:
        ctrl = self._controller
        if ctrl is None:
            return
        try:
            ctrl.close()
        except Exception:
            pass
