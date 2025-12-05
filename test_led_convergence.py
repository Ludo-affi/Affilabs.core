"""LED Convergence Test - Aligned with Main Calibration Logic

Tests LED convergence with auto-boost to 80% saturation for optimal SNR.
Uses SAME convergence strategy as main calibration code (LEDCONVERGENCE.py):
- Intensity mode: Boost LED intensity, keep integration time fixed
- Time mode: Boost integration time, keep LED at 255

Features:
- Auto-boost to 80% of max detector count for optimal SNR
- Adaptive sampling: 10 rapid samples (no delay) + 20 steady-state samples
- Enhanced metrics: rise time, overshoot, convergence time, stability CV
- 3-panel diagnostic plots (intensity, normalized response, stability)
- Follows same parameter adjustment logic as LEDconverge/LEDnormalizationtime

Usage:
    python test_led_convergence.py [mode] [led]
    
    mode: 1=Real hardware, 2=Mock devices (default: 2)
    led: a, b, c, or d (default: a)
"""

import numpy as np
import time
import logging
import json
from typing import Dict, Tuple, Optional
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.led_normalization import (
    LEDNormalizer,
    PeakIntensityCalculator
)
from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer
from src.hardware.mock_devices import MockController, MockSpectrometer
from src.utils.controller import PicoP4SPR
from src.utils.usb4000_wrapper import USB4000

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_led_convergence_optimized(normalizer: LEDNormalizer, 
                                   results: Dict, 
                                   led: str = 'a', 
                                   mode: str = 'intensity',
                                   target_saturation: float = 0.8, 
                                   max_detector_count: int = 65535,
                                   num_samples: int = 30, 
                                   rapid_samples: int = 10) -> Dict:
    """
    Optimized LED convergence test with V1.9 firmware.
    
    Uses same convergence logic as main calibration code:
    - Intensity mode: Boost LED intensity, keep integration time fixed
    - Time mode: Boost integration time, keep LED at 255
    
    Features:
    1. Auto-boost to 80% of max detector count for optimal SNR
    2. Rapid initial sampling (no delays) to catch turn-on transient
    3. Adaptive sampling (fast then slow)
    
    Args:
        normalizer: LEDNormalizer instance
        results: Normalization results from normalize()
        led: LED to test (lowercase: 'a', 'b', 'c', 'd')
        mode: 'intensity' or 'time' (must match normalization mode)
        target_saturation: Target percentage of max detector count (0.8 = 80%)
        max_detector_count: Maximum detector counts (65535 for 16-bit)
        num_samples: Total samples to collect
        rapid_samples: Number of rapid samples at start (no delay)
    
    Returns:
        dict: Enhanced convergence metrics
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"OPTIMIZED LED {led.upper()} CONVERGENCE TEST ({mode.upper()} MODE)")
    logger.info(f"Target saturation: {target_saturation*100:.0f}% of detector max")
    logger.info(f"{'='*80}")
    
    # Step 1: Apply base normalization
    normalizer.apply_normalization(results, led.lower())
    base_params = results[led.lower()]
    
    # Step 2: Measure current intensity at normalized settings
    normalizer.controller.turn_on_channel(led.lower())
    time.sleep(0.2)  # Initial settling
    
    spectrum = normalizer.spectrometer.read_spectrum()
    if spectrum is None:
        raise ValueError("Failed to read spectrum")
    wavelengths = normalizer.spectrometer.get_wavelengths()
    current_intensity = normalizer.intensity_calculator.calculate(spectrum, wavelengths)
    
    logger.info(f"Current intensity at normalized settings: {current_intensity:.1f} counts")
    
    # Step 3: Calculate boost factor to reach target saturation
    target_count = max_detector_count * target_saturation
    boost_factor = target_count / current_intensity if current_intensity > 0 else 1.0
    
    logger.info(f"Target count ({target_saturation*100:.0f}% saturation): {target_count:.0f}")
    logger.info(f"Boost factor needed: {boost_factor:.2f}x")
    
    # Step 4: Apply boost using SAME LOGIC as main calibration code
    if mode == 'intensity':
        # INTENSITY MODE: Boost LED intensity, keep integration time fixed
        # This matches LEDnormalizationintensity + LEDconverge with adjust_leds=True
        
        current_integration_time = normalizer.spectrometer.get_integration_time()
        new_intensity = min(int(base_params['value'] * boost_factor), 255)
        
        logger.info(f"Intensity mode: Boosting LED {base_params['value']} → {new_intensity}")
        logger.info(f"  (keeping integration time fixed at {current_integration_time}ms)")
        
        normalizer.controller.set_intensity(led.lower(), new_intensity)
        boosted_param = new_intensity
        boosted_param_name = 'LED intensity'
        
    else:  # mode == 'time'
        # TIME MODE: Boost integration time, keep LED at 255
        # This matches LEDnormalizationtime logic
        
        current_led = normalizer.controller.get_led_intensities().get(led.lower(), 255)
        new_time = min(int(base_params['value'] * boost_factor), 200)
        
        logger.info(f"Time mode: Boosting integration time {base_params['value']}ms → {new_time}ms")
        logger.info(f"  (keeping LED intensity fixed at {current_led})")
        
        normalizer.spectrometer.set_integration_time(new_time)
        boosted_param = new_time
        boosted_param_name = 'integration time (ms)'
    
    # Turn off and prepare for convergence test
    normalizer.controller.turn_off_channels()
    time.sleep(0.5)  # Ensure complete off state
    
    # Step 5: Rapid convergence test - ADAPTIVE SAMPLING
    logger.info(f"\nStarting adaptive convergence test...")
    logger.info(f"Phase 1: {rapid_samples} rapid samples (no delay)")
    logger.info(f"Phase 2: {num_samples - rapid_samples} steady-state samples (100ms delay)")
    
    samples = []
    timestamps = []
    
    # Turn on LED and start timer
    start_time = time.time()
    normalizer.controller.turn_on_channel(led.lower())
    
    # Phase 1: Rapid sampling (catch turn-on transient)
    for i in range(rapid_samples):
        current_time = time.time() - start_time
        
        spectrum = normalizer.spectrometer.read_spectrum()
        if spectrum is None:
            logger.warning(f"Skipping sample {i+1} - spectrum read failed")
            continue
        wavelengths = normalizer.spectrometer.get_wavelengths()
        intensity = normalizer.intensity_calculator.calculate(spectrum, wavelengths)
        
        samples.append(intensity)
        timestamps.append(current_time)
        
        logger.info(f"  Rapid sample {i+1}/{rapid_samples} at t={current_time*1000:.1f}ms: {intensity:.1f} counts")
        # NO DELAY - back-to-back reads
    
    # Phase 2: Steady-state sampling (measure stability)
    for i in range(num_samples - rapid_samples):
        time.sleep(0.1)  # 100ms between samples
        
        current_time = time.time() - start_time
        
        spectrum = normalizer.spectrometer.read_spectrum()
        if spectrum is None:
            logger.warning(f"Skipping sample {i+1} - spectrum read failed")
            continue
        wavelengths = normalizer.spectrometer.get_wavelengths()
        intensity = normalizer.intensity_calculator.calculate(spectrum, wavelengths)
        
        samples.append(intensity)
        timestamps.append(current_time)
        
        logger.info(f"  Steady sample {i+1}/{num_samples-rapid_samples} at t={current_time:.2f}s: {intensity:.1f} counts")
    
    normalizer.controller.turn_off_channels()
    
    # Step 6: Advanced convergence analysis
    samples_array = np.array(samples)
    timestamps_array = np.array(timestamps)
    
    # Find convergence time (when reaches 95% of final value)
    final_value = np.mean(samples_array[-5:])  # Average last 5 samples
    convergence_threshold = final_value * 0.95
    converged_idx = np.where(samples_array >= convergence_threshold)[0]
    convergence_time = timestamps_array[converged_idx[0]] if len(converged_idx) > 0 else None
    
    # Calculate rise time (10% to 90% of final value)
    ten_percent = final_value * 0.1
    ninety_percent = final_value * 0.9
    rise_start_idx = np.where(samples_array >= ten_percent)[0]
    rise_end_idx = np.where(samples_array >= ninety_percent)[0]
    
    if len(rise_start_idx) > 0 and len(rise_end_idx) > 0:
        rise_time = timestamps_array[rise_end_idx[0]] - timestamps_array[rise_start_idx[0]]
    else:
        rise_time = None
    
    # Calculate steady-state stability (last 50% of samples)
    steady_start = len(samples_array) // 2
    steady_samples = samples_array[steady_start:]
    steady_mean = np.mean(steady_samples)
    steady_std = np.std(steady_samples)
    steady_cv = (steady_std / steady_mean) * 100 if steady_mean > 0 else 0
    
    # Peak overshoot
    peak_intensity = np.max(samples_array)
    overshoot = ((peak_intensity - final_value) / final_value) * 100 if final_value > 0 else 0
    
    # Saturation achievement
    saturation_achieved = (final_value / max_detector_count) * 100
    
    metrics = {
        'led': led,
        'mode': mode,
        'boosted_parameter': boosted_param_name,
        'target_count': target_count,
        'target_saturation_percent': target_saturation * 100,
        'boost_factor': boost_factor,
        'boosted_parameter': boosted_param,
        'samples': samples,
        'timestamps': timestamps,
        'convergence_time_ms': convergence_time * 1000 if convergence_time else None,
        'rise_time_ms': rise_time * 1000 if rise_time else None,
        'final_intensity': final_value,
        'steady_state_mean': steady_mean,
        'steady_state_std': steady_std,
        'steady_state_cv_percent': steady_cv,
        'peak_intensity': peak_intensity,
        'overshoot_percent': overshoot,
        'saturation_achieved_percent': saturation_achieved,
        'max_detector_count': max_detector_count
    }
    
    # Print enhanced summary
    logger.info(f"\n--- LED {led.upper()} OPTIMIZED Convergence Summary ---")
    logger.info(f"Mode: {mode.upper()} (boosted {boosted_param_name})")
    logger.info(f"Target: {target_count:.0f} counts ({target_saturation*100:.0f}% saturation)")
    logger.info(f"Boost factor: {boost_factor:.2f}x → {boosted_param_name} = {boosted_param}")
    if convergence_time:
        logger.info(f"Convergence time (to 95%): {metrics['convergence_time_ms']:.1f}ms")
    if rise_time:
        logger.info(f"Rise time (10%-90%): {metrics['rise_time_ms']:.1f}ms")
    logger.info(f"Final intensity: {final_value:.1f} counts ({saturation_achieved:.1f}% saturation)")
    logger.info(f"Peak overshoot: {overshoot:.2f}%")
    logger.info(f"Steady-state stability (CV): {steady_cv:.3f}%")
    logger.info(f"Steady-state: {steady_mean:.1f} ± {steady_std:.1f} counts")
    
    return metrics


def plot_optimized_convergence(metrics: Dict, save_path: Optional[str] = None, show_plot: bool = True):
    """
    Enhanced convergence plot with rise time, overshoot, and saturation markers.
    
    Args:
        metrics: Convergence metrics from test_led_convergence_optimized
        save_path: Path to save plot (optional)
        show_plot: Whether to display plot (default True)
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed, skipping plot")
        return
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    timestamps_ms = np.array(metrics['timestamps']) * 1000  # Convert to ms
    samples = np.array(metrics['samples'])
    
    # Plot 1: Intensity with key markers
    ax1 = axes[0]
    ax1.plot(timestamps_ms, samples, 'b-', linewidth=2, label='Measured Intensity')
    
    # Target line
    ax1.axhline(y=metrics['target_count'], color='r', linestyle='--', 
                linewidth=1.5, label=f"Target ({metrics['target_count']:.0f})")
    
    # Final value line
    ax1.axhline(y=metrics['final_intensity'], color='g', linestyle=':', 
                linewidth=1.5, label=f"Final ({metrics['final_intensity']:.0f})")
    
    # Convergence time marker
    if metrics['convergence_time_ms']:
        ax1.axvline(x=metrics['convergence_time_ms'], color='orange', linestyle='--',
                   linewidth=1, label=f"Conv. ({metrics['convergence_time_ms']:.1f}ms)")
    
    # Peak overshoot marker
    peak_idx = np.argmax(samples)
    ax1.plot(timestamps_ms[peak_idx], metrics['peak_intensity'], 'r*', 
            markersize=15, label=f"Peak ({metrics['overshoot_percent']:.1f}% overshoot)")
    
    ax1.set_xlabel('Time (ms)')
    ax1.set_ylabel('Intensity (counts)')
    ax1.set_title(f"LED {metrics['led'].upper()} Optimized Convergence ({metrics['mode'].upper()} mode, "
                 f"{metrics['target_saturation_percent']:.0f}% saturation target)")
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Normalized response (0-100%)
    ax2 = axes[1]
    normalized = (samples / metrics['final_intensity']) * 100
    ax2.plot(timestamps_ms, normalized, 'g-', linewidth=2)
    ax2.axhline(y=95, color='orange', linestyle='--', linewidth=1, label='95% threshold')
    ax2.axhline(y=100, color='r', linestyle='--', linewidth=1, label='100% (final)')
    
    if metrics['rise_time_ms']:
        # Mark 10% and 90% points
        ten_pct_idx = np.where(samples >= metrics['final_intensity'] * 0.1)[0][0]
        ninety_pct_idx = np.where(samples >= metrics['final_intensity'] * 0.9)[0][0]
        
        ax2.plot([timestamps_ms[ten_pct_idx], timestamps_ms[ninety_pct_idx]], 
                [10, 90], 'ro-', linewidth=2, markersize=8, 
                label=f"Rise time: {metrics['rise_time_ms']:.1f}ms")
    
    ax2.set_xlabel('Time (ms)')
    ax2.set_ylabel('Response (%)')
    ax2.set_title('Normalized LED Response')
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Stability (rolling standard deviation)
    ax3 = axes[2]
    window = 5
    rolling_std = np.array([np.std(samples[max(0, i-window):i+1]) for i in range(len(samples))])
    rolling_cv = (rolling_std / samples) * 100
    
    ax3.plot(timestamps_ms, rolling_cv, 'purple', linewidth=2)
    ax3.axhline(y=metrics['steady_state_cv_percent'], color='r', linestyle='--',
               linewidth=1.5, label=f"Steady-state CV: {metrics['steady_state_cv_percent']:.3f}%")
    ax3.set_xlabel('Time (ms)')
    ax3.set_ylabel('Coefficient of Variation (%)')
    ax3.set_title('Intensity Stability (Rolling CV)')
    ax3.legend(loc='best')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"Optimized convergence plot saved to {save_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def test_all_leds_convergence(normalizer: LEDNormalizer, 
                              results: Dict, 
                              mode: str = 'intensity',
                              target_saturation: float = 0.8,
                              generate_plots: bool = False) -> Dict:
    """
    Test convergence for all LEDs and generate comparative summary.
    
    Args:
        normalizer: LEDNormalizer instance
        results: Normalization results
        mode: 'intensity' or 'time'
        target_saturation: Target percentage of detector max
        generate_plots: Whether to generate individual LED plots
    
    Returns:
        dict: Convergence metrics for all LEDs
    """
    all_metrics = {}
    
    for led in ['a', 'b', 'c', 'd']:
        if led in results:
            logger.info(f"\n{'='*80}")
            logger.info(f"Testing LED {led.upper()} convergence...")
            logger.info(f"{'='*80}")
            
            try:
                metrics = test_led_convergence_optimized(
                    normalizer, results, led, mode,
                    target_saturation=target_saturation,
                    num_samples=30,
                    rapid_samples=10
                )
                all_metrics[led] = metrics
                
                if generate_plots:
                    plot_optimized_convergence(
                        metrics,
                        save_path=f'led_{led}_convergence_{mode}.png',
                        show_plot=False  # Don't block, just save
                    )
                
                time.sleep(0.5)  # Cool down between LEDs
                
            except Exception as e:
                logger.error(f"LED {led.upper()} convergence test failed: {e}")
                continue
    
    # Comparative summary
    logger.info(f"\n{'='*80}")
    logger.info(f"COMPARATIVE LED CONVERGENCE SUMMARY ({mode.upper()} MODE)")
    logger.info(f"{'='*80}")
    logger.info(f"{'LED':<5} {'Conv Time':<15} {'Rise Time':<15} {'Stability':<12} {'Final Sat':<15}")
    logger.info(f"{'-'*80}")
    
    for led, metrics in all_metrics.items():
        conv_time = f"{metrics['convergence_time_ms']:.1f}ms" if metrics['convergence_time_ms'] else "N/A"
        rise_time = f"{metrics['rise_time_ms']:.1f}ms" if metrics['rise_time_ms'] else "N/A"
        stability = f"{metrics['steady_state_cv_percent']:.3f}%"
        saturation = f"{metrics['saturation_achieved_percent']:.1f}%"
        logger.info(f"{led.upper():<5} {conv_time:<15} {rise_time:<15} {stability:<12} {saturation:<15}")
    
    return all_metrics


