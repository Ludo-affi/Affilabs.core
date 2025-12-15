"""Test all pipeline methods on baseline data

SIMPLIFIED VERSION: Tests how each pipeline processes the raw baseline wavelength data.

Since we have already computed wavelengths from spectra in the baseline data,
this script applies the batch processing and filtering techniques to see
how each method reduces the noise.

Usage:
    python test_all_pipelines_baseline.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import pipeline classes
from utils.pipelines.adaptive_multifeature_pipeline import AdaptiveMultiFeaturePipeline
from utils.pipelines.batch_savgol_pipeline import BatchSavgolPipeline
from utils.pipelines.direct_argmin_pipeline import DirectArgminPipeline
from utils.pipelines.fourier_pipeline import FourierPipeline

# Constants for SPR detection range
SPR_PEAK_MIN = 560.0  # nm
SPR_PEAK_MAX = 720.0  # nm


def load_baseline_data():
    """Load the recovered baseline data"""
    # Use the latest baseline data file
    baseline_file = Path("src/baseline_data/baseline_wavelengths_20251127_013519.csv")

    if not baseline_file.exists():
        print(f"❌ ERROR: {baseline_file} not found!")
        print("   Trying fallback file...")
        baseline_file = Path(
            "src/baseline_data/baseline_wavelengths_20251126_223040.csv",
        )
        if not baseline_file.exists():
            print("❌ ERROR: Fallback file also not found!")
            return None

    df = pd.read_csv(baseline_file)

    # Extract channel A data (first channel)
    wavelength_data = df["channel_a"].values
    timestamp_data = df["timestamp_a"].values

    # Convert timestamps to relative time (seconds from start)
    timestamp_data = timestamp_data - timestamp_data[0]

    print(f"✅ Loaded {len(wavelength_data)} baseline data points (Channel A)")
    print(f"   Time range: {timestamp_data.min():.2f}s to {timestamp_data.max():.2f}s")
    print(f"   Duration: {timestamp_data.max() - timestamp_data.min():.2f}s")

    return wavelength_data


def create_mock_spectrum(wavelength_nm):
    """Create a mock transmission spectrum with SPR dip at given wavelength

    This simulates what the transmission spectrum would look like for a given
    resonance wavelength.
    """
    # Generate wavelength array (same as detector)
    wavelengths = np.linspace(SPR_PEAK_MIN, SPR_PEAK_MAX, 3648)

    # Create SPR dip (Lorentzian shape)
    width = 15.0  # nm, typical SPR width
    baseline = 90.0  # % transmission baseline
    depth = 60.0  # % transmission dip depth

    transmission = baseline - depth / (1 + ((wavelengths - wavelength_nm) / width) ** 2)

    return transmission, wavelengths


def test_pipeline(
    pipeline_name,
    pipeline_class,
    wavelength_data,
    config=None,
    batch_size=20,
    window_length=11,
    polyorder=2,
):
    """Test a single pipeline on the baseline data with BATCH POST-PROCESSING

    Fair comparison: All pipelines get the same batch smoothing treatment
    1. Process individual points through the pipeline
    2. Apply Savitzky-Golay smoothing to the resulting wavelength time series

    Args:
        pipeline_name: Name of the pipeline
        pipeline_class: Pipeline class to instantiate
        wavelength_data: Array of true wavelengths (nm)
        config: Optional configuration dict
        batch_size: Not used, kept for compatibility
        window_length: Savgol window length for post-processing
        polyorder: Savgol polynomial order for post-processing

    Returns:
        dict with results

    """
    print(f"\n{'='*80}")
    print(f"Testing: {pipeline_name}")
    print(f"{'='*80}")

    # Create pipeline instance
    pipeline = pipeline_class(config=config)

    # Process each data point FIRST (no batching yet)
    raw_wavelengths = []

    for i, true_wl in enumerate(wavelength_data):
        # Create mock spectrum
        transmission, wavelengths = create_mock_spectrum(true_wl)

        # Detect peak
        try:
            detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)
            # Handle case where pipeline returns None or non-numeric value
            if detected_wl is None or (
                isinstance(detected_wl, (list, tuple)) and len(detected_wl) == 0
            ):
                raw_wavelengths.append(np.nan)
            # Extract wavelength if tuple (e.g., from Adaptive pipeline)
            elif isinstance(detected_wl, tuple):
                raw_wavelengths.append(float(detected_wl[0]))
            else:
                raw_wavelengths.append(float(detected_wl))
        except Exception as e:
            print(f"⚠️  Error at point {i}: {e}")
            raw_wavelengths.append(np.nan)

    raw_wavelengths = np.array(raw_wavelengths, dtype=float)

    # Remove NaN values
    valid_mask = ~np.isnan(raw_wavelengths)
    raw_wavelengths = raw_wavelengths[valid_mask]

    if len(raw_wavelengths) == 0:
        print("❌ ERROR: No valid detections!")
        return {
            "name": pipeline_name,
            "peak_to_peak": np.nan,
            "std": np.nan,
            "mean": np.nan,
            "valid_points": 0,
            "detected": [],
        }

    # NOW apply batch Savitzky-Golay smoothing to the wavelength time series
    if len(raw_wavelengths) >= window_length:
        detected_wavelengths = savgol_filter(
            raw_wavelengths,
            window_length=window_length,
            polyorder=polyorder,
        )
    else:
        detected_wavelengths = raw_wavelengths

    # Calculate statistics on smoothed data
    peak_to_peak = np.ptp(detected_wavelengths)
    std_dev = np.std(detected_wavelengths)
    mean_val = np.mean(detected_wavelengths)

    print(
        f"✅ Processed {len(detected_wavelengths)} valid points (post-batch smoothing applied)",
    )
    print(f"   Peak-to-Peak: {peak_to_peak:.6f} nm ({peak_to_peak*1000:.3f} pm)")
    print(f"   Std Dev:      {std_dev:.6f} nm ({std_dev*1000:.3f} pm)")
    print(f"   Mean:         {mean_val:.6f} nm")

    return {
        "name": pipeline_name,
        "peak_to_peak": peak_to_peak,
        "std": std_dev,
        "mean": mean_val,
        "valid_points": len(detected_wavelengths),
        "detected": detected_wavelengths,
    }


def test_batch_savgol_pipeline(wavelength_data, batch_size=20):
    """Test Batch Savitzky-Golay - uses batching INTERNALLY in the pipeline

    This is different from other pipelines - it buffers raw wavelengths
    and applies smoothing before returning them.
    """
    print(f"\n{'='*80}")
    print("Testing: Batch Savitzky-Golay (INTERNAL BATCHING)")
    print(f"{'='*80}")

    pipeline = BatchSavgolPipeline()

    # Add all data to batch
    detected_wavelengths = []
    timestamps = np.linspace(0, len(wavelength_data) * 0.025, len(wavelength_data))

    for i, (true_wl, timestamp) in enumerate(
        zip(wavelength_data, timestamps, strict=False),
    ):
        # Add to batch
        pipeline.add_to_batch(true_wl, timestamp)

        # Process batch when full
        if len(pipeline._wavelength_batch) >= pipeline.batch_size:
            batch_wl, batch_ts = pipeline.process_batch()
            if batch_wl is not None and len(batch_wl) > 0:
                detected_wavelengths.extend(batch_wl)

    # Process remaining batch
    if len(pipeline._wavelength_batch) > 0:
        batch_wl, batch_ts = pipeline.process_batch()
        if batch_wl is not None and len(batch_wl) > 0:
            detected_wavelengths.extend(batch_wl)

    detected_wavelengths = np.array(detected_wavelengths)

    if len(detected_wavelengths) == 0:
        print("❌ ERROR: No valid detections!")
        return {
            "name": "Batch Savitzky-Golay (INTERNAL BATCHING)",
            "peak_to_peak": np.nan,
            "std": np.nan,
            "mean": np.nan,
            "valid_points": 0,
            "detected": [],
        }

    # Calculate statistics
    peak_to_peak = np.ptp(detected_wavelengths)
    std_dev = np.std(detected_wavelengths)
    mean_val = np.mean(detected_wavelengths)

    print(f"✅ Processed {len(detected_wavelengths)} valid points")
    print(f"   Peak-to-Peak: {peak_to_peak:.6f} nm ({peak_to_peak*1000:.3f} pm)")
    print(f"   Std Dev:      {std_dev:.6f} nm ({std_dev*1000:.3f} pm)")
    print(f"   Mean:         {mean_val:.6f} nm")

    return {
        "name": "Batch Savitzky-Golay (INTERNAL BATCHING)",
        "peak_to_peak": peak_to_peak,
        "std": std_dev,
        "mean": mean_val,
        "valid_points": len(detected_wavelengths),
        "detected": detected_wavelengths,
    }


def main():
    print("\n" + "=" * 80)
    print("🧪 PIPELINE COMPARISON TEST - BASELINE DATA (FAIR BATCH COMPARISON)")
    print("=" * 80)

    # Load baseline data
    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return

    print("\n📊 Input Data Statistics:")
    print(f"   Points:       {len(wavelength_data)}")
    print(
        f"   Peak-to-Peak: {np.ptp(wavelength_data):.6f} nm ({np.ptp(wavelength_data)*1000:.3f} pm)",
    )
    print(
        f"   Std Dev:      {np.std(wavelength_data):.6f} nm ({np.std(wavelength_data)*1000:.3f} pm)",
    )
    print(f"   Mean:         {np.mean(wavelength_data):.6f} nm")

    # Batch smoothing parameters (applied to ALL pipelines for fair comparison)
    WINDOW_LENGTH = 11  # ~275ms at 40Hz
    POLYORDER = 2

    print("\n📦 BATCH POST-PROCESSING (Applied to ALL Pipelines):")
    print(f"   Savitzky-Golay window: {WINDOW_LENGTH} points")
    print(f"   Polynomial order: {POLYORDER}")
    print("   ⚠️  Each pipeline first detects peaks, then output is smoothed")

    # Test all pipelines WITH BATCH POST-PROCESSING
    results = []

    # 1. Fourier Transform + Batch Smoothing
    results.append(
        test_pipeline(
            "Fourier + Batch Smoothing",
            FourierPipeline,
            wavelength_data,
            config={"baseline_correction": False},
            window_length=WINDOW_LENGTH,
            polyorder=POLYORDER,
        ),
    )

    # 2. Batch Savitzky-Golay (INTERNAL batching - different approach)
    results.append(test_batch_savgol_pipeline(wavelength_data))

    # 3. Direct ArgMin + Batch Smoothing
    results.append(
        test_pipeline(
            "Direct ArgMin + Batch Smoothing",
            DirectArgminPipeline,
            wavelength_data,
            window_length=WINDOW_LENGTH,
            polyorder=POLYORDER,
        ),
    )

    # 4. Adaptive Multi-Feature + Batch Smoothing
    results.append(
        test_pipeline(
            "Adaptive Multi-Feature + Batch Smoothing",
            AdaptiveMultiFeaturePipeline,
            wavelength_data,
            window_length=WINDOW_LENGTH,
            polyorder=POLYORDER,
        ),
    )

    # Print summary table
    print("\n" + "=" * 80)
    print("📊 SUMMARY - PEAK-TO-PEAK VARIATION PER METHOD")
    print("=" * 80)
    print(f"{'Pipeline':<40} {'P2P (nm)':<12} {'P2P (pm)':<12} {'Std (nm)':<12}")
    print("-" * 80)

    for result in results:
        p2p_nm = result["peak_to_peak"]
        p2p_pm = p2p_nm * 1000
        std_nm = result["std"]

        if np.isnan(p2p_nm):
            print(f"{result['name']:<40} {'FAILED':<12} {'FAILED':<12} {'FAILED':<12}")
        else:
            print(
                f"{result['name']:<40} {p2p_nm:<12.6f} {p2p_pm:<12.3f} {std_nm:<12.6f}",
            )

    # Print ranking
    print("\n" + "=" * 80)
    print("🏆 RANKING (Best to Worst)")
    print("=" * 80)

    valid_results = [r for r in results if not np.isnan(r["peak_to_peak"])]
    valid_results.sort(key=lambda x: x["peak_to_peak"])

    for i, result in enumerate(valid_results, 1):
        p2p_pm = result["peak_to_peak"] * 1000
        print(f"{i}. {result['name']:<40} {p2p_pm:>10.3f} pm")

    # Save results to CSV
    results_df = pd.DataFrame(
        [
            {
                "Pipeline": r["name"],
                "Peak_to_Peak_nm": r["peak_to_peak"],
                "Peak_to_Peak_pm": r["peak_to_peak"] * 1000,
                "Std_Dev_nm": r["std"],
                "Std_Dev_pm": r["std"] * 1000,
                "Mean_nm": r["mean"],
                "Valid_Points": r["valid_points"],
            }
            for r in results
        ],
    )

    output_file = Path("pipeline_comparison_results.csv")
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Results saved to: {output_file}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
