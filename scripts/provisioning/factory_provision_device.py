"""Factory Device Provisioning Script

Run this script at the QC station before shipping devices to customers.
Creates pre-configured device configuration and exports to USB drive.

Author: AI Assistant
Date: October 11, 2025
Version: 1.0

Usage:
    python factory_provision_device.py
"""

from __future__ import annotations

import sys
from datetime import datetime

from utils.device_configuration import DeviceConfiguration
from utils.hardware_detection import HardwareDetector
from utils.logger import logger


def print_header():
    """Print factory provisioning header."""
    print("\n" + "=" * 70)
    print("  AFFINITÉ FACTORY DEVICE PROVISIONING")
    print("  Version 1.0")
    print("=" * 70)
    print()


def detect_hardware() -> dict:
    """Detect connected hardware."""
    print("🔍 Step 1: Detecting Hardware...")
    print("-" * 70)

    detector = HardwareDetector()
    detected = detector.detect_all_hardware()

    # Print detection results
    detector.print_detected_hardware()

    # Validate
    if not detected["spectrometer"]:
        print("\n❌ ERROR: Spectrometer not detected!")
        print("   Please connect the spectrometer and try again.")
        return None

    if not detected["controller"]:
        print("\n⚠️  WARNING: Controller not detected")
        print("   This is optional for provisioning.")

    print("\n✅ Hardware detection complete")
    return detected


def get_physical_configuration() -> tuple[int, str] | None:
    """Get physical configuration from QC operator."""
    print("\n📋 Step 2: Physical Configuration")
    print("-" * 70)

    # Optical fiber diameter
    print("\n🔬 Optical Fiber Diameter:")
    print("  1. 100 µm (Higher resolution, lower signal)")
    print("  2. 200 µm (Higher signal, most common)")
    print()

    while True:
        fiber_choice = input("Select optical fiber (1/2): ").strip()
        if fiber_choice == "1":
            optical_fiber = 100
            break
        if fiber_choice == "2":
            optical_fiber = 200
            break
        print("❌ Invalid choice. Please enter 1 or 2.")

    print(f"✅ Optical Fiber: {optical_fiber} µm")

    # LED PCB model
    print("\n💡 LED PCB Model:")
    print("  1. Luminus Cool White (Most common)")
    print("  2. Osram Warm White")
    print()

    while True:
        led_choice = input("Select LED PCB model (1/2): ").strip()
        if led_choice == "1":
            led_pcb_model = "luminus_cool_white"
            break
        if led_choice == "2":
            led_pcb_model = "osram_warm_white"
            break
        print("❌ Invalid choice. Please enter 1 or 2.")

    print(f"✅ LED PCB Model: {led_pcb_model.replace('_', ' ').title()}")

    return optical_fiber, led_pcb_model


def generate_device_id(detected: dict) -> str:
    """Generate unique device ID."""
    year = datetime.now().strftime("%Y")

    if detected["spectrometer"] and detected["spectrometer"]["serial_number"]:
        # Use last 4 digits of spectrometer serial
        spec_serial = detected["spectrometer"]["serial_number"]
        suffix = spec_serial[-4:] if len(spec_serial) >= 4 else spec_serial
    else:
        # Use timestamp
        suffix = datetime.now().strftime("%m%d%H%M")[-4:]

    return f"DEV-{year}-{suffix}"


def create_configuration(
    detected: dict,
    optical_fiber: int,
    led_pcb_model: str,
    device_id: str,
) -> DeviceConfiguration:
    """Create device configuration."""
    print("\n⚙️  Step 3: Creating Configuration...")
    print("-" * 70)

    config = DeviceConfiguration()

    # Set basic configuration
    config.set_optical_fiber_diameter(optical_fiber)
    config.set_led_pcb_model(led_pcb_model)

    # Set device ID
    config.config["device_info"]["device_id"] = device_id
    config.config["device_info"]["created_date"] = datetime.now().isoformat()

    # Set hardware information
    if detected["spectrometer"]:
        serial = detected["spectrometer"]["serial_number"]
        if serial:
            config.set_spectrometer_serial(serial)

    # Mark as factory configured
    config.config["device_info"]["factory_provisioned"] = True
    config.config["device_info"]["provisioning_date"] = datetime.now().isoformat()

    # Validate configuration
    is_valid, errors = config.validate()
    if not is_valid:
        print("\n❌ Configuration validation failed:")
        for error in errors:
            print(f"   • {error}")
        return None

    print("✅ Configuration created and validated")
    return config


