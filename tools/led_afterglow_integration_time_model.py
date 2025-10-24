"""
LED Afterglow Characterization - Integration Time Aware
========================================================

Comprehensive characterization of LED phosphor afterglow across multiple
integration times to build integration-time-dependent correction models.

This script:
1. Characterizes all 4 channels (A, B, C, D) at multiple integration times
2. Builds lookup tables: τ(integration_time) for each channel
3. Enables accurate correction regardless of acquisition settings
4. Generates interpolation-ready data for production use

Expected runtime: 40-50 minutes (4 channels × 5 integration times × 5 cycles)

Author: AI Assistant
Date: 2025-10-11
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

# Local imports
from utils.logger import logger as base_logger
from utils.hal.pico_p4spr_hal import PicoP4SPRHAL, ChannelID

try:
    import seabreeze
    seabreeze.use('cseabreeze')
    from seabreeze.spectrometers import list_devices, Spectrometer
except ImportError:
    base_logger.error("SeaBreeze not available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)


def exponential_decay(t: np.ndarray, baseline: float, amplitude: float, tau: float) -> np.ndarray:
    """
    Exponential decay model: signal(t) = baseline + amplitude * exp(-t/tau)

    Args:
        t: Time array (ms)
        baseline: Dark signal baseline (counts)
        amplitude: Initial afterglow amplitude (counts)
        tau: Decay time constant (ms)

    Returns:
        Signal array (counts)
    """
    return baseline + amplitude * np.exp(-t / tau)


def characterize_channel_at_integration_time(
    ctrl: Any,
    spec: Any,
    channel: ChannelID,
    integration_time_ms: int,
    cycles: int = 5
) -> dict[str, Any]:
    """
    Characterize afterglow decay for one channel at specific integration time.

    Args:
        ctrl: Hardware controller (PicoP4SPR)
        spec: Spectrometer instance
        channel: LED channel to test (A, B, C, D)
        integration_time_ms: Integration time in milliseconds
        cycles: Number of measurement cycles for averaging

    Returns:
        Dictionary with decay parameters: baseline, amplitude, tau, R²
    """
    logger.info(f"\n   Channel {channel.name} @ {integration_time_ms}ms integration:")

    # Set integration time
    spec.integration_time_micros(integration_time_ms * 1000)

    # Decay time points to measure (ms after LED turns off)
    # Adjust based on integration time - need enough points for good fit
    if integration_time_ms <= 5:
        decay_times = [0, 1, 2, 3, 5, 10, 15, 20, 30, 50]
    elif integration_time_ms <= 20:
        decay_times = [0, 2, 5, 10, 15, 20, 30, 50, 75, 100]
    else:
        decay_times = [0, 5, 10, 20, 30, 50, 75, 100, 150, 200]

    # Storage for all cycles
    all_measurements = []

    for cycle_num in range(cycles):
        cycle_data = []

        # Measure baseline (all LEDs off)
        ctrl._send_command("lx\n")  # All LEDs off
        time.sleep(0.1)
        baseline_spectrum = spec.intensities()
        baseline = np.mean(baseline_spectrum)

        # Activate LED and stabilize
        ctrl.activate_channel(channel)
        time.sleep(0.1)  # 100ms stabilization

        # Measure peak signal
        peak_spectrum = spec.intensities()
        peak_signal = np.mean(peak_spectrum)

        # Turn off LED and measure decay
        ctrl._send_command("lx\n")  # All LEDs off

        for delay_ms in decay_times:
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            spectrum = spec.intensities()
            signal = np.mean(spectrum)
            cycle_data.append(signal)

        all_measurements.append(cycle_data)

    # Average across cycles
    avg_signals = np.mean(all_measurements, axis=0)
    std_signals = np.std(all_measurements, axis=0)
    decay_times_array = np.array(decay_times, dtype=float)

    # Fit exponential decay
    try:
        # Initial guess
        baseline_guess = avg_signals[-1]  # Signal at longest delay
        amplitude_guess = avg_signals[0] - baseline_guess
        tau_guess = 2.0  # ms

        p0 = [baseline_guess, amplitude_guess, tau_guess]
        bounds = (
            [baseline_guess - 500, 0, 0.1],  # Lower bounds
            [baseline_guess + 500, 5000, 50]  # Upper bounds
        )

        popt, pcov = curve_fit(
            exponential_decay,
            decay_times_array,
            avg_signals,
            p0=p0,
            bounds=bounds,
            maxfev=5000
        )

        baseline_fit, amplitude_fit, tau_fit = popt

        # Calculate R²
        residuals = avg_signals - exponential_decay(decay_times_array, *popt)
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((avg_signals - np.mean(avg_signals))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Calculate recommended delays for different residual thresholds
        delays = {}
        for threshold_pct in [1, 2, 5]:
            # Solve: amplitude * exp(-t/tau) = threshold% * amplitude
            # t = -tau * ln(threshold%)
            threshold_fraction = threshold_pct / 100.0
            if amplitude_fit > 0:
                delay = -tau_fit * np.log(threshold_fraction)
                delays[f"{threshold_pct}pct"] = float(delay)
            else:
                delays[f"{threshold_pct}pct"] = 0.0

        logger.info(f"      τ = {tau_fit:.2f} ms, R² = {r_squared:.4f}, A = {amplitude_fit:.1f} counts")
        logger.info(f"      Delays: 5%={delays['5pct']:.1f}ms, 2%={delays['2pct']:.1f}ms, 1%={delays['1pct']:.1f}ms")

        return {
            'integration_time_ms': integration_time_ms,
            'baseline': float(baseline_fit),
            'amplitude': float(amplitude_fit),
            'tau_ms': float(tau_fit),
            'r_squared': float(r_squared),
            'recommended_delays_ms': delays,
            'decay_times_ms': decay_times,
            'measured_signals': avg_signals.tolist(),
            'signal_std': std_signals.tolist(),
            'peak_signal': float(peak_signal),
            'cycles': cycles,
            'fit_success': True
        }

    except Exception as e:
        logger.warning(f"      ❌ Fit failed: {e}")
        return {
            'integration_time_ms': integration_time_ms,
            'fit_success': False,
            'error': str(e),
            'decay_times_ms': decay_times,
            'measured_signals': avg_signals.tolist(),
            'signal_std': std_signals.tolist()
        }


def characterize_all_channels_all_integration_times(
    ctrl: Any,
    spec: Any,
    channels: list[ChannelID],
    integration_times_ms: list[int],
    cycles: int = 5,
    polarizer_mode: str = 'S'
) -> dict[str, Any]:
    """
    Comprehensive characterization: all channels × all integration times.

    Args:
        ctrl: Hardware controller
        spec: Spectrometer instance
        channels: List of channels to test
        integration_times_ms: List of integration times to test
        cycles: Number of cycles per measurement
        polarizer_mode: 'S' or 'P' mode for polarization state

    Returns:
        Complete characterization data for all channels and integration times
    """
    results = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'polarizer_mode': polarizer_mode,
            'channels_tested': [ch.name for ch in channels],
            'integration_times_ms': integration_times_ms,
            'cycles_per_measurement': cycles,
            'total_measurements': len(channels) * len(integration_times_ms)
        },
        'channel_data': {}
    }

    total_measurements = len(channels) * len(integration_times_ms)
    measurement_count = 0

    for channel in channels:
        logger.info(f"\n{'='*60}")
        logger.info(f"CHARACTERIZING CHANNEL {channel.name}")
        logger.info(f"{'='*60}")

        channel_results = {
            'channel_id': channel.name,
            'integration_time_data': []
        }

        for int_time in integration_times_ms:
            measurement_count += 1
            logger.info(f"\n[{measurement_count}/{total_measurements}] Testing {int_time}ms integration...")

            result = characterize_channel_at_integration_time(
                ctrl, spec, channel, int_time, cycles
            )
            channel_results['integration_time_data'].append(result)

            # Brief pause between measurements
            time.sleep(1.0)

        # Analyze integration time dependency for this channel
        successful_measurements = [
            m for m in channel_results['integration_time_data']
            if m.get('fit_success', False)
        ]

        if len(successful_measurements) >= 2:
            tau_values = [m['tau_ms'] for m in successful_measurements]
            int_times = [m['integration_time_ms'] for m in successful_measurements]

            # Create lookup table for interpolation
            channel_results['tau_lookup'] = {
                'integration_times_ms': int_times,
                'tau_ms': tau_values,
                'mean_tau': float(np.mean(tau_values)),
                'std_tau': float(np.std(tau_values)),
                'min_tau': float(np.min(tau_values)),
                'max_tau': float(np.max(tau_values))
            }

            logger.info(f"\n   📊 Channel {channel.name} Summary:")
            logger.info(f"      τ range: {np.min(tau_values):.2f} - {np.max(tau_values):.2f} ms")
            logger.info(f"      τ mean ± std: {np.mean(tau_values):.2f} ± {np.std(tau_values):.2f} ms")

        results['channel_data'][channel.name] = channel_results

    return results


def plot_integration_time_dependency(results: dict[str, Any], output_dir: Path) -> None:
    """
    Create comprehensive plots showing how τ varies with integration time.

    Args:
        results: Characterization results dictionary
        output_dir: Directory to save plots
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('LED Afterglow: Integration Time Dependency Analysis',
                 fontsize=14, fontweight='bold')

    channels = list(results['channel_data'].keys())
    colors = {'A': 'red', 'B': 'blue', 'C': 'green', 'D': 'orange'}

    for channel_name in channels:
        channel_data = results['channel_data'][channel_name]
        int_time_data = channel_data['integration_time_data']

        # Extract successful measurements
        successful = [m for m in int_time_data if m.get('fit_success', False)]
        if not successful:
            continue

        int_times = [m['integration_time_ms'] for m in successful]
        tau_values = [m['tau_ms'] for m in successful]
        r_squared = [m['r_squared'] for m in successful]
        amplitudes = [m['amplitude'] for m in successful]

        color = colors.get(channel_name, 'gray')

        # Plot 1: Decay constant vs integration time
        axes[0, 0].plot(int_times, tau_values, 'o-', label=f'Channel {channel_name}',
                       color=color, markersize=8, linewidth=2)

        # Plot 2: R² vs integration time
        axes[0, 1].plot(int_times, r_squared, 'o-', label=f'Channel {channel_name}',
                       color=color, markersize=8, linewidth=2)

        # Plot 3: Amplitude vs integration time
        axes[1, 0].plot(int_times, amplitudes, 'o-', label=f'Channel {channel_name}',
                       color=color, markersize=8, linewidth=2)

        # Plot 4: Example decay curve at middle integration time
        if len(successful) >= 3:
            mid_idx = len(successful) // 2
            mid_data = successful[mid_idx]
            decay_times = np.array(mid_data['decay_times_ms'])
            measured = np.array(mid_data['measured_signals'])

            # Fit curve
            fitted = exponential_decay(
                decay_times,
                mid_data['baseline'],
                mid_data['amplitude'],
                mid_data['tau_ms']
            )

            axes[1, 1].plot(decay_times, measured, 'o', label=f'Ch {channel_name} measured',
                           color=color, markersize=6, alpha=0.7)
            axes[1, 1].plot(decay_times, fitted, '-', color=color, linewidth=2,
                           label=f'Ch {channel_name} fit (τ={mid_data["tau_ms"]:.2f}ms)')

    # Format plots
    axes[0, 0].set_xlabel('Integration Time (ms)', fontsize=11)
    axes[0, 0].set_ylabel('Decay Constant τ (ms)', fontsize=11)
    axes[0, 0].set_title('Decay Constant vs Integration Time', fontweight='bold')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_xscale('log')

    axes[0, 1].set_xlabel('Integration Time (ms)', fontsize=11)
    axes[0, 1].set_ylabel('R² (Fit Quality)', fontsize=11)
    axes[0, 1].set_title('Fit Quality vs Integration Time', fontweight='bold')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].set_xscale('log')
    axes[0, 1].axhline(y=0.9, color='gray', linestyle='--', alpha=0.5, label='Good fit threshold')

    axes[1, 0].set_xlabel('Integration Time (ms)', fontsize=11)
    axes[1, 0].set_ylabel('Afterglow Amplitude (counts)', fontsize=11)
    axes[1, 0].set_title('Afterglow Amplitude vs Integration Time', fontweight='bold')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_xscale('log')

    axes[1, 1].set_xlabel('Time After LED Off (ms)', fontsize=11)
    axes[1, 1].set_ylabel('Signal (counts)', fontsize=11)
    axes[1, 1].set_title('Example Decay Curves (Mid Integration Time)', fontweight='bold')
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    output_file = output_dir / 'led_afterglow_integration_time_analysis.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"\n📊 Analysis plot saved: {output_file}")

    plt.show()


