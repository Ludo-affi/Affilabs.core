"""Analyze Step 4 LED balancing with detailed diagnostics and graphs.

This script captures raw data during Step 4 calibration to verify
LED balancing is working correctly for each channel.
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from utils.logger import logger
from settings.settings import CH_LIST


def plot_step4_raw_data():
    """Load and plot raw Step 4 measurement data."""

    # Look for recent S-ref data (Step 6) which shows final calibrated state
    calib_dir = ROOT_DIR / "generated-files" / "calibration_data"

    if not calib_dir.exists():
        logger.error(f"❌ Calibration data directory not found: {calib_dir}")
        return

    # Find most recent s_ref files
    s_ref_files = {}
    for ch in CH_LIST:
        pattern = f"s_ref_{ch}_*.npy"
        files = sorted(calib_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            s_ref_files[ch] = files[0]

    if not s_ref_files:
        logger.error("❌ No S-ref calibration files found")
        return

    logger.info("=" * 80)
    logger.info("📊 STEP 4 LED BALANCING ANALYSIS")
    logger.info("=" * 80)

    # Load S-ref data for each channel
    s_ref_data = {}
    for ch, filepath in s_ref_files.items():
        try:
            data = np.load(filepath)
            s_ref_data[ch] = data
            logger.info(f"✅ Loaded {ch}: {filepath.name}")
            logger.info(f"   Shape: {data.shape}, Mean: {np.mean(data):.1f}, Max: {np.max(data):.1f}")
        except Exception as e:
            logger.error(f"❌ Failed to load {ch}: {e}")

    if len(s_ref_data) != 4:
        logger.error(f"❌ Expected 4 channels, got {len(s_ref_data)}")
        return

    # Create figure with multiple plots
    fig = plt.figure(figsize=(16, 10))

    # Plot 1: Raw S-ref spectra (all channels overlaid)
    ax1 = plt.subplot(2, 2, 1)
    colors = {'a': 'red', 'b': 'blue', 'c': 'green', 'd': 'orange'}

    for ch in CH_LIST:
        if ch in s_ref_data:
            ax1.plot(s_ref_data[ch], label=f'Channel {ch.upper()}', color=colors[ch], alpha=0.7)

    ax1.set_xlabel('Pixel Index')
    ax1.set_ylabel('Intensity (counts)')
    ax1.set_title('Step 4: Raw S-ref Spectra (After LED Balancing)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Peak intensities comparison
    ax2 = plt.subplot(2, 2, 2)
    peak_values = {ch: np.max(s_ref_data[ch]) for ch in CH_LIST if ch in s_ref_data}
    mean_values = {ch: np.mean(s_ref_data[ch]) for ch in CH_LIST if ch in s_ref_data}

    x_pos = np.arange(len(CH_LIST))
    peak_bars = ax2.bar(x_pos - 0.2, [peak_values.get(ch, 0) for ch in CH_LIST],
                        0.4, label='Peak', alpha=0.8, color='steelblue')
    mean_bars = ax2.bar(x_pos + 0.2, [mean_values.get(ch, 0) for ch in CH_LIST],
                        0.4, label='Mean', alpha=0.8, color='coral')

    ax2.set_xlabel('Channel')
    ax2.set_ylabel('Intensity (counts)')
    ax2.set_title('Peak vs Mean Intensity per Channel')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels([ch.upper() for ch in CH_LIST])
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bars in [peak_bars, mean_bars]:
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=9)

    # Plot 3: ROI region (580-610nm) comparison
    ax3 = plt.subplot(2, 2, 3)

    # Estimate ROI (assuming SPR range ~400-800nm mapped to 1591 pixels)
    # 580-610nm is roughly middle region
    roi_start = len(s_ref_data['a']) // 3
    roi_end = 2 * len(s_ref_data['a']) // 3

    for ch in CH_LIST:
        if ch in s_ref_data:
            roi_data = s_ref_data[ch][roi_start:roi_end]
            ax3.plot(roi_data, label=f'Channel {ch.upper()}', color=colors[ch], alpha=0.7, linewidth=2)

    ax3.set_xlabel('Pixel Index (ROI region)')
    ax3.set_ylabel('Intensity (counts)')
    ax3.set_title('Step 4: ROI Region (Target Balancing Zone)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Plot 4: Balance quality metrics
    ax4 = plt.subplot(2, 2, 4)

    # Calculate ROI means for balance check
    roi_means = {}
    for ch in CH_LIST:
        if ch in s_ref_data:
            roi_data = s_ref_data[ch][roi_start:roi_end]
            roi_means[ch] = np.mean(roi_data)

    # Calculate balance statistics
    mean_of_means = np.mean(list(roi_means.values()))
    std_of_means = np.std(list(roi_means.values()))
    cv = (std_of_means / mean_of_means * 100) if mean_of_means > 0 else 0

    x_pos = np.arange(len(CH_LIST))
    bars = ax4.bar(x_pos, [roi_means.get(ch, 0) for ch in CH_LIST],
                   color=[colors[ch] for ch in CH_LIST], alpha=0.7)

    # Add target line (mean across channels)
    ax4.axhline(y=mean_of_means, color='red', linestyle='--',
                linewidth=2, label=f'Target: {mean_of_means:.0f}')

    ax4.set_xlabel('Channel')
    ax4.set_ylabel('Mean Intensity in ROI (counts)')
    ax4.set_title(f'Balance Quality (CV: {cv:.1f}%)')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([ch.upper() for ch in CH_LIST])
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()

    # Save figure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = ROOT_DIR / f"step4_balancing_analysis_{timestamp}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"")
    logger.info(f"💾 Saved analysis plot: {output_file}")

    plt.show()

    # Print summary statistics
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 BALANCE QUALITY SUMMARY")
    logger.info("=" * 80)
    logger.info(f"ROI Mean Intensities:")
    for ch in CH_LIST:
        if ch in roi_means:
            deviation = ((roi_means[ch] - mean_of_means) / mean_of_means * 100) if mean_of_means > 0 else 0
            logger.info(f"   {ch.upper()}: {roi_means[ch]:7.0f} counts ({deviation:+.1f}% from target)")
    logger.info("")
    logger.info(f"Target (mean): {mean_of_means:.0f} counts")
    logger.info(f"Std deviation: {std_of_means:.0f} counts")
    logger.info(f"CV (coefficient of variation): {cv:.1f}%")
    logger.info("")

    if cv < 5:
        logger.info("✅ EXCELLENT: Channels are well balanced (CV < 5%)")
    elif cv < 10:
        logger.info("✅ GOOD: Channels are reasonably balanced (CV < 10%)")
    elif cv < 20:
        logger.info("⚠️  FAIR: Some imbalance detected (CV < 20%)")
    else:
        logger.info("❌ POOR: Significant imbalance (CV >= 20%)")

    logger.info("=" * 80)


def check_led_values():
    """Check what LED values were set during calibration."""
    config_file = ROOT_DIR / "config" / "device_config.json"

    if not config_file.exists():
        logger.warning(f"❌ Device config not found: {config_file}")
        return

    import json
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        led_cal = config.get('calibration', {}).get('led_calibration', {})
        s_mode = led_cal.get('s_mode_intensities', {})

        logger.info("")
        logger.info("=" * 80)
        logger.info("🔦 LED INTENSITIES FROM CALIBRATION")
        logger.info("=" * 80)
        for ch in CH_LIST:
            val = s_mode.get(ch, 'N/A')
            logger.info(f"   Channel {ch.upper()}: LED = {val}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error reading LED values: {e}")


if __name__ == "__main__":
    logger.info("🔍 Analyzing Step 4 LED balancing results...")
    logger.info("")

    # Check LED values first
    check_led_values()

    # Plot raw data
    plot_step4_raw_data()
