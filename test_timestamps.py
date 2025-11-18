"""Quick test to verify timestamps are now correct per channel."""
import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Old software')

import time
from utils.channel_manager import ChannelManager
from settings import CH_LIST

print("Testing per-channel timestamp tracking...\n")

mgr = ChannelManager()

# Simulate 3 acquisition cycles
for cycle in range(3):
    print(f"Cycle {cycle + 1}:")
    cycle_time = time.perf_counter()

    # Process each channel (as main.py does)
    for ch in CH_LIST:
        wavelength = 1550.0 + cycle * 0.1  # Same wavelength this cycle
        timestamp = cycle_time  # Same timestamp this cycle

        mgr.add_data_point(
            channel=ch,
            wavelength=wavelength,
            timestamp=timestamp,
            filtered_value=wavelength,
        )
        print(f"  Ch {ch}: wavelength={wavelength:.3f}, timestamp={timestamp:.6f}")

    # Increment buffer after all channels
    mgr.increment_buffer_index()
    print()

# Check that all channels have the same timestamps
print("Verification:")
data = mgr.get_sensorgram_data()
for ch in CH_LIST:
    times = data[ch]['times']
    values = data[ch]['values']
    print(f"Channel {ch}: {len(times)} points")
    for i in range(len(times)):
        print(f"  [{i}] time={times[i]:.6f}, value={values[i]:.3f}")

print("\n✅ Test complete - all channels should have SAME timestamps per cycle!")
