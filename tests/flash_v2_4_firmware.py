"""Flash V2.4 Firmware to PicoP4SPR using Software BOOTSEL
Automatically updates firmware via serial reboot command.
"""

import logging
import shutil
import time
from pathlib import Path

import serial
import serial.tools.list_ports

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)


def find_pico_port():
    """Find COM port for Pico P4SPR."""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        # Pico shows up with VID 0x2E8A
        if port.vid == 0x2E8A:
            logger.info(f"Found Pico on {port.device}")
            return port.device

    logger.error("No Pico device found")
    return None


def get_firmware_version(ser):
    """Query current firmware version."""
    try:
        ser.reset_input_buffer()
        ser.write(b'id\n')
        time.sleep(0.2)

        lines = []
        for _ in range(3):
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line:
                lines.append(line)

        # Look for version in response
        for line in lines:
            if line.startswith('V'):
                return line

        return "Unknown"
    except Exception as e:
        logger.warning(f"Could not read version: {e}")
        return "Unknown"


def reboot_to_bootsel(ser):
    """Reboot Pico into BOOTSEL mode using software command."""
    try:
        logger.info("Sending reboot command to enter BOOTSEL mode...")
        ser.reset_input_buffer()

        # Try multiple reboot commands that might be supported
        commands = [b'reboot\n', b'ib\n', b'iB\n']

        for cmd in commands:
            ser.write(cmd)
            time.sleep(0.3)

        logger.info("Reboot command sent. Waiting for bootloader drive...")
        return True

    except Exception as e:
        logger.error(f"Failed to send reboot command: {e}")
        return False


def wait_for_bootloader_drive(timeout=15.0):
    """Wait for RPI-RP2 bootloader drive to appear."""
    import string
    from ctypes import windll

    start_time = time.time()

    logger.info("Waiting for RPI-RP2 drive...")

    while time.time() - start_time < timeout:
        try:
            # Check all drive letters
            import win32api

            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_path = Path(f"{letter}:\\")
                    if drive_path.exists():
                        try:
                            volume_info = win32api.GetVolumeInformation(str(drive_path))
                            if volume_info[0] == "RPI-RP2":
                                logger.info(f"✅ Found bootloader drive: {drive_path}")
                                return drive_path
                        except:
                            pass
                bitmask >>= 1
        except Exception as e:
            logger.debug(f"Error checking drives: {e}")

        time.sleep(0.5)

    logger.error(f"❌ Bootloader drive not found after {timeout}s")
    logger.info("   Try manually: Hold BOOTSEL button, plug USB, release button")
    return None


def flash_firmware(bootloader_drive, firmware_path):
    """Copy firmware to bootloader drive."""
    try:
        if not firmware_path.exists():
            logger.error(f"❌ Firmware file not found: {firmware_path}")
            return False

        dest_path = bootloader_drive / firmware_path.name
        logger.info(f"Copying firmware to {dest_path}...")

        shutil.copy2(firmware_path, dest_path)

        logger.info("✅ Firmware copied! Device will reboot automatically...")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to copy firmware: {e}")
        return False


def wait_for_reconnect(original_port, timeout=20.0):
    """Wait for device to reconnect after flashing."""
    start_time = time.time()

    logger.info("Waiting for device to reconnect...")

    while time.time() - start_time < timeout:
        port = find_pico_port()
        if port:
            time.sleep(2)  # Give it a moment to fully boot
            return port
        time.sleep(0.5)

    return None


def verify_firmware(port, expected_version="V2.4"):
    """Verify firmware was flashed correctly."""
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(1)

        version = get_firmware_version(ser)
        ser.close()

        if expected_version in version:
            logger.info(f"✅ Firmware verified: {version}")
            return True
        else:
            logger.warning(f"⚠️  Unexpected version: {version}")
            return False

    except Exception as e:
        logger.error(f"Failed to verify firmware: {e}")
        return False


def main():
    print("=" * 70)
    print("PicoP4SPR Firmware Update: V2.4.1 (Latest)")
    print("=" * 70)

    # Firmware path - V2.4.1 (compiled Dec 14, 2025)
    firmware_path = Path(__file__).parent / "firmware_archive" / "pico_p4spr" / "affinite_p4spr_v2.4.1.uf2"

    if not firmware_path.exists():
        print(f"\n❌ ERROR: Firmware file not found!")
        print(f"   Expected: {firmware_path}")
        return False

    print(f"\n✅ Found firmware: {firmware_path.name}")
    print(f"   Size: {firmware_path.stat().st_size:,} bytes")

    # Find device
    print("\n[1/5] Finding Pico device...")
    port = find_pico_port()
    if not port:
        print("\n❌ No Pico found. Make sure device is connected.")
        return False

    print(f"   ✅ Found device on {port}")

    # Get current version
    print("\n[2/5] Checking current firmware version...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(1)
        current_version = get_firmware_version(ser)
        print(f"   Current version: {current_version}")

        if "V2.4" in current_version:
            print("\n⚠️  Device already has V2.4 firmware!")
            response = input("   Continue anyway? (y/n): ").strip().lower()
            if response != 'y':
                ser.close()
                print("Update cancelled.")
                return False

        # Reboot to bootsel
        print("\n[3/5] Rebooting to BOOTSEL mode...")
        reboot_to_bootsel(ser)
        ser.close()

    except Exception as e:
        print(f"   ⚠️  Could not communicate with device: {e}")
        print("   Proceeding with manual BOOTSEL...")

    # Wait for bootloader
    print("\n[4/5] Waiting for bootloader drive...")
    bootloader_drive = wait_for_bootloader_drive(timeout=15.0)

    if not bootloader_drive:
        print("\n❌ Bootloader drive not detected!")
        print("\nManual BOOTSEL Instructions:")
        print("1. Unplug the Pico USB cable")
        print("2. Hold down the BOOTSEL button (white button on board)")
        print("3. While holding BOOTSEL, plug in the USB cable")
        print("4. Release the BOOTSEL button")
        print("5. Run this script again")
        return False

    # Flash firmware
    print("\n[5/5] Flashing firmware...")
    if not flash_firmware(bootloader_drive, firmware_path):
        return False

    # Wait and verify
    print("\n[Verification] Waiting for device to reconnect...")
    new_port = wait_for_reconnect(port, timeout=20.0)

    if new_port:
        print(f"   Device reconnected on {new_port}")
        time.sleep(2)

        if verify_firmware(new_port, "V2.4"):
            print("\n" + "=" * 70)
            print("✅ FIRMWARE UPDATE COMPLETE!")
            print("=" * 70)
            print(f"\nDevice: {new_port}")
            print("Firmware: V2.4 (CYCLE_SYNC)")
            print("\nNew features:")
            print("  • 75% less USB traffic (CYCLE_START synchronization)")
            print("  • Hardware timer-based LED sequencing")
            print("  • Deterministic timing (1ms precision)")
            print("  • Autonomous multi-cycle operation")
            return True
        else:
            print("\n⚠️  Firmware flashed but verification failed")
            print("   Device may still be working - check manually")
            return False
    else:
        print("\n⚠️  Device did not reconnect in time")
        print("   Firmware may have been flashed successfully")
        print("   Check device manually")
        return False


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Update cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
