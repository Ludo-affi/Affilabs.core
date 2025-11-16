"""Test LED Batch Commands

Demonstrates batch LED command functionality with the new HAL.
This script shows how to use batch commands for optimized LED control.
"""

import sys
import time
from pathlib import Path

# Add Old software directory to path
old_software_path = Path(__file__).parent / "Old software"
sys.path.insert(0, str(old_software_path))

# Change to Old software directory for settings to work
import os
os.chdir(old_software_path)

from utils.controller import PicoP4SPR, ArduinoController
from utils.hal.adapters import CtrlLEDAdapter
from utils.hal.interfaces import LEDCommand
from utils.led_batch import LEDBatchBuilder, create_calibration_batch


def test_batch_commands():
    """Test batch command functionality"""
    
    print("=" * 60)
    print("LED HAL Batch Command Test")
    print("=" * 60)
    
    # Try to connect to controller
    print("\n1. Searching for controller...")
    
    controller = None
    try:
        # Try Pico first
        controller = PicoP4SPR()
        # Ensure it's connected
        if hasattr(controller, 'connect'):
            controller.connect()
        print(f"   ✅ Found Pico controller: {type(controller).__name__}")
    except Exception as e:
        print(f"   ⚠️  Pico not found: {e}")
        try:
            # Try Arduino
            controller = ArduinoController()
            if hasattr(controller, 'connect'):
                controller.connect()
            print(f"   ✅ Found Arduino controller: {type(controller).__name__}")
        except Exception as e2:
            print(f"   ❌ No controller found: {e2}")
            print("\n⚠️  Cannot test without hardware, showing examples only\n")
            show_usage_examples()
            return
    
    if controller is None:
        show_usage_examples()
        return
    
    # Create LED HAL adapter
    led_hal = CtrlLEDAdapter(controller)
    
    # Check capabilities
    print("\n2. Checking LED HAL capabilities...")
    caps = led_hal.get_capabilities()
    print(f"   Controller: {caps['controller_type']}")
    print(f"   Batch support: {caps['supports_batch']}")
    print(f"   Channels: {caps['channels']}")
    print(f"   Modes: {caps['modes']}")
    print(f"   Max intensity: {caps['max_intensity']}")
    
    # Test 1: Builder pattern
    print("\n3. Testing builder pattern (fluent interface)...")
    batch = LEDBatchBuilder()
    success = batch.set_mode('s')\
                   .set_intensity('a', 180)\
                   .set_intensity('b', 200)\
                   .set_intensity('c', 150)\
                   .set_intensity('d', 100)\
                   .execute(led_hal)
    
    if success:
        print("   ✅ Batch executed successfully")
    else:
        print("   ❌ Batch execution failed")
    
    time.sleep(0.5)
    
    # Test 2: Helper function
    print("\n4. Testing helper function (create_calibration_batch)...")
    commands = create_calibration_batch('p', {
        'a': 200,
        'b': 180,
        'c': 160,
        'd': 140
    })
    success = led_hal.execute_batch(commands)
    
    if success:
        print("   ✅ Calibration batch executed successfully")
    else:
        print("   ❌ Calibration batch failed")
    
    time.sleep(0.5)
    
    # Test 3: Manual command list
    print("\n5. Testing manual command list...")
    commands = [
        LEDCommand('mode', mode='s'),
        LEDCommand('intensity', channel='a', intensity=220),
        LEDCommand('intensity', channel='b', intensity=220),
    ]
    success = led_hal.execute_batch(commands)
    
    if success:
        print("   ✅ Manual batch executed successfully")
    else:
        print("   ❌ Manual batch failed")
    
    time.sleep(0.5)
    
    # Test 4: Compare batch vs sequential timing
    print("\n6. Performance comparison (batch vs sequential)...")
    
    # Batch approach
    start = time.perf_counter()
    batch = LEDBatchBuilder()
    batch.set_mode('p')\
         .set_intensity('a', 180)\
         .set_intensity('b', 190)\
         .set_intensity('c', 200)\
         .set_intensity('d', 210)\
         .execute(led_hal)
    batch_time = time.perf_counter() - start
    print(f"   Batch time: {batch_time*1000:.2f} ms")
    
    time.sleep(0.5)
    
    # Sequential approach
    start = time.perf_counter()
    led_hal.set_mode('s')
    led_hal.set_intensity('a', 210)
    led_hal.set_intensity('b', 200)
    led_hal.set_intensity('c', 190)
    led_hal.set_intensity('d', 180)
    sequential_time = time.perf_counter() - start
    print(f"   Sequential time: {sequential_time*1000:.2f} ms")
    
    if batch_time < sequential_time:
        speedup = sequential_time / batch_time
        print(f"   \u2705 Batch is {speedup:.1f}x faster!")
    else:
        print(f"   \u26a0\ufe0f Sequential was faster (controller may not support batch)")
    
    # Cleanup
    print("\n7. Turning off all LEDs...")
    led_hal.turn_off_channels()
    print("   \u2705 LEDs off")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


def show_usage_examples():
    """Show usage examples without hardware"""
    print("\n" + "=" * 60)
    print("LED Batch Command Usage Examples")
    print("=" * 60)
    
    print("""
# Example 1: Builder Pattern (Fluent Interface)
from utils.led_batch import LEDBatchBuilder

batch = LEDBatchBuilder()
batch.set_mode('s')\\
     .set_intensity('a', 180)\\
     .set_intensity('b', 200)\\
     .set_intensity('c', 150)\\
     .set_intensity('d', 100)\\
     .execute(led_controller)

# Example 2: Helper Function
from utils.led_batch import create_calibration_batch

commands = create_calibration_batch('p', {
    'a': 180,
    'b': 200,
    'c': 150,
    'd': 100
})
led_controller.execute_batch(commands)

# Example 3: Manual Command List
from utils.hal.interfaces import LEDCommand

commands = [
    LEDCommand('mode', mode='s'),
    LEDCommand('intensity', channel='a', intensity=180),
    LEDCommand('intensity', channel='b', intensity=200),
]
led_controller.execute_batch(commands)

# Example 4: Capability Check
caps = led_controller.get_capabilities()
if caps.get('supports_batch', False):
    # Use optimized batch
    batch.set_mode('s').set_intensity('a', 180).execute(led_controller)
else:
    # Fall back to individual commands
    led_controller.set_mode('s')
    led_controller.set_intensity('a', 180)

# Example 5: Integration in Acquisition Loop
# Before starting acquisition cycle:
batch = LEDBatchBuilder()
batch.set_mode('s')
for ch, intensity in channel_intensities.items():
    batch.set_intensity(ch, intensity)
batch.execute(led_controller)

# Then proceed with individual channel acquisitions
    """)
    
    print("=" * 60)


if __name__ == "__main__":
    test_batch_commands()
