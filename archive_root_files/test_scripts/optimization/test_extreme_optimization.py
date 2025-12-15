"""Final optimization push - test every possible combination

Test matrix:
- Pipelines: Fourier, Direct, Adaptive
- Batch sizes: 2, 3, 4, 5
- Post-Savgol windows: 3, 5, 7, 9, 11
- Kalman variants: different process/measurement variances
- Hybrid: Batch → Savgol → Kalman
- Triple smoothing: Batch → Savgol → Exponential
"""

import os
import sys

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.pipelines.adaptive_multifeature_pipeline import AdaptiveMultiFeaturePipeline
from utils.pipelines.direct_argmin_pipeline import DirectArgminPipeline
from utils.pipelines.fourier_pipeline import FourierPipeline

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
        return None
    df = pd.read_csv(baseline_file)
    return df["channel_a"].values


def detect_wavelengths(wavelength_data, pipeline_class):
    pipeline = pipeline_class()
    detected = []

    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)

        if detected_wl is None:
            detected.append(np.nan)
        # Handle tuple return (Adaptive pipeline)
        elif isinstance(detected_wl, tuple):
            detected.append(float(detected_wl[0]))
        else:
            detected.append(float(detected_wl))

    return np.array(detected, dtype=float)[~np.isnan(np.array(detected, dtype=float))]


def batch_process(data, batch_size, method="mean"):
    """Batch processing with different aggregation methods"""
    result = []
    for i in range(0, len(data) - batch_size + 1, batch_size):
        batch = data[i : i + batch_size]
        if method == "mean":
            result.append(np.mean(batch))
        elif method == "median":
            result.append(np.median(batch))
        elif method == "trimmed_mean":
            sorted_batch = np.sort(batch)
            # Remove 20% from each end
            trim = max(1, int(len(batch) * 0.2))
            result.append(np.mean(sorted_batch[trim:-trim]))
        elif method == "weighted":
            # Linear weights favoring recent
            weights = np.linspace(0.5, 1.5, len(batch))
            weights /= weights.sum()
            result.append(np.average(batch, weights=weights))
    return np.array(result)


def apply_savgol(data, window, poly=2):
    """Apply Savgol if enough points"""
    if len(data) >= window:
        return savgol_filter(data, window_length=window, polyorder=poly)
    return data


def kalman_filter(data, process_var, measurement_var):
    """Kalman filter implementation"""
    estimate = data[0]
    estimate_error = 1.0
    result = []

    for measurement in data:
        prediction = estimate
        prediction_error = estimate_error + process_var
        kalman_gain = prediction_error / (prediction_error + measurement_var)
        estimate = prediction + kalman_gain * (measurement - prediction)
        estimate_error = (1 - kalman_gain) * prediction_error
        result.append(estimate)

    return np.array(result)


def exponential_smooth(data, alpha):
    """Exponential smoothing"""
    result = [data[0]]
    for i in range(1, len(data)):
        result.append(alpha * data[i] + (1 - alpha) * result[-1])
    return np.array(result)


def calculate_stats(data, name):
    if len(data) == 0:
        return None
    valid = data[~np.isnan(data)]
    if len(valid) < 5:  # Need minimum points
        return None
    return {
        "name": name,
        "points": len(valid),
        "p2p_pm": np.ptp(valid) * 1000,
        "std_pm": np.std(valid) * 1000,
    }


