"""Test Phase Photonics Hardware Averaging Feature

Tests the internal scan averaging capability of the Phase Photonics detector.
This should achieve ~44% faster acquisition compared to manual averaging.

Expected results:
- Manual averaging (8 scans): ~352ms (8 × 44ms)
- Hardware averaging (8 scans): ~198ms (8 × 22ms + 22ms transfer)
"""

import time
import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger


def test_hardware_averaging():
    """Test Phase Photonics internal scan averaging."""
    print("\n" + "="*80)
    print("PHASE PHOTONICS HARDWARE AVERAGING TEST")
    print("="*80)
    
    try:
        # Connect to detector
        print("\nConnecting to Phase Photonics detector...")
        detector = PhasePhotonics()
        detector.get_device_list()
        
        if not detector.devs:
            print("❌ No Phase Photonics detector found!")
            return
        
        if not detector.open():
            print("❌ Failed to open detector!")
            return
        
        print(f"✓ Connected: {detector.serial_number}\n")
        
        # Set integration time
        int_time = 22.0  # ms
        detector.set_integration(int_time)
        print(f"Integration time: {int_time}ms\n")
        
        # Test 1: Manual averaging (current method)
        print("="*80)
        print("TEST 1: Manual Averaging (8 scans read separately)")
        print("="*80)
        
        manual_times = []
        for i in range(10):
            start = time.perf_counter()
            spectra = []
            for _ in range(8):
                spectra.append(detector.read_intensity())
            avg_spectrum = np.mean(spectra, axis=0)
            elapsed = (time.perf_counter() - start) * 1000
            manual_times.append(elapsed)
        
        manual_times = np.array(manual_times)
        manual_avg = np.mean(manual_times)
        
        print(f"  Average time: {manual_avg:.1f} ms ± {np.std(manual_times):.1f} ms")
        print(f"  Expected: ~352ms (8 scans × 44ms)")
        print(f"  Time per scan: {manual_avg / 8:.1f} ms\n")
        
        # Test 2: Hardware averaging (new method)
        print("="*80)
        print("TEST 2: Hardware Averaging (8 scans averaged internally)")
        print("="*80)
        
        # Enable hardware averaging
        if not detector.set_averaging(8):
            print("❌ Failed to set hardware averaging!")
            return
        
        # Wait a moment for settings to take effect
        time.sleep(0.1)
        
        hardware_times = []
        for i in range(10):
            start = time.perf_counter()
            avg_spectrum = detector.read_intensity()  # Detector returns averaged result
            elapsed = (time.perf_counter() - start) * 1000
            hardware_times.append(elapsed)
            
            if i < 3:
                print(f"  Read #{i+1}: {elapsed:.1f} ms")
        
        hardware_times = np.array(hardware_times)
        hardware_avg = np.mean(hardware_times)
        
        print(f"\n  Average time: {hardware_avg:.1f} ms ± {np.std(hardware_times):.1f} ms")
        print(f"  Expected: ~198ms (8 × 22ms integration + 22ms transfer)")
        print(f"  Equivalent time per scan: {hardware_avg / 8:.1f} ms\n")
        
        # Compare results
        print("="*80)
        print("COMPARISON")
        print("="*80)
        
        speedup = manual_avg / hardware_avg
        time_saved = manual_avg - hardware_avg
        percent_faster = ((manual_avg - hardware_avg) / manual_avg) * 100
        
        print(f"  Manual averaging:   {manual_avg:.1f} ms")
        print(f"  Hardware averaging: {hardware_avg:.1f} ms")
        print(f"  Speedup: {speedup:.2f}x faster")
        print(f"  Time saved: {time_saved:.1f} ms ({percent_faster:.1f}% faster)\n")
        
        # Verify data quality
        print("="*80)
        print("DATA QUALITY VERIFICATION")
        print("="*80)
        
        # Reset to no averaging for single scan
        detector.set_averaging(1)
        time.sleep(0.1)
        
        # Get manual averaged spectrum
        manual_spectra = []
        for _ in range(8):
            manual_spectra.append(detector.read_intensity())
        manual_result = np.mean(manual_spectra, axis=0)
        
        # Get hardware averaged spectrum
        detector.set_averaging(8)
        time.sleep(0.1)
        hardware_result = detector.read_intensity()
        
        # Compare
        diff = np.abs(manual_result - hardware_result)
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        
        print(f"  Manual avg mean: {np.mean(manual_result):.1f} counts")
        print(f"  Hardware avg mean: {np.mean(hardware_result):.1f} counts")
        print(f"  Max difference: {max_diff:.1f} counts")
        print(f"  Mean difference: {mean_diff:.1f} counts")
        
        if mean_diff < 10:
            print(f"  ✓ Results match (difference < 10 counts)\n")
        else:
            print(f"  ⚠ Large difference - verify averaging is working correctly\n")
        
        # Final recommendations
        print("="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        if hardware_avg < manual_avg * 0.7:
            print("\n  ✅ HARDWARE AVERAGING IS WORKING!")
            print(f"  • Use detector.set_averaging(8) for {speedup:.2f}x faster acquisition")
            print(f"  • Total time for 8 scans: ~{hardware_avg:.0f}ms instead of ~{manual_avg:.0f}ms")
            print(f"  • Throughput improvement: {percent_faster:.0f}% faster")
            print(f"  • Expected throughput: ~{1000/hardware_avg:.1f} averaged spectra/second")
        else:
            print("\n  ⚠ Hardware averaging may not be enabled properly")
            print(f"  • Expected ~198ms, got {hardware_avg:.1f}ms")
            print("  • Check DLL version and detector firmware")
        
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("Hardware averaging test failed")
        raise


if __name__ == "__main__":
    test_hardware_averaging()
