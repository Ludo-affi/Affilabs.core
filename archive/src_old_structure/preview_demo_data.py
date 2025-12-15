"""Preview Demo Data - Generate and visualize demo SPR curves

Quick preview of the demo data before loading into UI.

Requirements:
    matplotlib (optional visualization library)
    Install with: pip install matplotlib

Usage:
    python preview_demo_data.py

Author: AI Assistant
Date: November 24, 2025
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Check for matplotlib
try:
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("\n" + "=" * 60)
    print("⚠️  WARNING: matplotlib not installed")
    print("=" * 60)
    print("\nThis script requires matplotlib for visualization.")
    print("\nTo install matplotlib, run:")
    print("  pip install matplotlib")
    print("\nAlternatively, to load demo data into the UI without preview:")
    print("  1. Run: python main_simplified.py")
    print("  2. Press: Ctrl+Shift+D (loads demo data)")
    print("  OR run: python load_demo_ui.py")
    print("=" * 60 + "\n")
    sys.exit(1)

from utils.demo_data_generator import generate_demo_cycle_data


def preview_demo_data():
    """Generate and display demo data with matplotlib."""
    print("Generating demo SPR kinetics data...")

    # Generate 3 cycles with progressive concentrations
    time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
        num_cycles=3,
        cycle_duration=600,
        sampling_rate=2.0,
        responses=[20, 40, 65],
        seed=42,
    )

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Plot 1: All channels
    colors = {"a": "#FF3B30", "b": "#34C759", "c": "#007AFF", "d": "#FF9500"}
    labels = {"a": "Channel A", "b": "Channel B", "c": "Channel C", "d": "Channel D"}

    for ch, data in channel_data.items():
        ax1.plot(
            time_array,
            data,
            label=labels[ch],
            color=colors[ch],
            linewidth=2,
            alpha=0.8,
        )

    # Add cycle boundaries
    for idx, (start, end) in enumerate(cycle_boundaries):
        ax1.axvline(start, color="gray", linestyle="--", alpha=0.3, linewidth=1)
        ax1.axvline(end, color="gray", linestyle="--", alpha=0.3, linewidth=1)

        # Label cycle
        mid_point = (start + end) / 2
        ax1.text(
            mid_point,
            ax1.get_ylim()[1] * 0.95,
            f"Cycle {idx + 1}",
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    ax1.set_ylabel("Response (RU)", fontsize=12, fontweight="bold")
    ax1.set_title("Demo SPR Kinetics - Full Timeline", fontsize=14, fontweight="bold")
    ax1.legend(loc="upper left", framealpha=0.9)
    ax1.grid(True, alpha=0.3, linestyle=":")
    ax1.set_ylim(-5, max([max(d) for d in channel_data.values()]) + 10)

    # Plot 2: Zoom into Cycle 2 (middle cycle)
    cycle_2_start, cycle_2_end = cycle_boundaries[1]
    mask = (time_array >= cycle_2_start) & (time_array <= cycle_2_end)
    time_zoom = time_array[mask] - cycle_2_start  # Reset time to 0

    for ch, data in channel_data.items():
        data_zoom = data[mask]
        ax2.plot(
            time_zoom,
            data_zoom,
            label=labels[ch],
            color=colors[ch],
            linewidth=2,
            alpha=0.8,
        )

    # Mark phases
    ax2.axvspan(0, 60, alpha=0.1, color="blue", label="Baseline")
    ax2.axvspan(60, 300, alpha=0.1, color="green", label="Association")
    ax2.axvspan(300, 600, alpha=0.1, color="red", label="Dissociation")

    ax2.set_xlabel("Time (seconds)", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Response (RU)", fontsize=12, fontweight="bold")
    ax2.set_title("Cycle 2 Detail - Binding Kinetics", fontsize=14, fontweight="bold")
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, alpha=0.3, linestyle=":")

    plt.tight_layout()

    # Print statistics
    print("\n" + "=" * 60)
    print("DEMO DATA STATISTICS")
    print("=" * 60)
    print(
        f"Total duration:    {time_array[-1]:.1f} seconds ({time_array[-1]/60:.1f} minutes)",
    )
    print(f"Data points:       {len(time_array)}")
    print(f"Sampling rate:     {len(time_array)/time_array[-1]:.2f} Hz")
    print(f"Number of cycles:  {len(cycle_boundaries)}")
    print("\nChannel Responses (Max RU):")
    for ch, data in channel_data.items():
        max_response = max(data)
        print(f"  Channel {ch.upper()}: {max_response:.2f} RU")

    print("\nCycle Boundaries:")
    for idx, (start, end) in enumerate(cycle_boundaries):
        print(
            f"  Cycle {idx + 1}: {start:.0f}s - {end:.0f}s (duration: {end-start:.0f}s)",
        )

    print("\n✅ Data generated successfully!")
    print("📸 Close the plot window to continue...")
    print("\nTo load this into the UI:")
    print("  1. Run: python main_simplified.py")
    print("  2. Press: Ctrl+Shift+D")
    print("  OR run: python load_demo_ui.py")
    print("=" * 60 + "\n")

    plt.show()


if __name__ == "__main__":
    preview_demo_data()
