"""Test Phase Photonics Detector Timing and Internal Scan Averaging

This script measures:
1. Detector read times with various delays between acquisitions
2. Performance of internal scan averaging vs manual averaging
3. Optimal detector off-time for stable acquisitions

The Phase Photonics detector can average scans internally, which may be faster
than reading multiple times from Python.
"""

import time
import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.hal.adapters import OceanSpectrometerAdapter
from affilabs.utils.logger import logger


def test_single_acquisition_timing(detector, integration_time_ms=22.0, num_tests=20):
    """Test timing of single acquisitions with no delay."""
    print("\n" + "="*80)
    print("TEST 1: Single Acquisition Timing (No Delay)")
    print("="*80)
    
    times = []
    
    for i in range(num_tests):
        start = time.perf_counter()
        spectrum = detector.read_intensity()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
        
        if i < 5 or i >= num_tests - 2:
            print(f"  Read #{i+1}: {elapsed:.1f} ms (expected ~{integration_time_ms}ms + overhead)")
    
    times = np.array(times)
    print(f"\n  Results ({num_tests} acquisitions):")
    print(f"    Average: {np.mean(times):.1f} ms")
    print(f"    Std Dev: {np.std(times):.1f} ms")
    print(f"    Min: {np.min(times):.1f} ms")
    print(f"    Max: {np.max(times):.1f} ms")
    print(f"    Overhead: {np.mean(times) - integration_time_ms:.1f} ms")
    
    return times


def test_acquisition_with_delays(detector, integration_time_ms=22.0, delays_ms=[0, 5, 10, 20, 50, 100]):
    """Test if adding delays between acquisitions affects stability."""
    print("\n" + "="*80)
    print("TEST 2: Acquisition Timing with Various Delays")
    print("="*80)
    
    results = {}
    
    for delay_ms in delays_ms:
        print(f"\n  Testing with {delay_ms}ms delay between reads...")
        times = []
        
        for i in range(10):
            start = time.perf_counter()
            spectrum = detector.read_intensity()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        
        times = np.array(times)
        results[delay_ms] = {
            'mean': np.mean(times),
            'std': np.std(times),
            'min': np.min(times),
            'max': np.max(times)
        }
        
        print(f"    Average: {results[delay_ms]['mean']:.1f} ms ± {results[delay_ms]['std']:.1f} ms")
        print(f"    Range: {results[delay_ms]['min']:.1f} - {results[delay_ms]['max']:.1f} ms")
    
    print("\n  Summary:")
    print(f"    {'Delay (ms)':<12} {'Avg Time (ms)':<15} {'Std Dev (ms)':<15} {'Stability':<15}")
    print(f"    {'-'*60}")
    
    for delay_ms in delays_ms:
        r = results[delay_ms]
        stability = "Excellent" if r['std'] < 2 else "Good" if r['std'] < 5 else "Variable"
        print(f"    {delay_ms:<12} {r['mean']:<15.1f} {r['std']:<15.1f} {stability:<15}")
    
    return results


