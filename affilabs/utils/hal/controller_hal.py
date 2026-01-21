"""Controller Hardware Abstraction Layer.

Provides unified interface for supported controller types:
- PicoP4SPR (affinite_P4SPR)
- PicoEZSPR (affinite_P4PRO)

Features:
- Type-safe capability queries
- Consistent API across controller types
- Servo position management

This is an ADDITIVE layer - does not modify existing controller implementations.
Use create_controller_hal() factory function to wrap existing controller instances.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ControllerHAL(Protocol):
    """Unified controller interface abstracting device-specific implementations.

    Provides:
    - LED control (on/off/intensity/batch operations)
    - Polarizer control (for devices that support it)
    - Type-safe capability queries (eliminates string-based device type checks)
    - Temperature monitoring
    - Pump control (for EZSPR devices)
    """

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        """Turn on a specific LED channel.

        Args:
            ch: Channel identifier ('a', 'b', 'c', 'd')

        Returns:
            True if command succeeded

        """
        ...

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels.

        Returns:
            True if command succeeded

        """
        ...

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        """Set LED channel intensity.

        Args:
            ch: Channel identifier ('a', 'b', 'c', 'd')
            raw_val: Intensity value (0-255)

        Returns:
            True if command succeeded

        """
        ...

    def set_batch_intensities(
        self,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        d: int = 0,
    ) -> bool:
        """Set all LED intensities in a single batch command (if supported).

        Falls back to sequential commands for controllers without batch support.

        Args:
            a: Intensity for LED A (0-255)
            b: Intensity for LED B (0-255)
            c: Intensity for LED C (0-255)
            d: Intensity for LED D (0-255)

        Returns:
            True if all commands succeeded

        """
        ...

    def led_rank_sequence(
        self,
        test_intensity: int = 128,
        settling_ms: int = 45,
        dark_ms: int = 5,
        timeout_s: float = 10.0,
    ):
        """Execute firmware-side LED ranking sequence for fast calibration (V2.4+).

        This command triggers the firmware to sequence through all 4 LEDs automatically,
        with precise timing control. Python reads spectra when signaled by firmware.

        Args:
            test_intensity: LED test brightness (0-255, default 128)
            settling_ms: LED settling time in ms (default 45ms)
            dark_ms: Dark time between channels in ms (default 5ms)
            timeout_s: Maximum time to wait for sequence (default 10s)

        Yields:
            tuple: (channel, signal) where signal is 'READY', 'READ', or 'DONE'

        Returns:
            Generator yielding (channel, signal) tuples, or None if not supported

        """
        ...

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode.

        Args:
            mode: 's' for S-polarization, 'p' for P-polarization

        Returns:
            True if command succeeded (False if polarizer not supported)

        """
        ...

    def get_polarizer_position(self) -> dict[str, Any]:
        """Get current polarizer position.

        Returns:
            Dictionary with 's' and 'p' positions, or empty dict if not supported

        """
        ...

    def servo_move_calibration_only(
        self,
        s: int | None = None,
        p: int | None = None,
    ) -> bool:
        """Move servo to position without firmware lock (calibration mode).

        Args:
            s: S-mode position (1-255)
            p: P-mode position (1-255)

        Returns:
            True if command succeeded (False if polarizer not supported)

        """
        ...

    def servo_move_raw_pwm(self, pwm: int) -> bool:
        """Move servo to arbitrary PWM position (CALIBRATION SWEEPS ONLY).

        This method is for servo calibration workflows that need to scan
        arbitrary PWM positions (1-255) to find optimal S and P angles.

        Args:
            pwm: Raw PWM value (1-255)

        Returns:
            True if command succeeded (False if polarizer not supported)

        """
        ...

    def servo_set(self, s: int | None = None, p: int | None = None) -> bool:
        """Set and lock servo positions in firmware RAM.

        Args:
            s: S-mode position (1-255)
            p: P-mode position (1-255)

        Returns:
            True if command succeeded (False if polarizer not supported)

        """
        ...

    # LED Query
    def get_all_led_intensities(self) -> dict[str, int] | None:
        """Query current LED intensities from device (firmware V1.1+).

        Returns:
            Dict with keys 'a', 'b', 'c', 'd' and intensity values (0-255),
            or None if not supported or query failed

        """
        ...

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        """Get the underlying device type string.

        Returns:
            Device type: 'PicoP4SPR' (affinite_P4SPR) or 'PicoEZSPR' (affinite_P4PRO)

        """
        ...

    def get_firmware_version(self) -> str:
        """Get firmware version if available.

        Returns:
            Version string (e.g., 'V1.4') or empty string if not available

        """
        ...

    def get_temperature(self) -> float:
        """Get device temperature in Celsius.

        Returns:
            Temperature in °C, or -1 if not supported

        """
        ...

    # Type-safe capability queries (eliminates string-based device checks)
    @property
    def supports_polarizer(self) -> bool:
        """Check if device has polarizer control capability."""
        ...

    @property
    def supports_batch_leds(self) -> bool:
        """Check if device supports batch LED intensity commands."""
        ...

    @property
    def supports_rank_sequence(self) -> bool:
        """Check if device supports firmware-controlled LED rank sequence (V2.4+)."""
        ...

    @property
    def supports_pump(self) -> bool:
        """Check if device has pump control capability (EZSPR only)."""
        ...

    @property
    def supports_firmware_update(self) -> bool:
        """Check if device supports firmware updates."""
        ...

    @property
    def channel_count(self) -> int:
        """Get number of LED channels (typically 4)."""
        ...

    # Pump Control (EZSPR-specific)
    def get_pump_corrections(self) -> tuple[float, float] | None:
        """Get pump correction factors (EZSPR only).

        Returns:
            Tuple of (pump1_correction, pump2_correction) or None if not supported

        """
        ...

    def set_pump_corrections(
        self,
        pump_1_correction: float,
        pump_2_correction: float,
    ) -> bool:
        """Set pump correction factors (EZSPR only).

        Args:
            pump_1_correction: Correction factor for pump 1
            pump_2_correction: Correction factor for pump 2

        Returns:
            True if command succeeded (False if not supported)

        """
        ...

    # Valve and Internal Pump Control (EZSPR-specific KNX methods)
    def knx_six(self, ch: int, state: int, timeout_seconds: int | None = None) -> bool:
        """Control 6-port valve for single channel with optional safety timeout (EZSPR only).

        Args:
            ch: Channel number (1 for KC1, 2 for KC2)
            state: 0 for LOAD, 1 for TO SENSOR (inject)
            timeout_seconds: Optional timeout for safety fallback.
                           - If None (default): NO timeout - valve stays open (for calculated contact times)
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    def knx_six_both(self, state: int, timeout_seconds: int | None = None) -> bool:
        """Control both 6-port valves simultaneously with optional safety timeout (EZSPR only).

        Args:
            state: 0 for LOAD, 1 for TO SENSOR (inject)
            timeout_seconds: Optional timeout for safety fallback.
                           - If None (default): NO timeout - valves stay open (for calculated contact times)
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    def knx_three_both(self, state: int) -> bool:
        """Control both 3-way valves simultaneously (EZSPR only).

        Args:
            state: 0 for A/C channels, 1 for B/D channels

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    def knx_start(self, rate: int, ch: int) -> bool:
        """Start internal pump via RPi GPIO (EZSPR only).

        Args:
            rate: Flow rate in µL/min (50, 100, 200, or 500 for flush)
            ch: Channel number (1 for KC1, 2 for KC2)

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    def knx_stop(self, ch: int) -> bool:
        """Stop internal pump via RPi GPIO (EZSPR only).

        Args:
            ch: Channel number (1 for KC1, 2 for KC2)

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    # Connection Management
    def open(self) -> bool:
        """Open connection to controller.

        Returns:
            True if connection established

        """
        ...

    def close(self) -> None:
        """Close connection to controller."""
        ...

    def is_connected(self) -> bool:
        """Check if controller is connected and ready.

        Returns:
            True if device is connected and operational

        """
        ...


