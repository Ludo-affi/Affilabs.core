"""PicoEZSPR Hardware Abstraction Layer Implementation

Implements the SPRControllerHAL interface for PicoEZSPR controllers,
providing standardized access to Pi Pico-based EZSPR devices with
enhanced features like pump correction and firmware updates.
"""

from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Final

import serial
import serial.tools.list_ports

from settings import PICO_PID, PICO_VID
from utils.logger import logger

from .hal_exceptions import HALConnectionError, HALOperationError, HALTimeoutError
from .spr_controller_hal import ChannelID, ControllerCapabilities, SPRControllerHAL


class PicoEZSPRHAL(SPRControllerHAL):
    """Hardware Abstraction Layer implementation for PicoEZSPR controllers.

    Provides standardized interface to Pi Pico-based EZSPR measurement devices
    with enhanced features including pump correction, firmware updates, and
    kinetic system integration.
    """

    # Version constants from original implementation
    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self) -> None:
        """Initialize PicoEZSPR HAL."""
        super().__init__("PicoEZSPR")
        self._ser: serial.Serial | None = None
        self._connection_timeout = 5.0  # EZSPR uses longer timeout
        self._operation_timeout = 2.0
        self._firmware_version = ""

    def connect(self, **connection_params: Any) -> bool:
        """Connect to PicoEZSPR controller.

        Args:
            **connection_params: Optional parameters:
                - port: Specific port to connect to (auto-detect if None)
                - timeout: Connection timeout in seconds (default: 5.0)
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
                # Auto-detect PicoEZSPR devices
                ports_to_try = self._find_pico_devices()

            if not ports_to_try:
                raise HALConnectionError(
                    "No PicoEZSPR devices found",
                    device_info={"model": "PicoEZSPR"},
                )

            # Try each potential device
            for port_info in ports_to_try:
                if self._attempt_connection(port_info.device, baud_rate, timeout):
                    self.status.connected = True
                    self._update_status()
                    logger.info(
                        f"Successfully connected to PicoEZSPR on {port_info.device}",
                    )
                    return True

            raise HALConnectionError(
                "Failed to establish communication with any PicoEZSPR device",
            )

        except Exception as e:
            self.status.connected = False
            self.status.last_error = str(e)
            if isinstance(e, HALConnectionError):
                raise
            raise HALConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from PicoEZSPR controller."""
        try:
            if self._ser is not None:
                self._ser.close()
                self._ser = None
            self.status.connected = False
            self.status.active_channel = None
            logger.info("Disconnected from PicoEZSPR")
        except Exception as e:
            logger.warning(f"Error during PicoEZSPR disconnect: {e}")

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
        """Get PicoEZSPR device information."""
        if not self.is_connected():
            raise HALOperationError("Device not connected", "get_device_info")

        try:
            return {
                "model": "PicoEZSPR",
                "firmware_version": self._firmware_version,
                "serial_number": "Unknown",  # PicoEZSPR doesn't provide serial number
                "hardware_revision": "Pi Pico Based",
                "connection_type": "USB CDC Serial",
                "vendor_id": f"0x{PICO_VID:04X}",
                "product_id": f"0x{PICO_PID:04X}",
                "supports_firmware_update": self._firmware_version
                in self.UPDATABLE_VERSIONS,
                "supports_pump_correction": self._firmware_version
                in self.VERSIONS_WITH_PUMP_CORRECTION,
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

                    if not temp_str:
                        continue  # Skip empty lines

                    logger.debug(f"Invalid temperature reading: '{temp_str}'")

            # No valid reading obtained
            logger.debug("No valid temperature reading from PicoEZSPR")
            return None

        except Exception as e:
            logger.warning(f"Temperature reading failed: {e}")
            return None

    def set_led_intensity(self, intensity: float) -> bool:
        """Set LED intensity for measurements.

        Args:
            intensity: LED intensity (0.0 to 1.0 normalized scale)

        Returns:
            True if setting successful, False otherwise

        """
        if not self.validate_led_intensity(intensity):
            return False

        if not self.is_connected():
            raise HALOperationError("Device not connected", "set_led_intensity")

        try:
            # Convert normalized intensity to EZSPR range (0-255)
            raw_val = int(intensity * 255)

            # Use current active channel or default to 'a'
            channel = (
                self.status.active_channel.value if self.status.active_channel else "a"
            )

            cmd = f"b{channel}{raw_val:03d}\n"
            success = self._send_command_with_response(cmd, expected_response=b"1")

            if success:
                # Activate channel after setting intensity
                self.activate_channel(ChannelID(channel))
                self.status.led_intensity = intensity
                logger.debug(f"Set LED intensity to {intensity:.2f} ({raw_val}/255)")

            return success

        except Exception as e:
            raise HALOperationError(
                f"LED intensity setting failed: {e}",
                "set_led_intensity",
            )

    def get_led_intensity(self) -> float | None:
        """Get current LED intensity."""
        return self.status.led_intensity

    def reset_device(self) -> bool:
        """Reset PicoEZSPR to default state."""
        if not self.is_connected():
            raise HALOperationError("Device not connected", "reset_device")

        try:
            # Turn off all channels
            cmd = "lx\n"
            success = self._send_command_with_response(cmd, expected_response=b"1")

            if success:
                self.status.active_channel = None
                self.status.led_intensity = None
                logger.info("PicoEZSPR reset to default state")

            return success

        except Exception as e:
            raise HALOperationError(f"Device reset failed: {e}", "reset_device")

    def _define_capabilities(self) -> ControllerCapabilities:
        """Define PicoEZSPR capabilities."""
        return ControllerCapabilities(
            # Channel capabilities
            supported_channels=[ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D],
            max_channels=4,
            # LED control (full variable intensity control)
            supports_led_control=True,
            led_intensity_range=(0.0, 1.0),
            led_intensity_resolution=1.0 / 255.0,  # 8-bit resolution
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
            device_model="PicoEZSPR",
            firmware_version_format="vX.Y",
            # Advanced features
            supports_dark_measurement=False,
            supports_multi_scan_averaging=False,  # Handled by host
            supports_external_trigger=False,
        )

    # ========================================================================
    # EZSPR-SPECIFIC FEATURES
    # ========================================================================

    def supports_firmware_update(self) -> bool:
        """Check if firmware update is supported for current version."""
        return self._firmware_version in self.UPDATABLE_VERSIONS

    def supports_pump_correction(self) -> bool:
        """Check if pump correction is supported for current version."""
        return self._firmware_version in self.VERSIONS_WITH_PUMP_CORRECTION

    def update_firmware(self, firmware_path: str) -> bool:
        """Update device firmware (EZSPR-specific feature).

        Args:
            firmware_path: Path to firmware file

        Returns:
            True if update successful, False otherwise

        """
        if not self.supports_firmware_update():
            logger.warning(
                f"Firmware update not supported for version {self._firmware_version}",
            )
            return False

        if not self.is_connected():
            raise HALOperationError("Device not connected", "update_firmware")

        try:
            # Enter firmware update mode
            if self._ser:
                self._ser.write(b"du\n")
            self.disconnect()

            # Wait for device to appear as USB drive
            now = time.monotonic_ns()
            timeout = now + 5_000_000_000  # 5 second timeout
            pico_drive = None

            while now <= timeout:
                try:
                    # Try to find the Pico drive
                    if hasattr(__import__("os"), "listdrives"):
                        from os import listdrives

                        drives = listdrives()
                    else:
                        # Fallback for newer Python versions
                        import os
                        import string

                        drives = [
                            f"{letter}:\\"
                            for letter in string.ascii_uppercase
                            if os.path.exists(f"{letter}:\\")
                        ]

                    for drive in drives:
                        if (Path(drive) / "INFO_UF2.TXT").exists():
                            pico_drive = drive
                            break

                    if pico_drive:
                        break

                except Exception:
                    pass

                time.sleep(0.1)
                now = time.monotonic_ns()

            if not pico_drive:
                raise HALTimeoutError("Device did not enter firmware update mode", 5.0)

            # Copy firmware
            from shutil import copy

            copy(firmware_path, pico_drive)

            # Wait for device to restart and reconnect
            now = time.monotonic_ns()
            timeout = now + 5_000_000_000  # 5 second timeout

            while now <= timeout:
                if self.connect():
                    logger.info("Firmware update completed successfully")
                    return True
                time.sleep(0.1)
                now = time.monotonic_ns()

            raise HALTimeoutError("Device did not restart after firmware update", 5.0)

        except Exception as e:
            raise HALOperationError(f"Firmware update failed: {e}", "update_firmware")

    def get_pump_corrections(self) -> tuple[float, float] | None:
        """Get pump correction factors (EZSPR-specific feature).

        Returns:
            Tuple of (pump1_correction, pump2_correction) or None if not supported

        """
        if not self.supports_pump_correction():
            return None

        if not self.is_connected():
            raise HALOperationError("Device not connected", "get_pump_corrections")

        try:
            if self._ser:
                self._ser.write(b"pc\n")
                reply = self._ser.readline()
                if len(reply) >= 2:
                    pump1_corr = reply[0] / self.PUMP_CORRECTION_MULTIPLIER
                    pump2_corr = reply[1] / self.PUMP_CORRECTION_MULTIPLIER
                    return (pump1_corr, pump2_corr)
            return None

        except Exception as e:
            raise HALOperationError(
                f"Failed to get pump corrections: {e}",
                "get_pump_corrections",
            )

    def set_pump_corrections(
        self,
        pump1_correction: float,
        pump2_correction: float,
    ) -> bool:
        """Set pump correction factors (EZSPR-specific feature).

        Args:
            pump1_correction: Correction factor for pump 1
            pump2_correction: Correction factor for pump 2

        Returns:
            True if setting successful, False otherwise

        """
        if not self.supports_pump_correction():
            logger.warning(
                f"Pump correction not supported for version {self._firmware_version}",
            )
            return False

        if not self.is_connected():
            raise HALOperationError("Device not connected", "set_pump_corrections")

        try:
            corrections = (pump1_correction, pump2_correction)
            correction_bytes = bytes(
                round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections
            )

            if self._ser:
                self._ser.write(b"pf" + correction_bytes + b"\n")

            logger.info(
                f"Set pump corrections: {pump1_correction:.3f}, {pump2_correction:.3f}",
            )
            return True

        except ValueError as e:
            raise HALOperationError(
                f"Invalid correction values: {e}",
                "set_pump_corrections",
            )
        except Exception as e:
            raise HALOperationError(
                f"Failed to set pump corrections: {e}",
                "set_pump_corrections",
            )

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _find_pico_devices(self) -> list:
        """Find all potential PicoEZSPR devices."""
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
        """Verify device is PicoEZSPR."""
        if not self._ser:
            return False

        try:
            cmd = "id\n"
            self._ser.write(cmd.encode())
            reply = self._ser.readline()[0:5].decode()
            logger.debug(f"Device ID response: {reply}")

            if reply == "EZSPR":
                # Get firmware version
                cmd = "iv\n"
                self._ser.write(cmd.encode())
                version = self._ser.readline()[0:4].decode()
                self._firmware_version = version
                logger.debug(f"EZSPR firmware version: {version}")
                return True

            return False

        except Exception as e:
            logger.debug(f"ID verification failed: {e}")
            return False

    def _test_communication(self) -> bool:
        """Test basic communication with device."""
        if not self._ser:
            return False

        try:
            with suppress(Exception):
                self._ser.reset_input_buffer()

            cmd = "id\n"
            self._ser.write(cmd.encode())
            time.sleep(0.1)

            response = self._ser.readline()
            reply = response.decode(errors="ignore").strip()
            return "EZSPR" in reply

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
