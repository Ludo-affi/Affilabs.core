"""Emergency baseline data recovery script.

Run this IMMEDIATELY after the failed save to recover data from memory.
The data is still in the recorder object if you haven't closed the app yet!

Usage:
    python recover_baseline_data.py
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

def recover_data_from_ui():
    """Attempt to recover data from the running application."""
    print("\n" + "="*80)
    print("🚨 BASELINE DATA RECOVERY TOOL")
    print("="*80)
    print("\nThis script will attempt to recover your baseline data from memory.")
    print("⚠️  DO NOT close the application yet!\n")

    # Try to access the application instance
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()

        if app is None:
            print("❌ ERROR: No Qt application running!")
            print("   The data might be lost if you already closed the app.")
            return False

        # Find the main window
        main_window = None
        for widget in app.topLevelWidgets():
            if hasattr(widget, '_baseline_recorder'):
                main_window = widget
                break

        if main_window is None:
            print("❌ ERROR: Could not find main window with recorder!")
            print("   Looking for app attribute...")

            # Try alternative path through app
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'app'):
                    # Found application instance
                    print(f"✅ Found application instance")
                    main_window = widget
                    break

        if main_window is None:
            print("❌ ERROR: Could not access recorder object!")
            return False

        # Get the recorder
        recorder = getattr(main_window, '_baseline_recorder', None)

        if recorder is None:
            print("❌ ERROR: Recorder not initialized!")
            return False

        # Check if data exists
        total_spectra = sum(len(recorder.transmission_data[ch]) for ch in ['a', 'b', 'c', 'd'])

        if total_spectra == 0:
            print("❌ ERROR: No data in recorder!")
            return False

        print(f"\n✅ FOUND DATA IN MEMORY!")
        print(f"   Total spectra collected: {total_spectra}")
        for ch in ['a', 'b', 'c', 'd']:
            count = len(recorder.transmission_data[ch])
            print(f"   Channel {ch}: {count} spectra")

        # Save the data
        print("\n📁 Saving recovered data...")
        output_dir = Path("baseline_data_recovered")
        output_dir.mkdir(exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save transmission spectra
        for ch in ['a', 'b', 'c', 'd']:
            if not recorder.transmission_data[ch]:
                continue

            df = pd.DataFrame(
                np.array(recorder.transmission_data[ch]).T,
                index=recorder.wavelength_axis,
                columns=[f"t_{i:04d}" for i in range(len(recorder.transmission_data[ch]))]
            )
            df.index.name = 'wavelength_nm'

            filepath = output_dir / f"baseline_transmission_ch{ch}_{timestamp_str}.csv"
            df.to_csv(filepath)
            print(f"   ✅ Channel {ch}: {filepath.name}")

        # Save wavelength traces with padding
        max_length = max(
            len(recorder.wavelength_data['a']),
            len(recorder.wavelength_data['b']),
            len(recorder.wavelength_data['c']),
            len(recorder.wavelength_data['d'])
        )

        wavelength_dict = {}
        for ch in ['a', 'b', 'c', 'd']:
            wl_data = recorder.wavelength_data[ch].copy()
            ts_data = recorder.timestamps[ch].copy()

            # Pad with NaN if needed
            if len(wl_data) < max_length:
                wl_data = wl_data + [np.nan] * (max_length - len(wl_data))
                ts_data = ts_data + [np.nan] * (max_length - len(ts_data))

            wavelength_dict[f'channel_{ch}'] = wl_data
            wavelength_dict[f'timestamp_{ch}'] = ts_data

        wavelength_df = pd.DataFrame(wavelength_dict)
        wavelength_filepath = output_dir / f"baseline_wavelengths_{timestamp_str}.csv"
        wavelength_df.to_csv(wavelength_filepath, index=False)
        print(f"   ✅ Wavelength traces: {wavelength_filepath.name}")

        # Save metadata
        metadata_df = pd.DataFrame([recorder.metadata])
        metadata_filepath = output_dir / f"baseline_metadata_{timestamp_str}.csv"
        metadata_df.to_csv(metadata_filepath, index=False)
        print(f"   ✅ Metadata: {metadata_filepath.name}")

        print(f"\n✅ DATA RECOVERED SUCCESSFULLY!")
        print(f"   Output directory: {output_dir.absolute()}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR during recovery: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = recover_data_from_ui()

    if not success:
        print("\n" + "="*80)
        print("⚠️  RECOVERY FAILED")
        print("="*80)
        print("\nIf the application is still running:")
        print("1. DO NOT close it!")
        print("2. In the Python console, run:")
        print("   >>> import recover_baseline_data")
        print("   >>> recover_baseline_data.recover_data_from_ui()")
        print("\nIf you already closed the app, the data is unfortunately lost.")
        print("The fix has been applied for future recordings.")
        sys.exit(1)
    else:
        print("\n✅ You can now safely close the application.")
        sys.exit(0)
