"""Optimize Phase Photonics Dip Tracking Parameters

The Phase Photonics detector has different characteristics than Ocean Optics:
- Phase Photonics ST00012: 1848 pixels, 0.085 nm/pixel resolution (570-720 nm = 150nm / 1766 valid pixels)
- Ocean Optics USB4000: 3648 pixels, ~0.044 nm/pixel resolution (560-720 nm = 160nm / ~3700 pixels)

Phase Photonics has ~50% of the pixel density → need adjusted parameters:

1. FOURIER_WINDOW (linear regression refinement window):
   - Current: 165 pixels → 165 × 0.085 nm = 14.0 nm window
   - Ocean Optics: 165 × 0.044 nm = 7.3 nm window
   - Optimal for Phase Photonics: ~85 pixels (7.2 nm window, similar physical size)

2. SG_WINDOW (Savitzky-Golay smoothing):
   - Current: 21 pixels → 21 × 0.085 nm = 1.8 nm window
   - Ocean Optics: 21 × 0.044 nm = 0.9 nm window
   - Optimal for Phase Photonics: ~11 pixels (0.9 nm window, similar physical size)

3. FOURIER_ALPHA (regularization strength):
   - Current: 9000 (optimized for USB4000 with 3700 pixels)
   - Phase Photonics has half the pixels → less regularization needed
   - Optimal: ~4500 (scale with pixel count)
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
    # Detector characteristics
    "pixels": 1848,
    "wavelength_range": (570.0, 720.0),
    "nm_per_pixel": 0.085,  # 150 nm / 1766 pixels
    
    # OPTIMIZED Pipeline parameters
    "sg_window": 11,  # Reduced from 21 (similar physical window: 0.9 nm)
    "sg_polyorder": 3,
    "fourier_alpha": 4500,  # Reduced from 9000 (scale with pixel count)
    "fourier_window": 85,  # Reduced from 165 (similar physical window: 7.2 nm)
}

OCEAN_OPTICS_CONFIG = {
    # Detector characteristics  
    "pixels": 3648,
    "wavelength_range": (560.0, 720.0),
    "nm_per_pixel": 0.044,  # 160 nm / 3700 pixels
    
    # DEFAULT Pipeline parameters (baseline)
    "sg_window": 21,
    "sg_polyorder": 3,
    "fourier_alpha": 9000,
    "fourier_window": 165,
}

# ============================================================================
# FOURIER DIP FINDING (Phase Photonics Optimized)
# ============================================================================

def find_dip_fourier_optimized(transmission, wavelengths, config):
    """Find resonance dip using Fourier method with detector-specific parameters.
    
    Args:
        transmission: Transmission spectrum (%)
        wavelengths: Wavelength array (nm)
        config: Parameter dictionary (PHASE_PHOTONICS_CONFIG or OCEAN_OPTICS_CONFIG)
        
    Returns:
        resonance_wavelength: Peak wavelength (nm)
    """
    try:
        # Filter wavelength range
        wl_min, wl_max = config["wavelength_range"]
        valid_mask = (wavelengths >= wl_min) & (wavelengths <= wl_max)
        wl = wavelengths[valid_mask]
        trans = transmission[valid_mask]
        
        if len(wl) < 50:
            return np.nan
            
        # Step 1: Savitzky-Golay smoothing (detector-optimized window)
        sg_window = config["sg_window"]
        if len(trans) >= sg_window:
            trans_smooth = savgol_filter(trans, sg_window, config["sg_polyorder"], mode='nearest')
        else:
            trans_smooth = trans
            
        # Step 2: Calculate Fourier weights (detector-specific alpha)
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
        
        # Step 7: Linear regression refinement (detector-specific window)
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
# ANALYZE BASELINE DATA
# ============================================================================

def analyze_baseline_with_optimized_params():
    """Compare default vs optimized parameters on Phase Photonics baseline data."""
    
    DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")
    
    if not DATA_FILE.exists():
        print(f"ERROR: Data file not found: {DATA_FILE}")
        return
        
    print("=" * 80)
    print("PHASE PHOTONICS PARAMETER OPTIMIZATION")
    print("=" * 80)
    print(f"\nData file: {DATA_FILE}")
    print(f"\nDetector: Phase Photonics ST00012")
    print(f"  Pixels: {PHASE_PHOTONICS_CONFIG['pixels']}")
    print(f"  Range: {PHASE_PHOTONICS_CONFIG['wavelength_range']} nm")
    print(f"  Resolution: {PHASE_PHOTONICS_CONFIG['nm_per_pixel']:.3f} nm/pixel")
    
    print(f"\n{'=' * 80}")
    print("PARAMETER COMPARISON")
    print(f"{'=' * 80}")
    print(f"{'Parameter':<25} {'Ocean Optics':<20} {'Phase Photonics':<20} {'Physical Size':<20}")
    print(f"{'-' * 85}")
    
    # SG Window
    oo_sg_nm = OCEAN_OPTICS_CONFIG['sg_window'] * OCEAN_OPTICS_CONFIG['nm_per_pixel']
    pp_sg_nm = PHASE_PHOTONICS_CONFIG['sg_window'] * PHASE_PHOTONICS_CONFIG['nm_per_pixel']
    print(f"{'SG Window (pixels)':<25} {OCEAN_OPTICS_CONFIG['sg_window']:<20} {PHASE_PHOTONICS_CONFIG['sg_window']:<20} {pp_sg_nm:.2f} nm")
    
    # Fourier Window
    oo_fw_nm = OCEAN_OPTICS_CONFIG['fourier_window'] * OCEAN_OPTICS_CONFIG['nm_per_pixel']
    pp_fw_nm = PHASE_PHOTONICS_CONFIG['fourier_window'] * PHASE_PHOTONICS_CONFIG['nm_per_pixel']
    print(f"{'Fourier Window (pixels)':<25} {OCEAN_OPTICS_CONFIG['fourier_window']:<20} {PHASE_PHOTONICS_CONFIG['fourier_window']:<20} {pp_fw_nm:.2f} nm")
    
    # Fourier Alpha
    print(f"{'Fourier Alpha':<25} {OCEAN_OPTICS_CONFIG['fourier_alpha']:<20} {PHASE_PHOTONICS_CONFIG['fourier_alpha']:<20} {'Regularization':<20}")
    
    print(f"\n{'=' * 80}")
    print("PROCESSING ALL CHANNELS")
    print(f"{'=' * 80}")
    
    # Process all 4 channels
    channels = ["Channel_A", "Channel_B", "Channel_C", "Channel_D"]
    results = {}
    
    for channel in channels:
        print(f"\n{channel.upper()}:")
        print(f"{'-' * 80}")
        
        # Load data
        df = pd.read_excel(DATA_FILE, sheet_name=channel)
        wavelengths = df.iloc[:, 0].values
        
        # Process all timepoints with BOTH parameter sets
        num_timepoints = df.shape[0]
        
        # DEFAULT parameters (Ocean Optics baseline)
        dips_default = []
        for i in range(num_timepoints):
            transmission = df.iloc[i, 1:].values
            dip = find_dip_fourier_optimized(transmission, wavelengths, OCEAN_OPTICS_CONFIG)
            if not np.isnan(dip):
                dips_default.append(dip)
        
        # OPTIMIZED parameters (Phase Photonics)
        dips_optimized = []
        for i in range(num_timepoints):
            transmission = df.iloc[i, 1:].values
            dip = find_dip_fourier_optimized(transmission, wavelengths, PHASE_PHOTONICS_CONFIG)
            if not np.isnan(dip):
                dips_optimized.append(dip)
        
        # Convert to RU (1 RU = 1 nm / 355)
        if len(dips_default) > 0:
            dips_default = np.array(dips_default)
            baseline_default = dips_default[0]
            shifts_default_nm = (dips_default - baseline_default)
            shifts_default_RU = shifts_default_nm * 355
            
            rms_default = np.std(shifts_default_RU)
            p2p_default = np.max(shifts_default_RU) - np.min(shifts_default_RU)
        else:
            rms_default = np.nan
            p2p_default = np.nan
            
        if len(dips_optimized) > 0:
            dips_optimized = np.array(dips_optimized)
            baseline_optimized = dips_optimized[0]
            shifts_optimized_nm = (dips_optimized - baseline_optimized)
            shifts_optimized_RU = shifts_optimized_nm * 355
            
            rms_optimized = np.std(shifts_optimized_RU)
            p2p_optimized = np.max(shifts_optimized_RU) - np.min(shifts_optimized_RU)
        else:
            rms_optimized = np.nan
            p2p_optimized = np.nan
        
        print(f"  DEFAULT (Ocean Optics params):")
        print(f"    RMS noise: {rms_default:.2f} RU")
        print(f"    Peak-to-peak: {p2p_default:.2f} RU")
        
        print(f"  OPTIMIZED (Phase Photonics params):")
        print(f"    RMS noise: {rms_optimized:.2f} RU")
        print(f"    Peak-to-peak: {p2p_optimized:.2f} RU")
        
        if not np.isnan(rms_default) and not np.isnan(rms_optimized):
            improvement = ((rms_default - rms_optimized) / rms_default) * 100
            print(f"  IMPROVEMENT: {improvement:+.1f}% {'(better)' if improvement > 0 else '(worse)'}")
        
        results[channel] = {
            "default_rms": rms_default,
            "default_p2p": p2p_default,
            "optimized_rms": rms_optimized,
            "optimized_p2p": p2p_optimized,
            "default_dips": dips_default,
            "optimized_dips": dips_optimized,
            "default_RU": shifts_default_RU if len(dips_default) > 0 else None,
            "optimized_RU": shifts_optimized_RU if len(dips_optimized) > 0 else None,
        }
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"{'Channel':<12} {'Default RMS':<15} {'Optimized RMS':<15} {'Improvement':<15}")
    print(f"{'-' * 80}")
    
    for channel in channels:
        ch_short = channel.split('_')[1]
        default_rms = results[channel]["default_rms"]
        optimized_rms = results[channel]["optimized_rms"]
        
        if not np.isnan(default_rms) and not np.isnan(optimized_rms):
            improvement = ((default_rms - optimized_rms) / default_rms) * 100
            print(f"{ch_short:<12} {default_rms:>8.2f} RU    {optimized_rms:>8.2f} RU    {improvement:>+7.1f}%")
        else:
            print(f"{ch_short:<12} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
    
    # Visualization
    print(f"\n{'=' * 80}")
    print("GENERATING COMPARISON PLOTS")
    print(f"{'=' * 80}")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Phase Photonics: Default vs Optimized Parameters\nBaseline Stability Comparison', 
                 fontsize=14, fontweight='bold')
    
    for idx, channel in enumerate(channels):
        ax = axes[idx // 2, idx % 2]
        ch_short = channel.split('_')[1]
        
        default_RU = results[channel]["default_RU"]
        optimized_RU = results[channel]["optimized_RU"]
        
        if default_RU is not None and optimized_RU is not None:
            time_default = np.arange(len(default_RU))
            time_optimized = np.arange(len(optimized_RU))
            
            ax.plot(time_default, default_RU, 'o-', alpha=0.6, linewidth=1, 
                   markersize=3, label=f'Default (RMS: {results[channel]["default_rms"]:.1f} RU)')
            ax.plot(time_optimized, optimized_RU, 's-', alpha=0.6, linewidth=1,
                   markersize=3, label=f'Optimized (RMS: {results[channel]["optimized_rms"]:.1f} RU)')
            
            ax.axhline(0, color='black', linestyle='--', linewidth=0.5, alpha=0.3)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Wavelength Shift (RU)')
            ax.set_title(f'Channel {ch_short}')
            ax.legend(loc='best', fontsize=8)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
    
    plt.tight_layout()
    plt.savefig('phase_photonics_parameter_optimization.png', dpi=150, bbox_inches='tight')
    print(f"\nPlot saved: phase_photonics_parameter_optimization.png")
    
    print(f"\n{'=' * 80}")
    print("RECOMMENDED PARAMETERS FOR PHASE PHOTONICS")
    print(f"{'=' * 80}")
    print(f"""
Update these values in your settings or pipeline configuration:

PHASE_PHOTONICS_FOURIER_PARAMS = {{
    "sg_window": {PHASE_PHOTONICS_CONFIG['sg_window']},           # Savitzky-Golay window (reduced from 21)
    "sg_polyorder": {PHASE_PHOTONICS_CONFIG['sg_polyorder']},        # Polynomial order
    "fourier_alpha": {PHASE_PHOTONICS_CONFIG['fourier_alpha']},      # Regularization (reduced from 9000)
    "fourier_window": {PHASE_PHOTONICS_CONFIG['fourier_window']},     # Linear regression window (reduced from 165)
}}

Physical window sizes:
  - SG smoothing: {pp_sg_nm:.2f} nm (similar to Ocean Optics {oo_sg_nm:.2f} nm)
  - Fourier refinement: {pp_fw_nm:.2f} nm (similar to Ocean Optics {oo_fw_nm:.2f} nm)
""")


if __name__ == "__main__":
    analyze_baseline_with_optimized_params()
