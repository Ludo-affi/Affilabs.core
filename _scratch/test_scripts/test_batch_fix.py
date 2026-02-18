"""Simple direct test of set_batch_intensities() fix."""
import sys
import time
sys.path.insert(0, 'affilabs')

from utils.controller import PicoP4PRO

print("="*70)
print("TESTING set_batch_intensities() WITH lm:ABCD FIX")
print("="*70)

# Create controller directly
print("\n1. Creating P4PRO controller...")
ctrl = PicoP4PRO()

print("2. Opening connection (auto-detect P4PRO)...")
if not ctrl.open():
    print("❌ Failed to find P4PRO!")
    sys.exit(1)

print(f"   Connected: {ctrl._ser.is_open}")
time.sleep(0.5)
ctrl._ser.read(1000)  # Clear buffer

print("\n3. Turn OFF LEDs (baseline)...")
ctrl._ser.write(b"lx\n")
time.sleep(0.1)
ctrl._ser.read(10)

input("Check detector (should be ~3090). Press Enter...")

print("\n4. Calling ctrl.set_batch_intensities(51, 51, 51, 51)...")
print("   This should now send:")
print("   - lm:ABCD (enable all LEDs)")
print("   - la:51, lb:51, lc:51, ld:51 (set intensities)")
result = ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)
print(f"   Result: {result}")

print("\n** CHECK DETECTOR NOW **")
print("   If fix works: signal should be >5000 counts")
print("   If still broken: signal will be ~3090 counts")

reading = input("\nEnter detector reading: ")

if reading.isdigit() and int(reading) > 5000:
    print("\n✅ SUCCESS! LEDs are ON - set_batch_intensities() fix works!")
elif reading.isdigit() and int(reading) < 4000:
    print("\n❌ FAIL! LEDs still OFF - lm:ABCD command not working")
    print("   Checking what was actually sent...")

    # Try manual commands
    print("\n5. Manual test - send lm:ABCD directly...")
    ctrl._ser.write(b"lm:ABCD\n")
    time.sleep(0.1)
    resp = ctrl._ser.read(10)
    print(f"   Response: {resp!r} {'✓' if resp == b'1' else '✗'}")

    print("\n6. Manual test - send la:51 directly...")
    ctrl._ser.write(b"la:51\n")
    time.sleep(0.1)
    resp = ctrl._ser.read(10)
    print(f"   Response: {resp!r} {'✓' if resp == b'1' else '✗'}")

    reading2 = input("\n   Check detector again - what's the reading? ")
    if reading2.isdigit() and int(reading2) > 5000:
        print("\n   Manual commands work but set_batch_intensities() doesn't!")
        print("   There's a bug in the method implementation.")
    else:
        print("\n   Even manual commands don't work - hardware issue?")

print("\n7. Cleanup - turning off LEDs...")
ctrl._ser.write(b"lx\n")
time.sleep(0.1)
ctrl._ser.read(10)

ctrl.close()
print("\nTest complete!")
