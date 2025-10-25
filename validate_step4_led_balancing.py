"""
Validate Step 4 LED Balancing Logic
====================================
Analyzes the LED balancing results from the most recent calibration
to identify issues with saturation handling.
"""
import json
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# Target signal level (75% of detector max)
DETECTOR_MAX = 65535
TARGET_COUNTS = int(0.75 * DETECTOR_MAX)  # 49,151
TARGET_TOLERANCE = 0.10  # ±10%

def load_config():
    """Load device config with LED calibration results"""
    with open('config/device_config.json', 'r') as f:
        return json.load(f)

def load_baseline_data():
    """Load S-ref baseline spectra from calibration data"""
    baseline_files = {
        'a': 'calibration_data/s_ref_a.npy',
        'b': 'calibration_data/s_ref_b.npy',
        'c': 'calibration_data/s_ref_c.npy',
        'd': 'calibration_data/s_ref_d.npy'
    }

    baseline_data = {}
    for ch, filepath in baseline_files.items():
        path = Path(filepath)
        if path.exists():
            baseline_data[ch] = np.load(path)
        else:
            baseline_data[ch] = None
            print(f"⚠️  Warning: {filepath} not found")

    return baseline_data

def analyze_led_balancing():
    """Analyze LED balancing quality from Step 4"""

    print("=" * 70)
    print("STEP 4 LED BALANCING VALIDATION")
    print("=" * 70)

    # Load configuration
    config = load_config()
    led_cal = config.get('led_calibration', {})
    diagnostics = config.get('diagnostics', {}).get('led_ranking', {})
    baseline_means = config.get('baseline_data', {}).get('s_ref_mean', {})

    print("\n📊 CALIBRATION METADATA")
    print("-" * 70)
    print(f"Calibration Date: {led_cal.get('calibration_date', 'N/A')}")
    print(f"Calibration Mode: {led_cal.get('calibration_mode', 'N/A')}")
    print(f"Global Integration Time: {led_cal.get('global_integration_time_ms', 'N/A')} ms")

    # LED intensities
    s_led = led_cal.get('s_mode_led_intensities', {})

    print("\n🔦 LED INTENSITIES (Step 4 Output)")
    print("-" * 70)
    print("Channel  LED Value  Expected Behavior")
    print("-" * 70)
    weakest = diagnostics.get('weakest_channel', 'b')
    for ch in ['a', 'b', 'c', 'd']:
        led_val = s_led.get(ch, 0)
        status = "✓ WEAKEST (max LED)" if ch == weakest else f"  Dimmed to {led_val}"
        print(f"   {ch.upper()}       {led_val:3d}      {status}")

    # Baseline signal levels
    print("\n📈 BASELINE SIGNAL LEVELS (S-ref from Step 6)")
    print("-" * 70)
    print("Channel  LED  Signal (counts)  Target  Deviation  Status")
    print("-" * 70)

    results = {}
    for ch in ['a', 'b', 'c', 'd']:
        led_val = s_led.get(ch, 0)
        signal = baseline_means.get(ch, 0)
        deviation_pct = ((signal - TARGET_COUNTS) / TARGET_COUNTS) * 100

        # Status check
        if abs(deviation_pct) <= TARGET_TOLERANCE * 100:
            status = "✅ GOOD"
        elif signal > TARGET_COUNTS * (1 + TARGET_TOLERANCE):
            status = "❌ TOO HIGH"
        else:
            status = "⚠️  TOO LOW"

        results[ch] = {
            'led': led_val,
            'signal': signal,
            'target': TARGET_COUNTS,
            'deviation_pct': deviation_pct,
            'status': status
        }

        print(f"   {ch.upper()}     {led_val:3d}    {signal:8.0f}      {TARGET_COUNTS:5d}   {deviation_pct:+6.1f}%   {status}")

    # Balance analysis
    print("\n⚖️  BALANCE QUALITY ANALYSIS")
    print("-" * 70)

    signals = [baseline_means.get(ch, 0) for ch in ['a', 'b', 'c', 'd']]
    mean_signal = np.mean(signals)
    std_signal = np.std(signals)
    cv = (std_signal / mean_signal * 100) if mean_signal > 0 else 0

    print(f"Mean Signal: {mean_signal:.0f} counts")
    print(f"Std Dev: {std_signal:.0f} counts")
    print(f"Coefficient of Variation (CV): {cv:.1f}%")
    print(f"Target CV: <10%")

    if cv < 10:
        print("✅ EXCELLENT balance")
    elif cv < 20:
        print("⚠️  ACCEPTABLE balance (needs improvement)")
    else:
        print("❌ POOR balance (Step 4 failed)")

    # Saturation analysis
    print("\n🚨 SATURATION ANALYSIS")
    print("-" * 70)

    saturated = diagnostics.get('saturated_on_first_pass', [])
    ranking = diagnostics.get('ranked_order', [])
    percent_of_weakest = diagnostics.get('percent_of_weakest', {})

    print(f"Weakest Channel: {weakest.upper()} (LED=255 fixed)")
    print(f"Channels Saturated at LED=255 during Step 3: {[ch.upper() for ch in saturated]}")
    print(f"\nRelative Brightness (% of weakest):")

    for ch in ranking:
        pct = percent_of_weakest.get(ch, 0)
        led_result = s_led.get(ch, 0)
        print(f"  {ch.upper()}: {pct:5.1f}% → LED={led_result}")

    # Problem identification
    print("\n🔍 PROBLEM IDENTIFICATION")
    print("-" * 70)

    issues = []

    # Check if channels with same LED have different brightness
    led_groups = {}
    for ch in ['a', 'b', 'c', 'd']:
        led = s_led.get(ch, 0)
        if led not in led_groups:
            led_groups[led] = []
        led_groups[led].append((ch, baseline_means.get(ch, 0)))

    for led_val, channels in led_groups.items():
        if len(channels) > 1:
            signals = [sig for _, sig in channels]
            if max(signals) / min(signals) > 1.2:  # 20% difference
                issue = f"❌ Channels at LED={led_val} have different brightness:"
                for ch, sig in channels:
                    issue += f"\n     {ch.upper()}: {sig:.0f} counts"
                issues.append(issue)

    # Check if saturated channels got same LED value
    if len(saturated) > 1:
        saturated_leds = [s_led.get(ch, 0) for ch in saturated]
        if len(set(saturated_leds)) == 1:
            issues.append(f"❌ All saturated channels ({[ch.upper() for ch in saturated]}) got same LED={saturated_leds[0]}")

    # Check if brighter channels are over-target
    for ch in ['a', 'b', 'c', 'd']:
        if ch in saturated and results[ch]['deviation_pct'] > 20:
            issues.append(f"❌ Channel {ch.upper()} (saturated) is {results[ch]['deviation_pct']:.1f}% over target")

    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(issue)
        print("\n🔧 ROOT CAUSE: Step 4 assumes linear LED-to-signal relationship")
        print("   When channels saturate at LED=255, formula breaks:")
        print(f"   LED = (target / saturated_signal) * 255")
        print(f"   LED = ({TARGET_COUNTS} / 65535) * 255 = 191 for ALL saturated channels")
        print("\n💡 SOLUTION: Measure at lower LED values for saturated channels")
    else:
        print("✅ No issues found - LED balancing working correctly!")

    # Create visualization
    create_validation_plot(results, config)

    return results

