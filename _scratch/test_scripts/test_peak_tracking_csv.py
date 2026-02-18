"""
Test HybridOriginalPipeline peak tracking on baseline data.
Compares second algorithm (HybridOriginal) against default (Fourier).
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# Import the peak tracking pipelines
from affilabs.utils.pipelines.fourier_pipeline import FourierPipeline
from affilabs.utils.pipelines.hybrid_original_pipeline import HybridOriginalPipeline


def load_baseline_from_xlsx(xlsx_file: Path, channel: str):
    """Load baseline data from Excel file for a specific channel."""
    if not xlsx_file.exists():
        return None, None

    # Read the Excel file - each channel has its own sheet
    sheet_name = f"Channel_{channel.upper()}"

    try:
        df = pd.read_excel(xlsx_file, sheet_name=sheet_name)
    except Exception as e:
        print(f"  Error reading sheet {sheet_name}: {e}")
        return None, None

    # First column is wavelengths, rest are transmission spectra over time
    wavelengths = df.iloc[:, 0].values
    transmission_spectra = df.iloc[:, 1:].values.T  # Transpose to get time x wavelength

    print(f"  Loaded {len(transmission_spectra)} spectra, {len(wavelengths)} wavelength points")

    return wavelengths, transmission_spectra


def test_pipelines(wavelengths, transmission_spectra, channel_name):
    """Test both Fourier and HybridOriginal pipelines."""
    print(f"\nTesting channel {channel_name}:")
    print(f"  Data shape: {transmission_spectra.shape} (time × wavelength)")

    # Initialize pipelines
    fourier = FourierPipeline()
    hybrid_original = HybridOriginalPipeline()

    # Test on each spectrum
    fourier_peaks = []
    hybrid_peaks = []

    for i, transmission in enumerate(transmission_spectra):
        # Fourier pipeline (default) - direct call to find_resonance_wavelength
        fourier_peak = fourier.find_resonance_wavelength(transmission, wavelengths)
        if fourier_peak is not None and not np.isnan(fourier_peak):
            fourier_peaks.append(fourier_peak)
        else:
            fourier_peaks.append(np.nan)

        # HybridOriginal pipeline (second algorithm) - direct call
        hybrid_peak = hybrid_original.find_resonance_wavelength(transmission, wavelengths)
        if hybrid_peak is not None and not np.isnan(hybrid_peak):
            hybrid_peaks.append(hybrid_peak)
        else:
            hybrid_peaks.append(np.nan)

        if i % 50 == 0:
            print(f"    Processed {i}/{len(transmission_spectra)} spectra...")

    fourier_peaks = np.array(fourier_peaks)
    hybrid_peaks = np.array(hybrid_peaks)

    # Calculate noise statistics
    fourier_valid = fourier_peaks[~np.isnan(fourier_peaks)]
    hybrid_valid = hybrid_peaks[~np.isnan(hybrid_peaks)]

    print("\n  Results summary:")
    print("    Fourier (default):")
    print(f"      Valid detections: {len(fourier_valid)}/{len(fourier_peaks)} ({100*len(fourier_valid)/len(fourier_peaks):.1f}%)")
    if len(fourier_valid) > 0:
        print(f"      Mean: {np.mean(fourier_valid):.2f} nm")
        print(f"      Std Dev: {np.std(fourier_valid):.3f} nm")
        print(f"      Range: {np.min(fourier_valid):.2f} - {np.max(fourier_valid):.2f} nm")

    print("\n    HybridOriginal (second algorithm):")
    print(f"      Valid detections: {len(hybrid_valid)}/{len(hybrid_peaks)} ({100*len(hybrid_valid)/len(hybrid_peaks):.1f}%)")
    if len(hybrid_valid) > 0:
        print(f"      Mean: {np.mean(hybrid_valid):.2f} nm")
        print(f"      Std Dev: {np.std(hybrid_valid):.3f} nm")
        print(f"      Range: {np.min(hybrid_valid):.2f} - {np.max(hybrid_valid):.2f} nm")

    # Compare when both detected
    both_valid = ~np.isnan(fourier_peaks) & ~np.isnan(hybrid_peaks)
    if np.sum(both_valid) > 0:
        difference = np.abs(fourier_peaks[both_valid] - hybrid_peaks[both_valid])
        print(f"\n    Agreement (when both detected, n={np.sum(both_valid)}):")
        print(f"      Mean difference: {np.mean(difference):.3f} nm")
        print(f"      Max difference: {np.max(difference):.3f} nm")

    return fourier_peaks, hybrid_peaks


def plot_comparison(fourier_peaks, hybrid_peaks, channel_name, output_dir):
    """Plot time series comparison."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    time = np.arange(len(fourier_peaks))

    # Plot 1: Time series overlay
    axes[0].plot(time, fourier_peaks, 'b-', alpha=0.6, label='Fourier (default)', linewidth=1)
    axes[0].plot(time, hybrid_peaks, 'r-', alpha=0.6, label='HybridOriginal (second)', linewidth=1)
    axes[0].set_xlabel('Spectrum #')
    axes[0].set_ylabel('Wavelength (nm)')
    axes[0].set_title(f'Channel {channel_name}: Peak Tracking Comparison')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Plot 2: Difference when both valid
    both_valid = ~np.isnan(fourier_peaks) & ~np.isnan(hybrid_peaks)
    diff = np.zeros_like(fourier_peaks)
    diff[both_valid] = hybrid_peaks[both_valid] - fourier_peaks[both_valid]
    diff[~both_valid] = np.nan

    axes[1].plot(time, diff, 'g-', alpha=0.6, linewidth=1)
    axes[1].axhline(y=0, color='k', linestyle='--', alpha=0.3)
    axes[1].set_xlabel('Spectrum #')
    axes[1].set_ylabel('Difference (nm)')
    axes[1].set_title('HybridOriginal - Fourier (when both detected)')
    axes[1].grid(True, alpha=0.3)

    # Plot 3: Noise (std over rolling window)
    window = 20
    fourier_rolling_std = pd.Series(fourier_peaks).rolling(window, center=True, min_periods=1).std()
    hybrid_rolling_std = pd.Series(hybrid_peaks).rolling(window, center=True, min_periods=1).std()

    axes[2].plot(time, fourier_rolling_std, 'b-', alpha=0.6, label='Fourier noise', linewidth=1)
    axes[2].plot(time, hybrid_rolling_std, 'r-', alpha=0.6, label='HybridOriginal noise', linewidth=1)
    axes[2].set_xlabel('Spectrum #')
    axes[2].set_ylabel(f'Rolling Std Dev (nm, window={window})')
    axes[2].set_title('Noise Comparison')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = output_dir / f"peak_tracking_comparison_ch{channel_name}.png"
    plt.savefig(output_file, dpi=150)
    print(f"\n  Saved plot: {output_file}")
    plt.close()


def main():
    baseline_dir = Path("baseline_data")
    output_dir = Path(".")

    print("=" * 80)
    print("Testing Peak Tracking Algorithms on Baseline Data")
    print("=" * 80)

    # Use the specific baseline file from today at 5pm
    baseline_file = baseline_dir / "baseline_recording_20251219_182111.xlsx"

    if not baseline_file.exists():
        print(f"\nBaseline file not found: {baseline_file.absolute()}")
        return

    print(f"\nUsing baseline file: {baseline_file.name}")

    # Test each channel
    channels = ['a', 'b', 'c', 'd']

    for channel in channels:
        print(f"\n{'='*80}")
        print(f"Channel {channel.upper()}")
        print(f"{'='*80}")

        wavelengths, transmission_spectra = load_baseline_from_xlsx(baseline_file, channel)

        if wavelengths is None:
            print(f"  Skipping channel {channel} - no data found")
            continue

        fourier_peaks, hybrid_peaks = test_pipelines(wavelengths, transmission_spectra, channel.upper())
        plot_comparison(fourier_peaks, hybrid_peaks, channel.upper(), output_dir)

    print("\n" + "=" * 80)
    print("Testing complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
