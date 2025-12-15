"""Demo: Dynamic Savitzky–Golay filter equalizes spectral noise across channels.

Generates synthetic SPR-like transmission spectra with different noise levels
and applies the dynamic SG filter used in utils.spr_data_processor to achieve
similar smoothness (std of second derivative) across all channels.

Run (PowerShell):
    python -u tools/analysis/demo_dynamic_sg.py
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from scipy.signal import savgol_filter
except ImportError:
    raise SystemExit("scipy is required for this demo (pip install scipy)")

import os
import sys

# Add project root to sys.path for imports when running as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.spr_data_processor import SPRDataProcessor


@dataclass
class SyntheticChannel:
    name: str
    spectrum: np.ndarray


def make_spr_like_spectrum(
    n: int = 1024,
    noise_sigma: float = 0.5,
    seed: int | None = None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)

    # Build a simple SPR-like dip: 100 - A * exp(-(x-x0)^2 / (2*sigma^2)) + baseline slope
    x = np.linspace(0, 1, n)
    x0 = 0.6
    sigma = 0.03
    A = 60.0
    baseline = 2.0 * (x - 0.5)
    clean = 100.0 - A * np.exp(-0.5 * ((x - x0) / sigma) ** 2) + baseline

    # Add Gaussian noise
    noisy = clean + rng.normal(0.0, noise_sigma, size=n)
    return noisy.astype(np.float64)


def second_deriv_std(y: np.ndarray) -> float:
    if len(y) < 5:
        return float("nan")
    d2 = np.diff(y, n=2)
    return float(np.std(d2))


def main() -> None:
    # Synthetic channels with different noise levels
    channels: list[SyntheticChannel] = [
        SyntheticChannel("A", make_spr_like_spectrum(1024, noise_sigma=0.4, seed=1)),
        SyntheticChannel("B", make_spr_like_spectrum(1024, noise_sigma=0.8, seed=2)),
        SyntheticChannel("C", make_spr_like_spectrum(1024, noise_sigma=1.2, seed=3)),
        SyntheticChannel("D", make_spr_like_spectrum(1024, noise_sigma=0.6, seed=4)),
    ]

    # Build a dummy processor with placeholder wavelength and Fourier weights
    n = len(channels[0].spectrum)
    wave = np.linspace(600.0, 800.0, n)
    weights = SPRDataProcessor.calculate_fourier_weights(wave_data_length=n)
    proc = SPRDataProcessor(wave_data=wave, fourier_weights=weights, med_filt_win=5)

    # Auto-target: use median smoothness from a quick scan (pass None)
    print("\n=== Dynamic SG (auto-target median) ===")
    for ch in channels:
        pre = second_deriv_std(ch.spectrum)
        smoothed, w, p = proc._apply_dynamic_sg_filter(
            ch.spectrum,
            target_smoothness=None,
        )
        post = second_deriv_std(smoothed)
        print(
            f"Ch {ch.name}: pre σ(d²)={pre:8.5f}  →  post σ(d²)={post:8.5f}  (w={w}, p={p})",
        )

    # Fixed global target: pick the median of pre-channel smoothness to unify
    target = np.median([second_deriv_std(ch.spectrum) for ch in channels])
    print(f"\n=== Dynamic SG (fixed global target = {target:.5f}) ===")
    for ch in channels:
        pre = second_deriv_std(ch.spectrum)
        smoothed, w, p = proc._apply_dynamic_sg_filter(
            ch.spectrum,
            target_smoothness=float(target),
        )
        post = second_deriv_std(smoothed)
        print(
            f"Ch {ch.name}: pre σ(d²)={pre:8.5f}  →  post σ(d²)={post:8.5f}  (w={w}, p={p})",
        )


if __name__ == "__main__":
    main()
