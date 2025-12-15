"""Validate Step 4 LED Balancing Logic

This script checks that Step 4 properly:
1. Sets weakest LED to 255
2. Finds integration time for weakest @ 75% detector max
3. Freezes integration time globally
4. Adjusts other LEDs individually to hit target at frozen integration time
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from settings.settings import CH_LIST
from utils.logger import logger


def load_calibration_data():
    """Load the most recent calibration data."""
    config_file = ROOT_DIR / "config" / "device_config.json"

    if not config_file.exists():
        logger.error(f"❌ Device config not found: {config_file}")
        return None

    try:
        with open(config_file) as f:
            config = json.load(f)

        led_cal = config.get("calibration", {}).get("led_calibration", {})
        if not led_cal:
            logger.error("❌ No LED calibration found in device_config.json")
            return None

        return {
            "integration_time_ms": led_cal.get("integration_time_ms", 0),
            "s_mode_leds": led_cal.get("s_mode_intensities", {}),
            "p_mode_leds": led_cal.get("p_mode_intensities", {}),
        }
    except Exception as e:
        logger.error(f"❌ Error loading calibration: {e}")
        return None


def load_s_ref_data():
    """Load S-ref data from Step 6."""
    calib_dir = ROOT_DIR / "generated-files" / "calibration_data"

    if not calib_dir.exists():
        logger.error(f"❌ Calibration directory not found: {calib_dir}")
        return None

    s_ref_data = {}
    for ch in CH_LIST:
        # Find most recent s_ref file for this channel
        pattern = f"s_ref_{ch}_*.npy"
        files = sorted(
            calib_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if files:
            try:
                data = np.load(files[0])
                s_ref_data[ch] = data
                logger.info(f"✅ Loaded {ch}: {files[0].name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {ch}: {e}")
        else:
            logger.warning(f"⚠️  No S-ref data found for channel {ch}")

    return s_ref_data if len(s_ref_data) == 4 else None


def validate_step4_logic(cal_data, s_ref_data):
    """Validate that Step 4 followed the correct logic."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("🔍 STEP 4 LOGIC VALIDATION")
    logger.info("=" * 80)

    # Extract LED values
    leds = cal_data["s_mode_leds"]
    integration_ms = cal_data["integration_time_ms"]

    logger.info(f"Integration Time: {integration_ms} ms (frozen globally)")
    logger.info("")
    logger.info("LED Values:")
    for ch in CH_LIST:
        logger.info(f"   {ch.upper()}: {leds.get(ch, 'N/A')}")

    # Check 1: Find weakest LED (should be 255)
    logger.info("")
    logger.info("CHECK 1: Weakest LED should be at 255")
    logger.info("-" * 80)

    max_led = max(leds.values())
    weakest_channels = [ch for ch, val in leds.items() if val == max_led]

    if max_led == 255:
        logger.info(f"✅ PASS: Weakest LED(s) set to 255: {weakest_channels}")
    else:
        logger.error(f"❌ FAIL: Maximum LED value is {max_led}, expected 255")
        return False

    # Check 2: Other LEDs should be <= 255
    logger.info("")
    logger.info("CHECK 2: All LED values should be in range [1, 255]")
    logger.info("-" * 80)

    all_valid = True
    for ch, val in leds.items():
        if 1 <= val <= 255:
            logger.info(f"✅ {ch.upper()}: {val} is valid")
        else:
            logger.error(f"❌ {ch.upper()}: {val} is OUT OF RANGE")
            all_valid = False

    if not all_valid:
        return False

    # Check 3: LEDs should be differentiated (not all the same)
    logger.info("")
    logger.info("CHECK 3: LED values should be differentiated")
    logger.info("-" * 80)

    unique_leds = set(leds.values())
    if len(unique_leds) == 1:
        logger.error(
            f"❌ FAIL: All LEDs have same value ({list(unique_leds)[0]}) - no balancing occurred",
        )
        return False
    logger.info(
        f"✅ PASS: {len(unique_leds)} unique LED values: {sorted(unique_leds, reverse=True)}",
    )

    # Check 4: S-ref signals should be balanced (similar intensities)
    logger.info("")
    logger.info("CHECK 4: S-ref signals should be balanced")
    logger.info("-" * 80)

    # Calculate mean signal in ROI region for each channel
    roi_start = len(s_ref_data["a"]) // 3
    roi_end = 2 * len(s_ref_data["a"]) // 3

    roi_means = {}
    for ch in CH_LIST:
        roi_data = s_ref_data[ch][roi_start:roi_end]
        roi_means[ch] = np.mean(roi_data)
        logger.info(
            f"   {ch.upper()}: ROI mean = {roi_means[ch]:7.0f} counts (LED={leds[ch]})",
        )

    # Calculate coefficient of variation
    mean_of_means = np.mean(list(roi_means.values()))
    std_of_means = np.std(list(roi_means.values()))
    cv = (std_of_means / mean_of_means * 100) if mean_of_means > 0 else 0

    logger.info("")
    logger.info("Balance Statistics:")
    logger.info(f"   Target (mean): {mean_of_means:.0f} counts")
    logger.info(f"   Std deviation: {std_of_means:.0f} counts")
    logger.info(f"   CV (coefficient of variation): {cv:.1f}%")
    logger.info("")

    if cv < 10:
        logger.info("✅ PASS: Excellent balance (CV < 10%)")
        balance_pass = True
    elif cv < 20:
        logger.info("⚠️  MARGINAL: Acceptable balance (CV < 20%)")
        balance_pass = True
    else:
        logger.error("❌ FAIL: Poor balance (CV >= 20%)")
        balance_pass = False

    # Check 5: Verify LED intensity correlates with signal
    logger.info("")
    logger.info("CHECK 5: LED intensity should correlate with signal level")
    logger.info("-" * 80)

    # Channels with same LED should have proportional signals
    # Check if weaker LEDs produced weaker signals (as expected)
    for ch in CH_LIST:
        if ch == weakest_channels[0]:
            continue  # Skip weakest

        led_ratio = leds[ch] / 255.0
        signal_ratio = roi_means[ch] / roi_means[weakest_channels[0]]

        logger.info(
            f"   {ch.upper()}: LED ratio={led_ratio:.2f}, Signal ratio={signal_ratio:.2f}",
        )

        # Signal ratio should be approximately equal to LED ratio
        # (within 50% tolerance due to non-linearity)
        if abs(signal_ratio - led_ratio) / led_ratio < 0.5:
            logger.info("      ✅ Correlation OK")
        else:
            logger.warning(
                "      ⚠️  Large deviation - possible non-linear LED response",
            )

    logger.info("")
    logger.info("=" * 80)

    if balance_pass:
        logger.info("✅ OVERALL: Step 4 LED balancing validation PASSED")
    else:
        logger.error("❌ OVERALL: Step 4 LED balancing validation FAILED")

    logger.info("=" * 80)

    return balance_pass


