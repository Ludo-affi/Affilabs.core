"""Performance Benchmark: np.append vs TimeSeriesBuffer vs pandas operations

This benchmark measures the performance improvements achieved by replacing
np.append() operations with pandas-backed batched operations.

Tests:
1. Data acquisition simulation (repeated appends)
2. CSV import operations
3. Data filtering operations
4. CSV export operations

Author: AI Assistant
Date: November 19, 2025
"""

import time
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

# Import our optimized classes
from utils.time_series_buffer import TimeSeriesBuffer


def benchmark_data_append(num_points: int) -> dict[str, float]:
    """Benchmark data append operations: np.append vs TimeSeriesBuffer.

    Args:
        num_points: Number of data points to append

    Returns:
        Dictionary with timing results
    """
    print(f"\n{'='*80}")
    print(f"Benchmark 1: Data Append Operations ({num_points:,} points)")
    print(f"{'='*80}")

    # Method 1: np.append (O(n²) quadratic time)
    start = time.perf_counter()
    np_times = np.array([])
    np_values = np.array([])
    for i in range(num_points):
        np_times = np.append(np_times, i * 0.1)
        np_values = np.append(np_values, np.sin(i * 0.01) + np.random.normal(0, 0.1))
    np_time = time.perf_counter() - start

    # Method 2: TimeSeriesBuffer with batched operations (O(n) linear time)
    start = time.perf_counter()
    buffer = TimeSeriesBuffer(channel="test", batch_size=100)
    for i in range(num_points):
        buffer.append(i * 0.1, np.sin(i * 0.01) + np.random.normal(0, 0.1))
    ts_time = time.perf_counter() - start

    # Method 3: List append then convert (baseline reference)
    start = time.perf_counter()
    list_times = []
    list_values = []
    for i in range(num_points):
        list_times.append(i * 0.1)
        list_values.append(np.sin(i * 0.01) + np.random.normal(0, 0.1))
    list_times = np.array(list_times)
    list_values = np.array(list_values)
    list_time = time.perf_counter() - start

    # Calculate speedups
    speedup_vs_np = np_time / ts_time
    speedup_vs_list = list_time / ts_time

    print(f"  np.append():       {np_time:.4f}s")
    print(f"  TimeSeriesBuffer:  {ts_time:.4f}s  (⚡ {speedup_vs_np:.1f}× faster than np.append)")
    print(f"  list→array:        {list_time:.4f}s  (⚡ {speedup_vs_list:.1f}× faster than list)")

    return {
        "num_points": num_points,
        "np_append_time": np_time,
        "timeseries_buffer_time": ts_time,
        "list_append_time": list_time,
        "speedup_vs_np": speedup_vs_np,
        "speedup_vs_list": speedup_vs_list,
    }


