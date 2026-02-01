"""FULL PRODUCTION PIPELINE WALKTHROUGH - GOLD STANDARD METHOD

This script applies the EXACT peak finding method from main.py including:
1. Savitzky-Golay spectral smoothing (window=21, poly=3)
2. Fourier transform (DST/IDCT) for derivative calculation
3. Zero-crossing detection with linear regression refinement

This is the "GOLD STANDARD" pipeline that achieved 0.008 nm baseline noise.

Data: baseline_recording_20260126_235959.xlsx
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import savgol_filter
from scipy.fft import dst, idct
from scipy.stats import linregress
import matplotlib.pyplot as plt

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")

# GOLD STANDARD parameters from affilabs/utils/pipelines/batch_savgol_pipeline.py
TRANSMISSION_SAVGOL_WINDOW = 21  # Must be odd
TRANSMISSION_SAVGOL_POLY = 3  # Cubic polynomial

FOURIER_ALPHA = 9000  # Smoothing strength
FOURIER_WINDOW = 165  # Window around zero-crossing for refinement

WAVELENGTH_RANGE = (570.0, 720.0)  # Valid detector range

# ============================================================================
# LOAD DATA
# ============================================================================

print("=" * 80)
print("GOLD STANDARD PEAK FINDING PIPELINE")
print("=" * 80)
print(f"\nLoading data from: {DATA_FILE}")

# Read Channel A data
df = pd.read_excel(DATA_FILE, sheet_name="Channel_A")
print(f"Data shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

# Extract wavelength array (first column)
wavelengths_raw = df.iloc[:, 0].values
print(f"\nRaw wavelengths: {len(wavelengths_raw)} points")
print(f"Range: {wavelengths_raw.min():.2f} - {wavelengths_raw.max():.2f} nm")

# Extract first timepoint (t_0000)
transmission_raw = df.iloc[:, 1].values
print(f"Raw transmission: {len(transmission_raw)} points")
print(f"Range: {transmission_raw.min():.4f} - {transmission_raw.max():.4f}%")

# ============================================================================
# STEP 1: WAVELENGTH FILTERING (570-720 nm)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 1: WAVELENGTH FILTERING")
print("=" * 80)

# Apply wavelength filter (detector limitation below 570nm)
wavelength_mask = (wavelengths_raw >= WAVELENGTH_RANGE[0]) & (wavelengths_raw <= WAVELENGTH_RANGE[1])
wavelengths = wavelengths_raw[wavelength_mask]
transmission_spectrum = transmission_raw[wavelength_mask]

print(f"\nFiltered wavelengths: {len(wavelengths)} points")
print(f"Range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")
print(f"Filtered transmission range: {transmission_spectrum.min():.4f} - {transmission_spectrum.max():.4f}%")

# ============================================================================
# STEP 2: SAVITZKY-GOLAY FILTERING (STAGE 3)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 2: SAVITZKY-GOLAY SPECTRAL SMOOTHING (STAGE 3)")
print("=" * 80)
print("\nParameters:")
print(f"  Window length: {TRANSMISSION_SAVGOL_WINDOW} points")
print(f"  Polynomial order: {TRANSMISSION_SAVGOL_POLY} (cubic)")
print(f"  Wavelength span: ~{TRANSMISSION_SAVGOL_WINDOW * 0.2:.1f} nm @ 0.2nm/pixel")

# Check if spectrum is long enough for SG filter
if len(transmission_spectrum) >= TRANSMISSION_SAVGOL_WINDOW:
    filtered_transmission = savgol_filter(
        transmission_spectrum,
        window_length=TRANSMISSION_SAVGOL_WINDOW,
        polyorder=TRANSMISSION_SAVGOL_POLY,
    )
    print("\nSavitzky-Golay filter applied successfully")
    print(f"RMS noise before SG: {np.std(transmission_spectrum):.6f}%")
    print(f"RMS noise after SG: {np.std(filtered_transmission):.6f}%")
    print(f"Noise reduction: {(1 - np.std(filtered_transmission)/np.std(transmission_spectrum))*100:.1f}%")
else:
    filtered_transmission = transmission_spectrum
    print(f"\n⚠ WARNING: Spectrum too short ({len(transmission_spectrum)} < {TRANSMISSION_SAVGOL_WINDOW})")
    print("Skipping SG filter, using raw transmission")

# ============================================================================
# STEP 3: FOURIER TRANSFORM DERIVATIVE CALCULATION (STAGE 4)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 3: FOURIER TRANSFORM DERIVATIVE (STAGE 4)")
print("=" * 80)
print("\nParameters:")
print(f"  Alpha (smoothing): {FOURIER_ALPHA}")
print("  Method: DST (Discrete Sine Transform) + IDCT (Inverse DCT)")

spectrum = filtered_transmission
n = len(spectrum) - 1

# Calculate Fourier weights
print(f"\nCalculating Fourier weights (n={n})...")
phi = np.pi / n * np.arange(1, n)
phi2 = phi**2
fourier_weights = phi / (1 + FOURIER_ALPHA * phi2 * (1 + phi2))
print(f"Fourier weights range: {fourier_weights.min():.6e} - {fourier_weights.max():.6e}")

# Initialize Fourier coefficients
fourier_coeff = np.zeros_like(spectrum)
fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

# Linear detrending
print("\nLinear detrending...")
linear_baseline = np.linspace(spectrum[0], spectrum[-1], len(spectrum))
detrended = spectrum[1:-1] - linear_baseline[1:-1]
print(f"Detrended range: {detrended.min():.6f} - {detrended.max():.6f}%")

# Apply DST with weights
print("\nApplying DST (Discrete Sine Transform)...")
dst_result = dst(detrended, type=1)
fourier_coeff[1:-1] = fourier_weights * dst_result
print(f"DST result range: {dst_result.min():.6e} - {dst_result.max():.6e}")

# Inverse transform to get derivative
print("\nApplying IDCT (Inverse Discrete Cosine Transform)...")
derivative = idct(fourier_coeff, type=1)
print(f"Derivative calculated: {len(derivative)} points")
print(f"Derivative range: {derivative.min():.6e} - {derivative.max():.6e}")

# ============================================================================
# STEP 4: ZERO-CROSSING DETECTION (STAGE 5)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 4: ZERO-CROSSING DETECTION (STAGE 5)")
print("=" * 80)

# Find where derivative crosses zero (changes sign)
zero_idx = np.searchsorted(derivative, 0)
print(f"\nZero-crossing index: {zero_idx}")
print(f"Zero-crossing wavelength (approx): {wavelengths[zero_idx]:.3f} nm")
print(f"Derivative before zero: {derivative[zero_idx-1]:.6e}")
print(f"Derivative after zero: {derivative[zero_idx]:.6e}")

# Check if zero-crossing is at boundary
if zero_idx == 0 or zero_idx >= len(derivative) - 1:
    print("\n⚠ WARNING: Zero-crossing at boundary!")
    min_idx = np.argmin(spectrum)
    peak_wavelength_fallback = wavelengths[min_idx]
    print(f"Fallback to minimum: {peak_wavelength_fallback:.3f} nm")
else:
    # ============================================================================
    # STEP 5: LINEAR REGRESSION REFINEMENT
    # ============================================================================

    print("\n" + "=" * 80)
    print("STEP 5: LINEAR REGRESSION REFINEMENT")
    print("=" * 80)
    print("\nParameters:")
    print(f"  Window size: ±{FOURIER_WINDOW} points")

    # Define window around zero-crossing
    start_idx = max(zero_idx - FOURIER_WINDOW, 0)
    end_idx = min(zero_idx + FOURIER_WINDOW, len(derivative) - 1)

    wl_window = wavelengths[start_idx:end_idx]
    deriv_window = derivative[start_idx:end_idx]

    print("\nWindow range:")
    print(f"  Indices: {start_idx} to {end_idx} ({len(wl_window)} points)")
    print(f"  Wavelengths: {wl_window.min():.3f} - {wl_window.max():.3f} nm")
    print(f"  Derivative range: {deriv_window.min():.6e} - {deriv_window.max():.6e}")

    if len(wl_window) < 3:
        print(f"\n⚠ WARNING: Not enough points for regression ({len(wl_window)} < 3)")
        peak_wavelength = wavelengths[zero_idx]
        print(f"Using zero-crossing index: {peak_wavelength:.3f} nm")
    else:
        # Linear regression: derivative = slope * wavelength + intercept
        slope, intercept, r_value, p_value, std_err = linregress(wl_window, deriv_window)

        print("\nLinear regression results:")
        print(f"  Slope: {slope:.6e} (derivative change per nm)")
        print(f"  Intercept: {intercept:.6e}")
        print(f"  R²: {r_value**2:.6f} (goodness of fit)")
        print(f"  P-value: {p_value:.6e}")
        print(f"  Std error: {std_err:.6e}")

        if abs(slope) < 1e-10:
            print(f"\n⚠ WARNING: Slope too small ({abs(slope):.6e} < 1e-10)")
            peak_wavelength = wavelengths[zero_idx]
            print(f"Using zero-crossing index: {peak_wavelength:.3f} nm")
        else:
            # Solve for zero-crossing: 0 = slope * λ + intercept
            # λ = -intercept / slope
            peak_wavelength = -intercept / slope

            print("\nRefined zero-crossing:")
            print(f"  Peak wavelength: {peak_wavelength:.6f} nm")
            print(f"  Improvement: {abs(peak_wavelength - wavelengths[zero_idx])*1000:.3f} pm from index")

            # Sanity check
            if peak_wavelength < wl_window.min() or peak_wavelength > wl_window.max():
                print(f"\n⚠ WARNING: Peak outside window! ({peak_wavelength:.3f} nm)")
                print(f"Window range: {wl_window.min():.3f} - {wl_window.max():.3f} nm")
                peak_wavelength = wavelengths[zero_idx]
                print(f"Using zero-crossing index: {peak_wavelength:.3f} nm")

# ============================================================================
# STEP 6: COMPARISON WITH SIMPLE ARGMIN
# ============================================================================

print("\n" + "=" * 80)
print("STEP 6: COMPARISON WITH SIMPLE ARGMIN")
print("=" * 80)

# Simple argmin on raw transmission
argmin_raw_idx = np.argmin(transmission_spectrum)
argmin_raw_wavelength = wavelengths[argmin_raw_idx]
argmin_raw_transmission = transmission_spectrum[argmin_raw_idx]

# Simple argmin on SG-filtered transmission
argmin_sg_idx = np.argmin(filtered_transmission)
argmin_sg_wavelength = wavelengths[argmin_sg_idx]
argmin_sg_transmission = filtered_transmission[argmin_sg_idx]

print(f"\nSimple argmin (raw): {argmin_raw_wavelength:.6f} nm ({argmin_raw_transmission:.4f}%)")
print(f"Simple argmin (SG-filtered): {argmin_sg_wavelength:.6f} nm ({argmin_sg_transmission:.4f}%)")
print(f"GOLD STANDARD (SG + Fourier): {peak_wavelength:.6f} nm")
print(f"\nDifference (argmin raw vs GOLD): {abs(argmin_raw_wavelength - peak_wavelength)*1000:.3f} pm")
print(f"Difference (argmin SG vs GOLD): {abs(argmin_sg_wavelength - peak_wavelength)*1000:.3f} pm")

# ============================================================================
# VISUALIZATION
# ============================================================================

print("\n" + "=" * 80)
print("GENERATING VISUALIZATION")
print("=" * 80)

fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# Plot 1: Raw vs SG-filtered transmission
ax1.plot(wavelengths, transmission_spectrum, 'b-', alpha=0.5, linewidth=1, label='Raw transmission')
ax1.plot(wavelengths, filtered_transmission, 'r-', linewidth=2, label='SG-filtered (window=21, poly=3)')
ax1.axvline(argmin_raw_wavelength, color='b', linestyle='--', alpha=0.5, label=f'Argmin raw: {argmin_raw_wavelength:.3f} nm')
ax1.axvline(peak_wavelength, color='g', linestyle='-', linewidth=2, label=f'GOLD STANDARD: {peak_wavelength:.3f} nm')
ax1.set_xlabel('Wavelength (nm)', fontsize=12)
ax1.set_ylabel('Transmission (%)', fontsize=12)
ax1.set_title('Step 2: Savitzky-Golay Filtering', fontsize=14, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)

# Plot 2: Derivative from Fourier transform
ax2.plot(wavelengths, derivative, 'purple', linewidth=2, label='Fourier derivative')
ax2.axhline(0, color='k', linestyle='--', alpha=0.5)
ax2.axvline(peak_wavelength, color='g', linestyle='-', linewidth=2, label=f'Zero-crossing: {peak_wavelength:.3f} nm')
ax2.set_xlabel('Wavelength (nm)', fontsize=12)
ax2.set_ylabel('Derivative (a.u.)', fontsize=12)
ax2.set_title('Step 3-4: Fourier Transform Derivative', fontsize=14, fontweight='bold')
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

# Plot 3: Zero-crossing detail with linear regression
window_start = max(zero_idx - FOURIER_WINDOW, 0)
window_end = min(zero_idx + FOURIER_WINDOW, len(derivative) - 1)
ax3.plot(wavelengths[window_start:window_end], derivative[window_start:window_end], 'bo-', markersize=3, label='Derivative')
ax3.axhline(0, color='k', linestyle='--', alpha=0.5)
ax3.axvline(wavelengths[zero_idx], color='orange', linestyle='--', label=f'Index: {wavelengths[zero_idx]:.3f} nm')
ax3.axvline(peak_wavelength, color='g', linestyle='-', linewidth=2, label=f'Refined: {peak_wavelength:.3f} nm')
# Plot regression line
if len(wl_window) >= 3 and abs(slope) >= 1e-10:
    regression_line = slope * wl_window + intercept
    ax3.plot(wl_window, regression_line, 'r--', linewidth=2, alpha=0.7, label=f'Linear fit (R²={r_value**2:.4f})')
ax3.set_xlabel('Wavelength (nm)', fontsize=12)
ax3.set_ylabel('Derivative (a.u.)', fontsize=12)
ax3.set_title('Step 5: Linear Regression Refinement', fontsize=14, fontweight='bold')
ax3.legend(fontsize=10)
ax3.grid(True, alpha=0.3)

# Plot 4: Final peak location on filtered spectrum
dip_window = 10  # Show ±10 nm around dip
dip_mask = (wavelengths >= peak_wavelength - dip_window) & (wavelengths <= peak_wavelength + dip_window)
ax4.plot(wavelengths[dip_mask], filtered_transmission[dip_mask], 'r-', linewidth=2, label='SG-filtered transmission')
ax4.axvline(peak_wavelength, color='g', linestyle='-', linewidth=2, label=f'GOLD STANDARD: {peak_wavelength:.6f} nm')
ax4.axvline(argmin_sg_wavelength, color='orange', linestyle='--', label=f'Argmin: {argmin_sg_wavelength:.6f} nm')
ax4.plot(peak_wavelength, np.interp(peak_wavelength, wavelengths, filtered_transmission), 'go', markersize=10, label='Peak (Fourier)')
ax4.set_xlabel('Wavelength (nm)', fontsize=12)
ax4.set_ylabel('Transmission (%)', fontsize=12)
ax4.set_title('Final Peak Location (±10 nm window)', fontsize=14, fontweight='bold')
ax4.legend(fontsize=10)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('gold_standard_pipeline_detailed.png', dpi=300, bbox_inches='tight')
print("\nSaved: gold_standard_pipeline_detailed.png")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("SUMMARY - GOLD STANDARD PIPELINE")
print("=" * 80)

print("\n📊 INPUT DATA:")
print(f"  File: {DATA_FILE.name}")
print(f"  Raw wavelengths: {len(wavelengths_raw)} points ({wavelengths_raw.min():.2f}-{wavelengths_raw.max():.2f} nm)")
print(f"  Filtered wavelengths: {len(wavelengths)} points ({wavelengths.min():.2f}-{wavelengths.max():.2f} nm)")

print("\n🔧 PROCESSING STAGES:")
print("  Stage 1: Wavelength filtering (570-720 nm)")
print(f"  Stage 2: Savitzky-Golay spectral smoothing (window={TRANSMISSION_SAVGOL_WINDOW}, poly={TRANSMISSION_SAVGOL_POLY})")
print(f"  Stage 3: Fourier transform derivative (alpha={FOURIER_ALPHA})")
print("  Stage 4: Zero-crossing detection")
print(f"  Stage 5: Linear regression refinement (window=±{FOURIER_WINDOW})")

print("\n🎯 RESULTS:")
print(f"  Simple argmin (raw): {argmin_raw_wavelength:.6f} nm")
print(f"  Simple argmin (SG): {argmin_sg_wavelength:.6f} nm")
print(f"  GOLD STANDARD: {peak_wavelength:.6f} nm ⭐")
print(f"  Refinement: {abs(peak_wavelength - argmin_sg_wavelength)*1000:.3f} pm from argmin")

print("\n✅ GOLD STANDARD PIPELINE COMPLETE")
print("=" * 80)
