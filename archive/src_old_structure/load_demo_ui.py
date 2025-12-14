"""Quick Demo Data Loader for Promotional Screenshots

Run this script to launch the UI with pre-loaded demo data.
Perfect for taking promotional screenshots with realistic SPR binding curves.

Usage:
    python load_demo_ui.py

Author: AI Assistant
Date: November 24, 2025
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from affilabs_core_ui import AffilabsMainWindow
from utils.demo_data_generator import generate_demo_cycle_data


def main():
    """Launch UI with demo data pre-loaded."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Create main window
    window = AffilabsMainWindow()

    # Generate demo data
    print("Generating demo SPR kinetics data...")
    time_array, channel_data, cycle_boundaries = generate_demo_cycle_data(
        num_cycles=3,
        cycle_duration=600,
        sampling_rate=2.0,
        responses=[20, 40, 65],  # Progressive concentration series
        seed=42,
    )

    # Load data into window buffers
    print("Loading data into UI...")
    window.time_buffer = list(time_array)
    window.wavelength_buffer_a = list(channel_data['a'])
    window.wavelength_buffer_b = list(channel_data['b'])
    window.wavelength_buffer_c = list(channel_data['c'])
    window.wavelength_buffer_d = list(channel_data['d'])

    # Update plots
    if hasattr(window, '_update_plots'):
        window._update_plots()

    print(f"✅ Demo data loaded successfully!")
    print(f"   - {len(time_array)} data points")
    print(f"   - {len(cycle_boundaries)} cycles")
    print(f"   - Duration: {time_array[-1]:.0f} seconds")
    print("\n📸 Ready for promotional screenshots!")
    print("   Tip: Use Ctrl+Shift+D while app is running to reload demo data")

    # Show window
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
