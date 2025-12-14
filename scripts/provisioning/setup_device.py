"""
Device Setup Wizard

Quick start wizard for initial device configuration.
Automatically detects hardware and guides user through setup.

Author: AI Assistant
Date: October 11, 2025
Version: 1.0

Usage:
    python setup_device.py
"""

import sys
from pathlib import Path

from utils.logger import logger
from utils.device_configuration import DeviceConfiguration
from utils.hardware_detection import HardwareDetector


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 70)
    print("  SPR SYSTEM SETUP WIZARD")
    print("  Version 1.0")
    print("=" * 70)
    print()


def print_step(step: int, total: int, title: str):
    """Print step header."""
    print(f"\n{'=' * 70}")
    print(f"  STEP {step}/{total}: {title}")
    print("=" * 70)


def hardware_detection_step() -> dict:
    """
    Step 1: Hardware Detection

    Returns:
        Detected hardware information
    """
    print_step(1, 4, "HARDWARE DETECTION")

    print("\n🔍 Scanning for connected devices...")
    print("   Please ensure your devices are connected:")
    print("   • Ocean Optics Spectrometer (USB)")
    print("   • Raspberry Pi Pico Controller (USB)")
    print()

    detector = HardwareDetector()
    detected = detector.detect_all_hardware()

    print("\n📊 Detection Results:")
    detector.print_detected_hardware()

    return detected


def led_pcb_selection_step() -> str:
    """
    Step 2: LED PCB Model Selection

    Returns:
        Selected LED PCB model
    """
    print_step(2, 4, "LED PCB MODEL SELECTION")

    print("\n💡 Select your LED PCB model:")
    print("   1. Luminus Cool White (most common)")
    print("   2. Osram Warm White")
    print()

    while True:
        choice = input("Select LED PCB model (1/2): ").strip()

        if choice == '1':
            return 'luminus_cool_white'
        elif choice == '2':
            return 'osram_warm_white'
        else:
            print("❌ Invalid choice. Please select 1 or 2.")


def fiber_diameter_selection_step() -> int:
    """
    Step 3: Optical Fiber Diameter Selection

    Returns:
        Selected fiber diameter in micrometers
    """
    print_step(3, 4, "OPTICAL FIBER DIAMETER")

    print("\n🔬 Select your optical fiber diameter:")
    print("   1. 100 µm (higher resolution)")
    print("   2. 200 µm (higher signal, most common)")
    print()
    print("   ℹ️  If unsure, select 200 µm (option 2)")
    print()

    while True:
        choice = input("Select fiber diameter (1/2): ").strip()

        if choice == '1':
            return 100
        elif choice == '2':
            return 200
        else:
            print("❌ Invalid choice. Please select 1 or 2.")


def configuration_summary_step(config: DeviceConfiguration):
    """
    Step 4: Configuration Summary & Save

    Args:
        config: Device configuration to display
    """
    print_step(4, 4, "CONFIGURATION SUMMARY")

    print("\n✅ Your device configuration:")
    print()
    print("🔧 Hardware:")
    print(f"   LED PCB Model:      {config.get_led_pcb_model()}")
    print(f"   Optical Fiber:      {config.get_optical_fiber_diameter()} µm")
    print(f"   Spectrometer S/N:   {config.get_spectrometer_serial() or 'Not detected'}")
    print()

    print("⏱️  Timing Parameters:")
    print(f"   Min Integration:    {config.get_min_integration_time()} ms")
    delays = config.get_led_delays()
    print(f"   LED Delays:         A={delays['a']}ms, B={delays['b']}ms, "
          f"C={delays['c']}ms, D={delays['d']}ms")
    print()

    print("📊 Frequency Limits:")
    limits_4 = config.get_frequency_limits(4)
    limits_2 = config.get_frequency_limits(2)
    print(f"   4-LED Mode:         Max {limits_4['max_hz']} Hz")
    print(f"   2-LED Mode:         Max {limits_2['max_hz']} Hz")
    print()


def main():
    """Main setup wizard."""
    print_banner()

    print("This wizard will guide you through initial device configuration.")
    print()

    # Check if configuration already exists
    config = DeviceConfiguration()
    if config.config_file.exists():
        print("⚠️  Existing configuration detected.")
        choice = input("Do you want to reconfigure? (y/n): ").strip().lower()
        if choice != 'y':
            print("\n✅ Keeping existing configuration.")
            print("   Use 'python -m utils.config_cli' to modify settings.")
            return
        print()

    try:
        # Step 1: Hardware Detection
        detected = hardware_detection_step()

        # Step 2: LED PCB Selection
        led_model = led_pcb_selection_step()

        # Step 3: Fiber Diameter Selection
        fiber_diameter = fiber_diameter_selection_step()

        # Create configuration
        config = DeviceConfiguration()
        config.set_led_pcb_model(led_model)
        config.set_optical_fiber_diameter(fiber_diameter)

        # Set spectrometer serial if detected
        if detected['spectrometer'] and detected['spectrometer']['serial_number']:
            config.set_spectrometer_serial(detected['spectrometer']['serial_number'])

        # Step 4: Summary & Save
        configuration_summary_step(config)

        print("\n💾 Save configuration?")
        choice = input("Save and continue? (y/n): ").strip().lower()

        if choice == 'y':
            config.save()
            print("\n✅ Configuration saved successfully!")
            print()
            print("=" * 70)
            print("  SETUP COMPLETE")
            print("=" * 70)
            print()
            print("📋 Next steps:")
            print("   1. Run calibration: python run_app.py")
            print("   2. Or modify settings: python -m utils.config_cli")
            print()
            print("✅ Your SPR system is ready to use!")
        else:
            print("\n❌ Configuration not saved. Run setup again when ready.")

    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Setup error: {e}")
        logger.exception("Setup wizard error")
        sys.exit(1)


if __name__ == "__main__":
    main()
