"""Test DataBufferManager integration with TimeSeriesBuffer."""

import time

import numpy as np

from settings import CH_LIST
from utils.data_buffer_manager import DataBufferManager


def test_buffer_manager_basic():
    """Test basic buffer manager operations."""
    print("=" * 60)
    print("Testing DataBufferManager with TimeSeriesBuffer backend")
    print("=" * 60)

    # Initialize
    buffer_mgr = DataBufferManager(channels=CH_LIST)
    print(f"\n✓ Initialized DataBufferManager with channels: {CH_LIST}")

    # Add some data points
    print("\n📊 Adding 1000 data points to each channel...")
    start_time = time.time()

    for i in range(1000):
        timestamp = i * 0.1  # 100ms intervals
        for ch in CH_LIST:
            value = 632.8 + np.sin(i * 0.01) * 0.5  # Simulated SPR wavelength

            # In actual usage, add_sensorgram_point is called once per acquisition
            # and includes all values (lambda, filtered, buffered) in the TimeSeriesBuffer.append()
            buffer_mgr.add_sensorgram_point(ch, value, timestamp)

    elapsed = time.time() - start_time
    print(f"✓ Added 1000 points × {len(CH_LIST)} channels in {elapsed:.3f}s")
    print(f"  ({1000 * len(CH_LIST) / elapsed:.0f} points/sec)")

    # Verify data
    print("\n📈 Verifying data integrity...")
    for ch in CH_LIST:
        count = len(buffer_mgr.lambda_values[ch])
        print(f"  Channel {ch}: {count} points")
        assert count == 1000, f"Expected 1000 points, got {count}"

    print("✓ All channels have correct data count")

    # Test memory usage
    memory = buffer_mgr.get_memory_usage()
    print("\n💾 Memory usage:")
    for ch in CH_LIST:
        print(f"  Channel {ch}: {memory[ch] / 1024:.1f} KB")
    print(f"  Total: {memory['total'] / 1024:.1f} KB")

    # Test buffer info
    info = buffer_mgr.get_buffer_info()
    print("\n📊 Buffer info:")
    print(f"  Max buffer size: {info['max_buffer_size']}")
    print(f"  Buffer trim size: {info['buffer_trim_size']}")

    # Test time shift
    print("\n⏱️ Testing time shift...")
    orig_time = buffer_mgr.lambda_times["a"][0]
    buffer_mgr.shift_time_reference(10.0)
    new_time = buffer_mgr.lambda_times["a"][0]
    print(f"  Original first timestamp: {orig_time:.3f}s")
    print(f"  After shift (-10.0s): {new_time:.3f}s")
    assert abs(new_time - (orig_time - 10.0)) < 0.001, "Time shift failed"
    print("✓ Time shift working correctly")

    # Test clear
    print("\n🗑️ Testing buffer clear...")
    buffer_mgr.clear_channel_buffers("a")
    count_a = len(buffer_mgr.lambda_values["a"])
    count_b = len(buffer_mgr.lambda_values["b"])
    print(f"  Channel a after clear: {count_a} points")
    print(f"  Channel b (not cleared): {count_b} points")
    assert count_a == 0, "Clear failed"
    assert count_b == 1000, "Clear affected wrong channel"
    print("✓ Selective clear working correctly")

    print(f"\n{'=' * 60}")
    print("✅ All tests passed!")
    print(f"{'=' * 60}")


def test_performance_comparison():
    """Compare np.append vs TimeSeriesBuffer performance."""
    print("\n" + "=" * 60)
    print("Performance Comparison: np.append vs TimeSeriesBuffer")
    print("=" * 60)

    n_points = 5000

    # Test 1: Legacy np.append
    print(f"\n🐌 Testing legacy np.append() with {n_points} points...")
    data = np.array([])
    times = np.array([])

    start = time.time()
    for i in range(n_points):
        data = np.append(data, 632.8 + i * 0.001)
        times = np.append(times, i * 0.1)
    elapsed_legacy = time.time() - start

    print(
        f"   Time: {elapsed_legacy:.3f}s ({n_points / elapsed_legacy:.0f} points/sec)",
    )

    # Test 2: TimeSeriesBuffer
    print(f"\n🚀 Testing TimeSeriesBuffer with {n_points} points...")
    buffer_mgr = DataBufferManager(channels=["a"])

    start = time.time()
    for i in range(n_points):
        buffer_mgr.add_sensorgram_point("a", 632.8 + i * 0.001, i * 0.1)
    elapsed_optimized = time.time() - start

    print(
        f"   Time: {elapsed_optimized:.3f}s ({n_points / elapsed_optimized:.0f} points/sec)",
    )

    # Calculate speedup
    speedup = elapsed_legacy / elapsed_optimized
    print(f"\n⚡ Performance improvement: {speedup:.1f}×")

    if speedup > 5:
        print(f"   🎉 Excellent! {speedup:.1f}× faster than legacy approach")
    elif speedup > 2:
        print(f"   ✓ Good! {speedup:.1f}× faster than legacy approach")
    else:
        print(f"   ⚠️ Modest improvement: {speedup:.1f}×")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    try:
        test_buffer_manager_basic()
        test_performance_comparison()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
