"""Check NPZ file structure."""

from pathlib import Path

import numpy as np

from settings.settings import ROOT_DIR

calib_dir = Path(ROOT_DIR) / "calibration_data"
npz_files = sorted(
    calib_dir.glob("s_roi_stability_*_spectra.npz"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

if len(npz_files) >= 2:
    for i, npz_file in enumerate(npz_files[:2]):
        print(f"\n{'='*80}")
        print(f"File {i+1}: {npz_file.name}")
        print("=" * 80)
        data = np.load(npz_file)
        print("Keys in NPZ file:")
        for key in data.keys():
            arr = data[key]
            if hasattr(arr, "shape"):
                print(f"  {key}: shape={arr.shape}, dtype={arr.dtype}")
            else:
                print(f"  {key}: {arr}")
        print()
