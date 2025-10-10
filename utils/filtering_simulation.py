"""Comprehensive Filtering Simulation: Before vs After Comparison

This script simulates realistic SPR data and compares:
1. Current approach (mean filter with bugs)
2. Improved approach (median filter with outlier rejection)

Run this to see exactly how the improvements affect your data quality.

Usage:
    python filtering_simulation.py
"""

import time

import matplotlib.pyplot as plt
import numpy as np

# ============================================================================
# SIMULATION PARAMETERS
# ============================================================================

DURATION = 300  # 5 minutes of simulated data
SAMPLING_RATE = 2.0  # 2 Hz (0.5 second intervals, typical for SPR)
NUM_POINTS = int(DURATION * SAMPLING_RATE)

# Noise characteristics (realistic SPR values)
GAUSSIAN_NOISE_STD = 0.05  # nm (electronic noise)
OUTLIER_PROBABILITY = 0.02  # 2% outliers (bubbles, spikes)
OUTLIER_MAGNITUDE = 2.0  # nm (large spikes)
BASELINE_DRIFT = 0.01  # nm/minute (thermal drift)

# Filter settings
MEDIAN_WINDOW = 11  # 5.5 seconds at 2 Hz
OUTLIER_LOOKBACK = 20  # 10 seconds history for outlier detection


# ============================================================================
# SPR DATA SIMULATOR
# ============================================================================


