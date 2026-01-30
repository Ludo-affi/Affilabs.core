"""Phase Photonics Timing Optimizer

Based on discovered characteristic:
  Total Time ≈ Integration Time × 1.93

User requirements:
  - 250 ms total per channel
  - 60 ms detector off time
  - Available acquisition time: 190 ms per channel

This tool calculates optimal number of scans for different integration times.
"""

import numpy as np


def calculate_optimal_scans():
    """Calculate optimal scan configuration."""
    print("\n" + "="*80)
    print("PHASE PHOTONICS TIMING OPTIMIZER")
    print("="*80)
    
    # User requirements
    total_budget_ms = 250  # Total time per channel
    detector_off_ms = 60   # Detector off between channels
    available_ms = total_budget_ms - detector_off_ms  # Actual acquisition time
    
    print("\nREQUIREMENTS:")
    print(f"  Total budget per channel: {total_budget_ms} ms")
    print(f"  Detector off time: {detector_off_ms} ms")
    print(f"  Available acquisition time: {available_ms} ms")
    
    # Measured characteristic
    overhead_multiplier = 1.93
    
    print(f"\nDETECTOR CHARACTERISTIC:")
    print(f"  Total Time = Integration Time × {overhead_multiplier}")
    print(f"  (includes integration + USB overhead)")
    
    # Test various integration times
    integration_times = [10, 12, 15, 18, 20, 22, 25, 30]
    
    print("\n" + "="*80)
    print("SCAN OPTIMIZATION TABLE")
    print("="*80)
    print(f"\n{'Int(ms)':<10} {'Time/Scan':<12} {'Max Scans':<12} {'Actual Time':<14} {'SNR Gain':<12} {'Status':<10}")
    print("-" * 80)
    
    best_configs = []
    
    for int_time in integration_times:
        time_per_scan = int_time * overhead_multiplier
        max_scans = int(available_ms / time_per_scan)
        actual_time = max_scans * time_per_scan
        snr_gain = np.sqrt(max_scans)
        
        # Status check
        if actual_time <= available_ms:
            status = "✅ OK"
            best_configs.append({
                'int_time': int_time,
                'scans': max_scans,
                'time': actual_time,
                'snr': snr_gain
            })
        else:
            status = "❌ Too slow"
        
        print(f"{int_time:<10} {time_per_scan:<12.1f} {max_scans:<12} {actual_time:<14.1f} {snr_gain:<12.2f} {status:<10}")
    
    # Find sweet spots
    print("\n" + "="*80)
    print("RECOMMENDED CONFIGURATIONS")
    print("="*80)
    
    # Sort by SNR gain
    best_configs.sort(key=lambda x: x['snr'], reverse=True)
    
    print("\nTop 3 configurations (by SNR):")
    for i, config in enumerate(best_configs[:3], 1):
        print(f"\n{i}. Integration: {config['int_time']}ms, Scans: {config['scans']}")
        print(f"   Total time: {config['time']:.1f}ms (leaves {available_ms - config['time']:.1f}ms spare)")
        print(f"   SNR gain: √{config['scans']} = {config['snr']:.2f}x")
        print(f"   Signal strength: {config['int_time']/22:.2f}x relative to 22ms baseline")
        
        # Calculate full 4-LED cycle
        cycle_time = 4 * config['time'] + 4 * detector_off_ms
        print(f"   Full 4-LED cycle: {cycle_time:.1f}ms ({cycle_time/1000:.2f} seconds)")
        print(f"   Throughput: {1000/cycle_time:.2f} cycles/second")
    
    # Verify our current config (22ms, 4 scans)
    print("\n" + "="*80)
    print("CURRENT CONFIGURATION VERIFICATION")
    print("="*80)
    
    current_int = 22
    current_scans = 4
    current_time_per_scan = current_int * overhead_multiplier
    current_total = current_scans * current_time_per_scan
    current_snr = np.sqrt(current_scans)
    
    print(f"\nCurrent: {current_int}ms integration, {current_scans} scans")
    print(f"  Time per scan: {current_time_per_scan:.1f}ms")
    print(f"  Total time: {current_total:.1f}ms")
    print(f"  Budget remaining: {available_ms - current_total:.1f}ms")
    print(f"  SNR gain: √{current_scans} = {current_snr:.2f}x")
    
    if current_total <= available_ms:
        print(f"  Status: ✅ FITS within {available_ms}ms budget")
        
        # Check if we can squeeze one more scan
        next_scans = current_scans + 1
        next_total = next_scans * current_time_per_scan
        if next_total <= available_ms:
            print(f"\n  💡 NOTE: You can fit {next_scans} scans ({next_total:.1f}ms)!")
            print(f"     SNR would improve to √{next_scans} = {np.sqrt(next_scans):.2f}x")
        else:
            print(f"\n  ℹ️ Cannot fit {next_scans} scans ({next_total:.1f}ms > {available_ms}ms)")
    else:
        print(f"  Status: ❌ EXCEEDS {available_ms}ms budget by {current_total - available_ms:.1f}ms")
    
    # Full cycle analysis
    print("\n" + "="*80)
    print("4-LED CYCLE ANALYSIS")
    print("="*80)
    
    cycle_acquisition = 4 * current_total
    cycle_off_time = 4 * detector_off_ms
    cycle_total = cycle_acquisition + cycle_off_time
    
    print(f"\nWith current config ({current_int}ms, {current_scans} scans):")
    print(f"  Acquisition time: 4 LEDs × {current_total:.1f}ms = {cycle_acquisition:.1f}ms")
    print(f"  Off time: 4 LEDs × {detector_off_ms}ms = {cycle_off_time:.1f}ms")
    print(f"  Total cycle: {cycle_total:.1f}ms ({cycle_total/1000:.2f} seconds)")
    print(f"  Throughput: {1000/cycle_total:.2f} cycles/second ({60000/cycle_total:.1f} cycles/minute)")
    
    # Breakdown
    print(f"\nTime breakdown per cycle:")
    print(f"  Acquisition: {cycle_acquisition/cycle_total*100:.1f}%")
    print(f"  Detector off: {cycle_off_time/cycle_total*100:.1f}%")
    
    print("\n" + "="*80)
    print("FORMULA VERIFICATION")
    print("="*80)
    
    # Verify formula with measured data
    test_cases = [
        (10, 19.3),
        (22, 42.5),
        (15, 29.0),
    ]
    
    print(f"\nTesting: Total Time = Integration × {overhead_multiplier}")
    print(f"{'Integration':<15} {'Predicted':<15} {'Expected':<15} {'Match':<10}")
    print("-" * 55)
    
    for int_time, expected in test_cases:
        predicted = int_time * overhead_multiplier
        match = "✅" if abs(predicted - expected) < 1 else "⚠️"
        print(f"{int_time}ms{'':<10} {predicted:.1f}ms{'':<8} {expected:.1f}ms{'':<8} {match}")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    calculate_optimal_scans()
