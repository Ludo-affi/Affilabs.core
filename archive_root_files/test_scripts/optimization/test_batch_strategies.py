"""Advanced batch strategies within batch=12 constraint (3 points per channel)

Test additional methods:
1. Weighted moving average (exponential decay)
2. Trimmed mean (remove outliers)
3. Winsorized mean (cap outliers)
4. Different batch sizes (overlapping vs non-overlapping)
5. Hybrid: Batch + small post-Savgol
6. Adaptive batch sizing based on variance
7. Kalman-like filtering with batch updates
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.pipelines.fourier_pipeline import FourierPipeline

# SPR simulation parameters
SPR_CENTER = 646.5
SPR_WIDTH = 10.0
WAVELENGTH_RANGE = (560, 720)
NUM_PIXELS = 3648


def create_mock_spectrum(wavelength_nm):
    wavelengths = np.linspace(WAVELENGTH_RANGE[0], WAVELENGTH_RANGE[1], NUM_PIXELS)
    width = SPR_WIDTH / 2.355
    baseline = 90.0
    depth = 60.0
    transmission = baseline - depth / (1 + ((wavelengths - wavelength_nm) / width) ** 2)
    return transmission, wavelengths


def load_baseline_data():
    baseline_file = "src/baseline_data/baseline_wavelengths_20251127_013519.csv"
    if not os.path.exists(baseline_file):
        print(f"❌ ERROR: Baseline file not found: {baseline_file}")
        return None

    df = pd.read_csv(baseline_file)
    wavelength_data = df["channel_a"].values
    timestamps = df["timestamp_a"].values
    duration = timestamps[-1] - timestamps[0]

    print(f"✅ Loaded {len(wavelength_data)} baseline data points")
    print(f"   Duration: {duration:.2f}s, Rate: {len(wavelength_data)/duration:.2f} Hz")

    return wavelength_data


def detect_wavelengths(wavelength_data, pipeline_class):
    pipeline = pipeline_class()
    detected = []

    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)
        detected.append(float(detected_wl) if detected_wl is not None else np.nan)

    return np.array(detected, dtype=float)[~np.isnan(np.array(detected, dtype=float))]


def strategy_weighted_mean(data, batch_size=3):
    """Weighted mean with exponential decay (newer = higher weight)"""
    result = []
    weights = np.array([0.2, 0.3, 0.5])  # Favor most recent

    for i in range(0, len(data) - batch_size + 1, batch_size):
        batch = data[i : i + batch_size]
        result.append(np.average(batch, weights=weights))

    return np.array(result)


def strategy_trimmed_mean(data, batch_size=3):
    """Trimmed mean - remove extreme value (best for outlier rejection)"""
    result = []

    for i in range(0, len(data) - batch_size + 1, batch_size):
        batch = data[i : i + batch_size]
        # For 3 points, this removes highest and lowest, keeps middle
        sorted_batch = np.sort(batch)
        result.append(sorted_batch[1])  # Middle value

    return np.array(result)


def strategy_winsorized_mean(data, batch_size=3):
    """Winsorized mean - cap extreme values"""
    result = []

    for i in range(0, len(data) - batch_size + 1, batch_size):
        batch = data[i : i + batch_size]
        sorted_batch = np.sort(batch)
        # Replace extremes with next value
        winsorized = np.array([sorted_batch[1], sorted_batch[1], sorted_batch[1]])
        result.append(np.mean(batch))  # Actually just use median for 3 points

    return np.array(result)


def strategy_overlapping_mean(data, batch_size=3, stride=1):
    """Overlapping batches - stride < batch_size"""
    result = []

    for i in range(0, len(data) - batch_size + 1, stride):
        batch = data[i : i + batch_size]
        result.append(np.mean(batch))

    return np.array(result)


def strategy_batch_then_savgol(data, batch_size=3, savgol_window=5):
    """First batch average, then small Savgol on batched output"""
    # Step 1: Batch mean
    batched = []
    for i in range(0, len(data) - batch_size + 1, batch_size):
        batch = data[i : i + batch_size]
        batched.append(np.mean(batch))

    batched = np.array(batched)

    # Step 2: Apply small Savgol if enough points
    if len(batched) >= savgol_window:
        return savgol_filter(batched, window_length=savgol_window, polyorder=2)
    return batched


def strategy_adaptive_batch(data, batch_size=3, var_threshold=1e-6):
    """Adaptive batch size based on local variance"""
    result = []
    i = 0

    while i < len(data) - batch_size + 1:
        batch = data[i : i + batch_size]
        variance = np.var(batch)

        if variance < var_threshold:
            # Low variance - can use larger batch
            extended_batch = data[i : min(i + batch_size + 2, len(data))]
            result.append(np.mean(extended_batch))
            i += len(extended_batch)
        else:
            # High variance - use smaller batch or median
            result.append(np.median(batch))
            i += batch_size

    return np.array(result)


def strategy_exponential_smoothing(data, alpha=0.3):
    """Exponential smoothing (single exponential)"""
    result = [data[0]]

    for i in range(1, len(data)):
        smoothed = alpha * data[i] + (1 - alpha) * result[-1]
        result.append(smoothed)

    return np.array(result)


def strategy_double_exponential(data, alpha=0.3, beta=0.3):
    """Double exponential smoothing (Holt's method)"""
    result = [data[0]]
    trend = [data[1] - data[0]]

    for i in range(1, len(data)):
        level = alpha * data[i] + (1 - alpha) * (result[-1] + trend[-1])
        trend_new = beta * (level - result[-1]) + (1 - beta) * trend[-1]
        result.append(level)
        trend.append(trend_new)

    return np.array(result)


def strategy_kalman_simple(data, process_variance=1e-5, measurement_variance=1e-4):
    """Simple 1D Kalman filter"""
    # Initialize
    estimate = data[0]
    estimate_error = 1.0

    result = []

    for measurement in data:
        # Prediction
        prediction = estimate
        prediction_error = estimate_error + process_variance

        # Update
        kalman_gain = prediction_error / (prediction_error + measurement_variance)
        estimate = prediction + kalman_gain * (measurement - prediction)
        estimate_error = (1 - kalman_gain) * prediction_error

        result.append(estimate)

    return np.array(result)


def calculate_stats(data, name):
    if len(data) == 0 or np.all(np.isnan(data)):
        return None

    valid_data = data[~np.isnan(data)]
    p2p = np.ptp(valid_data)
    std = np.std(valid_data)

    return {
        "name": name,
        "points": len(valid_data),
        "peak_to_peak_pm": p2p * 1000,
        "std_pm": std * 1000,
        "mean_nm": np.mean(valid_data),
    }


def main():
    print("\n" + "=" * 80)
    print("🔬 ADVANCED BATCH STRATEGIES TEST")
    print("=" * 80)

    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return

    print(
        f"\n📊 Raw Input: P2P={np.ptp(wavelength_data)*1000:.3f} pm, Std={np.std(wavelength_data)*1000:.3f} pm",
    )

    # Detect wavelengths
    print("\n🔍 Detecting wavelengths...")
    detected = detect_wavelengths(wavelength_data, FourierPipeline)
    print(f"✅ Detected {len(detected)} valid wavelengths")

    results = []

    # Baseline
    results.append(calculate_stats(detected, "Raw (No Processing)"))

    # Test all strategies
    print(f"\n{'='*80}")
    print("TESTING STRATEGIES")
    print("=" * 80)

    strategies = [
        ("Batch Mean (n=3)", lambda d: strategy_overlapping_mean(d, 3, 3)),
        ("Weighted Mean (0.2,0.3,0.5)", lambda d: strategy_weighted_mean(d, 3)),
        ("Trimmed Mean (keep middle)", lambda d: strategy_trimmed_mean(d, 3)),
        ("Overlapping Mean (stride=1)", lambda d: strategy_overlapping_mean(d, 3, 1)),
        ("Overlapping Mean (stride=2)", lambda d: strategy_overlapping_mean(d, 3, 2)),
        ("Batch → Savgol(5)", lambda d: strategy_batch_then_savgol(d, 3, 5)),
        ("Batch → Savgol(7)", lambda d: strategy_batch_then_savgol(d, 3, 7)),
        ("Exponential α=0.2", lambda d: strategy_exponential_smoothing(d, 0.2)),
        ("Exponential α=0.3", lambda d: strategy_exponential_smoothing(d, 0.3)),
        ("Exponential α=0.5", lambda d: strategy_exponential_smoothing(d, 0.5)),
        ("Double Exponential", lambda d: strategy_double_exponential(d, 0.3, 0.3)),
        ("Kalman Filter (simple)", lambda d: strategy_kalman_simple(d, 1e-5, 3e-4)),
        ("Kalman Filter (tight)", lambda d: strategy_kalman_simple(d, 1e-6, 1e-4)),
        (
            "Savgol (w=11, p=2)",
            lambda d: savgol_filter(d, 11, 2) if len(d) >= 11 else d,
        ),
    ]

    for name, strategy_func in strategies:
        try:
            result_data = strategy_func(detected)
            stats = calculate_stats(result_data, name)
            if stats:
                results.append(stats)
                print(
                    f"✓ {name:35s} P2P={stats['peak_to_peak_pm']:7.3f} pm, Std={stats['std_pm']:6.3f} pm, N={stats['points']:3d}",
                )
        except Exception as e:
            print(f"✗ {name:35s} ERROR: {e}")

    # Summary
    print(f"\n{'='*80}")
    print("📊 RANKING (Best to Worst)")
    print("=" * 80)

    df = pd.DataFrame(results)
    df_sorted = df.sort_values("peak_to_peak_pm")

    print(
        "\n"
        + df_sorted[["name", "peak_to_peak_pm", "std_pm", "points"]].to_string(
            index=False,
        ),
    )

    # Best method
    best = df_sorted.iloc[0]
    raw = df[df["name"] == "Raw (No Processing)"].iloc[0]

    print(f"\n{'='*80}")
    print("🏆 WINNER")
    print("=" * 80)
    print(f"Method: {best['name']}")
    print(f"Peak-to-Peak: {best['peak_to_peak_pm']:.3f} pm")
    print(f"Std Dev:      {best['std_pm']:.3f} pm")
    print(f"Points:       {int(best['points'])}")
    print(
        f"\nImprovement: {(raw['peak_to_peak_pm']-best['peak_to_peak_pm'])/raw['peak_to_peak_pm']*100:.1f}%",
    )
    print(f"Reduction:   {raw['peak_to_peak_pm']/best['peak_to_peak_pm']:.1f}x")

    # Top 3 practical methods (exclude Savgol w=11 as baseline)
    print(f"\n{'='*80}")
    print("🎯 TOP 3 PRACTICAL METHODS (excluding post-Savgol)")
    print("=" * 80)

    practical = df_sorted[~df_sorted["name"].str.contains("Savgol \\(w=11")]
    for i, row in practical.head(3).iterrows():
        print(
            f"{practical.index.get_loc(i)+1}. {row['name']:35s} {row['peak_to_peak_pm']:7.3f} pm",
        )

    # Save
    df.to_csv("batch_strategies_results.csv", index=False)
    print("\n💾 Results saved to: batch_strategies_results.csv")


if __name__ == "__main__":
    main()
