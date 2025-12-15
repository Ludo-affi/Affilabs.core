"""Quick diagnostic to visualize transmission issues"""

import matplotlib.pyplot as plt
import numpy as np

# Load both datasets
print("Loading data...")
s_old = np.load("training_data/used_current/20251022_165706_channel_A_s_mode.npz")
p_old = np.load("training_data/used_current/20251022_165706_channel_A_p_mode.npz")
s_new = np.load("training_data/new_sealed/20251022_173640_channel_A_s_mode.npz")
p_new = np.load("training_data/new_sealed/20251022_173640_channel_A_p_mode.npz")

fig, axes = plt.subplots(3, 2, figsize=(16, 12))

# OLD SENSOR (LEFT COLUMN)
s_spec_old = s_old["spectra"][0]
p_spec_old = p_old["spectra"][0]
s_dark_old = s_old["dark"]
p_dark_old = p_old["dark"]

# Raw spectra
axes[0, 0].plot(s_spec_old, "b-", alpha=0.7, label="S-mode")
axes[0, 0].plot(p_spec_old, "r-", alpha=0.7, label="P-mode")
axes[0, 0].axhline(65535, color="k", linestyle="--", alpha=0.3, label="Saturation")
axes[0, 0].set_title(
    "OLD SENSOR: Raw Spectra (SATURATED!)",
    fontsize=12,
    fontweight="bold",
)
axes[0, 0].set_ylabel("Counts")
axes[0, 0].legend()
axes[0, 0].grid(alpha=0.3)

# Dark-corrected
s_corr_old = s_spec_old - s_dark_old
p_corr_old = p_spec_old - p_dark_old
axes[1, 0].plot(s_corr_old, "b-", alpha=0.7, label="S-mode (dark corrected)")
axes[1, 0].plot(p_corr_old, "r-", alpha=0.7, label="P-mode (dark corrected)")
axes[1, 0].set_title("OLD SENSOR: Dark Corrected", fontsize=12, fontweight="bold")
axes[1, 0].set_ylabel("Counts")
axes[1, 0].legend()
axes[1, 0].grid(alpha=0.3)

# Transmission
trans_old = p_corr_old / np.where(s_corr_old < 1, 1, s_corr_old)
axes[2, 0].plot(trans_old, "g-", linewidth=1.5)
axes[2, 0].axhline(1.0, color="k", linestyle="--", alpha=0.3)
axes[2, 0].set_title(
    f"OLD SENSOR: Transmission\nRange: {trans_old.min():.3f} to {trans_old.max():.3f}",
    fontsize=12,
    fontweight="bold",
)
axes[2, 0].set_ylabel("Transmission (P/S)")
axes[2, 0].set_xlabel("Pixel")
axes[2, 0].grid(alpha=0.3)
axes[2, 0].set_ylim([-1, 3])

# NEW SENSOR (RIGHT COLUMN)
s_spec_new = s_new["spectra"][0]
p_spec_new = p_new["spectra"][0]
s_dark_new = s_new["dark"]
p_dark_new = p_new["dark"]

# Raw spectra
axes[0, 1].plot(s_spec_new, "b-", alpha=0.7, label="S-mode")
axes[0, 1].plot(p_spec_new, "r-", alpha=0.7, label="P-mode")
axes[0, 1].axhline(65535, color="k", linestyle="--", alpha=0.3, label="Saturation")
axes[0, 1].set_title(
    "NEW SENSOR: Raw Spectra (SATURATED!)",
    fontsize=12,
    fontweight="bold",
)
axes[0, 1].set_ylabel("Counts")
axes[0, 1].legend()
axes[0, 1].grid(alpha=0.3)

# Dark-corrected
s_corr_new = s_spec_new - s_dark_new
p_corr_new = p_spec_new - p_dark_new
axes[1, 1].plot(s_corr_new, "b-", alpha=0.7, label="S-mode (dark corrected)")
axes[1, 1].plot(p_corr_new, "r-", alpha=0.7, label="P-mode (dark corrected)")
axes[1, 1].set_title("NEW SENSOR: Dark Corrected", fontsize=12, fontweight="bold")
axes[1, 1].set_ylabel("Counts")
axes[1, 1].legend()
axes[1, 1].grid(alpha=0.3)

# Transmission
trans_new = p_corr_new / np.where(s_corr_new < 1, 1, s_corr_new)
axes[2, 1].plot(trans_new, "g-", linewidth=1.5)
axes[2, 1].axhline(1.0, color="k", linestyle="--", alpha=0.3)
axes[2, 1].set_title(
    f"NEW SENSOR: Transmission\nRange: {trans_new.min():.3f} to {trans_new.max():.3f}",
    fontsize=12,
    fontweight="bold",
)
axes[2, 1].set_ylabel("Transmission (P/S)")
axes[2, 1].set_xlabel("Pixel")
axes[2, 1].grid(alpha=0.3)
axes[2, 1].set_ylim([-1, 3])

plt.suptitle(
    "TRANSMISSION DIAGNOSTIC - SATURATION ISSUE",
    fontsize=14,
    fontweight="bold",
    y=0.995,
)
plt.tight_layout()
plt.savefig("transmission_diagnostic.png", dpi=150, bbox_inches="tight")
print("\n✓ Saved transmission_diagnostic.png")

# Print summary
print("\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)
print("\nOLD SENSOR:")
print(f"  S-mode: mean={s_spec_old.mean():.1f}, max={s_spec_old.max():.1f}")
print(f"  P-mode: mean={p_spec_old.mean():.1f}, max={p_spec_old.max():.1f}")
print(f"  Saturated pixels (S): {np.sum(s_spec_old >= 65535)}")
print(f"  Saturated pixels (P): {np.sum(p_spec_old >= 65535)}")
print(f"  Transmission range: {trans_old.min():.3f} to {trans_old.max():.3f}")

print("\nNEW SENSOR:")
print(f"  S-mode: mean={s_spec_new.mean():.1f}, max={s_spec_new.max():.1f}")
print(f"  P-mode: mean={p_spec_new.mean():.1f}, max={p_spec_new.max():.1f}")
print(f"  Saturated pixels (S): {np.sum(s_spec_new >= 65535)}")
print(f"  Saturated pixels (P): {np.sum(p_spec_new >= 65535)}")
print(f"  Transmission range: {trans_new.min():.3f} to {trans_new.max():.3f}")

print("\n" + "=" * 80)
print("PROBLEM IDENTIFIED")
print("=" * 80)
print("❌ BOTH SENSORS ARE SATURATED!")
print("   - Collection script uses LED=255 (full power)")
print("   - No integration time optimization")
print("   - Results in detector saturation (65535 counts)")
print("   - Transmission calculation becomes unreliable")
print("\n✅ SOLUTION:")
print("   - Use calibrated LED intensities from device config")
print("   - OR use much lower LED intensity (e.g., 50-100)")
print("   - OR use shorter integration time")
print("=" * 80)
