"""Example: Using Controller HAL to replace string-based device checks.

This demonstrates how to refactor existing code to use the Controller HAL
for type-safe capability queries instead of fragile string matching.
"""

import sys
from pathlib import Path

# Add Old software directory to path
sys.path.insert(0, str(Path(__file__).parent / "Old software"))

from utils.controller import PicoP4SPR
from utils.hal.controller_hal import create_controller_hal


def old_way_example(device_config, ctrl):
    """OLD WAY: Fragile string matching scattered throughout code."""
    # Problem 1: Fragile - easy to miss a device type
    if device_config["ctrl"] in ["P4SPR", "PicoP4SPR"]:
        ctrl.set_mode("s")  # Polarizer control

    # Problem 2: Duplicate lists across codebase
    if device_config["ctrl"] in ["PicoP4SPR"]:
        ctrl.set_batch_intensities(a=255, b=128, c=64, d=0)
    else:
        # Sequential fallback
        ctrl.set_intensity("a", 255)
        ctrl.set_intensity("b", 128)
        ctrl.set_intensity("c", 64)
        ctrl.set_intensity("d", 0)

    # Problem 3: Long condition chains
    if device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
        corrections = ctrl.get_pump_corrections()

    # Problem 4: Temperature check scattered everywhere
    if device_config["ctrl"] in ["PicoP4SPR"]:
        temp = ctrl.get_temp()
        print(f"Temperature: {temp}°C")


def new_way_example(ctrl):
    """NEW WAY: Clean, type-safe capability queries."""
    # Wrap controller with HAL
    hal = create_controller_hal(ctrl)

    # Type-safe capability check
    if hal.supports_polarizer:
        hal.set_mode("s")

    # Batch command if available, otherwise automatic fallback
    if hal.supports_batch_leds:
        hal.set_batch_intensities(a=255, b=128, c=64, d=0)
    else:
        # Fallback to sequential
        hal.set_intensity("a", 255)
        hal.set_intensity("b", 128)
        hal.set_intensity("c", 64)
        hal.set_intensity("d", 0)
        hal.set_intensity("a", 255)
        hal.set_intensity("b", 128)
        hal.set_intensity("c", 64)
        hal.set_intensity("d", 0)

    # Clean capability check
    if hal.supports_pump:
        corrections = hal.get_pump_corrections()

    # Unified temperature access
    temp = hal.get_temperature()
    if temp > 0:
        print(f"Temperature: {temp}°C")


def real_world_example():
    """Real-world example: Hardware-dependent UI initialization."""
    # Simulate hardware initialization
    ctrl = PicoP4SPR()
    if not ctrl.open():
        print("Failed to open controller")
        return

    # Wrap with HAL
    hal = create_controller_hal(ctrl)

    print(f"\n=== Device: {hal.get_device_type()} {hal.get_firmware_version()} ===\n")

    # Enable/disable features based on actual hardware
    print("Available features:")
    print(f"  ✓ LED control ({hal.channel_count} channels)")

    if hal.supports_polarizer:
        print("  ✓ Polarizer control")

    if hal.supports_batch_leds:
        print("  ✓ Batch LED commands (15x faster)")

    if hal.supports_pump:
        print("  ✓ Pump control")

    if hal.supports_firmware_update:
        print("  ✓ Firmware updates")

    temp = hal.get_temperature()
    if temp > 0:
        print(f"  ✓ Temperature monitoring ({temp}°C)")

    print("\n=== Setting up LEDs ===\n")

    # Use batch command if available
    if hal.supports_batch_leds:
        print("Using fast batch command...")
        hal.set_batch_intensities(a=255, b=128, c=64, d=32)
    else:
        print("Using sequential commands...")
        hal.set_intensity("a", 255)
        hal.set_intensity("b", 128)
        hal.set_intensity("c", 64)
        hal.set_intensity("d", 32)

    print("✓ LEDs configured")

    # Polarizer control if available
    if hal.supports_polarizer:
        print("\n=== Configuring polarizer ===\n")
        hal.set_mode("s")
        position = hal.get_polarizer_position()
        print(f"✓ Polarizer set to S-polarization: {position}")


def comparison_example():
    """Side-by-side comparison of old vs new approach."""
    print("\n" + "=" * 60)
    print("BEFORE: Fragile string matching")
    print("=" * 60)
    print("""
    # Scattered throughout codebase
    if self.device_config["ctrl"] in ["P4SPR", "PicoP4SPR"]:
        self.ctrl.set_mode('s')

    if self.device_config["ctrl"] in ["PicoP4SPR"]:
        self.ctrl.set_batch_intensities(...)

    if self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
        self.ctrl.get_pump_corrections()

    # Problems:
    # - Easy to miss a device type
    # - Duplicate lists across files
    # - Hard to test without hardware
    # - No type checking
    """)

    print("\n" + "=" * 60)
    print("AFTER: Type-safe HAL")
    print("=" * 60)
    print("""
    # Clean and type-safe
    hal = create_controller_hal(self.ctrl)

    if hal.supports_polarizer:
        hal.set_mode('s')

    if hal.supports_batch_leds:
        hal.set_batch_intensities(...)

    if hal.supports_pump:
        hal.get_pump_corrections()

    # Benefits:
    # - Type-safe capability queries
    # - Single source of truth
    # - Easy to mock for testing
    # - IDE autocomplete support
    # - Centralized device capabilities
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("Controller HAL Usage Examples")
    print("=" * 60)

    # Real-world example
    real_world_example()

    # Comparison
    comparison_example()

    print("\n" + "=" * 60)
    print("See CONTROLLER_HAL_COMPLETE.md for full documentation")
    print("=" * 60)
