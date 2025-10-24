"""
Analyze impact of width/asymmetry on peak estimates and separate real shift vs. width-induced bias.

This tool:
- Loads a base transmission spectrum (wavelengths [nm], transmission [0-1] or [0-100%])
- Synthesizes variants with:
  * true center shift (±Δ nm)
  * symmetric broadening (Gaussian σ in nm)
  * right-side asymmetry (exponential tail with tau [nm] for afterglow-like skew)
- Evaluates multiple peak estimators: small-window parabolic, wide-window centroid,
  physics-aware centroid (right-side taper), left/right edge at fixed depth, and a
  parametric fit (exGaussian dip) to recover the true center (μ) and width parameters.
- Reports bias under width-only vs. true-shift conditions and saves plots + JSON summary.

Usage examples:
  python analyze_width_vs_shift_model.py --input-csv data.csv --shift-nm -0.5 0 0.5 \
      --gauss-sigma 0 0.5 1.0 2.0 --asym-tau 0 1.0 2.0 --center-estimators centroid physics-aware parabolic left-edge

If no input is provided, a synthetic base dip at ~603.3 nm is generated (for demo).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt

try:
    from scipy.ndimage import gaussian_filter1d
    from scipy.optimize import curve_fit
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


# -------------------------------
# Helper dataclasses and methods
# -------------------------------

@dataclass
class PeakEstimates:
    method: str
    estimate_nm: float
    error_nm: float
    extra: Dict[str, float]


def ensure_percent(trans: np.ndarray) -> np.ndarray:
    """Normalize transmission to 0..1 if values look like 0..100."""
    tmin, tmax = float(np.nanmin(trans)), float(np.nanmax(trans))
    if tmax > 1.5:  # assume percent
        return np.clip(trans / 100.0, 0.0, 1.0)
    return np.clip(trans, 0.0, 1.0)


def find_min_index(y: np.ndarray) -> int:
    return int(np.nanargmin(y))


def parabolic_minimum(x: np.ndarray, y: np.ndarray, idx: int) -> float:
    """3-point parabolic interpolation around discrete minimum index."""
    if idx <= 0 or idx >= len(y) - 1:
        return float(x[idx])
    x3 = x[idx-1:idx+2]
    y3 = y[idx-1:idx+2]
    try:
        A = np.vstack([x3**2, x3, np.ones_like(x3)]).T
        a, b, c = np.linalg.lstsq(A, y3, rcond=None)[0]
        if a > 0:
            return float(-b / (2*a))
    except Exception:
        pass
    return float(x[idx])


def centroid_nm(x: np.ndarray, y: np.ndarray, window_nm: float = 100.0,
                right_decay_gamma: Optional[float] = None) -> float:
    """Centroid around the discrete min within ±window_nm/2, with optional right-side decay."""
    imin = find_min_index(y)
    x0 = x[imin]
    half = window_nm / 2.0
    mask = (x >= x0 - half) & (x <= x0 + half)
    xw, yw = x[mask], y[mask]
    if len(xw) < 3:
        return float(x0)
    # Invert for weighting (lower transmission -> higher weight)
    w = np.maximum(yw.max() - yw, 1e-9)
    if right_decay_gamma and right_decay_gamma > 0:
        # Downweight right side exponentially in nm
        decay = np.exp(-np.clip(xw - x0, 0, None) * right_decay_gamma)
        w = w * decay
    num = np.sum(w * xw)
    den = np.sum(w)
    return float(num / den) if den > 0 else float(x0)


def edge_at_fraction(x: np.ndarray, y: np.ndarray, frac: float = 0.5, side: str = 'left') -> float:
    """Find wavelength where transmission crosses baseline - frac * depth on left/right side."""
    # Baseline = max, depth = max - min
    ymin, ymax = np.nanmin(y), np.nanmax(y)
    level = ymax - frac * (ymax - ymin)
    # Find indices around minimum
    i0 = find_min_index(y)
    if side == 'left':
        segment_x, segment_y = x[:i0+1], y[:i0+1]
    else:
        segment_x, segment_y = x[i0:], y[i0:]
    # Find crossing
    idx = np.where(np.diff(np.sign(segment_y - level)) != 0)[0]
    if len(idx) == 0:
        return float(x[i0])
    # Take the crossing closest to the minimum
    j = idx[-1] if side == 'left' else idx[0]
    xa, xb = segment_x[j], segment_x[j+1]
    ya, yb = segment_y[j], segment_y[j+1]
    # Linear interpolation
    if yb != ya:
        t = (level - ya) / (yb - ya)
        return float(xa + t * (xb - xa))
    return float(xa)


def convolve_right_exponential(x: np.ndarray, y: np.ndarray, tau_nm: float) -> np.ndarray:
    """Convolve with a right-sided exponential kernel (afterglow-like skew) in nm domain."""
    if tau_nm <= 0:
        return y
    # Build kernel over x-grid spacing (assume approx uniform)
    dx = float(np.median(np.diff(x)))
    span_nm = 6 * tau_nm
    n_right = max(1, int(np.ceil(span_nm / dx)))
    kx = np.arange(0, (n_right+1)) * dx
    kern = np.exp(-kx / tau_nm)
    kern = kern / np.sum(kern)
    # Causal right-sided convolution
    conv = np.convolve(y, kern, mode='full')[:len(y)]
    return conv


def shift_spectrum(x: np.ndarray, y: np.ndarray, delta_nm: float) -> np.ndarray:
    """Shift spectrum by delta_nm using linear interpolation."""
    return np.interp(x, x - delta_nm, y, left=y[0], right=y[-1])


def gaussian_broaden(x: np.ndarray, y: np.ndarray, sigma_nm: float) -> np.ndarray:
    if sigma_nm <= 0 or not SCIPY_AVAILABLE:
        return y
    dx = float(np.median(np.diff(x)))
    sigma_px = max(0.1, sigma_nm / dx)
    return gaussian_filter1d(y, sigma_px, mode='nearest')


def exgaussian_dip(x, mu, sigma, tau, depth, baseline):
    """ExGaussian dip profile: baseline - depth * exGaussian_pdf normalized to peak 1.

    Uses a numerically-stable formulation. Parameters:
      mu: center [nm]
      sigma: Gaussian width [nm]
      tau: exponential tail [nm] (right-sided)
      depth: dip depth (0..1)
      baseline: top level (≈1)
    """
    # Avoid degenerate params
    sigma = max(1e-6, sigma)
    tau = max(1e-6, tau)
    z = (x - mu) / sigma
    lam = 1.0 / tau
    # exGaussian PDF (unnormalized dip); use numerical helper
    # pdf = lam/2 * exp(lam/2*(2*mu + lam*sigma^2 - 2*x)) * erfc((mu + lam*sigma^2 - x)/(sqrt(2)*sigma))
    try:
        from math import sqrt
        from math import erfc
    except Exception:
        # Fallback: approximate erfc via numpy
        from numpy import erfc  # type: ignore
        from numpy import sqrt  # type: ignore
    arg = (mu + lam * (sigma**2) - x) / (np.sqrt(2.0) * sigma)
    pdf = (lam / 2.0) * np.exp((lam / 2.0) * (2*mu + lam*(sigma**2) - 2*x)) * erfc(arg)
    # Normalize pdf to unit peak to make depth interpretable
    pdf = pdf / (np.max(pdf) + 1e-12)
    return baseline - depth * pdf


def fit_exgaussian_dip(x: np.ndarray, y: np.ndarray, guess_mu: float) -> Tuple[float, Dict[str, float]]:
    """Fit exGaussian dip around the minimum to estimate true center (mu) and width/tail.

    Returns: (mu_est, params dict)
    """
    if not SCIPY_AVAILABLE:
        return float(guess_mu), {"sigma": np.nan, "tau": np.nan, "depth": np.nan, "baseline": np.nan}

    # Window around the min to fit
    half = 60.0
    mask = (x >= guess_mu - half) & (x <= guess_mu + half)
    xn, yn = x[mask], y[mask]
    if len(xn) < 15:
        return float(guess_mu), {"sigma": np.nan, "tau": np.nan, "depth": np.nan, "baseline": np.nan}

    # Initial guesses
    baseline0 = float(np.nanmax(yn))
    depth0 = float(np.clip(baseline0 - np.nanmin(yn), 0.01, 0.9))
    sigma0 = 2.0
    tau0 = 1.0
    p0 = [guess_mu, sigma0, tau0, depth0, baseline0]

    bounds = ([guess_mu - 10.0, 0.2, 0.0, 0.0, 0.5],
              [guess_mu + 10.0, 10.0, 10.0, 1.5, 1.5])
    try:
        popt, _ = curve_fit(exgaussian_dip, xn, yn, p0=p0, bounds=bounds, maxfev=3000)
        mu, sigma, tau, depth, baseline = [float(v) for v in popt]
        return mu, {"sigma": sigma, "tau": tau, "depth": depth, "baseline": baseline}
    except Exception:
        return float(guess_mu), {"sigma": np.nan, "tau": np.nan, "depth": np.nan, "baseline": np.nan}


# -------------------------------
# Core analysis
# -------------------------------

def run_analysis(wave_nm: np.ndarray,
                 trans_in: np.ndarray,
                 shifts_nm: List[float],
                 sigmas_nm: List[float],
                 taus_nm: List[float],
                 estimators: List[str]) -> Dict:
    trans = ensure_percent(trans_in)
    # Denoise lightly for stability (optional)
    if SCIPY_AVAILABLE:
        trans = gaussian_filter1d(trans, 0.5, mode='nearest')

    base_min_idx = find_min_index(trans)
    base_mu = float(wave_nm[base_min_idx])

    results = []

    for dmu in shifts_nm:
        for sigma in sigmas_nm:
            for tau in taus_nm:
                # Build synthetic variant
                y = trans.copy()
                # True shift
                y = shift_spectrum(wave_nm, y, dmu) if abs(dmu) > 0 else y
                # Symmetric broadening
                y = gaussian_broaden(wave_nm, y, sigma)
                # Right-side asymmetry
                y = convolve_right_exponential(wave_nm, y, tau)

                # Re-normalize to 0..1 in case of blur/tail amplitude drift
                y = ensure_percent(y)

                # Ground truth center for this synthetic case
                true_mu = base_mu + dmu

                # Left/right edges for features
                left50 = edge_at_fraction(wave_nm, y, frac=0.5, side='left')
                right50 = edge_at_fraction(wave_nm, y, frac=0.5, side='right')
                width50 = max(0.0, right50 - left50)
                asym50 = max(0.0, right50 - true_mu) - max(0.0, true_mu - left50)

                ests: List[PeakEstimates] = []
                if 'parabolic' in estimators:
                    idx = find_min_index(y)
                    est = parabolic_minimum(wave_nm, y, idx)
                    ests.append(PeakEstimates('parabolic', est, est - true_mu, {}))

                if 'centroid' in estimators:
                    est = centroid_nm(wave_nm, y, window_nm=100.0, right_decay_gamma=None)
                    ests.append(PeakEstimates('centroid100', est, est - true_mu, {}))

                if 'physics-aware' in estimators:
                    est = centroid_nm(wave_nm, y, window_nm=100.0, right_decay_gamma=0.02)
                    ests.append(PeakEstimates('physaware100g002', est, est - true_mu, {}))

                if 'left-edge' in estimators:
                    est = edge_at_fraction(wave_nm, y, frac=0.5, side='left')
                    ests.append(PeakEstimates('left50', est, est - true_mu, {"width50": width50}))

                if 'fit-exgauss' in estimators:
                    # Initialize fit at centroid for stability
                    init = centroid_nm(wave_nm, y, window_nm=20.0)
                    mu_hat, params = fit_exgaussian_dip(wave_nm, y, guess_mu=init)
                    ests.append(PeakEstimates('fit_exgauss', mu_hat, mu_hat - true_mu, params))

                # Simple linear bias correction using 50% width asymmetry
                # est_corr = est_centroid - k * asymmetry; learn k on-the-fly via regression on synthetic grid later if needed
                centroid_est = centroid_nm(wave_nm, y, window_nm=100.0, right_decay_gamma=None)
                k = 0.5  # default slope; can tune by minimizing bias on width-only cases
                est_corr = float(centroid_est - k * asym50)
                ests.append(PeakEstimates('centroid100_biascorr_asym', est_corr, est_corr - true_mu,
                                          {"k": k, "asym50": asym50}))

                results.append({
                    "true_mu": true_mu,
                    "shift_nm": dmu,
                    "sigma_nm": sigma,
                    "tau_nm": tau,
                    "width50_nm": width50,
                    "asym50_nm": asym50,
                    "estimates": [e.__dict__ for e in ests],
                })

    return {
        "base_mu": base_mu,
        "results": results,
    }


def plot_summary(out_dir: Path, wave_nm: np.ndarray, base_trans: np.ndarray, analysis: Dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Example plot: bias vs. sigma for width-only (shift=0) cases
    res = analysis["results"]
    width_only = [r for r in res if abs(r["shift_nm"]) < 1e-9]
    if not width_only:
        width_only = res

    # Collect bias per estimator
    methods = set(e["method"] for r in width_only for e in r["estimates"])
    fig, ax = plt.subplots(figsize=(8, 5))
    for m in sorted(methods):
        xs, ys = [], []
        for r in width_only:
            sigma = r["sigma_nm"]
            # Average bias across tau grid for same sigma
            errs = [e["error_nm"] for e in r["estimates"] if e["method"] == m]
            if not errs:
                continue
            xs.append(sigma)
            ys.append(np.mean(errs))
        if xs:
            ax.plot(xs, ys, marker='o', label=m)
    ax.set_title("Bias vs. Gaussian width (width-only cases)")
    ax.set_xlabel("Gaussian σ [nm]")
    ax.set_ylabel("Mean bias [nm]")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "bias_vs_sigma.png", dpi=150)

    # Base spectrum preview
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.plot(wave_nm, base_trans, lw=1.0)
    ax2.set_title("Base transmission spectrum")
    ax2.set_xlabel("Wavelength [nm]")
    ax2.set_ylabel("Transmission [0..1]")
    ax2.grid(True, alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(out_dir / "base_spectrum.png", dpi=150)


def load_input(input_csv: Optional[str]) -> Tuple[np.ndarray, np.ndarray]:
    if input_csv and Path(input_csv).exists():
        data = np.loadtxt(input_csv, delimiter=",", ndmin=2)
        if data.shape[1] < 2:
            raise ValueError("Input CSV must have at least 2 columns: wavelength_nm, transmission")
        wl = data[:, 0]
        tr = data[:, 1]
        return wl, ensure_percent(tr)

    # Fallback: synthetic spectrum (Gaussian dip + mild right tail)
    wl = np.linspace(580, 720, 1201)
    mu, sigma, depth, baseline = 603.3, 2.0, 0.35, 1.0
    dip = baseline - depth * np.exp(-0.5 * ((wl - mu) / sigma) ** 2)
    dip = convolve_right_exponential(wl, dip, tau_nm=0.8)
    return wl, ensure_percent(dip)


def main():
    parser = argparse.ArgumentParser(description="Width vs. shift modeling and estimator robustness")
    parser.add_argument("--input-csv", type=str, default=None, help="CSV with wavelength,transmission (optional)")
    parser.add_argument("--shift-nm", type=float, nargs="*", default=[0.0, -0.5, 0.5], help="True shift values [nm]")
    parser.add_argument("--gauss-sigma", type=float, nargs="*", default=[0.0, 0.5, 1.0, 2.0], help="Gaussian broadening σ [nm]")
    parser.add_argument("--asym-tau", type=float, nargs="*", default=[0.0, 0.5, 1.0], help="Right-tail exponential τ [nm]")
    parser.add_argument("--center-estimators", type=str, nargs="*",
                        default=["parabolic", "centroid", "physics-aware", "left-edge", "fit-exgauss"],
                        help="Estimators to evaluate")
    parser.add_argument("--output-dir", type=str, default="analysis_results/width_vs_shift_model",
                        help="Directory to save plots and JSON summary")

    args = parser.parse_args()

    wave_nm, trans = load_input(args.input_csv)

    analysis = run_analysis(wave_nm, trans,
                            shifts_nm=list(args.shift_nm),
                            sigmas_nm=list(args.gauss_sigma),
                            taus_nm=list(args.asym_tau),
                            estimators=list(args.center_estimators))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON summary
    with open(out_dir / "summary.json", "w") as f:
        json.dump(analysis, f, indent=2)

    # Save plots
    plot_summary(out_dir, wave_nm, trans, analysis)

    print(f"\n✓ Analysis complete. Results saved to: {out_dir}")


if __name__ == "__main__":
    main()