class PicoP4SPRAdapter:
    """Adapter wrapping PicoP4SPR controller to provide ControllerHAL interface."""

    def __init__(self, controller, device_config=None):
        """Initialize adapter with existing PicoP4SPR controller instance.

        Args:
            controller: PicoP4SPR instance from affilabs.utils.controller
            device_config: Optional DeviceConfiguration for servo position management

        """
        self._ctrl = controller
        self._device_type = "PicoP4SPR"
        self._device_config = device_config

    @property
    def _ser(self):
        """Expose serial port for low-level calibration operations."""
        return self._ctrl._ser

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(
        self,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        d: int = 0,
    ) -> bool:
        # PicoP4SPR supports batch command
        return self._ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)

    def led_rank_sequence(
        self,
        test_intensity: int = 128,
        settling_ms: int = 45,
        dark_ms: int = 5,
        timeout_s: float = 10.0,
    ):  # type: ignore
        """Execute firmware-side LED ranking sequence (V2.4+)."""
        # PicoP4SPR V2.4 supports rank command
        return self._ctrl.led_rank_sequence(
            test_intensity=test_intensity,
            settling_ms=settling_ms,
            dark_ms=dark_ms,
            timeout_s=timeout_s,
        )

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return self._ctrl.set_mode(mode) or False

    def get_polarizer_position(self) -> dict[str, Any]:
        """Get polarizer positions from device_config (NOT EEPROM).

        ========================================================================
        CRITICAL: POSITIONS FROM DEVICE_CONFIG ONLY
        ========================================================================
        This function returns positions from device_config.json.
        Legacy servo_get() EEPROM reading has been DELETED.

        Positions are loaded at startup and NEVER changed at runtime.
        ========================================================================
        """
        try:
            # Return positions from device_config (passed via constructor)
            # For now, return empty dict - caller should use device_config directly
            logger.warning(
                "get_polarizer_position() called - use device_config.get_servo_positions() instead",
            )
            return {}
        except Exception as e:
            logger.error(f"get_polarizer_position error: {e}")
            return {}

    def servo_move_calibration_only(
        self,
        s: int | None = None,
        p: int | None = None,
    ) -> bool:
        """Move servo to position without firmware lock (calibration mode)."""
        return self._ctrl.servo_move_calibration_only(s=s, p=p) or False

    def servo_move_raw_pwm(self, pwm: int) -> bool:
        """Move servo to arbitrary PWM position for calibration sweeps.

        IMPORTANT: The firmware sv command expects DEGREES (0-180), not PWM values!
        This method converts PWM (1-255) to degrees (0-180) before sending.

        PWM to Degrees conversion:
        - PWM 1 → 0°
        - PWM 128 → 90°
        - PWM 255 → 180°

        Args:
            pwm: PWM value (1-255) - will be converted to degrees

        Returns:
            True if command succeeded
        """
        try:
            # Delegate to actual controller which handles V2.4 servo:ANGLE,DURATION format
            if hasattr(self._ctrl, 'servo_move_raw_pwm'):
                return self._ctrl.servo_move_raw_pwm(pwm)

            # Fallback for old controllers
            if not (1 <= pwm <= 255):
                return False

            # Convert PWM (1-255) to degrees (0-180)
            degrees = int((pwm - 1) * 180 / 254)
            degrees = max(0, min(180, degrees))

            # V2.4 firmware format: servo:ANGLE,DURATION
            cmd = f"servo:{degrees},500\n"
            if self._ser is None or not self._ser.is_open:
                return False

            # Enable servo power first (V2.4 firmware requirement)
            self._ser.write(b"sp1\n")
            time.sleep(0.05)
            self._ser.read(1)  # Consume enable response

            # Send movement command
            self._ser.write(cmd.encode())
            time.sleep(0.05)
            response = self._ser.read(1)

            # V2.4 firmware responds with '1', older with '6'
            if response in (b"1", b"6"):
                time.sleep(0.6)  # Wait for movement
                return True
            return False
        except Exception:
            return False

    def servo_set(self, s: int | None = None, p: int | None = None) -> bool:
        """Set and lock servo positions in firmware RAM.

        NOTE: PicoP4SPR doesn't have separate firmware RAM lock like PicoEZSPR.
        Just move servo to position - firmware remembers last position.
        """
        return self._ctrl.servo_move_calibration_only(s=s, p=p) or False

    # LED Query
    def get_all_led_intensities(self) -> dict[str, int] | None:
        """Query current LED intensities from device (firmware V1.1+)."""
        if hasattr(self._ctrl, "get_all_led_intensities"):
            return self._ctrl.get_all_led_intensities()
        return None

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return getattr(self._ctrl, "version", "")

    def get_temperature(self) -> float:
        try:
            return self._ctrl.get_temp()
        except Exception:
            return -1.0

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return True  # P4SPR has polarizer

    @property
    def supports_batch_leds(self) -> bool:
        return True  # P4SPR has batch command

    @property
    def supports_rank_sequence(self) -> bool:
        return True  # P4SPR V2.4+ has firmware rank command

    @property
    def supports_pump(self) -> bool:
        return False  # P4SPR does not have pump

    @property
    def supports_firmware_update(self) -> bool:
        return False  # P4SPR firmware update not implemented

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control (not supported)
    def get_pump_corrections(self) -> tuple[float, float] | None:
        return None

    def set_pump_corrections(
        self,
        pump_1_correction: float,
        pump_2_correction: float,
    ) -> bool:
        return False

    # Valve and Internal Pump Control (not supported on P4SPR)
    def knx_six(self, ch: int, state: int, timeout_seconds: int | None = None) -> bool:
        return False

    def knx_six_both(self, state: int, timeout_seconds: int | None = None) -> bool:
        return False

    def knx_three_both(self, state: int) -> bool:
        return False

    def knx_start(self, rate: int, ch: int) -> bool:
        return False

    def knx_stop(self, ch: int) -> bool:
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl._ser is not None and self._ctrl._ser.is_open


