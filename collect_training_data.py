"""
Enhanced Spectral Data Collection Tool for ML Training

Collects S-mode and P-mode spectral data with:
- Real-time optimal processing (dark → denoise S&P → transmission)
- Live quality metrics display
- Interactive sensor labeling
- Structured training data output

Usage:
    python collect_training_data.py --device "demo P4SPR 2.0" --label used_current
    python collect_training_data.py --device "demo P4SPR 2.0" --label new_sealed --sensor-id "BATCH-001"
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from datetime import datetime
import time
import argparse
from scipy.signal import savgol_filter
from typing import Dict, Tuple, Optional

# Hardware imports
from utils.controller import PicoP4SPR
from utils.usb4000_oceandirect import USB4000OceanDirect
from utils.device_configuration import DeviceConfiguration
from settings import MIN_WAVELENGTH, MAX_WAVELENGTH

# Configuration
SAVGOL_WINDOW = 51
SAVGOL_POLYORDER = 3
SEARCH_START = 400  # Pixel index in FILTERED spectrum (after wavelength mask)
SEARCH_END = 1400   # Pixel index in FILTERED spectrum
SPECTRA_PER_MODE = 480  # 2 minutes @ 4 Hz
TARGET_RATE = 4.0  # Hz

# Sensor state options
SENSOR_STATES = {
    'new_sealed': 'Factory sealed, never opened',
    'new_unsealed': 'Opened but unused',
    'used_good': 'Normal use, working well',
    'used_current': 'Current sensor in use',
    'used_recycled': 'Reused cartridge, not fresh',
    'contaminated': 'Visible contamination',
    'degraded': 'Old, expired, or damaged',
}


class OptimalProcessor:
    """Optimal SPR spectral processing pipeline."""

    @staticmethod
    def denoise_spectrum(spectrum: np.ndarray) -> np.ndarray:
        """Apply Savitzky-Golay filter."""
        return savgol_filter(spectrum, SAVGOL_WINDOW, SAVGOL_POLYORDER)

    @staticmethod
    def process_transmission(s_raw: np.ndarray, p_raw: np.ndarray,
                           s_dark: np.ndarray, p_dark: np.ndarray) -> np.ndarray:
        """
        Process S and P mode spectra to transmission.
        Pipeline: dark correction → denoise S&P → transmission calculation
        """
        # Dark correction
        s_corr = s_raw - s_dark
        p_corr = p_raw - p_dark

        # Denoise S and P separately
        s_clean = OptimalProcessor.denoise_spectrum(s_corr)
        p_clean = OptimalProcessor.denoise_spectrum(p_corr)

        # Calculate transmission
        s_safe = np.where(s_clean < 1, 1, s_clean)
        transmission = p_clean / s_safe

        return transmission

    @staticmethod
    def find_minimum_centroid(transmission: np.ndarray, width: int = 40) -> float:
        """Find minimum using weighted centroid (best method)."""
        search_region = transmission[SEARCH_START:SEARCH_END]
        min_idx = np.argmin(search_region)

        # Window around minimum
        window_start = max(0, min_idx - width // 2)
        window_end = min(len(search_region), min_idx + width // 2)

        window = search_region[window_start:window_end]
        window_inverted = np.max(window) - window

        # Weighted centroid
        x = np.arange(window_start, window_end)
        centroid = np.sum(x * window_inverted) / np.sum(window_inverted)

        return float(SEARCH_START + centroid)

    @staticmethod
    def calculate_quality_metrics(positions: np.ndarray, transmission: np.ndarray) -> Dict:
        """Calculate quality metrics for sensorgram."""
        # Peak-to-peak variation
        p2p = np.ptp(positions)

        # Standard deviation
        std = np.std(positions)

        # Mean position
        mean_pos = np.mean(positions)

        # High-frequency noise (differential)
        hf_noise = np.std(np.diff(positions))

        # Peak depth (at mean position)
        mean_idx = int(mean_pos)
        if SEARCH_START <= mean_idx < SEARCH_END:
            peak_depth = 1.0 - transmission[mean_idx]
        else:
            peak_depth = 0.0

        # Signal-to-noise ratio (inverse of relative variation)
        snr = mean_pos / std if std > 0 else 0

        return {
            'p2p_px': float(p2p),
            'std_px': float(std),
            'mean_position_px': float(mean_pos),
            'hf_noise_px': float(hf_noise),
            'peak_depth': float(peak_depth),
            'snr': float(snr)
        }


class TrainingDataCollector:
    """Collects and processes spectral data for ML training."""

    def __init__(self, device_name: str, sensor_state: str,
                 sensor_id: Optional[str] = None, notes: Optional[str] = None):
        self.device_name = device_name
        self.sensor_state = sensor_state
        self.sensor_id = sensor_id or f"SENSOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.notes = notes or ""

        # Initialize hardware
        print("\n" + "="*80)
        print("TRAINING DATA COLLECTION TOOL")
        print("="*80)
        print(f"\nDevice: {device_name}")
        print(f"Sensor State: {sensor_state} - {SENSOR_STATES.get(sensor_state, 'Unknown')}")
        print(f"Sensor ID: {self.sensor_id}")
        if self.notes:
            print(f"Notes: {self.notes}")

        print("\nInitializing hardware...")
        self.spr_device = PicoP4SPR()
        self.spectrometer = USB4000OceanDirect()

        # Connect to hardware
        if not self.spr_device.open():
            raise RuntimeError("Failed to connect to PicoP4SPR controller")
        print("✓ Controller connected")

        if not self.spectrometer.connect():
            raise RuntimeError("Failed to connect to USB4000 spectrometer")
        print("✓ Spectrometer connected")

        # Initialize wavelength mask (same as main app)
        wavelengths = np.array(self.spectrometer.get_wavelengths())
        self.wavelength_mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
        print(f"✓ Wavelength filter: {np.sum(self.wavelength_mask)} pixels ({MIN_WAVELENGTH}-{MAX_WAVELENGTH} nm)")

        # Output directory
        self.output_dir = Path("training_data") / sensor_state
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"✓ Output directory: {self.output_dir}")

    def collect_dark_spectrum(self, mode: str) -> np.ndarray:
        """Collect dark spectrum with LED off."""
        print(f"\nCollecting {mode}-mode dark spectrum (LED OFF)...")

        # Turn off all LEDs
        self.spr_device.turn_off_channels()
        time.sleep(0.5)

        # Collect dark frames
        dark_frames = []
        for i in range(10):
            spectrum = self.spectrometer.acquire_spectrum()
            if spectrum is not None:
                dark_frames.append(spectrum[self.wavelength_mask])  # Apply wavelength filter
            time.sleep(0.1)

        dark = np.mean(dark_frames, axis=0)
        print(f"✓ Dark spectrum collected (averaged {len(dark_frames)} frames)")

        return dark

    def collect_mode_data(self, mode: str, channel: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Collect spectral data for S-mode or P-mode.

        Returns:
            (spectra, dark, timestamps)
        """
        print(f"\n{'='*80}")
        print(f"COLLECTING {mode.upper()}-MODE DATA - CHANNEL {channel.upper()}")
        print(f"{'='*80}")

        # Set up channel and polarization
        self.spr_device.turn_on_channel(channel.lower())
        time.sleep(0.2)

        # CRITICAL FIX: Actually move the polarizer!
        if mode == 's':
            print(f"  → Setting polarizer to S-mode...")
            self.spr_device.set_mode('s')
            time.sleep(2.0)  # Wait for servo to move
        else:
            print(f"  → Setting polarizer to P-mode...")
            self.spr_device.set_mode('p')
            time.sleep(2.0)  # Wait for servo to move

        time.sleep(0.5)

        # Collect dark spectrum
        dark = self.collect_dark_spectrum(mode)

        # Load calibrated LED intensity and integration time from device_config.json
        print(f"\nLoading calibrated LED parameters from device_config.json...")

        device_config = DeviceConfiguration()
        calibration = device_config.load_led_calibration()

        # Always consult the device-config minimum integration time as a safety floor
        min_integration_ms = None
        try:
            min_integration_ms = float(device_config.get_min_integration_time())
        except Exception:
            # Fallback if device config doesn't expose it for some reason
            min_integration_ms = 50.0

        if calibration:
            # Get calibrated LED intensity for this channel
            # Note: device_config.json stores lowercase channel keys ('a', 'b', 'c', 'd')
            led_intensity = calibration['s_mode_intensities'].get(channel.lower(), 128)
            # Prefer calibrated integration time, but enforce the minimum from device config
            integration_time_ms = int(calibration.get('integration_time_ms', min_integration_ms))

            if integration_time_ms < min_integration_ms:
                print(f"  -> Calibration integration time {integration_time_ms} ms < device-config minimum {min_integration_ms} ms; using minimum")
                integration_time_ms = int(min_integration_ms)

            print(f"  -> Using calibrated LED intensity: {led_intensity}")
            print(f"  -> Using integration time: {integration_time_ms} ms (source: device_config{' - calibrated' if 'integration_time_ms' in calibration else ''})")

            # Set integration time (convert ms to seconds)
            self.spectrometer.set_integration_time(integration_time_ms / 1000.0)

            # Use calibrated LED intensity
            print(f"\nTurning on LED for {mode}-mode...")
            self.spr_device.set_intensity(channel.lower(), led_intensity)
        else:
            # No calibration found - use conservative defaults coming from device config
            print("WARNING: No LED calibration found in device_config.json")
            print(f"  -> Using fallback LED intensity: 128 (safe default)")
            print(f"  -> Using device-config minimum integration time: {min_integration_ms} ms")
            print(f"  -> Run calibration in main app first for optimal data collection!")

            self.spectrometer.set_integration_time(min_integration_ms / 1000.0)
            self.spr_device.set_intensity(channel.lower(), 128)

        time.sleep(1.0)        # Collect spectra
        print(f"\nCollecting {SPECTRA_PER_MODE} spectra @ {TARGET_RATE} Hz...")
        print("Progress: ", end="", flush=True)

        spectra = []
        timestamps = []
        start_time = time.time()

        for i in range(SPECTRA_PER_MODE):
            spectrum = self.spectrometer.acquire_spectrum()
            if spectrum is None:
                print(f"\n⚠️  Warning: Failed to acquire spectrum {i+1}")
                continue

            # Apply wavelength filter (same as main app)
            spectrum = spectrum[self.wavelength_mask]

            timestamp = time.time() - start_time

            spectra.append(spectrum)
            timestamps.append(timestamp)

            # Progress indicator
            if (i + 1) % 48 == 0:  # Every 12 seconds
                print(f"{i+1}...", end="", flush=True)

            # Rate limiting
            target_interval = 1.0 / TARGET_RATE
            elapsed = time.time() - start_time
            expected_time = (i + 1) * target_interval
            sleep_time = expected_time - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

        total_time = time.time() - start_time
        actual_rate = len(spectra) / total_time

        print(f"\n✓ Collection complete!")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Actual rate: {actual_rate:.2f} Hz")
        print(f"  Spectra collected: {len(spectra)}")

        return np.array(spectra), dark, np.array(timestamps)

    def process_and_visualize(self, s_spectra: np.ndarray, p_spectra: np.ndarray,
                             s_dark: np.ndarray, p_dark: np.ndarray,
                             s_timestamps: np.ndarray, p_timestamps: np.ndarray,
                             channel: str = 'A') -> Dict:
        """Process data with optimal pipeline and create visualization."""
        print("\n" + "="*80)
        print("PROCESSING WITH OPTIMAL PIPELINE")
        print("="*80)

        n_spectra = len(s_spectra)
        positions = np.zeros(n_spectra)
        transmissions = []

        print("\nProcessing spectra...")
        for i in range(n_spectra):
            transmission = OptimalProcessor.process_transmission(
                s_spectra[i], p_spectra[i], s_dark, p_dark
            )
            transmissions.append(transmission)
            positions[i] = OptimalProcessor.find_minimum_centroid(transmission)

        transmissions = np.array(transmissions)

        # Calculate quality metrics
        mean_transmission = np.mean(transmissions, axis=0)
        metrics = OptimalProcessor.calculate_quality_metrics(positions, mean_transmission)

        # Convert to RU estimate (rough)
        nm_per_pixel = 0.091  # Full detector
        ru_per_nm = 355
        metrics['p2p_ru_estimate'] = metrics['p2p_px'] * nm_per_pixel * ru_per_nm

        print("\n" + "="*80)
        print("QUALITY METRICS")
        print("="*80)
        print(f"Peak-to-peak:      {metrics['p2p_px']:.2f} px  (~{metrics['p2p_ru_estimate']:.0f} RU)")
        print(f"Std deviation:     {metrics['std_px']:.2f} px")
        print(f"HF noise:          {metrics['hf_noise_px']:.2f} px")
        print(f"Mean position:     {metrics['mean_position_px']:.2f} px")
        print(f"Peak depth:        {metrics['peak_depth']:.2%}")
        print(f"SNR:               {metrics['snr']:.1f}")

        # Quality assessment
        print("\n" + "="*80)
        print("QUALITY ASSESSMENT")
        print("="*80)

        if metrics['p2p_px'] < 500:
            print("✓ GOOD: Low noise")
        elif metrics['p2p_px'] < 1000:
            print("⚠ ACCEPTABLE: Moderate noise")
        else:
            print("✗ POOR: High noise")

        if metrics['peak_depth'] > 0.3:
            print("✓ GOOD: Strong SPR signal")
        elif metrics['peak_depth'] > 0.15:
            print("⚠ ACCEPTABLE: Moderate SPR signal")
        else:
            print("✗ POOR: Weak SPR signal")

        # Create visualization
        self._create_visualization(positions, s_timestamps, transmissions, metrics, channel=channel)

        return metrics

    def _create_visualization(self, positions: np.ndarray, timestamps: np.ndarray,
                             transmissions: np.ndarray, metrics: Dict, channel: str = 'A'):
        """Create comprehensive visualization."""
        fig = plt.figure(figsize=(16, 10))

        # Sensorgram
        ax1 = plt.subplot(2, 3, 1)
        ax1.plot(timestamps, positions, 'b-', linewidth=1.5, alpha=0.8)
        ax1.set_xlabel('Time (s)', fontsize=11)
        ax1.set_ylabel('Resonance Position (px)', fontsize=11)
        ax1.set_title(f'Sensorgram\nP-P: {metrics["p2p_px"]:.1f} px',
                     fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Add quality indicator
        quality_color = 'green' if metrics['p2p_px'] < 500 else 'orange' if metrics['p2p_px'] < 1000 else 'red'
        ax1.axhline(y=np.mean(positions), color=quality_color, linestyle='--', alpha=0.3, linewidth=2)

        # Position histogram
        ax2 = plt.subplot(2, 3, 2)
        ax2.hist(positions, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
        ax2.set_xlabel('Position (px)', fontsize=11)
        ax2.set_ylabel('Count', fontsize=11)
        ax2.set_title(f'Position Distribution\nStd: {metrics["std_px"]:.2f} px',
                     fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')

        # Mean transmission spectrum
        ax3 = plt.subplot(2, 3, 3)
        mean_trans = np.mean(transmissions, axis=0)
        pixels = np.arange(len(mean_trans))
        ax3.plot(pixels[SEARCH_START:SEARCH_END], mean_trans[SEARCH_START:SEARCH_END],
                'r-', linewidth=2)
        ax3.axvline(x=metrics['mean_position_px'], color='blue', linestyle='--',
                   label=f'Mean: {metrics["mean_position_px"]:.1f} px')
        ax3.set_xlabel('Pixel Position', fontsize=11)
        ax3.set_ylabel('Transmission', fontsize=11)
        ax3.set_title(f'Mean Transmission Spectrum\nDepth: {metrics["peak_depth"]:.2%}',
                     fontsize=12, fontweight='bold')
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3)

        # Transmission heatmap
        ax4 = plt.subplot(2, 3, 4)
        im = ax4.imshow(transmissions[:, SEARCH_START:SEARCH_END].T,
                       aspect='auto', cmap='viridis', interpolation='nearest',
                       extent=[timestamps[0], timestamps[-1], SEARCH_END, SEARCH_START])
        ax4.plot(timestamps, positions, 'r-', linewidth=2, alpha=0.8, label='Minimum')
        ax4.set_xlabel('Time (s)', fontsize=11)
        ax4.set_ylabel('Pixel Position', fontsize=11)
        ax4.set_title('Transmission Time Series', fontsize=12, fontweight='bold')
        ax4.legend(fontsize=9)
        plt.colorbar(im, ax=ax4, label='Transmission')

        # Noise analysis
        ax5 = plt.subplot(2, 3, 5)
        position_diff = np.diff(positions)
        ax5.plot(timestamps[1:], position_diff, 'g-', linewidth=1, alpha=0.7)
        ax5.set_xlabel('Time (s)', fontsize=11)
        ax5.set_ylabel('Position Change (px)', fontsize=11)
        ax5.set_title(f'High-Frequency Noise\nStd: {metrics["hf_noise_px"]:.2f} px',
                     fontsize=12, fontweight='bold')
        ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax5.grid(True, alpha=0.3)

        # Metrics summary
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')

        summary = f"""
COLLECTION SUMMARY

Sensor State: {self.sensor_state}
Sensor ID: {self.sensor_id}
Device: {self.device_name}

QUALITY METRICS:
Peak-to-peak: {metrics['p2p_px']:.1f} px
  (~{metrics['p2p_ru_estimate']:.0f} RU estimate)
Std deviation: {metrics['std_px']:.2f} px
HF noise: {metrics['hf_noise_px']:.2f} px
Mean position: {metrics['mean_position_px']:.1f} px
Peak depth: {metrics['peak_depth']:.1%}
SNR: {metrics['snr']:.1f}

PROCESSING:
Pipeline: dark → denoise S&P → transmission
Denoising: Savgol (w=51, p=3)
Peak finding: Centroid

STATUS: {'GOOD ✓' if metrics['p2p_px'] < 500 else 'ACCEPTABLE ⚠' if metrics['p2p_px'] < 1000 else 'POOR ✗'}
        """

        ax6.text(0.1, 0.5, summary, transform=ax6.transAxes,
                fontsize=10, verticalalignment='center',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3, pad=1))

        plt.suptitle(f'Training Data Collection - {self.sensor_state.upper()}\n'
                    f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    fontsize=14, fontweight='bold')

        plt.tight_layout()

        # Save figure
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        fig_path = self.output_dir / f"{timestamp_str}_channel_{channel}_visualization.png"
        plt.savefig(fig_path, dpi=150, bbox_inches='tight')
        print(f"\n✓ Visualization saved: {fig_path}")

        plt.show(block=False)
        plt.pause(0.1)

    def save_data(self, channel: str, s_spectra: np.ndarray, p_spectra: np.ndarray,
                  s_dark: np.ndarray, p_dark: np.ndarray,
                  s_timestamps: np.ndarray, p_timestamps: np.ndarray,
                  metrics: Dict):
        """Save collected data and metadata."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save S-mode data
        s_file = self.output_dir / f"{timestamp_str}_channel_{channel}_s_mode.npz"
        np.savez_compressed(
            s_file,
            spectra=s_spectra,
            dark=s_dark,
            timestamps=s_timestamps
        )
        print(f"✓ Saved S-mode data: {s_file}")

        # Save P-mode data
        p_file = self.output_dir / f"{timestamp_str}_channel_{channel}_p_mode.npz"
        np.savez_compressed(
            p_file,
            spectra=p_spectra,
            dark=p_dark,
            timestamps=p_timestamps
        )
        print(f"✓ Saved P-mode data: {p_file}")

        # Save metadata
        metadata = {
            'timestamp': timestamp_str,
            'datetime': datetime.now().isoformat(),
            'sensor_state': self.sensor_state,
            'sensor_state_description': SENSOR_STATES.get(self.sensor_state, 'Unknown'),
            'sensor_id': self.sensor_id,
            'notes': self.notes,
            'device_name': self.device_name,
            'channel': channel,
            'collection_params': {
                'spectra_per_mode': SPECTRA_PER_MODE,
                'target_rate_hz': TARGET_RATE,
                'actual_rate_hz': len(s_timestamps) / s_timestamps[-1]
            },
            'processing_params': {
                'pipeline': 'dark → denoise S&P → transmission',
                'denoising': f'Savgol (window={SAVGOL_WINDOW}, polyorder={SAVGOL_POLYORDER})',
                'peak_finding': 'Centroid',
                'search_range': [SEARCH_START, SEARCH_END]
            },
            'quality_metrics': metrics
        }

        metadata_file = self.output_dir / f"{timestamp_str}_channel_{channel}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"✓ Saved metadata: {metadata_file}")

        return timestamp_str

    def collect_full_dataset(self, channels: list = ['A']):
        """Collect complete dataset for specified channels."""
        print("\n" + "="*80)
        print("STARTING COLLECTION")
        print("="*80)
        print(f"Channels: {', '.join(channels)}")
        print(f"Spectra per mode: {SPECTRA_PER_MODE}")
        print(f"Estimated time per channel: ~{(SPECTRA_PER_MODE / TARGET_RATE * 2) / 60:.1f} minutes")

        input("\nPress ENTER to start collection...")

        for channel in channels:
            print(f"\n\n{'#'*80}")
            print(f"# CHANNEL {channel}")
            print(f"{'#'*80}")

            # Collect S-mode
            s_spectra, s_dark, s_timestamps = self.collect_mode_data('s', channel)

            # Small pause between modes
            print("\nPausing before P-mode collection...")
            time.sleep(2)

            # Collect P-mode
            p_spectra, p_dark, p_timestamps = self.collect_mode_data('p', channel)

            # Process and analyze
            metrics = self.process_and_visualize(
                s_spectra, p_spectra, s_dark, p_dark,
                s_timestamps, p_timestamps, channel=channel
            )

            # Save data
            print("\n" + "="*80)
            print("SAVING DATA")
            print("="*80)
            timestamp_str = self.save_data(
                channel, s_spectra, p_spectra,
                s_dark, p_dark, s_timestamps, p_timestamps,
                metrics
            )

            print(f"\n✓ Channel {channel} complete!")

            if channel != channels[-1]:
                print("\nPrepare for next channel...")
                time.sleep(3)

        print("\n" + "="*80)
        print("COLLECTION COMPLETE!")
        print("="*80)
        print(f"\nAll data saved to: {self.output_dir}")

        # Turn off LEDs
        self.spr_device.turn_off_channels()

    def cleanup(self):
        """Clean up hardware connections."""
        try:
            self.spr_device.turn_off_channels()
            print("\n✓ LEDs turned off")
        except:
            pass

        try:
            if hasattr(self.spr_device, 'close'):
                self.spr_device.close()
        except:
            pass

        try:
            if hasattr(self.spectrometer, 'disconnect'):
                self.spectrometer.disconnect()
        except:
            pass


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Collect training data for ML sensor classification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sensor States:
  new_sealed      Factory sealed, never opened
  new_unsealed    Opened but unused
  used_good       Normal use, working well
  used_current    Current sensor in use
  used_recycled   Reused cartridge, not fresh
  contaminated    Visible contamination
  degraded        Old, expired, or damaged

Examples:
  python collect_training_data.py --device "demo P4SPR 2.0" --label used_current
  python collect_training_data.py --device "demo P4SPR 2.0" --label new_sealed --sensor-id "BATCH-001"
  python collect_training_data.py --device "demo P4SPR 2.0" --label used_recycled --notes "After 50 assays"
        """
    )

    parser.add_argument('--device', type=str, required=True,
                       help='Device name (e.g., "demo P4SPR 2.0")')
    parser.add_argument('--label', type=str, required=True,
                       choices=list(SENSOR_STATES.keys()),
                       help='Sensor state label')
    parser.add_argument('--sensor-id', type=str, default=None,
                       help='Sensor ID or batch number (optional)')
    parser.add_argument('--notes', type=str, default=None,
                       help='Additional notes (optional)')
    parser.add_argument('--channels', type=str, default='A,B,C,D',
                       help='Channels to collect (comma-separated, e.g., "A,B,C,D")')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print integration time and LED intensity per channel without connecting to hardware')

    args = parser.parse_args()

    channels = [ch.strip().upper() for ch in args.channels.split(',')]

    # Dry-run path: report planned settings without touching hardware
    if args.dry_run:
        print("\n" + "="*80)
        print("TRAINING DATA COLLECTION TOOL - DRY RUN")
        print("="*80)
        print(f"\nDevice: {args.device}")
        print(f"Sensor State: {args.label} - {SENSOR_STATES.get(args.label, 'Unknown')}")
        if args.sensor_id:
            print(f"Sensor ID: {args.sensor_id}")
        if args.notes:
            print(f"Notes: {args.notes}")

        device_config = DeviceConfiguration()
        calibration = device_config.load_led_calibration()
        try:
            min_integration_ms = float(device_config.get_min_integration_time())
        except Exception:
            min_integration_ms = 50.0

        print("\nLoaded device configuration")
        print(f"  → Minimum integration time (device-config): {min_integration_ms} ms")

        for ch in channels:
            ch_key = ch.lower()
            if calibration:
                led_intensity = calibration['s_mode_intensities'].get(ch_key, 128)
                integration_time_ms = int(calibration.get('integration_time_ms', min_integration_ms))
                if integration_time_ms < min_integration_ms:
                    integration_time_ms = int(min_integration_ms)
                print(f"\nChannel {ch}:")
                print(f"  LED intensity (device-config calibrated): {led_intensity}")
                print(f"  Integration time (enforced min): {integration_time_ms} ms ({integration_time_ms/1000.0:.3f} s)")
            else:
                print(f"\nChannel {ch}:")
                print(f"  LED intensity (fallback): 128")
                print(f"  Integration time (device-config minimum): {min_integration_ms} ms ({min_integration_ms/1000.0:.3f} s)")

        print("\nNo hardware actions were performed. Use without --dry-run to start collection.")
        return

    # Create collector
    collector = TrainingDataCollector(
        device_name=args.device,
        sensor_state=args.label,
        sensor_id=args.sensor_id,
        notes=args.notes
    )

    try:
        # Run collection
        collector.collect_full_dataset(channels=channels)

        print("\n" + "="*80)
        print("SUCCESS!")
        print("="*80)
        print("\nData collection complete. Ready for ML training when you have")
        print("collected data from multiple sensor states.")

    except KeyboardInterrupt:
        print("\n\n⚠️ Collection interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during collection: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.cleanup()
        print("\n✓ Cleanup complete")


if __name__ == "__main__":
    main()
