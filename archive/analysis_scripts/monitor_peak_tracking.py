"""
Peak Tracking Performance Monitor

Monitors the live app and extracts peak tracking stability data.
Run this while the main app is running.
"""

import time
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
import csv

# Add project root
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

print("\n" + "="*70)
print("PEAK TRACKING PERFORMANCE MONITOR")
print("="*70)
print("This script monitors peak tracking stability by analyzing log files.")
print("Please run the main app (python run_app.py) and let it run for 2 minutes.")
print("="*70 + "\n")

# Wait for user to start the app
input("Press ENTER when the app is running and acquiring data...")

print("\n⏱️  Starting 2-minute data collection from logs...")
print("Monitor will sample log file every second for 120 seconds.\n")

# Find most recent log
log_dir = ROOT_DIR / "logs"
if not log_dir.exists():
    print(f"❌ Log directory not found: {log_dir}")
    sys.exit(1)

log_files = sorted(log_dir.glob("*.log"))
if not log_files:
    print(f"❌ No log files found in: {log_dir}")
    sys.exit(1)

latest_log = log_files[-1]
print(f"📁 Monitoring log file: {latest_log.name}\n")

# Data storage
data = {
    'a': [],
    'b': [],
    'c': [],
    'd': []
}
timestamps = []

# Pattern matching for lambda values in logs
import re
# Looking for timing cycle messages or lambda values
pattern = re.compile(r'Channel ([A-D]):.*?λ\s*=\s*(\d+\.\d+)\s*nm', re.IGNORECASE)

DURATION = 120  # 2 minutes
SAMPLE_INTERVAL = 1.0  # 1 Hz

start_time = time.time()
last_file_pos = 0
sample_count = 0

print("Collecting data...")
print("Progress: [" + " " * 50 + "] 0%", end="", flush=True)

try:
    while True:
        elapsed = time.time() - start_time

        if elapsed >= DURATION:
            break

        # Read new content from log file
        try:
            with open(latest_log, 'r') as f:
                f.seek(last_file_pos)
                new_content = f.read()
                last_file_pos = f.tell()

                # Extract lambda values from new content
                for match in pattern.finditer(new_content):
                    channel = match.group(1).lower()
                    lambda_val = float(match.group(2))

                    # Only add if we're in a sampling window
                    if time.time() - start_time >= sample_count * SAMPLE_INTERVAL:
                        data[channel].append(lambda_val)

        except Exception as e:
            pass  # Log file might be locked, try again

        # Update sample count
        current_sample = int(elapsed / SAMPLE_INTERVAL)
        if current_sample > sample_count:
            sample_count = current_sample
            timestamps.append(elapsed)

            # Update progress bar
            progress = int((elapsed / DURATION) * 50)
            percent = int((elapsed / DURATION) * 100)
            bar = "█" * progress + " " * (50 - progress)
            eta = int(DURATION - elapsed)
            print(f"\rProgress: [{bar}] {percent}% | ETA: {eta}s   ", end="", flush=True)

        time.sleep(0.1)  # Small sleep

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user")
    elapsed = time.time() - start_time

print("\n\n" + "="*70)
print("DATA COLLECTION COMPLETE")
print("="*70)
print(f"Duration: {elapsed:.1f} seconds")
print("="*70 + "\n")

# Analyze data
print("\n" + "="*70)
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

if not stats:
    print("❌ NO DATA COLLECTED")
    print("\nPossible issues:")
    print("• Main app not running")
    print("• Log level not showing lambda values")
    print("• App not in measurement mode")
    sys.exit(1)

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
print("TEST COMPLETE")
print("="*70 + "\n")
