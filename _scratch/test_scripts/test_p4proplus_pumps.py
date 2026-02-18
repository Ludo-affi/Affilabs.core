"""Test P4PROPLUS internal pump control.

This script demonstrates the pump control features available on P4PROPLUS V2.3+
devices. Regular P4PRO devices will show a warning that pumps are not available.
"""
import time
from affilabs.utils.controller import PicoP4PRO

print("=" * 70)
print("P4PRO/P4PROPLUS PUMP CONTROL TEST")
print("=" * 70)

# Connect to controller
print("\n1. Connecting to P4PRO/P4PROPLUS controller...")
ctrl = PicoP4PRO()
if not ctrl.open():
    print("❌ Failed to connect to P4PRO/P4PROPLUS!")
    exit(1)

print(f"✅ Connected to {ctrl.firmware_id} (version {ctrl.version})")
print(f"   Device has internal pumps: {ctrl.has_pumps()}")

if not ctrl.has_pumps():
    print("\n⚠️  This is a standard P4PRO without internal pumps.")
    print("   Pump commands are only available on P4PROPLUS V2.3+")
    ctrl.close()
    exit(0)

# This is a P4PROPLUS - test pump features
print("\n" + "=" * 70)
print("P4PROPLUS PUMP FEATURES")
print("=" * 70)

# Read pump calibration
print("\n2. Reading pump calibration...")
cal = ctrl.pump_read_calibration()
if cal:
    pump1_pct, pump2_pct = cal
    print(f"   Pump 1 calibration: {pump1_pct}%")
    print(f"   Pump 2 calibration: {pump2_pct}%")
else:
    print("   ❌ Could not read calibration")

# Read pump cycle counts
print("\n3. Reading pump cycle counts...")
counts = ctrl.pump_read_cycle_counts()
if counts:
    count1, count2 = counts
    print(f"   Pump 1 cycles: {count1}")
    print(f"   Pump 2 cycles: {count2}")
else:
    print("   ❌ Could not read cycle counts")

# Test pump control
print("\n4. Testing pump control...")
print("   NOTE: Ensure pumps are not connected to anything before running!")
input("   Press ENTER to test pumps at low speed (25 RPM) or Ctrl+C to skip...")

try:
    # Run pump 1 at 25 RPM
    print("\n   Running pump 1 at 25 RPM for 3 seconds...")
    if ctrl.pump_run(1, 25):
        time.sleep(3)
        if ctrl.pump_stop(1):
            print("   ✓ Pump 1 test complete")
        else:
            print("   ❌ Failed to stop pump 1")
    else:
        print("   ❌ Failed to start pump 1")

    time.sleep(1)

    # Run pump 2 at 25 RPM
    print("\n   Running pump 2 at 25 RPM for 3 seconds...")
    if ctrl.pump_run(2, 25):
        time.sleep(3)
        if ctrl.pump_stop(2):
            print("   ✓ Pump 2 test complete")
        else:
            print("   ❌ Failed to stop pump 2")
    else:
        print("   ❌ Failed to start pump 2")

    time.sleep(1)

    # Run both pumps at 25 RPM
    print("\n   Running both pumps at 25 RPM for 3 seconds...")
    if ctrl.pump_run(3, 25):
        time.sleep(3)
        if ctrl.pump_stop(3):
            print("   ✓ Both pumps test complete")
        else:
            print("   ❌ Failed to stop both pumps")
    else:
        print("   ❌ Failed to start both pumps")

    print("\n✅ Pump control test completed successfully!")

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted - stopping all pumps...")
    ctrl.pump_stop(3)
    print("   Pumps stopped")

# Read cycle counts again to see if they incremented
print("\n5. Reading final pump cycle counts...")
counts = ctrl.pump_read_cycle_counts()
if counts:
    count1, count2 = counts
    print(f"   Pump 1 cycles: {count1}")
    print(f"   Pump 2 cycles: {count2}")

# Cleanup
ctrl.close()
print("\n" + "=" * 70)
print("Test complete - connection closed")
print("=" * 70)
