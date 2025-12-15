"""Analyze S/P cleanliness and transmission for a 2-minute dataset.

- Loads latest S and P NPZ pair from training_data/<state> (default: used_current)
- Denoises S and P using Savitzky–Golay (OptimalProcessor convention)
- Computes transmission via OptimalProcessor pipeline
- Tracks resonance position over time using centroid and pseudo-Voigt fit
- Saves a figure showing:
  (1) Example S/P raw vs dark-corrected vs denoised
  (2) Example transmission with fitted center markers
  (3) Time series of peak positions for both methods with metrics

Usage:
  python -u tools/analysis/analyze_sp_transmission_cleanliness.py --channel A --state used_current
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

from settings.settings import (
    MAX_WAVELENGTH,
    MIN_WAVELENGTH,
    SPR_PEAK_EXPECTED_MAX,
    SPR_PEAK_EXPECTED_MIN,
)

# Robust OptimalProcessor import (top-level or scripts path)
try:
    from collect_training_data import OptimalProcessor  # type: ignore
except Exception:
    from scripts.collection.collect_training_data import (
        OptimalProcessor,  # type: ignore
    )

DATA_ROOT = Path("training_data")
DEFAULT_STATE = "used_current"


def find_latest_dataset(state: str, channel: str) -> tuple[Path, Path, Path | None]:
    state_dir = DATA_ROOT / state
    s_files = sorted(state_dir.glob(f"*_channel_{channel}_s_mode.npz"))
    p_files = sorted(state_dir.glob(f"*_channel_{channel}_p_mode.npz"))
    if not s_files or not p_files:
        raise FileNotFoundError(
            f"No S/P NPZ found for state={state}, channel={channel}",
        )
    s_latest = s_files[-1]
    timestamp = s_latest.name.split("_channel_")[0]
    p_latest = state_dir / f"{timestamp}_channel_{channel}_p_mode.npz"
    if not p_latest.exists():
        p_latest = p_files[-1]
        timestamp = p_latest.name.split("_channel_")[0]
        s_latest = state_dir / f"{timestamp}_channel_{channel}_s_mode.npz"
    meta = state_dir / f"{timestamp}_channel_{channel}_metadata.json"
    return s_latest, p_latest, meta if meta.exists() else None


def load_wavelengths_masked(target_length: int | None = None) -> np.ndarray:
    # Try device wavelengths; fall back to a matching grid
    try:
        from utils.usb4000_oceandirect import USB4000OceanDirect

        spec = USB4000OceanDirect()
        if spec.connect():
            got = spec.get_wavelengths()
            spec.disconnect()
            if got is not None:
                wl = np.array(got)
            else:
                wl = spec._get_fallback_wavelengths()
        else:
            wl = spec._get_fallback_wavelengths()
    except Exception:
        # Device libs not available or device not present
        wl = np.linspace(
            float(MIN_WAVELENGTH),
            float(MAX_WAVELENGTH),
            target_length or 2048,
        )

    mask = (wl >= MIN_WAVELENGTH) & (wl <= MAX_WAVELENGTH)
    wl_masked = wl[mask]
    if target_length is not None and wl_masked.size != int(target_length):
        return np.linspace(
            float(MIN_WAVELENGTH),
            float(MAX_WAVELENGTH),
            int(target_length),
        )
    return wl_masked


def compute_transmission_series(
    s_npz: Path,
    p_npz: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    s_data = np.load(s_npz)
    p_data = np.load(p_npz)
    s_spectra = s_data["spectra"]
    p_spectra = p_data["spectra"]
    s_dark = s_data["dark"].reshape(-1)
    p_dark = p_data["dark"].reshape(-1)
    t = p_data["timestamps"].reshape(-1)
    assert s_spectra.shape == p_spectra.shape
    n = s_spectra.shape[0]
    trans_series = np.zeros_like(p_spectra, dtype=np.float64)
    for i in range(n):
        trans_series[i] = OptimalProcessor.process_transmission(
            s_spectra[i],
            p_spectra[i],
            s_dark,
            p_dark,
        )
    return s_spectra, p_spectra, trans_series, s_dark, p_dark, t


def _pseudo_voigt(x, mu, fwhm, eta, A, y0):
    z = (x - mu) / max(1e-12, fwhm)
    G = np.exp(-4.0 * np.log(2.0) * (z**2))
    L = 1.0 / (1.0 + 4.0 * (z**2))
    v = eta * L + (1.0 - eta) * G
    return y0 + A * v


def pvoigt_fit_mu(
    wl: np.ndarray,
    y: np.ndarray,
    search_min: float,
    search_max: float,
) -> float:
    mask = (wl >= search_min) & (wl <= search_max)
    if np.count_nonzero(mask) < 7:
        return float(wl[np.argmin(y)])
    w = wl[mask]
    spec = y[mask]
    inv = spec.max() - spec
    mu0 = float(w[np.argmax(inv)])
    p0 = [
        mu0,
        8.0,
        0.5,
        float(inv.max()) if inv.max() > 0 else 0.1,
        float(np.median(inv)),
    ]
    bounds = ([search_min, 0.5, 0.0, 0.0, 0.0], [search_max, 50.0, 1.0, np.inf, np.inf])
    try:
        popt, _ = curve_fit(_pseudo_voigt, w, inv, p0=p0, bounds=bounds, maxfev=2000)
        mu = float(popt[0])
        if mu < w[0] or mu > w[-1]:
            return mu0
        return mu
    except Exception:
        return mu0


def summarize_metrics(x: np.ndarray) -> dict[str, float]:
    return {
        "p2p": float(np.ptp(x)),
        "std": float(np.std(x)),
        "mean": float(np.mean(x)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--channel", default="A")
    ap.add_argument("--search_min", type=float, default=float(SPR_PEAK_EXPECTED_MIN))
    ap.add_argument("--search_max", type=float, default=float(SPR_PEAK_EXPECTED_MAX))
    args = ap.parse_args()

    ch = args.channel.upper()
    s_npz, p_npz, meta = find_latest_dataset(args.state, ch)

    s_raw, p_raw, trans, s_dark, p_dark, t = compute_transmission_series(s_npz, p_npz)
    wl = load_wavelengths_masked(target_length=trans.shape[1])

    # Choose an example index near middle
    i0 = int(len(t) // 2)

    # Denoise S/P for display (dark-corrected then SG)
    s_corr = s_raw[i0] - s_dark
    p_corr = p_raw[i0] - p_dark
    s_denoised = savgol_filter(s_corr, 51, 3) if s_corr.size >= 51 else s_corr
    p_denoised = savgol_filter(p_corr, 51, 3) if p_corr.size >= 51 else p_corr

    # Transmission example
    y = trans[i0]

    # Peak positions over time
    smin = max(args.search_min, float(wl.min()))
    smax = min(args.search_max, float(wl.max()))

    centroid_series = np.zeros(len(t), dtype=float)
    pvoigt_series = np.zeros(len(t), dtype=float)

    for i in range(len(t)):
        spectrum = trans[i]
        centroid_series[i] = OptimalProcessor.find_minimum_centroid_nm(
            spectrum,
            wl,
            search_min_nm=smin,
            search_max_nm=smax,
            window_nm=8.0,
            right_decay_gamma=0.02,
        )
        pvoigt_series[i] = pvoigt_fit_mu(wl, spectrum, smin, smax)

    cmet = summarize_metrics(centroid_series)
    pmet = summarize_metrics(pvoigt_series)

    # Plot
    outdir = Path("analysis_results") / "cleanliness"
    outdir.mkdir(parents=True, exist_ok=True)
    timestamp = s_npz.name.split("_channel_")[0]
    outfile = outdir / f"cleanliness_{timestamp}_{ch}.png"

    fig = plt.figure(figsize=(16, 10))
    ax1 = plt.subplot(3, 1, 1)
    ax2 = plt.subplot(3, 1, 2)
    ax3 = plt.subplot(3, 1, 3)

    # Panel 1: S/P example
    ax1.plot(wl, s_corr, color="#888", alpha=0.7, label="S raw-dark")
    ax1.plot(wl, s_denoised, color="#0044cc", lw=1.2, label="S denoised")
    ax1.plot(wl, p_corr, color="#999", alpha=0.7, label="P raw-dark")
    ax1.plot(wl, p_denoised, color="#cc4400", lw=1.2, label="P denoised")
    ax1.set_title(f"S/P dark-corrected vs denoised (example frame {i0})")
    ax1.set_xlabel("Wavelength (nm)")
    ax1.set_ylabel("Intensity (a.u.)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(ncol=2)

    # Panel 2: Transmission example with fits
    ax2.plot(wl, y, color="#222", lw=1.0, label="Transmission")
    c0 = OptimalProcessor.find_minimum_centroid_nm(
        y,
        wl,
        search_min_nm=smin,
        search_max_nm=smax,
        window_nm=8.0,
        right_decay_gamma=0.02,
    )
    p0 = pvoigt_fit_mu(wl, y, smin, smax)
    ax2.axvline(c0, color="#1f77b4", ls="--", lw=1.2, label=f"Centroid {c0:.2f} nm")
    ax2.axvline(p0, color="#d62728", ls=":", lw=1.2, label=f"pVoigt {p0:.2f} nm")
    ax2.set_xlim(smin, smax)
    ax2.set_title("Transmission example with fitted centers")
    ax2.set_xlabel("Wavelength (nm)")
    ax2.set_ylabel("Transmission (P/S)")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # Panel 3: Time series of positions
    t0 = t - float(t[0])
    ax3.plot(
        t0,
        centroid_series,
        color="#1f77b4",
        label=f"Centroid  P2P={cmet['p2p']:.3f} nm, STD={cmet['std']:.3f} nm",
    )
    ax3.plot(
        t0,
        pvoigt_series,
        color="#d62728",
        label=f"pVoigt    P2P={pmet['p2p']:.3f} nm, STD={pmet['std']:.3f} nm",
    )
    ax3.set_title(f"Resonance position over time (state={args.state}, channel={ch})")
    ax3.set_xlabel("Time (s)")
    ax3.set_ylabel("Resonance (nm)")
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print("\n=== Cleanliness Summary ===")
    print(f"Dataset: {timestamp} channel {ch} (state: {args.state})")
    print(
        f"Frames: {len(t)} | Pixels: {trans.shape[1]} | wl range: {wl.min():.1f}-{wl.max():.1f} nm | search: {smin:.1f}-{smax:.1f} nm",
    )
    print(
        f"Centroid: P-P {cmet['p2p']:.3f} nm, STD {cmet['std']:.3f} nm, mean {cmet['mean']:.2f} nm",
    )
    print(
        f"pVoigt:   P-P {pmet['p2p']:.3f} nm, STD {pmet['std']:.3f} nm, mean {pmet['mean']:.2f} nm",
    )
    print(f"Saved figure: {outfile}")


if __name__ == "__main__":
    main()
