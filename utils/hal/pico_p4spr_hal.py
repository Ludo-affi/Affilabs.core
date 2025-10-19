"""PicoP4SPR Hardware Abstraction Layer Implementation

Implements the SPRControllerHAL interface for PicoP4SPR controllers,
providing standardized access to Pi Pico-based P4SPR devices.
"""

from __future__ import annotations

import time
from contextlib import suppress
from typing import Any

import serial
import serial.tools.list_ports

from settings import PICO_PID, PICO_VID
from utils.logger import logger

from .hal_exceptions import HALConnectionError, HALOperationError
from .spr_controller_hal import ChannelID, ControllerCapabilities, SPRControllerHAL


class PicoP4SPRHAL(SPRControllerHAL):
    """Hardware Abstraction Layer implementation for PicoP4SPR controllers.

    Provides standardized interface to Pi Pico-based P4SPR measurement devices
    using USB CDC (serial) communication.
    """

    def __init__(self) -> None:
        """Initialize PicoP4SPR HAL."""
        super().__init__("PicoP4SPR")
        self._ser: serial.Serial | None = None
        self._connection_timeout = 3.0
        self._operation_timeout = 2.0
        self._current_intensity = 1.0  # Default to full intensity (firmware default)

    def connect(self, **connection_params: Any) -> bool:
        """Connect to PicoP4SPR controller.

        Args:
            **connection_params: Optional parameters:
                - port: Specific port to connect to (auto-detect if None)
                - timeout: Connection timeout in seconds (default: 3.0)
                - baud_rate: Serial baud rate (default: 115200)

        Returns:
            True if connection successful, False otherwise

        Raises:
            HALConnectionError: If connection fails

        """
        try:
            # Extract connection parameters
            specific_port = connection_params.get("port")
            timeout = connection_params.get("timeout", self._connection_timeout)
            baud_rate = connection_params.get("baud_rate", 115200)

            # If specific port provided, try only that port
            if specific_port:
                # Create a mock port object for direct connection
                class MockPort:
                    def __init__(self, device: str) -> None:
                        self.device = device
                        self.vid = PICO_VID
                        self.pid = PICO_PID

                ports_to_try = [MockPort(specific_port)]
            else:
                # Auto-detect PicoP4SPR devices
                ports_to_try = self._find_pico_devices()

            if not ports_to_try:
                raise HALConnectionError(
                    "No PicoP4SPR devices found",
                    device_info={"model": "PicoP4SPR"},
                )

            # Try each potential device
            for port_info in ports_to_try:
                if self._attempt_connection(port_info.device, baud_rate, timeout):
                    self.status.connected = True
                    self._update_status()
                    logger.info(
                        f"Successfully connected to PicoP4SPR on {port_info.device}",
                    )
                    return True

            raise HALConnectionError(
                "Failed to establish communication with any PicoP4SPR device",
            )

        except Exception as e:
            self.status.connected = False
            self.status.last_error = str(e)
            if isinstance(e, HALConnectionError):
                raise
            raise HALConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from PicoP4SPR controller."""
        try:
            # CRITICAL: Turn off all LEDs before disconnect
            if self._ser is not None and getattr(self._ser, "is_open", False):
                try:
                    self.emergency_shutdown()
                    logger.info("Emergency LED shutdown completed before disconnect")
                except Exception as e:
                    logger.warning(f"Emergency shutdown failed during disconnect: {e}")

                # Close serial connection
                self._ser.close()
                self._ser = None
            self.status.connected = False
            self.status.active_channel = None
            logger.info("Disconnected from PicoP4SPR")
        except Exception as e:
            logger.warning(f"Error during PicoP4SPR disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if controller is connected and responsive."""
        try:
            return (
                self._ser is not None
                and getattr(self._ser, "is_open", False)
                and self._test_communication()
            )
        except Exception:
            return False

    def get_device_info(self) -> dict[str, Any]:
        """Get PicoP4SPR device information."""
        if not self.is_connected():
            raise HALOperationError("Device not connected", "get_device_info")

        try:
            # Get firmware version
            firmware_version = self._get_firmware_version()

            return {
                "model": "PicoP4SPR",
                "firmware_version": firmware_version,
                "serial_number": "Unknown",  # PicoP4SPR doesn't provide serial number
                "hardware_revision": "Pi Pico Based",
                "connection_type": "USB CDC Serial",
                "vendor_id": f"0x{PICO_VID:04X}",
                "product_id": f"0x{PICO_PID:04X}",
            }
        except Exception as e:
            raise HALOperationError(
                f"Failed to get device info: {e}",
                "get_device_info",
            )

    def activate_channel(self, channel: ChannelID) -> bool:
        """Activate specified measurement channel."""
        if not self.validate_channel(channel):
            raise HALOperationError(
                f"Channel {channel.value} not supported",
                "activate_channel",
            )

        if not self.is_connected():
            raise HALOperationError("Device not connected", "activate_channel")

        try:
            cmd = f"l{channel.value}\n"
            success = self._send_command_with_response(cmd, expected_response=b"1")

            if success:
                self.status.active_channel = channel
                logger.debug(f"Activated channel {channel.value}")
            else:
                logger.warning(f"Failed to activate channel {channel.value}")

            return success

        except Exception as e:
            raise HALOperationError(
                f"Channel activation failed: {e}",
                "activate_channel",
            )

    def get_temperature(self) -> float | None:
        """Read controller temperature."""
        if not self.get_capabilities().supports_temperature:
            return None

        if not self.is_connected():
            raise HALOperationError("Device not connected", "get_temperature")

        try:
            # Clear input buffer
            with suppress(Exception):
                if self._ser:
                    self._ser.reset_input_buffer()

            if self._ser:
                self._ser.write(b"it\n")

                # Try reading temperature with retries
                for _attempt in range(3):
                    line = self._ser.readline()
                    temp_str = line.decode(errors="ignore").strip()

                    if (
                        temp_str
                        and temp_str.replace(".", "").replace("-", "").isdigit()
                    ):
                        temperature = float(temp_str)
                        self.status.temperature = temperature
                        return temperature

                    time.sleep(0.1)  # Brief delay before retry

            # No valid reading obtained
            logger.debug("No valid temperature reading from PicoP4SPR")
            return None

        except Exception as e:
            logger.warning(f"Temperature reading failed: {e}")
            return None

    def set_led_intensity(self, intensity: float) -> bool:
        """Set LED intensity for all channels.

        Args:
            intensity: LED intensity (0.0 to 1.0 normalized scale)

        Returns:
            True if setting successful, False otherwise

        Note:
            - Firmware uses 0-255 range (8-bit PWM)
            - 4LED PCB: Limited to 204 max (~80% range)
            - 8LED PCB: Full 255 range
            - Commands: baXXX\n, bbXXX\n, bcXXX\n, bdXXX\n
        """
        if not self.validate_led_intensity(intensity):
            return False

        if not self.is_connected():
            raise HALOperationError("Device not connected", "set_led_intensity")

        try:
            # Convert 0.0-1.0 to 0-255 firmware range
            # Apply hardware-specific max intensity limit (204 for 4LED, 255 for 8LED)
            # TODO: Get max from device config - for now assume 204 (4LED PCB)
            max_intensity = 204
            firmware_value = int(intensity * max_intensity)
            firmware_value = max(0, min(firmware_value, max_intensity))  # Clamp

            # Format as 3-digit zero-padded string
            intensity_str = f"{firmware_value:03d}"

            # Set intensity for all 4 channels
            success = True
            for channel_letter in ['a', 'b', 'c', 'd']:
                cmd = f"b{channel_letter}{intensity_str}\n"
                if not self._send_command_with_response(cmd, expected_response=b"1"):
                    logger.warning(f"Failed to set intensity for channel {channel_letter}")
                    success = False

            if success:
                self._current_intensity = intensity
                logger.debug(f"Set LED intensity to {intensity:.2f} (firmware: {firmware_value})")

            return success

        except Exception as e:
            raise HALOperationError(
                f"LED intensity control failed: {e}",
                "set_led_intensity",
            )

    def get_led_intensity(self) -> float | None:
        """Get current LED intensity.

        Returns:
            Current LED intensity (0.0 to 1.0), or None if not available

        Note:
            PicoP4SPR firmware doesn't support reading back intensity,
            so we return the last set value.
        """
        return getattr(self, '_current_intensity', 1.0)  # Default to full intensity

    def emergency_shutdown(self) -> bool:
        """Emergency shutdown - turn off all LEDs and safe shutdown."""
        logger.warning("🚨 EMERGENCY SHUTDOWN - Turning off all LEDs")
        try:
            # Force turn off all LEDs by sending 'l0' command
            if self.is_connected():
                # Correct command for all-LEDs-off on PicoP4SPR is 'lx\n'
                self._send_command("lx\n")  # Turn off all LEDs
                # Backup: ensure intensity is zero as a safety net
                try:
                    self._send_command("i0\n")
                except Exception:
                    pass
                self.status.active_channel = None
                logger.info("✅ LEDs safely turned off")
                return True
            else:
                logger.error("❌ Cannot turn off LEDs - device not connected")
                return False
        except Exception as e:
            logger.error(f"❌ Emergency shutdown failed: {e}")
            return False

    def set_intensity(self, ch: str = "a", raw_val: int = 1) -> bool:
        """Set LED intensity for a specific channel.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')
            raw_val: Intensity value (0-255, where 0=off, 255=max)

        Returns:
            True if successful, False otherwise

        Raises:
            HALOperationError: If device not connected or invalid parameters
        """
        if not self.is_connected():
            raise HALOperationError("Device not connected", "set_intensity")

        try:
            # Validate channel
            if ch not in {"a", "b", "c", "d"}:
                raise ValueError(f"Invalid channel: {ch}. Must be 'a', 'b', 'c', or 'd'")

            # Clamp intensity to valid range (0-255)
            if raw_val > 255:
                logger.debug(f"Invalid intensity value {raw_val}, clamping to 255")
                raw_val = 255
            elif raw_val < 0:
                logger.debug(f"Invalid intensity value {raw_val}, clamping to 0")
                raw_val = 0

            # Build command: format is "b{ch}{intensity:03d}\n"
            # Example: "ba128\n" sets channel A to intensity 128
            cmd = f"b{ch}{int(raw_val):03d}\n"

            logger.debug(f"Setting LED {ch.upper()} intensity to {raw_val}")

            # Send command and check response
            success = self._send_command_with_response(cmd, b"1")

            if success:
                # Turn on the channel after setting intensity
                turn_on_cmd = f"l{ch}\n"
                self._send_command_with_response(turn_on_cmd, b"1")
                logger.debug(f"✅ LED {ch.upper()} set to intensity {raw_val}")
            else:
                logger.error(f"❌ Failed to set LED {ch.upper()} intensity")

            return success

        except ValueError as e:
            logger.error(f"❌ Invalid parameters: {e}")
            raise HALOperationError(f"Invalid parameters: {e}", "set_intensity")
        except Exception as e:
            logger.error(f"❌ Error setting LED intensity: {e}")
            raise HALOperationError(f"Failed to set LED intensity: {e}", "set_intensity")

    def set_mode(self, mode: str = "s") -> bool:
        """Set polarizer mode.

        Args:
            mode: "s" for S-mode (perpendicular), "p" for P-mode (parallel)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            raise HALOperationError("Device not connected", "set_mode")

        try:
            # Map mode to firmware command
            if mode.lower() == "s":
                cmd = "ss\n"  # S-mode command
            else:
                cmd = "sp\n"  # P-mode command

            logger.info(f"🔄 Setting polarizer to {mode.upper()}-mode (command: {cmd.strip()})")

            # Send command and get response
            success = self._send_command_with_response(cmd, b"1")

            if success:
                logger.info(f"✅ Polarizer set to {mode.upper()}-mode successfully")
            else:
                logger.warning(f"⚠️ Unexpected polarizer response")

            return success

        except Exception as e:
            logger.error(f"❌ Error moving polarizer: {e}")
            raise HALOperationError(f"Failed to set polarizer mode: {e}", "set_mode")

    def servo_set(self, s: int, p: int) -> bool:
        """Set servo positions for S and P modes.

        Args:
            s: S-mode position (0-255 raw servo value)
            p: P-mode position (0-255 raw servo value)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            raise HALOperationError("Device not connected", "servo_set")

        try:
            # Validate positions (0-255 servo range, NOT degrees)
            if not (0 <= s <= 255) or not (0 <= p <= 255):
                raise ValueError(f"Servo positions must be 0-255 (got s={s}, p={p})")

            # Format command: sv{s:03d}{p:03d}
            cmd = f"sv{s:03d}{p:03d}\n"
            logger.info(f"🔧 Setting servo positions: S={s}, P={p} (0-255 scale, command: {cmd.strip()})")

            # Send command and get response
            success = self._send_command_with_response(cmd, b"1")

            if success:
                logger.info(f"✅ Servo positions set successfully")
            else:
                logger.warning(f"⚠️ Unexpected servo response")

            return success

        except Exception as e:
            logger.error(f"❌ Error setting servo positions: {e}")
            raise HALOperationError(f"Failed to set servo positions: {e}", "servo_set")

    def servo_get(self) -> dict[str, bytes] | None:
        """Get current servo positions.

        Returns:
            Dictionary with 's' and 'p' keys containing position bytes, or None if failed
        """
        if not self.is_connected():
            raise HALOperationError("Device not connected", "servo_get")

        try:
            cmd = "sr\n"
            self._send_command(cmd)

            # Read full line response: "SSS,PPP\n" (e.g., "165,050\n")
            # Firmware sends comma-separated format with newline
            response = self._ser.readline()

            if response:
                # Decode and strip newline/whitespace
                response_str = response.decode().strip()
                
                # Split by comma separator
                if ',' in response_str:
                    parts = response_str.split(',')
                    if len(parts) == 2:
                        s_pos = parts[0].encode()  # Convert back to bytes for consistency
                        p_pos = parts[1].encode()
                        logger.debug(f"Current servo positions: S={s_pos}, P={p_pos}")
                        return {"s": s_pos, "p": p_pos}
                
                logger.warning(f"Invalid servo position response format: {response_str}")
                return None
            else:
                logger.warning("No servo position response received")
                return None

        except Exception as e:
            logger.error(f"❌ Error reading servo positions: {e}")
            return None

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels.

        Sends the 'lx' command to turn off all channels at once.
        This is used for dark noise measurements and emergency shutdowns.

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            raise HALOperationError("Device not connected", "turn_off_channels")

        try:
            cmd = "lx\n"
            logger.debug("🔦 Turning off all LED channels...")

            success = self._send_command_with_response(cmd, b"1")

            if success:
                logger.debug("✅ All LED channels turned off")
            else:
                logger.warning("⚠️ Unexpected response when turning off LEDs")

            return success

        except Exception as e:
            logger.error(f"❌ Error turning off LED channels: {e}")
            raise HALOperationError(f"Failed to turn off channels: {e}", "turn_off_channels")

    def reset_device(self) -> bool:
        """Reset PicoP4SPR to default state."""
        if not self.is_connected():
            raise HALOperationError("Device not connected", "reset_device")

        try:
            # Turn off all channels
            for channel in [ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D]:
                try:
                    cmd = f"o{channel.value}\n"  # Turn off channel
                    self._send_command(cmd)
                except Exception:
                    pass  # Continue even if individual channel fails

            self.status.active_channel = None
            logger.info("PicoP4SPR reset to default state")
            return True

        except Exception as e:
            raise HALOperationError(f"Device reset failed: {e}", "reset_device")

    def _define_capabilities(self) -> ControllerCapabilities:
        """Define PicoP4SPR capabilities."""
        return ControllerCapabilities(
            # Channel capabilities
            supported_channels=[ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D],
            max_channels=4,
            # LED control (limited - on/off only via channel activation)
            supports_led_control=False,  # No variable intensity control
            led_intensity_range=(0.0, 1.0),
            led_intensity_resolution=1.0,  # Binary on/off only
            # Temperature monitoring
            supports_temperature=True,
            temperature_range=(-40.0, 85.0),  # Typical Pi Pico operating range
            temperature_accuracy=1.0,  # ±1°C typical
            # Timing capabilities
            min_integration_time=0.01,  # 10ms
            max_integration_time=10.0,  # 10s
            supports_variable_timing=False,  # Controlled by host software
            # Communication
            connection_type="USB_SERIAL",
            baud_rate=115200,
            # Identification
            device_model="PicoP4SPR",
            firmware_version_format="vX.Y",
            # Advanced features
            supports_dark_measurement=False,
            supports_multi_scan_averaging=False,  # Handled by host
            supports_external_trigger=False,
        )

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _find_pico_devices(self) -> list:
        """Find all potential PicoP4SPR devices."""
        devices = []

        for dev in serial.tools.list_ports.comports():
            try:
                logger.debug(
                    f"Checking port {dev.device} {getattr(dev, 'vid', None)}:{getattr(dev, 'pid', None)} - {dev.description}",
                )
            except Exception:
                logger.debug(f"Checking port {dev.device} - {dev.description}")

            # Check for Pico VID/PID
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                # Prefer CDC interface (MI_00) when present
                try:
                    hwid = getattr(dev, "hwid", "")
                    if "MI_" in hwid and "MI_00" not in hwid:
                        logger.debug(
                            f"Skipping non-CDC interface on {dev.device} (hwid={hwid})",
                        )
                        continue
                except Exception:
                    pass

                devices.append(dev)

        return devices

    def _attempt_connection(self, port: str, baud_rate: int, timeout: float) -> bool:
        """Attempt connection to specific port."""
        try:
            # Open serial connection
            self._ser = serial.Serial(
                port=port,
                baudrate=baud_rate,
                timeout=timeout,
                write_timeout=2,
            )

            # Configure DTR/RTS for CDC compatibility
            with suppress(Exception):
                self._ser.dtr = False
                time.sleep(0.02)
                self._ser.dtr = True
                self._ser.rts = False

            # Clear buffers and allow device to stabilize
            time.sleep(0.15)
            with suppress(Exception):
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

            # Test device identification
            return self._verify_device_identity()

        except Exception as e:
            logger.debug(f"Connection attempt to {port} failed: {e}")
            if self._ser:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
            return False

    def _verify_device_identity(self) -> bool:
        """Verify device is PicoP4SPR."""
        if not self._ser:
            return False

        for attempt in range(5):
            try:
                self._ser.write(b"id\r\n")
                time.sleep(0.15)

                line = self._ser.readline()
                if not line:
                    # Try reading available bytes
                    with suppress(Exception):
                        waiting = self._ser.in_waiting
                        if waiting:
                            line = self._ser.read(waiting)

                reply = line.decode(errors="ignore").strip()
                logger.debug(f"Device ID response: {reply}")

                if "P4SPR" in reply:
                    return True

                time.sleep(0.2)

            except Exception as e:
                logger.debug(f"ID verification attempt {attempt + 1} failed: {e}")

        return False

    def _get_firmware_version(self) -> str:
        """Get firmware version from device."""
        if not self._ser:
            return "Unknown"

        try:
            self._ser.write(b"iv\r\n")
            time.sleep(0.1)
            version_raw = self._ser.readline()
            version = version_raw.decode(errors="ignore").strip()
            return version[:4] if version else "Unknown"
        except Exception as e:
            logger.debug(f"Failed to get firmware version: {e}")
            return "Unknown"

    def _test_communication(self) -> bool:
        """Test basic communication with device."""
        if not self._ser:
            return False

        try:
            with suppress(Exception):
                self._ser.reset_input_buffer()

            self._ser.write(b"id\r\n")
            time.sleep(0.1)

            response = self._ser.readline()
            reply = response.decode(errors="ignore").strip()
            return "P4SPR" in reply

        except Exception:
            return False

    def _send_command(self, command: str) -> None:
        """Send command to device."""
        if not self._ser or not self._ser.is_open:
            raise HALOperationError("Device not connected", "send_command")

        try:
            self._ser.write(command.encode())
        except Exception as e:
            raise HALOperationError(f"Command send failed: {e}", "send_command")

    def _send_command_with_response(
        self,
        command: str,
        expected_response: bytes,
    ) -> bool:
        """Send command and check for expected response."""
        if not self._ser:
            return False

        try:
            self._send_command(command)
            response = self._ser.read(1)  # Read single byte response
            return response == expected_response
        except Exception as e:
            logger.debug(f"Command with response failed: {e}")
            return False

    def _update_status(self) -> None:
        """Update controller status."""
        if self.is_connected():
            try:
                # Update firmware version
                device_info = self.get_device_info()
                self.status.firmware_version = device_info.get("firmware_version", "")

                # Update temperature
                self.status.temperature = self.get_temperature()

            except Exception as e:
                logger.debug(f"Status update failed: {e}")
