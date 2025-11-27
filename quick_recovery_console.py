"""Quick recovery - paste this into your Python console in the running app.

If the app is still running, you can recover the data!
"""

# Paste this into the Python console:
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# Get the recorder from the main window
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
main_window = [w for w in app.topLevelWidgets() if hasattr(w, '_baseline_recorder')][0]
recorder = main_window._baseline_recorder

# Check data
total = sum(len(recorder.transmission_data[ch]) for ch in ['a', 'b', 'c', 'd'])
print(f"Found {total} spectra in memory!")

# Save it
output_dir = Path("baseline_data_recovered")
output_dir.mkdir(exist_ok=True)
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

# Save each channel
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
    print(f"Saved channel {ch}: {filepath.name}")

# Save wavelength traces with padding
max_length = max(len(recorder.wavelength_data[ch]) for ch in ['a', 'b', 'c', 'd'])
wavelength_dict = {}
for ch in ['a', 'b', 'c', 'd']:
    wl_data = recorder.wavelength_data[ch].copy()
    ts_data = recorder.timestamps[ch].copy()
    if len(wl_data) < max_length:
        wl_data = wl_data + [np.nan] * (max_length - len(wl_data))
        ts_data = ts_data + [np.nan] * (max_length - len(ts_data))
    wavelength_dict[f'channel_{ch}'] = wl_data
    wavelength_dict[f'timestamp_{ch}'] = ts_data

wavelength_df = pd.DataFrame(wavelength_dict)
wavelength_filepath = output_dir / f"baseline_wavelengths_{timestamp_str}.csv"
wavelength_df.to_csv(wavelength_filepath, index=False)
print(f"Saved wavelengths: {wavelength_filepath.name}")

# Save metadata
metadata_df = pd.DataFrame([recorder.metadata])
metadata_filepath = output_dir / f"baseline_metadata_{timestamp_str}.csv"
metadata_df.to_csv(metadata_filepath, index=False)
print(f"Saved metadata: {metadata_filepath.name}")

print(f"\n✅ DATA RECOVERED to: {output_dir.absolute()}")