class PicoEZSPRAdapter:
    """Adapter wrapping PicoEZSPR controller to provide ControllerHAL interface.

    PicoEZSPR handles EZSPR and AFFINITE firmware only (NOT P4PRO).
    P4PRO uses the separate PicoP4PROAdapter.
    """

    def __init__(self, controller):
        """Initialize adapter with existing PicoEZSPR controller instance.

        Args:
            controller: PicoEZSPR instance from affilabs.utils.controller

        """
        self._ctrl = controller
        # Use actual firmware ID to determine device type (EZSPR vs AFFINITE)
        # P4PRO is NOT handled here - it uses PicoP4PRO class
        if hasattr(controller, 'firmware_id') and controller.firmware_id:
            fw_id = controller.firmware_id.upper()
            if 'AFFINITE' in fw_id:
                self._device_type = "PicoAFFINITE"  # Affinite has integrated kinetics
            else:
                self._device_type = "PicoEZSPR"  # Default EZSPR (2 LEDs)
        else:
            # Fallback if firmware_id not available
            self._device_type = "PicoEZSPR"

    @property
    def _ser(self):
        """Expose serial port for low-level calibration operations."""
        return self._ctrl._ser

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(
        self,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        d: int = 0,
    ) -> bool:
        # EZSPR doesn't have batch command - fall back to sequential
        success = True
        if a > 0:
            success &= self.set_intensity("a", a)
        if b > 0:
            success &= self.set_intensity("b", b)
        if c > 0:
            success &= self.set_intensity("c", c)
        if d > 0:
            success &= self.set_intensity("d", d)
        return success

    def led_rank_sequence(
        self,
        test_intensity: int = 128,
        settling_ms: int = 45,
        dark_ms: int = 5,
        timeout_s: float = 10.0,
    ):  # type: ignore
        """EZSPR does not support firmware rank sequence - returns None."""
        return None

    # Polarizer Control (NOT SUPPORTED on EZSPR/AFFINITE)
    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode - NOT SUPPORTED on EZSPR/AFFINITE (use P4PRO)."""
        return False

    def get_polarizer_position(self) -> dict[str, Any]:
        """Get current polarizer position - NOT SUPPORTED."""
        return {}

    def servo_move_calibration_only(
        self,
        s: int | None = None,
        p: int | None = None,
    ) -> bool:
        """Move servo - NOT SUPPORTED on EZSPR/AFFINITE."""
        return False

    def servo_move_raw_pwm(self, pwm: int) -> bool:
        """Move servo - NOT SUPPORTED on EZSPR/AFFINITE."""
        return False

    def servo_set(self, s: int | None = None, p: int | None = None) -> bool:
        """Set servo positions - NOT SUPPORTED on EZSPR/AFFINITE."""
        return False

    def set_servo_positions(self, s: int, p: int) -> None:
        """Load servo positions - NOT SUPPORTED on EZSPR/AFFINITE."""
        pass

    # LED Query
    def get_all_led_intensities(self) -> dict[str, int] | None:
        """Query current LED intensities from device (if supported)."""
        if hasattr(self._ctrl, "get_all_led_intensities"):
            return self._ctrl.get_all_led_intensities()
        return None

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return getattr(self._ctrl, "version", "")

    def get_temperature(self) -> float:
        return -1.0  # EZSPR doesn't have temp sensor

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        """EZSPR/AFFINITE do NOT have polarizer/servo support (P4PRO does)."""
        return False  # EZSPR/AFFINITE have no servo

    @property
    def supports_batch_leds(self) -> bool:
        return False  # EZSPR doesn't have batch command

    @property
    def supports_rank_sequence(self) -> bool:
        return False  # EZSPR doesn't have firmware rank command

    @property
    def supports_pump(self) -> bool:
        return True  # EZSPR has pump control

    @property
    def supports_firmware_update(self) -> bool:
        return True  # EZSPR supports firmware updates

    @property
    def channel_count(self) -> int:
        return 2  # EZSPR/AFFINITE have 2 LED channels (not 4 like P4PRO)

    # Pump Control
    def get_pump_corrections(self) -> tuple[float, float] | None:
        return self._ctrl.get_pump_corrections()

    def set_pump_corrections(
        self,
        pump_1_correction: float,
        pump_2_correction: float,
    ) -> bool:
        return self._ctrl.set_pump_corrections(pump_1_correction, pump_2_correction)

    # Valve Control (KNX methods for pump/valve operations)
    def knx_six(self, ch: int, state: int, timeout_seconds: int | None = None) -> bool:
        """Control 6-port valve for single channel with optional safety timeout.

        Args:
            ch: Channel number (1 for KC1, 2 for KC2)
            state: 0 for LOAD, 1 for TO SENSOR (inject)
            timeout_seconds: Optional timeout for safety fallback.
                           - If None (default): NO timeout - valve stays open (for calculated contact times)
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations

        Returns:
            True if command succeeded
        """
        if hasattr(self._ctrl, "knx_six"):
            return self._ctrl.knx_six(state, ch, timeout_seconds=timeout_seconds)
        return False

    def knx_six_both(self, state: int, timeout_seconds: int | None = None) -> bool:
        """Control both 6-port valves simultaneously with optional safety timeout.

        Args:
            state: 0 for LOAD, 1 for TO SENSOR (inject)
            timeout_seconds: Optional timeout for safety fallback.
                           - If None (default): NO timeout - valves stay open (for calculated contact times)
                           - If specified (e.g., 300): Safety timeout for manual/unknown operations

        Returns:
            True if command succeeded
        """
        if hasattr(self._ctrl, "knx_six_both"):
            return self._ctrl.knx_six_both(state, timeout_seconds=timeout_seconds)
        return False

    def knx_three_both(self, state: int) -> bool:
        """Control both 3-way valves simultaneously.

        Args:
            state: 0 for A/C channels, 1 for B/D channels

        Returns:
            True if command succeeded
        """
        if hasattr(self._ctrl, "knx_three_both"):
            return self._ctrl.knx_three_both(state)
        return False

    def knx_start(self, rate: int, ch: int) -> bool:
        """Start internal pump (RPi GPIO).

        Args:
            rate: Flow rate in µL/min (50, 100, 200, or 500 for flush)
            ch: Channel number (1 for KC1, 2 for KC2)

        Returns:
            True if command succeeded
        """
        if hasattr(self._ctrl, "knx_start"):
            return self._ctrl.knx_start(rate, ch)
        return False

    def knx_stop(self, ch: int) -> bool:
        """Stop internal pump (RPi GPIO).

        Args:
            ch: Channel number (1 for KC1, 2 for KC2)

        Returns:
            True if command succeeded
        """
        if hasattr(self._ctrl, "knx_stop"):
            return self._ctrl.knx_stop(ch)
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl.valid()


# ============================================================================
# PicoP4PRO Adapter - Standalone P4PRO with 4 LEDs + Servo
# ============================================================================


class PicoP4PROAdapter:
    """Hardware Abstraction Layer for P4PRO controller.

    P4PRO is a standalone controller with:
    - 4 LED channels (A, B, C, D)
    - Servo-controlled polarizer
    - 6-port and 3-way valve control
    - NO batch LED command support (use individual set_intensity)
    - Uses 'sv' command for fast RAM-only servo moves
    """

    def __init__(self, ctrl, device_config):
        """Initialize P4PRO adapter.

        Args:
            ctrl: PicoP4PRO controller instance
            device_config: DeviceConfiguration instance
        """
        self._ctrl = ctrl
        self._device_config = device_config
        self._device_type = "PicoP4PRO"  # Fixed type, no firmware detection needed

        # Load servo positions from device config if available
        if device_config:
            try:
                hw_settings = device_config.get_hardware()
                s_pos = hw_settings.get("servo_s_position")
                p_pos = hw_settings.get("servo_p_position")
                if s_pos is not None and p_pos is not None:
                    self._ctrl.set_servo_positions(s_pos, p_pos)
            except Exception:
                pass

    # LED Control
    def enable_multi_led(self, a: bool = True, b: bool = True, c: bool = True, d: bool = True) -> bool:
        """Enable multiple LEDs using lm:A,B,C,D command.

        CRITICAL: P4PRO firmware requires this command before LEDs respond to intensity.
        """
        return self._ctrl.enable_multi_led(a, b, c, d)

    def turn_on_channel(self, ch: str) -> bool:
        """Enable LED channel before setting intensity."""
        return self._ctrl.turn_on_channel(ch)

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels."""
        return self._ctrl.turn_off_channels()

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        """Set LED intensity for a single channel."""
        return self._ctrl.set_intensity(ch, raw_val)

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        """Set all 4 LED intensities using batch command.

        CRITICAL: Channels must be enabled first with turn_on_channel() before
        the batch command will work.
        """
        return self._ctrl.set_batch_intensities(a, b, c, d)

    def led_rank_sequence(
        self,
        test_intensity: int = 128,
        settling_ms: int = 45,
        dark_ms: int = 5,
        timeout_s: float = 10.0,
    ):  # type: ignore
        """P4PRO does not support firmware rank sequence - returns None."""
        return None

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode (S or P) using stored positions."""
        return self._ctrl.set_mode(mode)

    def get_polarizer_position(self) -> dict[str, Any]:
        """Get current polarizer position."""
        return {}  # P4PRO doesn't report position

    def servo_move_calibration_only(
        self,
        s: int | None = None,
        p: int | None = None,
    ) -> bool:
        """Move servo to S or P position."""
        if s is not None:
            return self._ctrl.servo_move_raw_pwm(s)
        if p is not None:
            return self._ctrl.servo_move_raw_pwm(p)
        return False

    def servo_move_raw_pwm(self, pwm: int) -> bool:
        """Move servo to raw PWM position."""
        return self._ctrl.servo_move_raw_pwm(pwm)

    def servo_set(self, s: int | None = None, p: int | None = None) -> bool:
        """Set servo positions (not applicable for P4PRO - use set_servo_positions)."""
        return False

    def set_servo_positions(self, s: int, p: int) -> None:
        """Load servo positions into controller for set_mode() usage."""
        self._ctrl.set_servo_positions(s, p)

    # LED Query
    def get_all_led_intensities(self) -> dict[str, int] | None:
        """Query current LED intensities (P4PRO doesn't report state)."""
        return None

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return getattr(self._ctrl, "version", "")

    def get_temperature(self) -> float:
        return self._ctrl.get_temp()

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        """P4PRO has servo-controlled polarizer."""
        return True

    @property
    def supports_batch_leds(self) -> bool:
        """P4PRO has batch LED command support."""
        return True

    @property
    def supports_rank_sequence(self) -> bool:
        """P4PRO doesn't have firmware rank command."""
        return False

    @property
    def supports_pump(self) -> bool:
        """P4PRO doesn't have pump control."""
        return False

    @property
    def supports_firmware_update(self) -> bool:
        """P4PRO supports firmware updates."""
        return True

    @property
    def channel_count(self) -> int:
        """P4PRO has 4 LED channels."""
        return 4

    # Pump Control (NOT SUPPORTED on P4PRO)
    def get_pump_corrections(self) -> tuple[float, float] | None:
        return None

    def set_pump_corrections(
        self,
        pump_1_correction: float,
        pump_2_correction: float,
    ) -> bool:
        return False

    # Valve Control
    def knx_six(self, ch: int, state: int, timeout_seconds: int | None = None) -> bool:
        """Control 6-port valve for single channel with optional safety timeout."""
        return self._ctrl.knx_six(state, ch, timeout_seconds=timeout_seconds)

    def knx_six_both(self, state: int, timeout_seconds: int | None = None) -> bool:
        """Control both 6-port valves simultaneously with optional safety timeout."""
        return self._ctrl.knx_six_both(state, timeout_seconds=timeout_seconds)

    def knx_three_both(self, state: int) -> bool:
        """Control both 3-way valves simultaneously."""
        return self._ctrl.knx_three_both(state)

    def knx_start(self, rate: int, ch: int) -> bool:
        """Start internal pump (NOT SUPPORTED on P4PRO)."""
        return False

    def knx_stop(self, ch: int) -> bool:
        """Stop internal pump (NOT SUPPORTED on P4PRO)."""
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl.valid()

    # Direct serial access for calibration
    @property
    def _ser(self):
        """Expose serial port for low-level calibration commands."""
        return self._ctrl._ser


# ============================================================================
# NOTE: ArduinoAdapter and KineticAdapter classes REMOVED
# Only PicoP4SPR, PicoP4PRO, and PicoEZSPR controllers are supported.
# ============================================================================


def create_controller_hal(controller, device_config=None) -> ControllerHAL:
    """Factory function to create appropriate HAL adapter for a controller instance.

    This is the main entry point for using the Controller HAL. Pass any existing
    controller instance and get back a ControllerHAL interface with type-safe
    capability queries.

    Supported Controllers:
        - PicoP4SPR (affinite_P4SPR) - 4-channel with polarizer control
        - PicoP4PRO (affinite_P4PRO) - 4-channel with servo polarizer + valves
        - PicoEZSPR (ezSPR/AFFINITE) - 4-channel with pump control

    Args:
        controller: Controller instance (PicoP4SPR, PicoP4PRO, or PicoEZSPR)
        device_config: Optional DeviceConfiguration for servo position management

    Returns:
        ControllerHAL adapter wrapping the controller

    Raises:
        ValueError: If controller type is not recognized

    Example:
        from affilabs.utils.controller import PicoP4SPR
        from affilabs.utils.hal.controller_hal import create_controller_hal
        from affilabs.utils.device_configuration import DeviceConfiguration

        # Create controller and config
        ctrl = PicoP4SPR()
        ctrl.open()
        device_config = DeviceConfiguration.load('path/to/device_config.json')

        # Wrap with HAL and provide config for servo management
        hal = create_controller_hal(ctrl, device_config)

        # Type-safe capability check (no more string matching!)
        if hal.supports_polarizer:
            hal.set_mode('s')

        # Use batch commands if available
        if hal.supports_batch_leds:
            hal.set_batch_intensities(a=255, b=128, c=64, d=0)

    """
    controller_name = (
        controller.name if hasattr(controller, "name") else type(controller).__name__
    )

    # Map controller name to adapter class - ONLY SUPPORTED CONTROLLERS
    adapter_map = {
        "pico_p4spr": PicoP4SPRAdapter,  # PicoP4SPR / affinite_P4SPR
        "PicoP4SPR": PicoP4SPRAdapter,
        "pico_p4pro": PicoP4PROAdapter,  # PicoP4PRO / standalone P4PRO
        "PicoP4PRO": PicoP4PROAdapter,
        "pico_ezspr": PicoEZSPRAdapter,  # PicoEZSPR / affinite_EZSPR/AFFINITE
        "PicoEZSPR": PicoEZSPRAdapter,
        "EZSPR": PicoEZSPRAdapter,  # Legacy EZSPR name
    }

    adapter_class = adapter_map.get(controller_name)
    if adapter_class is None:
        raise ValueError(f"Unknown controller type: {controller_name}")

    # PicoP4SPR and PicoP4PRO adapters accept device_config parameter
    if adapter_class in (PicoP4SPRAdapter, PicoP4PROAdapter):
        return adapter_class(controller, device_config=device_config)
    return adapter_class(controller)