def benchmark_csv_import(num_rows: int) -> dict[str, float]:
    """Benchmark CSV import: row-by-row vs pandas.read_csv().

    Args:
        num_rows: Number of rows in test CSV file

    Returns:
        Dictionary with timing results
    """
    print(f"\n{'='*80}")
    print(f"Benchmark 2: CSV Import Operations ({num_rows:,} rows)")
    print(f"{'='*80}")

    # Create test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        csv_path = Path(f.name)
        # Write header
        f.write("Time_A\tChannel_A\tTime_B\tChannel_B\tTime_C\tChannel_C\tTime_D\tChannel_D\n")
        # Write data
        for i in range(num_rows):
            t = i * 0.1
            f.write(f"{t}\t{np.sin(t)}\t{t}\t{np.cos(t)}\t{t}\t{np.sin(2*t)}\t{t}\t{np.cos(2*t)}\n")

    try:
        # Method 1: Row-by-row with list append (old method)
        start = time.perf_counter()
        data_old = {"a": [], "b": [], "c": [], "d": []}
        with open(csv_path, 'r') as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().split('\t')
                data_old["a"].append(float(parts[1]))
                data_old["b"].append(float(parts[3]))
                data_old["c"].append(float(parts[5]))
                data_old["d"].append(float(parts[7]))
        # Convert to numpy
        for ch in data_old:
            data_old[ch] = np.array(data_old[ch])
        old_time = time.perf_counter() - start

        # Method 2: pandas read_csv with vectorized operations (new method)
        start = time.perf_counter()
        df = pd.read_csv(csv_path, sep='\t')
        data_new = {
            "a": df["Channel_A"].to_numpy(),
            "b": df["Channel_B"].to_numpy(),
            "c": df["Channel_C"].to_numpy(),
            "d": df["Channel_D"].to_numpy(),
        }
        new_time = time.perf_counter() - start

        # Calculate speedup
        speedup = old_time / new_time

        print(f"  Row-by-row import: {old_time:.4f}s")
        print(f"  pandas.read_csv(): {new_time:.4f}s  (⚡ {speedup:.1f}× faster)")

        return {
            "num_rows": num_rows,
            "row_by_row_time": old_time,
            "pandas_time": new_time,
            "speedup": speedup,
        }

    finally:
        # Clean up temp file
        csv_path.unlink()


def benchmark_filter_operations(num_points: int) -> dict[str, float]:
    """Benchmark filtering: loop-based vs pandas rolling windows.

    Args:
        num_points: Number of data points to filter

    Returns:
        Dictionary with timing results
    """
    print(f"\n{'='*80}")
    print(f"Benchmark 3: Filter Operations ({num_points:,} points)")
    print(f"{'='*80}")

    # Generate test data
    data = np.sin(np.linspace(0, 10, num_points)) + np.random.normal(0, 0.2, num_points)
    window = 5

    # Method 1: Loop-based median filter (old method)
    start = time.perf_counter()
    filtered_old = np.full_like(data, np.nan)
    half_window = window // 2
    for i in range(len(data)):
        start_idx = max(0, i - half_window)
        end_idx = min(len(data), i + half_window + 1)
        window_data = data[start_idx:end_idx]
        filtered_old[i] = np.nanmedian(window_data)
    old_time = time.perf_counter() - start

    # Method 2: pandas rolling window (new method)
    start = time.perf_counter()
    series = pd.Series(data)
    filtered_new = series.rolling(window=window, center=True, min_periods=1).median().to_numpy()
    new_time = time.perf_counter() - start

    # Calculate speedup
    speedup = old_time / new_time

    print(f"  Loop-based filter: {old_time:.4f}s")
    print(f"  pandas rolling():  {new_time:.4f}s  (⚡ {speedup:.1f}× faster)")

    return {
        "num_points": num_points,
        "loop_time": old_time,
        "pandas_time": new_time,
        "speedup": speedup,
    }


def benchmark_csv_export(num_rows: int) -> dict[str, float]:
    """Benchmark CSV export: row-by-row vs DataFrame.to_csv().

    Args:
        num_rows: Number of rows to export

    Returns:
        Dictionary with timing results
    """
    print(f"\n{'='*80}")
    print(f"Benchmark 4: CSV Export Operations ({num_rows:,} rows)")
    print(f"{'='*80}")

    # Generate test data
    data = {
        "Time_A": np.linspace(0, num_rows * 0.1, num_rows),
        "Signal_A": np.random.randn(num_rows),
        "Time_B": np.linspace(0, num_rows * 0.1, num_rows),
        "Signal_B": np.random.randn(num_rows),
        "Time_C": np.linspace(0, num_rows * 0.1, num_rows),
        "Signal_C": np.random.randn(num_rows),
        "Time_D": np.linspace(0, num_rows * 0.1, num_rows),
        "Signal_D": np.random.randn(num_rows),
    }

    # Method 1: Row-by-row CSV writing (old method)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        csv_path_old = Path(f.name)

    start = time.perf_counter()
    import csv
    with open(csv_path_old, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data.keys()), delimiter='\t')
        writer.writeheader()
        for i in range(num_rows):
            row_dict = {key: data[key][i] for key in data.keys()}
            writer.writerow(row_dict)
    old_time = time.perf_counter() - start

    # Method 2: pandas DataFrame.to_csv() (new method)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path_new = Path(f.name)

    start = time.perf_counter()
    df = pd.DataFrame(data)
    df.to_csv(csv_path_new, sep='\t', index=False)
    new_time = time.perf_counter() - start

    # Calculate speedup
    speedup = old_time / new_time

    print(f"  Row-by-row export: {old_time:.4f}s")
    print(f"  DataFrame.to_csv():{new_time:.4f}s  (⚡ {speedup:.1f}× faster)")

    # Clean up
    csv_path_old.unlink()
    csv_path_new.unlink()

    return {
        "num_rows": num_rows,
        "row_by_row_time": old_time,
        "pandas_time": new_time,
        "speedup": speedup,
    }