def main():
    """Main execution: comprehensive characterization across all channels and integration times."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='LED Afterglow Characterization - Integration Time Aware'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['S', 'P'],
        required=True,
        help='Polarization mode: S (no sensor resonance) or P (sensor resonance)'
    )
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Fast mode for proof of concept (2 integration times, 3 cycles, ~11 min)'
    )
    parser.add_argument(
        '--channels',
        type=str,
        default='A,B,C,D',
        help='Comma-separated list of channels to test (default: A,B,C,D)'
    )
    args = parser.parse_args()

    polarizer_mode = args.mode.upper()

    # Parse channels
    channels = [ch.strip().upper() for ch in args.channels.split(',')]
    for ch in channels:
        if ch not in ['A', 'B', 'C', 'D']:
            parser.error(f"Invalid channel: {ch}. Must be A, B, C, or D")

    print("\n" + "="*60)
    print("🔬 LED AFTERGLOW - INTEGRATION TIME AWARE CHARACTERIZATION")
    print("="*60)
    print(f"\n⚡ Polarization Mode: {polarizer_mode}-signal")

    if args.fast:
        print("\n⚡ FAST MODE - Proof of Concept")
        print("\nThis fast test will:")
        print(f"  • Characterize channel{'s' if len(channels) > 1 else ''} {', '.join(channels)}")
        print("  • At 2 integration times (10, 100 ms)")
        print("  • 3 cycles per measurement")
        print("  • Build τ(integration_time) lookup tables")
        print(f"  • In {polarizer_mode}-mode (polarizer-specific corrections)")
        print(f"\n  Total measurements: {len(channels) * 2} ({len(channels)} channel{'s' if len(channels) > 1 else ''} × 2 integration times)")
        print(f"  Expected runtime: ~{len(channels) * 3} minutes")
    else:
        print("\nThis comprehensive test will:")
        print(f"  • Characterize channel{'s' if len(channels) > 1 else ''} {', '.join(channels)}")
        print("  • At 5 integration times (5, 10, 20, 50, 100 ms)")
        print("  • 5 cycles per measurement for accuracy")
        print("  • Build τ(integration_time) lookup tables")
        print(f"  • In {polarizer_mode}-mode (polarizer-specific corrections)")
        print("\n  Total measurements: 20")
        print("  Expected runtime: 40-50 minutes")

    print("\n" + "="*60)
    print("\nStarting automatically...")
    # input("\nPress ENTER to start...")  # Commented out for automated runs

    # Initialize hardware
    logger.info("🔌 Connecting to hardware...")

    # Initialize controller
    ctrl = PicoP4SPRHAL()
    if not ctrl.connect():
        logger.error("Failed to connect to PicoP4SPR controller")
        return
    logger.info(f"✅ Controller: PicoP4SPR")

    # Set polarizer mode
    try:
        if hasattr(ctrl, 'set_mode'):
            result = ctrl.set_mode(polarizer_mode.lower())
            if result:
                logger.info(f"✅ Polarizer set to {polarizer_mode}-mode")
            else:
                logger.warning(f"⚠️  Polarizer command returned False - may not have moved")
        else:
            logger.error(f"❌ Controller does not have set_mode() method")
            raise RuntimeError("Cannot set polarizer mode - controller missing set_mode()")
    except Exception as e:
        logger.warning(f"⚠️  Could not set polarizer mode (demo hardware?): {e}")
        logger.warning(f"   Assuming polarizer is already in {polarizer_mode}-mode position")

    # Initialize spectrometer
    devices = list_devices()
    if not devices:
        logger.error("No spectrometer found")
        ctrl.disconnect()
        return

    spec = Spectrometer(devices[0])
    logger.info(f"✅ Spectrometer: {spec.model} (S/N: {spec.serial_number})")

    # Convert channel strings to ChannelID enum
    channel_map = {'A': ChannelID.A, 'B': ChannelID.B, 'C': ChannelID.C, 'D': ChannelID.D}
    channel_ids = [channel_map[ch] for ch in channels]

    # Fast mode for proof of concept
    if args.fast:
        integration_times_ms = [10, 100]  # Just 2 integration times (fast interpolation)
        cycles = 3  # Fewer cycles for speed
        logger.info(f"⚡ FAST MODE: 2 integration times, 3 cycles (~{len(channels) * 3} min)")
    else:
        integration_times_ms = [5, 10, 20, 50, 100]  # Full characterization
        cycles = 5  # High accuracy

    # Run characterization
    logger.info("\n" + "="*60)
    logger.info("STARTING COMPREHENSIVE CHARACTERIZATION")
    logger.info("="*60)

    start_time = time.time()

    try:
        results = characterize_all_channels_all_integration_times(
            ctrl, spec, channel_ids, integration_times_ms, cycles, polarizer_mode
        )

        elapsed_time = time.time() - start_time
        results['metadata']['elapsed_time_seconds'] = elapsed_time

        # Save results
        output_dir = Path('generated-files/characterization')
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = output_dir / f'led_afterglow_integration_time_models_{polarizer_mode}mode_{timestamp}.json'

        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"\n{'='*60}")
        logger.info("✅ CHARACTERIZATION COMPLETE!")
        logger.info(f"{'='*60}")
        logger.info(f"⏱️  Total time: {elapsed_time/60:.1f} minutes")
        logger.info(f"💾 Results saved: {json_file}")

        # Generate plots
        plot_integration_time_dependency(results, output_dir)

        # Print summary
        print("\n" + "="*60)
        print("📊 CHARACTERIZATION SUMMARY")
        print("="*60)

        for channel_name in channels:
            channel_data = results['channel_data'][channel_name.name]
            if 'tau_lookup' in channel_data:
                lookup = channel_data['tau_lookup']
                print(f"\nChannel {channel_name.name}:")
                print(f"  τ range: {lookup['min_tau']:.2f} - {lookup['max_tau']:.2f} ms")
                print(f"  τ mean: {lookup['mean_tau']:.2f} ± {lookup['std_tau']:.2f} ms")
                print(f"  Integration times tested: {lookup['integration_times_ms']}")
                print(f"  Corresponding τ values: {[f'{t:.2f}' for t in lookup['tau_ms']]}")

        print("\n" + "="*60)
        print("✅ Data ready for interpolation-based correction!")
        print("="*60)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Characterization interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Error during characterization: {e}", exc_info=True)
    finally:
        # Emergency shutdown
        logger.warning("🚨 EMERGENCY SHUTDOWN - Turning off all LEDs")
        try:
            ctrl._send_command("lx\n")  # All LEDs off
            logger.info("✅ LEDs safely turned off")
        except:
            pass

        logger.info("Emergency LED shutdown completed before disconnect")
        ctrl.disconnect()
        logger.info("Disconnected from PicoP4SPR")

    # input("\nPress ENTER to exit...")  # Commented out for automated runs
    print("\nCalibration complete!")


if __name__ == '__main__':
    main()
