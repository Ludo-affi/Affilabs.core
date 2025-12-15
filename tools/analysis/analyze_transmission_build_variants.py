"""Analyze raw→transmission build variants to reduce high-frequency noise.

This script keeps the peak-finding method fixed (centroid in nm) and only
varies how we build transmission from raw S/P spectra:
 - Pre-ratio denoise on S/P (Savitzky–Golay, Gaussian, Median, FFT low-pass)
 - Post-ratio denoise on transmission (optional)
 - Compare against current baseline (SG w=51,p=3 on S and P before ratio)

Outputs:
 - Overlay of resonance position time series for all variants
 - Bar charts of P-P and STD per variant (nm)
 - Saved under analysis_results/transmission_build

Usage (Python 3.12):
  python -u analyze_transmission_build_variants.py --state used_current --channel A
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from collect_training_data import OptimalProcessor
from scipy.ndimage import gaussian_filter1d
from scipy.signal import medfilt, savgol_filter

from settings.settings import (
    MAX_WAVELENGTH,
    MIN_WAVELENGTH,
    SPR_PEAK_EXPECTED_MAX,
    SPR_PEAK_EXPECTED_MIN,
)
from utils.usb4000_oceandirect import USB4000OceanDirect

DATA_ROOT = Path("training_data")
DEFAULT_STATE = "used_current"


def find_latest_dataset(state: str, channel: str) -> tuple[Path, Path]:
    state_dir = DATA_ROOT / state
    if not state_dir.exists():
        raise FileNotFoundError(f"No directory found: {state_dir}")

    s_files = sorted(state_dir.glob(f"*_channel_{channel}_s_mode.npz"))
    p_files = sorted(state_dir.glob(f"*_channel_{channel}_p_mode.npz"))
    if not s_files or not p_files:
        raise FileNotFoundError("Could not find matching S/P NPZ files.")

    s_latest = s_files[-1]
    timestamp = s_latest.name.split("_channel_")[0]
    p_latest = state_dir / f"{timestamp}_channel_{channel}_p_mode.npz"
    if not p_latest.exists():
        p_latest = p_files[-1]

    return s_latest, p_latest


def load_wavelengths_masked() -> np.ndarray:
    spec = USB4000OceanDirect()
    if not spec.connect():
        raise RuntimeError(
            "Failed to connect to USB4000 spectrometer to fetch wavelengths",
        )
    wl = np.array(spec.get_wavelengths())
    spec.disconnect()
    mask = (wl >= MIN_WAVELENGTH) & (wl <= MAX_WAVELENGTH)
    return wl[mask]


def rfft_lowpass(x: np.ndarray, cutoff: float = 0.15) -> np.ndarray:
    """Simple real-FFT low-pass filter (normalized cutoff 0-0.5)."""
    if len(x) < 4:
        return x
    coeffs = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x))
    coeffs[freqs > cutoff] = 0
    y = np.fft.irfft(coeffs, n=len(x))
    return y


def causal_moving_average_time(series: np.ndarray, k: int) -> np.ndarray:
    """Causal moving average along time axis for 2D array (time, wavelength).

    out[t] = mean(series[max(0, t-k+1):t+1], axis=0)
    """
    if k is None or k <= 1:
        return series
    n, m = series.shape
    out = np.empty_like(series, dtype=np.float64)
    for t in range(n):
        start = max(t - k + 1, 0)
        out[t] = np.mean(series[start : t + 1], axis=0)
    return out


def apply_spectral_denoise(
    spectrum: np.ndarray,
    kind: str | None,
    params: Mapping[str, int | float] | None,
) -> np.ndarray:
    if not kind or kind == "none":
        return spectrum
    params = {} if params is None else dict(params)
    if kind == "sg":
        w = int(params.get("window", 51))
        p = int(params.get("poly", 3))
        # window must be odd and >= poly+2
        if w % 2 == 0:
            w += 1
        w = max(w, p + 2 + (p + 2) % 2)  # ensure odd and large enough
        return savgol_filter(spectrum, window_length=w, polyorder=p)
    if kind == "gauss":
        sigma = float(params.get("sigma", 2.0))
        return gaussian_filter1d(spectrum, sigma=sigma)
    if kind == "median":
        k = int(params.get("kernel", 5))
        if k % 2 == 0:
            k += 1
        return medfilt(spectrum, kernel_size=k)
    if kind == "fft":
        cutoff = float(params.get("cutoff", 0.15))
        return rfft_lowpass(spectrum, cutoff=cutoff)
    raise ValueError(f"Unknown denoise kind: {kind}")


def build_transmission(
    s_raw: np.ndarray,
    p_raw: np.ndarray,
    s_dark: np.ndarray,
    p_dark: np.ndarray,
    pre_kind: str | None = None,
    pre_params: dict[str, int | float] | None = None,
    post_kind: str | None = None,
    post_params: dict[str, int | float] | None = None,
) -> np.ndarray:
    """Build transmission with optional pre/post denoising.

    - Pre: denoise on dark-corrected S/P prior to ratio
    - Post: denoise on transmission after ratio
    """
    # Dark correction
    s_corr = s_raw - s_dark
    p_corr = p_raw - p_dark

    # Optional pre-ratio denoise on S and P
    if pre_kind and pre_kind != "none":
        s_corr = apply_spectral_denoise(s_corr, pre_kind, pre_params)
        p_corr = apply_spectral_denoise(p_corr, pre_kind, pre_params)

    # Ratio (with safe floor on denominator)
    s_safe = np.where(s_corr < 1, 1, s_corr)
    transmission = p_corr / s_safe

    # Optional post-ratio denoise
    if post_kind and post_kind != "none":
        transmission = apply_spectral_denoise(transmission, post_kind, post_params)

    return transmission


def compute_variant_series(
    s_npz: Path,
    p_npz: Path,
    pre_kind: str | None,
    pre_params: dict[str, int | float] | None,
    post_kind: str | None,
    post_params: dict[str, int | float] | None,
    temporal_pre: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    s_data = np.load(s_npz)
    p_data = np.load(p_npz)
    s_spectra = s_data["spectra"]
    s_dark = s_data["dark"].reshape(-1)
    p_spectra = p_data["spectra"]
    p_dark = p_data["dark"].reshape(-1)
    timestamps = p_data["timestamps"].reshape(-1)

    assert s_spectra.shape == p_spectra.shape

    # Dark correction for entire time series
    s_corr_all = s_spectra - s_dark
    p_corr_all = p_spectra - p_dark

    # Optional causal temporal moving average on S and P before any spectral filtering/ratio
    if temporal_pre and temporal_pre > 1:
        s_corr_all = causal_moving_average_time(s_corr_all, temporal_pre)
        p_corr_all = causal_moving_average_time(p_corr_all, temporal_pre)

    n = s_spectra.shape[0]
    trans_series = np.zeros_like(p_spectra, dtype=np.float64)
    for i in range(n):
        s_corr = s_corr_all[i]
        p_corr = p_corr_all[i]

        # Optional pre-ratio spectral denoise
        if pre_kind and pre_kind != "none":
            s_corr = apply_spectral_denoise(s_corr, pre_kind, pre_params)
            p_corr = apply_spectral_denoise(p_corr, pre_kind, pre_params)

        # Ratio with safe floor on S
        s_safe = np.where(s_corr < 1, 1, s_corr)
        trans = p_corr / s_safe

        # Optional post-ratio spectral denoise
        if post_kind and post_kind != "none":
            trans = apply_spectral_denoise(trans, post_kind, post_params)

        trans_series[i] = trans

    return trans_series, timestamps


def summarize_metrics(x: np.ndarray) -> dict[str, float]:
    return {
        "p2p": float(np.ptp(x)),
        "std": float(np.std(x)),
        "mean": float(np.mean(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def plot_results(
    t: np.ndarray,
    methods: list[str],
    series: dict[str, np.ndarray],
    metrics: dict[str, dict[str, float]],
    state: str,
    channel: str,
) -> Path:
    outdir = Path("analysis_results") / "transmission_build"
    outdir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9))
    ax1 = plt.subplot(2, 1, 1)

    cmap = plt.get_cmap("tab10")
    for idx, m in enumerate(methods):
        ax1.plot(t, series[m], label=m, color=cmap(idx))

    ax1.set_title(f"Transmission Build Variants (Channel {channel}, state: {state})")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Resonance position (nm)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(ncol=3)

    ax2 = plt.subplot(2, 2, 3)
    ax3 = plt.subplot(2, 2, 4)

    labels = methods
    p2p_vals = [metrics[m]["p2p"] for m in methods]
    std_vals = [metrics[m]["std"] for m in methods]

    bars2 = ax2.bar(labels, p2p_vals, color=[cmap(i) for i in range(len(labels))])
    ax2.set_title("Peak-to-Peak (nm)")
    ax2.set_ylabel("nm")
    ax2.grid(axis="y", alpha=0.3)
    for b, v in zip(bars2, p2p_vals, strict=False):
        ax2.text(
            b.get_x() + b.get_width() / 2,
            b.get_height(),
            f"{v:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    bars3 = ax3.bar(labels, std_vals, color=[cmap(i) for i in range(len(labels))])
    ax3.set_title("Standard Deviation (nm)")
    ax3.set_ylabel("nm")
    ax3.grid(axis="y", alpha=0.3)
    for b, v in zip(bars3, std_vals, strict=False):
        ax3.text(
            b.get_x() + b.get_width() / 2,
            b.get_height(),
            f"{v:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    outfile = outdir / f"transmission_build_comparison_{state}_{channel}.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return outfile


def main():
    parser = argparse.ArgumentParser(
        description="Compare raw→transmission build variants (pre/post denoise)",
    )
    parser.add_argument(
        "--state",
        default=DEFAULT_STATE,
        help="Sensor state subfolder under training_data/",
    )
    parser.add_argument("--channel", default="A", help="Channel letter (A-D)")
    parser.add_argument(
        "--enable-sg-sweep",
        action="store_true",
        help="Add Savitzky–Golay pre-denoise sweep variants",
    )
    parser.add_argument(
        "--temporal-pre",
        type=int,
        default=1,
        help="Causal moving average window on S/P before ratio (frames)",
    )
    args = parser.parse_args()

    channel = args.channel.upper()
    s_npz, p_npz = find_latest_dataset(args.state, channel)
    wl = load_wavelengths_masked()

    # nm search bounds
    smin = max(SPR_PEAK_EXPECTED_MIN, float(wl.min()))
    smax = min(SPR_PEAK_EXPECTED_MAX, float(wl.max()))

    # Define variants (labels kept short for plotting)
    variants = {
        # Baseline (matches OptimalProcessor: SG w=51,p=3 pre, no post)
        "pre_sg51p3": ("sg", {"window": 51, "poly": 3}, None, {}),
        # Lighter SG pre
        "pre_sg21p2": ("sg", {"window": 21, "poly": 2}, None, {}),
        # Gaussian pre
        "pre_gauss2": ("gauss", {"sigma": 2.0}, None, {}),
        # Median pre
        "pre_med5": ("median", {"kernel": 5}, None, {}),
        # FFT low-pass pre
        "pre_fft015": ("fft", {"cutoff": 0.15}, None, {}),
        # No pre, post SG (denoise transmission only)
        "post_sg5": (None, {}, "sg", {"window": 5, "poly": 2}),
        # No pre, post FFT
        "post_fft015": (None, {}, "fft", {"cutoff": 0.15}),
        # Hybrid: mild pre + mild post
        "pre_sg21_post_sg5": (
            "sg",
            {"window": 21, "poly": 2},
            "sg",
            {"window": 5, "poly": 2},
        ),
    }

    # Optional SG pre-denoise sweep
    if args.enable_sg_sweep:
        win_candidates = [31, 41, 51, 61]
        poly_candidates = [2, 3]
        for w in win_candidates:
            for p in poly_candidates:
                label = f"pre_sg{w}p{p}"
                if label not in variants:
                    variants[label] = ("sg", {"window": w, "poly": p}, None, {})

    results_series: dict[str, np.ndarray] = {}
    results_metrics: dict[str, dict[str, float]] = {}

    for label, (pre_kind, pre_params, post_kind, post_params) in variants.items():
        trans_series, t = compute_variant_series(
            s_npz,
            p_npz,
            pre_kind,
            pre_params,
            post_kind,
            post_params,
            temporal_pre=args.temporal_pre,
        )

        # Track resonance via centroid (nm), identical across variants
        n = trans_series.shape[0]
        positions = np.zeros(n, dtype=np.float64)
        for i in range(n):
            positions[i] = OptimalProcessor.find_minimum_centroid_nm(
                trans_series[i],
                wl,
                search_min_nm=smin,
                search_max_nm=smax,
            )

        results_series[label] = positions
        results_metrics[label] = summarize_metrics(positions)

    # Console summary
    print("\n=== Transmission Build Variants (nm) ===")
    print("Variants:", ", ".join(variants.keys()))
    for m in variants:
        print(
            f"- {m:18s} P-P: {results_metrics[m]['p2p']:.3f} nm   STD: {results_metrics[m]['std']:.3f} nm   mean: {results_metrics[m]['mean']:.2f} nm",
        )

    # Plot
    outpath = plot_results(
        t,
        list(variants.keys()),
        results_series,
        results_metrics,
        args.state,
        channel,
    )
    print(f"\nSaved comparison plot: {outpath}")


if __name__ == "__main__":
    main()