def export_to_usb(config: DeviceConfiguration, device_id: str) -> bool:
    """Export configuration to USB drive."""
    print("\n💾 Step 4: Exporting to USB Drive...")
    print("-" * 70)

    # Try to find USB drive
    usb_drives = []
    if sys.platform == "win32":
        import string
        from pathlib import Path

        # Check all drive letters
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists() and drive.is_dir():
                # Check if it's removable (heuristic: not C: or D:)
                if letter not in ["C", "D"]:
                    usb_drives.append(drive)

    if not usb_drives:
        print("\n⚠️  No USB drive detected automatically.")
        print("   Please enter the path manually.")
        usb_path = input("USB drive path (e.g., E:\\): ").strip()
        usb_drive = Path(usb_path)
    else:
        print("\n📁 Detected USB drives:")
        for i, drive in enumerate(usb_drives, 1):
            print(f"  {i}. {drive}")

        if len(usb_drives) == 1:
            usb_drive = usb_drives[0]
            print(f"\nUsing: {usb_drive}")
        else:
            choice = input(f"\nSelect drive (1-{len(usb_drives)}): ").strip()
            try:
                usb_drive = usb_drives[int(choice) - 1]
            except (ValueError, IndexError):
                print("❌ Invalid choice")
                return False

    # Create filename
    filename = f"device_config_{device_id}.json"
    export_path = usb_drive / filename

    try:
        # Export configuration
        config.export_config(str(export_path))
        print(f"✅ Configuration exported to: {export_path}")

        # Also save a copy to factory records
        factory_records = Path("factory_records")
        factory_records.mkdir(exist_ok=True)
        factory_copy = factory_records / filename
        config.export_config(str(factory_copy))
        print(f"✅ Factory copy saved to: {factory_copy}")

        return True

    except Exception as e:
        print(f"❌ Export failed: {e}")
        logger.error(f"Export failed: {e}")
        return False


def print_label_info(
    device_id: str,
    config: DeviceConfiguration,
    detected: dict,
):
    """Print device label information."""
    print("\n" + "=" * 70)
    print("  📋 PRINT THIS LABEL AND ATTACH TO DEVICE")
    print("=" * 70)
    print()
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  AFFINITÉ SPR SYSTEM                                         │")
    print("│                                                              │")
    print(f"│  Device ID: {device_id:<45} │")

    if detected["spectrometer"] and detected["spectrometer"]["serial_number"]:
        spec_sn = detected["spectrometer"]["serial_number"]
        print(f"│  Spectrometer S/N: {spec_sn:<40} │")

    print("│                                                              │")
    print("│  CONFIGURATION:                                              │")

    fiber = config.get_optical_fiber_diameter()
    print(f"│    • Optical Fiber: {fiber} µm{' ' * (38 - len(str(fiber)))} │")

    led = config.get_led_pcb_model().replace("_", " ").title()
    print(f"│    • LED PCB: {led:<47} │")

    print("│    • Controller: Raspberry Pi Pico P4SPR                    │")
    print("│                                                              │")

    mfg_date = datetime.now().strftime("%Y-%m-%d")
    print(f"│  Manufacturing Date: {mfg_date:<40} │")

    print("│  QC Approved: _________                                     │")
    print("│                                                              │")
    print("│  🔗 Setup Instructions: affinite.com/setup                   │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def main():
    """Main provisioning workflow."""
    try:
        print_header()

        # Step 1: Detect hardware
        detected = detect_hardware()
        if not detected:
            print("\n❌ Provisioning failed: Hardware detection error")
            return 1

        input("\nPress Enter to continue...")

        # Step 2: Get physical configuration
        result = get_physical_configuration()
        if not result:
            print("\n❌ Provisioning failed: Configuration error")
            return 1

        optical_fiber, led_pcb_model = result

        # Step 3: Generate device ID
        device_id = generate_device_id(detected)
        print(f"\n🆔 Generated Device ID: {device_id}")

        input("\nPress Enter to continue...")

        # Step 4: Create configuration
        config = create_configuration(
            detected,
            optical_fiber,
            led_pcb_model,
            device_id,
        )
        if not config:
            print("\n❌ Provisioning failed: Configuration creation error")
            return 1

        input("\nPress Enter to continue...")

        # Step 5: Export to USB
        if not export_to_usb(config, device_id):
            print("\n❌ Provisioning failed: Export error")
            return 1

        # Step 6: Print label
        print_label_info(device_id, config, detected)

        # Success summary
        print("=" * 70)
        print("  ✅ DEVICE PROVISIONING COMPLETE")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Print and attach the label to the device")
        print("  2. Include the USB drive with the device shipment")
        print("  3. Pack the device for shipping")
        print()
        print(f"Device ID: {device_id}")
        print("Configuration saved to USB drive and factory records")
        print()

        logger.info(f"Device provisioned successfully: {device_id}")

        return 0

    except KeyboardInterrupt:
        print("\n\n👋 Provisioning cancelled by operator")
        return 1
    except Exception as e:
        print(f"\n\n❌ Provisioning failed: {e}")
        logger.exception("Provisioning error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
