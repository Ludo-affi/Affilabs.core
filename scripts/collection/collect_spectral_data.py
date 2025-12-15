"""S/P Signal Data Collection for Spectral Analysis

Collects comprehensive spectral data from all 4 channels:
- Raw spectra at every time point
- Dark spectra
- All intermediate processing steps
- Saves everything for ML training

Usage:
    # S-signal collection (5 minutes, all channels)
    python collect_spectral_data.py --mode S --duration 300 --device-serial "SN12345" --sensor-quality "new_sealed"

    # P-signal collection (same script, different mode)
    python collect_spectral_data.py --mode P --duration 300 --device-serial "SN12345" --sensor-quality "new_sealed"

Sensor Quality Labels:
    - new_sealed: Brand new, unopened sensor
    - new_unsealed: New sensor, package opened
    - used: Previously used sensor
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from utils.device_configuration import DeviceConfiguration

# Import your existing hardware managers
from utils.hal.pico_p4spr_hal import PicoP4SPRHAL
from utils.logger import logger
from utils.usb4000_oceandirect import USB4000OceanDirect


def connect_hardware():
    """Connect to hardware components."""
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
        spec = USB4000OceanDirect()
        if spec.connect():
            logger.info("✅ Spectrometer: USB4000")
        else:
            logger.error("❌ Spectrometer connection failed")
            ctrl.disconnect()
            return None, None

        return ctrl, spec

    except Exception as e:
        logger.error(f"❌ Spectrometer error: {e}")
        if ctrl:
            ctrl.disconnect()
        return None, None


class SpectralDataCollector:
    """Collects comprehensive spectral data for ML training."""

    def __init__(self, device_serial: str, sensor_quality: str):
        """Initialize collector.

        Args:
            device_serial: Device serial number (e.g., "SN12345")
            sensor_quality: new_sealed, new_unsealed, or used

        """
        self.device_serial = device_serial
        self.sensor_quality = sensor_quality

        # Initialize hardware
        self.ctrl, self.usb = connect_hardware()

        if not self.ctrl or not self.usb:
            raise RuntimeError("Failed to connect to hardware")

        logger.info("✅ Hardware connected successfully")

        # Load device configuration
        self.device_config = DeviceConfiguration()

        # Get calibration context (already defined in your system)
        self.calibration = self._load_calibration_context()

        # Storage for collected data
        self.data = {
            "metadata": {
                "device_serial": device_serial,
                "sensor_quality": sensor_quality,
                "collection_date": datetime.now().isoformat(),
                "calibration": self.calibration,
            },
            "channels": {
                "A": {"spectra": [], "dark": [], "timestamps": []},
                "B": {"spectra": [], "dark": [], "timestamps": []},
                "C": {"spectra": [], "dark": [], "timestamps": []},
                "D": {"spectra": [], "dark": [], "timestamps": []},
            },
        }

    def _load_calibration_context(self):
        """Load existing calibration parameters - using safe defaults."""
        calibration = {}

        # Use safe defaults for all channels
        default_integration_ms = 100.0  # ms
        default_led_intensity = 100  # %
        default_led_delay_ms = 20  # ms

        for channel in ["A", "B", "C", "D"]:
            calibration[channel] = {
                "integration_time_ms": default_integration_ms,
                "led_intensity": default_led_intensity,
                "led_delay_ms": default_led_delay_ms,
            }

        logger.info("Using default acquisition parameters:")
        for ch, settings in calibration.items():
            logger.info(
                f"  Channel {ch}: {settings['integration_time_ms']}ms, {settings['led_intensity']}% intensity",
            )

        return calibration

    def collect_dark_spectrum(self, channel: str):
        """Collect dark spectrum (LED off).

        Args:
            channel: "A", "B", "C", or "D"

        Returns:
            Dark spectrum array

        """
        ch_lower = channel.lower()

        # Turn LED off
        self.ctrl.turn_off_channels()
        time.sleep(0.1)  # Settle time

        # Measure dark - use read_intensity() method
        if hasattr(self.usb, "read_intensity"):
            dark_spectrum = self.usb.read_intensity()
        elif hasattr(self.usb, "acquire_spectrum"):
            dark_spectrum = self.usb.acquire_spectrum()
        else:
            raise RuntimeError(
                "Spectrometer does not have read_intensity() or acquire_spectrum() method",
            )

        return dark_spectrum

    def collect_signal_spectrum(self, channel: str, mode: str):
        """Collect signal spectrum (LED on, S or P mode).
        NOTE: Polarizer mode should already be set by collect_channel_data().

        Args:
            channel: "A", "B", "C", or "D"
            mode: "S" or "P" (for metadata only - polarizer already set)

        Returns:
            Raw spectrum array

        """
        ch_lower = channel.lower()

        # Turn LED on (uses calibrated intensity from device config)
        self.ctrl.activate_channel(ch_lower)
        time.sleep(0.02)  # 20ms LED delay

        # Measure spectrum
        if hasattr(self.usb, "read_intensity"):
            raw_spectrum = self.usb.read_intensity()
        elif hasattr(self.usb, "acquire_spectrum"):
            raw_spectrum = self.usb.acquire_spectrum()
        else:
            raise RuntimeError(
                "Spectrometer does not have read_intensity() or acquire_spectrum() method",
            )

        # Turn LED off
        self.ctrl.turn_off_channels()

        return raw_spectrum

    def collect_channel_data(self, channel: str, mode: str, duration_seconds: int):
        """Collect data from one channel for specified duration.

        Args:
            channel: "A", "B", "C", or "D"
            mode: "S" or "P"
            duration_seconds: Collection duration

        """
        print(
            f"\n📊 Collecting {mode}-signal from Channel {channel} for {duration_seconds}s...",
        )

        # Set polarization mode ONCE at the start
        if hasattr(self.ctrl, "set_mode"):
            result = self.ctrl.set_mode(mode.lower())
            if result:
                logger.info(
                    f"✅ Polarizer set to {mode.upper()}-mode for Channel {channel}",
                )
            else:
                logger.warning(
                    "⚠️ Polarizer mode setting returned False - may not have moved",
                )
            time.sleep(0.4)  # 400ms settle time for polarizer servo (ONCE per channel)
        else:
            logger.error(
                "❌ Controller does not support set_mode - cannot set polarization!",
            )
            raise RuntimeError(
                f"Controller {type(self.ctrl).__name__} does not have set_mode method",
            )

        # Collect initial dark spectrum
        print("  • Measuring dark spectrum...")
        dark = self.collect_dark_spectrum(channel)
        self.data["channels"][channel]["dark"].append(dark.tolist())

        # Collect signal spectra over time
        # Target: 1-5 Hz range (matching production system)
        # Use 4 Hz = 250ms interval (middle of range, matches ~200ms/channel production timing)
        acquisition_interval = 0.25  # seconds
        start_time = time.time()
        next_acquisition = start_time
        measurement_count = 0

        while (time.time() - start_time) < duration_seconds:
            current_time = time.time()

            # Wait for next scheduled acquisition time
            if current_time < next_acquisition:
                time.sleep(0.01)  # Small sleep to avoid CPU spinning
                continue

            # Collect spectrum
            spectrum = self.collect_signal_spectrum(channel, mode)
            timestamp = current_time - start_time

            # Store
            self.data["channels"][channel]["spectra"].append(spectrum.tolist())
            self.data["channels"][channel]["timestamps"].append(timestamp)

            measurement_count += 1
            next_acquisition += acquisition_interval

            # Progress update every 30 seconds
            if measurement_count % 10 == 0:
                elapsed = time.time() - start_time
                actual_rate = measurement_count / elapsed if elapsed > 0 else 0
                print(
                    f"  • {elapsed:.1f}s / {duration_seconds}s ({measurement_count} spectra @ {actual_rate:.1f} Hz)",
                )

        print(f"  ✓ Collected {measurement_count} spectra from Channel {channel}")

    def collect_all_channels(
        self,
        mode: str,
        duration_seconds: int,
        channels: list | None = None,
    ):
        """Collect data from specified channels.

        Args:
            mode: "S" or "P"
            duration_seconds: Collection duration per channel
            channels: List of channels to collect (default: ["A", "B", "C", "D"])

        """
        if channels is None:
            channels = ["A", "B", "C", "D"]

        print(f"\n{'='*60}")
        print(
            f"  {mode}-Signal Collection - Channel{'s' if len(channels) > 1 else ''} {', '.join(channels)}",
        )
        print(f"{'='*60}")
        print(f"  Device Serial: {self.device_serial}")
        print(f"  Sensor Quality: {self.sensor_quality}")
        print(f"  Duration per channel: {duration_seconds}s")
        print(f"  Mode: {mode}-polarization")
        print(f"{'='*60}\n")

        # Collect from each channel
        for channel in channels:
            self.collect_channel_data(channel, mode, duration_seconds)

        print(
            f"\n✓ Collection complete for {'all channels' if len(channels) == 4 else 'channel(s) ' + ', '.join(channels)}!",
        )

    def save_data(self, mode: str):
        """Save collected data to organized structure.

        Args:
            mode: "S" or "P"

        """
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (
            Path("spectral_training_data")
            / self.device_serial
            / mode.lower()
            / self.sensor_quality
            / timestamp
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(self.data["metadata"], f, indent=2)

        # Save each channel's data as separate NPZ file (efficient for ML)
        for channel in ["A", "B", "C", "D"]:
            channel_file = output_dir / f"channel_{channel}.npz"

            np.savez_compressed(
                channel_file,
                spectra=np.array(self.data["channels"][channel]["spectra"]),
                dark=np.array(self.data["channels"][channel]["dark"]),
                timestamps=np.array(self.data["channels"][channel]["timestamps"]),
            )

        # Save summary
        summary = {
            "device_serial": self.device_serial,
            "sensor_quality": self.sensor_quality,
            "mode": mode,
            "timestamp": timestamp,
            "data_location": str(output_dir),
            "channels": {},
        }

        for channel in ["A", "B", "C", "D"]:
            summary["channels"][channel] = {
                "num_spectra": len(self.data["channels"][channel]["spectra"]),
                "num_dark": len(self.data["channels"][channel]["dark"]),
                "duration_seconds": self.data["channels"][channel]["timestamps"][-1]
                if self.data["channels"][channel]["timestamps"]
                else 0,
            }

        summary_file = output_dir / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'='*60}")
        print("  Data Saved")
        print(f"{'='*60}")
        print(f"  Location: {output_dir}")
        print("  Files:")
        print("    • metadata.json")
        print("    • summary.json")
        for channel in ["A", "B", "C", "D"]:
            print(f"    • channel_{channel}.npz")
        print(f"{'='*60}\n")

        return output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Collect spectral data for ML training",
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["S", "P"],
        help="Polarization mode (S or P)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Collection duration per channel in seconds (default: 300 = 5 minutes)",
    )

    parser.add_argument(
        "--device-serial",
        required=True,
        help="Device serial number (e.g., SN12345)",
    )

    parser.add_argument(
        "--sensor-quality",
        required=True,
        choices=["new_sealed", "new_unsealed", "used"],
        help="Sensor quality label",
    )

    parser.add_argument(
        "--channels",
        default="A,B,C,D",
        help="Comma-separated list of channels to collect (default: A,B,C,D)",
    )

    args = parser.parse_args()

    # Parse channels
    channels = [ch.strip().upper() for ch in args.channels.split(",")]
    for ch in channels:
        if ch not in ["A", "B", "C", "D"]:
            parser.error(f"Invalid channel: {ch}. Must be A, B, C, or D")

    # Create collector
    collector = SpectralDataCollector(
        device_serial=args.device_serial,
        sensor_quality=args.sensor_quality,
    )

    # Collect data
    collector.collect_all_channels(
        mode=args.mode,
        duration_seconds=args.duration,
        channels=channels,
    )

    # Save data
    output_dir = collector.save_data(mode=args.mode)

    print("\n🎉 Collection complete!")
    print(f"   Data saved to: {output_dir}")
    print(f"\n   To collect {('P' if args.mode == 'S' else 'S')}-signal, run:")
    print(
        f"   python collect_spectral_data.py --mode {('P' if args.mode == 'S' else 'S')} --duration {args.duration} --device-serial {args.device_serial} --sensor-quality {args.sensor_quality}",
    )


if __name__ == "__main__":
    main()
