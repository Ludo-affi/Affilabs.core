"""LED Timing and Optical Performance Characterization Tool

This tool characterizes the optical performance of your SPR system:
1. LED rise/fall times (switching speed)
2. LED intensity vs counts relationship
3. Optimal integration time vs signal level
4. Channel balance and uniformity
5. Recommended operating parameters

Outputs:
- LED timing parameters (rise/fall times, optimal delay)
- Intensity calibration curves for each channel
- Integration time recommendations
- Device-specific performance profile

Usage:
    python led_timing_characterization.py

Author: AI Assistant
Date: October 11, 2025
"""

import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from utils.device_configuration import get_device_config
from utils.hal import HALFactory
from utils.logger import logger


class LEDTimingCharacterization:
    """Characterize LED timing and optical performance."""

    def __init__(self):
        """Initialize characterization tool."""
        self.device_config = get_device_config()

        # Hardware references
        self.ctrl = None
        self.usb = None  # Results storage
        self.results = {
            "device_info": {},
            "led_timing": {},
            "intensity_curves": {},
            "integration_times": {},
            "recommendations": {},
            "timestamp": datetime.now().isoformat(),
        }

        # Output directory
        self.output_dir = Path("generated-files/characterization")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def connect_hardware(self) -> bool:
        """Connect to hardware using HALFactory (same as main app)."""
        try:
            logger.info("🔌 Connecting to hardware...")

            # Connect controller (auto-detect)
            try:
                self.ctrl = HALFactory.create_controller(auto_detect=True)
                ctrl_info = self.ctrl.get_device_info()
                logger.info(f"✅ Controller: {ctrl_info.get('model', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ Controller connection failed: {e}")
                return False

            # Connect spectrometer
            try:
                self.usb = HALFactory.create_spectrometer(auto_detect=True)
                spec_info = self.usb.get_device_info()
                logger.info(f"✅ Spectrometer: {spec_info.get('model', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ Spectrometer connection failed: {e}")
                if self.ctrl:
                    self.ctrl.disconnect()
                return False

            # Store device info
            self.results["device_info"] = {
                "controller_type": ctrl_info.get("model", "Unknown"),
                "controller_serial": ctrl_info.get("serial_number", "Unknown"),
                "spectrometer_type": spec_info.get("model", "Unknown"),
                "spectrometer_serial": spec_info.get("serial_number", "Unknown"),
                "optical_fiber_um": self.device_config.get_optical_fiber_diameter(),
                "led_pcb_model": self.device_config.get_led_pcb_model(),
            }

            return True

        except Exception as e:
            logger.error(f"❌ Hardware connection failed: {e}")
            return False

    def characterize_led_timing(self, channel: str = "a") -> dict:
        """Characterize LED rise and fall times.

        Args:
            channel: LED channel to test ('a', 'b', 'c', 'd')

        Returns:
            Dict with timing measurements

        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 LED TIMING CHARACTERIZATION - Channel {channel.upper()}")
        logger.info(f"{'='*60}")

        try:
            # Set fast integration time for timing measurements
            fast_integration_ms = 5
            self.usb.set_integration_time(fast_integration_ms)

            # Turn off all LEDs
            self.ctrl.turn_off_all_leds()
            time.sleep(0.5)

            # Measure baseline (LED off)
            logger.info("1️⃣ Measuring baseline (LED OFF)...")
            baseline_samples = []
            for _ in range(10):
                spectrum = self.usb.acquire_spectrum()
                baseline_samples.append(np.mean(spectrum))
                time.sleep(0.01)
            baseline = np.mean(baseline_samples)
            logger.info(f"   Baseline: {baseline:.1f} counts")

            # Test different LED delays to find rise time
            logger.info("\n2️⃣ Testing LED rise time...")
            delays_ms = [0, 2, 5, 10, 15, 20, 30, 50, 100]
            rise_measurements = []

            for delay_ms in delays_ms:
                delay_sec = delay_ms / 1000.0

                # Turn LED on, wait delay, then measure
                self.ctrl.set_led_intensity(channel, 255)
                time.sleep(delay_sec)
                spectrum = self.usb.acquire_spectrum()
                signal = np.mean(spectrum)
                self.ctrl.set_led_intensity(channel, 0)
                time.sleep(0.1)  # Let LED fully turn off

                rise_measurements.append(
                    {
                        "delay_ms": delay_ms,
                        "signal": signal,
                        "percent_of_max": 0,  # Will calculate after finding max
                    },
                )

                logger.info(f"   Delay {delay_ms:3d} ms → Signal: {signal:6.1f} counts")

            # Calculate percent of max
            max_signal = max(m["signal"] for m in rise_measurements)
            for m in rise_measurements:
                m["percent_of_max"] = (m["signal"] / max_signal) * 100

            # Find 90% and 95% rise times
            rise_90_delay = next(
                (m["delay_ms"] for m in rise_measurements if m["percent_of_max"] >= 90),
                delays_ms[-1],
            )
            rise_95_delay = next(
                (m["delay_ms"] for m in rise_measurements if m["percent_of_max"] >= 95),
                delays_ms[-1],
            )

            logger.info("\n   📈 Rise Time Analysis:")
            logger.info(f"      90% signal: {rise_90_delay} ms")
            logger.info(f"      95% signal: {rise_95_delay} ms")

            # Test fall time
            logger.info("\n3️⃣ Testing LED fall time...")

            # Turn LED fully on
            self.ctrl.set_led_intensity(channel, 255)
            time.sleep(0.1)  # Let it stabilize

            # Turn off and measure at different delays
            fall_measurements = []
            for delay_ms in delays_ms:
                delay_sec = delay_ms / 1000.0

                # Turn on, stabilize
                self.ctrl.set_led_intensity(channel, 255)
                time.sleep(0.05)

                # Turn off, wait delay, then measure
                self.ctrl.set_led_intensity(channel, 0)
                time.sleep(delay_sec)
                spectrum = self.usb.acquire_spectrum()
                signal = np.mean(spectrum)

                fall_measurements.append(
                    {
                        "delay_ms": delay_ms,
                        "signal": signal,
                        "percent_of_baseline": (
                            (signal - baseline) / (max_signal - baseline)
                        )
                        * 100
                        if max_signal > baseline
                        else 0,
                    },
                )

                logger.info(
                    f"   Delay {delay_ms:3d} ms → Signal: {signal:6.1f} counts ({fall_measurements[-1]['percent_of_baseline']:.1f}% above baseline)",
                )

                time.sleep(0.1)

            # Find 10% and 5% fall times (when signal drops to near baseline)
            fall_10_delay = next(
                (
                    m["delay_ms"]
                    for m in fall_measurements
                    if m["percent_of_baseline"] <= 10
                ),
                delays_ms[-1],
            )
            fall_5_delay = next(
                (
                    m["delay_ms"]
                    for m in fall_measurements
                    if m["percent_of_baseline"] <= 5
                ),
                delays_ms[-1],
            )

            logger.info("\n   📉 Fall Time Analysis:")
            logger.info(f"      10% above baseline: {fall_10_delay} ms")
            logger.info(f"      5% above baseline: {fall_5_delay} ms")

            # Calculate recommended LED delay
            # Use the longer of rise or fall time, plus safety margin
            recommended_delay_ms = (
                max(rise_95_delay, fall_5_delay) + 5
            )  # +5ms safety margin

            logger.info(f"\n   ✅ Recommended LED Delay: {recommended_delay_ms} ms")

            # Store results
            timing_results = {
                "channel": channel,
                "baseline_counts": float(baseline),
                "max_signal_counts": float(max_signal),
                "rise_time_90pct_ms": int(rise_90_delay),
                "rise_time_95pct_ms": int(rise_95_delay),
                "fall_time_10pct_ms": int(fall_10_delay),
                "fall_time_5pct_ms": int(fall_5_delay),
                "recommended_delay_ms": int(recommended_delay_ms),
                "rise_measurements": rise_measurements,
                "fall_measurements": fall_measurements,
            }

            self.results["led_timing"][channel] = timing_results

            return timing_results

        except Exception as e:
            logger.error(f"❌ LED timing characterization failed: {e}")
            return {}

    def characterize_intensity_vs_counts(self, channel: str = "a") -> dict:
        """Characterize LED intensity vs detector counts relationship.

        Args:
            channel: LED channel to test

        Returns:
            Dict with intensity curve data

        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 INTENSITY CURVE - Channel {channel.upper()}")
        logger.info(f"{'='*60}")

        try:
            # Use medium integration time
            integration_ms = 50
            self.usb.set_integration_time(integration_ms)

            # Test intensity range
            intensities = [0, 16, 32, 64, 96, 128, 160, 192, 224, 255]
            measurements = []

            logger.info(f"Testing {len(intensities)} intensity levels...")

            for intensity in intensities:
                self.ctrl.set_led_intensity(channel, intensity)
                time.sleep(0.05)  # Let LED stabilize

                # Average multiple measurements
                samples = []
                for _ in range(3):
                    spectrum = self.usb.acquire_spectrum()
                    samples.append(np.mean(spectrum))
                    time.sleep(0.01)

                mean_signal = np.mean(samples)
                std_signal = np.std(samples)

                measurements.append(
                    {
                        "intensity": intensity,
                        "counts": float(mean_signal),
                        "std": float(std_signal),
                    },
                )

                logger.info(
                    f"   Intensity {intensity:3d} → {mean_signal:7.1f} ± {std_signal:5.1f} counts",
                )

            self.ctrl.set_led_intensity(channel, 0)

            # Analyze linearity
            intensities_array = np.array([m["intensity"] for m in measurements])
            counts_array = np.array([m["counts"] for m in measurements])

            # Linear fit
            coeffs = np.polyfit(intensities_array, counts_array, 1)
            slope, intercept = coeffs

            # R-squared
            predicted = np.polyval(coeffs, intensities_array)
            ss_res = np.sum((counts_array - predicted) ** 2)
            ss_tot = np.sum((counts_array - np.mean(counts_array)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            logger.info("\n   📈 Linearity Analysis:")
            logger.info(f"      Slope: {slope:.2f} counts/intensity")
            logger.info(f"      Intercept: {intercept:.1f} counts")
            logger.info(f"      R²: {r_squared:.4f}")

            curve_results = {
                "channel": channel,
                "integration_time_ms": integration_ms,
                "measurements": measurements,
                "linear_fit": {
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r_squared),
                },
            }

            self.results["intensity_curves"][channel] = curve_results

            return curve_results

        except Exception as e:
            logger.error(f"❌ Intensity characterization failed: {e}")
            return {}

    def find_optimal_integration_time(
        self,
        channel: str = "a",
        target_percent: float = 80.0,
    ) -> dict:
        """Find optimal integration time for target signal level.

        Args:
            channel: LED channel to test
            target_percent: Target signal as percent of detector max

        Returns:
            Dict with integration time recommendations

        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 INTEGRATION TIME OPTIMIZATION - Channel {channel.upper()}")
        logger.info(f"{'='*60}")

        try:
            # Get detector max from device config or use default
            detector_max = 65535  # USB4000/Flame-T default
            target_counts = detector_max * (target_percent / 100.0)

            logger.info(
                f"Target: {target_percent}% of {detector_max} = {target_counts:.0f} counts",
            )

            # Test LED intensity = 255 (maximum)
            self.ctrl.set_led_intensity(channel, 255)
            time.sleep(0.05)

            # Test different integration times
            integration_times_ms = [5, 10, 20, 30, 50, 75, 100, 150, 200]
            measurements = []

            logger.info(f"\nTesting {len(integration_times_ms)} integration times...")

            for int_time_ms in integration_times_ms:
                self.usb.set_integration_time(int_time_ms)
                time.sleep(0.02)

                # Average measurements
                samples = []
                for _ in range(3):
                    spectrum = self.usb.acquire_spectrum()
                    samples.append(np.max(spectrum))  # Use max for saturation check
                    time.sleep(0.01)

                max_signal = np.mean(samples)
                percent_of_max = (max_signal / detector_max) * 100

                measurements.append(
                    {
                        "integration_time_ms": int_time_ms,
                        "max_counts": float(max_signal),
                        "percent_of_detector_max": float(percent_of_max),
                        "saturated": max_signal >= detector_max * 0.95,
                    },
                )

                status = "⚠️ SATURATED" if measurements[-1]["saturated"] else "✅"
                logger.info(
                    f"   {int_time_ms:3d} ms → {max_signal:7.1f} counts ({percent_of_max:5.1f}%) {status}",
                )

            self.ctrl.set_led_intensity(channel, 0)

            # Find closest to target without saturation
            valid_measurements = [m for m in measurements if not m["saturated"]]

            if valid_measurements:
                optimal = min(
                    valid_measurements,
                    key=lambda m: abs(m["percent_of_detector_max"] - target_percent),
                )
                optimal_int_time = optimal["integration_time_ms"]

                logger.info(f"\n   ✅ Optimal Integration Time: {optimal_int_time} ms")
                logger.info(
                    f"      Achieves {optimal['percent_of_detector_max']:.1f}% of detector max",
                )
            else:
                optimal_int_time = integration_times_ms[0]
                logger.warning("\n   ⚠️ All integration times saturated!")
                logger.warning(f"      Using minimum: {optimal_int_time} ms")

            int_results = {
                "channel": channel,
                "target_percent": target_percent,
                "detector_max_counts": detector_max,
                "optimal_integration_ms": optimal_int_time,
                "measurements": measurements,
            }

            self.results["integration_times"][channel] = int_results

            return int_results

        except Exception as e:
            logger.error(f"❌ Integration time optimization failed: {e}")
            return {}

    def generate_recommendations(self):
        """Generate recommended operating parameters based on measurements."""
        logger.info(f"\n{'='*60}")
        logger.info("📋 GENERATING RECOMMENDATIONS")
        logger.info(f"{'='*60}")

        try:
            # Analyze LED timing results
            timing_data = list(self.results["led_timing"].values())
            if timing_data:
                max_rise_time = max(t["rise_time_95pct_ms"] for t in timing_data)
                max_fall_time = max(t["fall_time_5pct_ms"] for t in timing_data)
                recommended_delay = max(max_rise_time, max_fall_time) + 5

                # Calculate max safe frequency
                # Cycle time = 4 channels × (LED delay + integration time)
                # Assume 100ms integration time as typical
                typical_integration_ms = 100
                cycle_time_ms = 4 * (recommended_delay + typical_integration_ms)
                max_frequency_hz = 1000.0 / cycle_time_ms

                self.results["recommendations"] = {
                    "led_delay_ms": recommended_delay,
                    "max_safe_frequency_hz": round(max_frequency_hz, 2),
                    "recommended_frequency_hz": round(
                        max_frequency_hz * 0.8,
                        2,
                    ),  # 80% of max for safety
                    "typical_integration_time_ms": typical_integration_ms,
                    "cycle_time_ms": cycle_time_ms,
                }

                logger.info("\n✅ RECOMMENDED PARAMETERS:")
                logger.info(f"   LED Delay: {recommended_delay} ms")
                logger.info(f"   Max Frequency: {max_frequency_hz:.2f} Hz")
                logger.info(
                    f"   Recommended Frequency: {max_frequency_hz * 0.8:.2f} Hz",
                )
                logger.info(f"   Typical Integration Time: {typical_integration_ms} ms")

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")

    def save_results(self):
        """Save characterization results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"led_characterization_{timestamp}.json"

        try:
            with open(output_file, "w") as f:
                json.dump(self.results, f, indent=2)

            logger.info(f"\n💾 Results saved to: {output_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def plot_results(self):
        """Generate plots of characterization results."""
        logger.info("\n📊 Generating plots...")

        try:
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(
                "LED Optical Performance Characterization",
                fontsize=16,
                fontweight="bold",
            )

            # Plot 1: LED Rise Time
            ax1 = axes[0, 0]
            for channel, data in self.results["led_timing"].items():
                delays = [m["delay_ms"] for m in data["rise_measurements"]]
                signals = [m["percent_of_max"] for m in data["rise_measurements"]]
                ax1.plot(
                    delays,
                    signals,
                    marker="o",
                    label=f"Channel {channel.upper()}",
                )
            ax1.axhline(y=90, color="r", linestyle="--", label="90% threshold")
            ax1.axhline(y=95, color="g", linestyle="--", label="95% threshold")
            ax1.set_xlabel("Delay (ms)")
            ax1.set_ylabel("Signal (% of max)")
            ax1.set_title("LED Rise Time Characterization")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Plot 2: Intensity vs Counts
            ax2 = axes[0, 1]
            for channel, data in self.results["intensity_curves"].items():
                intensities = [m["intensity"] for m in data["measurements"]]
                counts = [m["counts"] for m in data["measurements"]]
                ax2.plot(
                    intensities,
                    counts,
                    marker="o",
                    label=f"Channel {channel.upper()}",
                )
            ax2.set_xlabel("LED Intensity (0-255)")
            ax2.set_ylabel("Detector Counts")
            ax2.set_title("LED Intensity vs Detector Response")
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            # Plot 3: Integration Time Optimization
            ax3 = axes[1, 0]
            for channel, data in self.results["integration_times"].items():
                int_times = [m["integration_time_ms"] for m in data["measurements"]]
                percentages = [
                    m["percent_of_detector_max"] for m in data["measurements"]
                ]
                ax3.plot(
                    int_times,
                    percentages,
                    marker="o",
                    label=f"Channel {channel.upper()}",
                )
            ax3.axhline(y=80, color="g", linestyle="--", label="80% target")
            ax3.axhline(y=95, color="r", linestyle="--", label="95% saturation")
            ax3.set_xlabel("Integration Time (ms)")
            ax3.set_ylabel("Signal (% of detector max)")
            ax3.set_title("Integration Time Optimization")
            ax3.legend()
            ax3.grid(True, alpha=0.3)

            # Plot 4: Summary Table
            ax4 = axes[1, 1]
            ax4.axis("off")

            # Create summary table
            summary_data = []
            if self.results["recommendations"]:
                rec = self.results["recommendations"]
                summary_data = [
                    ["Parameter", "Value"],
                    ["LED Delay", f"{rec['led_delay_ms']} ms"],
                    ["Max Frequency", f"{rec['max_safe_frequency_hz']:.2f} Hz"],
                    ["Recommended Freq", f"{rec['recommended_frequency_hz']:.2f} Hz"],
                    ["Integration Time", f"{rec['typical_integration_time_ms']} ms"],
                    ["Cycle Time", f"{rec['cycle_time_ms']:.0f} ms"],
                ]

            if summary_data:
                table = ax4.table(
                    cellText=summary_data,
                    cellLoc="left",
                    loc="center",
                    colWidths=[0.5, 0.5],
                )
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1, 2)

                # Style header row
                for i in range(2):
                    table[(0, i)].set_facecolor("#4CAF50")
                    table[(0, i)].set_text_props(weight="bold", color="white")

            ax4.set_title("Recommended Operating Parameters", fontweight="bold", pad=20)

            plt.tight_layout()

            # Save plot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_file = self.output_dir / f"characterization_plots_{timestamp}.png"
            plt.savefig(plot_file, dpi=150, bbox_inches="tight")

            logger.info(f"📊 Plots saved to: {plot_file}")

            plt.show()

        except Exception as e:
            logger.error(f"Failed to generate plots: {e}")

    def run_full_characterization(self):
        """Run complete characterization sequence."""
        logger.info("\n" + "=" * 60)
        logger.info("🔬 LED OPTICAL PERFORMANCE CHARACTERIZATION")
        logger.info("=" * 60)
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Fiber: {self.device_config.get_optical_fiber_diameter()} µm")
        logger.info(f"LED PCB: {self.device_config.get_led_pcb_model()}")
        logger.info("=" * 60)

        try:
            # Connect hardware
            if not self.connect_hardware():
                logger.error("❌ Cannot proceed without hardware")
                return False

            # Test channel 'a' (can extend to all channels)
            test_channel = "a"

            # 1. LED Timing
            self.characterize_led_timing(test_channel)

            # 2. Intensity Curve
            self.characterize_intensity_vs_counts(test_channel)

            # 3. Integration Time
            self.find_optimal_integration_time(test_channel)

            # 4. Generate Recommendations
            self.generate_recommendations()

            # 5. Save Results
            self.save_results()

            # 6. Plot Results
            self.plot_results()

            logger.info("\n" + "=" * 60)
            logger.info("✅ CHARACTERIZATION COMPLETE!")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"❌ Characterization failed: {e}")
            return False

        finally:
            # Cleanup
            if self.ctrl:
                try:
                    self.ctrl.turn_off_all_leds()
                except:
                    pass


def main():
    """Main execution function."""
    print("\n" + "=" * 60)
    print("🔬 LED TIMING AND OPTICAL PERFORMANCE CHARACTERIZATION")
    print("=" * 60)
    print("\nThis tool will characterize:")
    print("  1. LED rise/fall times (switching speed)")
    print("  2. LED intensity vs detector counts")
    print("  3. Optimal integration time")
    print("  4. Recommended operating parameters")
    print("\n⚠️  Make sure hardware is connected!")
    print("=" * 60)

    input("\nPress ENTER to start characterization...")

    char = LEDTimingCharacterization()
    success = char.run_full_characterization()

    if success:
        print("\n✅ Characterization complete! Check generated-files/characterization/")
    else:
        print("\n❌ Characterization failed. Check logs for details.")

    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