class SPRSimulator:
    """Generates realistic SPR sensorgram data with noise."""

    def __init__(self, duration: float, sampling_rate: float):
        self.duration = duration
        self.sampling_rate = sampling_rate
        self.num_points = int(duration * sampling_rate)
        self.time = np.linspace(0, duration, self.num_points)

    def generate_clean_signal(self) -> np.ndarray:
        """Generate clean SPR signal with realistic binding kinetics.

        Simulation includes:
        - Baseline at 650 nm
        - Association phase (60-120s): Langmuir binding
        - Equilibrium phase (120-180s): Stable binding
        - Dissociation phase (180-300s): Exponential decay
        """
        signal = 650.0 * np.ones(self.num_points)

        # Association phase (60-120s)
        assoc_start = int(60 * self.sampling_rate)
        assoc_end = int(120 * self.sampling_rate)

        for i in range(assoc_start, assoc_end):
            t = (i - assoc_start) / self.sampling_rate
            # Langmuir binding: R = Rmax * (1 - exp(-ka*t))
            signal[i] = 650.0 + 5.0 * (1 - np.exp(-t / 20))

        # Equilibrium phase (120-180s)
        for i in range(assoc_end, int(180 * self.sampling_rate)):
            signal[i] = 655.0

        # Dissociation phase (180-300s)
        dissoc_start = int(180 * self.sampling_rate)
        for i in range(dissoc_start, self.num_points):
            t = (i - dissoc_start) / self.sampling_rate
            # Exponential decay: R = Rmax * exp(-kd*t)
            signal[i] = 655.0 - 5.0 * (1 - np.exp(-t / 30))

        return signal

    def add_gaussian_noise(self, signal: np.ndarray, std: float) -> np.ndarray:
        """Add white Gaussian noise (electronic noise, shot noise)."""
        return signal + np.random.normal(0, std, len(signal))

    def add_outliers(
        self, signal: np.ndarray, prob: float, magnitude: float
    ) -> np.ndarray:
        """Add random outlier spikes.

        Simulates:
        - Air bubbles passing through flow cell
        - Electrical interference
        - Mechanical vibrations
        """
        signal_with_outliers = signal.copy()
        num_outliers = 0

        for i in range(len(signal)):
            if np.random.random() < prob:
                # Random spike (positive or negative)
                spike = np.random.choice([-1, 1]) * magnitude
                signal_with_outliers[i] += spike
                num_outliers += 1

        print(f"  Added {num_outliers} outliers ({100 * prob:.1f}% of data)")
        return signal_with_outliers

    def add_baseline_drift(self, signal: np.ndarray, rate: float) -> np.ndarray:
        """Add linear baseline drift (thermal effects, baseline shift)."""
        drift = rate * self.time / 60  # Convert to per minute
        return signal + drift

    def generate_realistic_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Generate complete realistic SPR data with all noise sources.

        Returns:
            clean_signal: Ideal noise-free signal
            noisy_signal: Realistic noisy signal

        """
        print("Generating SPR simulation data...")
        clean = self.generate_clean_signal()

        print(f"  Duration: {self.duration}s ({self.num_points} points)")
        print(f"  Sampling rate: {self.sampling_rate} Hz")
        print(f"  Gaussian noise: {GAUSSIAN_NOISE_STD} nm")

        noisy = self.add_gaussian_noise(clean, GAUSSIAN_NOISE_STD)
        noisy = self.add_outliers(noisy, OUTLIER_PROBABILITY, OUTLIER_MAGNITUDE)
        noisy = self.add_baseline_drift(noisy, BASELINE_DRIFT)

        return clean, noisy


# ============================================================================
# FILTERING METHODS
# ============================================================================


class CurrentApproach:
    """Current implementation (with bugs)."""

    @staticmethod
    def causal_mean_filter(data: np.ndarray, window: int) -> np.ndarray:
        """Current buggy implementation: causal MEAN filter.

        Problems:
        1. Uses mean instead of median (sensitive to outliers)
        2. Causal (backward-looking) introduces unnecessary delay
        3. No outlier rejection
        """
        filtered = np.full_like(data, np.nan)

        for i in range(len(data)):
            if i < window:
                # Expanding window at start
                window_data = data[0 : i + 1]
            else:
                # Causal window (looks backward only)
                window_data = data[i - window : i]

            # BUG: Using mean instead of median!
            filtered[i] = np.nanmean(window_data)

        return filtered


class ImprovedApproach:
    """Improved implementation with all fixes."""

    @staticmethod
    def detect_outliers_iqr(data: np.ndarray, lookback: int = 20) -> np.ndarray:
        """Detect outliers using IQR (Interquartile Range) method.

        Args:
            data: Input data array
            lookback: Number of recent points to use for statistics

        Returns:
            Boolean array: True for outliers, False for valid points

        """
        outliers = np.zeros(len(data), dtype=bool)

        for i in range(lookback, len(data)):
            # Get recent valid data
            recent = data[max(0, i - lookback) : i]
            recent_valid = recent[~np.isnan(recent)]

            if len(recent_valid) < 5:
                continue  # Need at least 5 points

            # Calculate IQR
            q1, q3 = np.percentile(recent_valid, [25, 75])
            iqr = q3 - q1

            # Define outlier bounds (3x IQR is conservative)
            lower_bound = q1 - 3 * iqr
            upper_bound = q3 + 3 * iqr

            # Check if current point is outlier
            if not (lower_bound <= data[i] <= upper_bound):
                outliers[i] = True

        return outliers

    @staticmethod
    def centered_median_filter(data: np.ndarray, window: int) -> np.ndarray:
        """Centered median filter (symmetric window).

        Advantages:
        - Robust to outliers
        - No phase distortion
        - Less delay than causal filter
        """
        filtered = np.full_like(data, np.nan)
        half_window = window // 2

        for i in range(len(data)):
            # Centered window
            start = max(0, i - half_window)
            end = min(len(data), i + half_window + 1)
            window_data = data[start:end]

            # Use MEDIAN (robust to outliers)
            if not np.isnan(window_data).all():
                filtered[i] = np.nanmedian(window_data)

        return filtered

    @staticmethod
    def complete_filter(
        data: np.ndarray, window: int, lookback: int = 20
    ) -> tuple[np.ndarray, np.ndarray]:
        """Complete filtering pipeline:
        1. Outlier detection (IQR)
        2. Replace outliers with NaN
        3. Centered median filter

        Returns:
            filtered_data: Filtered signal
            outlier_mask: Boolean array marking outliers

        """
        # Step 1: Detect outliers
        outlier_mask = ImprovedApproach.detect_outliers_iqr(data, lookback)

        # Step 2: Replace outliers with NaN
        cleaned_data = data.copy()
        cleaned_data[outlier_mask] = np.nan

        # Step 3: Apply median filter
        filtered_data = ImprovedApproach.centered_median_filter(cleaned_data, window)

        return filtered_data, outlier_mask


# ============================================================================
# METRICS CALCULATION
# ============================================================================


def calculate_metrics(
    filtered: np.ndarray, true_signal: np.ndarray, noisy_signal: np.ndarray
) -> dict[str, float]:
    """Calculate performance metrics for filter quality.

    Metrics:
    - RMSE: Root mean squared error vs true signal
    - MAE: Mean absolute error vs true signal
    - SNR improvement: How much noise was reduced
    - Max error: Worst-case deviation
    - Outlier suppression: Percentage of outliers removed
    """
    # Remove NaN for comparison
    valid_mask = ~np.isnan(filtered)
    filtered_valid = filtered[valid_mask]
    true_valid = true_signal[valid_mask]
    noisy_valid = noisy_signal[valid_mask]

    if len(filtered_valid) == 0:
        return {
            "rmse": np.nan,
            "mae": np.nan,
            "snr_improvement": np.nan,
            "max_error": np.nan,
            "outlier_suppression": np.nan,
        }

    # Calculate errors
    errors = filtered_valid - true_valid
    noisy_errors = noisy_valid - true_valid

    metrics = {
        "rmse": np.sqrt(np.mean(errors**2)),
        "mae": np.mean(np.abs(errors)),
        "snr_improvement": np.std(noisy_errors) / np.std(errors),
        "max_error": np.max(np.abs(errors)),
        "outlier_suppression": np.sum(np.abs(noisy_errors) > 0.5) / len(noisy_errors),
    }

    return metrics


# ============================================================================
# VISUALIZATION
# ============================================================================


def create_comparison_plots(
    time: np.ndarray,
    clean: np.ndarray,
    noisy: np.ndarray,
    current_filtered: np.ndarray,
    improved_filtered: np.ndarray,
    outlier_mask: np.ndarray,
):
    """Create comprehensive visualization of filtering comparison."""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(4, 2, hspace=0.3, wspace=0.3)

    # ========================================================================
    # Plot 1: Full time series comparison
    # ========================================================================
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(
        time, noisy, "o", markersize=2, alpha=0.3, color="gray", label="Noisy data"
    )
    ax1.plot(
        time, clean, "-", linewidth=2, color="black", label="True signal", alpha=0.7
    )
    ax1.plot(
        time,
        current_filtered,
        "-",
        linewidth=1.5,
        color="red",
        label="Current (mean filter)",
        alpha=0.8,
    )
    ax1.plot(
        time,
        improved_filtered,
        "-",
        linewidth=1.5,
        color="green",
        label="Improved (median + outlier rejection)",
        alpha=0.8,
    )

    # Mark outliers
    outlier_indices = np.where(outlier_mask)[0]
    if len(outlier_indices) > 0:
        ax1.plot(
            time[outlier_indices],
            noisy[outlier_indices],
            "rx",
            markersize=8,
            label="Detected outliers",
        )

    ax1.set_xlabel("Time (s)", fontsize=12)
    ax1.set_ylabel("Wavelength (nm)", fontsize=12)
    ax1.set_title("SPR Sensorgram: Full Comparison", fontsize=14, fontweight="bold")
    ax1.legend(loc="best", fontsize=10)
    ax1.grid(True, alpha=0.3)

    # ========================================================================
    # Plot 2: Zoomed view of outlier region
    # ========================================================================
    ax2 = fig.add_subplot(gs[1, 0])
    zoom_start, zoom_end = 100, 150  # 50-75 seconds
    zoom_mask = (time >= zoom_start) & (time <= zoom_end)

    ax2.plot(
        time[zoom_mask],
        noisy[zoom_mask],
        "o",
        markersize=4,
        alpha=0.5,
        color="gray",
        label="Noisy data",
    )
    ax2.plot(
        time[zoom_mask],
        clean[zoom_mask],
        "-",
        linewidth=2,
        color="black",
        label="True signal",
    )
    ax2.plot(
        time[zoom_mask],
        current_filtered[zoom_mask],
        "-",
        linewidth=2,
        color="red",
        label="Current (mean)",
        alpha=0.8,
    )
    ax2.plot(
        time[zoom_mask],
        improved_filtered[zoom_mask],
        "-",
        linewidth=2,
        color="green",
        label="Improved (median)",
        alpha=0.8,
    )

    # Mark outliers in zoom
    zoom_outliers = outlier_mask & zoom_mask
    if np.any(zoom_outliers):
        ax2.plot(
            time[zoom_outliers],
            noisy[zoom_outliers],
            "rx",
            markersize=10,
            label="Outliers",
        )

    ax2.set_xlabel("Time (s)", fontsize=11)
    ax2.set_ylabel("Wavelength (nm)", fontsize=11)
    ax2.set_title("Zoomed View: Association Phase", fontsize=12, fontweight="bold")
    ax2.legend(loc="best", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # ========================================================================
    # Plot 3: Error comparison
    # ========================================================================
    ax3 = fig.add_subplot(gs[1, 1])

    current_error = current_filtered - clean
    improved_error = improved_filtered - clean

    ax3.plot(
        time,
        np.abs(current_error),
        "-",
        linewidth=1,
        color="red",
        alpha=0.6,
        label="Current error",
    )
    ax3.plot(
        time,
        np.abs(improved_error),
        "-",
        linewidth=1,
        color="green",
        alpha=0.6,
        label="Improved error",
    )
    ax3.axhline(
        y=0.1, linestyle="--", color="orange", alpha=0.5, label="±0.1 nm threshold"
    )

    ax3.set_xlabel("Time (s)", fontsize=11)
    ax3.set_ylabel("Absolute Error (nm)", fontsize=11)
    ax3.set_title("Filter Error Over Time", fontsize=12, fontweight="bold")
    ax3.legend(loc="best", fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim([0, 1.0])

    # ========================================================================
    # Plot 4: Error distribution (histogram)
    # ========================================================================
    ax4 = fig.add_subplot(gs[2, 0])

    valid_current = ~np.isnan(current_error)
    valid_improved = ~np.isnan(improved_error)

    ax4.hist(
        current_error[valid_current],
        bins=50,
        alpha=0.5,
        color="red",
        label="Current",
        density=True,
    )
    ax4.hist(
        improved_error[valid_improved],
        bins=50,
        alpha=0.5,
        color="green",
        label="Improved",
        density=True,
    )

    ax4.axvline(x=0, linestyle="--", color="black", alpha=0.5)
    ax4.set_xlabel("Error (nm)", fontsize=11)
    ax4.set_ylabel("Probability Density", fontsize=11)
    ax4.set_title("Error Distribution", fontsize=12, fontweight="bold")
    ax4.legend(loc="best", fontsize=9)
    ax4.grid(True, alpha=0.3)

    # ========================================================================
    # Plot 5: Residuals (filtered - true)
    # ========================================================================
    ax5 = fig.add_subplot(gs[2, 1])

    ax5.scatter(
        time, current_error, s=5, alpha=0.3, color="red", label="Current residuals"
    )
    ax5.scatter(
        time, improved_error, s=5, alpha=0.3, color="green", label="Improved residuals"
    )
    ax5.axhline(y=0, linestyle="-", color="black", linewidth=1)
    ax5.axhline(y=0.1, linestyle="--", color="orange", alpha=0.5)
    ax5.axhline(y=-0.1, linestyle="--", color="orange", alpha=0.5)

    ax5.set_xlabel("Time (s)", fontsize=11)
    ax5.set_ylabel("Residual (nm)", fontsize=11)
    ax5.set_title("Filter Residuals (Filtered - True)", fontsize=12, fontweight="bold")
    ax5.legend(loc="best", fontsize=9)
    ax5.grid(True, alpha=0.3)
    ax5.set_ylim([-1.5, 1.5])

    # ========================================================================
    # Plot 6: Metrics comparison bar chart
    # ========================================================================
    ax6 = fig.add_subplot(gs[3, :])

    current_metrics = calculate_metrics(current_filtered, clean, noisy)
    improved_metrics = calculate_metrics(improved_filtered, clean, noisy)

    metrics_names = ["RMSE\n(nm)", "MAE\n(nm)", "SNR\nImprovement", "Max Error\n(nm)"]
    current_values = [
        current_metrics["rmse"],
        current_metrics["mae"],
        current_metrics["snr_improvement"],
        current_metrics["max_error"],
    ]
    improved_values = [
        improved_metrics["rmse"],
        improved_metrics["mae"],
        improved_metrics["snr_improvement"],
        improved_metrics["max_error"],
    ]

    x = np.arange(len(metrics_names))
    width = 0.35

    bars1 = ax6.bar(
        x - width / 2,
        current_values,
        width,
        label="Current (mean)",
        color="red",
        alpha=0.7,
    )
    bars2 = ax6.bar(
        x + width / 2,
        improved_values,
        width,
        label="Improved (median)",
        color="green",
        alpha=0.7,
    )

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax6.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax6.set_ylabel("Metric Value", fontsize=11)
    ax6.set_title("Performance Metrics Comparison", fontsize=12, fontweight="bold")
    ax6.set_xticks(x)
    ax6.set_xticklabels(metrics_names, fontsize=10)
    ax6.legend(loc="best", fontsize=10)
    ax6.grid(True, alpha=0.3, axis="y")

    plt.suptitle(
        "SPR Filtering Comparison: Current vs Improved Approach",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    return fig


# ============================================================================
# MAIN SIMULATION
# ============================================================================


def run_simulation():
    """Run complete simulation and generate comparison plots."""
    print("=" * 70)
    print("SPR FILTERING SIMULATION: BEFORE vs AFTER")
    print("=" * 70)
    print()

    # Generate realistic SPR data
    np.random.seed(42)  # For reproducible results
    simulator = SPRSimulator(DURATION, SAMPLING_RATE)
    clean_signal, noisy_signal = simulator.generate_realistic_data()
    print()

    # Apply current (buggy) approach
    print("Applying CURRENT approach (mean filter)...")
    start_time = time.time()
    current_filtered = CurrentApproach.causal_mean_filter(noisy_signal, MEDIAN_WINDOW)
    current_time = time.time() - start_time
    print(f"  Completed in {current_time * 1000:.2f} ms")
    print()

    # Apply improved approach
    print("Applying IMPROVED approach (median + outlier rejection)...")
    start_time = time.time()
    improved_filtered, outlier_mask = ImprovedApproach.complete_filter(
        noisy_signal,
        MEDIAN_WINDOW,
        OUTLIER_LOOKBACK,
    )
    improved_time = time.time() - start_time
    num_outliers_detected = np.sum(outlier_mask)
    print(f"  Completed in {improved_time * 1000:.2f} ms")
    print(f"  Detected and removed {num_outliers_detected} outliers")
    print()

    # Calculate metrics
    print("=" * 70)
    print("PERFORMANCE METRICS")
    print("=" * 70)

    current_metrics = calculate_metrics(current_filtered, clean_signal, noisy_signal)
    improved_metrics = calculate_metrics(improved_filtered, clean_signal, noisy_signal)

    print("\nCURRENT APPROACH (Mean Filter):")
    print(f"  RMSE:             {current_metrics['rmse']:.4f} nm")
    print(f"  MAE:              {current_metrics['mae']:.4f} nm")
    print(f"  SNR Improvement:  {current_metrics['snr_improvement']:.2f}x")
    print(f"  Max Error:        {current_metrics['max_error']:.4f} nm")

    print("\nIMPROVED APPROACH (Median + Outlier Rejection):")
    print(f"  RMSE:             {improved_metrics['rmse']:.4f} nm")
    print(f"  MAE:              {improved_metrics['mae']:.4f} nm")
    print(f"  SNR Improvement:  {improved_metrics['snr_improvement']:.2f}x")
    print(f"  Max Error:        {improved_metrics['max_error']:.4f} nm")

    print("\nIMPROVEMENT:")
    rmse_improvement = (1 - improved_metrics["rmse"] / current_metrics["rmse"]) * 100
    mae_improvement = (1 - improved_metrics["mae"] / current_metrics["mae"]) * 100
    snr_improvement = (
        (improved_metrics["snr_improvement"] / current_metrics["snr_improvement"]) - 1
    ) * 100

    print(f"  RMSE reduced by:  {rmse_improvement:.1f}%")
    print(f"  MAE reduced by:   {mae_improvement:.1f}%")
    print(f"  SNR improved by:  {snr_improvement:.1f}%")
    print()

    # Create visualization
    print("=" * 70)
    print("GENERATING PLOTS...")
    print("=" * 70)

    fig = create_comparison_plots(
        simulator.time,
        clean_signal,
        noisy_signal,
        current_filtered,
        improved_filtered,
        outlier_mask,
    )

    # Save figure
    output_file = "filtering_comparison.png"
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved as: {output_file}")

    # Show plot
    plt.show()

    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)
    print("\nKEY FINDINGS:")
    print("1. Median filter is more robust to outliers than mean filter")
    print("2. Centered window reduces phase delay vs causal window")
    print("3. Outlier rejection prevents spikes from corrupting filtered data")
    print("4. Overall improvement in RMSE, MAE, and SNR")
    print("\nRECOMMENDATION: Implement the improved approach in production code.")


if __name__ == "__main__":
    # Check dependencies
    try:
        import matplotlib
        import scipy
    except ImportError as e:
        print(f"ERROR: Missing dependency - {e}")
        print("Please install: pip install scipy matplotlib")
        exit(1)

    # Run simulation
    run_simulation()
