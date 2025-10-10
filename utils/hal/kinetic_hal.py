"""KineticController Hardware Abstraction Layer (HAL)

Provides a standardized interface for KNX kinetic system hardware including:
- KNX2 boards (primary)
- KNX1 boards (legacy support)
- Future kinetic hardware compatibility

This HAL abstracts valve control, pump operations, flow sensing, and temperature
monitoring for SPR kinetic experiments.

Hardware Components Managed:
- Six-port valves (Takasago Electric)
- Three-way valves (The Lee Company)
- Flow sensors (I2C-based)
- Temperature sensors
- Peristaltic pumps
"""

from __future__ import annotations

import json
import threading
from typing import Any

import serial
import serial.tools.list_ports

from utils.logger import logger

from .hal_exceptions import HALConnectionError, HALError, HALOperationError

# Hardware constants
CP210X_VID = 0x10C4
CP210X_PID = 0xEA60
BAUD_RATE = 115200
TIMEOUT_SEC = 3
WRITE_TIMEOUT_SEC = 2

# Channel mapping
CH_DICT = {"a": 1, "b": 2, "c": 3, "d": 4}

# Command constants
GET_INFO_CMD = "get_info"
GET_STATUS_CMD = "get_status"
GET_PARAMETERS_CMD = "get_parameters"
STOP_CMD = "stop"
SHUTDOWN_CMD = "shutdown"


