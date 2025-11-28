"""
Automatic Firmware Updater for PicoP4SPR
Reboots Pico into bootloader mode and flashes new firmware
"""

import serial
import time
import os
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PicoFirmwareUpdater:
    """Handles automatic firmware updates for Pico-based controllers."""

    EXPECTED_VERSION = "V1.2"
    BOOTLOADER_VID = 0x2E8A
    BOOTLOADER_PID = 0x0003

    def __init__(self, com_port: str):
        """Initialize updater for a specific COM port.

        Args:
            com_port: COM port where Pico is connected (e.g., 'COM4')
        """
        self.com_port = com_port
        self.firmware_path = Path(__file__).parent.parent.parent / "firmware" / "pico_p4spr" / "affinite_p4spr_v1.1.uf2"

    def get_current_version(self, ser: serial.Serial) -> Optional[str]:
        """Query current firmware version from Pico.

        Args:
            ser: Open serial connection to Pico

        Returns:
            Version string (e.g., "V1.0") or None if query failed
        """
        try:
            ser.reset_input_buffer()
            ser.write(b"iv\n")
            time.sleep(0.1)
            response = ser.read(20).decode('ascii', errors='ignore').strip()

            # Response format: "V1.0" or similar
            if response and response.startswith('V'):
                return response

            logger.warning(f"Unexpected version response: {repr(response)}")
            return None

        except Exception as e:
            logger.error(f"Failed to query firmware version: {e}")
            return None

    def needs_update(self, current_version: str) -> bool:
        """Check if firmware needs to be updated.

        Args:
            current_version: Current version string (e.g., "V1.0")

        Returns:
            True if update needed, False otherwise
        """
        if current_version == self.EXPECTED_VERSION:
            return False

        logger.info(f"Firmware version mismatch: current={current_version}, expected={self.EXPECTED_VERSION}")
        return True

    def reboot_to_bootloader(self, ser: serial.Serial) -> bool:
        """Reboot Pico into bootloader mode using magic command.

        The Pico SDK provides a way to reboot into BOOTSEL mode programmatically
        by resetting the watchdog with special flags.

        Args:
            ser: Open serial connection to Pico

        Returns:
            True if reboot command sent successfully
        """
        try:
            # Send custom command to trigger bootloader mode
            # We'll add this command to the firmware: "iB\n" = reboot to Bootloader
            ser.reset_input_buffer()
            ser.write(b"iB\n")
            time.sleep(0.5)

            response = ser.read(10)
            logger.info(f"Bootloader reboot response: {repr(response)}")

            # Pico will disconnect and reappear as RPI-RP2 drive
            return True

        except Exception as e:
            logger.error(f"Failed to send bootloader command: {e}")
            return False

    def wait_for_bootloader_drive(self, timeout: float = 10.0) -> Optional[Path]:
        """Wait for RPI-RP2 drive to appear after bootloader reboot.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Path to RPI-RP2 drive or None if not found
        """
        import platform

        start_time = time.time()

        if platform.system() == 'Windows':
            # On Windows, look for drive with label RPI-RP2
            while time.time() - start_time < timeout:
                import string
                from ctypes import windll

                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drive_path = Path(f"{letter}:\\")
                        if drive_path.exists():
                            try:
                                # Check volume label
                                import win32api
                                volume_info = win32api.GetVolumeInformation(str(drive_path))
                                if volume_info[0] == "RPI-RP2":
                                    logger.info(f"Found bootloader drive: {drive_path}")
                                    return drive_path
                            except:
                                pass
                    bitmask >>= 1

                time.sleep(0.5)

        else:
            # On Linux/Mac, look for /media/*/RPI-RP2 or /Volumes/RPI-RP2
            possible_paths = [
                Path("/media") / os.getenv("USER", "user") / "RPI-RP2",
                Path("/Volumes") / "RPI-RP2",
            ]

            while time.time() - start_time < timeout:
                for path in possible_paths:
                    if path.exists():
                        logger.info(f"Found bootloader drive: {path}")
                        return path
                time.sleep(0.5)

        logger.error(f"Bootloader drive not found after {timeout}s")
        return None

    def flash_firmware(self, bootloader_drive: Path) -> bool:
        """Copy firmware .uf2 file to bootloader drive.

        Args:
            bootloader_drive: Path to RPI-RP2 drive

        Returns:
            True if firmware copied successfully
        """
        try:
            if not self.firmware_path.exists():
                logger.error(f"Firmware file not found: {self.firmware_path}")
                return False

            dest_path = bootloader_drive / self.firmware_path.name
            logger.info(f"Copying firmware: {self.firmware_path} -> {dest_path}")

            shutil.copy2(self.firmware_path, dest_path)

            logger.info("Firmware copied successfully. Pico will reboot automatically.")
            return True

        except Exception as e:
            logger.error(f"Failed to copy firmware: {e}")
            return False

    def wait_for_device_reconnect(self, timeout: float = 15.0) -> bool:
        """Wait for Pico to reboot and reconnect after firmware flash.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if device reconnected successfully
        """
        import serial.tools.list_ports

        logger.info(f"Waiting for Pico to reconnect on {self.com_port}...")
        start_time = time.time()

        # Wait a bit for bootloader to finish
        time.sleep(3)

        while time.time() - start_time < timeout:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.device == self.com_port:
                    # Found the port, wait a bit more for firmware to initialize
                    time.sleep(2)
                    logger.info(f"Pico reconnected on {self.com_port}")
                    return True

            time.sleep(0.5)

        logger.error(f"Pico did not reconnect after {timeout}s")
        return False

    def update_firmware(self) -> bool:
        """Perform complete firmware update process.

        Returns:
            True if update successful, False otherwise
        """
        try:
            logger.info(f"Starting firmware update on {self.com_port}")

            # Step 1: Open serial connection
            ser = serial.Serial(self.com_port, 115200, timeout=1)
            time.sleep(0.1)

            # Step 2: Get current version
            current_version = self.get_current_version(ser)
            if not current_version:
                logger.error("Could not read current firmware version")
                ser.close()
                return False

            logger.info(f"Current firmware version: {current_version}")

            # Step 3: Check if update needed
            if not self.needs_update(current_version):
                logger.info("Firmware is already up to date")
                ser.close()
                return True

            # Step 4: Reboot to bootloader
            logger.info("Rebooting Pico into bootloader mode...")
            if not self.reboot_to_bootloader(ser):
                logger.error("Failed to reboot to bootloader")
                ser.close()
                return False

            ser.close()

            # Step 5: Wait for bootloader drive
            bootloader_drive = self.wait_for_bootloader_drive()
            if not bootloader_drive:
                logger.error("Bootloader drive not found")
                return False

            # Step 6: Flash firmware
            if not self.flash_firmware(bootloader_drive):
                logger.error("Failed to flash firmware")
                return False

            # Step 7: Wait for reconnect
            if not self.wait_for_device_reconnect():
                logger.error("Device did not reconnect after firmware update")
                return False

            # Step 8: Verify new version
            ser = serial.Serial(self.com_port, 115200, timeout=1)
            time.sleep(0.5)

            new_version = self.get_current_version(ser)
            ser.close()

            if new_version == self.EXPECTED_VERSION:
                logger.info(f"✅ Firmware update successful: {current_version} -> {new_version}")
                return True
            else:
                logger.error(f"❌ Firmware update verification failed: expected {self.EXPECTED_VERSION}, got {new_version}")
                return False

        except Exception as e:
            logger.error(f"Firmware update failed with exception: {e}")
            return False


def check_and_update_firmware(com_port: str) -> bool:
    """Convenience function to check and update firmware if needed.

    Args:
        com_port: COM port where Pico is connected

    Returns:
        True if firmware is up to date (or update successful), False if update failed
    """
    updater = PicoFirmwareUpdater(com_port)
    return updater.update_firmware()


if __name__ == "__main__":
    # Test firmware updater
    logging.basicConfig(level=logging.INFO)

    import sys
    if len(sys.argv) > 1:
        com_port = sys.argv[1]
    else:
        com_port = "COM4"

    print(f"Testing firmware updater on {com_port}")
    success = check_and_update_firmware(com_port)

    if success:
        print("✅ Firmware is up to date")
    else:
        print("❌ Firmware update failed")
