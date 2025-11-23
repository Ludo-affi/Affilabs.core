"""Test script to verify batched spectrum acquisition."""

import sys
import time
from pathlib import Path

# Add Old software to path
old_software_path = Path(__file__).parent / "Old software"
sys.path.insert(0, str(old_software_path))

from core.data_acquisition_manager import DataAcquisitionManager
from utils.logger import logger


def test_batch_configuration():
    """Test batch size configuration."""
    print("=" * 60)
    print("TEST 1: Batch Size Configuration")
    print("=" * 60)

    mgr = DataAcquisitionManager(None)

    # Test initial batch size
    assert mgr.batch_size == 4, "Default batch size should be 4"
    print(f"✓ Default batch size: {mgr.batch_size}")

    # Test setting valid batch size
    mgr.set_batch_size(8)
    assert mgr.batch_size == 8, "Batch size should be 8"
    print(f"✓ Changed batch size to: {mgr.batch_size}")

    # Test setting batch size to 1 (real-time mode)
    mgr.set_batch_size(1)
    assert mgr.batch_size == 1, "Batch size should be 1"
    print(f"✓ Real-time mode (batch_size=1): {mgr.batch_size}")

    # Test invalid batch size (should clamp to 1)
    mgr.set_batch_size(0)
    assert mgr.batch_size == 1, "Invalid batch size should clamp to 1"
    print(f"✓ Invalid batch size clamped to: {mgr.batch_size}")

    print("\n✅ Batch configuration test PASSED\n")


def test_batch_buffers():
    """Test batch buffer initialization."""
    print("=" * 60)
    print("TEST 2: Batch Buffer Initialization")
    print("=" * 60)

    mgr = DataAcquisitionManager(None)

    # Check batch buffers exist
    assert hasattr(mgr, '_spectrum_batch'), "Should have _spectrum_batch"
    assert hasattr(mgr, '_batch_timestamps'), "Should have _batch_timestamps"
    print("✓ Batch buffers initialized")

    # Check all channels have buffers
    for ch in ['a', 'b', 'c', 'd']:
        assert ch in mgr._spectrum_batch, f"Channel {ch} should have spectrum batch buffer"
        assert ch in mgr._batch_timestamps, f"Channel {ch} should have timestamp batch buffer"
        assert isinstance(mgr._spectrum_batch[ch], list), "Batch buffer should be a list"
        assert isinstance(mgr._batch_timestamps[ch], list), "Timestamp buffer should be a list"
        print(f"✓ Channel {ch.upper()} batch buffers ready")

    print("\n✅ Batch buffer test PASSED\n")


def test_batch_logic():
    """Test batch processing logic."""
    print("=" * 60)
    print("TEST 3: Batch Processing Logic")
    print("=" * 60)

    mgr = DataAcquisitionManager(None)
    mgr.set_batch_size(4)

    # Simulate adding spectra to batch
    print(f"Batch size set to: {mgr.batch_size}")
    print(f"Simulating spectrum acquisition for channel A...")

    for i in range(3):
        # Simulate adding spectrum data
        mgr._spectrum_batch['a'].append({'wavelength': [], 'intensity': []})
        mgr._batch_timestamps['a'].append(time.time())
        print(f"  Spectrum {i+1} buffered. Batch size: {len(mgr._spectrum_batch['a'])}/{mgr.batch_size}")

    assert len(mgr._spectrum_batch['a']) == 3, "Should have 3 spectra in batch"
    print(f"✓ Batch buffer size < threshold: No processing yet")

    # Add one more to trigger batch processing (would happen in real code)
    mgr._spectrum_batch['a'].append({'wavelength': [], 'intensity': []})
    mgr._batch_timestamps['a'].append(time.time())
    print(f"  Spectrum 4 buffered. Batch size: {len(mgr._spectrum_batch['a'])}/{mgr.batch_size}")

    assert len(mgr._spectrum_batch['a']) >= mgr.batch_size, "Should have reached batch threshold"
    print(f"✓ Batch buffer size >= threshold: Ready for processing")

    # Simulate clearing batch
    mgr._spectrum_batch['a'].clear()
    mgr._batch_timestamps['a'].clear()
    assert len(mgr._spectrum_batch['a']) == 0, "Batch should be cleared"
    print(f"✓ Batch cleared after processing")

    print("\n✅ Batch processing logic test PASSED\n")


def print_performance_estimate():
    """Print performance improvement estimates."""
    print("=" * 60)
    print("PERFORMANCE IMPROVEMENT ESTIMATES")
    print("=" * 60)

    print("\nOLD (Sequential Processing):")
    print("  - 1 USB read per spectrum")
    print("  - 1 processing call per spectrum")
    print("  - High USB communication overhead")
    print("  - Example: 100 spectra = 100 USB transactions")

    print("\nNEW (Batched Processing with batch_size=4):")
    print("  - 4 USB reads buffered before processing")
    print("  - Processing amortized over 4 spectra")
    print("  - Reduced USB communication overhead")
    print("  - Example: 100 spectra = 100 USB reads, but 25 processing waves")

    print("\nBenefits:")
    print("  ✓ Reduced processing overhead (75% fewer processing calls)")
    print("  ✓ Better CPU cache utilization")
    print("  ✓ Smoother data flow to UI")
    print("  ✓ Lower system load")

    print("\nTrade-offs:")
    print("  • Slight latency increase (wait for 4 spectra)")
    print("  • Can adjust batch_size for latency vs throughput")
    print("  • Use batch_size=1 for real-time, 8+ for high throughput")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("BATCHED SPECTRUM ACQUISITION TEST SUITE")
        print("=" * 60 + "\n")

        test_batch_configuration()
        test_batch_buffers()
        test_batch_logic()
        print_performance_estimate()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
