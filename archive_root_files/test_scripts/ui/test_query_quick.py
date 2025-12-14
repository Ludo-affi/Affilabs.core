"""Quick visual test for LED query side effect.

SIMPLE TEST:
1. Turn off all LEDs
2. Send query command (ia)
3. WATCH: Does LED A turn on?

Run this and OBSERVE the physical LEDs.
"""

import time
import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR

def main():
    print("="*60)
    print("QUICK LED QUERY SIDE EFFECT TEST")
    print("="*60)

    ctrl = PicoP4SPR()
    if not ctrl.open():
        print("❌ Failed to connect")
        return 1

    print(f"✅ Connected: {ctrl.name} v{getattr(ctrl, 'version', '?')}\n")

    # Test sequence
    print("Step 1: Turn off all LEDs")
    print("        Command: lx")
    ctrl.turn_off_channels()
    time.sleep(1.0)
    print("        👀 OBSERVE: All LEDs should be OFF\n")
    input("        Press ENTER to continue...")

    print("\nStep 2: Query LED A intensity (READ-ONLY)")
    print("        Command: ia")
    print("        👀 CRITICAL: Watch LED A - does it turn on?\n")

    # Send query command
    if ctrl._ser:
        with ctrl._lock:
            ctrl._ser.reset_input_buffer()
            ctrl._ser.write(b"ia\n")
            time.sleep(0.05)
            response = ctrl._ser.readline().decode().strip()
            print(f"        Response: {response}")

    time.sleep(2.0)

    print("\n" + "="*60)
    result = input("Did LED A turn ON after query? (y/n): ").strip().lower()
    print("="*60)

    if result == 'y':
        print("\n❌ BUG CONFIRMED:")
        print("   Query command (ia) activates LED")
        print("   Workaround is CORRECT - keep queries disabled")
    else:
        print("\n✅ NO BUG:")
        print("   Query command is read-only")
        print("   Safe to re-enable queries")

    # Cleanup
    ctrl.turn_off_channels()
    ctrl.close()
    print("\n✅ Test complete")

    return 0 if result == 'n' else 1

if __name__ == "__main__":
    sys.exit(main())
