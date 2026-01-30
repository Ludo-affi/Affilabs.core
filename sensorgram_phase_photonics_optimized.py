"""Sensorgram with Phase Photonics Optimized Parameters

Apply detector-specific Fourier parameters to baseline data and generate sensorgram.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import savgol_filter
from scipy.fftpack import dst, idct
from scipy.stats import linregress
import matplotlib.pyplot as plt

# ============================================================================
# PHASE PHOTONICS OPTIMIZED PARAMETERS
# ============================================================================

PHASE_PHOTONICS_CONFIG = {
    "sg_window": 11,         # Optimized for 1848 pixels (0.94 nm physical window)
    "sg_polyorder": 3,
    "fourier_alpha": 4500,   # Scaled for lower pixel count
    "fourier_window": 85,    # Optimized for 1848 pixels (7.2 nm physical window)
    "wavelength_range": (570.0, 720.0),
}

# ============================================================================
# FOURIER DIP FINDING
# ============================================================================

def find_dip_fourier(transmission, wavelengths, config):
    """Find resonance dip using Phase Photonics optimized Fourier method."""
    try:
        # Filter wavelength range
        wl_min, wl_max = config["wavelength_range"]
        valid_mask = (wavelengths >= wl_min) & (wavelengths <= wl_max)
        wl = wavelengths[valid_mask]
        trans = transmission[valid_mask]
        
        if len(wl) < 50:
            return np.nan
            
        # Step 1: Savitzky-Golay smoothing (Phase Photonics optimized)
        sg_window = config["sg_window"]
        if len(trans) >= sg_window:
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
        
        # Step 7: Linear regression refinement (Phase Photonics optimized window)
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
        print(f"Error in Fourier dip finding: {e}")
        return np.nan


# ============================================================================
# PROCESS BASELINE DATA
# ============================================================================

DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")

if not DATA_FILE.exists():
    print(f"ERROR: Data file not found: {DATA_FILE}")
    exit(1)

print("=" * 80)
print("PHASE PHOTONICS OPTIMIZED SENSORGRAM")
print("=" * 80)
print(f"\nData file: {DATA_FILE}")
print(f"\nOptimized Parameters:")
print(f"  SG Window: {PHASE_PHOTONICS_CONFIG['sg_window']} pixels (0.94 nm)")
print(f"  Fourier Alpha: {PHASE_PHOTONICS_CONFIG['fourier_alpha']}")
print(f"  Fourier Window: {PHASE_PHOTONICS_CONFIG['fourier_window']} pixels (7.2 nm)")

# Process all 4 channels
channels = ["Channel_A", "Channel_B", "Channel_C", "Channel_D"]
results = {}

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Phase Photonics Baseline Stability - Optimized Parameters\nSensorgram (1 Hz, 300s)', 
             fontsize=14, fontweight='bold')

for idx, channel in enumerate(channels):
    print(f"\n{'-' * 80}")
    print(f"Processing {channel}")
    print(f"{'-' * 80}")
    
    # Load data
    df = pd.read_excel(DATA_FILE, sheet_name=channel)
    wavelengths = df['wavelength_nm'].values
    
    # Get number of timepoints (columns except wavelength column)
    num_timepoints = len(df.columns) - 1
    
    print(f"  Wavelengths: {len(wavelengths)} points ({wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm)")
    print(f"  Timepoints: {num_timepoints}")
    
    # Process all timepoints
    time_seconds = []
    dips_nm = []
    
    for i in range(num_timepoints):
        col_name = f't_{i:04d}'
        if col_name not in df.columns:
            continue
            
        transmission = df[col_name].values
        dip = find_dip_fourier(transmission, wavelengths, PHASE_PHOTONICS_CONFIG)
        
        if not np.isnan(dip):
            time_seconds.append(i)  # 1 Hz = 1 second per frame
            dips_nm.append(dip)
    
    if len(dips_nm) > 0:
        dips_nm = np.array(dips_nm)
        time_seconds = np.array(time_seconds)
        
        # Convert to RU (baseline at t=0 = 0 RU)
        baseline_nm = dips_nm[0]
        shifts_nm = dips_nm - baseline_nm
        shifts_RU = shifts_nm * 355  # 1 RU = 1 nm / 355
        
        # Statistics
        rms_RU = np.std(shifts_RU)
        p2p_RU = np.max(shifts_RU) - np.min(shifts_RU)
        mean_nm = np.mean(dips_nm)
        
        print(f"\n  Baseline wavelength: {baseline_nm:.3f} nm")
        print(f"  Mean wavelength: {mean_nm:.3f} nm")
        print(f"  RMS noise: {rms_RU:.2f} RU")
        print(f"  Peak-to-peak: {p2p_RU:.2f} RU")
        
        results[channel] = {
            "time": time_seconds,
            "wavelength": dips_nm,
            "shifts_RU": shifts_RU,
            "rms": rms_RU,
            "p2p": p2p_RU,
            "baseline": baseline_nm,
        }
        
        # Plot sensorgram
        ax = axes[idx // 2, idx % 2]
        ch_short = channel.split('_')[1]
        
        ax.plot(time_seconds, shifts_RU, 'o-', alpha=0.7, linewidth=1, markersize=2)
        ax.axhline(0, color='black', linestyle='--', linewidth=0.5, alpha=0.3)
        ax.set_xlabel('Time (s)', fontsize=10)
        ax.set_ylabel('Wavelength Shift (RU)', fontsize=10)
        ax.set_title(f'Channel {ch_short} - RMS: {rms_RU:.2f} RU, P-P: {p2p_RU:.2f} RU', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Add statistics text
        ax.text(0.02, 0.98, f'Baseline: {baseline_nm:.3f} nm\nMean: {mean_nm:.3f} nm', 
                transform=ax.transAxes, fontsize=8, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    else:
        print(f"  ERROR: No valid dips found!")

plt.tight_layout()
plt.savefig('phase_photonics_sensorgram_optimized.png', dpi=150, bbox_inches='tight')
print(f"\n{'=' * 80}")
print(f"Sensorgram saved: phase_photonics_sensorgram_optimized.png")

# Summary table
print(f"\n{'=' * 80}")
print("SUMMARY - PHASE PHOTONICS OPTIMIZED PARAMETERS")
print(f"{'=' * 80}")
print(f"{'Channel':<12} {'Baseline (nm)':<15} {'RMS (RU)':<12} {'Peak-to-Peak (RU)':<18}")
print(f"{'-' * 80}")

for channel in channels:
    ch_short = channel.split('_')[1]
    if channel in results:
        baseline = results[channel]["baseline"]
        rms = results[channel]["rms"]
        p2p = results[channel]["p2p"]
        print(f"{ch_short:<12} {baseline:>10.3f}      {rms:>8.2f}     {p2p:>12.2f}")
    else:
        print(f"{ch_short:<12} {'N/A':<15} {'N/A':<12} {'N/A':<18}")

print(f"\n{'=' * 80}")
print("Parameters Used:")
print(f"  SG Window: {PHASE_PHOTONICS_CONFIG['sg_window']} pixels")
print(f"  Fourier Alpha: {PHASE_PHOTONICS_CONFIG['fourier_alpha']}")
print(f"  Fourier Window: {PHASE_PHOTONICS_CONFIG['fourier_window']} pixels")
print(f"{'=' * 80}")
