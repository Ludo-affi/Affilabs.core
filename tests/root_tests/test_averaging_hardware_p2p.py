"""Hardware test: Compare averaging methods using real peak-to-peak sensorgram variation.

This script acquires real spectra from hardware and tests different averaging strategies
by measuring the peak-to-peak (p2p) variation in the resulting sensorgram - the ultimate
measure of stability and accuracy.

Methods tested:
1. Standard average (1/3, 1/3, 1/3)
2. Weighted averages with different weights
3. Scans 2&3 only (0, 0.5, 0.5) with CV% reporting

Author: Hardware validation of scan averaging optimization
Date: 2025-12-14
"""

import sys
import time
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import matplotlib.pyplot as plt

# Add project paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "affilabs"))

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger


def weighted_average(
    scan1: np.ndarray,
    scan2: np.ndarray,
    scan3: np.ndarray,
    weights: Tuple[float, float, float]
) -> np.ndarray:
    """Weighted average of 3 scans."""
    w1, w2, w3 = weights
    return w1 * scan1 + w2 * scan2 + w3 * scan3


def get_max_intensity(spectrum: np.ndarray) -> float:
    """Get maximum intensity from spectrum."""
    return np.max(spectrum)


def is_saturated(spectrum: np.ndarray, threshold: float = 65000) -> bool:
    """Check if spectrum is saturated."""
    return np.max(spectrum) >= threshold


def find_optimal_intensity(
    hardware_mgr,
    channel: str,
    integration_ms: int,
    target_counts: float = 45000,
    max_attempts: int = 20
) -> int:
    """Find LED intensity that gives ~target_counts without saturation.
    
    Returns:
        Optimal LED intensity (0-255)
    """
    print(f"🔍 Finding optimal LED intensity for ~{target_counts:.0f} counts...")
    print(f"   Integration time: {integration_ms}ms")

    # Start with a very low intensity to avoid saturation
    test_intensity = 10
    hardware_mgr.usb.set_integration(integration_ms * 1000)

    for attempt in range(max_attempts):
        # Set LED and acquire
        hardware_mgr.ctrl.set_intensity(channel, test_intensity)
        time.sleep(0.05)

        spectrum = hardware_mgr.usb.read_intensity()
        hardware_mgr.ctrl.set_intensity(channel, 0)

        if spectrum is None:
            print("   Failed to read spectrum, trying again...")
            continue

        max_counts = np.max(spectrum)

        # Check saturation - be more aggressive at reducing
        if max_counts >= 65000:
            print(f"   Intensity {test_intensity}: SATURATED ({max_counts:.0f} counts) - reducing aggressively")
            test_intensity = max(1, int(test_intensity * 0.5))  # Cut in half, minimum 1
            time.sleep(0.05)
            continue

        # Check if we're in the right range (35K-50K)
        if 35000 <= max_counts <= 50000:
            print(f"   ✅ Optimal intensity: {test_intensity} → {max_counts:.0f} counts")
            return test_intensity

        # If too low, increase
        if max_counts < 35000:
            ratio = target_counts / max_counts
            test_intensity = int(test_intensity * ratio * 0.8)  # Conservative increase
            test_intensity = max(1, min(255, test_intensity))
            print(f"   Intensity {test_intensity}: {max_counts:.0f} counts - increasing...")
            time.sleep(0.05)
            continue

        # If slightly too high (50K-65K), reduce carefully
        if max_counts > 50000:
            ratio = target_counts / max_counts
            test_intensity = int(test_intensity * ratio * 0.9)
            test_intensity = max(1, test_intensity)
            print(f"   Intensity {test_intensity}: {max_counts:.0f} counts - reducing...")
            time.sleep(0.05)

    print(f"   ⚠️  WARNING: Could not find optimal intensity after {max_attempts} attempts")
    print(f"   ⚠️  Consider reducing integration time (currently {integration_ms}ms)")
    print(f"   ⚠️  Using intensity {test_intensity} anyway")
    return test_intensity