def create_validation_plot(results, config):
    """Create visualization of LED balancing validation"""

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Step 4 LED Balancing Validation', fontsize=16, fontweight='bold')

    channels = ['a', 'b', 'c', 'd']
    colors = {'a': '#FF6B6B', 'b': '#4ECDC4', 'c': '#45B7D1', 'd': '#FFA07A'}

    # 1. LED Values
    ax = axes[0, 0]
    led_values = [results[ch]['led'] for ch in channels]
    bars = ax.bar([ch.upper() for ch in channels], led_values, color=[colors[ch] for ch in channels], alpha=0.7, edgecolor='black')
    ax.axhline(255, color='red', linestyle='--', linewidth=2, label='Max LED (255)')
    ax.set_ylabel('LED Intensity', fontsize=12)
    ax.set_xlabel('Channel', fontsize=12)
    ax.set_title('LED Values Set by Step 4', fontsize=13, fontweight='bold')
    ax.set_ylim(0, 270)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add values on bars
    for bar, val in zip(bars, led_values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{int(val)}', ha='center', va='bottom', fontweight='bold')

    # 2. Signal Levels vs Target
    ax = axes[0, 1]
    signals = [results[ch]['signal'] for ch in channels]
    bars = ax.bar([ch.upper() for ch in channels], signals, color=[colors[ch] for ch in channels], alpha=0.7, edgecolor='black')
    ax.axhline(TARGET_COUNTS, color='green', linestyle='--', linewidth=2, label=f'Target ({TARGET_COUNTS:,})')
    ax.axhspan(TARGET_COUNTS * 0.9, TARGET_COUNTS * 1.1, alpha=0.2, color='green', label='±10% tolerance')
    ax.set_ylabel('Signal (counts)', fontsize=12)
    ax.set_xlabel('Channel', fontsize=12)
    ax.set_title('Achieved Signal Levels (S-ref)', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add values on bars
    for bar, val in zip(bars, signals):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1000,
                f'{int(val):,}', ha='center', va='bottom', fontsize=9)

    # 3. Deviation from Target
    ax = axes[1, 0]
    deviations = [results[ch]['deviation_pct'] for ch in channels]
    bar_colors = ['red' if abs(d) > 10 else 'orange' if abs(d) > 5 else 'green' for d in deviations]
    bars = ax.bar([ch.upper() for ch in channels], deviations, color=bar_colors, alpha=0.7, edgecolor='black')
    ax.axhline(0, color='black', linestyle='-', linewidth=1)
    ax.axhspan(-10, 10, alpha=0.2, color='green', label='±10% tolerance')
    ax.set_ylabel('Deviation from Target (%)', fontsize=12)
    ax.set_xlabel('Channel', fontsize=12)
    ax.set_title('Signal Deviation from Target', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add values on bars
    for bar, val in zip(bars, deviations):
        height = bar.get_height()
        y_pos = height + (2 if height > 0 else -4)
        ax.text(bar.get_x() + bar.get_width()/2., y_pos,
                f'{val:+.1f}%', ha='center', va='bottom' if height > 0 else 'top', fontweight='bold', fontsize=9)

    # 4. Balance Quality Summary
    ax = axes[1, 1]
    ax.axis('off')

    # Calculate stats
    mean_signal = np.mean(signals)
    std_signal = np.std(signals)
    cv = (std_signal / mean_signal * 100) if mean_signal > 0 else 0

    diagnostics = config.get('diagnostics', {}).get('led_ranking', {})
    saturated = diagnostics.get('saturated_on_first_pass', [])

    summary_text = f"""
BALANCE QUALITY SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Target Signal: {TARGET_COUNTS:,} counts
Mean Signal: {mean_signal:,.0f} counts
Std Deviation: {std_signal:,.0f} counts
CV: {cv:.1f}% (target: <10%)

Balance Status: {"✅ GOOD" if cv < 10 else "⚠️  POOR" if cv < 20 else "❌ FAILED"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHANNELS AT TARGET (±10%):
{sum(1 for ch in channels if abs(results[ch]['deviation_pct']) <= 10)}/4 channels

CHANNELS SATURATED IN STEP 3:
{', '.join([ch.upper() for ch in saturated]) if saturated else "None"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ISSUE: {"Step 4 saturation bug detected!" if cv > 20 else "No major issues"}
    """

    ax.text(0.1, 0.5, summary_text, transform=ax.transAxes,
            fontsize=11, verticalalignment='center', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    output_file = 'step4_validation_report.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n📊 Validation plot saved to: {output_file}")

    return fig

if __name__ == "__main__":
    try:
        results = analyze_led_balancing()
        print("\n" + "=" * 70)
        print("✅ Validation complete!")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