def main():
    print("\n" + "=" * 80)
    print("🚀 EXTREME OPTIMIZATION - TESTING ALL COMBINATIONS")
    print("=" * 80)

    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return

    print(f"✅ Loaded {len(wavelength_data)} baseline points")
    print(f"📊 Raw: P2P={np.ptp(wavelength_data)*1000:.3f} pm\n")

    # Test pipelines
    pipelines = [
        ("Fourier", FourierPipeline),
        ("Direct", DirectArgminPipeline),
        ("Adaptive", AdaptiveMultiFeaturePipeline),
    ]

    all_results = []

    for pipeline_name, pipeline_class in pipelines:
        print(f"Testing {pipeline_name} pipeline...")

        try:
            detected = detect_wavelengths(wavelength_data, pipeline_class)
            print(f"  ✓ Detected {len(detected)} wavelengths")

            # Raw
            all_results.append(calculate_stats(detected, f"{pipeline_name}"))

            # Batch sizes
            for batch_size in [2, 3, 4, 5]:
                # Batch methods
                for batch_method in ["mean", "median", "weighted"]:
                    batched = batch_process(detected, batch_size, batch_method)

                    # Just batched
                    all_results.append(
                        calculate_stats(
                            batched,
                            f"{pipeline_name}+Batch{batch_size}_{batch_method}",
                        ),
                    )

                    # Batch + Savgol
                    for savgol_win in [3, 5, 7, 9, 11]:
                        if len(batched) >= savgol_win:
                            smoothed = apply_savgol(batched, savgol_win)
                            all_results.append(
                                calculate_stats(
                                    smoothed,
                                    f"{pipeline_name}+B{batch_size}_{batch_method}+SG{savgol_win}",
                                ),
                            )

                            # Triple: Batch + Savgol + Exponential
                            for alpha in [0.1, 0.2, 0.3]:
                                triple = exponential_smooth(smoothed, alpha)
                                all_results.append(
                                    calculate_stats(
                                        triple,
                                        f"{pipeline_name}+B{batch_size}+SG{savgol_win}+Exp{alpha}",
                                    ),
                                )

            # Kalman variants on raw
            for pv, mv in [(1e-6, 1e-4), (1e-6, 5e-5), (5e-7, 1e-4), (1e-7, 5e-5)]:
                kalman = kalman_filter(detected, pv, mv)
                all_results.append(
                    calculate_stats(
                        kalman,
                        f"{pipeline_name}+Kalman(pv={pv:.0e},mv={mv:.0e})",
                    ),
                )

            # Hybrid: Savgol then Kalman
            for savgol_win in [7, 9, 11]:
                if len(detected) >= savgol_win:
                    sg = apply_savgol(detected, savgol_win)
                    for pv, mv in [(1e-6, 1e-4), (5e-7, 5e-5)]:
                        kalman = kalman_filter(sg, pv, mv)
                        all_results.append(
                            calculate_stats(
                                kalman,
                                f"{pipeline_name}+SG{savgol_win}+Kalman",
                            ),
                        )

        except Exception as e:
            print(f"  ✗ Error: {e}")

    # Filter None results
    all_results = [r for r in all_results if r is not None]

    # Sort and display
    print(f"\n{'='*80}")
    print(f"🏆 TOP 20 CONFIGURATIONS (from {len(all_results)} tested)")
    print("=" * 80)

    df = pd.DataFrame(all_results)
    df_sorted = df.sort_values("p2p_pm")

    print("\nRank  P2P (pm)  Std (pm)  Points  Configuration")
    print("-" * 80)
    for idx, (i, row) in enumerate(df_sorted.head(20).iterrows(), 1):
        print(
            f"{idx:3d}.  {row['p2p_pm']:7.3f}  {row['std_pm']:7.3f}  {row['points']:4d}   {row['name']}",
        )

    # Best overall
    best = df_sorted.iloc[0]
    raw_fourier = df[df["name"] == "Fourier"].iloc[0]

    print(f"\n{'='*80}")
    print("🥇 ABSOLUTE BEST")
    print("=" * 80)
    print(f"Configuration: {best['name']}")
    print(f"Peak-to-Peak:  {best['p2p_pm']:.3f} pm")
    print(f"Std Dev:       {best['std_pm']:.3f} pm")
    print(f"Output Points: {int(best['points'])}")
    print(
        f"\nImprovement: {(raw_fourier['p2p_pm']-best['p2p_pm'])/raw_fourier['p2p_pm']*100:.1f}%",
    )
    print(f"Reduction:   {raw_fourier['p2p_pm']/best['p2p_pm']:.1f}x")

    # Best per pipeline
    print(f"\n{'='*80}")
    print("📊 BEST PER PIPELINE")
    print("=" * 80)

    for pipeline_name in ["Fourier", "Direct", "Adaptive"]:
        pipeline_results = df_sorted[df_sorted["name"].str.startswith(pipeline_name)]
        if len(pipeline_results) > 0:
            best_pipeline = pipeline_results.iloc[0]
            print(f"\n{pipeline_name}:")
            print(f"  {best_pipeline['name']}")
            print(f"  P2P: {best_pipeline['p2p_pm']:.3f} pm")

    # Save
    df_sorted.to_csv("extreme_optimization_results.csv", index=False)
    print("\n💾 Full results saved to: extreme_optimization_results.csv")
    print(f"   Total configurations tested: {len(all_results)}")


if __name__ == "__main__":
    main()
