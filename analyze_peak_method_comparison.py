"""
Compare peak-finding methods on the latest training_data dataset.

This script keeps the processing pipeline identical and only changes the
peak-finding method applied per spectrum. It computes the resonance position
time series (in nm) for each method, then plots an overlay and compares
peak-to-peak (P-P) variation and standard deviation (STD).

Included methods (from existing codebase):
 - direct: simple argmin within expected nm range
 - centroid: OptimalProcessor weighted centroid in nm
 - parabolic: 3-point parabolic interpolation near minimum (nm)
 - num_deriv: Fourier-based numerical derivative zero-crossing (old software)
 - enhanced: FFT + polynomial + derivative (no temporal smoothing here)

Usage (Python 3.12 venv):
    python -u analyze_peak_method_comparison.py --channel A
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import UnivariateSpline
from scipy.optimize import curve_fit

from settings.settings import MIN_WAVELENGTH, MAX_WAVELENGTH, SPR_PEAK_EXPECTED_MIN, SPR_PEAK_EXPECTED_MAX
from utils.usb4000_oceandirect import USB4000OceanDirect
from collect_training_data import OptimalProcessor
from utils.enhanced_peak_tracking import find_resonance_wavelength_enhanced
from utils.numerical_derivative_peak import find_peak_numerical_derivative


DATA_ROOT = Path("training_data")
DEFAULT_STATE = "used_current"


def find_latest_dataset(state: str, channel: str) -> Tuple[Path, Path]:
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
        raise RuntimeError("Failed to connect to USB4000 spectrometer to fetch wavelengths")
    wl = np.array(spec.get_wavelengths())
    spec.disconnect()
    mask = (wl >= MIN_WAVELENGTH) & (wl <= MAX_WAVELENGTH)
    return wl[mask]


def compute_transmission_series(s_npz: Path, p_npz: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    s_data = np.load(s_npz)
    p_data = np.load(p_npz)

    s_spectra = s_data["spectra"]
    s_dark = s_data["dark"].reshape(-1)
    p_spectra = p_data["spectra"]
    p_dark = p_data["dark"].reshape(-1)
    timestamps = p_data["timestamps"].reshape(-1)

    assert s_spectra.shape == p_spectra.shape, "S and P arrays must be same shape"

    n = s_spectra.shape[0]
    trans_series = np.zeros_like(p_spectra, dtype=np.float64)
    for i in range(n):
        trans_series[i] = OptimalProcessor.process_transmission(
            s_spectra[i], p_spectra[i], s_dark, p_dark
        )

    return trans_series, timestamps, s_dark, p_dark


def _find_peak_spline(
    wavelengths_nm: np.ndarray,
    spectrum: np.ndarray,
    search_range: Tuple[float, float],
    smooth_factor: float = 0.001,
) -> float:
    """Cubic smoothing spline + derivative root inside range.

    Picks the derivative root that minimizes the spline value (deepest dip).
    """
    mask = (wavelengths_nm >= search_range[0]) & (wavelengths_nm <= search_range[1])
    wl = wavelengths_nm[mask]
    spec = spectrum[mask]
    if len(wl) < 5:
        return float(wavelengths_nm[np.argmin(spectrum)])

    # Small smoothing: proportional to number of points
    s_val = max(0.0, smooth_factor * len(wl))
    try:
        spl = UnivariateSpline(wl, spec, s=s_val)
        d1 = spl.derivative()
        roots = d1.roots()
        if len(roots) == 0:
            return float(wl[np.argmin(spec)])
        # pick root within bounds that minimizes spline value
        roots = roots[(roots >= wl[0]) & (roots <= wl[-1])]
        if len(roots) == 0:
            return float(wl[np.argmin(spec)])
        vals = spl(roots)
        return float(roots[np.argmin(vals)])
    except Exception:
        return float(wl[np.argmin(spec)])


def _pseudo_voigt(x, mu, fwhm, eta, A, y0):
    """Pseudo-Voigt profile with height A and baseline y0.

    Uses FWHM parameterization for both Gaussian and Lorentzian parts.
    G(x) = exp(-4 ln 2 * ((x-mu)^2 / fwhm^2))
    L(x) = 1 / (1 + 4 * ((x-mu)^2 / fwhm^2))
    v = eta * L + (1-eta) * G
    y = y0 + A * v
    """
    z = (x - mu) / max(1e-12, fwhm)
    G = np.exp(-4.0 * np.log(2.0) * (z**2))
    L = 1.0 / (1.0 + 4.0 * (z**2))
    v = eta * L + (1.0 - eta) * G
    return y0 + A * v


def _find_peak_pvoigt(
    wavelengths_nm: np.ndarray,
    spectrum: np.ndarray,
    search_range: Tuple[float, float],
) -> float:
    """Fit pseudo-Voigt to inverted dip in a narrow window; return center mu."""
    mask = (wavelengths_nm >= search_range[0]) & (wavelengths_nm <= search_range[1])
    wl = wavelengths_nm[mask]
    spec = spectrum[mask]
    if len(wl) < 7:
        return float(wavelengths_nm[np.argmin(spectrum)])

    # Invert dip to positive peak-like for fitting stability
    inv = (spec.max() - spec)

    # Initial guesses
    mu0 = float(wl[np.argmax(inv)])
    fwhm0 = 8.0  # nm, conservative
    eta0 = 0.5
    A0 = float(inv.max()) if inv.max() > 0 else 0.1
    y00 = float(np.median(inv))

    p0 = [mu0, fwhm0, eta0, A0, y00]
    bounds = ([search_range[0], 0.5, 0.0, 0.0, 0.0],
              [search_range[1], 50.0, 1.0, np.inf, np.inf])

    try:
        popt, _ = curve_fit(_pseudo_voigt, wl, inv, p0=p0, bounds=bounds, maxfev=2000)
        mu = float(popt[0])
        # sanity clamp
        if mu < wl[0] or mu > wl[-1]:
            return float(wl[np.argmax(inv)])
        return mu
    except Exception:
        return float(wl[np.argmax(inv)])


def peak_positions_by_method(
    trans_series: np.ndarray,
    wavelengths_nm: np.ndarray,
    method: str,
    search_min: float,
    search_max: float,
) -> np.ndarray:
    n = trans_series.shape[0]
    pos = np.zeros(n, dtype=np.float64)
    rng = (search_min, search_max)

    for i in range(n):
        spectrum = trans_series[i]

        if method == "direct":
            mask = (wavelengths_nm >= rng[0]) & (wavelengths_nm <= rng[1])
            region = spectrum[mask]
            wl_region = wavelengths_nm[mask]
            pos[i] = wl_region[np.argmin(region)] if len(wl_region) else np.nan

        elif method == "centroid":
            pos[i] = OptimalProcessor.find_minimum_centroid_nm(spectrum, wavelengths_nm, search_min_nm=rng[0], search_max_nm=rng[1])

        elif method == "parabolic":
            peak_nm, _diag = find_resonance_wavelength_enhanced(
                spectrum, wavelengths_nm, search_range=rng, method="parabolic"
            )
            pos[i] = float(peak_nm)

        elif method == "num_deriv":
            pos[i] = find_peak_numerical_derivative(wavelengths_nm, spectrum, search_range=rng)

        elif method == "enhanced":
            # Note: Uses internal FFT+polynomial, but no temporal smoothing here
            peak_nm, _diag = find_resonance_wavelength_enhanced(
                spectrum, wavelengths_nm, search_range=rng, method="enhanced"
            )
            pos[i] = float(peak_nm)

        elif method == "spline":
            pos[i] = _find_peak_spline(wavelengths_nm, spectrum, rng)

        elif method == "pvoigt":
            pos[i] = _find_peak_pvoigt(wavelengths_nm, spectrum, rng)

        else:
            raise ValueError(f"Unknown method: {method}")

    return pos


def summarize_metrics(x: np.ndarray) -> Dict[str, float]:
    return {
        "p2p": float(np.ptp(x)),
        "std": float(np.std(x)),
        "mean": float(np.mean(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def plot_comparison(t: np.ndarray, methods: List[str], series: Dict[str, np.ndarray], metrics: Dict[str, Dict[str, float]], state: str, channel: str) -> Path:
    outdir = Path("analysis_results") / "peak_methods"
    outdir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9))
    ax1 = plt.subplot(2, 1, 1)

    cmap = plt.get_cmap('tab10')
    for idx, m in enumerate(methods):
        ax1.plot(t, series[m], label=f"{m}", color=cmap(idx))

    ax1.set_title(f"Peak Methods Comparison (Channel {channel}, state: {state})")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Resonance position (nm)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(ncol=3)

    # Bar charts: P-P and STD
    ax2 = plt.subplot(2, 2, 3)
    ax3 = plt.subplot(2, 2, 4)

    labels = methods
    p2p_vals = [metrics[m]["p2p"] for m in methods]
    std_vals = [metrics[m]["std"] for m in methods]

    bars2 = ax2.bar(labels, p2p_vals, color=[cmap(i) for i in range(len(labels))])
    ax2.set_title("Peak-to-Peak (nm)")
    ax2.set_ylabel("nm")
    ax2.grid(axis='y', alpha=0.3)
    for b, v in zip(bars2, p2p_vals):
        ax2.text(b.get_x() + b.get_width()/2, b.get_height(), f"{v:.2f}", ha='center', va='bottom', fontsize=9)

    bars3 = ax3.bar(labels, std_vals, color=[cmap(i) for i in range(len(labels))])
    ax3.set_title("Standard Deviation (nm)")
    ax3.set_ylabel("nm")
    ax3.grid(axis='y', alpha=0.3)
    for b, v in zip(bars3, std_vals):
        ax3.text(b.get_x() + b.get_width()/2, b.get_height(), f"{v:.2f}", ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    outfile = outdir / f"peak_methods_comparison_{state}_{channel}.png"
    plt.savefig(outfile, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return outfile


def main():
    parser = argparse.ArgumentParser(description="Compare peak-finding methods on the same dataset")
    parser.add_argument('--state', default=DEFAULT_STATE, help='Sensor state subfolder under training_data/')
    parser.add_argument('--channel', default='A', help='Channel letter (A-D)')
    parser.add_argument('--methods', nargs='*', default=["direct", "centroid", "parabolic", "num_deriv", "enhanced", "spline", "pvoigt"],
                        help='Methods to compare (subset of: direct, centroid, parabolic, num_deriv, enhanced)')
    args = parser.parse_args()

    channel = args.channel.upper()
    s_npz, p_npz = find_latest_dataset(args.state, channel)
    wl = load_wavelengths_masked()

    trans_series, t, _sd, _pd = compute_transmission_series(s_npz, p_npz)

    # Use expected SPR range intersected with measured wavelengths
    smin = max(SPR_PEAK_EXPECTED_MIN, float(wl.min()))
    smax = min(SPR_PEAK_EXPECTED_MAX, float(wl.max()))

    results: Dict[str, np.ndarray] = {}
    metrics: Dict[str, Dict[str, float]] = {}

    for m in args.methods:
        pos = peak_positions_by_method(trans_series, wl, m, smin, smax)
        results[m] = pos
        metrics[m] = summarize_metrics(pos)

    # Console summary
    print("\n=== Peak Method Comparison (nm) ===")
    print(f"Methods: {', '.join(args.methods)}")
    for m in args.methods:
        print(f"- {m:10s}  P-P: {metrics[m]['p2p']:.3f} nm   STD: {metrics[m]['std']:.3f} nm   mean: {metrics[m]['mean']:.2f} nm")

    # Plot
    outpath = plot_comparison(t, args.methods, results, metrics, args.state, channel)
    print(f"\nSaved comparison plot: {outpath}")


if __name__ == "__main__":
    main()
