import time
import sys
sys.path.insert(0, r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\test\ezControl-AI")
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

d = PhasePhotonics()
d.open()

# Set low integration time for clear results
d.set_integration(0.010)  # 10ms
print(f"Integration time: {d._integration_time * 1000:.1f}ms\n")

for num_scans in [1, 3, 5, 9]:
    print(f"Testing {num_scans} scans...")
    d.set_averaging(num_scans)
    time.sleep(0.1)
    
    times = []
    for _ in range(5):
        start = time.perf_counter()
        spectrum = d.read_intensity()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    predicted = (num_scans * 10) + 25  # 10ms integration + 25ms USB
    print(f"  Actual: {avg_time:.1f}ms, Predicted: {predicted}ms\n")

d.set_averaging(1)
d.close()
