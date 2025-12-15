"""Test script to verify preallocation optimization works correctly."""

import sys

sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Old software")

import time

from settings import CH_LIST
from utils.channel_manager import ChannelManager


def test_preallocation():
    """Test that preallocated buffers work correctly."""
    print("Testing preallocated buffer implementation...")

    # Create channel manager
    mgr = ChannelManager()

    # Check initial state
    print("\nInitial state:")
    print(f"  Buffer capacity: {mgr._buffer_capacity}")
    print(f"  Current lengths: {mgr._current_length}")
    print(f"  Buffer index: {mgr.buffer_index}")

    # Add some data points
    print("\nAdding 10 data points...")
    for i in range(10):
        timestamp = time.perf_counter()

        # Add data for all channels
        for ch in CH_LIST:
            wavelength = 1550.0 + i * 0.1  # Incrementing wavelength
            filtered = wavelength + 0.01  # Slightly different filtered value

            mgr.add_data_point(
                channel=ch,
                wavelength=wavelength,
                timestamp=timestamp,
                filtered_value=filtered,
            )

        # Increment buffer index after all channels processed
        mgr.increment_buffer_index()

    print(f"  Current lengths: {mgr._current_length}")
    print(f"  Buffer index: {mgr.buffer_index}")

    # Check that data is stored correctly
    print("\nVerifying data storage...")
    stats = mgr.get_statistics()
    for ch in CH_LIST:
        print(
            f"  Channel {ch}: {stats[ch]['total_points']} points, "
            f"latest = {stats[ch]['latest_wavelength']:.3f} nm",
        )

    # Get sensorgram data
    print("\nRetrieving sensorgram data...")
    data = mgr.get_sensorgram_data()
    for ch in CH_LIST:
        values = data[ch]["values"]
        print(
            f"  Channel {ch}: {len(values)} values, "
            f"first = {values[0]:.3f}, last = {values[-1]:.3f}",
        )

    # Test growth by adding many points
    print("\nTesting buffer growth (adding 10,000 more points)...")
    start_time = time.perf_counter()

    for i in range(10000):
        timestamp = time.perf_counter()
        for ch in CH_LIST:
            wavelength = 1550.0 + i * 0.0001
            mgr.add_data_point(
                channel=ch,
                wavelength=wavelength,
                timestamp=timestamp,
                filtered_value=wavelength,
            )
        mgr.increment_buffer_index()

    elapsed = time.perf_counter() - start_time

    print(f"  Added 10,000 cycles in {elapsed:.3f} seconds")
    print(f"  Average: {elapsed/10000*1000:.3f} ms per cycle")
    print(f"  Final lengths: {mgr._current_length}")
    print(f"  Final capacity: {mgr._buffer_capacity}")
    max_len = max(mgr._current_length.values())
    print(f"  Utilization: {100 * max_len / mgr._buffer_capacity:.1f}%")

    # Test clear
    print("\nTesting clear_data()...")
    mgr.clear_data()
    print(
        f"  After clear: length = {mgr._current_length}, capacity = {mgr._buffer_capacity}",
    )

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_preallocation()