def run_full_benchmark():
    """Run complete performance benchmark suite."""
    print("\n" + "="*80)
    print("PANDAS OPTIMIZATION PERFORMANCE BENCHMARK")
    print("="*80)
    print(f"Testing np.append vs TimeSeriesBuffer vs pandas operations")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Test with different data sizes
    test_sizes = [1000, 5000, 10000]

    results = {
        "append": [],
        "import": [],
        "filter": [],
        "export": [],
    }

    for size in test_sizes:
        results["append"].append(benchmark_data_append(size))
        results["import"].append(benchmark_csv_import(size))
        results["filter"].append(benchmark_filter_operations(size))
        results["export"].append(benchmark_csv_export(size))

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    print("\n📊 Data Append Operations (np.append → TimeSeriesBuffer):")
    for r in results["append"]:
        print(f"  {r['num_points']:>6,} points: {r['speedup_vs_np']:>5.1f}× speedup")

    print("\n📊 CSV Import Operations (row-by-row → pandas.read_csv):")
    for r in results["import"]:
        print(f"  {r['num_rows']:>6,} rows:   {r['speedup']:>5.1f}× speedup")

    print("\n📊 Filter Operations (loops → pandas.rolling):")
    for r in results["filter"]:
        print(f"  {r['num_points']:>6,} points: {r['speedup']:>5.1f}× speedup")

    print("\n📊 CSV Export Operations (row-by-row → DataFrame.to_csv):")
    for r in results["export"]:
        print(f"  {r['num_rows']:>6,} rows:   {r['speedup']:>5.1f}× speedup")

    # Calculate average improvements
    avg_append_speedup = sum(r["speedup_vs_np"] for r in results["append"]) / len(results["append"])
    avg_import_speedup = sum(r["speedup"] for r in results["import"]) / len(results["import"])
    avg_filter_speedup = sum(r["speedup"] for r in results["filter"]) / len(results["filter"])
    avg_export_speedup = sum(r["speedup"] for r in results["export"]) / len(results["export"])

    print(f"\n{'='*80}")
    print("AVERAGE IMPROVEMENTS")
    print(f"{'='*80}")
    print(f"  Data Append:  {avg_append_speedup:.1f}× faster (np.append → TimeSeriesBuffer)")
    print(f"  CSV Import:   {avg_import_speedup:.1f}× faster (row-by-row → pandas)")
    print(f"  Filtering:    {avg_filter_speedup:.1f}× faster (loops → pandas.rolling)")
    print(f"  CSV Export:   {avg_export_speedup:.1f}× faster (row-by-row → DataFrame)")
    print(f"\n  🎯 Overall average: {(avg_append_speedup + avg_import_speedup + avg_filter_speedup + avg_export_speedup) / 4:.1f}× performance improvement")
    print(f"{'='*80}\n")

    return results


if __name__ == "__main__":
    results = run_full_benchmark()
