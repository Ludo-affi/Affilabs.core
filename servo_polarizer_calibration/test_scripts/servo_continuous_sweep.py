"""Continuous servo sweep with data acquisition during movement.

Strategy:
1. Start continuous spectral acquisition at 5ms integration time (~200 Hz max)
2. Command servo to move from PWM 1 to PWM 255
3. Record timestamps for each spectrum during movement
4. Calculate servo position based on timestamp and known speed

Hardware: PicoP4SPR + USB4000
LEDs: All 4 at 20% (51/255)
Integration: 5 ms
"""

import sys
import threading
import time
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
    integration_time_s = integration_time_ms / 1000.0

    print("\n=== 5-POSITION CONTINUOUS SWEEP TEST ===")
    print("Moving through 5 positions, acquiring continuously during movement")
    print("Forward sweep (1->255) then Backward sweep (255->1)")

    # Define 5 target positions
    start_pwm = 1
    end_pwm = 255
    num_positions = 5
    target_positions = [
        int(start_pwm + i * (end_pwm - start_pwm) / (num_positions - 1))
        for i in range(num_positions)
    ]

    print(f"# Target positions: {target_positions}")
    print(
        "cycle,direction,segment,target_pwm,timestamp,elapsed_time,estimated_pwm,intensity",
    )

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

    # Let a few samples accumulate before starting
    time.sleep(0.2)

    # ========== FORWARD SWEEP ==========
    print("# === FORWARD SWEEP (1->255) ===")

    # Move to first position to start
    print(f"# Moving to start position (PWM {target_positions[0]})...")
    cmd = f"sv{target_positions[0]:03d}000\n"
    hm.ctrl._ser.reset_input_buffer()
    hm.ctrl._ser.write(cmd.encode())
    time.sleep(0.1)
    hm.ctrl._ser.write(b"ss\n")
    time.sleep(2.0)  # Wait at start

    # Move through each segment
    for i in range(len(target_positions) - 1):
        start_pos = target_positions[i]
        end_pos = target_positions[i + 1]

        print(f"# Forward segment {i+1}: PWM {start_pos} -> {end_pos}")

        # Command servo to move to next position
        cmd = f"sv{end_pos:03d}000\n"
        hm.ctrl._ser.reset_input_buffer()
        hm.ctrl._ser.write(cmd.encode())
        time.sleep(0.05)

        # Record segment start time
        segment_start = time.time()
        segment_start_sample_count = len(samples)
        hm.ctrl._ser.write(b"ss\n")

        # Wait for movement to complete (estimate based on PWM distance)
        pwm_distance = abs(end_pos - start_pos)
        estimated_time = pwm_distance / 42.0  # ~42 PWM/sec from previous test
        time.sleep(estimated_time + 0.5)  # Add margin

        segment_end = time.time()
        segment_samples = len(samples) - segment_start_sample_count
        print(
            f"# Segment {i+1} complete: {segment_samples} samples in {segment_end - segment_start:.3f}s",
        )

    print("# Forward sweep complete")

    # ========== BACKWARD SWEEP ==========
    print("# === BACKWARD SWEEP (255->1) ===")

    # Reverse the target positions for backward sweep
    backward_positions = list(reversed(target_positions))

    # Move through each segment in reverse
    for i in range(len(backward_positions) - 1):
        start_pos = backward_positions[i]
        end_pos = backward_positions[i + 1]

        print(f"# Backward segment {i+1}: PWM {start_pos} -> {end_pos}")

        # Command servo to move to next position
        cmd = f"sv{end_pos:03d}000\n"
        hm.ctrl._ser.reset_input_buffer()
        hm.ctrl._ser.write(cmd.encode())
        time.sleep(0.05)

        # Record segment start time
        segment_start = time.time()
        segment_start_sample_count = len(samples)
        hm.ctrl._ser.write(b"ss\n")

        # Wait for movement to complete
        pwm_distance = abs(end_pos - start_pos)
        estimated_time = pwm_distance / 42.0
        time.sleep(estimated_time + 0.5)

        segment_end = time.time()
        segment_samples = len(samples) - segment_start_sample_count
        print(
            f"# Segment {i+1} complete: {segment_samples} samples in {segment_end - segment_start:.3f}s",
        )

    print("# Backward sweep complete")

    # Stop acquisition
    acquiring = False
    acq_thread.join(timeout=1.0)

    print(f"# Total samples collected: {len(samples)}")

    # Process and output all data with segment information
    if samples:
        print(f"# Processing {len(samples)} samples...")

        # Forward sweep segments
        fwd_segment_idx = 0
        for i in range(len(target_positions) - 1):
            start_pos = target_positions[i]
            end_pos = target_positions[i + 1]

            # Find samples in this segment's time window
            # (This is approximate - using simple time-based estimation)
            segment_duration = abs(end_pos - start_pos) / 42.0
            segment_start_time = (
                samples[0][0] + 2.0 + fwd_segment_idx * (segment_duration + 0.5)
            )
            segment_end_time = segment_start_time + segment_duration + 0.5

            for timestamp, intensity in samples:
                if segment_start_time <= timestamp <= segment_end_time:
                    elapsed = timestamp - segment_start_time
                    # Linear interpolation for PWM position
                    if segment_duration > 0:
                        progress = min(1.0, elapsed / segment_duration)
                        estimated_pwm = start_pos + progress * (end_pos - start_pos)
                    else:
                        estimated_pwm = start_pos

                    print(
                        f"forward,forward,{i+1},{end_pos},{timestamp:.6f},{elapsed:.6f},{estimated_pwm:.1f},{intensity:.2f}",
                    )

            fwd_segment_idx += 1

        # Backward sweep segments
        bwd_start_time = segment_end_time
        bwd_segment_idx = 0
        backward_positions = list(reversed(target_positions))

        for i in range(len(backward_positions) - 1):
            start_pos = backward_positions[i]
            end_pos = backward_positions[i + 1]

            segment_duration = abs(end_pos - start_pos) / 42.0
            segment_start_time = bwd_start_time + bwd_segment_idx * (
                segment_duration + 0.5
            )
            segment_end_time = segment_start_time + segment_duration + 0.5

            for timestamp, intensity in samples:
                if segment_start_time <= timestamp <= segment_end_time:
                    elapsed = timestamp - segment_start_time
                    # Linear interpolation for PWM position
                    if segment_duration > 0:
                        progress = min(1.0, elapsed / segment_duration)
                        estimated_pwm = start_pos + progress * (end_pos - start_pos)
                    else:
                        estimated_pwm = start_pos

                    print(
                        f"backward,backward,{i+1},{end_pos},{timestamp:.6f},{elapsed:.6f},{estimated_pwm:.1f},{intensity:.2f}",
                    )

            bwd_segment_idx += 1

    print(f"\n# Total samples: {len(samples)}")
    print(f"# Integration time: {integration_time_ms} ms")

    # Save to CSV file
    csv_path = ROOT / "servo_continuous_latest.csv"
    with open(csv_path, "w") as f:
        f.write(
            "cycle,direction,segment,target_pwm,timestamp,elapsed_time,estimated_pwm,intensity\n",
        )

        # Forward sweep segments
        fwd_segment_idx = 0
        for i in range(len(target_positions) - 1):
            start_pos = target_positions[i]
            end_pos = target_positions[i + 1]

            segment_duration = abs(end_pos - start_pos) / 42.0
            segment_start_time = (
                samples[0][0] + 2.0 + fwd_segment_idx * (segment_duration + 0.5)
            )
            segment_end_time = segment_start_time + segment_duration + 0.5

            for timestamp, intensity in samples:
                if segment_start_time <= timestamp <= segment_end_time:
                    elapsed = timestamp - segment_start_time
                    if segment_duration > 0:
                        progress = min(1.0, elapsed / segment_duration)
                        estimated_pwm = start_pos + progress * (end_pos - start_pos)
                    else:
                        estimated_pwm = start_pos

                    f.write(
                        f"forward,forward,{i+1},{end_pos},{timestamp:.6f},{elapsed:.6f},{estimated_pwm:.1f},{intensity:.2f}\n",
                    )

            fwd_segment_idx += 1

        # Backward sweep segments
        bwd_start_time = segment_end_time
        bwd_segment_idx = 0
        backward_positions = list(reversed(target_positions))

        for i in range(len(backward_positions) - 1):
            start_pos = backward_positions[i]
            end_pos = backward_positions[i + 1]

            segment_duration = abs(end_pos - start_pos) / 42.0
            segment_start_time = bwd_start_time + bwd_segment_idx * (
                segment_duration + 0.5
            )
            segment_end_time = segment_start_time + segment_duration + 0.5

            for timestamp, intensity in samples:
                if segment_start_time <= timestamp <= segment_end_time:
                    elapsed = timestamp - segment_start_time
                    if segment_duration > 0:
                        progress = min(1.0, elapsed / segment_duration)
                        estimated_pwm = start_pos + progress * (end_pos - start_pos)
                    else:
                        estimated_pwm = start_pos

                    f.write(
                        f"backward,backward,{i+1},{end_pos},{timestamp:.6f},{elapsed:.6f},{estimated_pwm:.1f},{intensity:.2f}\n",
                    )

            bwd_segment_idx += 1

    print(f"# Saved data to {csv_path}")

    # Turn off LEDs
    hm.ctrl._ser.write(b"lx\n")
    print("\nDone!")


if __name__ == "__main__":
    main()
