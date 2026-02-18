"""Test hardware averaging timing fits within LED cycle budget.

LED cycle structure (from settings.py):
- LED OFF: 55ms (between channels)
- LED ON: 225-240ms per channel
  ├─ Detector wait: 45ms (LED stabilization)
  ├─ Detector window: 170ms (available for acquisition)
  └─ Safety buffer: 10ms

Total cycle time: ~250ms per channel (4 channels = 1000ms/cycle)

Hardware averaging timing:
- Formula: (num_scans x integration_time) + USB_OVERHEAD (25ms)
- Must fit within 170ms detector window
"""

import time
import sys
import numpy as np

sys.path.insert(0, r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\test\ezControl-AI")

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
import settings as root_settings

# LED cycle timing (from settings.py)
LED_ON_TIME_MS = getattr(root_settings, 'LED_ON_TIME_MS', 225.0)
DETECTOR_WAIT_MS = getattr(root_settings, 'DETECTOR_WAIT_MS', 45.0)
SAFETY_BUFFER_MS = getattr(root_settings, 'SAFETY_BUFFER_MS', 10.0)

# Calculate detector window
DETECTOR_ON_TIME_MS = LED_ON_TIME_MS - DETECTOR_WAIT_MS
DETECTOR_WINDOW_MS = DETECTOR_ON_TIME_MS - SAFETY_BUFFER_MS

USB_OVERHEAD_MS = 25.0
MAX_HARDWARE_AVERAGING = 15


def measure_acquisition_time(detector, num_scans, num_iterations=10):
    """Measure actual acquisition time with hardware averaging."""
    times = []
    
    # Set hardware averaging
    detector.set_averaging(num_scans)
    time.sleep(0.05)  # Let setting stabilize
    
    # Warm up
    detector.read_intensity()
    
    # Measure
    for _ in range(num_iterations):
        start = time.perf_counter()
        spectrum = detector.read_intensity()
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    
    # Reset
    detector.set_averaging(1)
    
    return np.array(times)


def main():
    print("=" * 80)
    print("PhasePhotonics Hardware Averaging - LED Cycle Timing Test")
    print("=" * 80)
    
    # Connect to detector
    print("\n1. Connecting to detector...")
    detector = PhasePhotonics()
    if not detector.open():
        print("FAIL: Failed to open detector")
        return
    print(f"OK Connected: {detector.serial_number}")

    # Get integration time from device config
    integration_time_ms = detector._integration_time * 1000 if detector._integration_time else 10.0
    print(f"OK Integration time: {integration_time_ms:.2f}ms")
    
    # Display LED cycle timing
    print(f"\n2. LED Cycle Timing Budget (from settings.py):")
    print(f"   LED ON time:       {LED_ON_TIME_MS:.1f}ms")
    print(f"   Detector wait:     {DETECTOR_WAIT_MS:.1f}ms (LED stabilization)")
    print(f"   Detector ON time:  {DETECTOR_ON_TIME_MS:.1f}ms")
    print(f"   Safety buffer:     {SAFETY_BUFFER_MS:.1f}ms")
    print(f"   DETECTOR WINDOW:   {DETECTOR_WINDOW_MS:.1f}ms <- AVAILABLE FOR ACQUISITION")
    
    # Calculate optimal scans
    print(f"\n3. Hardware Averaging Calculation:")
    print(f"   Formula: (num_scans x integration_time) + USB_overhead <= detector_window")
    
    available_time = DETECTOR_WINDOW_MS - USB_OVERHEAD_MS
    calculated_scans = int(available_time / integration_time_ms)
    optimal_scans = min(calculated_scans, MAX_HARDWARE_AVERAGING)
    
    print(f"   Available time:    {DETECTOR_WINDOW_MS:.1f}ms - {USB_OVERHEAD_MS:.0f}ms = {available_time:.1f}ms")
    print(f"   Scans per window:  {available_time:.1f}ms / {integration_time_ms:.2f}ms = {calculated_scans} scans")
    print(f"   Hardware cap:      {MAX_HARDWARE_AVERAGING} scans")
    print(f"   OPTIMAL SCANS:     {optimal_scans} scans")
    
    predicted_time = (optimal_scans * integration_time_ms) + USB_OVERHEAD_MS
    print(f"   Predicted time:    ({optimal_scans} x {integration_time_ms:.2f}ms) + {USB_OVERHEAD_MS:.0f}ms = {predicted_time:.1f}ms")
    
    # Test different scan counts
    test_scans = [1, 5, 9, optimal_scans]
    test_scans = sorted(list(set(test_scans)))  # Remove duplicates
    
    print(f"\n4. Actual Timing Measurements:")
    print(f"   {'Scans':<8} {'Predicted':<12} {'Actual':<12} {'Fits?':<8} {'SNR Gain':<10}")
    print(f"   {'-'*60}")
    
    results = []
    for num_scans in test_scans:
        # Predicted time
        predicted = (num_scans * integration_time_ms) + USB_OVERHEAD_MS
        
        # Measure actual time
        times = measure_acquisition_time(detector, num_scans, num_iterations=10)
        actual = np.mean(times)
        std = np.std(times)
        
        # Check if fits in window
        fits = actual <= DETECTOR_WINDOW_MS
        fits_str = "OK" if fits else "FAIL"
        
        # SNR improvement
        snr_gain = np.sqrt(num_scans)
        
        print(f"   {num_scans:<8} {predicted:>8.1f}ms    {actual:>8.1f}±{std:.1f}ms   {fits_str:<8} {snr_gain:.2f}x")
        
        results.append({
            'scans': num_scans,
            'predicted': predicted,
            'actual': actual,
            'std': std,
            'fits': fits,
            'snr_gain': snr_gain
        })
    
    # Summary
    print(f"\n5. Verdict:")
    print(f"   {'-'*60}")
    
    optimal_result = [r for r in results if r['scans'] == optimal_scans][0]
    
    if optimal_result['fits']:
        margin = DETECTOR_WINDOW_MS - optimal_result['actual']
        print(f"   PASS: {optimal_scans}-scan averaging FITS in detector window")
        print(f"      Actual time:   {optimal_result['actual']:.1f}ms")
        print(f"      Window budget: {DETECTOR_WINDOW_MS:.1f}ms")
        print(f"      Margin:        {margin:.1f}ms ({margin/DETECTOR_WINDOW_MS*100:.1f}% headroom)")
        print(f"      SNR gain:      {optimal_result['snr_gain']:.2f}x")
    else:
        overage = optimal_result['actual'] - DETECTOR_WINDOW_MS
        print(f"   FAIL: {optimal_scans}-scan averaging EXCEEDS detector window")
        print(f"      Actual time:   {optimal_result['actual']:.1f}ms")
        print(f"      Window budget: {DETECTOR_WINDOW_MS:.1f}ms")
        print(f"      Overage:       {overage:.1f}ms (too slow!)")
    
    # Compare to software averaging
    print(f"\n6. Hardware vs Software Averaging (at {optimal_scans} scans):")
    
    # Software averaging estimate (from earlier tests: ~44ms per scan)
    software_time_per_scan = 44.0  # ms (measured from test_hardware_averaging.py)
    software_total = optimal_scans * software_time_per_scan
    
    hardware_total = optimal_result['actual']
    speedup = software_total / hardware_total
    time_saved = software_total - hardware_total
    
    print(f"   Software averaging: {optimal_scans} x {software_time_per_scan:.0f}ms = {software_total:.0f}ms")
    print(f"   Hardware averaging: ({optimal_scans} x {integration_time_ms:.1f}ms) + {USB_OVERHEAD_MS:.0f}ms = {hardware_total:.1f}ms")
    print(f"   Speedup:            {speedup:.2f}x faster")
    print(f"   Time saved:         {time_saved:.0f}ms per channel")
    print(f"   4-channel savings:  {time_saved * 4:.0f}ms per cycle")
    
    # Full cycle timing
    print(f"\n7. Full 4-Channel Cycle Timing:")
    led_off_per_channel = 55.0  # ms
    time_per_channel = LED_ON_TIME_MS + led_off_per_channel
    total_cycle_time = time_per_channel * 4
    
    print(f"   Per channel: {LED_ON_TIME_MS:.0f}ms LED ON + {led_off_per_channel:.0f}ms LED OFF = {time_per_channel:.0f}ms")
    print(f"   4 channels:  {time_per_channel:.0f}ms x 4 = {total_cycle_time:.0f}ms/cycle")
    print(f"   Throughput:  {1000/total_cycle_time:.2f} cycles/second")
    
    detector.close()
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
