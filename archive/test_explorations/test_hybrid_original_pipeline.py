"""Test Hybrid Original Pipeline on saved baseline data

This script loads the most recent baseline recording and processes it
using the HybridOriginalPipeline (second algorithm) to evaluate performance.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

# Import the pipeline
from affilabs.utils.pipelines.hybrid_original_pipeline import HybridOriginalPipeline
from affilabs.utils.logger import logger

def load_latest_baseline():
    """Load the most recent baseline recording"""
    baseline_dir = Path("baseline_data")

    # Find most recent Excel file
    excel_files = list(baseline_dir.glob("baseline_recording_*.xlsx"))
    if not excel_files:
        # Try old format (individual CSV files)
        csv_files = list(baseline_dir.glob("baseline_transmission_cha_*.csv"))
        if not csv_files:
            print("❌ No baseline data found!")
            return None

        # Load old format
        latest_csv = sorted(csv_files)[-1]
        timestamp = latest_csv.stem.split('_')[-2] + '_' + latest_csv.stem.split('_')[-1]
        print(f"📂 Loading old format baseline data: {timestamp}")

        data = {}
        for ch in ['a', 'b', 'c', 'd']:
            filename = baseline_dir / f"baseline_transmission_ch{ch}_{timestamp}.csv"
            if filename.exists():
                df = pd.read_csv(filename)
                data[ch] = df

        # Load wavelengths if available
        wavelength_file = baseline_dir / f"baseline_wavelengths_{timestamp}.csv"
        if wavelength_file.exists():
            wl_df = pd.read_csv(wavelength_file)
            data['wavelengths'] = wl_df

        return data

    # Load Excel format
    latest_file = sorted(excel_files)[-1]
    print(f"📂 Loading baseline data: {latest_file.name}")

    data = {}

    # Load transmission data for each channel
    for ch in ['a', 'b', 'c', 'd']:
        sheet_name = f"Channel_{ch.upper()}"
        try:
            df = pd.read_excel(latest_file, sheet_name=sheet_name, index_col=0)
            data[ch] = df
            print(f"   Channel {ch.upper()}: {df.shape[1]} spectra, {df.shape[0]} wavelength points")
        except Exception as e:
            print(f"   ⚠️  Channel {ch.upper()} not found: {e}")

    # Load wavelength traces
    try:
        wl_df = pd.read_excel(latest_file, sheet_name="Wavelengths")
        data['wavelengths'] = wl_df
        print(f"   Wavelengths: {len(wl_df)} time points")
    except Exception as e:
        print(f"   ⚠️  Wavelengths not found: {e}")

    # Load metadata
    try:
        meta_df = pd.read_excel(latest_file, sheet_name="Metadata")
        data['metadata'] = meta_df
        print(f"   Metadata loaded")
    except Exception as e:
        print(f"   ⚠️  Metadata not found: {e}")

    return data

def test_pipeline_on_channel(transmission_df, channel_name):
    """Test HybridOriginalPipeline on a channel's transmission data

    Args:
        transmission_df: DataFrame with wavelength index and time columns
        channel_name: Channel identifier (a, b, c, d)
    """
    print(f"\n{'='*80}")
    print(f"Testing HybridOriginalPipeline on Channel {channel_name.upper()}")
    print(f"{'='*80}")

    # Create pipeline instance
    pipeline = HybridOriginalPipeline()

    # Get wavelength axis
    wavelengths = transmission_df.index.values
    print(f"Wavelength range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")
    print(f"Number of spectra: {transmission_df.shape[1]}")

    # Process each spectrum
    detected_wavelengths = []

    for i, col in enumerate(transmission_df.columns):
        transmission = transmission_df[col].values

        # Skip if all NaN
        if np.all(np.isnan(transmission)):
            continue

        # Process with pipeline
        try:
            result = pipeline.process_spectrum(
                wavelengths=wavelengths,
                transmission=transmission,
                channel=channel_name,
                reference=None,  # Not needed for transmission-based processing
                dark=None
            )

            if result.success and result.resonance_wavelength is not None:
                detected_wavelengths.append(result.resonance_wavelength)
            else:
                detected_wavelengths.append(np.nan)

        except Exception as e:
            print(f"   ❌ Error processing spectrum {i}: {e}")
            detected_wavelengths.append(np.nan)

    detected_wavelengths = np.array(detected_wavelengths)
    valid_wavelengths = detected_wavelengths[~np.isnan(detected_wavelengths)]

    print(f"\n📊 RESULTS:")
    print(f"   Total spectra: {len(detected_wavelengths)}")
    print(f"   Successfully detected: {len(valid_wavelengths)}")
    print(f"   Failed: {len(detected_wavelengths) - len(valid_wavelengths)}")

    if len(valid_wavelengths) > 0:
        print(f"\n📈 STATISTICS:")
        print(f"   Mean wavelength: {np.mean(valid_wavelengths):.4f} nm")
        print(f"   Std deviation: {np.std(valid_wavelengths):.4f} nm")
        print(f"   Min: {np.min(valid_wavelengths):.4f} nm")
        print(f"   Max: {np.max(valid_wavelengths):.4f} nm")
        print(f"   Range: {np.max(valid_wavelengths) - np.min(valid_wavelengths):.4f} nm")

        # Calculate RU noise (assuming ~1000 RU per nm for typical SPR)
        ru_per_nm = 1000  # Approximate conversion
        std_ru = np.std(valid_wavelengths) * ru_per_nm
        print(f"\n🎯 BASELINE NOISE (estimated):")
        print(f"   {std_ru:.2f} RU  (assuming {ru_per_nm} RU/nm sensitivity)")

    return detected_wavelengths

def plot_results(wavelengths_dict):
    """Plot detected wavelengths for all channels"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle('HybridOriginalPipeline - Peak Tracking Results', fontsize=14, fontweight='bold')

    channels = ['a', 'b', 'c', 'd']
    for idx, (ax, ch) in enumerate(zip(axes.flat, channels)):
        wl_data = wavelengths_dict[ch]
        valid_data = wl_data[~np.isnan(wl_data)]

        if len(valid_data) > 0:
            # Time series
            ax.plot(valid_data, 'b-', alpha=0.6, linewidth=0.5)
            ax.set_title(f'Channel {ch.upper()}: {np.std(valid_data):.4f} nm std')
            ax.set_xlabel('Time point')
            ax.set_ylabel('Wavelength (nm)')
            ax.grid(True, alpha=0.3)

            # Add stats text
            stats_text = f'Mean: {np.mean(valid_data):.3f} nm\nStd: {np.std(valid_data):.4f} nm'
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                   fontsize=9)
        else:
            ax.text(0.5, 0.5, 'No valid data', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title(f'Channel {ch.upper()}')

    plt.tight_layout()

    # Save figure
    output_dir = Path("baseline_data")
    output_file = output_dir / "hybrid_original_pipeline_test_results.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n💾 Plot saved: {output_file}")

    plt.show()

def main():
    print("🔬 Testing HybridOriginalPipeline (Second Algorithm)")
    print("="*80)

    # Load data
    data = load_latest_baseline()
    if data is None:
        return

    # Test on each channel
    results = {}
    for ch in ['a', 'b', 'c', 'd']:
        if ch in data:
            wavelengths = test_pipeline_on_channel(data[ch], ch)
            results[ch] = wavelengths

    # Plot results
    if results:
        plot_results(results)

    print("\n" + "="*80)
    print("✅ Testing complete!")
    print("="*80)

if __name__ == "__main__":
    main()
