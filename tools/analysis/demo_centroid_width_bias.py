"""Demo: Centroid vs Width-Bias-Corrected Centroid on a synthetic SPR-like spectrum.

This script generates an asymmetric transmission dip, then computes:
  - Plain centroid (within CENTROID_WINDOW_NM)
  - Width-bias-corrected centroid (centroid - K * asymmetry)

It prints both estimates and their difference. If matplotlib is available,
it will also plot the spectrum and mark both estimates.

Run (PowerShell):
    python -u tools/analysis/demo_centroid_width_bias.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

# Add project root to sys.path for imports when running as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from settings.settings import (
    CENTROID_WINDOW_NM,
)
from utils.spr_data_processor import SPRDataProcessor


def make_asymmetric_spr_spectrum(
    n: int = 2048,
    seed: int | None = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a synthetic asymmetric SPR-like transmission spectrum.

    Returns:
        wavelengths (nm), transmission (%), both as float64 arrays

    """
    rng = np.random.default_rng(seed)

    wl = np.linspace(600.0, 800.0, n)
    # Base Gaussian dip
    true_mu = 650.0
    sigma = 4.5  # nm
    depth = 55.0  # % drop at center
    baseline = np.linspace(-1.0, +1.0, n)
    base = 100.0 - depth * np.exp(-0.5 * ((wl - true_mu) / sigma) ** 2) + baseline

    # Add asymmetry: right tail heavier (exponential taper on right side)
    right_tail = 6.0 * np.exp(-np.clip(wl - true_mu, 0, None) / 8.0)
    asym = base + right_tail

    # Add small noise
    noisy = asym + rng.normal(0.0, 0.15, size=n)

    return wl.astype(np.float64), noisy.astype(np.float64)


def main() -> None:
    # Create synthetic spectrum
    wl, spec = make_asymmetric_spr_spectrum()

    # Build processor with dummy Fourier weights (not used by centroid helper)
    weights = SPRDataProcessor.calculate_fourier_weights(wave_data_length=len(wl))
    proc = SPRDataProcessor(wave_data=wl, fourier_weights=weights, med_filt_win=5)

    # Plain centroid (no width-bias)
    mu_centroid = proc._estimate_centroid_with_optional_width_bias(
        spec,
        apply_width_bias=False,
    )
    # Width-bias-corrected centroid
    mu_bias = proc._estimate_centroid_with_optional_width_bias(
        spec,
        apply_width_bias=True,
    )

    print("\n=== Centroid vs Width-Bias-Corrected Centroid ===")
    print(f"Centroid (no bias)      : {mu_centroid:.3f} nm")
    print(f"Width-bias corrected    : {mu_bias:.3f} nm")
    if not np.isnan(mu_centroid) and not np.isnan(mu_bias):
        print(f"Correction (bias delta) : {mu_bias - mu_centroid:+.3f} nm")

    # ------------------------------------------------------------------
    # Two-window mean bias correction demo (matches prior 80nm/8nm test)
    # ------------------------------------------------------------------
    def centroid_in_window(
        trans: np.ndarray,
        wl_nm: np.ndarray,
        center_nm: float | None,
        window_nm: float,
    ) -> float:
        """Compute weighted centroid in an nm-window around a center.

        If center_nm is None, center at the discrete minimum of trans.
        Weights are inverted transmission (dip → higher weight), without decay.
        """
        if trans.size != wl_nm.size or trans.size < 5:
            return float("nan")
        if center_nm is None:
            i0 = int(np.argmin(trans))
            center_nm = float(wl_nm[i0])
        half = float(window_nm) / 2.0
        mask = (wl_nm >= center_nm - half) & (wl_nm <= center_nm + half)
        if not np.any(mask):
            return float(center_nm)
        w = wl_nm[mask]
        t = trans[mask]
        inv = float(np.max(t)) - t
        s = float(np.sum(inv))
        if s <= 0:
            return float(center_nm)
        return float(np.sum(w * inv) / s)

    # Generate multiple spectra to estimate the mean bias
    N = 50
    centroids_80_list: list[float] = []
    baselines_8_list: list[float] = []
    for k in range(N):
        wl_k, spec_k = make_asymmetric_spr_spectrum(seed=100 + k)
        # Center each centroid at its discrete min, use different window sizes
        c80 = centroid_in_window(spec_k, wl_k, center_nm=None, window_nm=80.0)
        b8 = centroid_in_window(spec_k, wl_k, center_nm=None, window_nm=8.0)
        centroids_80_list.append(c80)
        baselines_8_list.append(b8)
    centroids_80 = np.array(centroids_80_list, dtype=float)
    baselines_8 = np.array(baselines_8_list, dtype=float)

    # Mean bias offset between the 80nm centroid and 8nm baseline
    bias_offset = float(np.mean(centroids_80) - np.mean(baselines_8))
    corrected_80 = centroids_80 - bias_offset

    print("\n=== Two-window mean bias correction (80 nm vs 8 nm) ===")
    print(f"Samples: {N}")
    print(
        f"Mean(centroid 80nm)      : {np.mean(centroids_80):.3f} nm  ± {np.std(centroids_80):.3f}",
    )
    print(
        f"Mean(baseline 8nm)       : {np.mean(baselines_8):.3f} nm  ± {np.std(baselines_8):.3f}",
    )
    print(f"Bias offset (80nm-8nm)   : {bias_offset:+.3f} nm")
    print(
        f"Mean(corrected 80nm)     : {np.mean(corrected_80):.3f} nm  ± {np.std(corrected_80):.3f}",
    )

    # Optional: plot if matplotlib is available
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(9, 4))
        plt.plot(wl, spec, "k-", lw=1.0, alpha=0.9, label="Transmission (%)")
        if not np.isnan(mu_centroid):
            plt.axvline(mu_centroid, color="#1f77b4", lw=1.8, ls="--", label="Centroid")
        if not np.isnan(mu_bias):
            plt.axvline(
                mu_bias,
                color="#d62728",
                lw=1.8,
                ls="--",
                label="Width-bias corrected",
            )
        # Mark centroid window
        half = float(CENTROID_WINDOW_NM) / 2.0
        if not np.isnan(mu_centroid):
            plt.axvspan(
                mu_centroid - half,
                mu_centroid + half,
                color="#1f77b4",
                alpha=0.08,
                label=f"Centroid window ±{half:.1f} nm",
            )
        plt.title("Centroid vs Width-Bias-Corrected Centroid (synthetic)")
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Transmission (%)")
        plt.legend(loc="best")
        plt.tight_layout()
        plt.show()
    except Exception:
        # No plotting available; that's fine for a quick textual demo
        pass


if __name__ == "__main__":
    main()
