"""
Refined servo sweep with 2 PWM resolution around S and P positions.

Based on initial sweep results:
- S position: PWM ~80-97 (peak intensity ~14,000 counts)
- P position: PWM ~1-5 (minimum intensity ~9,100 counts)

This script performs detailed sweeps around these regions.
"""

import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from core.hardware_manager import HardwareManager

def main():
    print("Connecting hardware...")
    hm = HardwareManager()
    hm.scan_and_connect(auto_connect=True)
    
    # Wait for connection
    t0 = time.time()
    while time.time() - t0 < 15.0:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)
    
    if not hm.ctrl or not hm.usb:
        print("ERROR: Hardware not connected")
        sys.exit(1)
    
    print(f"Connected: {hm.ctrl.name}, {hm.usb.serial_number}")
    
    # Turn on LEDs using lm command + batch brightness
    print("\nTurning on LEDs...")
    hm.ctrl._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)
    hm.ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)
    
    # Set integration time
    integration_time_ms = 5.0
    hm.usb.set_integration(integration_time_ms)
    
    print("\n=== REFINED SERVO SWEEP ===")
    print("Phase 1: P position region (PWM 1-15, step 2)")
    print("Phase 2: S position region (PWM 70-105, step 2)")
    
    # Define sweep regions with 2 PWM resolution
    p_region = list(range(1, 16, 2))  # [1, 3, 5, 7, 9, 11, 13, 15]
    s_region = list(range(70, 106, 2))  # [70, 72, 74, ..., 104]
    
    print(f"# P region positions: {p_region}")
    print(f"# S region positions: {s_region}")
    print("region,pwm,timestamp,intensity")
    
    # Storage for acquired data
    samples = []
    acquiring = True
    
    def acquire_continuously():
        """Background thread to acquire spectra"""
        while acquiring:
            try:
                spectrum = hm.usb.read_intensity()
                if spectrum is not None:
                    timestamp = time.time()
                    intensity = float(spectrum.max())
                    samples.append((timestamp, intensity))
            except Exception as e:
                print(f"# Acquisition error: {e}")
                break
    
    # Start acquisition thread
    acq_thread = threading.Thread(target=acquire_continuously, daemon=True)
    acq_thread.start()
    
    # Let a few samples accumulate
    time.sleep(0.2)
    
    # ========== PHASE 1: P REGION ==========
    print(f"# === PHASE 1: P REGION (1-15 PWM) ===")
    
    # Move to first position
    print(f"# Moving to PWM {p_region[0]}...")
    cmd = f"sv{p_region[0]:03d}000\n"
    hm.ctrl._ser.reset_input_buffer()
    hm.ctrl._ser.write(cmd.encode())
    time.sleep(0.1)
    hm.ctrl._ser.write(b"ss\n")
    time.sleep(2.0)  # Wait to settle
    
    segment_start = time.time()
    sample_start_idx = len(samples)
    
    # Move through P region
    for i, pwm in enumerate(p_region):
        if i == 0:
            continue  # Already at first position
        
        cmd = f"sv{pwm:03d}000\n"
        hm.ctrl._ser.reset_input_buffer()
        hm.ctrl._ser.write(cmd.encode())
        time.sleep(0.05)
        hm.ctrl._ser.write(b"ss\n")
        
        # Small movements, so short wait
        time.sleep(0.3)
    
    segment_end = time.time()
    p_samples = len(samples) - sample_start_idx
    print(f"# P region complete: {p_samples} samples in {segment_end - segment_start:.3f}s")
    
    # Output P region data
    pwm_per_sec = (p_region[-1] - p_region[0]) / (segment_end - segment_start)
    for timestamp, intensity in samples[sample_start_idx:]:
        elapsed = timestamp - segment_start
        estimated_pwm = p_region[0] + elapsed * pwm_per_sec
        estimated_pwm = max(p_region[0], min(p_region[-1], estimated_pwm))
        print(f"P,{estimated_pwm:.1f},{timestamp:.6f},{intensity:.2f}")
    
    # ========== PHASE 2: S REGION ==========
    print(f"# === PHASE 2: S REGION (70-105 PWM) ===")
    
    # Move to first position of S region
    print(f"# Moving to PWM {s_region[0]}...")
    cmd = f"sv{s_region[0]:03d}000\n"
    hm.ctrl._ser.reset_input_buffer()
    hm.ctrl._ser.write(cmd.encode())
    time.sleep(0.1)
    hm.ctrl._ser.write(b"ss\n")
    time.sleep(2.5)  # Longer move from P to S region
    
    segment_start = time.time()
    sample_start_idx = len(samples)
    
    # Move through S region
    for i, pwm in enumerate(s_region):
        if i == 0:
            continue  # Already at first position
        
        cmd = f"sv{pwm:03d}000\n"
        hm.ctrl._ser.reset_input_buffer()
        hm.ctrl._ser.write(cmd.encode())
        time.sleep(0.05)
        hm.ctrl._ser.write(b"ss\n")
        
        # Small movements
        time.sleep(0.3)
    
    segment_end = time.time()
    s_samples = len(samples) - sample_start_idx
    print(f"# S region complete: {s_samples} samples in {segment_end - segment_start:.3f}s")
    
    # Output S region data
    pwm_per_sec = (s_region[-1] - s_region[0]) / (segment_end - segment_start)
    for timestamp, intensity in samples[sample_start_idx:]:
        elapsed = timestamp - segment_start
        estimated_pwm = s_region[0] + elapsed * pwm_per_sec
        estimated_pwm = max(s_region[0], min(s_region[-1], estimated_pwm))
        print(f"S,{estimated_pwm:.1f},{timestamp:.6f},{intensity:.2f}")
    
    # Stop acquisition
    acquiring = False
    acq_thread.join(timeout=1.0)
    
    print(f"\n# Total samples: {len(samples)}")
    print(f"# P region: {p_samples} samples")
    print(f"# S region: {s_samples} samples")
    print(f"# Integration time: {integration_time_ms} ms")
    
    # Save to CSV
    csv_path = ROOT / "servo_refined_sweep.csv"
    with open(csv_path, 'w') as f:
        f.write("region,pwm,timestamp,intensity\n")
        
        # P region data
        pwm_per_sec = (p_region[-1] - p_region[0]) / (segment_end - segment_start)
        p_segment_start = samples[0][0] + 2.0  # Approximate start after initial settle
        p_segment_end = p_segment_start + (p_region[-1] - p_region[0]) / pwm_per_sec
        
        for timestamp, intensity in samples:
            if timestamp >= p_segment_start and timestamp <= p_segment_end:
                elapsed = timestamp - p_segment_start
                estimated_pwm = p_region[0] + elapsed * ((p_region[-1] - p_region[0]) / (p_segment_end - p_segment_start))
                estimated_pwm = max(p_region[0], min(p_region[-1], estimated_pwm))
                f.write(f"P,{estimated_pwm:.1f},{timestamp:.6f},{intensity:.2f}\n")
        
        # S region data (approximate start time)
        s_segment_start = p_segment_end + 3.0  # Approximate transition time
        s_segment_end = s_segment_start + (s_region[-1] - s_region[0]) / pwm_per_sec
        
        for timestamp, intensity in samples:
            if timestamp >= s_segment_start and timestamp <= s_segment_end:
                elapsed = timestamp - s_segment_start
                estimated_pwm = s_region[0] + elapsed * ((s_region[-1] - s_region[0]) / (s_segment_end - s_segment_start))
                estimated_pwm = max(s_region[0], min(s_region[-1], estimated_pwm))
                f.write(f"S,{estimated_pwm:.1f},{timestamp:.6f},{intensity:.2f}\n")
    
    print(f"# Saved data to {csv_path}")
    
    # Turn off LEDs
    hm.ctrl._ser.write(b"lx\n")
    print("\nDone!")

if __name__ == "__main__":
    main()
