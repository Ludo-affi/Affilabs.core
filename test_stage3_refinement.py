"""Test multi-pass converging scan to find windows.

This script performs 5 back-and-forth scans with increasing resolution
to find P and S polarization windows.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add parent directory to path for affilabs imports
ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

from affilabs.core.hardware_manager import HardwareManager


def measure_intensity(hm, wavelengths):
    """Take a single intensity measurement using spectral analysis."""
    try:
        spectrum = hm.usb.read_intensity()
        if spectrum is None or len(spectrum) == 0:
            return 0.0
        
        # Get peak in 900-1000nm range (similar to calibration)
        mask = (wavelengths >= 900) & (wavelengths <= 1000)
        if not np.any(mask):
            return float(np.max(spectrum))
        
        return float(np.max(spectrum[mask]))
    except Exception as e:
        print(f"  Warning: Measurement failed: {e}")
        return 0.0


def move_servo_pwm(ctrl, p_pwm, s_pwm, settle_time=0.5):
    """Move servo to specific PWM positions using sv+sp commands."""
    raw_ctrl = ctrl._ctrl if hasattr(ctrl, '_ctrl') else ctrl
    
    try:
        # Convert PWM to degrees
        p_degrees = int(p_pwm * 180.0 / 255.0)
        s_degrees = int(s_pwm * 180.0 / 255.0)
        
        # Send sv command
        cmd = f"sv{s_degrees:03d}{p_degrees:03d}\n"
        raw_ctrl._ser.write(cmd.encode())
        time.sleep(0.1)
        sv_response = raw_ctrl._ser.readline().strip()
        
        # Send sp to move P servo and wait for settling
        raw_ctrl._ser.write(b"sp\n")
        time.sleep(settle_time)
        sp_response = raw_ctrl._ser.readline().strip()
        
        return True
    except Exception as e:
        print(f"  Error moving servo: {e}")
        return False


def converging_scan(hm, wavelengths, ctrl, s_fixed=128, dark_threshold=1000):
    """Perform 2 passes to find windows efficiently.
    
    Pass 1: 0-255 step 15 (forward) - identify interesting regions
    Pass 2: Refine only non-baseline regions with step 8
    """
    
    settle_time = 0.5  # Single settle time for all movements
    
    # Pass 1: Coarse scan to identify regions
    print(f"\nPass 1: Coarse scan (step 15, settle={settle_time}s)")
    positions = list(range(0, 256, 15))
    print(f"  Testing {len(positions)} positions")
    
    all_results = []
    baseline_regions = []  # Track baseline regions to skip
    
    for p_pwm in positions:
        success = move_servo_pwm(ctrl, p_pwm, s_fixed, settle_time)
        if not success:
            continue
        
        # Measure 2 times
        measurements = []
        for i in range(2):
            intensity = measure_intensity(hm, wavelengths)
            measurements.append(intensity)
            if i < 1:
                time.sleep(0.1)
        
        mean_intensity = np.mean(measurements)
        all_results.append((p_pwm, mean_intensity))
        
        # Track if this is baseline
        if mean_intensity < dark_threshold:
            baseline_regions.append(p_pwm)
            marker = "BASELINE"
        elif mean_intensity < 2500:
            marker = "P-POL"
        else:
            marker = "S-POL"
        
        if mean_intensity < dark_threshold or mean_intensity > 2000:
            print(f"    PWM {p_pwm:3d}: {mean_intensity:6.1f} counts <<< {marker}")
    
    # Identify non-baseline ranges
    non_baseline_ranges = []
    for pwm, intensity in all_results:
        if intensity >= dark_threshold:
            # Add range around this position
            non_baseline_ranges.append((max(0, pwm - 15), min(255, pwm + 15)))
    
    # Merge overlapping ranges
    if non_baseline_ranges:
        non_baseline_ranges.sort()
        merged = [non_baseline_ranges[0]]
        for start, end in non_baseline_ranges[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        non_baseline_ranges = merged
    
    print(f"\nNon-baseline regions: {non_baseline_ranges}")
    
    # Pass 2: Medium resolution on non-baseline regions (FINAL PASS)
    print(f"\nPass 2: Medium scan (step 8, settle={settle_time}s)")
    pass2_positions = []
    for start, end in non_baseline_ranges:
        pass2_positions.extend(range(start, end + 1, 8))
    print(f"  Testing {len(pass2_positions)} positions")
    
    for p_pwm in pass2_positions:
        if any(abs(p_pwm - r[0]) < 3 for r in all_results):
            continue  # Skip if already tested recently
        
        success = move_servo_pwm(ctrl, p_pwm, s_fixed, settle_time)
        if not success:
            continue
        
        measurements = []
        for i in range(2):
            intensity = measure_intensity(hm, wavelengths)
            measurements.append(intensity)
            if i < 1:
                time.sleep(0.1)
        
        mean_intensity = np.mean(measurements)
        all_results.append((p_pwm, mean_intensity))
        
        if mean_intensity < dark_threshold:
            marker = "BASELINE"
        elif mean_intensity < 2500:
            marker = "P-POL"
        else:
            marker = "S-POL"
        
        if mean_intensity < dark_threshold or mean_intensity > 2000:
            print(f"    PWM {p_pwm:3d}: {mean_intensity:6.1f} counts <<< {marker}")
    
    return all_results


def main():
    """Test multi-pass converging scan."""
    print("\n" + "=" * 70)
    print("MULTI-PASS CONVERGING SCAN TEST")
    print("=" * 70)
    
    # Connect to hardware
    hm = HardwareManager()
    print("\nConnecting hardware...")
    hm.scan_and_connect(auto_connect=True)
    time.sleep(2)
    
    if not hm.ctrl or not hm.usb:
        print("ERROR: Hardware not connected")
        return
    
    print("✅ Hardware connected")
    
    # Enable LEDs using P4SPR method (lm:ABCD)
    print("\nEnabling all 4 LEDs...")
    ctrl = hm.ctrl
    raw_ctrl = ctrl._ctrl if hasattr(ctrl, '_ctrl') else ctrl
    
    try:
        if hasattr(raw_ctrl, '_ser') and raw_ctrl._ser is not None:
            raw_ctrl._ser.write(b"lm:ABCD\n")
            time.sleep(0.05)
            response = raw_ctrl._ser.readline().strip()
            print(f"  lm:ABCD response: {response}")
    except Exception as e:
        print(f"  WARNING: Failed to enable LEDs: {e}")
    
    # Set LED intensity to 20%
    led_intensity = int(20 * 255 / 100)
    print(f"\nSetting LED intensity to 20% (PWM {led_intensity})...")
    try:
        for ch in ['a', 'b', 'c', 'd']:
            try:
                hm.ctrl.turn_on_channel(ch=ch)
                hm.ctrl.set_intensity(ch=ch, raw_val=led_intensity)
            except Exception:
                pass
    except Exception as e:
        print(f"  Warning: Batch LED setup failed: {e}")
    
    time.sleep(0.2)
    
    # Set integration time
    print("\nSetting integration time to 10ms...")
    hm.usb.set_integration(10.0)
    
    # Get wavelengths
    wavelengths = hm.usb.read_wavelength()
    print(f"✅ Got {len(wavelengths)} wavelength points")
    
    # Get detector characteristics
    dark_current = getattr(hm.usb, 'dark_current', 900)
    dark_threshold = int(dark_current * 1.1)  # 10% margin above dark current
    
    print(f"\nDetector dark current: {dark_current} counts")
    print(f"Dark threshold: {dark_threshold} counts")
    
    time.sleep(1.0)
    
    # Run converging scan
    print("\n" + "=" * 70)
    print("STARTING 2-PASS CONVERGING SCAN")
    print("=" * 70)
    print("S servo fixed at PWM 128")
    print("P servo scanning 0-255 with increasing resolution")
    print(f"DARK < {dark_threshold} | P-pol = lowest non-dark | S-pol = highest")
    
    results = converging_scan(hm, wavelengths, ctrl, s_fixed=128, dark_threshold=dark_threshold)
    results = converging_scan(hm, wavelengths, ctrl, s_fixed=128)
    
    # Analyze results
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    # Find dark and bright regions
    pwm_vals = [r[0] for r in results]
    intensities = [r[1] for r in results]
    
    # Sort by intensity
    sorted_results = sorted(results, key=lambda x: x[1])
    
    print("\nDARKEST positions (P polarization candidates):")
    for pwm, intensity in sorted_results[:10]:
        print(f"  PWM {pwm:3d}: {intensity:6.1f} counts")
    
    print("\nBRIGHTEST positions (S polarization candidates):")
    for pwm, intensity in sorted_results[-10:]:
        print(f"  PWM {pwm:3d}: {intensity:6.1f} counts")
    
    # Find distinct windows
    # DARK baseline < dark_threshold, P-pol = lowest non-dark, S-pol = highest
    dark_baseline = [r for r in results if r[1] < dark_threshold]
    non_dark = [r for r in results if r[1] >= dark_threshold]
    
    if non_dark:
        non_dark_sorted = sorted(non_dark, key=lambda x: x[1])
        p_candidates = non_dark_sorted[:20]  # Lowest 20 non-dark positions
        s_candidates = non_dark_sorted[-20:]  # Highest 20 positions
    else:
        p_candidates = []
        s_candidates = []
    
    print(f"\nFound {len(dark_baseline)} baseline dark positions (< {dark_threshold} counts)")
    print(f"Found {len(p_candidates)} P-pol candidates (lowest non-dark)")
    print(f"Found {len(s_candidates)} S-pol candidates (highest)")
    
    # Cluster to find distinct windows
    def cluster_positions(positions, threshold=30):
        """Group positions within threshold PWM."""
        if not positions:
            return []
        
        clusters = []
        sorted_pos = sorted(positions, key=lambda x: x[0])
        
        current_cluster = [sorted_pos[0]]
        for pos in sorted_pos[1:]:
            if abs(pos[0] - current_cluster[0][0]) <= threshold:
                current_cluster.append(pos)
            else:
                clusters.append(current_cluster)
                current_cluster = [pos]
        clusters.append(current_cluster)
        
        return clusters
    
    if p_candidates:
        p_clusters = cluster_positions(p_candidates)
        print(f"\nP window clusters ({len(p_clusters)}):")
        for i, cluster in enumerate(p_clusters):
            best = min(cluster, key=lambda x: x[1])  # Lowest in cluster
            avg_pwm = int(np.mean([c[0] for c in cluster]))
            print(f"  Cluster {i+1}: PWM ~{avg_pwm} (best: PWM {best[0]}, {best[1]:.1f} counts)")
    
    if s_candidates:
        s_clusters = cluster_positions(s_candidates)
        print(f"\nS window clusters ({len(s_clusters)}):")
        for i, cluster in enumerate(s_clusters):
            best = max(cluster, key=lambda x: x[1])  # Highest in cluster
            avg_pwm = int(np.mean([c[0] for c in cluster]))
            print(f"  Cluster {i+1}: PWM ~{avg_pwm} (best: PWM {best[0]}, {best[1]:.1f} counts)")
    
    # Save results to file
    output_file = ROOT / "converging_scan_results.txt"
    with open(output_file, 'w') as f:
        f.write("PWM,Intensity\n")
        for pwm, intensity in results:
            f.write(f"{pwm},{intensity:.1f}\n")
    print(f"\n✅ Results saved to {output_file}")
    
    # Turn off LEDs
    print("\nCleaning up...")
    try:
        raw_ctrl._ser.write(b"lx\n")
        time.sleep(0.1)
    except:
        pass
    print("Done!")


if __name__ == "__main__":
    main()