class KineticHAL:
    """Hardware Abstraction Layer for KNX Kinetic Controllers.

    Provides standardized interface for:
    - Valve control (3-way and 6-port valves)
    - Pump operations
    - Flow and temperature sensing
    - Hardware status monitoring

    This is a standalone HAL class specifically for kinetic systems,
    separate from the SPR controller HAL hierarchy.
    """

    def __init__(self, device_name: str = "KNX Controller") -> None:
        """Initialize Kinetic HAL."""
        self.device_name = device_name
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()
        self._device_info = {
            "model": "Unknown",
            "firmware_version": "Unknown",
            "hardware_version": "Unknown",
            "serial_number": "Unknown",
            "connected": False,
            "device_type": "kinetic_controller",
            "manufacturer": "Affinite Instruments",
        }

    def connect(self, **kwargs) -> bool:
        """Connect to KNX kinetic controller hardware.

        Args:
            **kwargs: Connection parameters (auto-detection used if none provided)

        Returns:
            True if connection successful

        Raises:
            HALConnectionError: If connection fails

        """
        try:
            # Auto-detect KNX hardware
            detected_port = self._detect_knx_hardware()
            if not detected_port:
                logger.error("No KNX kinetic controller found")
                raise HALConnectionError("No KNX kinetic controller found")

            # Open serial connection
            self._serial = serial.Serial(
                port=detected_port,
                baudrate=BAUD_RATE,
                timeout=TIMEOUT_SEC,
                write_timeout=WRITE_TIMEOUT_SEC,
            )

            # Verify connection and get device info
            if not self._verify_connection():
                self._serial.close()
                self._serial = None
                raise HALConnectionError("Failed to verify KNX controller connection")

            self._device_info["connected"] = True
            logger.info(
                f"Connected to KNX controller: {self._device_info['model']} v{self._device_info['firmware_version']}"
            )
            return True

        except HALConnectionError:
            raise
        except Exception as e:
            logger.exception(f"Failed to connect to KNX controller: {e}")
            if self._serial:
                self._serial.close()
                self._serial = None
            raise HALConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> bool:
        """Disconnect from kinetic controller.

        Returns:
            True if disconnection successful

        Raises:
            HALError: If disconnection fails

        """
        try:
            if self._serial and self._serial.is_open:
                # Send shutdown command
                self._send_command(SHUTDOWN_CMD, reply=False)
                self._serial.close()

            self._serial = None
            self._device_info["connected"] = False
            logger.info("Disconnected from KNX controller")
            return True

        except Exception as e:
            logger.exception(f"Error during KNX controller disconnect: {e}")
            raise HALError(f"Disconnect failed: {e}")

    def is_connected(self) -> bool:
        """Check if connected to kinetic controller.

        Returns:
            True if connected

        """
        return self._serial is not None and self._serial.is_open

    def get_device_info(self) -> dict[str, Any]:
        """Get device information.

        Returns:
            Dictionary with device information

        """
        return self._device_info.copy()

    def get_capabilities(self) -> list[str]:
        """Get HAL capabilities.

        Returns:
            List of supported capabilities

        """
        return [
            "valve_control",
            "pump_control",
            "flow_sensing",
            "temperature_monitoring",
            "hardware_status",
            "firmware_info",
            "multi_channel",
        ]

    # ========================================================================
    # Hardware Information Methods
    # ========================================================================

    def get_status(self) -> dict[str, Any] | None:
        """Get current hardware status.

        Returns:
            Status dictionary or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            return self._send_command(GET_STATUS_CMD, parse_json=True)
        except Exception as e:
            logger.exception(f"Error getting status: {e}")
            raise HALOperationError(f"Failed to get status: {e}")

    def get_info(self) -> dict[str, Any] | None:
        """Get hardware information.

        Returns:
            Info dictionary or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            return self._send_command(GET_INFO_CMD, parse_json=True)
        except Exception as e:
            logger.exception(f"Error getting info: {e}")
            raise HALOperationError(f"Failed to get info: {e}")

    def get_parameters(self) -> dict[str, Any] | None:
        """Get hardware parameters.

        Returns:
            Parameters dictionary or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            return self._send_command(GET_PARAMETERS_CMD, parse_json=True)
        except Exception as e:
            logger.exception(f"Error getting parameters: {e}")
            raise HALOperationError(f"Failed to get parameters: {e}")

    # ========================================================================
    # Valve Control Methods
    # ========================================================================

    def set_three_way_valve(self, channel: str | int, state: int) -> bool:
        """Control three-way valve position.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            state: Valve state (0=waste, 1=load)

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_three_{state}_{hw_channel}")
            return result is not None
        except ValueError as e:
            logger.error(f"Invalid channel for three-way valve: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error setting three-way valve: {e}")
            raise HALOperationError(f"Three-way valve operation failed: {e}")

    def set_six_port_valve(self, channel: str | int, state: int) -> bool:
        """Control six-port valve position.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            state: Valve state (0=load, 1=inject)

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_six_{state}_{hw_channel}")
            return result is not None
        except ValueError as e:
            logger.error(f"Invalid channel for six-port valve: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error setting six-port valve: {e}")
            raise HALOperationError(f"Six-port valve operation failed: {e}")

    def get_valve_status(self, channel: str | int) -> dict[str, Any] | None:
        """Get valve status for channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            Valve status dictionary or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            return self._send_command(f"knx_status_{hw_channel}", parse_json=True)
        except ValueError as e:
            logger.error(f"Invalid channel for valve status: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error getting valve status: {e}")
            raise HALOperationError(f"Valve status operation failed: {e}")

    # ========================================================================
    # Pump Control Methods
    # ========================================================================

    def start_pump(self, channel: str | int, rate: int) -> bool:
        """Start pump at specified rate.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            rate: Flow rate (implementation-specific units)

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_start_{rate}_{hw_channel}")
            return result is not None
        except ValueError as e:
            logger.error(f"Invalid channel for pump start: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error starting pump: {e}")
            raise HALOperationError(f"Pump start operation failed: {e}")

    def stop_pump(self, channel: str | int) -> bool:
        """Stop pump on channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_stop_{hw_channel}")
            return result is not None
        except ValueError as e:
            logger.error(f"Invalid channel for pump stop: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error stopping pump: {e}")
            raise HALOperationError(f"Pump stop operation failed: {e}")

    def stop_all_pumps(self) -> bool:
        """Emergency stop all pumps.

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command("knx_stop_all")
            return result is not None
        except Exception as e:
            logger.exception(f"Error stopping all pumps: {e}")
            raise HALOperationError(f"Emergency stop failed: {e}")

    # ========================================================================
    # LED Control Methods
    # ========================================================================

    def turn_on_led(self, channel: str = "a") -> bool:
        """Turn on LED for channel.

        Args:
            channel: LED channel ('a', 'b', 'c', 'd')

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            if channel not in CH_DICT:
                raise ValueError(f"Invalid LED channel: {channel}")
            result = self._send_command(f"led_on({CH_DICT[channel]})")
            return result is not None
        except ValueError as e:
            logger.error(f"LED control error: {e}")
            raise HALOperationError(f"Invalid LED channel: {e}")
        except Exception as e:
            logger.exception(f"Error turning on LED {channel}: {e}")
            raise HALOperationError(f"LED control failed: {e}")

    def turn_off_leds(self) -> bool:
        """Turn off all LEDs.

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command("led_off")
            return result is not None
        except Exception as e:
            logger.exception(f"Error turning off LEDs: {e}")
            raise HALOperationError(f"LED control failed: {e}")

    def set_led_intensity(self, channel: str = "a", intensity: int = 255) -> bool:
        """Set LED intensity and turn on.

        Args:
            channel: LED channel ('a', 'b', 'c', 'd')
            intensity: Intensity value (0-255)

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            if channel not in CH_DICT:
                raise ValueError(f"Invalid LED channel: {channel}")

            # Convert 0-255 range to 1-32 range for hardware
            val = int((intensity / 255) * 31) + 1

            # Set intensity
            result1 = self._send_command(f"led_intensity({CH_DICT[channel]},{val})")
            if result1 is None:
                return False

            # Turn on LED
            result2 = self._send_command(f"led_on({CH_DICT[channel]})")
            return result2 is not None

        except ValueError as e:
            logger.error(f"LED intensity error: {e}")
            raise HALOperationError(f"Invalid LED parameter: {e}")
        except Exception as e:
            logger.exception(f"Error setting LED intensity {channel}: {e}")
            raise HALOperationError(f"LED intensity control failed: {e}")

    # ========================================================================
    # Data Reading Methods
    # ========================================================================

    def read_wavelength(self, channel: str | int) -> list[int] | None:
        """Read wavelength data from channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            List of wavelength values or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            hw_channel = self._normalize_channel(channel)
            data = self._send_command(f"read{hw_channel}")
            if data:
                return [int(v) for v in data.split(",")]
            return None
        except ValueError as e:
            logger.error(f"Invalid channel for wavelength read: {e}")
            raise HALOperationError(f"Invalid channel: {e}")
        except Exception as e:
            logger.exception(f"Error reading wavelength: {e}")
            raise HALOperationError(f"Wavelength read failed: {e}")

    def read_intensity(self) -> list[int] | None:
        """Read intensity measurements.

        Returns:
            List of intensity values or None if error

        Raises:
            HALOperationError: If operation fails

        """
        try:
            data = self._send_command("intensity")
            if data:
                return [int(v) for v in data.split(",")]
            return None
        except Exception as e:
            logger.exception(f"Error reading intensity: {e}")
            raise HALOperationError(f"Intensity read failed: {e}")

    # ========================================================================
    # Configuration Methods
    # ========================================================================

    def set_integration_time(self, time_ms: int) -> bool:
        """Set integration time.

        Args:
            time_ms: Integration time in milliseconds

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command(f"set_integration({time_ms})")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting integration time: {e}")
            raise HALOperationError(f"Integration time setting failed: {e}")

    def set_servo_mode(self, mode: str = "s") -> bool:
        """Set servo mode.

        Args:
            mode: Servo mode identifier

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command(f"servo_{mode}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting servo mode: {e}")
            raise HALOperationError(f"Servo mode setting failed: {e}")

    def set_servo_position(self, speed: int = 10, position: int = 100) -> bool:
        """Set servo position.

        Args:
            speed: Servo speed
            position: Servo position

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command(f"servo_set({speed},{position})")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting servo position: {e}")
            raise HALOperationError(f"Servo position setting failed: {e}")

    def stop_system(self) -> bool:
        """Stop system operations.

        Returns:
            True if successful

        Raises:
            HALOperationError: If operation fails

        """
        try:
            result = self._send_command(STOP_CMD)
            return result is not None
        except Exception as e:
            logger.exception(f"Error stopping system: {e}")
            raise HALOperationError(f"System stop failed: {e}")

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _detect_knx_hardware(self) -> str | None:
        """Auto-detect KNX hardware on system ports.

        Returns:
            Serial port path or None if not found

        """
        for port in serial.tools.list_ports.comports():
            if port.pid == CP210X_PID and port.vid == CP210X_VID:
                logger.debug(f"Found potential KNX controller: {port.device}")
                return port.device
        return None

    def _verify_connection(self) -> bool:
        """Verify connection and populate device info.

        Returns:
            True if verification successful

        """
        try:
            info = self._send_command(GET_INFO_CMD, parse_json=True)
            if not info:
                return False

            fw_ver = info.get("fw ver", "")

            # Check for supported firmware types
            if fw_ver.startswith("KNX2"):
                self._device_info["model"] = "KNX2"
                self._device_info["firmware_version"] = fw_ver
                if fw_ver.startswith("KNX2 V1.1"):
                    self._device_info["hardware_version"] = "1.1"
                else:
                    self._device_info["hardware_version"] = "1.0"
                return True

            if fw_ver.startswith("KNX1"):
                self._device_info["model"] = "KNX1"
                self._device_info["firmware_version"] = fw_ver
                self._device_info["hardware_version"] = "1.1"
                return True

            logger.error(f"Unsupported firmware version: {fw_ver}")
            return False

        except Exception as e:
            logger.exception(f"Error verifying KNX connection: {e}")
            return False

    def _send_command(
        self, cmd: str, parse_json: bool = False, reply: bool = True
    ) -> Any:
        """Send command to hardware.

        Args:
            cmd: Command string
            parse_json: Parse response as JSON
            reply: Expect reply from hardware

        Returns:
            Command response or None if error

        Raises:
            HALOperationError: If command fails

        """
        if not self.is_connected():
            raise HALOperationError(
                "Cannot send command: not connected to KNX controller"
            )

        try:
            with self._lock:
                logger.debug(f"KNX HAL: Sending command - `{cmd}`")
                if self._serial:
                    self._serial.write(f"{cmd}\n".encode())

                    if reply and self._serial:
                        response = self._serial.readline().decode().strip()

                        if parse_json:
                            try:
                                return json.loads(response)
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Failed to parse JSON response for {cmd}: {response}"
                                )
                                return None
                        else:
                            return response if response else None

        except Exception as e:
            logger.exception(f"Error sending command '{cmd}': {e}")
            # Connection may be lost
            self._device_info["connected"] = False
            raise HALOperationError(f"Command failed: {e}")

    def _normalize_channel(self, channel: str | int) -> int:
        """Normalize channel identifier to hardware channel number.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            Hardware channel number (1 or 2)

        Raises:
            ValueError: If channel is invalid

        """
        if isinstance(channel, int):
            if channel in [1, 2]:
                return channel
        elif isinstance(channel, str):
            if channel.upper() in ["CH1", "1"]:
                return 1
            if channel.upper() in ["CH2", "2"]:
                return 2

        raise ValueError(f"Invalid channel identifier: {channel}")

    """
    Hardware Abstraction Layer for KNX Kinetic Controllers.

    Provides standardized interface for:
    - Valve control (3-way and 6-port valves)
    - Pump operations
    - Flow and temperature sensing
    - Hardware status monitoring
    """

    def __init__(self, **kwargs) -> None:
        """Initialize Kinetic HAL."""
        super().__init__(**kwargs)
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()
        self._device_info = {
            "model": "Unknown",
            "firmware_version": "Unknown",
            "hardware_version": "Unknown",
            "serial_number": "Unknown",
            "connected": False,
            "device_type": "kinetic_controller",
            "manufacturer": "Affinite Instruments",
        }

    def connect(self, **kwargs) -> bool:
        """Connect to KNX kinetic controller hardware.

        Args:
            **kwargs: Connection parameters (auto-detection used if none provided)

        Returns:
            True if connection successful

        """
        try:
            # Auto-detect KNX hardware
            detected_port = self._detect_knx_hardware()
            if not detected_port:
                logger.error("No KNX kinetic controller found")
                return False

            # Open serial connection
            self._serial = serial.Serial(
                port=detected_port,
                baudrate=BAUD_RATE,
                timeout=TIMEOUT_SEC,
                write_timeout=WRITE_TIMEOUT_SEC,
            )

            # Verify connection and get device info
            if not self._verify_connection():
                self._serial.close()
                self._serial = None
                return False

            self._device_info["connected"] = True
            logger.info(
                f"Connected to KNX controller: {self._device_info['model']} v{self._device_info['firmware_version']}"
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to connect to KNX controller: {e}")
            if self._serial:
                self._serial.close()
                self._serial = None
            return False

    def disconnect(self) -> bool:
        """Disconnect from kinetic controller.

        Returns:
            True if disconnection successful

        """
        try:
            if self._serial and self._serial.is_open:
                # Send shutdown command
                self._send_command(SHUTDOWN_CMD, reply=False)
                self._serial.close()

            self._serial = None
            self._device_info["connected"] = False
            logger.info("Disconnected from KNX controller")
            return True

        except Exception as e:
            logger.exception(f"Error during KNX controller disconnect: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to kinetic controller.

        Returns:
            True if connected

        """
        return self._serial is not None and self._serial.is_open

    def get_device_info(self) -> dict[str, Any]:
        """Get device information.

        Returns:
            Dictionary with device information

        """
        return self._device_info.copy()

    def get_capabilities(self) -> list[str]:
        """Get HAL capabilities.

        Returns:
            List of supported capabilities

        """
        return [
            "valve_control",
            "pump_control",
            "flow_sensing",
            "temperature_monitoring",
            "hardware_status",
            "firmware_info",
            "multi_channel",
        ]

    # ========================================================================
    # Hardware Information Methods
    # ========================================================================

    def get_status(self) -> dict[str, Any] | None:
        """Get current hardware status.

        Returns:
            Status dictionary or None if error

        """
        return self._send_command(GET_STATUS_CMD, parse_json=True)

    def get_info(self) -> dict[str, Any] | None:
        """Get hardware information.

        Returns:
            Info dictionary or None if error

        """
        return self._send_command(GET_INFO_CMD, parse_json=True)

    def get_parameters(self) -> dict[str, Any] | None:
        """Get hardware parameters.

        Returns:
            Parameters dictionary or None if error

        """
        return self._send_command(GET_PARAMETERS_CMD, parse_json=True)

    # ========================================================================
    # Valve Control Methods
    # ========================================================================

    def set_three_way_valve(self, channel: str | int, state: int) -> bool:
        """Control three-way valve position.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            state: Valve state (0=waste, 1=load)

        Returns:
            True if successful

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_three_{state}_{hw_channel}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting three-way valve CH{hw_channel}: {e}")
            return False

    def set_six_port_valve(self, channel: str | int, state: int) -> bool:
        """Control six-port valve position.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            state: Valve state (0=load, 1=inject)

        Returns:
            True if successful

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_six_{state}_{hw_channel}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting six-port valve CH{hw_channel}: {e}")
            return False

    def get_valve_status(self, channel: str | int) -> dict[str, Any] | None:
        """Get valve status for channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            Valve status dictionary or None if error

        """
        try:
            hw_channel = self._normalize_channel(channel)
            return self._send_command(f"knx_status_{hw_channel}", parse_json=True)
        except Exception as e:
            logger.exception(f"Error getting valve status CH{hw_channel}: {e}")
            return None

    # ========================================================================
    # Pump Control Methods
    # ========================================================================

    def start_pump(self, channel: str | int, rate: int) -> bool:
        """Start pump at specified rate.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")
            rate: Flow rate (implementation-specific units)

        Returns:
            True if successful

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_start_{rate}_{hw_channel}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error starting pump CH{hw_channel}: {e}")
            return False

    def stop_pump(self, channel: str | int) -> bool:
        """Stop pump on channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            True if successful

        """
        try:
            hw_channel = self._normalize_channel(channel)
            result = self._send_command(f"knx_stop_{hw_channel}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error stopping pump CH{hw_channel}: {e}")
            return False

    def stop_all_pumps(self) -> bool:
        """Emergency stop all pumps.

        Returns:
            True if successful

        """
        try:
            result = self._send_command("knx_stop_all")
            return result is not None
        except Exception as e:
            logger.exception(f"Error stopping all pumps: {e}")
            return False

    # ========================================================================
    # LED Control Methods
    # ========================================================================

    def turn_on_led(self, channel: str = "a") -> bool:
        """Turn on LED for channel.

        Args:
            channel: LED channel ('a', 'b', 'c', 'd')

        Returns:
            True if successful

        """
        try:
            if channel not in CH_DICT:
                logger.error(f"Invalid LED channel: {channel}")
                return False
            result = self._send_command(f"led_on({CH_DICT[channel]})")
            return result is not None
        except Exception as e:
            logger.exception(f"Error turning on LED {channel}: {e}")
            return False

    def turn_off_leds(self) -> bool:
        """Turn off all LEDs.

        Returns:
            True if successful

        """
        try:
            result = self._send_command("led_off")
            return result is not None
        except Exception as e:
            logger.exception(f"Error turning off LEDs: {e}")
            return False

    def set_led_intensity(self, channel: str = "a", intensity: int = 255) -> bool:
        """Set LED intensity and turn on.

        Args:
            channel: LED channel ('a', 'b', 'c', 'd')
            intensity: Intensity value (0-255)

        Returns:
            True if successful

        """
        try:
            if channel not in CH_DICT:
                logger.error(f"Invalid LED channel: {channel}")
                return False

            # Convert 0-255 range to 1-32 range for hardware
            val = int((intensity / 255) * 31) + 1

            # Set intensity
            result1 = self._send_command(f"led_intensity({CH_DICT[channel]},{val})")
            if result1 is None:
                return False

            # Turn on LED
            result2 = self._send_command(f"led_on({CH_DICT[channel]})")
            return result2 is not None

        except Exception as e:
            logger.exception(f"Error setting LED intensity {channel}: {e}")
            return False

    # ========================================================================
    # Data Reading Methods
    # ========================================================================

    def read_wavelength(self, channel: str | int) -> list[int] | None:
        """Read wavelength data from channel.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            List of wavelength values or None if error

        """
        try:
            hw_channel = self._normalize_channel(channel)
            data = self._send_command(f"read{hw_channel}")
            if data:
                return [int(v) for v in data.split(",")]
            return None
        except Exception as e:
            logger.exception(f"Error reading wavelength CH{hw_channel}: {e}")
            return None

    def read_intensity(self) -> list[int] | None:
        """Read intensity measurements.

        Returns:
            List of intensity values or None if error

        """
        try:
            data = self._send_command("intensity")
            if data:
                return [int(v) for v in data.split(",")]
            return None
        except Exception as e:
            logger.exception(f"Error reading intensity: {e}")
            return None

    # ========================================================================
    # Configuration Methods
    # ========================================================================

    def set_integration_time(self, time_ms: int) -> bool:
        """Set integration time.

        Args:
            time_ms: Integration time in milliseconds

        Returns:
            True if successful

        """
        try:
            result = self._send_command(f"set_integration({time_ms})")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting integration time: {e}")
            return False

    def set_servo_mode(self, mode: str = "s") -> bool:
        """Set servo mode.

        Args:
            mode: Servo mode identifier

        Returns:
            True if successful

        """
        try:
            result = self._send_command(f"servo_{mode}")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting servo mode: {e}")
            return False

    def set_servo_position(self, speed: int = 10, position: int = 100) -> bool:
        """Set servo position.

        Args:
            speed: Servo speed
            position: Servo position

        Returns:
            True if successful

        """
        try:
            result = self._send_command(f"servo_set({speed},{position})")
            return result is not None
        except Exception as e:
            logger.exception(f"Error setting servo position: {e}")
            return False

    def stop_system(self) -> bool:
        """Stop system operations.

        Returns:
            True if successful

        """
        try:
            result = self._send_command(STOP_CMD)
            return result is not None
        except Exception as e:
            logger.exception(f"Error stopping system: {e}")
            return False

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _detect_knx_hardware(self) -> str | None:
        """Auto-detect KNX hardware on system ports.

        Returns:
            Serial port path or None if not found

        """
        for port in serial.tools.list_ports.comports():
            if port.pid == CP210X_PID and port.vid == CP210X_VID:
                logger.debug(f"Found potential KNX controller: {port.device}")
                return port.device
        return None

    def _verify_connection(self) -> bool:
        """Verify connection and populate device info.

        Returns:
            True if verification successful

        """
        try:
            info = self._send_command(GET_INFO_CMD, parse_json=True)
            if not info:
                return False

            fw_ver = info.get("fw ver", "")

            # Check for supported firmware types
            if fw_ver.startswith("KNX2"):
                self._device_info["model"] = "KNX2"
                self._device_info["firmware_version"] = fw_ver
                if fw_ver.startswith("KNX2 V1.1"):
                    self._device_info["hardware_version"] = "1.1"
                else:
                    self._device_info["hardware_version"] = "1.0"
                return True

            if fw_ver.startswith("KNX1"):
                self._device_info["model"] = "KNX1"
                self._device_info["firmware_version"] = fw_ver
                self._device_info["hardware_version"] = "1.1"
                return True

            logger.error(f"Unsupported firmware version: {fw_ver}")
            return False

        except Exception as e:
            logger.exception(f"Error verifying KNX connection: {e}")
            return False

    def _send_command(
        self, cmd: str, parse_json: bool = False, reply: bool = True
    ) -> Any:
        """Send command to hardware.

        Args:
            cmd: Command string
            parse_json: Parse response as JSON
            reply: Expect reply from hardware

        Returns:
            Command response or None if error

        """
        if not self.is_connected():
            logger.error("Cannot send command: not connected to KNX controller")
            return None

        try:
            with self._lock:
                logger.debug(f"KNX HAL: Sending command - `{cmd}`")
                self._serial.write(f"{cmd}\n".encode())

                if reply:
                    response = self._serial.readline().decode().strip()

                    if parse_json:
                        try:
                            return json.loads(response)
                        except json.JSONDecodeError:
                            logger.error(
                                f"Failed to parse JSON response for {cmd}: {response}"
                            )
                            return None
                    else:
                        return response if response else None

        except Exception as e:
            logger.exception(f"Error sending command '{cmd}': {e}")
            # Connection may be lost
            self._device_info["connected"] = False
            return None

    def _normalize_channel(self, channel: str | int) -> int:
        """Normalize channel identifier to hardware channel number.

        Args:
            channel: Channel identifier (1, 2, "CH1", "CH2")

        Returns:
            Hardware channel number (1 or 2)

        Raises:
            ValueError: If channel is invalid

        """
        if isinstance(channel, int):
            if channel in [1, 2]:
                return channel
        elif isinstance(channel, str):
            if channel.upper() in ["CH1", "1"]:
                return 1
            if channel.upper() in ["CH2", "2"]:
                return 2

        raise ValueError(f"Invalid channel identifier: {channel}")