def acquire_three_scans_hardware(
    hardware_mgr: HardwareManager,
    channel: str,
    led_intensity: int,
    integration_ms: int = 12
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Acquire 3 scans from hardware for one channel.
    
    Returns:
        scan1, scan2, scan3, wavelengths
    """
    ctrl = hardware_mgr.ctrl
    usb = hardware_mgr.usb

    # Set LED
    ctrl.set_intensity(channel, led_intensity)
    time.sleep(0.045)  # PRE LED delay

    # Set integration time
    usb.set_integration(integration_ms * 1000)  # Convert ms to µs

    # Acquire 3 scans
    scans = []
    for i in range(3):
        spectrum = usb.read_intensity()
        wavelengths = usb.read_wavelength()
        if spectrum is not None and wavelengths is not None:
            scans.append(spectrum)
        else:
            raise RuntimeError(f"Failed to read scan {i+1}")
        time.sleep(0.005)  # Small delay between scans

    # Turn off LED
    ctrl.set_intensity(channel, 0)
    time.sleep(0.005)  # POST LED delay

    return scans[0], scans[1], scans[2], wavelengths


def run_hardware_p2p_test(
    port: str,
    channel: str = 'a',
    led_intensity: int = 255,
    integration_ms: int = 12,
    num_cycles: int = 20
) -> Dict:
    """Run hardware test comparing averaging methods via p2p variation.
    
    Args:
        port: COM port for controller
        channel: LED channel to test ('a', 'b', 'c', 'd')
        led_intensity: LED intensity (0-255)
        integration_ms: Integration time in milliseconds
        num_cycles: Number of measurement cycles
        
    Returns:
        Dictionary with results for each averaging method
    """
    print(f"\n{'='*80}")
    print("HARDWARE P2P VARIATION TEST - Averaging Method Comparison")
    print(f"{'='*80}")
    print(f"Port: {port}")
    print(f"Channel: {channel.upper()}")
    print(f"LED Intensity: {led_intensity}")
    print(f"Integration: {integration_ms}ms")
    print(f"Cycles: {num_cycles}")
    print(f"{'='*80}\n")

    # Initialize hardware
    print("🔌 Connecting to hardware...")
    hardware_mgr = HardwareManager()

    # Scan and connect to hardware (blocking until connected)
    hardware_mgr.scan_and_connect(auto_connect=True)

    # Wait for connection to complete (scan_and_connect runs in background thread)
    max_wait = 10  # seconds
    wait_start = time.time()
    while not hardware_mgr.connected and (time.time() - wait_start) < max_wait:
        time.sleep(0.1)

    if not hardware_mgr.ctrl:
        raise RuntimeError("Failed to connect to controller")

    if not hardware_mgr.usb:
        raise RuntimeError("Failed to connect to USB4000 spectrometer")

    print("✅ Hardware connected")
    print(f"   Controller: {hardware_mgr.ctrl.name}")
    print(f"   Spectrometer: {hardware_mgr.usb.serial_number if hasattr(hardware_mgr.usb, 'serial_number') else 'USB4000'}")
    print()

    # Set LED intensity
    if led_intensity is None:
        # Auto-set based on channel: A/D at 80%, B/C at 20%
        if channel.lower() in ['a', 'd']:
            led_intensity = int(255 * 0.8)  # 204 (80%)
            print(f"   Auto-setting LED intensity for channel {channel.upper()}: {led_intensity} (80%)")
        else:  # B or C
            led_intensity = int(255 * 0.2)  # 51 (20%)
            print(f"   Auto-setting LED intensity for channel {channel.upper()}: {led_intensity} (20%)")
    else:
        print(f"   Using specified LED intensity: {led_intensity}")

    # Quick saturation check
    print(f"   Checking for saturation at {led_intensity} intensity...")
    hardware_mgr.ctrl.set_intensity(channel, led_intensity)
    time.sleep(0.05)
    test_spectrum = hardware_mgr.usb.read_intensity()
    hardware_mgr.ctrl.set_intensity(channel, 0)

    if test_spectrum is not None:
        max_test = np.max(test_spectrum)
        if max_test >= 65000:
            print(f"   ⚠️  WARNING: SATURATED at {max_test:.0f} counts!")
            print("   ⚠️  Reduce LED intensity or integration time")
        else:
            print(f"   ✅ OK: {max_test:.0f} counts (no saturation)")
    print()

    # Storage for results (track max intensities)
    saturated_cycles = []
    methods = {
        'standard': {'weights': (1/3, 1/3, 1/3), 'max_intensities': [], 'label': 'Standard (1/3, 1/3, 1/3)'},
        'weighted_02': {'weights': (0.2, 0.4, 0.4), 'max_intensities': [], 'label': 'Weighted (0.2, 0.4, 0.4)'},
        'weighted_01': {'weights': (0.1, 0.45, 0.45), 'max_intensities': [], 'label': 'Weighted (0.1, 0.45, 0.45)'},
        'weighted_015': {'weights': (0.15, 0.425, 0.425), 'max_intensities': [], 'label': 'Weighted (0.15, 0.425, 0.425)'},
        'scans_23': {'weights': (0.0, 0.5, 0.5), 'max_intensities': [], 'label': 'Scans 2&3 Only'},
    }

    # Acquire data
    print(f"📊 Acquiring {num_cycles} cycles (3 scans each)...\n")

    for cycle in range(num_cycles):
        print(f"  Cycle {cycle+1}/{num_cycles}...", end=' ', flush=True)

        try:
            # Acquire 3 scans from hardware
            scan1, scan2, scan3, wavelengths = acquire_three_scans_hardware(
                hardware_mgr, channel, led_intensity, integration_ms
            )

            # Check for saturation in any scan
            if is_saturated(scan1) or is_saturated(scan2) or is_saturated(scan3):
                print("⚠️ SATURATED - skipping")
                saturated_cycles.append(cycle)
                continue

            # Test each averaging method on the SAME raw data
            for method_name, method_data in methods.items():
                weights = method_data['weights']
                avg_spectrum = weighted_average(scan1, scan2, scan3, weights)

                # Get maximum intensity from averaged spectrum
                max_intensity = get_max_intensity(avg_spectrum)
                method_data['max_intensities'].append(max_intensity)

            print("✓")
            time.sleep(0.1)  # Brief pause between cycles

        except Exception as e:
            print(f"✗ Error: {e}")
            continue

    # Cleanup
    print("\n🔌 Disconnecting hardware...")
    hardware_mgr.disconnect_all()
    print("✅ Hardware disconnected\n")

    # Report saturation issues
    if saturated_cycles:
        print(f"\n⚠️  WARNING: {len(saturated_cycles)} cycles were saturated and excluded")
        print(f"   Saturated cycles: {saturated_cycles}")

    # Calculate statistics - CV% of max intensity
    print(f"\n{'='*80}")
    print("RESULTS - CV% of Maximum Intensity (No Saturation)")
    print(f"{'='*80}")
    print(f"{'Method':<35} {'Mean Max':<12} {'Std Dev':<12} {'CV%':<10}")
    print(f"{'-'*80}")

    results_summary = {}

    for method_name, method_data in methods.items():
        max_array = np.array(method_data['max_intensities'])

        if len(max_array) > 0:
            mean_max = np.mean(max_array)
            std_max = np.std(max_array)
            cv_percent = (std_max / mean_max) * 100

            label = method_data['label']

            print(f"{label:<35} {mean_max:>10.1f}   {std_max:>10.2f}   {cv_percent:>8.3f}%")

            results_summary[method_name] = {
                'mean_max': mean_max,
                'std_max': std_max,
                'cv_percent': cv_percent,
                'max_intensities': max_array,
                'label': label
            }

    print(f"{'='*80}\n")

    # Find best method (lowest CV%)
    best_method = min(results_summary.items(), key=lambda x: x[1]['cv_percent'])
    standard_cv = results_summary['standard']['cv_percent']
    best_cv = best_method[1]['cv_percent']
    improvement = ((standard_cv - best_cv) / standard_cv) * 100

    print("📈 ANALYSIS:")
    print(f"   • Standard method CV%: {standard_cv:.3f}%")
    print(f"   • Best method: {best_method[1]['label']}")
    print(f"   • Best CV%: {best_cv:.3f}%")
    print(f"   • Improvement: {improvement:.1f}% reduction in CV%")
    print("\n   Lower CV% = More stable/consistent measurements")

    print(f"\n{'='*80}\n")

    return results_summary


def plot_results(results_summary: Dict, save_path: str = "hardware_cv_comparison.png"):
    """Plot max intensity traces and CV% comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Plot 1: Max intensity traces over time
    colors = ['blue', 'orange', 'green', 'red', 'purple']
    for i, (method_name, data) in enumerate(results_summary.items()):
        max_intensities = data['max_intensities']
        cycles = np.arange(len(max_intensities))
        ax1.plot(cycles, max_intensities, 'o-', label=data['label'],
                color=colors[i], alpha=0.7, linewidth=1.5, markersize=4)

    ax1.set_xlabel('Cycle Number', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Maximum Intensity (counts)', fontsize=12, fontweight='bold')
    ax1.set_title('Max Intensity Stability Comparison', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Plot 2: CV% comparison
    method_labels = [data['label'] for data in results_summary.values()]
    cv_values = [data['cv_percent'] for data in results_summary.values()]

    bars = ax2.bar(range(len(method_labels)), cv_values, color=colors[:len(method_labels)])
    ax2.set_xticks(range(len(method_labels)))
    ax2.set_xticklabels([label.split('(')[0].strip() for label in method_labels],
                         rotation=45, ha='right', fontsize=10)
    ax2.set_ylabel('CV% of Max Intensity', fontsize=12, fontweight='bold')
    ax2.set_title('Stability Comparison (Lower is Better)', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, cv_values)):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{val:.3f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"✅ Plot saved as '{save_path}'")
    plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test averaging methods using hardware p2p variation")
    parser.add_argument("port", help="COM port for controller (e.g., COM5)")
    parser.add_argument("--channel", default="a", choices=['a', 'b', 'c', 'd'],
                       help="LED channel to test (default: a)")
    parser.add_argument("--intensity", type=int, default=None,
                       help="LED intensity 0-255 (default: auto-detect, or 204 for A/D, 51 for B/C)")
    parser.add_argument("--integration", type=int, default=30,
                       help="Integration time in ms (default: 30)")
    parser.add_argument("--cycles", type=int, default=20,
                       help="Number of measurement cycles (default: 20)")

    args = parser.parse_args()

    try:
        # Run hardware test
        results = run_hardware_p2p_test(
            port=args.port,
            channel=args.channel,
            led_intensity=args.intensity,
            integration_ms=args.integration,
            num_cycles=args.cycles
        )

        # Plot results
        plot_results(results)

        print("\n✅ Hardware CV% test complete!\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
