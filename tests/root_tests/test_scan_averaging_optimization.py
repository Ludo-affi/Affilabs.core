"""Test script for optimizing 3-scan averaging to reduce first-scan rise time effects.

Two approaches tested:
1. Weighted average - less weight to scan 1, more to scans 2&3
2. CV% analysis - use only scans 2&3 for final average

Author: Testing weighted averaging for SPR measurements
Date: 2025-12-14
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Dict


def simulate_scans_with_rise_time(
    baseline_spectrum: np.ndarray,
    rise_time_effect: float = 0.05,
    noise_level: float = 0.01
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate 3 scans where scan 1 has rise time effects.
    
    Args:
        baseline_spectrum: Ground truth spectrum
        rise_time_effect: Fractional deviation for scan 1 (e.g., 0.05 = 5% lower)
        noise_level: Random noise added to each scan
        
    Returns:
        scan1, scan2, scan3 as numpy arrays
    """
    # Scan 1: Affected by rise time (systematically lower)
    scan1 = baseline_spectrum * (1 - rise_time_effect) + np.random.normal(0, noise_level, len(baseline_spectrum))

    # Scans 2 & 3: Stable, just noise
    scan2 = baseline_spectrum + np.random.normal(0, noise_level, len(baseline_spectrum))
    scan3 = baseline_spectrum + np.random.normal(0, noise_level, len(baseline_spectrum))

    return scan1, scan2, scan3


def standard_average(scan1: np.ndarray, scan2: np.ndarray, scan3: np.ndarray) -> np.ndarray:
    """Standard equal-weight average of 3 scans."""
    return np.mean([scan1, scan2, scan3], axis=0)


def weighted_average(
    scan1: np.ndarray,
    scan2: np.ndarray,
    scan3: np.ndarray,
    weights: Tuple[float, float, float] = (0.2, 0.4, 0.4)
) -> np.ndarray:
    """Weighted average giving less weight to scan 1.
    
    Args:
        scan1, scan2, scan3: Input spectra
        weights: Tuple of (w1, w2, w3) where w1 + w2 + w3 = 1.0
                 Default: (0.2, 0.4, 0.4) gives 20% to scan1, 40% each to scan2&3
                 
    Returns:
        Weighted average spectrum
    """
    w1, w2, w3 = weights
    assert abs(w1 + w2 + w3 - 1.0) < 1e-6, "Weights must sum to 1.0"
    return w1 * scan1 + w2 * scan2 + w3 * scan3


def scans_2_3_only(scan1: np.ndarray, scan2: np.ndarray, scan3: np.ndarray) -> Tuple[np.ndarray, float]:
    """Average only scans 2 and 3, report CV%.
    
    Args:
        scan1, scan2, scan3: Input spectra (scan1 ignored)
        
    Returns:
        average_spectrum: Mean of scan2 and scan3
        cv_percent: Coefficient of variation (%) between scan2 and scan3
    """
    # Average of scan 2 and 3
    avg_spectrum = np.mean([scan2, scan3], axis=0)

    # Calculate CV% across the spectrum
    # CV = (std / mean) * 100
    mean_vals = avg_spectrum
    std_vals = np.std([scan2, scan3], axis=0)

    # Compute mean CV% across all wavelengths (excluding zeros)
    mask = mean_vals > 1e-6  # Avoid division by zero
    cv_values = (std_vals[mask] / mean_vals[mask]) * 100
    mean_cv_percent = np.mean(cv_values)

    return avg_spectrum, mean_cv_percent


def calculate_rmse(predicted: np.ndarray, ground_truth: np.ndarray) -> float:
    """Calculate root mean squared error."""
    return np.sqrt(np.mean((predicted - ground_truth) ** 2))


def run_comparison_test(
    num_tests: int = 100,
    rise_time_effects: list = [0.01, 0.03, 0.05, 0.1],
    noise_level: float = 0.01
) -> Dict:
    """Run comparison tests across different rise time scenarios.
    
    Args:
        num_tests: Number of Monte Carlo simulations per scenario
        rise_time_effects: List of rise time effect magnitudes to test
        noise_level: Random noise level
        
    Returns:
        Dictionary with results for each method
    """
    results = {
        'rise_time_effects': rise_time_effects,
        'standard_rmse': [],
        'weighted_02_04_04_rmse': [],
        'weighted_01_045_045_rmse': [],
        'weighted_015_0425_0425_rmse': [],
        'scans_2_3_rmse': [],
        'scans_2_3_cv': []
    }

    # Ground truth spectrum (simulated SPR curve)
    wavelengths = np.linspace(600, 800, 2048)
    ground_truth = 30000 + 20000 * np.exp(-((wavelengths - 660) ** 2) / (2 * 15 ** 2))

    for rise_effect in rise_time_effects:
        rmse_standard = []
        rmse_weighted_02 = []
        rmse_weighted_01 = []
        rmse_weighted_015 = []
        rmse_scans_23 = []
        cv_scans_23 = []

        for _ in range(num_tests):
            # Simulate scans
            scan1, scan2, scan3 = simulate_scans_with_rise_time(
                ground_truth,
                rise_time_effect=rise_effect,
                noise_level=noise_level
            )

            # Test all methods
            avg_standard = standard_average(scan1, scan2, scan3)
            avg_weighted_02 = weighted_average(scan1, scan2, scan3, weights=(0.2, 0.4, 0.4))
            avg_weighted_01 = weighted_average(scan1, scan2, scan3, weights=(0.1, 0.45, 0.45))
            avg_weighted_015 = weighted_average(scan1, scan2, scan3, weights=(0.15, 0.425, 0.425))
            avg_scans_23, cv_pct = scans_2_3_only(scan1, scan2, scan3)

            # Calculate RMSE vs ground truth
            rmse_standard.append(calculate_rmse(avg_standard, ground_truth))
            rmse_weighted_02.append(calculate_rmse(avg_weighted_02, ground_truth))
            rmse_weighted_01.append(calculate_rmse(avg_weighted_01, ground_truth))
            rmse_weighted_015.append(calculate_rmse(avg_weighted_015, ground_truth))
            rmse_scans_23.append(calculate_rmse(avg_scans_23, ground_truth))
            cv_scans_23.append(cv_pct)

        # Store mean results
        results['standard_rmse'].append(np.mean(rmse_standard))
        results['weighted_02_04_04_rmse'].append(np.mean(rmse_weighted_02))
        results['weighted_01_045_045_rmse'].append(np.mean(rmse_weighted_01))
        results['weighted_015_0425_0425_rmse'].append(np.mean(rmse_weighted_015))
        results['scans_2_3_rmse'].append(np.mean(rmse_scans_23))
        results['scans_2_3_cv'].append(np.mean(cv_scans_23))

    return results


