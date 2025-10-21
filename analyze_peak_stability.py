"""
Extract Peak Tracking Data from Log File

Analyzes the log output to extract lambda values and calculate stability metrics.
"""

import re
from pathlib import Path
from datetime import datetime
import numpy as np


def analyze_log_file(log_path: Path):
    """Analyze log file for peak tracking performance."""

    print("\n" + "="*70)
    print("PEAK TRACKING LOG ANALYSIS")
    print("="*70)
    print(f"Log file: {log_path}")
    print("="*70 + "\n")

    # Data storage
    data = {
        'a': [],
        'b': [],
        'c': [],
        'd': []
    }

    # Pattern to match lambda values
    # Looking for lines like: "Channel A: λ = 628.1234 nm"
    pattern = re.compile(r'Channel ([A-D]):.*?λ\s*=\s*(\d+\.\d+)\s*nm', re.IGNORECASE)

    # Read log file
    with open(log_path, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                channel = match.group(1).lower()
                lambda_val = float(match.group(2))
                data[channel].append(lambda_val)

    # Analyze data
    if all(len(data[ch]) == 0 for ch in ['a', 'b', 'c', 'd']):
        print("❌ No lambda data found in log file")
        print("\nTip: Make sure INFO level logging is enabled")
        return

    print("Data collection summary:")
    for ch in ['a', 'b', 'c', 'd']:
        print(f"  Channel {ch.upper()}: {len(data[ch])} samples")
    print()

    # Calculate statistics
    print("="*70)
    print("RESULTS - PEAK TRACKING STABILITY")
    print("="*70 + "\n")

    stats = {}
    for ch in ['a', 'b', 'c', 'd']:
        if len(data[ch]) > 10:  # Need at least 10 samples
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
            print(f"  Samples:      {stats[ch]['count']}")
            print(f"  Mean:         {stats[ch]['mean']:.4f} nm")
            print(f"  Min:          {stats[ch]['min']:.4f} nm")
            print(f"  Max:          {stats[ch]['max']:.4f} nm")
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

            print(f"  Std Dev:      {stats[ch]['std']:.4f} nm")
            print(f"  SNR:          {stats[ch]['snr']:.1f}")
            print()
        else:
            print(f"Channel {ch.upper()}: ⚠️ Insufficient data ({len(data[ch])} samples)")
            print()

    # Overall assessment
    if stats:
        print("="*70)
        print("OVERALL ASSESSMENT")
        print("="*70 + "\n")

        avg_p2p = np.mean([stats[ch]['p2p'] for ch in stats.keys()])
        avg_snr = np.mean([stats[ch]['snr'] for ch in stats.keys()])

        print(f"Average Peak-to-Peak: {avg_p2p:.4f} nm")
        print(f"Average SNR:          {avg_snr:.1f}")
        print()

        if avg_p2p < 0.1:
            print("🎉 EXCELLENT performance! Peak tracking is very stable.")
            print("   Current settings (LED delay: 3ms, scans: 2) are optimal.")
        elif avg_p2p < 0.2:
            print("✅ GOOD performance. Peak tracking is stable.")
            print("   Current settings are working well.")
        elif avg_p2p < 0.5:
            print("⚠️  ACCEPTABLE performance. Some noise present.")
            print("   Consider:")
            print("   • Increasing LED delay from 3ms to 6ms (2× buffer)")
            print("   • Keeping scan count at 2 or increasing to 4")
        else:
            print("❌ POOR performance. High variation detected.")
            print("   Recommended actions:")
            print("   • Increase LED delay from 3ms to 6ms (2× buffer)")
            print("   • Increase scan count from 2 to 4")
            print("   • Check for mechanical vibrations")
            print("   • Verify fluid stability")

        print("\n" + "="*70)


if __name__ == "__main__":
    # Find most recent log file
    log_dir = Path(__file__).parent / "logs"

    if not log_dir.exists():
        print(f"❌ Log directory not found: {log_dir}")
        print("\nTip: Run the app first to generate logs")
    else:
        # Get most recent log file
        log_files = sorted(log_dir.glob("*.log"))
        if log_files:
            latest_log = log_files[-1]
            analyze_log_file(latest_log)
        else:
            print(f"❌ No log files found in: {log_dir}")
            print("\nTip: Run the app first to generate logs")
