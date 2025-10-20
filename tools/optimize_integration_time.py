"""
Integration Time Optimizer for SPR Acquisition

Finds optimal integration time that balances:
1. Acquisition speed (shorter = faster)
2. Signal quality (sufficient SNR for <2 RU noise)
3. Peak tracking stability

Strategy:
- Test multiple integration times (e.g., 20, 30, 40, 50, 60, 80, 100ms)
- Measure signal levels and noise for each
- Calculate peak wavelength stability (std dev in nm)
- Convert to RU using sensitivity factor
- Find minimum integration time that meets <2 RU target

Usage:
    python tools/optimize_integration_time.py
    
    Follow prompts:
    1. Ensure stable SPR setup (no binding events)
    2. Script will test 7 integration times
    3. Results saved to integration_time_optimization.json
    4. Recommended settings displayed

Author: GitHub Copilot
Date: October 19, 2025
"""

import sys
import time
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import logger
from utils.device_configuration import get_device_config
from utils.hal.pico_p4spr_hal import PicoP4SPRHAL, ChannelID

try:
    import seabreeze
    seabreeze.use('cseabreeze')
    from seabreeze.spectrometers import list_devices, Spectrometer
except ImportError:
    logger.error("SeaBreeze not available")
    exit(1)


class IntegrationTimeOptimizer:
    """Optimize integration time for SPR acquisition."""
    
    def __init__(self, ctrl: PicoP4SPRHAL, spec: Spectrometer):
        """Initialize optimizer.
        
        Args:
            ctrl: SPR controller HAL instance
            spec: Spectrometer instance
        """
        self.ctrl = ctrl
        self.spec = spec
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_conditions': {},
            'channel_results': {},
            'recommendations': {}
        }
        
        # Load afterglow correction if available
        self.afterglow_correction = None
        try:
            device_config = get_device_config().to_dict()
            optical_cal_file = device_config.get('optical_calibration_file')
            if optical_cal_file and Path(optical_cal_file).exists():
                from afterglow_correction import AfterglowCorrection
                self.afterglow_correction = AfterglowCorrection(optical_cal_file)
                logger.info(f"✅ Loaded afterglow correction: {Path(optical_cal_file).name}")
        except Exception as e:
            logger.warning(f"⚠️ Afterglow correction not available: {e}")
    
    def find_spr_peak(self, spectrum: np.ndarray, wavelengths: np.ndarray) -> float:
        """Find SPR transmission minimum (peak).
        
        Uses simple argmin in SPR range (600-680nm).
        
        Args:
            spectrum: Transmission spectrum
            wavelengths: Wavelength array
            
        Returns:
            Peak wavelength in nm
        """
        # SPR range
        mask = (wavelengths >= 600) & (wavelengths <= 680)
        wl_spr = wavelengths[mask]
        spec_spr = spectrum[mask]
        
        if len(spec_spr) == 0:
            return np.nan
        
        min_idx = np.argmin(spec_spr)
        return wl_spr[min_idx]
    
    def test_integration_time(
        self,
        channel: str,
        integration_time_ms: float,
        num_measurements: int = 100,
        led_intensity: int = 168,
        normalize_time_ms: float = 200.0
    ) -> Dict:
        """Test single integration time and measure stability.
        
        NORMALIZED ACQUISITION: Takes multiple scans to reach normalize_time_ms.
        Example: 20ms × 10 scans = 200ms, 50ms × 4 scans = 200ms, 100ms × 2 scans = 200ms
        This tests if averaging multiple fast scans gives better noise than one long scan.
        
        Args:
            channel: Channel to test ('a', 'b', 'c', 'd')
            integration_time_ms: Integration time to test (ms)
            num_measurements: Number of repeated measurements for statistics
            led_intensity: LED intensity to use
            normalize_time_ms: Total acquisition time per measurement (default 200ms)
            
        Returns:
            Dictionary with results:
                - mean_signal: Average signal level (counts)
                - std_signal: Signal noise (counts)
                - snr: Signal-to-noise ratio
                - mean_peak_nm: Average peak wavelength (nm)
                - std_peak_nm: Peak wavelength std dev (nm)
                - estimated_ru: Estimated RU noise
                - scans_per_measurement: Number of scans averaged
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing Channel {channel.upper()} @ {integration_time_ms:.1f}ms")
        logger.info(f"{'='*70}")
        
        # Calculate number of scans to normalize acquisition time
        scans_per_measurement = max(1, int(round(normalize_time_ms / integration_time_ms)))
        actual_time_ms = scans_per_measurement * integration_time_ms
        
        logger.info(f"Scans per measurement: {scans_per_measurement} (total ~{actual_time_ms:.1f}ms)")
        
        # Set integration time
        int_time_us = int(integration_time_ms * 1000)
        self.spec.integration_time_micros(int_time_us)
        time.sleep(0.2)  # Let spectrometer settle
        
        # Calculate optimal LED delay for this integration time
        if self.afterglow_correction:
            led_delay = self.afterglow_correction.get_optimal_led_delay(
                integration_time_ms=integration_time_ms,
                target_residual_percent=2.0
            )
        else:
            led_delay = 0.05  # 50ms default
        
        logger.info(f"LED delay: {led_delay*1000:.1f}ms")
        
        # Activate channel and turn on LED (use string channel ID)
        channel_enum = ChannelID[channel.upper()]
        self.ctrl.activate_channel(channel_enum)
        time.sleep(0.1)  # Let channel activate
        
        # Set LED intensity (HAL uses string channel internally)
        if not self.ctrl.set_intensity(channel, led_intensity):
            logger.error(f"Failed to set LED intensity for channel {channel}")
            return {}
        
        time.sleep(led_delay * 2)  # Extra settling time for first measurement
        
        # Collect measurements
        signal_levels = []
        peak_wavelengths = []
        
        for i in range(num_measurements):
            # Take multiple scans and average them
            scan_spectra = []
            for scan in range(scans_per_measurement):
                spectrum = self.spec.intensities()
                scan_spectra.append(spectrum)
            
            # Average the scans
            avg_spectrum = np.mean(scan_spectra, axis=0)
            wavelengths = self.spec.wavelengths()
            
            # Measure signal level (average in SPR range)
            mask = (wavelengths >= 600) & (wavelengths <= 680)
            signal = np.mean(avg_spectrum[mask])
            signal_levels.append(signal)
            
            # Find peak
            peak = self.find_spr_peak(avg_spectrum, wavelengths)
            if not np.isnan(peak):
                peak_wavelengths.append(peak)
            
            # Progress
            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i+1}/{num_measurements} measurements...")
        
        # Turn off LED
        self.ctrl.set_intensity(channel, 0)
        
        # Calculate statistics
        signal_levels = np.array(signal_levels)
        peak_wavelengths = np.array(peak_wavelengths)
        
        mean_signal = np.mean(signal_levels)
        std_signal = np.std(signal_levels)
        snr = mean_signal / std_signal if std_signal > 0 else 0
        
        mean_peak = np.mean(peak_wavelengths)
        std_peak = np.std(peak_wavelengths)
        
        # Convert to RU using system-specific calibration: 1 nm = 355 RU
        # This is the calibrated sensitivity for this SPR system
        RU_PER_NM = 355.0
        estimated_ru = std_peak * RU_PER_NM
        
        results = {
            'integration_time_ms': integration_time_ms,
            'scans_per_measurement': scans_per_measurement,
            'actual_acquisition_time_ms': actual_time_ms,
            'led_delay_s': led_delay,
            'num_measurements': len(peak_wavelengths),
            'mean_signal_counts': float(mean_signal),
            'std_signal_counts': float(std_signal),
            'snr': float(snr),
            'mean_peak_nm': float(mean_peak),
            'std_peak_nm': float(std_peak),
            'estimated_ru_noise': float(estimated_ru),
            'signal_levels': signal_levels.tolist()[:20],  # Save first 20 for debugging
            'peak_wavelengths': peak_wavelengths.tolist()[:20]
        }
        
        logger.info(f"\n📊 Results:")
        logger.info(f"   Integration: {integration_time_ms:.1f}ms × {scans_per_measurement} scans = {actual_time_ms:.1f}ms total")
        logger.info(f"   Signal: {mean_signal:.1f} ± {std_signal:.1f} counts (SNR: {snr:.1f})")
        logger.info(f"   Peak: {mean_peak:.3f} ± {std_peak:.4f} nm")
        logger.info(f"   Estimated RU noise: {estimated_ru:.2f} RU")
        
        return results
        logger.info(f"   Signal: {mean_signal:.1f} ± {std_signal:.1f} counts (SNR: {snr:.1f})")
        logger.info(f"   Peak: {mean_peak:.3f} ± {std_peak:.3f} nm")
        logger.info(f"   Estimated noise: {estimated_ru:.2f} RU")
        
        return results
    
    def optimize_channel(
        self,
        channel: str,
        integration_times_ms: List[float] = [20, 30, 40, 50, 60, 80, 100],
        target_ru_noise: float = 2.0,
        num_measurements: int = 100
    ) -> Dict:
        """Find optimal integration time for a channel.
        
        Args:
            channel: Channel to optimize
            integration_times_ms: List of integration times to test
            target_ru_noise: Target RU noise threshold
            num_measurements: Measurements per integration time
            
        Returns:
            Dictionary with optimization results and recommendation
        """
        logger.info(f"\n{'#'*70}")
        logger.info(f"# OPTIMIZING CHANNEL {channel.upper()}")
        logger.info(f"# Target: <{target_ru_noise} RU noise")
        logger.info(f"# Testing {len(integration_times_ms)} integration times")
        logger.info(f"{'#'*70}\n")
        
        test_results = []
        
        for int_time in integration_times_ms:
            result = self.test_integration_time(
                channel=channel,
                integration_time_ms=int_time,
                num_measurements=num_measurements
            )
            test_results.append(result)
            time.sleep(1.0)  # Brief pause between tests
        
        # Find optimal integration time
        # Strategy: Minimum integration time that meets RU target
        optimal_result = None
        for result in sorted(test_results, key=lambda x: x['integration_time_ms']):
            if result['estimated_ru_noise'] <= target_ru_noise:
                optimal_result = result
                break
        
        if optimal_result is None:
            # None met target - use longest integration time
            optimal_result = max(test_results, key=lambda x: x['integration_time_ms'])
            logger.warning(f"⚠️ No integration time met {target_ru_noise} RU target!")
            logger.warning(f"   Best result: {optimal_result['estimated_ru_noise']:.2f} RU")
        else:
            logger.info(f"\n✅ Optimal integration time found!")
            logger.info(f"   {optimal_result['integration_time_ms']:.1f}ms")
            logger.info(f"   Noise: {optimal_result['estimated_ru_noise']:.2f} RU")
            logger.info(f"   SNR: {optimal_result['snr']:.1f}")
        
        return {
            'channel': channel,
            'test_results': test_results,
            'optimal': optimal_result,
            'target_ru_noise': target_ru_noise
        }
    
    def plot_results(self, channel_results: Dict, output_file: str = 'integration_time_optimization.png'):
        """Create visualization of optimization results.
        
        Args:
            channel_results: Results dictionary from optimize_channel
            output_file: Output filename for plot
        """
        test_results = channel_results['test_results']
        optimal = channel_results['optimal']
        channel = channel_results['channel']
        
        int_times = [r['integration_time_ms'] for r in test_results]
        ru_noise = [r['estimated_ru_noise'] for r in test_results]
        snr = [r['snr'] for r in test_results]
        signal = [r['mean_signal_counts'] for r in test_results]
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f'Integration Time Optimization - Channel {channel.upper()}', 
                     fontsize=14, fontweight='bold')
        
        # Plot 1: RU Noise vs Integration Time
        ax1 = axes[0, 0]
        ax1.plot(int_times, ru_noise, 'b-o', linewidth=2, markersize=8)
        ax1.axhline(y=2.0, color='r', linestyle='--', label='Target (2 RU)')
        ax1.axvline(x=optimal['integration_time_ms'], color='g', linestyle='--', 
                   label=f'Optimal ({optimal["integration_time_ms"]:.0f}ms)')
        ax1.set_xlabel('Integration Time (ms)', fontsize=12)
        ax1.set_ylabel('Estimated RU Noise', fontsize=12)
        ax1.set_title('Sensorgram Noise vs Integration Time', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Plot 2: SNR vs Integration Time
        ax2 = axes[0, 1]
        ax2.plot(int_times, snr, 'g-o', linewidth=2, markersize=8)
        ax2.axvline(x=optimal['integration_time_ms'], color='g', linestyle='--', 
                   label=f'Optimal ({optimal["integration_time_ms"]:.0f}ms)')
        ax2.set_xlabel('Integration Time (ms)', fontsize=12)
        ax2.set_ylabel('Signal-to-Noise Ratio', fontsize=12)
        ax2.set_title('SNR vs Integration Time', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Plot 3: Signal Level vs Integration Time
        ax3 = axes[1, 0]
        ax3.plot(int_times, signal, 'orange', marker='o', linewidth=2, markersize=8)
        ax3.axvline(x=optimal['integration_time_ms'], color='g', linestyle='--', 
                   label=f'Optimal ({optimal["integration_time_ms"]:.0f}ms)')
        ax3.set_xlabel('Integration Time (ms)', fontsize=12)
        ax3.set_ylabel('Mean Signal (counts)', fontsize=12)
        ax3.set_title('Signal Level vs Integration Time', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        
        # Plot 4: Acquisition Rate Comparison
        ax4 = axes[1, 1]
        
        # Calculate acquisition rates (including LED delay and USB transfer ~50ms)
        current_int_time = 100  # Current setting
        current_led_delay = 100 if not self.afterglow_correction else \
                           self.afterglow_correction.get_optimal_led_delay(current_int_time, 2.0) * 1000
        current_total = current_int_time + current_led_delay + 50  # ms per channel
        current_rate = 1000.0 / current_total  # Hz
        
        optimal_int_time = optimal['integration_time_ms']
        optimal_led_delay = optimal['led_delay_s'] * 1000
        optimal_total = optimal_int_time + optimal_led_delay + 50
        optimal_rate = 1000.0 / optimal_total
        
        speedup = optimal_rate / current_rate
        
        categories = ['Current\nSetup', 'Optimized\nSetup']
        rates = [current_rate, optimal_rate]
        colors = ['#ff6b6b', '#51cf66']
        
        bars = ax4.bar(categories, rates, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax4.set_ylabel('Acquisition Rate (Hz)', fontsize=12)
        ax4.set_title('Acquisition Speed Comparison', fontsize=13, fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bar, rate in zip(bars, rates):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{rate:.2f} Hz',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        # Add speedup annotation
        ax4.text(0.5, max(rates) * 0.5, 
                f'{speedup:.1f}× FASTER',
                ha='center', fontsize=14, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"\n📊 Plot saved: {output_file}")
        plt.show()
    
    def save_results(self, output_file: str = 'integration_time_optimization.json'):
        """Save optimization results to JSON file."""
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"💾 Results saved: {output_path}")


def main():
    """Run integration time optimization."""
    print("\n" + "="*70)
    print(" SPR INTEGRATION TIME OPTIMIZER")
    print("="*70)
    print("\nThis tool finds the optimal integration time for your SPR setup.")
    print("It will test multiple integration times and measure signal quality.")
    print("\n⚠️  IMPORTANT: Ensure stable conditions (no binding events)")
    print("    - Equilibrated temperature")
    print("    - Stable buffer flow")
    print("    - No injections during test")
    print("\nEstimated time: ~10-15 minutes per channel")
    print("="*70 + "\n")
    
    input("Press ENTER to start...")
    
    # Connect to hardware
    logger.info("🔌 Connecting to hardware...")
    
    device_config = get_device_config()
    ctrl = PicoP4SPRHAL()
    if not ctrl.connect():
        logger.error("❌ Failed to connect to controller")
        return
    
    devices = list_devices()
    if not devices:
        logger.error("❌ No spectrometer found")
        ctrl.disconnect()
        return
    
    spec = Spectrometer(devices[0])
    logger.info(f"✅ Connected: {spec.model}")
    
    # Create optimizer
    optimizer = IntegrationTimeOptimizer(ctrl, spec)
    
    # Test channels
    channels_to_test = ['a']  # Start with channel A
    
    print(f"\n📋 Testing channel(s): {', '.join([ch.upper() for ch in channels_to_test])}")
    print("    Integration times: 20, 25, 40, 50, 67, 100, 200 ms")
    print("    NORMALIZED to 200ms total acquisition time:")
    print("      • 20ms × 10 scans = 200ms")
    print("      • 25ms × 8 scans = 200ms")
    print("      • 40ms × 5 scans = 200ms")
    print("      • 50ms × 4 scans = 200ms")
    print("      • 67ms × 3 scans = 201ms")
    print("      • 100ms × 2 scans = 200ms")
    print("      • 200ms × 1 scan = 200ms")
    print("    Measurements per time: 100")
    print("    Target noise: <2 RU\n")
    
    for channel in channels_to_test:
        results = optimizer.optimize_channel(
            channel=channel,
            integration_times_ms=[20, 25, 40, 50, 67, 100, 200],
            target_ru_noise=2.0,
            num_measurements=100
        )
        optimizer.results['channel_results'][channel] = results
        
        # Plot results
        optimizer.plot_results(results, f'integration_time_ch{channel}.png')
    
    # Save results
    optimizer.save_results('integration_time_optimization.json')
    
    # Print recommendations
    print("\n" + "="*70)
    print(" RECOMMENDATIONS")
    print("="*70 + "\n")
    
    for channel, results in optimizer.results['channel_results'].items():
        optimal = results['optimal']
        print(f"Channel {channel.upper()}:")
        print(f"  Optimal integration time: {optimal['integration_time_ms']:.1f}ms")
        print(f"  Expected RU noise: {optimal['estimated_ru_noise']:.2f} RU")
        print(f"  SNR: {optimal['snr']:.1f}")
        print(f"  LED delay: {optimal['led_delay_s']*1000:.1f}ms")
        print()
    
    # Disconnect
    ctrl.disconnect()
    logger.info("✅ Optimization complete!")


if __name__ == "__main__":
    main()