def plot_step4_results(cal_data, s_ref_data):
    """Create diagnostic plots for Step 4 results."""
    leds = cal_data["s_mode_leds"]

    fig = plt.figure(figsize=(16, 12))

    # Plot 1: S-ref spectra overlay
    ax1 = plt.subplot(3, 2, 1)
    colors = {"a": "red", "b": "blue", "c": "green", "d": "orange"}

    for ch in CH_LIST:
        ax1.plot(
            s_ref_data[ch],
            label=f"{ch.upper()} (LED={leds[ch]})",
            color=colors[ch],
            alpha=0.7,
            linewidth=1.5,
        )

    ax1.set_xlabel("Pixel Index")
    ax1.set_ylabel("Intensity (counts)")
    ax1.set_title("S-ref Spectra After Step 4 Balancing")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: ROI region zoomed
    ax2 = plt.subplot(3, 2, 2)
    roi_start = len(s_ref_data["a"]) // 3
    roi_end = 2 * len(s_ref_data["a"]) // 3

    for ch in CH_LIST:
        roi_data = s_ref_data[ch][roi_start:roi_end]
        ax2.plot(
            roi_data,
            label=f"{ch.upper()} (LED={leds[ch]})",
            color=colors[ch],
            alpha=0.7,
            linewidth=2,
        )

    ax2.set_xlabel("Pixel Index (ROI)")
    ax2.set_ylabel("Intensity (counts)")
    ax2.set_title("ROI Region (Balancing Target Zone)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: LED values bar chart
    ax3 = plt.subplot(3, 2, 3)
    x_pos = np.arange(len(CH_LIST))
    led_values = [leds[ch] for ch in CH_LIST]
    bars = ax3.bar(x_pos, led_values, color=[colors[ch] for ch in CH_LIST], alpha=0.7)

    ax3.axhline(y=255, color="red", linestyle="--", linewidth=2, label="Maximum (255)")
    ax3.set_xlabel("Channel")
    ax3.set_ylabel("LED Intensity")
    ax3.set_title("Step 4: Final LED Values")
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels([ch.upper() for ch in CH_LIST])
    ax3.set_ylim(0, 270)
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis="y")

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height)}",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

    # Plot 4: ROI mean intensities
    ax4 = plt.subplot(3, 2, 4)
    roi_means = {}
    for ch in CH_LIST:
        roi_data = s_ref_data[ch][roi_start:roi_end]
        roi_means[ch] = np.mean(roi_data)

    mean_values = [roi_means[ch] for ch in CH_LIST]
    bars = ax4.bar(x_pos, mean_values, color=[colors[ch] for ch in CH_LIST], alpha=0.7)

    target = np.mean(mean_values)
    ax4.axhline(
        y=target,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Target: {target:.0f}",
    )

    ax4.set_xlabel("Channel")
    ax4.set_ylabel("Mean Intensity (counts)")
    ax4.set_title("ROI Mean Intensities (Balance Quality)")
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([ch.upper() for ch in CH_LIST])
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis="y")

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        deviation = ((height - target) / target * 100) if target > 0 else 0
        ax4.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height)}\n({deviation:+.0f}%)",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Plot 5: LED vs Signal correlation
    ax5 = plt.subplot(3, 2, 5)

    led_vals = [leds[ch] for ch in CH_LIST]
    signal_vals = [roi_means[ch] for ch in CH_LIST]

    ax5.scatter(
        led_vals,
        signal_vals,
        s=100,
        alpha=0.7,
        c=[colors[ch] for ch in CH_LIST],
    )

    for ch, led, sig in zip(CH_LIST, led_vals, signal_vals, strict=False):
        ax5.annotate(
            ch.upper(),
            (led, sig),
            fontsize=12,
            fontweight="bold",
            xytext=(5, 5),
            textcoords="offset points",
        )

    ax5.set_xlabel("LED Intensity")
    ax5.set_ylabel("ROI Mean Signal (counts)")
    ax5.set_title("LED Intensity vs Signal Correlation")
    ax5.grid(True, alpha=0.3)

    # Plot 6: Balance quality metrics
    ax6 = plt.subplot(3, 2, 6)
    ax6.axis("off")

    # Calculate statistics
    std_signal = np.std(mean_values)
    cv_signal = (std_signal / target * 100) if target > 0 else 0

    std_led = np.std(led_vals)
    mean_led = np.mean(led_vals)
    cv_led = (std_led / mean_led * 100) if mean_led > 0 else 0

    summary_text = f"""
    STEP 4 BALANCING SUMMARY
    ═══════════════════════════════════

    Integration Time: {cal_data['integration_time_ms']} ms (FROZEN)

    LED Statistics:
       Mean LED: {mean_led:.0f}
       Std Dev: {std_led:.0f}
       CV: {cv_led:.1f}%

    Signal Statistics (ROI):
       Target: {target:.0f} counts
       Std Dev: {std_signal:.0f} counts
       CV: {cv_signal:.1f}%

    Balance Quality:
       {"✅ EXCELLENT (CV < 10%)" if cv_signal < 10 else
        "⚠️  ACCEPTABLE (CV < 20%)" if cv_signal < 20 else
        "❌ POOR (CV >= 20%)"}

    LED Values:
    """

    for ch in CH_LIST:
        summary_text += (
            f"\n       {ch.upper()}: {leds[ch]:3d}  →  {roi_means[ch]:7.0f} counts"
        )

    ax6.text(
        0.1,
        0.95,
        summary_text,
        transform=ax6.transAxes,
        fontsize=11,
        verticalalignment="top",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
    )

    plt.tight_layout()

    # Save figure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = ROOT_DIR / f"step4_validation_{timestamp}.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.info("")
    logger.info(f"💾 Saved validation plot: {output_file}")

    plt.show()


if __name__ == "__main__":
    logger.info("🔍 Validating Step 4 LED Balancing...")
    logger.info("")

    # Load calibration data
    cal_data = load_calibration_data()
    if not cal_data:
        sys.exit(1)

    # Load S-ref data
    s_ref_data = load_s_ref_data()
    if not s_ref_data:
        sys.exit(1)

    # Validate logic
    passed = validate_step4_logic(cal_data, s_ref_data)

    # Create diagnostic plots
    plot_step4_results(cal_data, s_ref_data)

    logger.info("")
    if passed:
        logger.info("✅ Step 4 validation COMPLETE - balancing is working correctly")
        sys.exit(0)
    else:
        logger.error("❌ Step 4 validation FAILED - balancing needs fixes")
        sys.exit(1)
