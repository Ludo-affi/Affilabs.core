"""Sensorgram with Minimal Smoothing - Phase Photonics

Test with reduced/no SG smoothing since data is already smooth.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import savgol_filter
from scipy.fftpack import dst, idct
from scipy.stats import linregress
import matplotlib.pyplot as plt

# ============================================================================
# PARAMETER VARIANTS TO TEST
# ============================================================================

CONFIGS = {
    "No SG Smoothing": {
        "sg_window": None,       # Disable SG filtering
        "fourier_alpha": 4500,
        "fourier_window": 85,
        "wavelength_range": (570.0, 720.0),
    },
    "Minimal SG (5 pixels)": {
        "sg_window": 5,          # Very light smoothing
        "sg_polyorder": 3,
        "fourier_alpha": 4500,
        "fourier_window": 85,
        "wavelength_range": (570.0, 720.0),
    },
    "Optimized SG (11 pixels)": {
        "sg_window": 11,         # Current optimized
        "sg_polyorder": 3,
        "fourier_alpha": 4500,
        "fourier_window": 85,
        "wavelength_range": (570.0, 720.0),
    },
}

# ============================================================================
# FOURIER DIP FINDING
# ============================================================================

def find_dip_fourier(transmission, wavelengths, config):
    """Find resonance dip using Fourier method."""
    try:
        # Filter wavelength range
        wl_min, wl_max = config["wavelength_range"]
        valid_mask = (wavelengths >= wl_min) & (wavelengths <= wl_max)
        wl = wavelengths[valid_mask]
        trans = transmission[valid_mask]
        
        if len(wl) < 50:
            return np.nan
            
        # Step 1: Optional Savitzky-Golay smoothing
        sg_window = config.get("sg_window")
        if sg_window is not None and len(trans) >= sg_window:
            trans_smooth = savgol_filter(trans, sg_window, config["sg_polyorder"], mode='nearest')
        else:
            trans_smooth = trans
            
        # Step 2: Calculate Fourier weights
        alpha = config["fourier_alpha"]
        N = len(trans_smooth)
        fourier_weights = 1.0 / (1.0 + alpha * (np.arange(1, N - 1) / N) ** 4)
        
        # Step 3: Linear detrending
        fourier_coeff = np.zeros(N)
        fourier_coeff[0] = 2 * (trans_smooth[-1] - trans_smooth[0])
        
        # Step 4: DST with Fourier weights
        linear_trend = np.linspace(trans_smooth[0], trans_smooth[-1], N)
        fourier_coeff[1:-1] = fourier_weights * dst(trans_smooth[1:-1] - linear_trend[1:-1], 1)
        
        # Step 5: IDCT to get derivative
        derivative = idct(fourier_coeff, 1)
        
        # Step 6: Find zero-crossing
        zero_idx = derivative.searchsorted(0)
        
        # Step 7: Linear regression refinement
        window = config["fourier_window"]
        start = max(zero_idx - window, 0)
        end = min(zero_idx + window, N - 1)
        
        if end - start < 10:
            return np.nan
            
        line = linregress(wl[start:end], derivative[start:end])
        resonance_wl = -line.intercept / line.slope
        
        # Validate result
        if wl_min <= resonance_wl <= wl_max:
            return resonance_wl
        else:
            return np.nan
            
    except Exception as e:
        return np.nan


# ============================================================================
# PROCESS BASELINE DATA WITH ALL CONFIGS
# ============================================================================

DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")

print("=" * 80)
print("PHASE PHOTONICS SMOOTHING COMPARISON")
print("=" * 80)

# Load data once
channel = "Channel_D"  # Best channel
df = pd.read_excel(DATA_FILE, sheet_name=channel)
wavelengths = df['wavelength_nm'].values
num_timepoints = len(df.columns) - 1

print(f"\nTesting on {channel} (best baseline)")
print(f"Wavelengths: {len(wavelengths)} points")
print(f"Timepoints: {num_timepoints}")

results_all = {}

for config_name, config in CONFIGS.items():
    print(f"\n{'-' * 80}")
    print(f"Testing: {config_name}")
    print(f"{'-' * 80}")
    
    # Process all timepoints
    dips_nm = []
    
    for i in range(num_timepoints):
        col_name = f't_{i:04d}'
        if col_name not in df.columns:
            continue
            
        transmission = df[col_name].values
        dip = find_dip_fourier(transmission, wavelengths, config)
        
        if not np.isnan(dip):
            dips_nm.append(dip)
    
    if len(dips_nm) > 0:
        dips_nm = np.array(dips_nm)
        time_seconds = np.arange(len(dips_nm))
        
        # Convert to RU
        baseline_nm = dips_nm[0]
        shifts_nm = dips_nm - baseline_nm
        shifts_RU = shifts_nm * 355
        
        # Statistics
        rms_RU = np.std(shifts_RU)
        p2p_RU = np.max(shifts_RU) - np.min(shifts_RU)
        
        sg_desc = config.get("sg_window")
        if sg_desc is None:
            sg_desc = "None"
        else:
            sg_desc = f"{sg_desc} pixels"
            
        print(f"  SG Window: {sg_desc}")
        print(f"  RMS noise: {rms_RU:.2f} RU")
        print(f"  Peak-to-peak: {p2p_RU:.2f} RU")
        
        results_all[config_name] = {
            "time": time_seconds,
            "shifts_RU": shifts_RU,
            "rms": rms_RU,
            "p2p": p2p_RU,
            "config": config,
        }

# ============================================================================
# PLOT COMPARISON
# ============================================================================

fig, axes = plt.subplots(len(CONFIGS), 1, figsize=(12, 10), sharex=True)
fig.suptitle(f'Phase Photonics {channel} - Smoothing Comparison\n(1 Hz, 300s baseline)', 
             fontsize=14, fontweight='bold')

for idx, (config_name, result) in enumerate(results_all.items()):
    ax = axes[idx]
    
    time = result["time"]
    shifts = result["shifts_RU"]
    rms = result["rms"]
    p2p = result["p2p"]
    
    ax.plot(time, shifts, '-', alpha=0.7, linewidth=1)
    ax.axhline(0, color='black', linestyle='--', linewidth=0.5, alpha=0.3)
    ax.set_ylabel('Shift (RU)', fontsize=10)
    ax.set_title(f'{config_name} - RMS: {rms:.2f} RU, P-P: {p2p:.2f} RU', fontsize=11)
    ax.grid(True, alpha=0.3)

axes[-1].set_xlabel('Time (s)', fontsize=10)
plt.tight_layout()
plt.savefig('phase_photonics_smoothing_comparison.png', dpi=150, bbox_inches='tight')

print(f"\n{'=' * 80}")
print("SUMMARY - SMOOTHING COMPARISON")
print(f"{'=' * 80}")
print(f"{'Configuration':<30} {'RMS (RU)':<15} {'Peak-to-Peak (RU)':<20}")
print(f"{'-' * 80}")

for config_name, result in results_all.items():
    print(f"{config_name:<30} {result['rms']:>10.2f}      {result['p2p']:>12.2f}")

print(f"\n{'=' * 80}")
print(f"Plot saved: phase_photonics_smoothing_comparison.png")
print(f"{'=' * 80}")

# Find best configuration
best_config = min(results_all.items(), key=lambda x: x[1]['rms'])
print(f"\nBest RMS: {best_config[0]} ({best_config[1]['rms']:.2f} RU)")
