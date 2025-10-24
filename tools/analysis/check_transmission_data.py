"""
Check what data we have for calculating transmission from Channel A
"""
import numpy as np
from pathlib import Path

# Load S-mode data
s_path = Path('spectral_training_data/demo P4SPR 2.0/s/used/20251022_140707/channel_A.npz')
s_data = np.load(s_path)

# Load P-mode data
p_path = Path('spectral_training_data/demo P4SPR 2.0/p/used/20251022_140940/channel_A.npz')
p_data = np.load(p_path)

print("="*70)
print("CHANNEL A DATA INVENTORY FOR TRANSMISSION CALCULATION")
print("="*70)

print("\n📊 S-MODE DATA (Reference signal, no sensor resonance):")
print(f"   Keys: {list(s_data.keys())}")
print(f"   Spectra shape: {s_data['spectra'].shape}")
print(f"   Dark shape: {s_data['dark'].shape}")
print(f"   Timestamps shape: {s_data['timestamps'].shape}")
print(f"   Duration: {s_data['timestamps'][-1]:.1f} seconds")
print(f"   Number of spectra: {len(s_data['spectra'])}")
print(f"   Wavelength points: {s_data['spectra'].shape[1]}")

print("\n📊 P-MODE DATA (Sample signal, with sensor resonance):")
print(f"   Keys: {list(p_data.keys())}")
print(f"   Spectra shape: {p_data['spectra'].shape}")
print(f"   Dark shape: {p_data['dark'].shape}")
print(f"   Timestamps shape: {p_data['timestamps'].shape}")
print(f"   Duration: {p_data['timestamps'][-1]:.1f} seconds")
print(f"   Number of spectra: {len(p_data['spectra'])}")
print(f"   Wavelength points: {p_data['spectra'].shape[1]}")

print("\n" + "="*70)
print("TRANSMISSION CALCULATION REQUIREMENTS")
print("="*70)

print("\n✅ What we HAVE:")
print("   • P-mode signal (sample): 480 spectra × 3648 pixels")
print("   • S-mode signal (reference): 480 spectra × 3648 pixels")
print("   • Dark spectra for both modes")
print("   • Timestamps for temporal tracking")

print("\n📐 TRANSMISSION FORMULA:")
print("   T = (P_signal - P_dark) / (S_signal - S_dark)")
print()
print("   Where:")
print("   • P_signal = Raw P-mode spectrum (with sensor resonance)")
print("   • P_dark = P-mode dark spectrum")
print("   • S_signal = Raw S-mode spectrum (no sensor resonance)")
print("   • S_dark = S-mode dark spectrum")

print("\n🤔 QUESTION: How to pair S and P spectra?")
print()
print("   Option 1: Use SINGLE S-mode reference (average or specific time)")
print("   • Pro: Simple, fast, matches production (1 ref per cycle)")
print("   • Con: Doesn't account for temporal drift in reference")
print()
print("   Option 2: Time-matched S and P references")
print("   • Pro: Corrects for LED drift in both modes")
print("   • Con: Requires paired collection (not how production works)")
print()
print("   Option 3: Use S-mode trend model")
print("   • Pro: Best drift correction")
print("   • Con: More complex, requires fitting")

print("\n💡 RECOMMENDATION:")
print("   Start with Option 1 (single S-mode reference) because:")
print("   • Matches production workflow (S measured once per cycle)")
print("   • Fast computation (<10ms requirement)")
print("   • We can use median of S-mode spectra for stability")

print("\n" + "="*70)

# Show a sample calculation
print("\nSAMPLE CALCULATION (first spectrum):")
print("="*70)

# Dark subtraction
s_corrected = s_data['spectra'][0] - s_data['dark'][0]
p_corrected = p_data['spectra'][0] - p_data['dark'][0]

# Transmission
transmission = p_corrected / np.maximum(s_corrected, 1.0)  # Avoid division by zero

print(f"\nS-mode (reference) - first spectrum:")
print(f"  Raw signal range: {s_data['spectra'][0].min():.0f} - {s_data['spectra'][0].max():.0f} counts")
print(f"  Dark level: {s_data['dark'][0].mean():.0f} counts")
print(f"  Corrected range: {s_corrected.min():.0f} - {s_corrected.max():.0f} counts")

print(f"\nP-mode (sample) - first spectrum:")
print(f"  Raw signal range: {p_data['spectra'][0].min():.0f} - {p_data['spectra'][0].max():.0f} counts")
print(f"  Dark level: {p_data['dark'][0].mean():.0f} counts")
print(f"  Corrected range: {p_corrected.min():.0f} - {p_corrected.max():.0f} counts")

print(f"\nTransmission spectrum:")
print(f"  Range: {transmission.min():.3f} - {transmission.max():.3f}")
print(f"  Mean: {transmission.mean():.3f}")
print(f"  Typical sensor dip location: pixel ~1800-2000 (if resonance present)")

print("\n✅ YES - We have everything needed to calculate transmission!")
print("="*70)