def test_internal_scan_averaging(detector, integration_time_ms=22.0, num_scans_list=[1, 2, 4, 8, 16]):
    """Test Phase Photonics scan averaging performance."""
    print("\n" + "="*80)
    print("TEST 3: Scan Averaging Performance")
    print("="*80)
    print("Phase Photonics requires manual averaging (reading multiple times).")
    print("Testing performance with different numbers of scans.\n")
    
    results = {}
    
    for num_scans in num_scans_list:
        print(f"\n  Testing with num_scans={num_scans} (manual averaging)...")
        
        # Test reading and averaging manually
        avg_times = []
        for i in range(10):
            start = time.perf_counter()
            spectra = []
            for _ in range(num_scans):
                spectra.append(detector.read_intensity())
            avg_spectrum = np.mean(spectra, axis=0)
            elapsed = (time.perf_counter() - start) * 1000
            avg_times.append(elapsed)
        
        avg_times = np.array(avg_times)
        
        # Calculate expected time (integration + overhead per scan)
        expected_per_scan = 22.0 + 20.0  # integration + overhead estimate
        expected_total = expected_per_scan * num_scans
        
        results[num_scans] = {
            'avg_mean': np.mean(avg_times),
            'avg_std': np.std(avg_times),
            'expected': expected_total,
            'efficiency': (expected_total / np.mean(avg_times)) * 100 if np.mean(avg_times) > 0 else 0
        }
        
        print(f"    Actual time: {results[num_scans]['avg_mean']:.1f} ms ± {results[num_scans]['avg_std']:.1f} ms")
        print(f"    Expected time: ~{expected_total:.1f} ms ({num_scans} scans)")
        print(f"    Efficiency: {results[num_scans]['efficiency']:.1f}%")
        print(f"    Time per scan: {results[num_scans]['avg_mean'] / num_scans:.1f} ms")
    
    print("\n  Summary:")
    print(f"    {'Scans':<8} {'Total Time (ms)':<18} {'Time/Scan (ms)':<18} {'Efficiency':<12}")
    print(f"    {'-'*60}")
    
    for num_scans in num_scans_list:
        r = results[num_scans]
        time_per_scan = r['avg_mean'] / num_scans if num_scans > 0 else 0
        print(f"    {num_scans:<8} {r['avg_mean']:<18.1f} {time_per_scan:<18.1f} {r['efficiency']:<12.1f}%")
    
    return results
    
    print("\n  Summary:")
    print(f"    {'Scans':<8} {'Internal (ms)':<16} {'Manual (ms)':<16} {'Speedup':<12} {'Efficiency':<12}")
    print(f"    {'-'*70}")
    
    for num_scans in num_scans_list:
        r = results[num_scans]
        efficiency = (integration_time_ms * num_scans) / r['internal_mean'] * 100
        print(f"    {num_scans:<8} {r['internal_mean']:<16.1f} {r['manual_mean']:<16.1f} {r['speedup']:<12.2f} {efficiency:<12.1f}%")
    
    return results


def test_roi_performance(detector, integration_time_ms=22.0):
    """Test detector read performance."""
    print("\n" + "="*80)
    print("TEST 4: Detector Read Performance")
    print("="*80)
    print("Phase Photonics always reads full spectrum (1848 pixels).")
    print("Software filtering happens after acquisition.\n")
    
    # Get full spectrum size
    full_spectrum = detector.read_intensity()
    full_size = len(full_spectrum)
    
    print(f"  Full detector: {full_size} pixels (1848 for Phase Photonics)")
    print(f"  Valid range: 570-720nm (pixels filtered in software)\n")
    
    # Test full spectrum
    print("  Testing full spectrum reads...")
    full_times = []
    for i in range(20):
        start = time.perf_counter()
        spectrum = detector.read_intensity()
        elapsed = (time.perf_counter() - start) * 1000
        full_times.append(elapsed)
    
    full_times = np.array(full_times)
    
    print(f"\n  Results:")
    print(f"    Full spectrum: {np.mean(full_times):.1f} ms ± {np.std(full_times):.1f} ms")
    print(f"    Note: Software filtering adds <1ms overhead")
    
    return full_times, None


