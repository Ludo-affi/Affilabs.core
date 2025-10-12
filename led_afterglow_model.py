"""
LED Afterglow Characterization & Correction Model

Performs multiple LED on/off cycles to:
1. Characterize phosphor afterglow decay precisely
2. Fit mathematical model (exponential decay)
3. Generate correction algorithm for multi-channel measurements

This allows optimizing inter-channel delays and correcting for residual afterglow.

Usage: python led_afterglow_model.py

Author: AI Assistant
Date: October 11, 2025
"""

from __future__ import annotations

import time
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy.optimize import curve_fit

from utils.logger import logger
from utils.device_configuration import get_device_config
from utils.hal.pico_p4spr_hal import PicoP4SPRHAL, ChannelID

try:
    import seabreeze
    seabreeze.use('cseabreeze')
    from seabreeze.spectrometers import list_devices, Spectrometer
except ImportError:
    logger.error("SeaBreeze not available")


class LEDAfterglowModel:
    """Model LED phosphor afterglow decay for correction."""

    def __init__(self):
        """Initialize model parameters."""
        self.baseline = 0.0
        self.amplitude = 0.0
        self.tau = 0.0  # Decay time constant (ms)
        self.is_fitted = False

    def decay_function(self, t, A, tau, baseline):
        """
        Exponential decay model: signal = baseline + A * exp(-t/tau)

        Args:
            t: Time after LED turn-off (ms)
            A: Initial amplitude above baseline
            tau: Decay time constant (ms)
            baseline: Background signal level
        """
        return baseline + A * np.exp(-t / tau)

    def fit_decay_data(self, times_ms, signals):
        """
        Fit exponential decay model to measured data.

        Args:
            times_ms: Array of times after LED off (ms)
            signals: Array of measured signals (counts)

        Returns:
            Tuple of (amplitude, tau, baseline, r_squared)
        """
        try:
            # Initial guess
            baseline_guess = min(signals)
            amplitude_guess = max(signals) - baseline_guess
            tau_guess = 30.0  # 30ms initial guess

            # Fit exponential decay
            popt, pcov = curve_fit(
                lambda t, A, tau: self.decay_function(t, A, tau, baseline_guess),
                times_ms,
                signals,
                p0=[amplitude_guess, tau_guess],
                maxfev=10000
            )

            self.amplitude = popt[0]
            self.tau = popt[1]
            self.baseline = baseline_guess

            # Calculate R-squared
            fitted_values = self.decay_function(times_ms, self.amplitude, self.tau, self.baseline)
            ss_res = np.sum((signals - fitted_values) ** 2)
            ss_tot = np.sum((signals - np.mean(signals)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            self.is_fitted = True

            logger.info(f"\n📊 Decay Model Fit:")
            logger.info(f"   Amplitude: {self.amplitude:.2f} counts")
            logger.info(f"   Time constant τ: {self.tau:.2f} ms")
            logger.info(f"   Baseline: {self.baseline:.2f} counts")
            logger.info(f"   R²: {r_squared:.4f}")

            return self.amplitude, self.tau, self.baseline, r_squared

        except Exception as e:
            logger.error(f"Failed to fit decay model: {e}")
            return None, None, None, 0

    def predict_afterglow(self, time_ms):
        """
        Predict afterglow signal at given time after LED turn-off.

        Args:
            time_ms: Time after LED off (ms)

        Returns:
            Predicted signal (counts)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted yet!")

        return self.decay_function(time_ms, self.amplitude, self.tau, self.baseline)

    def calculate_correction(self, time_ms):
        """
        Calculate correction to subtract from measurement.

        Args:
            time_ms: Time since previous LED was turned off (ms)

        Returns:
            Correction value to subtract (counts)
        """
        if not self.is_fitted:
            return 0.0

        # Return afterglow above baseline
        return self.predict_afterglow(time_ms) - self.baseline

    def minimum_delay_for_residual(self, max_residual_percent=1.0):
        """
        Calculate minimum delay for afterglow to decay below threshold.

        Args:
            max_residual_percent: Maximum acceptable residual (% of initial)

        Returns:
            Minimum delay time (ms)
        """
        if not self.is_fitted:
            return 100.0  # Default fallback

        # Solve: residual = A * exp(-t/tau) < (max_residual_percent/100) * A
        # t = -tau * ln(max_residual_percent/100)
        min_delay = -self.tau * np.log(max_residual_percent / 100.0)

        return min_delay


def connect_hardware():
    """Connect to hardware."""
    logger.info("🔌 Connecting to hardware...")

    # Connect controller
    try:
        ctrl = PicoP4SPRHAL()
        if ctrl.connect():
            logger.info(f"✅ Controller: {ctrl.get_device_info()['model']}")
        else:
            logger.error("❌ Controller connection failed")
            return None, None
    except Exception as e:
        logger.error(f"❌ Controller error: {e}")
        return None, None

    # Connect spectrometer
    try:
        devices = list_devices()
        if not devices:
            logger.error("❌ No spectrometer found")
            ctrl.disconnect()
            return None, None

        spec = Spectrometer(devices[0])
        logger.info(f"✅ Spectrometer: {spec.model} (S/N: {spec.serial_number})")

        return ctrl, spec

    except Exception as e:
        logger.error(f"❌ Spectrometer error: {e}")
        if ctrl:
            ctrl.disconnect()
        return None, None


def characterize_afterglow_decay(ctrl, spec, channel=ChannelID.A, n_cycles=5):
    """
    Run multiple LED cycles to characterize afterglow decay.

    Args:
        ctrl: Controller object
        spec: Spectrometer object
        channel: LED channel to test
        n_cycles: Number of on/off cycles to run

    Returns:
        Dictionary with decay characterization results
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🔬 LED AFTERGLOW DECAY CHARACTERIZATION")
    logger.info(f"{'='*60}")
    logger.info(f"Channel: {channel.value.upper()}")
    logger.info(f"Cycles: {n_cycles}")

    # Set fast integration time
    int_time_us = 5000  # 5ms
    spec.integration_time_micros(int_time_us)
    logger.info(f"Integration time: {int_time_us/1000:.1f} ms")

    # Measure baseline
    logger.info("\n1️⃣ Measuring baseline...")
    time.sleep(0.5)
    baseline_samples = []
    for _ in range(10):
        spectrum = spec.intensities()
        baseline_samples.append(np.mean(spectrum))
        time.sleep(0.01)
    baseline = np.mean(baseline_samples)
    logger.info(f"   Baseline: {baseline:.1f} counts")

    # Time points to sample (ms after LED off)
    decay_times_ms = [0, 1, 2, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200]

    # Storage for all cycles
    all_cycle_data = []

    # Run multiple cycles
    logger.info(f"\n2️⃣ Running {n_cycles} LED on/off cycles...")

    for cycle in range(n_cycles):
        logger.info(f"\n   Cycle {cycle + 1}/{n_cycles}:")

        cycle_data = {
            'cycle': cycle + 1,
            'decay_measurements': []
        }

        # Turn LED on and stabilize
        logger.info("      LED ON → stabilizing...")
        ctrl.activate_channel(channel)
        time.sleep(0.1)  # 100ms stabilization

        # Measure LED-on signal
        spectrum = spec.intensities()
        led_on_signal = np.mean(spectrum)
        logger.info(f"      LED ON signal: {led_on_signal:.1f} counts")

        # Turn LED OFF and measure decay at multiple time points
        logger.info("      LED OFF → measuring decay...")
        ctrl._send_command("lx\n")  # All LEDs off

        for delay_ms in decay_times_ms:
            delay_sec = delay_ms / 1000.0
            time.sleep(delay_sec)

            spectrum = spec.intensities()
            signal = np.mean(spectrum)

            cycle_data['decay_measurements'].append({
                'time_ms': delay_ms,
                'signal': float(signal),
                'above_baseline': float(signal - baseline)
            })

        # Report decay at key times
        signal_0ms = cycle_data['decay_measurements'][0]['signal']
        signal_20ms = [m for m in cycle_data['decay_measurements'] if m['time_ms'] == 20][0]['signal']
        signal_100ms = [m for m in cycle_data['decay_measurements'] if m['time_ms'] == 100][0]['signal']

        logger.info(f"      Decay: 0ms={signal_0ms:.0f}, 20ms={signal_20ms:.0f}, 100ms={signal_100ms:.0f}")

        all_cycle_data.append(cycle_data)

        # Wait before next cycle
        time.sleep(0.5)

    # Average across all cycles
    logger.info("\n3️⃣ Averaging across cycles...")

    averaged_decay = []
    for time_idx, time_ms in enumerate(decay_times_ms):
        signals_at_time = [
            cycle['decay_measurements'][time_idx]['signal']
            for cycle in all_cycle_data
        ]

        avg_signal = np.mean(signals_at_time)
        std_signal = np.std(signals_at_time)

        averaged_decay.append({
            'time_ms': time_ms,
            'signal_mean': float(avg_signal),
            'signal_std': float(std_signal),
            'above_baseline_mean': float(avg_signal - baseline),
            'above_baseline_std': float(std_signal)
        })

    # Fit exponential decay model
    logger.info("\n4️⃣ Fitting exponential decay model...")

    times = np.array([d['time_ms'] for d in averaged_decay])
    signals = np.array([d['signal_mean'] for d in averaged_decay])

    model = LEDAfterglowModel()
    amplitude, tau, baseline_fit, r_squared = model.fit_decay_data(times, signals)

    # Calculate recommended delays
    delay_1pct = model.minimum_delay_for_residual(1.0)
    delay_2pct = model.minimum_delay_for_residual(2.0)
    delay_5pct = model.minimum_delay_for_residual(5.0)

    logger.info(f"\n5️⃣ Recommended inter-channel delays:")
    logger.info(f"   For 1% residual: {delay_1pct:.1f} ms")
    logger.info(f"   For 2% residual: {delay_2pct:.1f} ms")
    logger.info(f"   For 5% residual: {delay_5pct:.1f} ms")

    # Compile results
    results = {
        'channel': channel.value,
        'n_cycles': n_cycles,
        'integration_time_us': int_time_us,
        'baseline_counts': float(baseline),
        'decay_model': {
            'amplitude': float(amplitude) if amplitude else 0,
            'tau_ms': float(tau) if tau else 0,
            'baseline': float(baseline_fit) if baseline_fit else float(baseline),
            'r_squared': float(r_squared)
        },
        'recommended_delays': {
            'for_1pct_residual': float(delay_1pct),
            'for_2pct_residual': float(delay_2pct),
            'for_5pct_residual': float(delay_5pct)
        },
        'averaged_decay_data': averaged_decay,
        'all_cycles': all_cycle_data,
        'timestamp': datetime.now().isoformat()
    }

    return results, model


def plot_afterglow_results(results, model):
    """Create comprehensive afterglow visualization."""

    decay_data = results['averaged_decay_data']
    times = np.array([d['time_ms'] for d in decay_data])
    signals_mean = np.array([d['signal_mean'] for d in decay_data])
    signals_std = np.array([d['signal_std'] for d in decay_data])

    baseline = results['baseline_counts']
    amplitude = results['decay_model']['amplitude']
    tau = results['decay_model']['tau_ms']

    # Generate fitted curve
    times_fine = np.linspace(0, max(times), 200)
    fitted_curve = model.decay_function(times_fine, amplitude, tau, baseline)

    # Create figure
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'LED Phosphor Afterglow Characterization - Channel {results["channel"].upper()}',
                 fontsize=16, fontweight='bold')

    # Plot 1: Decay curve (linear) with fit
    ax1.errorbar(times, signals_mean, yerr=signals_std, fmt='ro', markersize=6,
                 capsize=5, label='Measured (mean ± std)')
    ax1.plot(times_fine, fitted_curve, 'b-', linewidth=2, label=f'Exponential fit (τ={tau:.1f}ms)')
    ax1.axhline(y=baseline, color='gray', linestyle='--', linewidth=1, label='Baseline')
    ax1.set_xlabel('Time after LED OFF (ms)', fontsize=12)
    ax1.set_ylabel('Signal (counts)', fontsize=12)
    ax1.set_title('Afterglow Decay Curve (Linear Scale)', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Plot 2: Decay curve (log scale)
    above_baseline = signals_mean - baseline
    above_baseline[above_baseline <= 0] = 0.1  # Avoid log(0)

    ax2.semilogy(times, above_baseline, 'ro', markersize=6, label='Measured')
    fitted_above_baseline = fitted_curve - baseline
    ax2.semilogy(times_fine, fitted_above_baseline, 'b-', linewidth=2,
                 label=f'Exponential fit (τ={tau:.1f}ms)')
    ax2.set_xlabel('Time after LED OFF (ms)', fontsize=12)
    ax2.set_ylabel('Signal above baseline (counts, log)', fontsize=12)
    ax2.set_title('Afterglow Decay (Log Scale)', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3, which='both')
    ax2.legend()

    # Plot 3: Residual afterglow vs time
    residual_percent = (above_baseline / amplitude) * 100
    ax3.plot(times, residual_percent, 'go-', markersize=6, linewidth=2)
    ax3.axhline(y=5, color='orange', linestyle='--', label='5% threshold')
    ax3.axhline(y=2, color='red', linestyle='--', label='2% threshold')
    ax3.axhline(y=1, color='purple', linestyle='--', label='1% threshold')
    ax3.set_xlabel('Time after LED OFF (ms)', fontsize=12)
    ax3.set_ylabel('Residual afterglow (% of initial)', fontsize=12)
    ax3.set_title('Residual Afterglow Over Time', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    ax3.set_ylim([0, 110])

    # Plot 4: Correction algorithm visualization
    correction_times = np.arange(0, 200, 5)
    corrections = [model.calculate_correction(t) for t in correction_times]

    ax4.plot(correction_times, corrections, 'b-', linewidth=2)
    ax4.fill_between(correction_times, 0, corrections, alpha=0.3)
    ax4.set_xlabel('Time since previous LED OFF (ms)', fontsize=12)
    ax4.set_ylabel('Correction to subtract (counts)', fontsize=12)
    ax4.set_title('Afterglow Correction Algorithm', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)

    # Add recommended delay markers
    delay_5pct = results['recommended_delays']['for_5pct_residual']
    delay_2pct = results['recommended_delays']['for_2pct_residual']
    delay_1pct = results['recommended_delays']['for_1pct_residual']

    ax4.axvline(x=delay_5pct, color='orange', linestyle='--', alpha=0.7, label=f'5% residual: {delay_5pct:.0f}ms')
    ax4.axvline(x=delay_2pct, color='red', linestyle='--', alpha=0.7, label=f'2% residual: {delay_2pct:.0f}ms')
    ax4.axvline(x=delay_1pct, color='purple', linestyle='--', alpha=0.7, label=f'1% residual: {delay_1pct:.0f}ms')
    ax4.legend(loc='upper right')

    plt.tight_layout()

    # Save plot
    output_dir = Path("generated-files/characterization")
    output_file = output_dir / "led_afterglow_model.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"\n💾 Plot saved: {output_file}")

    plt.show()


def plot_all_channels_comparison(all_channel_results):
    """Create comparison plot for all 4 channels."""

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('LED Afterglow Comparison - All 4 Channels', fontsize=16, fontweight='bold')

    colors = {'a': 'red', 'b': 'blue', 'c': 'green', 'd': 'orange'}

    # Plot 1: Decay curves (linear)
    for channel, results in all_channel_results.items():
        decay_data = results['averaged_decay_data']
        times = [d['time_ms'] for d in decay_data]
        signals = [d['signal_mean'] for d in decay_data]
        baseline = results['baseline_counts']

        ax1.plot(times, signals, 'o-', color=colors[channel], markersize=4,
                linewidth=2, label=f'Channel {channel.upper()}')

    ax1.set_xlabel('Time after LED OFF (ms)', fontsize=12)
    ax1.set_ylabel('Signal (counts)', fontsize=12)
    ax1.set_title('Decay Curves - All Channels', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Plot 2: Decay curves (log scale)
    for channel, results in all_channel_results.items():
        decay_data = results['averaged_decay_data']
        times = [d['time_ms'] for d in decay_data]
        signals = [d['signal_mean'] for d in decay_data]
        baseline = results['baseline_counts']
        above_baseline = [max(s - baseline, 0.1) for s in signals]

        ax2.semilogy(times, above_baseline, 'o-', color=colors[channel], markersize=4,
                    linewidth=2, label=f'Channel {channel.upper()} (τ={results["decay_model"]["tau_ms"]:.2f}ms)')

    ax2.set_xlabel('Time after LED OFF (ms)', fontsize=12)
    ax2.set_ylabel('Signal above baseline (counts, log)', fontsize=12)
    ax2.set_title('Decay Curves - Log Scale', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3, which='both')
    ax2.legend()

    # Plot 3: Decay time constants comparison
    channels = list(all_channel_results.keys())
    taus = [all_channel_results[ch]['decay_model']['tau_ms'] for ch in channels]
    channel_labels = [ch.upper() for ch in channels]

    bars = ax3.bar(channel_labels, taus, color=[colors[ch] for ch in channels], alpha=0.7)
    ax3.set_ylabel('Decay time constant τ (ms)', fontsize=12)
    ax3.set_title('Decay Time Constants by Channel', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bar, tau in zip(bars, taus):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{tau:.2f} ms', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Plot 4: Recommended delays comparison
    delays_5pct = [all_channel_results[ch]['recommended_delays']['for_5pct_residual'] for ch in channels]
    delays_2pct = [all_channel_results[ch]['recommended_delays']['for_2pct_residual'] for ch in channels]
    delays_1pct = [all_channel_results[ch]['recommended_delays']['for_1pct_residual'] for ch in channels]

    x = np.arange(len(channels))
    width = 0.25

    ax4.bar(x - width, delays_5pct, width, label='5% residual', alpha=0.7)
    ax4.bar(x, delays_2pct, width, label='2% residual', alpha=0.7)
    ax4.bar(x + width, delays_1pct, width, label='1% residual', alpha=0.7)

    ax4.set_xlabel('Channel', fontsize=12)
    ax4.set_ylabel('Recommended delay (ms)', fontsize=12)
    ax4.set_title('Recommended Inter-Channel Delays', fontsize=13, fontweight='bold')
    ax4.set_xticks(x)
    ax4.set_xticklabels(channel_labels)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    # Save plot
    output_dir = Path("generated-files/characterization")
    output_file = output_dir / "led_afterglow_all_channels.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"\n💾 Comparison plot saved: {output_file}")

    plt.show()


def main():
    """Main execution."""
    print("\n" + "="*60)
    print("🔬 LED AFTERGLOW DECAY CHARACTERIZATION - ALL 4 CHANNELS")
    print("="*60)
    print("\nThis will:")
    print("  • Test all 4 LED channels (A, B, C, D)")
    print("  • Run multiple LED on/off cycles per channel")
    print("  • Characterize phosphor afterglow decay")
    print("  • Fit exponential decay model for each")
    print("  • Generate channel-specific correction algorithms")
    print("="*60)

    input("\nPress ENTER to start...")

    # Load device config
    dev_cfg = get_device_config()
    logger.info(f"Device: {dev_cfg.get_optical_fiber_diameter()}µm fiber, {dev_cfg.get_led_pcb_model()} LED")

    # Connect hardware
    ctrl, spec = connect_hardware()

    if not ctrl or not spec:
        logger.error("❌ Hardware connection failed!")
        input("\nPress ENTER to exit...")
        return

    try:
        # Test all 4 channels
        channels = [ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D]
        all_results = {}
        all_models = {}

        for channel in channels:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing Channel {channel.value.upper()}")
            logger.info(f"{'='*60}")

            # Run afterglow characterization
            results, model = characterize_afterglow_decay(ctrl, spec, channel, n_cycles=5)

            all_results[channel.value] = results
            all_models[channel.value] = model

            # Brief pause between channels
            time.sleep(1.0)

        # Save all results
        output_dir = Path("generated-files/characterization")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"led_afterglow_all_channels_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)

        logger.info(f"\n💾 All results saved to: {output_file}")

        # Plot individual channel results
        for channel in channels:
            plot_afterglow_results(all_results[channel.value], all_models[channel.value])

        # Plot comparison of all channels
        plot_all_channels_comparison(all_results)

        # Summary
        logger.info("\n" + "="*60)
        logger.info("✅ ALL CHANNELS CHARACTERIZATION COMPLETE!")
        logger.info("="*60)

        for channel in channels:
            results = all_results[channel.value]
            logger.info(f"\n📊 Channel {channel.value.upper()} Decay Model:")
            logger.info(f"   τ = {results['decay_model']['tau_ms']:.2f} ms, R² = {results['decay_model']['r_squared']:.4f}")
            logger.info(f"   Delays: 5%={results['recommended_delays']['for_5pct_residual']:.1f}ms, " +
                       f"2%={results['recommended_delays']['for_2pct_residual']:.1f}ms, " +
                       f"1%={results['recommended_delays']['for_1pct_residual']:.1f}ms")

        # Calculate overall recommendation
        max_delay_1pct = max(all_results[ch.value]['recommended_delays']['for_1pct_residual'] for ch in channels)
        max_delay_2pct = max(all_results[ch.value]['recommended_delays']['for_2pct_residual'] for ch in channels)
        max_delay_5pct = max(all_results[ch.value]['recommended_delays']['for_5pct_residual'] for ch in channels)

        logger.info(f"\n⏱️ Overall Recommended Inter-Channel Delays (worst case across all channels):")
        logger.info(f"   Fast (5% residual): {max_delay_5pct:.0f} ms")
        logger.info(f"   Balanced (2% residual): {max_delay_2pct:.0f} ms")
        logger.info(f"   Precise (1% residual): {max_delay_1pct:.0f} ms")

    except Exception as e:
        logger.error(f"❌ Characterization failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        try:
            if spec:
                spec.close()
            if ctrl:
                ctrl.disconnect()
        except:
            pass

    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
