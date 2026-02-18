"""
Benchmark: Measure current SlopeEstimator performance
This is a SAFE, READ-ONLY test that does NOT modify any code.
"""

import timeit
from affilabs.convergence.estimators import SlopeEstimator

def benchmark_slope_estimation():
    """Simulate real cycle analysis with 10k data points"""
    estimator = SlopeEstimator()
    
    # Record 10,000 points (typical cycle)
    for i in range(10000):
        time_val = float(i)
        signal_val = 100.0 + i * 0.1 + (i % 100) * 0.01  # Realistic noisy signal
        estimator.record('cycle_1', time_val, signal_val)
    
    # Calculate slope
    slope = estimator.estimate('cycle_1')
    return slope

def main():
    print("=" * 60)
    print("Convergence Engine Benchmark")
    print("=" * 60)
    print()
    print("SlopeEstimator (10k data points, 10 iterations)")
    print()
    
    # Warm up
    benchmark_slope_estimation()
    
    # Main benchmark
    total_time = timeit.timeit(benchmark_slope_estimation, number=10)
    avg_time_ms = (total_time / 10) * 1000
    
    print(f"Results: {total_time:.2f}s total / {avg_time_ms:.2f}ms avg")
    print()
    
    if avg_time_ms < 5:
        print("✅ FAST (< 5ms) - No optimization needed")
    elif avg_time_ms < 20:
        print("✅ GOOD (< 20ms) - C++ optional")
    elif avg_time_ms < 100:
        print("⚠️  SLOW (< 100ms) - C++ recommended")
    else:
        print("❌ VERY SLOW (> 100ms) - C++ optimization needed")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
