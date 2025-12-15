"""Centroid window sweep analysis.

Compares the stability of the nm-based centroid method vs window size.
Keeps the transmission building identical (OptimalProcessor pipeline), and
only varies the centroid window width (in nm). Also evaluates point-based
windows by converting ±N points to nm using the wavelength spacing.

Outputs:
- Overlay of resonance position time series for all windows
- Bar charts of P-P and STD per window (nm)
- Saved under analysis_results/centroid_window

Usage (Python 3.12):
  python -u analyze_centroid_window_sweep.py --state used_current --channel A
  python -u analyze_centroid_window_sweep.py --state used_current --channel A --include-points
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from collect_training_data import OptimalProcessor

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


def summarize_metrics(x: np.ndarray) -> dict[str, float]:
    return {
        "p2p": float(np.ptp(x)),
        "std": float(np.std(x)),
        "mean": float(np.mean(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def find_centroid_nm_with_window(
    transmission: np.ndarray,
    wavelengths_nm: np.ndarray,
    search_min_nm: float,
    search_max_nm: float,
    window_nm: float,
    detrend: bool = False,
    left_half_nm: float | None = None,
    right_half_nm: float | None = None,
    right_decay_gamma: float | None = None,
) -> float:
    """Find centroid within a window around the minimum, with optional local detrend.

    detrend=True: fit a first-order polynomial to the window region and subtract it
    before computing inverse-intensity weights, reducing baseline slope bias.
    """
    # Build nm-based search mask
    search_mask = (wavelengths_nm >= search_min_nm) & (wavelengths_nm <= search_max_nm)
    if not np.any(search_mask):
        search_mask = np.ones_like(wavelengths_nm, dtype=bool)

    trans_search = transmission[search_mask]
    wl_search = wavelengths_nm[search_mask]

    # Argmin in nm region
    min_idx_rel = int(np.argmin(trans_search))
    min_wl = float(wl_search[min_idx_rel])

    # Window around min
    # Build (possibly asymmetric) window
    if left_half_nm is None or right_half_nm is None:
        half = float(window_nm) / 2.0
        left_nm = half
        right_nm = half
    else:
        left_nm = float(left_half_nm)
        right_nm = float(right_half_nm)
    window_mask = (wl_search >= (min_wl - left_nm)) & (wl_search <= (min_wl + right_nm))
    w_window = wl_search[window_mask]
    t_window = trans_search[window_mask]

    if len(w_window) < 3:
        return min_wl

    if detrend:
        # Fit linear trend and subtract
        coeffs = np.polyfit(w_window, t_window, 1)
        baseline = np.polyval(coeffs, w_window)
        t_proc = t_window - baseline
    else:
        t_proc = t_window

    # Invert to convert dip into peak weights and ensure nonnegative weights
    t_max = float(np.max(t_proc))
    inv = t_max - t_proc
    # Optional right-side downweighting (monotone decay to the right of min)
    if right_decay_gamma and right_decay_gamma > 0:
        # delta > 0 on the right of the minimum
        delta = w_window - min_wl
        taper = np.exp(-right_decay_gamma * np.maximum(0.0, delta))
        inv = inv * taper
    inv = np.where(inv > 0, inv, 0.0)
    inv_sum = float(np.sum(inv))
    if inv_sum <= 0:
        return min_wl

    centroid_nm = float(np.sum(w_window * inv) / inv_sum)
    return centroid_nm


def plot_results(
    t: np.ndarray,
    methods: list[str],
    series: dict[str, np.ndarray],
    metrics: dict[str, dict[str, float]],
    state: str,
    channel: str,
) -> Path:
    outdir = Path("analysis_results") / "centroid_window"
    outdir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9))
    ax1 = plt.subplot(2, 1, 1)

    cmap = plt.get_cmap("tab10")
    for idx, m in enumerate(methods):
        ax1.plot(t, series[m], label=m, color=cmap(idx % 10))

    ax1.set_title(f"Centroid Window Sweep (Channel {channel}, state: {state})")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Resonance position (nm)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(ncol=3)

    ax2 = plt.subplot(2, 2, 3)
    ax3 = plt.subplot(2, 2, 4)

    labels = methods
    p2p_vals = [metrics[m]["p2p"] for m in methods]
    std_vals = [metrics[m]["std"] for m in methods]

    bars2 = ax2.bar(labels, p2p_vals, color=[cmap(i % 10) for i in range(len(labels))])
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

    bars3 = ax3.bar(labels, std_vals, color=[cmap(i % 10) for i in range(len(labels))])
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
    outfile = outdir / f"centroid_window_comparison_{state}_{channel}.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return outfile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare centroid window widths in nm and point-equivalents, with optional local detrend",
    )
    parser.add_argument(
        "--state",
        default=DEFAULT_STATE,
        help="Sensor state subfolder under training_data/",
    )
    parser.add_argument("--channel", default="A", help="Channel letter (A-D)")
    parser.add_argument(
        "--include-points",
        action="store_true",
        help="Include point-based windows (±50/±100/±250) converted to nm",
    )
    parser.add_argument(
        "--include-detrend",
        action="store_true",
        help="Also compute a detrended centroid for each window size",
    )
    parser.add_argument(
        "--include-asymmetric",
        action="store_true",
        help="Include asymmetric window variants and right-side decay tapers",
    )
    parser.add_argument(
        "--baseline-label",
        default="nm_8",
        help="Label to use as mean baseline for optional bias correction (e.g., 'nm_8')",
    )
    parser.add_argument(
        "--include-biascorr",
        action="store_true",
        help="Add bias-corrected variants aligned to the baseline label mean",
    )
    args = parser.parse_args()

    channel = args.channel.upper()
    s_npz, p_npz = find_latest_dataset(args.state, channel)
    wl = load_wavelengths_masked()

    # nm search bounds
    smin = max(SPR_PEAK_EXPECTED_MIN, float(wl.min()))
    smax = min(SPR_PEAK_EXPECTED_MAX, float(wl.max()))

    # Transmission series via OptimalProcessor baseline
    s_data = np.load(s_npz)
    p_data = np.load(p_npz)
    s_spectra = s_data["spectra"]
    s_dark = s_data["dark"].reshape(-1)
    p_spectra = p_data["spectra"]
    p_dark = p_data["dark"].reshape(-1)
    timestamps = p_data["timestamps"].reshape(-1)

    assert s_spectra.shape == p_spectra.shape
    n = s_spectra.shape[0]

    # Build transmission once, reuse across window variants
    trans_series = np.zeros_like(p_spectra, dtype=np.float64)
    for i in range(n):
        trans_series[i] = OptimalProcessor.process_transmission(
            s_spectra[i],
            p_spectra[i],
            s_dark,
            p_dark,
        )

    # Define nm window variants (total width)
    nm_windows = [2.0, 4.0, 6.0, 8.0, 10.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0, 150.0]
    variants: dict[str, float] = {f"nm_{int(w)}": w for w in nm_windows}

    # Optionally add point-based windows converted to nm
    if args.include_points:
        # Use median spacing to be robust to any small non-uniformities
        d_lambda = float(np.median(np.diff(wl)))
        for pts in (50, 100, 250):
            wnm = 2.0 * pts * d_lambda
            label = f"pts_{pts}_({wnm:.1f}nm)"
            variants[label] = wnm

    results_series: dict[str, np.ndarray] = {}
    results_metrics: dict[str, dict[str, float]] = {}

    for label, window_nm in variants.items():
        # Baseline centroid
        positions = np.zeros(n, dtype=np.float64)
        for i in range(n):
            positions[i] = find_centroid_nm_with_window(
                trans_series[i],
                wl,
                smin,
                smax,
                float(window_nm),
                detrend=False,
            )
        results_series[label] = positions
        results_metrics[label] = summarize_metrics(positions)

        # Detrended centroid (optional)
        if args.include_detrend:
            dlabel = f"{label}_detrend"
            positions_d = np.zeros(n, dtype=np.float64)
            for i in range(n):
                positions_d[i] = find_centroid_nm_with_window(
                    trans_series[i],
                    wl,
                    smin,
                    smax,
                    float(window_nm),
                    detrend=True,
                )
            results_series[dlabel] = positions_d
            results_metrics[dlabel] = summarize_metrics(positions_d)

    # Asymmetric variants: left/right half-width and right-side exponential decay
    if args.include_asymmetric:
        asym_specs = [
            ("asym_lr80_20", 80.0, 20.0, None),
            ("asym_lr60_20", 60.0, 20.0, None),
            ("asym_lr50_10", 50.0, 10.0, None),
            ("asym_100_decay002", None, None, 0.02),
            ("asym_100_decay005", None, None, 0.05),
            ("asym_60_decay005", None, None, 0.05),
        ]
        for name, lnm, rnm, gamma in asym_specs:
            positions = np.zeros(n, dtype=np.float64)
            for i in range(n):
                if lnm is not None and rnm is not None:
                    # Asymmetric fixed half-widths around min (total window varies)
                    positions[i] = find_centroid_nm_with_window(
                        trans_series[i],
                        wl,
                        smin,
                        smax,
                        window_nm=max(lnm + rnm, 1.0),
                        detrend=False,
                        left_half_nm=lnm,
                        right_half_nm=rnm,
                        right_decay_gamma=None,
                    )
                else:
                    # Symmetric 100 nm (or 60 nm) total window with right-side decay
                    total = 100.0 if "100" in name else 60.0
                    positions[i] = find_centroid_nm_with_window(
                        trans_series[i],
                        wl,
                        smin,
                        smax,
                        window_nm=total,
                        detrend=False,
                        left_half_nm=None,
                        right_half_nm=None,
                        right_decay_gamma=gamma,
                    )
            results_series[name] = positions
            results_metrics[name] = summarize_metrics(positions)

    # Optional bias correction vs chosen baseline (align means)
    if args.include_biascorr and args.baseline_label in results_series:
        base = results_series[args.baseline_label]
        base_mean = float(np.mean(base))
        to_add: dict[str, np.ndarray] = {}
        for lbl, arr in results_series.items():
            if lbl == args.baseline_label:
                continue
            offset = float(np.mean(arr) - base_mean)
            corrected = arr - offset
            to_add[f"{lbl}_biascorr"] = corrected
        # merge
        results_series.update(to_add)
        for lbl, arr in to_add.items():
            results_metrics[lbl] = summarize_metrics(arr)

    # Console summary
    print("\n=== Centroid Window Sweep (nm) ===")
    ordered = list(results_series.keys())
    print("Windows:", ", ".join(ordered))
    for m in ordered:
        print(
            f"- {m:18s} P-P: {results_metrics[m]['p2p']:.3f} nm   STD: {results_metrics[m]['std']:.3f} nm   mean: {results_metrics[m]['mean']:.2f} nm",
        )

    # Plot
    outpath = plot_results(
        timestamps,
        ordered,
        results_series,
        results_metrics,
        args.state,
        channel,
    )
    print(f"\nSaved comparison plot: {outpath}")


if __name__ == "__main__":
    main()
