"""
Test P4PRO turn_on_channel() timing to verify serial read fix
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "affilabs"))

from utils.controller import PicoP4PRO
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)

def test_turn_on_channel_speed():
    """Test turn_on_channel timing"""

    print("=" * 80)
    print("P4PRO TURN_ON_CHANNEL TIMING TEST")
    print("=" * 80)

    # Connect to P4PRO
    print("\n[1/2] Connecting to P4PRO...")
    ctrl = PicoP4PRO()
    if not ctrl.open():
        print("❌ Failed to connect")
        return False
    print("✓ Connected")

    # Set batch intensities
    print("\n[2/2] Testing turn_on_channel timing...")
    intensities = {'a': 200, 'b': 200, 'c': 200, 'd': 200}
    ctrl.set_batch_intensities(intensities)

    channels = ['a', 'b', 'c', 'd']
    times = []

    print("-" * 80)
    for i in range(5):
        cycle_times = []
        for ch in channels:
            start = time.perf_counter()
            ctrl.turn_on_channel(ch)
            end = time.perf_counter()
            elapsed = (end - start) * 1000
            cycle_times.append(elapsed)

        total = sum(cycle_times)
        times.append(total)

        status = "✓" if total < 100 else "❌"
        print(f"  Cycle {i+1}: {total:6.1f}ms {status}  (A:{cycle_times[0]:.1f} B:{cycle_times[1]:.1f} C:{cycle_times[2]:.1f} D:{cycle_times[3]:.1f})")

        # Turn off all LEDs between cycles
        ctrl.turn_off_all_leds()
        time.sleep(0.01)

    print("-" * 80)
    avg_time = sum(times) / len(times)

    print("\nRESULTS:")
    print(f"  Average: {avg_time:.1f}ms")
    print("  Target:  < 100ms (4 channels × ~20ms each)")

    if avg_time < 100:
        print("\n✅ PASS - turn_on_channel is fast!")
        return True
    else:
        print("\n❌ FAIL - turn_on_channel still slow (serial read timeout?)")
        return False

if __name__ == "__main__":
    try:
        success = test_turn_on_channel_speed()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