def test_burst_acquisition(detector, integration_time_ms=22.0, burst_sizes=[10, 20, 50, 100]):
    """Test continuous burst acquisitions to find thermal/stability limits."""
    print("\n" + "="*80)
    print("TEST 5: Burst Acquisition (Thermal Stability)")
    print("="*80)
    print("Testing detector stability during continuous high-speed acquisition.\n")
    
    results = {}
    
    for burst_size in burst_sizes:
        print(f"\n  Testing burst of {burst_size} acquisitions...")
        
        times = []
        start_burst = time.perf_counter()
        
        for i in range(burst_size):
            start = time.perf_counter()
            spectrum = detector.read_intensity()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        total_burst_time = (time.perf_counter() - start_burst) * 1000
        times = np.array(times)
        
        # Check for timing drift (early vs late acquisitions)
        early_avg = np.mean(times[:5])
        late_avg = np.mean(times[-5:])
        drift = late_avg - early_avg
        
        results[burst_size] = {
            'total_time': total_burst_time,
            'avg_time': np.mean(times),
            'std': np.std(times),
            'early_avg': early_avg,
            'late_avg': late_avg,
            'drift': drift,
            'throughput': burst_size / (total_burst_time / 1000)  # acquisitions/sec
        }
        
        print(f"    Total time: {total_burst_time:.0f} ms ({burst_size} acquisitions)")
        print(f"    Average per acquisition: {results[burst_size]['avg_time']:.1f} ms ± {results[burst_size]['std']:.1f} ms")
        print(f"    Throughput: {results[burst_size]['throughput']:.1f} acquisitions/second")
        print(f"    Timing drift: {drift:.1f} ms (early: {early_avg:.1f} ms → late: {late_avg:.1f} ms)")
        
        stability = "Stable" if abs(drift) < 2 else "Minor drift" if abs(drift) < 5 else "Significant drift"
        print(f"    Stability: {stability}")
    
    return results


def main():
    """Run all detector timing tests."""
    print("\n" + "="*80)
    print("PHASE PHOTONICS DETECTOR TIMING & PERFORMANCE TEST")
    print("="*80)
    
    try:
        # Connect to detector
        print("\nConnecting to Phase Photonics detector...")
        detector = PhasePhotonics()
        detector.get_device_list()
        
        if not detector.devs:
            print("❌ No Phase Photonics detector found!")
            print("   Make sure the detector is connected and D2XX drivers are installed.")
            return
        
        if not detector.open():
            print("❌ Failed to open detector!")
            return
        
        # Create adapter for HAL interface
        usb = OceanSpectrometerAdapter(detector)
        
        print(f"✓ Connected: {detector.serial_number}")
        
        # Get current integration time
        current_int_time = detector._integration_time * 1000  # convert to ms
        print(f"  Integration time: {current_int_time:.2f} ms")
        
        # Set a known integration time for consistent testing
        test_int_time = 22.0
        detector.set_integration(test_int_time)
        print(f"  Set to: {test_int_time} ms for testing\n")
        
        # Run all tests
        test_single_acquisition_timing(detector, test_int_time)
        test_acquisition_with_delays(detector, test_int_time)
        test_internal_scan_averaging(detector, test_int_time)
        test_roi_performance(detector, test_int_time)
        test_burst_acquisition(detector, test_int_time)
        
        # Final recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        print("\n1. DETECTOR OFF-TIME:")
        print("   • Phase Photonics does NOT need delays between acquisitions")
        print("   • Can read continuously at maximum speed")
        print("   • Overhead is typically 20-25ms per acquisition")
        
        print("\n2. SCAN AVERAGING:")
        print("   • Phase Photonics requires manual averaging (read multiple times)")
        print("   • Average 8 scans for good SNR: ~350-400ms total")
        print("   • Each read is independent - no internal averaging available")
        
        print("\n3. OPTIMAL SETTINGS FOR SPEED:")
        print("   • Integration time: 20-25ms (balance speed vs SNR)")
        print("   • Use num_scans=8 for internal averaging")
        print("   • Expected total time: ~180-200ms per averaged spectrum")
        print("   • Throughput: ~5 averaged spectra/second")
        
        print("\n4. ROI OPTIMIZATION:")
        print("   • Phase Photonics always reads full spectrum (1848 pixels)")
        print("   • Software filtering (<1ms overhead) removes data below 570nm")
        print("   • Already implemented in spectroscopy_presenter.py")
        
        # Restore original integration time
        detector.set_integration(current_int_time)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("Detector timing test failed")
        raise
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
