"""LED Afterglow Validation: Integration Time Dependency Test

Comprehensive validation to determine if afterglow correction is universal
or needs adjustment based on integration time and acquisition frequency.

Tests:
1. Measure decay at multiple integration times (1, 2, 5, 10, 20, 50, 100ms)
2. Test rapid multi-channel cycling (worst case - cumulative buildup)
3. Apply correction to live data and validate accuracy

This determines if decay constant τ is truly intrinsic or measurement-dependent.

Usage: python led_afterglow_validation.py

Author: AI Assistant
Date: October 11, 2025
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from utils.device_configuration import get_device_config
from utils.hal.pico_p4spr_hal import ChannelID, PicoP4SPRHAL
from utils.logger import logger

try:
    import seabreeze

    seabreeze.use("cseabreeze")
    from seabreeze.spectrometers import Spectrometer, list_devices
except ImportError:
    logger.error("SeaBreeze not available")


class AfterglowValidator:
    """Validate afterglow correction across different measurement conditions."""

    def __init__(self, ctrl, spec):
        """Initialize validator with hardware."""
        self.ctrl = ctrl
        self.spec = spec
        self.results = {
            "integration_time_tests": {},
            "rapid_cycling_tests": {},
            "cumulative_error_analysis": {},
            "correction_validation": {},
            "timestamp": datetime.now().isoformat(),
        }

    def exponential_decay(self, t, A, tau, baseline):
        """Exponential decay model: signal = baseline + A * exp(-t/tau)"""
        return baseline + A * np.exp(-t / tau)

    def measure_decay_at_integration_time(self, channel, int_time_ms, n_cycles=3):
        """Measure afterglow decay at specific integration time.

        Args:
            channel: LED channel to test
            int_time_ms: Integration time in milliseconds
            n_cycles: Number of cycles to average

        Returns:
            Dict with decay measurements and fitted model

        """
        logger.info(f"\n   Testing integration time: {int_time_ms} ms")

        # Set integration time
        int_time_us = int(int_time_ms * 1000)
        self.spec.integration_time_micros(int_time_us)
        time.sleep(0.05)

        # Measure baseline
        baseline_samples = []
        for _ in range(5):
            spectrum = self.spec.intensities()
            baseline_samples.append(np.mean(spectrum))
            time.sleep(0.01)
        baseline = np.mean(baseline_samples)

        # Decay sampling times (adjusted based on integration time)
        if int_time_ms <= 5:
            decay_times_ms = [0, 1, 2, 3, 5, 10, 15, 20, 30, 50]
        elif int_time_ms <= 20:
            decay_times_ms = [0, 5, 10, 20, 30, 50, 75, 100]
        else:
            decay_times_ms = [0, 10, 20, 50, 100, 150, 200]

        # Run multiple cycles
        all_measurements = []

        for cycle in range(n_cycles):
            cycle_data = []

            # Turn LED on and stabilize
            self.ctrl.activate_channel(channel)
            time.sleep(0.1)

            # Turn LED OFF and measure decay
            self.ctrl._send_command("lx\n")

            for delay_ms in decay_times_ms:
                time.sleep(delay_ms / 1000.0)
                spectrum = self.spec.intensities()
                signal = np.mean(spectrum)
                cycle_data.append(signal)

            all_measurements.append(cycle_data)
            time.sleep(0.2)  # Rest between cycles

        # Average across cycles
        averaged_signals = np.mean(all_measurements, axis=0)
        std_signals = np.std(all_measurements, axis=0)

        # Fit decay model
        try:
            times_arr = np.array(decay_times_ms)

            # Initial guess
            A_guess = max(averaged_signals) - baseline
            tau_guess = int_time_ms  # Guess tau ~ integration time

            popt, pcov = curve_fit(
                lambda t, A, tau: self.exponential_decay(t, A, tau, baseline),
                times_arr,
                averaged_signals,
                p0=[A_guess, tau_guess],
                maxfev=10000,
            )

            A_fit, tau_fit = popt

            # Calculate R-squared
            fitted = self.exponential_decay(times_arr, A_fit, tau_fit, baseline)
            ss_res = np.sum((averaged_signals - fitted) ** 2)
            ss_tot = np.sum((averaged_signals - np.mean(averaged_signals)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            logger.info(f"      τ = {tau_fit:.2f} ms, R² = {r_squared:.4f}")

            return {
                "integration_time_ms": int_time_ms,
                "baseline": float(baseline),
                "amplitude": float(A_fit),
                "tau_ms": float(tau_fit),
                "r_squared": float(r_squared),
                "decay_times": decay_times_ms,
                "measured_signals": averaged_signals.tolist(),
                "signal_std": std_signals.tolist(),
            }

        except Exception as e:
            logger.error(f"      Failed to fit: {e}")
            return {
                "integration_time_ms": int_time_ms,
                "baseline": float(baseline),
                "error": str(e),
            }

    def test_integration_time_dependency(self, channel=ChannelID.D):
        """Test decay measurement at multiple integration times.

        Tests if measured τ changes with integration time.
        """
        logger.info(f"\n{'='*60}")
        logger.info("TEST 1: INTEGRATION TIME DEPENDENCY")
        logger.info(f"{'='*60}")
        logger.info(f"Testing Channel {channel.value.upper()} (fastest decay)")

        # Test multiple integration times
        integration_times_ms = [1, 2, 5, 10, 20, 50, 100]

        results = []
        for int_time_ms in integration_times_ms:
            result = self.measure_decay_at_integration_time(
                channel,
                int_time_ms,
                n_cycles=3,
            )
            results.append(result)
            time.sleep(0.5)

        self.results["integration_time_tests"] = {
            "channel": channel.value,
            "test_integration_times_ms": integration_times_ms,
            "measurements": results,
        }

        # Analyze dependency
        valid_results = [r for r in results if "tau_ms" in r]
        if len(valid_results) >= 3:
            int_times = [r["integration_time_ms"] for r in valid_results]
            taus = [r["tau_ms"] for r in valid_results]

            # Check if tau is constant or varies with integration time
            tau_mean = np.mean(taus)
            tau_std = np.std(taus)
            tau_cv = (tau_std / tau_mean) * 100  # Coefficient of variation (%)

            logger.info("\n📊 Integration Time Dependency Analysis:")
            logger.info(f"   Mean τ: {tau_mean:.2f} ms")
            logger.info(f"   Std τ: {tau_std:.2f} ms")
            logger.info(f"   Coefficient of Variation: {tau_cv:.1f}%")

            if tau_cv < 20:
                logger.info("   ✅ τ is STABLE across integration times (CV < 20%)")
                logger.info("   → Correction is universal!")
            else:
                logger.info(
                    "   ⚠️ τ VARIES significantly with integration time (CV > 20%)",
                )
                logger.info("   → Need integration-time-dependent correction!")

        return results

    def test_rapid_cycling(
        self,
        channels=[ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D],
        int_time_ms=50,
        n_cycles=10,
        inter_channel_delay_ms=5,
    ):
        """Test rapid multi-channel cycling for cumulative buildup.

        Args:
            channels: List of channels to cycle through
            int_time_ms: Integration time
            n_cycles: Number of full cycles (A→B→C→D loops)
            inter_channel_delay_ms: Delay between channel switches

        """
        logger.info(f"\n{'='*60}")
        logger.info("TEST 2: RAPID MULTI-CHANNEL CYCLING")
        logger.info(f"{'='*60}")
        logger.info(f"Integration time: {int_time_ms} ms")
        logger.info(f"Inter-channel delay: {inter_channel_delay_ms} ms")
        logger.info(f"Cycles: {n_cycles} (A→B→C→D loops)")

        # Set integration time
        int_time_us = int(int_time_ms * 1000)
        self.spec.integration_time_micros(int_time_us)
        time.sleep(0.05)

        # Measure baseline
        baseline_samples = []
        for _ in range(5):
            spectrum = self.spec.intensities()
            baseline_samples.append(np.mean(spectrum))
            time.sleep(0.01)
        baseline = np.mean(baseline_samples)

        logger.info(f"\nBaseline: {baseline:.1f} counts")
        logger.info("\nStarting rapid cycling...")

        # Storage for all measurements
        cycle_results = []

        # Run rapid cycling
        for cycle in range(n_cycles):
            cycle_data = {"cycle": cycle + 1, "channels": []}

            for channel in channels:
                # Turn LED on
                self.ctrl.activate_channel(channel)
                time.sleep(inter_channel_delay_ms / 1000.0)

                # Measure
                spectrum = self.spec.intensities()
                signal = np.mean(spectrum)

                cycle_data["channels"].append(
                    {
                        "channel": channel.value,
                        "signal": float(signal),
                        "above_baseline": float(signal - baseline),
                    },
                )

                # Turn LED off
                self.ctrl._send_command("lx\n")
                time.sleep(inter_channel_delay_ms / 1000.0)

            cycle_results.append(cycle_data)

            # Progress update
            if (cycle + 1) % 5 == 0:
                avg_signal = np.mean([ch["signal"] for ch in cycle_data["channels"]])
                logger.info(f"   Cycle {cycle + 1}: avg signal = {avg_signal:.1f}")

        # Analyze for cumulative buildup
        logger.info("\n📊 Rapid Cycling Analysis:")

        # Check if signal drifts over cycles (cumulative buildup indicator)
        for ch_idx, channel in enumerate(channels):
            signals_per_cycle = [
                cycle["channels"][ch_idx]["signal"] for cycle in cycle_results
            ]

            first_5 = np.mean(signals_per_cycle[:5])
            last_5 = np.mean(signals_per_cycle[-5:])
            drift = ((last_5 - first_5) / first_5) * 100

            logger.info(
                f"   Channel {channel.value.upper()}: First 5 cycles = {first_5:.1f}, Last 5 = {last_5:.1f}, Drift = {drift:.2f}%",
            )

            if abs(drift) < 2:
                logger.info("      ✅ Stable (drift < 2%)")
            else:
                logger.info(
                    "      ⚠️ Significant drift detected! Possible cumulative buildup",
                )

        self.results["rapid_cycling_tests"] = {
            "integration_time_ms": int_time_ms,
            "inter_channel_delay_ms": inter_channel_delay_ms,
            "n_cycles": n_cycles,
            "baseline": float(baseline),
            "cycle_data": cycle_results,
        }

        return cycle_results

    def test_correction_accuracy(self, channel=ChannelID.D, int_time_ms=50):
        """Test correction accuracy by comparing predicted vs measured afterglow.

        Uses previously measured τ to predict afterglow, then validates.
        """
        logger.info(f"\n{'='*60}")
        logger.info("TEST 3: CORRECTION ACCURACY VALIDATION")
        logger.info(f"{'='*60}")

        # Load previously measured decay model (from integration time tests)
        int_time_test = self.results.get("integration_time_tests", {})
        measurements = int_time_test.get("measurements", [])

        # Find closest integration time test
        model_data = None
        for m in measurements:
            if m.get("integration_time_ms") == int_time_ms and "tau_ms" in m:
                model_data = m
                break

        if not model_data:
            logger.warning("   No model data available for this integration time!")
            return

        tau = model_data["tau_ms"]
        amplitude = model_data["amplitude"]
        baseline = model_data["baseline"]

        logger.info(
            f"   Using model: τ={tau:.2f}ms, A={amplitude:.1f}, baseline={baseline:.1f}",
        )

        # Test at specific delays
        test_delays_ms = [0, 2, 5, 10, 20, 50]

        logger.info("\n   Testing correction at delays:")

        predictions = []
        measurements_data = []

        for delay_ms in test_delays_ms:
            # Predict afterglow using model
            predicted = baseline + amplitude * np.exp(-delay_ms / tau)

            # Measure actual
            self.ctrl.activate_channel(channel)
            time.sleep(0.1)
            self.ctrl._send_command("lx\n")
            time.sleep(delay_ms / 1000.0)

            spectrum = self.spec.intensities()
            measured = np.mean(spectrum)

            error = measured - predicted
            error_pct = (error / amplitude) * 100

            logger.info(
                f"      {delay_ms:3d} ms: Predicted={predicted:.1f}, Measured={measured:.1f}, Error={error:+.1f} ({error_pct:+.1f}%)",
            )

            predictions.append(float(predicted))
            measurements_data.append(float(measured))

            time.sleep(0.2)

        # Calculate overall prediction accuracy
        predictions_arr = np.array(predictions)
        measured_arr = np.array(measurements_data)

        rmse = np.sqrt(np.mean((measured_arr - predictions_arr) ** 2))
        mae = np.mean(np.abs(measured_arr - predictions_arr))
        mape = np.mean(np.abs((measured_arr - predictions_arr) / amplitude)) * 100

        logger.info("\n   📊 Prediction Accuracy:")
        logger.info(f"      RMSE: {rmse:.2f} counts")
        logger.info(f"      MAE: {mae:.2f} counts")
        logger.info(f"      MAPE: {mape:.1f}% (of amplitude)")

        if mape < 5:
            logger.info("      ✅ EXCELLENT accuracy (MAPE < 5%)")
        elif mape < 10:
            logger.info("      ✅ GOOD accuracy (MAPE < 10%)")
        elif mape < 20:
            logger.info("      ⚠️ MODERATE accuracy (MAPE < 20%)")
        else:
            logger.info(
                "      ❌ POOR accuracy (MAPE > 20%) - Model may not be universal",
            )

        self.results["correction_validation"] = {
            "channel": channel.value,
            "integration_time_ms": int_time_ms,
            "model_tau_ms": float(tau),
            "model_amplitude": float(amplitude),
            "model_baseline": float(baseline),
            "test_delays_ms": test_delays_ms,
            "predicted_signals": predictions,
            "measured_signals": measurements_data,
            "rmse": float(rmse),
            "mae": float(mae),
            "mape": float(mape),
        }


def plot_validation_results(results):
    """Create comprehensive validation plots."""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    fig.suptitle(
        "LED Afterglow Validation: Integration Time & Frequency Dependency",
        fontsize=16,
        fontweight="bold",
    )

    # Plot 1: τ vs Integration Time
    ax1 = fig.add_subplot(gs[0, 0])
    int_time_data = results["integration_time_tests"]["measurements"]
    valid_data = [d for d in int_time_data if "tau_ms" in d]

    int_times = [d["integration_time_ms"] for d in valid_data]
    taus = [d["tau_ms"] for d in valid_data]
    r_squareds = [d["r_squared"] for d in valid_data]

    ax1.plot(int_times, taus, "bo-", markersize=8, linewidth=2)
    ax1.axhline(
        y=np.mean(taus),
        color="r",
        linestyle="--",
        label=f"Mean τ={np.mean(taus):.2f}ms",
    )
    ax1.fill_between(
        int_times,
        np.mean(taus) - np.std(taus),
        np.mean(taus) + np.std(taus),
        alpha=0.3,
        color="red",
    )
    ax1.set_xlabel("Integration Time (ms)", fontsize=11)
    ax1.set_ylabel("Decay constant τ (ms)", fontsize=11)
    ax1.set_title("τ vs Integration Time", fontsize=12, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xscale("log")

    # Plot 2: R² vs Integration Time
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(int_times, r_squareds, "go-", markersize=8, linewidth=2)
    ax2.axhline(y=0.95, color="orange", linestyle="--", label="95% threshold")
    ax2.set_xlabel("Integration Time (ms)", fontsize=11)
    ax2.set_ylabel("R² (fit quality)", fontsize=11)
    ax2.set_title("Fit Quality vs Integration Time", fontsize=12, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_xscale("log")
    ax2.set_ylim([0.9, 1.0])

    # Plot 3: Decay curves at different integration times
    ax3 = fig.add_subplot(gs[0, 2])
    colors = plt.cm.viridis(np.linspace(0, 1, len(valid_data)))

    for idx, data in enumerate(valid_data):
        times = data["decay_times"]
        signals = data["measured_signals"]
        baseline = data["baseline"]
        above_baseline = [s - baseline for s in signals]

        ax3.semilogy(
            times,
            above_baseline,
            "o-",
            color=colors[idx],
            markersize=4,
            label=f'{data["integration_time_ms"]}ms (τ={data["tau_ms"]:.2f})',
        )

    ax3.set_xlabel("Time after LED OFF (ms)", fontsize=11)
    ax3.set_ylabel("Signal above baseline (counts, log)", fontsize=11)
    ax3.set_title(
        "Decay Curves at Different Integration Times",
        fontsize=12,
        fontweight="bold",
    )
    ax3.grid(True, alpha=0.3, which="both")
    ax3.legend(fontsize=8, loc="upper right")

    # Plot 4: Rapid cycling - signal stability
    ax4 = fig.add_subplot(gs[1, :])

    if results.get("rapid_cycling_tests"):
        cycling_data = results["rapid_cycling_tests"]["cycle_data"]

        channels = ["a", "b", "c", "d"]
        colors_ch = {"a": "red", "b": "blue", "c": "green", "d": "orange"}

        for ch_idx, channel in enumerate(channels):
            signals = [cycle["channels"][ch_idx]["signal"] for cycle in cycling_data]
            cycles = [cycle["cycle"] for cycle in cycling_data]

            ax4.plot(
                cycles,
                signals,
                "o-",
                color=colors_ch[channel],
                markersize=4,
                linewidth=1.5,
                label=f"Channel {channel.upper()}",
                alpha=0.7,
            )

        ax4.set_xlabel("Cycle Number", fontsize=11)
        ax4.set_ylabel("Signal (counts)", fontsize=11)
        ax4.set_title(
            "Rapid Multi-Channel Cycling: Signal Stability",
            fontsize=12,
            fontweight="bold",
        )
        ax4.grid(True, alpha=0.3)
        ax4.legend()

    # Plot 5: Correction validation - predicted vs measured
    ax5 = fig.add_subplot(gs[2, 0])

    if results.get("correction_validation"):
        corr_data = results["correction_validation"]
        delays = corr_data["test_delays_ms"]
        predicted = corr_data["predicted_signals"]
        measured = corr_data["measured_signals"]

        ax5.plot(delays, predicted, "b-o", markersize=8, linewidth=2, label="Predicted")
        ax5.plot(delays, measured, "r--s", markersize=8, linewidth=2, label="Measured")
        ax5.set_xlabel("Delay after LED OFF (ms)", fontsize=11)
        ax5.set_ylabel("Signal (counts)", fontsize=11)
        ax5.set_title(
            "Correction Validation: Predicted vs Measured",
            fontsize=12,
            fontweight="bold",
        )
        ax5.grid(True, alpha=0.3)
        ax5.legend()

    # Plot 6: Prediction error
    ax6 = fig.add_subplot(gs[2, 1])

    if results.get("correction_validation"):
        corr_data = results["correction_validation"]
        delays = corr_data["test_delays_ms"]
        predicted = np.array(corr_data["predicted_signals"])
        measured = np.array(corr_data["measured_signals"])
        errors = measured - predicted

        ax6.bar(
            range(len(delays)),
            errors,
            color=["green" if abs(e) < 5 else "orange" for e in errors],
            alpha=0.7,
        )
        ax6.set_xticks(range(len(delays)))
        ax6.set_xticklabels([f"{d}ms" for d in delays])
        ax6.set_xlabel("Delay", fontsize=11)
        ax6.set_ylabel("Prediction Error (counts)", fontsize=11)
        ax6.set_title("Correction Error Analysis", fontsize=12, fontweight="bold")
        ax6.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax6.grid(True, alpha=0.3, axis="y")

        # Add MAPE text
        mape = corr_data.get("mape", 0)
        ax6.text(
            0.98,
            0.95,
            f"MAPE = {mape:.1f}%",
            transform=ax6.transAxes,
            fontsize=10,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    # Plot 7: Summary text
    ax7 = fig.add_subplot(gs[2, 2])
    ax7.axis("off")

    # Generate summary text
    summary_text = "VALIDATION SUMMARY\n" + "=" * 40 + "\n\n"

    if valid_data:
        tau_mean = np.mean(taus)
        tau_std = np.std(taus)
        tau_cv = (tau_std / tau_mean) * 100

        summary_text += "Integration Time Dependency:\n"
        summary_text += f"  Mean τ: {tau_mean:.2f} ± {tau_std:.2f} ms\n"
        summary_text += f"  CV: {tau_cv:.1f}%\n"

        if tau_cv < 20:
            summary_text += "  ✅ τ is STABLE\n"
            summary_text += "  → Universal correction OK\n\n"
        else:
            summary_text += "  ⚠️ τ VARIES significantly\n"
            summary_text += "  → Need time-dependent model\n\n"

    if results.get("correction_validation"):
        mape = results["correction_validation"].get("mape", 0)
        summary_text += "Correction Accuracy:\n"
        summary_text += f"  MAPE: {mape:.1f}%\n"

        if mape < 5:
            summary_text += "  ✅ EXCELLENT\n\n"
        elif mape < 10:
            summary_text += "  ✅ GOOD\n\n"
        else:
            summary_text += "  ⚠️ Needs improvement\n\n"

    summary_text += "Recommendation:\n"
    if tau_cv < 20 and (
        "correction_validation" not in results
        or results["correction_validation"].get("mape", 100) < 10
    ):
        summary_text += "✅ Current correction model\n"
        summary_text += "   is VALID for all tested\n"
        summary_text += "   integration times!\n"
    else:
        summary_text += "⚠️ Consider integration-time-\n"
        summary_text += "   dependent corrections"

    ax7.text(
        0.1,
        0.9,
        summary_text,
        transform=ax7.transAxes,
        fontsize=10,
        verticalalignment="top",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )

    # Save plot
    output_dir = Path("generated-files/characterization")
    output_file = output_dir / "led_afterglow_validation.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.info(f"\n💾 Validation plot saved: {output_file}")

    plt.show()


def connect_hardware():
    """Connect to hardware."""
    logger.info("🔌 Connecting to hardware...")

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


def main():
    """Main execution."""
    print("\n" + "=" * 60)
    print("🔬 LED AFTERGLOW VALIDATION - INTEGRATION TIME DEPENDENCY")
    print("=" * 60)
    print("\nCOMPREHENSIVE TEST (30 minutes)")
    print("\nThis will test:")
    print("  1. Decay at 7 integration times (1-100ms)")
    print("  2. Rapid multi-channel cycling (10 cycles)")
    print("  3. Correction accuracy validation")
    print("\nDetermines if correction is universal or needs adjustment.")
    print("=" * 60)

    input("\nPress ENTER to start...")

    # Load device config
    dev_cfg = get_device_config()
    logger.info(
        f"Device: {dev_cfg.get_optical_fiber_diameter()}µm fiber, {dev_cfg.get_led_pcb_model()} LED",
    )

    # Connect hardware
    ctrl, spec = connect_hardware()

    if not ctrl or not spec:
        logger.error("❌ Hardware connection failed!")
        input("\nPress ENTER to exit...")
        return

    try:
        # Create validator
        validator = AfterglowValidator(ctrl, spec)

        # Test 1: Integration time dependency (use fastest channel D)
        validator.test_integration_time_dependency(channel=ChannelID.D)

        # Test 2: Rapid cycling
        validator.test_rapid_cycling(
            channels=[ChannelID.A, ChannelID.B, ChannelID.C, ChannelID.D],
            int_time_ms=50,
            n_cycles=10,
            inter_channel_delay_ms=5,
        )

        # Test 3: Correction accuracy
        validator.test_correction_accuracy(channel=ChannelID.D, int_time_ms=50)

        # Save results
        output_dir = Path("generated-files/characterization")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"led_afterglow_validation_{timestamp}.json"

        with open(output_file, "w") as f:
            json.dump(validator.results, f, indent=2)

        logger.info(f"\n💾 Results saved to: {output_file}")

        # Plot results
        plot_validation_results(validator.results)

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("✅ VALIDATION COMPLETE!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
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
