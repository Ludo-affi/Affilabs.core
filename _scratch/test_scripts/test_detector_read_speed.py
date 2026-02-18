"""
Test script to measure individual detector read_intensity() timing
Diagnose why each read is taking ~150ms instead of expected 22.4ms
"""

import sys
import time
from pathlib import Path

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent / "affilabs"))

from utils.usb4000_wrapper import USB4000
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)

def test_read_speed():
    """Test individual detector read timing"""

    print("=" * 80)
    print("DETECTOR READ SPEED TEST")
    print("=" * 80)

    # Connect to spectrometer
    print("\n[1/3] Connecting to USB4000...")
    usb = USB4000()
    if not usb.open():
        print("❌ Failed to connect")
        return False
    print(f"✓ Connected: {usb.serial_number}")

    # Test different integration times
    print("\n[2/3] Testing read speed at different integration times...")
    print("-" * 80)

    integration_times = [10.0, 20.0, 22.4, 30.0, 50.0, 100.0]

    for int_time_ms in integration_times:
        usb.set_integration(int_time_ms)

        # Warmup read
        _ = usb.read_intensity()

        # Time 10 reads
        read_times = []
        for i in range(10):
            start = time.perf_counter()
            data = usb.read_intensity()
            end = time.perf_counter()

            if data is not None:
                read_times.append((end - start) * 1000)

        avg_read_time = sum(read_times) / len(read_times)
        overhead = avg_read_time - int_time_ms

        print(f"  Integration: {int_time_ms:5.1f}ms  →  Actual read: {avg_read_time:6.1f}ms  (overhead: {overhead:+5.1f}ms)")

    # Test burst reads (measure inter-read delay)
    print("\n[3/3] Testing burst read timing (8 consecutive reads)...")
    print("-" * 80)

    usb.set_integration(22.4)

    for burst in range(3):
        burst_start = time.perf_counter()

        read_times = []
        for i in range(8):
            read_start = time.perf_counter()
            data = usb.read_intensity()
            read_end = time.perf_counter()
            read_times.append((read_end - read_start) * 1000)

        burst_end = time.perf_counter()
        burst_total = (burst_end - burst_start) * 1000

        avg_read = sum(read_times) / len(read_times)
        min_read = min(read_times)
        max_read = max(read_times)

        print(f"  Burst {burst+1}: Total={burst_total:6.1f}ms  Avg={avg_read:5.1f}ms  Min={min_read:5.1f}ms  Max={max_read:5.1f}ms")
        print(f"           Expected: {8 * 22.4:.1f}ms (8 scans × 22.4ms)")

    print("-" * 80)
    print("\n💡 DIAGNOSIS:")
    print("   Each read_intensity() should take ~integration_time")
    print("   If much longer → driver overhead, buffering, or trigger mode issue")
    print("   For batch mode: 8 reads × actual_time = total delay per channel")

    return True

if __name__ == "__main__":
    try:
        test_read_speed()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
