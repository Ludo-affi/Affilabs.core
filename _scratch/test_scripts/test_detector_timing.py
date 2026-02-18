"""Detector Acquisition Timing Test - Shows full LED cycle timing breakdown"""

import time
import sys
import numpy as np

sys.path.insert(0, r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\test\ezControl-AI")

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
import settings as root_settings

# Get timing parameters from settings
LED_ON_TIME_MS = root_settings.LED_ON_TIME_MS
DETECTOR_WAIT_MS = root_settings.DETECTOR_WAIT_MS
SAFETY_BUFFER_MS = root_settings.SAFETY_BUFFER_MS

# Calculate derived timing
DETECTOR_ON_TIME_MS = LED_ON_TIME_MS - DETECTOR_WAIT_MS
DETECTOR_WINDOW_MS = DETECTOR_ON_TIME_MS - SAFETY_BUFFER_MS

# Hardware averaging parameters
USB_OVERHEAD_MS = 8.0
MAX_HARDWARE_AVERAGING = 15


def visualize_timing():
    """Show visual breakdown of LED cycle timing."""
    print("=" * 80)
    print("LED CYCLE TIMING BREAKDOWN")
    print("=" * 80)
    print()
    print("Single Channel Cycle:")
    print()
    print(f"  0ms                                           {LED_ON_TIME_MS}ms")
    print("  |---------------------------------------------|")
    print("  |           LED ON                            |")
    print("  |---------------------------------------------|")
    print("  |        |                            |       |")
    print(f"  0      {DETECTOR_WAIT_MS}ms                        {DETECTOR_ON_TIME_MS}ms    {LED_ON_TIME_MS}ms")
    print("         |                            |")
    print("         |<-- DETECTOR ON TIME ------>|")
    print("         |                      |     |")
    print(f"         |<- DETECTOR WINDOW ->|     |")
    print(f"         |   ({DETECTOR_WINDOW_MS}ms available) |  {SAFETY_BUFFER_MS}ms|")
    print("         |                      |  buffer")
    print()
    print("Timeline breakdown:")
    print(f"  [0-{DETECTOR_WAIT_MS}ms]:       LED stabilization (DETECTOR_WAIT)")
    print(f"  [{DETECTOR_WAIT_MS}-{DETECTOR_ON_TIME_MS}ms]:    Detector acquisition window ({DETECTOR_WINDOW_MS}ms)")
    print(f"  [{DETECTOR_ON_TIME_MS}-{LED_ON_TIME_MS}ms]:      Safety buffer ({SAFETY_BUFFER_MS}ms)")
    print()


def test_acquisition_timing(detector):
    """Measure actual detector acquisition timing."""
    print("=" * 80)
    print("ACTUAL ACQUISITION TIMING MEASUREMENTS")
    print("=" * 80)
    print()
    
    # Get integration time
    integration_ms = detector._integration_time * 1000
    print(f"Integration time: {integration_ms:.2f}ms")
    print(f"USB overhead:     {USB_OVERHEAD_MS}ms (measured)")
    print()
    
    # Calculate optimal scans
    available_time = DETECTOR_WINDOW_MS - USB_OVERHEAD_MS
    calculated_scans = int(available_time / integration_ms)
    optimal_scans = min(calculated_scans, MAX_HARDWARE_AVERAGING)
    
    print(f"Optimal scan calculation:")
    print(f"  Available time:   {DETECTOR_WINDOW_MS}ms - {USB_OVERHEAD_MS}ms = {available_time}ms")
    print(f"  Scans per window: {available_time}ms / {integration_ms:.2f}ms = {calculated_scans}")
    print(f"  Hardware cap:     {MAX_HARDWARE_AVERAGING}")
    print(f"  OPTIMAL SCANS:    {optimal_scans}")
    print()
    
    # Test different scan counts
    print("Timing measurements:")
    print(f"  {'Scans':<8} {'Predicted':<15} {'Actual':<15} {'Fits Window?':<15} {'Margin':<10}")
    print("  " + "-" * 70)
    
    test_scans = [1, 3, 5, 9, optimal_scans]
    test_scans = sorted(list(set(test_scans)))
    
    for num_scans in test_scans:
        # Predicted time (hardware averaging is super efficient, so use measured ~7-8ms base)
        predicted_ms = (num_scans * integration_ms) + USB_OVERHEAD_MS
        
        # Measure actual
        detector.set_averaging(num_scans)
        time.sleep(0.05)
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            spectrum = detector.read_intensity()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
        
        actual_ms = np.mean(times)
        std_ms = np.std(times)
        
        # Check if fits
        fits = actual_ms <= DETECTOR_WINDOW_MS
        fits_str = "YES" if fits else "NO - TOO SLOW!"
        margin_ms = DETECTOR_WINDOW_MS - actual_ms
        margin_pct = (margin_ms / DETECTOR_WINDOW_MS) * 100
        
        print(f"  {num_scans:<8} {predicted_ms:>8.1f}ms       {actual_ms:>8.1f}+/-{std_ms:.1f}ms   {fits_str:<15} {margin_ms:>6.1f}ms ({margin_pct:>4.1f}%)")
    
    detector.set_averaging(1)
    print()
    
    return optimal_scans, actual_ms


def test_full_cycle_timing():
    """Show complete 4-channel cycle timing."""
    print("=" * 80)
    print("FULL 4-CHANNEL CYCLE TIMING")
    print("=" * 80)
    print()
    
    led_off_ms = 55.0  # Between channels
    channel_total = LED_ON_TIME_MS + led_off_ms
    cycle_total = channel_total * 4
    
    print("Per channel:")
    print(f"  LED ON:  {LED_ON_TIME_MS}ms")
    print(f"  LED OFF: {led_off_ms}ms")
    print(f"  TOTAL:   {channel_total}ms per channel")
    print()
    print("Full cycle (4 channels):")
    print(f"  Total time:  {cycle_total}ms = {cycle_total/1000:.2f}s")
    print(f"  Throughput:  {1000/cycle_total:.2f} cycles/second")
    print(f"               {60000/cycle_total:.1f} cycles/minute")
    print()


def main():
    print("\n")
    
    # Part 1: Visual breakdown
    visualize_timing()
    
    # Part 2: Connect to detector and test
    print("=" * 80)
    print("CONNECTING TO DETECTOR")
    print("=" * 80)
    print()
    
    detector = PhasePhotonics()
    if not detector.open():
        print("ERROR: Failed to open detector")
        return
    
    print(f"Connected: {detector.serial_number}")
    print()
    
    # Part 3: Measure acquisition timing
    optimal_scans, actual_time = test_acquisition_timing(detector)
    
    # Part 4: Full cycle timing
    test_full_cycle_timing()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Detector wait time:        {DETECTOR_WAIT_MS}ms (LED stabilization)")
    print(f"Detector window:           {DETECTOR_WINDOW_MS}ms (available for acquisition)")
    print(f"Optimal scans:             {optimal_scans} scans")
    print(f"Actual acquisition time:   {actual_time:.1f}ms")
    print(f"Time margin:               {DETECTOR_WINDOW_MS - actual_time:.1f}ms ({(DETECTOR_WINDOW_MS - actual_time)/DETECTOR_WINDOW_MS*100:.1f}%)")
    print(f"SNR improvement:           {np.sqrt(optimal_scans):.2f}x (vs single scan)")
    print()
    print("Hardware averaging is working correctly!" if actual_time <= DETECTOR_WINDOW_MS else "WARNING: Acquisition too slow!")
    print()
    
    detector.close()


if __name__ == "__main__":
    main()
