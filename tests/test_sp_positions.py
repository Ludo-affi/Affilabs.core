"""Test S/P Polarizer Positions with Light Measurement

Tests that both S and P positions transmit light correctly.
"""

import time
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from affilabs.utils.usb4000_wrapper import USB4000
from affilabs.utils.hal.controller_hal import create_controller_hal
from affilabs.utils.device_configuration import DeviceConfiguration
from affilabs.core.hardware_manager import HardwareManager

def test_sp_positions():
    """Test S and P positions see light."""
    print("\n" + "="*80)
    print("TESTING S/P POLARIZER POSITIONS WITH LIGHT")
    print("="*80)
    
    # Initialize hardware
    print("\n1. Initializing hardware...")
    hm = HardwareManager()
    
    # Scan and connect
    print("Scanning for devices...")
    hm.scan_and_connect(auto_connect=True)
    
    # Wait for connection to complete
    print("Waiting for hardware connection...")
    for i in range(30):  # Wait up to 15 seconds
        if hm.ctrl and hm.usb:
            print(f"✓ Hardware connected after {i * 0.5:.1f}s")
            break
        time.sleep(0.5)
    else:
        print("❌ Hardware connection timeout!")
        return False
    
    ctrl = hm.ctrl
    usb = hm.usb
    
    print(f"✓ Connected: {type(ctrl).__name__}, {usb.serial_number}")
    
    # Load device config to get S/P positions
    print("\n2. Loading device config...")
    device_config = DeviceConfiguration(device_serial=usb.serial_number)
    servo_pos = device_config.get_servo_positions()
    s_pos = servo_pos["s"]
    p_pos = servo_pos["p"]
    print(f"✓ S position: {s_pos}")
    print(f"✓ P position: {p_pos}")
    
    # Configure servo positions in firmware
    print("\n3. Configuring servo positions in firmware...")
    if hasattr(ctrl, 'servo_move_calibration_only'):
        ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
        time.sleep(0.5)
        print("✓ Positions configured")
    else:
        print("⚠️  servo_move_calibration_only not available")
    
    # Set integration time
    integration_ms = 50.0
    usb.set_integration(integration_ms)
    print(f"\n4. Integration time set to {integration_ms}ms")
    
    # Turn on all LEDs to moderate intensity
    print("\n5. Turning on all LEDs to intensity 100...")
    ctrl.set_batch_intensities(a=100, b=100, c=100, d=100)
    time.sleep(0.5)
    print("✓ LEDs ON")
    
    # Test S position
    print("\n" + "="*80)
    print("TESTING S-MODE")
    print("="*80)
    print(f"Moving servo to S position ({s_pos})...")
    ctrl.set_mode("s")
    time.sleep(1.0)  # Wait for servo to settle
    
    spectrum_s = usb.read_intensity()
    signal_s = spectrum_s.mean()
    max_s = spectrum_s.max()
    print(f"✓ S-mode signal: mean={signal_s:.0f}, max={max_s:.0f}")
    
    if signal_s > 5000:
        print("✅ S-mode: GOOD signal level")
    else:
        print(f"❌ S-mode: LOW signal ({signal_s:.0f} < 5000)")
    
    # Test P position
    print("\n" + "="*80)
    print("TESTING P-MODE")
    print("="*80)
    print(f"Moving servo to P position ({p_pos})...")
    ctrl.set_mode("p")
    time.sleep(1.0)  # Wait for servo to settle
    
    spectrum_p = usb.read_intensity()
    signal_p = spectrum_p.mean()
    max_p = spectrum_p.max()
    print(f"✓ P-mode signal: mean={signal_p:.0f}, max={max_p:.0f}")
    
    if signal_p > 2000:
        print("✅ P-mode: GOOD signal level")
    else:
        print(f"❌ P-mode: LOW signal ({signal_p:.0f} < 2000)")
    
    # Calculate ratio
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    if signal_s > 0 and signal_p > 0:
        ratio = signal_s / signal_p
        print(f"S/P ratio: {ratio:.2f}")
        if ratio > 1.5:
            print("✅ S/P ratio good (>1.5)")
        else:
            print(f"⚠️  S/P ratio low ({ratio:.2f} < 1.5)")
    
    print(f"\nS-mode: mean={signal_s:.0f}, max={max_s:.0f}")
    print(f"P-mode: mean={signal_p:.0f}, max={max_p:.0f}")
    
    # Cleanup
    print("\n6. Turning off LEDs...")
    ctrl.turn_off_channels()
    print("✓ Cleanup complete")
    
    return True

if __name__ == "__main__":
    try:
        test_sp_positions()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
