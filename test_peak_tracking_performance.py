"""
Peak Tracking Performance Test

Measures peak-to-peak variation per channel over 2 minutes to evaluate
the performance of the resonance peak tracking algorithm.

The test:
1. Runs live data acquisition for 2 minutes
2. Records all lambda values for each channel
3. Calculates peak-to-peak variation (max - min)
4. Calculates standard deviation
5. Reports statistics per channel

Usage:
    python test_peak_tracking_performance.py

Author: AI Assistant
Date: October 21, 2025
"""

import time
import numpy as np
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Python 3.9 compatibility: Mock Self type if not available
import typing
if not hasattr(typing, 'Self'):
    typing.Self = typing.TypeVar('Self')

from utils.logger import logger
from utils.spr_state_machine import SPRStateMachine
from settings import CH_LIST


class PeakTrackingTest:
    """Test to measure peak tracking performance over time."""

    def __init__(self, duration_seconds: int = 120):
        """Initialize the test.

        Args:
            duration_seconds: Test duration in seconds (default: 120 = 2 minutes)
        """
        self.duration = duration_seconds
        self.state_machine = None
        self.data_collected = {ch: [] for ch in CH_LIST}
        self.timestamps = {ch: [] for ch in CH_LIST}
        self.start_time = None

    def data_update_callback(self, data_dict):
        """Callback to collect data during acquisition.

        Args:
            data_dict: Dictionary containing lambda_values and lambda_times
        """
        try:
            # Extract lambda values and times for each channel
            lambda_values = data_dict.get('lambda_values', {})
            lambda_times = data_dict.get('lambda_times', {})

            for ch in CH_LIST:
                if ch in lambda_values and len(lambda_values[ch]) > 0:
                    # Get the most recent value (last in array)
                    latest_lambda = lambda_values[ch][-1]
                    latest_time = lambda_times[ch][-1] if ch in lambda_times and len(lambda_times[ch]) > 0 else 0

                    # Only collect valid (non-NaN) values
                    if not np.isnan(latest_lambda):
                        self.data_collected[ch].append(latest_lambda)
                        self.timestamps[ch].append(latest_time)

        except Exception as e:
            logger.error(f"Error in data callback: {e}")

    def run_test(self):
        """Run the 2-minute peak tracking test."""

        print("=" * 80)
        print("PEAK TRACKING PERFORMANCE TEST")
        print("=" * 80)
        print(f"Duration: {self.duration} seconds ({self.duration/60:.1f} minutes)")
        print(f"Channels: {', '.join(CH_LIST)}")
        print("=" * 80)
        print()

        # Initialize state machine
        logger.info("Initializing SPR system...")
        self.state_machine = SPRStateMachine()

        # Register data callback
        self.state_machine.data_acquisition.data_ready.connect(self.data_update_callback)

        # Start hardware discovery and calibration
        logger.info("Discovering hardware...")
        self.state_machine.discover_hardware()

        # Wait for discovery to complete
        time.sleep(3)

        # Start calibration
        logger.info("Starting calibration...")
        self.state_machine.start_calibration()

        # Wait for calibration to complete (max 60 seconds)
        calibration_timeout = 60
        calibration_start = time.time()
        while not self.state_machine.data_acquisition.calibrated:
            if time.time() - calibration_start > calibration_timeout:
                logger.error("Calibration timeout!")
                return False
            time.sleep(0.5)

        logger.info("✅ Calibration complete!")
        print("\n" + "=" * 80)
        print("STARTING DATA COLLECTION")
        print("=" * 80)

        # Start live mode
        self.state_machine.start_live_mode()
        self.start_time = time.time()

        # Collect data for specified duration
        try:
            while True:
                elapsed = time.time() - self.start_time

                # Print progress every 10 seconds
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    remaining = self.duration - elapsed
                    print(f"⏱️  Progress: {elapsed:.0f}s / {self.duration}s ({elapsed/self.duration*100:.0f}%) - "
                          f"Remaining: {remaining:.0f}s")

                    # Print current data counts
                    counts = {ch: len(self.data_collected[ch]) for ch in CH_LIST}
                    print(f"   Data points: {counts}")

                # Check if duration reached
                if elapsed >= self.duration:
                    break

                time.sleep(0.1)  # Small sleep to avoid busy loop

        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")

        # Stop live mode
        self.state_machine.stop_live_mode()

        # Analyze results
        self.analyze_results()

        return True

    def analyze_results(self):
        """Analyze collected data and print statistics."""

        print("\n" + "=" * 80)
        print("PEAK TRACKING PERFORMANCE RESULTS")
        print("=" * 80)
        print()

        results = {}

        for ch in CH_LIST:
            data = np.array(self.data_collected[ch])

            if len(data) == 0:
                print(f"Channel {ch.upper()}: ❌ NO DATA COLLECTED")
                continue

            # Calculate statistics
            mean_val = np.mean(data)
            std_val = np.std(data)
            min_val = np.min(data)
            max_val = np.max(data)
            peak_to_peak = max_val - min_val
            rms = np.sqrt(np.mean(data**2))

            # Store results
            results[ch] = {
                'count': len(data),
                'mean': mean_val,
                'std': std_val,
                'min': min_val,
                'max': max_val,
                'peak_to_peak': peak_to_peak,
                'rms': rms,
            }

            # Print results for this channel
            print(f"Channel {ch.upper()}:")
            print(f"  Data points collected: {len(data)}")
            print(f"  Mean wavelength: {mean_val:.4f} nm")
            print(f"  Standard deviation: {std_val:.6f} nm")
            print(f"  Minimum: {min_val:.4f} nm")
            print(f"  Maximum: {max_val:.4f} nm")
            print(f"  ⭐ PEAK-TO-PEAK: {peak_to_peak:.6f} nm ⭐")
            print(f"  RMS: {rms:.4f} nm")
            print()

        # Summary table
        print("=" * 80)
        print("SUMMARY TABLE")
        print("=" * 80)
        print(f"{'Channel':<10} {'Points':<10} {'Mean (nm)':<12} {'Std (nm)':<12} {'P-P (nm)':<12}")
        print("-" * 80)

        for ch in CH_LIST:
            if ch in results:
                r = results[ch]
                print(f"{ch.upper():<10} {r['count']:<10} {r['mean']:<12.4f} "
                      f"{r['std']:<12.6f} {r['peak_to_peak']:<12.6f}")

        print("=" * 80)
        print()

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = ROOT_DIR / "generated-files" / f"peak_tracking_test_{timestamp}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            f.write("PEAK TRACKING PERFORMANCE TEST RESULTS\n")
            f.write("=" * 80 + "\n")
            f.write(f"Test duration: {self.duration} seconds\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("\n")

            for ch in CH_LIST:
                if ch in results:
                    r = results[ch]
                    f.write(f"Channel {ch.upper()}:\n")
                    f.write(f"  Data points: {r['count']}\n")
                    f.write(f"  Mean: {r['mean']:.4f} nm\n")
                    f.write(f"  Std Dev: {r['std']:.6f} nm\n")
                    f.write(f"  Min: {r['min']:.4f} nm\n")
                    f.write(f"  Max: {r['max']:.4f} nm\n")
                    f.write(f"  Peak-to-Peak: {r['peak_to_peak']:.6f} nm\n")
                    f.write(f"  RMS: {r['rms']:.4f} nm\n")
                    f.write("\n")

        print(f"📁 Results saved to: {output_file}")
        print()

        return results

    def cleanup(self):
        """Clean up resources."""
        if self.state_machine:
            try:
                self.state_machine.stop_live_mode()
                self.state_machine.shutdown()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    test = PeakTrackingTest(duration_seconds=120)  # 2 minutes

    try:
        success = test.run_test()
        if not success:
            print("❌ Test failed!")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)
        print(f"❌ Test error: {e}")
        return 1
    finally:
        test.cleanup()

    print("✅ Test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
