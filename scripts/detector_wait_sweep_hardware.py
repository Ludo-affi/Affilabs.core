"""Detector Wait Sweep with Hardware Integration

Tests different detector sampling delays to find optimal stability.
Connects to real spectrometer hardware and measures signal stability.
"""

import statistics
import sys
import time
from pathlib import Path

import numpy as np
import serial

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import hardware components
from utils.hal.hal_factory import HALFactory
from utils.logger import logger


class DetectorWaitSweep:
    """Hardware-integrated detector wait sweep experiment."""

    def __init__(self, firmware_port: str):
        self.firmware_port = firmware_port
        self.firmware = None
        self.spectrometer = None
        self.wavelengths = None

    def connect_hardware(self) -> bool:
        """Connect to firmware and spectrometer."""
        try:
            # Connect to firmware
            self.firmware = serial.Serial(
                self.firmware_port,
                baudrate=115200,
                timeout=2,
            )
            self.firmware.setDTR(True)
            self.firmware.setRTS(True)
            time.sleep(0.5)
            self.firmware.reset_input_buffer()
            self.firmware.reset_output_buffer()

            # Verify firmware
            self.firmware.write(b"id\n")
            time.sleep(0.3)
            fw_id = self.firmware.readline().decode("ascii", "ignore").strip()
            print(f"✓ Firmware: {fw_id}")

            # Connect to spectrometer
            print("Connecting to spectrometer...")
            self.spectrometer = HALFactory.create_spectrometer(auto_detect=True)

            if self.spectrometer is None:
                print("❌ No spectrometer found")
                return False

            # Get wavelengths
            if hasattr(self.spectrometer, "get_wavelengths"):
                self.wavelengths = np.array(self.spectrometer.get_wavelengths())
            else:
                print("❌ Cannot get wavelengths from spectrometer")
                return False

            print(f"✓ Spectrometer: {len(self.wavelengths)} pixels")

            # Set integration time
            if hasattr(self.spectrometer, "set_integration_time"):
                self.spectrometer.set_integration_time(100.0)  # 100ms default
                print("✓ Integration time: 100ms")

            return True

        except Exception as e:
            print(f"❌ Hardware connection failed: {e}")
            return False

    def disconnect_hardware(self):
        """Disconnect all hardware."""
        if self.firmware:
            self.firmware.close()
        if self.spectrometer and hasattr(self.spectrometer, "disconnect"):
            self.spectrometer.disconnect()

    def send_command(self, cmd: str):
        """Send command to firmware."""
        self.firmware.write((cmd + "\n").encode("ascii"))

    def read_spectrum(self) -> np.ndarray | None:
        """Read spectrum from detector."""
        try:
            if hasattr(self.spectrometer, "acquire_spectrum"):
                return np.array(self.spectrometer.acquire_spectrum())
            if hasattr(self.spectrometer, "read_intensity"):
                return np.array(self.spectrometer.read_intensity())
            return None
        except Exception as e:
            logger.debug(f"Spectrum read failed: {e}")
            return None

    def run_sweep(
        self,
        led_on_times_ms: list[int],
        cycles_per_test: int = 20,
        led_intensities: tuple = (50, 100, 150, 200),
        detector_wait_ms: int = 5,
    ) -> list[dict]:
        """Run LED ON time sweep experiment with 4-LED rankbatch.

        Args:
            led_on_times_ms: List of LED ON durations to test (ms)
            cycles_per_test: Number of 4-LED cycles per LED ON time
            led_intensities: Tuple of 4 LED intensities (A, B, C, D)
            detector_wait_ms: Fixed detector sampling delay after READY (ms)

        Returns:
            List of result dictionaries with stability metrics

        """
        print("=" * 70)
        print("LED ON TIME SWEEP - 4-LED RANKBATCH")
        print("=" * 70)
        print(f"\nLED ON times to test: {led_on_times_ms} ms")
        print(f"Cycles per test: {cycles_per_test} (4 LEDs per cycle)")
        print(
            f"LED intensities: A={led_intensities[0]}, B={led_intensities[1]}, C={led_intensities[2]}, D={led_intensities[3]}",
        )
        print(f"Detector wait (fixed): {detector_wait_ms} ms")
        print(
            f"Wavelength range: {self.wavelengths[0]:.1f} - {self.wavelengths[-1]:.1f} nm\n",
        )

        results = []

        for led_on_ms in led_on_times_ms:
            print(f"\n{'='*70}")
            print(f"Testing LED ON time = {led_on_ms} ms")
            print(f"{'='*70}")

            # Send keepalive
            self.send_command("ka")
            time.sleep(0.1)

            # Start rankbatch with 4 LEDs and varying LED ON time
            cmd = f"rankbatch:{led_intensities[0]},{led_intensities[1]},{led_intensities[2]},{led_intensities[3]},{led_on_ms},0,{cycles_per_test}"
            self.send_command(cmd)

            # Parse BATCH_START and ACK
            batch_line = self.firmware.readline().decode("ascii", "ignore").strip()
            ack_line = self.firmware.readline().decode("ascii", "ignore").strip()
            # Filter out ACK character (may be concatenated with next message)
            batch_line = batch_line.replace("\x06", "").strip()
            ack_line = ack_line.replace("\x06", "").strip()
            print(
                f"Status: {batch_line[:20]}, ACK: {ack_line[:10] if ack_line else 'OK'}",
            )

            # Collect detector readings for each LED in each cycle
            readings_per_led = {"A": [], "B": [], "C": [], "D": []}
            last_keepalive = time.time()

            print(
                f"Sampling 4 LEDs per cycle (LED_ON={led_on_ms}ms, detector_wait={detector_wait_ms}ms)...",
            )

            # Each cycle has 4 READY signals (one per LED)
            total_samples = cycles_per_test * 4
            samples_collected = 0
            current_led_index = 0
            led_names = ["A", "B", "C", "D"]

            # Check if ack_line is actually the first READY signal (happens with instant READY firmware)
            if ":READY" in ack_line:
                led_id = ack_line[0].upper()
                if led_id in led_names:
                    # Wait specified detector delay before sampling
                    time.sleep(detector_wait_ms / 1000.0)
                    # Read spectrum
                    spectrum = self.read_spectrum()
                    if spectrum is not None:
                        mask = (self.wavelengths >= 550) & (self.wavelengths <= 800)
                        peak_value = np.max(spectrum[mask])
                        readings_per_led[led_id].append(peak_value)
                        samples_collected += 1
                        current_led_index = (current_led_index + 1) % 4

            for sample in range(total_samples):
                # Wait for READY or timeout
                ready_found = False
                timeout = time.time() + 2.0

                while time.time() < timeout and not ready_found:
                    # Send keepalive if needed
                    if (time.time() - last_keepalive) >= 5.0:
                        self.send_command("ka")
                        last_keepalive = time.time()

                    if self.firmware.in_waiting:
                        line = (
                            self.firmware.readline().decode("ascii", "ignore").strip()
                        )
                        # Strip ACK character that may be concatenated (e.g., "6a:READY" -> "a:READY")
                        line = line.replace("\x06", "").lstrip("6").strip()
                        if "READY" in line or "BATCH" in line or "CYCLE" in line:
                            ready_found = True
                            break
                    else:
                        time.sleep(0.01)

                if not ready_found:
                    current_led_index = (current_led_index + 1) % 4
                    continue

                # Apply minimal detector wait
                time.sleep(detector_wait_ms / 1000.0)

                # Read spectrum
                spectrum = self.read_spectrum()

                if spectrum is not None and len(spectrum) > 0:
                    # Get peak intensity in wavelength range of interest (550-800nm typical SPR)
                    mask = (self.wavelengths >= 550) & (self.wavelengths <= 800)
                    if np.any(mask):
                        peak_val = np.max(spectrum[mask])
                        mean_val = np.mean(spectrum[mask])
                    else:
                        peak_val = np.max(spectrum)
                        mean_val = np.mean(spectrum)

                    # Store reading for current LED
                    led_name = led_names[current_led_index]
                    readings_per_led[led_name].append(
                        {"peak": peak_val, "mean": mean_val},
                    )
                    samples_collected += 1

                    if samples_collected % 20 == 0:
                        current_cycle = samples_collected // 4
                        print(
                            f"  Cycles: {current_cycle}/{cycles_per_test}, LED {led_name}: {peak_val:.0f} counts",
                        )

                # Move to next LED
                current_led_index = (current_led_index + 1) % 4

                # Also check keepalive after each sample
                if (time.time() - last_keepalive) >= 5.0:
                    self.send_command("ka")
                    last_keepalive = time.time()

            # Compute stability metrics per LED
            print(f"\nResults for LED_ON={led_on_ms}ms:")

            led_results = {}
            for led_name in ["A", "B", "C", "D"]:
                readings = readings_per_led[led_name]

                if len(readings) >= 3:
                    peaks = [r["peak"] for r in readings]
                    means = [r["mean"] for r in readings]

                    peak_mean = statistics.mean(peaks)
                    peak_stdev = statistics.pstdev(peaks)
                    peak_cv = (peak_stdev / peak_mean * 100) if peak_mean > 0 else 0

                    led_results[led_name] = {
                        "count": len(readings),
                        "peak_mean": peak_mean,
                        "peak_stdev": peak_stdev,
                        "peak_cv": peak_cv,
                        "peak_min": min(peaks),
                        "peak_max": max(peaks),
                    }

                    print(
                        f"  LED {led_name}: {len(readings)} samples, peak={peak_mean:.0f}±{peak_stdev:.1f} (CV={peak_cv:.2f}%), range={min(peaks):.0f}-{max(peaks):.0f}",
                    )
                else:
                    print(
                        f"  LED {led_name}: ❌ Insufficient samples ({len(readings)})",
                    )

            # Overall metrics
            if led_results:
                avg_cv = statistics.mean([r["peak_cv"] for r in led_results.values()])
                result = {
                    "led_on_ms": led_on_ms,
                    "led_results": led_results,
                    "avg_cv": avg_cv,
                    "total_samples": samples_collected,
                }
                results.append(result)
                print(f"  Average CV across LEDs: {avg_cv:.2f}%")
            else:
                print("  ❌ No valid LED results")

            time.sleep(0.5)

        return results

    def print_summary(self, results: list[dict]):
        """Print summary table of all results."""
        print(f"\n{'='*70}")
        print("SUMMARY - Signal Stability vs LED ON Time")
        print(f"{'='*70}")

        # Per-LED table
        for led in ["A", "B", "C", "D"]:
            print(f"\nLED {led}:")
            print(
                f"{'LED_ON(ms)':<12} {'Samples':<10} {'Peak Mean':<12} {'Std Dev':<10} {'CV%':<8}",
            )
            print("-" * 60)
            for r in results:
                if led in r["led_results"]:
                    lr = r["led_results"][led]
                    print(
                        f"{r['led_on_ms']:<12} {lr['count']:<10} {lr['peak_mean']:<12.0f} "
                        f"{lr['peak_stdev']:<10.1f} {lr['peak_cv']:<8.2f}",
                    )

        # Overall average CV
        print(f"\n{'='*70}")
        print("Average CV across all 4 LEDs:")
        print(f"{'LED_ON(ms)':<12} {'Avg CV%':<10} {'Total Samples':<15}")
        print("-" * 40)
        for r in results:
            print(f"{r['led_on_ms']:<12} {r['avg_cv']:<10.2f} {r['total_samples']:<15}")

        # Find optimal LED ON time (minimum average CV)
        if results:
            best = min(results, key=lambda x: x["avg_cv"])
            print("\n" + "=" * 70)
            print(
                f"✓ Optimal LED ON time: {best['led_on_ms']}ms (Avg CV: {best['avg_cv']:.2f}%)",
            )
            print("=" * 70)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/detector_wait_sweep_hardware.py <COMx> <led_on_csv> [cycles] [detector_wait_ms]",
        )
        print(
            "\nExample: python scripts/detector_wait_sweep_hardware.py COM5 0,10,25,50,100 15 5",
        )
        print(
            "\nTests different LED ON times with 4-LED rankbatch to find optimal stability.",
        )
        print(
            "Connects to real spectrometer hardware and measures signal statistics per LED.",
        )
        sys.exit(1)

    port = sys.argv[1]
    led_on_times = [int(x) for x in sys.argv[2].split(",")]
    cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    detector_wait = int(sys.argv[4]) if len(sys.argv) > 4 else 5

    sweep = DetectorWaitSweep(port)

    try:
        if not sweep.connect_hardware():
            print("\n❌ Hardware connection failed. Check connections and try again.")
            sys.exit(1)

        results = sweep.run_sweep(led_on_times, cycles, detector_wait_ms=detector_wait)

        if results:
            sweep.print_summary(results)
        else:
            print("\n❌ No results collected")

    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        sweep.disconnect_hardware()
        print("\n✓ Hardware disconnected")


if __name__ == "__main__":
    main()
