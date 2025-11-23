"""
Simple Peak Tracking Stability Test

Directly accesses the data acquisition system without GUI dependencies.
Measures peak-to-peak variation over 2 minutes.
"""

import time
import numpy as np
from pathlib import Path
import sys
from datetime import datetime
import csv

# Add project root
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Import only what we need
from utils.logger import logger


def test_peak_stability():
    """Test peak tracking stability for 2 minutes."""

    print("\n" + "="*70)
    print("PEAK TRACKING STABILITY TEST")
    print("="*70)
    print(f"Duration: 2 minutes")
    print(f"Sampling: 1 Hz")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Import state machine here after logger is initialized
    from utils.spr_state_machine import SPRStateMachine

    try:
        # Initialize state machine - it auto-initializes hardware
        print("Initializing SPR system...")
        state_machine = SPRStateMachine(app=None)

        # Wait for hardware initialization
        print("Waiting for hardware initialization...")
        time.sleep(5)

        # The state machine should have initialized automatically
        print("✅ System initialized")

        # Check if we have data access
        if not hasattr(state_machine, 'data_acquisition_wrapper'):
            print("❌ ERROR: No data acquisition wrapper")
            return

        if not state_machine.data_acquisition_wrapper:
            print("❌ ERROR: Data acquisition wrapper is None")
            return

        acq = state_machine.data_acquisition_wrapper

        # Wait for data acquisition to start
        print("Waiting for data acquisition to start...")
        time.sleep(3)

        # Data storage
        data = {
            'a': [],
            'b': [],
            'c': [],
            'd': []
        }
        timestamps = []

        # Test parameters
        DURATION = 120  # 2 minutes
        SAMPLE_INTERVAL = 1.0  # 1 Hz

        start_time = time.time()
        last_sample_time = start_time
        sample_count = 0

        print("\nCollecting data...")
        print("Progress: [" + " " * 50 + "] 0%", end="", flush=True)

        while True:
            elapsed = time.time() - start_time

            if elapsed >= DURATION:
                break

            # Sample at 1 Hz
            if time.time() - last_sample_time >= SAMPLE_INTERVAL:
                # Collect data
                for ch in ['a', 'b', 'c', 'd']:
                    if hasattr(acq, 'filtered_lambda'):
                        if ch in acq.filtered_lambda:
                            if len(acq.filtered_lambda[ch]) > 0:
                                lambda_val = acq.filtered_lambda[ch][-1]
                                data[ch].append(lambda_val)

                timestamps.append(elapsed)
                sample_count += 1
                last_sample_time = time.time()

                # Update progress bar
                progress = int((elapsed / DURATION) * 50)
                percent = int((elapsed / DURATION) * 100)
                bar = "█" * progress + " " * (50 - progress)
                eta = int(DURATION - elapsed)
                print(f"\rProgress: [{bar}] {percent}% | ETA: {eta}s   ", end="", flush=True)

            time.sleep(0.1)  # Small sleep to prevent CPU spinning

        print("\n\n" + "="*70)
        print("DATA COLLECTION COMPLETE")
        print("="*70)
        print(f"Samples collected: {sample_count}")
        print(f"Duration: {elapsed:.1f} seconds")
        print("="*70 + "\n")

        # Stop acquisition
        if hasattr(state_machine, 'stop'):
            state_machine.stop()

        # Analyze data
        print("\n" + "="*70)
        print("RESULTS - PEAK TRACKING STABILITY")
        print("="*70 + "\n")

        stats = {}
        for ch in ['a', 'b', 'c', 'd']:
            if len(data[ch]) > 0:
                arr = np.array(data[ch])
                stats[ch] = {
                    'count': len(arr),
                    'min': np.min(arr),
                    'max': np.max(arr),
                    'mean': np.mean(arr),
                    'std': np.std(arr),
                    'p2p': np.max(arr) - np.min(arr)
                }

                # SNR calculation
                if stats[ch]['std'] > 0:
                    stats[ch]['snr'] = stats[ch]['mean'] / stats[ch]['std']
                else:
                    stats[ch]['snr'] = float('inf')

                # Print channel results
                print(f"Channel {ch.upper()}:")
                print(f"  Samples:     {stats[ch]['count']}")
                print(f"  Mean:        {stats[ch]['mean']:.4f} nm")
                print(f"  Min:         {stats[ch]['min']:.4f} nm")
                print(f"  Max:         {stats[ch]['max']:.4f} nm")
                print(f"  Peak-to-Peak: {stats[ch]['p2p']:.4f} nm  ", end="")

                # Assessment
                if stats[ch]['p2p'] < 0.1:
                    print("✅ EXCELLENT")
                elif stats[ch]['p2p'] < 0.2:
                    print("✅ GOOD")
                elif stats[ch]['p2p'] < 0.5:
                    print("⚠️  ACCEPTABLE")
                else:
                    print("❌ POOR")

                print(f"  Std Dev:     {stats[ch]['std']:.4f} nm")
                print(f"  SNR:         {stats[ch]['snr']:.1f}")
                print()
            else:
                print(f"Channel {ch.upper()}: ❌ NO DATA")
                print()

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = ROOT_DIR / f"peak_tracking_test_{timestamp}.csv"

        print("="*70)
        print(f"Saving data to: {csv_path.name}")
        print("="*70 + "\n")

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['timestamp', 'channel_a', 'channel_b', 'channel_c', 'channel_d'])

            # Data rows
            max_len = max(len(data[ch]) for ch in ['a', 'b', 'c', 'd'])
            for i in range(max_len):
                row = [timestamps[i] if i < len(timestamps) else '']
                for ch in ['a', 'b', 'c', 'd']:
                    row.append(data[ch][i] if i < len(data[ch]) else '')
                writer.writerow(row)

        print("✅ Data saved successfully")

        # Overall assessment
        print("\n" + "="*70)
        print("OVERALL ASSESSMENT")
        print("="*70 + "\n")

        avg_p2p = np.mean([stats[ch]['p2p'] for ch in ['a', 'b', 'c', 'd'] if ch in stats])
        avg_snr = np.mean([stats[ch]['snr'] for ch in ['a', 'b', 'c', 'd'] if ch in stats])

        print(f"Average Peak-to-Peak: {avg_p2p:.4f} nm")
        print(f"Average SNR:          {avg_snr:.1f}")
        print()

        if avg_p2p < 0.1:
            print("🎉 EXCELLENT performance! Peak tracking is very stable.")
            print("   Current settings are optimal.")
        elif avg_p2p < 0.2:
            print("✅ GOOD performance. Peak tracking is stable.")
            print("   Current settings are working well.")
        elif avg_p2p < 0.5:
            print("⚠️  ACCEPTABLE performance. Some noise present.")
            print("   Consider:")
            print("   • Increasing LED delay (currently 3ms)")
            print("   • Increasing scan count (currently 2)")
        else:
            print("❌ POOR performance. High variation detected.")
            print("   Recommended actions:")
            print("   • Increase LED delay from 3ms to 6ms (2× buffer)")
            print("   • Increase scan count from 2 to 4")
            print("   • Check for mechanical vibrations")
            print("   • Verify fluid stability")

        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        if 'state_machine' in locals() and hasattr(state_machine, 'stop'):
            state_machine.stop()
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        if 'state_machine' in locals() and hasattr(state_machine, 'stop'):
            state_machine.stop()


if __name__ == "__main__":
    test_peak_stability()