if __name__ == "__main__":
    """
    Standalone convergence test.
    
    Usage:
        python test_led_convergence.py [mode] [led]
        
        mode: 1=Real hardware, 2=Mock devices (default: 2)
        led: a, b, c, or d (default: a)
    """
    
    test_mode = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    test_led = sys.argv[2].lower() if len(sys.argv) > 2 else 'a'
    
    print(f"\n{'='*80}")
    print("LED CONVERGENCE TEST (Standalone)")
    print(f"{'='*80}")
    print(f"Mode: {'Real Hardware' if test_mode == 1 else 'Mock Devices'}")
    print(f"LED: {test_led.upper()}")
    print(f"{'='*80}\n")
    
    controller = None
    spectrometer = None
    controller_hw = None
    spectrometer_hw = None
    
    try:
        # Initialize hardware
        if test_mode == 1:
            # Real hardware
            print("Initializing real hardware...")
            controller_hw = PicoP4SPR()
            controller_hw.open()
            
            spectrometer_hw = USB4000()
            spectrometer_hw.set_integration_time(10)
            
            controller = wrap_existing_controller(controller_hw)
            spectrometer = wrap_existing_spectrometer(spectrometer_hw)
            controller.connect()
            spectrometer.connect()
            
        else:
            # Mock devices
            print("Using mock devices...")
            controller = MockController()
            spectrometer = MockSpectrometer()
            controller.connect()
            spectrometer.connect()
        
        # Create normalizer
        intensity_calc = PeakIntensityCalculator()
        normalizer = LEDNormalizer(controller, spectrometer, intensity_calc)
        
        # First, normalize the LED (using intensity mode as example)
        print(f"\nStep 1: Normalizing LED {test_led.upper()}...")
        results = normalizer.normalize(
            mode='intensity',
            target_value=30000,
            tolerance=500,
            max_iterations=10
        )
        
        # Then test convergence with 80% saturation boost
        print(f"\nStep 2: Testing convergence with 80% saturation boost...")
        metrics = test_led_convergence_optimized(
            normalizer,
            results,
            led=test_led,
            mode='intensity',
            target_saturation=0.8,
            num_samples=30,
            rapid_samples=10
        )
        
        # Generate plot
        print(f"\nStep 3: Generating convergence plot...")
        plot_optimized_convergence(
            metrics,
            save_path=f'led_{test_led}_convergence_standalone.png',
            show_plot=True
        )
        
        # Save metrics
        print(f"\nStep 4: Saving convergence data...")
        with open(f'led_{test_led}_convergence_metrics.json', 'w') as f:
            # Convert numpy arrays to lists for JSON
            serializable = {
                k: (v.tolist() if isinstance(v, np.ndarray) else v)
                for k, v in metrics.items()
            }
            json.dump(serializable, f, indent=2)
        
        print(f"\n✅ Convergence test complete!")
        print(f"   - Plot saved: led_{test_led}_convergence_standalone.png")
        print(f"   - Data saved: led_{test_led}_convergence_metrics.json")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            if controller:
                controller.turn_off_channels()
                controller.disconnect()
            if spectrometer:
                spectrometer.disconnect()
            if test_mode == 1:
                if controller_hw and hasattr(controller_hw, 'close'):
                    controller_hw.close()
                if spectrometer_hw and hasattr(spectrometer_hw, 'disconnect'):
                    spectrometer_hw.disconnect()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