def plot_results(results: Dict):
    """Plot comparison results."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    rise_effects_pct = [r * 100 for r in results['rise_time_effects']]

    # RMSE comparison
    ax1.plot(rise_effects_pct, results['standard_rmse'], 'o-', label='Standard (1/3, 1/3, 1/3)', linewidth=2)
    ax1.plot(rise_effects_pct, results['weighted_02_04_04_rmse'], 's-', label='Weighted (0.2, 0.4, 0.4)', linewidth=2)
    ax1.plot(rise_effects_pct, results['weighted_01_045_045_rmse'], '^-', label='Weighted (0.1, 0.45, 0.45)', linewidth=2)
    ax1.plot(rise_effects_pct, results['weighted_015_0425_0425_rmse'], 'd-', label='Weighted (0.15, 0.425, 0.425)', linewidth=2)
    ax1.plot(rise_effects_pct, results['scans_2_3_rmse'], 'v-', label='Scans 2&3 Only (0, 0.5, 0.5)', linewidth=2)

    ax1.set_xlabel('Rise Time Effect (%)', fontsize=12)
    ax1.set_ylabel('RMSE vs Ground Truth', fontsize=12)
    ax1.set_title('Averaging Method Performance', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # CV% for scans 2&3 method
    ax2.plot(rise_effects_pct, results['scans_2_3_cv'], 'o-', color='green', linewidth=2)
    ax2.set_xlabel('Rise Time Effect (%)', fontsize=12)
    ax2.set_ylabel('Mean CV% (Scans 2&3)', fontsize=12)
    ax2.set_title('Variability in Scans 2&3', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='1% CV target')
    ax2.legend()

    plt.tight_layout()
    plt.savefig('scan_averaging_optimization.png', dpi=150, bbox_inches='tight')
    print("\n✅ Plot saved as 'scan_averaging_optimization.png'")
    plt.show()


def print_results(results: Dict):
    """Print formatted results table."""
    print("\n" + "="*90)
    print("SCAN AVERAGING OPTIMIZATION RESULTS")
    print("="*90)
    print(f"{'Rise Effect':<12} {'Standard':<12} {'W(0.2,0.4,0.4)':<16} {'W(0.1,0.45,0.45)':<18} "
          f"{'W(0.15,0.425)':<16} {'Scans 2&3':<12} {'CV%':<8}")
    print("-"*90)

    for i, rise_effect in enumerate(results['rise_time_effects']):
        print(f"{rise_effect*100:>6.1f}%      "
              f"{results['standard_rmse'][i]:>8.2f}    "
              f"{results['weighted_02_04_04_rmse'][i]:>11.2f}     "
              f"{results['weighted_01_045_045_rmse'][i]:>13.2f}     "
              f"{results['weighted_015_0425_0425_rmse'][i]:>11.2f}     "
              f"{results['scans_2_3_rmse'][i]:>8.2f}      "
              f"{results['scans_2_3_cv'][i]:>5.2f}%")

    print("="*90)
    print("\n📊 INTERPRETATION:")
    print("   • Lower RMSE = Better accuracy vs ground truth")
    print("   • Lower CV% = More consistent between scan 2 and scan 3")
    print("\n💡 RECOMMENDATIONS:")

    # Find best performer for each rise time scenario
    for i, rise_effect in enumerate(results['rise_time_effects']):
        rmse_values = [
            results['standard_rmse'][i],
            results['weighted_02_04_04_rmse'][i],
            results['weighted_01_045_045_rmse'][i],
            results['weighted_015_0425_0425_rmse'][i],
            results['scans_2_3_rmse'][i]
        ]
        best_idx = np.argmin(rmse_values)
        methods = ['Standard', 'Weighted (0.2,0.4,0.4)', 'Weighted (0.1,0.45,0.45)',
                   'Weighted (0.15,0.425,0.425)', 'Scans 2&3 Only']

        improvement = ((results['standard_rmse'][i] - rmse_values[best_idx]) / results['standard_rmse'][i]) * 100
        print(f"   • {rise_effect*100:.0f}% rise effect: Best = {methods[best_idx]} "
              f"({improvement:.1f}% better than standard)")


if __name__ == "__main__":
    print("\n🚀 Testing scan averaging optimization strategies...")
    print("   Scenario: First scan affected by LED rise time, scans 2&3 stable\n")

    # Run tests with different rise time magnitudes
    results = run_comparison_test(
        num_tests=100,  # Monte Carlo simulations
        rise_time_effects=[0.01, 0.03, 0.05, 0.1],  # 1%, 3%, 5%, 10% effects
        noise_level=0.01  # 1% random noise
    )

    # Display results
    print_results(results)

    # Plot results
    plot_results(results)

    print("\n✅ Test complete!\n")
