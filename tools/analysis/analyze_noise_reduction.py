"""
Noise reduction analysis on the latest training_data dataset.

Loads the most recent S-mode and P-mode NPZ files for a channel, computes
transmission time series, tracks resonance position in nm, and compares
raw vs smoothed (median + moving average) sensorgram noise.

Usage (Python 3.12 venv):
  .\.venv312\Scripts\python.exe -u analyze_noise_reduction.py --channel A
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
from typing import Tuple

from settings import MIN_WAVELENGTH, MAX_WAVELENGTH
from utils.usb4000_oceandirect import USB4000OceanDirect

# Reuse spectral processing from the collector
from collect_training_data import OptimalProcessor

DATA_ROOT = Path("training_data")
DEFAULT_STATE = "used_current"


def find_latest_dataset(state: str, channel: str) -> Tuple[Path, Path]:
    """Return paths to latest S-mode and P-mode NPZ files for a channel."""
    state_dir = DATA_ROOT / state
    if not state_dir.exists():
        raise FileNotFoundError(f"No directory found: {state_dir}")

    # Find all matching files with both s_mode and p_mode for the same timestamp
    s_files = sorted(state_dir.glob(f"*_channel_{channel}_s_mode.npz"))
    p_files = sorted(state_dir.glob(f"*_channel_{channel}_p_mode.npz"))

    if not s_files or not p_files:
        raise FileNotFoundError("Could not find matching S/P NPZ files.")

    # Use the most recent pair by timestamp (filenames start with timestamp)
    s_latest = s_files[-1]
    # Derive corresponding p filename by replacing suffix
    timestamp = s_latest.name.split("_channel_")[0]
    p_latest = state_dir / f"{timestamp}_channel_{channel}_p_mode.npz"
    if not p_latest.exists():
        # fallback to the latest p file
        p_latest = p_files[-1]

    return s_latest, p_latest


def load_wavelengths_masked() -> np.ndarray:
    """Connect to spectrometer to retrieve masked wavelength vector used in collection."""
    spec = USB4000OceanDirect()
    if not spec.connect():
        raise RuntimeError("Failed to connect to USB4000 spectrometer to fetch wavelengths")
    wl = np.array(spec.get_wavelengths())
    spec.disconnect()
    mask = (wl >= MIN_WAVELENGTH) & (wl <= MAX_WAVELENGTH)
    return wl[mask]


def median_filter(x: np.ndarray, window: int) -> np.ndarray:
    """Simple median filter."""
    if window <= 1:
        return x.copy()
    pad = window // 2
    xpad = np.pad(x, (pad, pad), mode="edge")
    out = np.empty_like(x)
    for i in range(len(x)):
        out[i] = np.median(xpad[i:i+window])
    return out


def moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """Centered moving average using edge-padded convolution (no zero-edge bias)."""
    if window <= 1:
        return x.copy()
    pad = window // 2
    xpad = np.pad(x, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / window
    # 'valid' on padded yields same length as original
    return np.convolve(xpad, kernel, mode="valid")


def compute_positions_nm(s_npz: Path, p_npz: Path, wavelengths_nm: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute transmission and resonance position (nm) over time."""
    s_data = np.load(s_npz)
    p_data = np.load(p_npz)

    s_spectra = s_data["spectra"]
    s_dark = s_data["dark"].reshape(-1)
    p_spectra = p_data["spectra"]
    p_dark = p_data["dark"].reshape(-1)
    timestamps = p_data["timestamps"].reshape(-1)

    assert s_spectra.shape == p_spectra.shape, "S and P arrays must be same shape"

    n = s_spectra.shape[0]
    positions_nm = np.zeros(n, dtype=np.float64)

    for i in range(n):
        trans = OptimalProcessor.process_transmission(
            s_spectra[i], p_spectra[i], s_dark, p_dark
        )
        positions_nm[i] = OptimalProcessor.find_minimum_centroid_nm(
            trans, wavelengths_nm
        )

    return positions_nm, timestamps, wavelengths_nm


def kalman_filter_positions(
    z: np.ndarray,
    t: np.ndarray,
    q_pos: float = 0.01,
    q_vel: float = 0.1,
    r_meas: float = 0.05,
) -> np.ndarray:
    """Constant-velocity 1D Kalman filter for position measurements.

    z: measured positions (nm)
    t: timestamps (s)
    q_pos: process noise std for position per second (nm/s)
    q_vel: process noise std for velocity per second (nm/s^2)
    r_meas: measurement noise std (nm)
    """
    n = len(z)
    x = np.zeros((2,))  # [pos, vel]
    x[0] = z[0]
    x[1] = 0.0
    P = np.diag([1.0, 1.0]) * (r_meas**2) * 100.0  # large initial uncertainty

    out = np.zeros(n)
    out[0] = z[0]

    for i in range(1, n):
        dt = float(max(t[i] - t[i-1], 1e-6))

        # State transition and process noise
        F = np.array([[1.0, dt], [0.0, 1.0]])
        G = np.array([[0.5*dt*dt, 0.0], [dt, 0.0]])  # split noise into pos/vel channels
        Q = np.diag([q_pos**2, q_vel**2])

        # Predict
        x = F @ x
        P = F @ P @ F.T + G @ Q @ G.T

        # Update
        H = np.array([[1.0, 0.0]])
        R = np.array([[r_meas**2]])
        y = np.array([[z[i]]]) - H @ x
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        x = x + (K @ y).reshape(2,)
        P = (np.eye(2) - K @ H) @ P

        out[i] = x[0]

    return out


def analyze(state: str, channel: str, med_win: int, avg_win: int, use_kf: bool, kf_q: float, kf_r: float) -> None:
    s_npz, p_npz = find_latest_dataset(state, channel)
    wl = load_wavelengths_masked()

    pos_nm, t, _ = compute_positions_nm(s_npz, p_npz, wl)

    # Raw stats
    p2p_raw = float(np.ptp(pos_nm))
    std_raw = float(np.std(pos_nm))

    # Smoothed: median then moving average
    pos_med = median_filter(pos_nm, med_win)
    pos_smooth = moving_average(pos_med, avg_win)

    p2p_smooth = float(np.ptp(pos_smooth))
    std_smooth = float(np.std(pos_smooth))

    # Kalman filter (high temporal resolution)
    kf_series = None
    p2p_kf = None
    std_kf = None
    if use_kf:
        # Estimate measurement noise if not provided (fallback): use raw STD
        r_eff = kf_r if kf_r > 0 else max(std_raw, 1e-3)
        kf_series = kalman_filter_positions(pos_nm, t, q_pos=kf_q, q_vel=kf_q*5.0, r_meas=r_eff)
        p2p_kf = float(np.ptp(kf_series))
        std_kf = float(np.std(kf_series))

    print("\n=== Peak Monitoring Noise (nm) ===")
    print(f"Raw P-P: {p2p_raw:.3f} nm; STD: {std_raw:.3f} nm")
    print(f"Smoothed P-P: {p2p_smooth:.3f} nm; STD: {std_smooth:.3f} nm")
    if use_kf and kf_series is not None:
        print(f"Kalman P-P: {p2p_kf:.3f} nm; STD: {std_kf:.3f} nm  (q={kf_q}, r={r_eff:.3f})")

    # Visualization
    fig = plt.figure(figsize=(14, 8))
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(t, pos_nm, 'b-', alpha=0.5, label='Raw (nm)')
    ax1.plot(t, pos_smooth, 'r-', linewidth=2, label=f'Smoothed (med{med_win}+avg{avg_win})')
    if use_kf and kf_series is not None:
        ax1.plot(t, kf_series, 'k-', linewidth=1.5, label=f'Kalman (q={kf_q}, r={r_eff:.2f})')
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Resonance Position (nm)')
    ax1.set_title('Sensorgram - Raw vs Smoothed')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2 = plt.subplot(2, 2, 3)
    ax2.hist(pos_nm, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
    ax2.set_title(f'Raw Distribution\nP-P={p2p_raw:.2f} nm; STD={std_raw:.2f} nm')

    ax3 = plt.subplot(2, 2, 4)
    ax3.hist(pos_smooth, bins=50, color='salmon', alpha=0.7, edgecolor='black')
    ax3.set_title(f'Smoothed Distribution\nP-P={p2p_smooth:.2f} nm; STD={std_smooth:.2f} nm')

    plt.tight_layout()
    outdir = Path('analysis_results') / 'noise_reduction'
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"noise_reduction_{state}_{channel}_med{med_win}_avg{avg_win}.png"
    plt.savefig(outfile, dpi=150, bbox_inches='tight')
    print(f"\nSaved visualization: {outfile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze and reduce peak monitoring noise")
    parser.add_argument('--state', default=DEFAULT_STATE, help='Sensor state subfolder under training_data/')
    parser.add_argument('--channel', default='A', help='Channel letter (A-D)')
    parser.add_argument('--med-win', type=int, default=5, help='Median filter window (odd)')
    parser.add_argument('--avg-win', type=int, default=11, help='Moving average window (odd)')
    parser.add_argument('--kalman', action='store_true', help='Include constant-velocity Kalman filter (high temporal resolution)')
    parser.add_argument('--kf-q', type=float, default=0.05, help='Process noise std (nm/s) base for position; velocity uses 5x')
    parser.add_argument('--kf-r', type=float, default=0.0, help='Measurement noise std (nm); 0 to auto-estimate from data')
    args = parser.parse_args()

    analyze(args.state, args.channel.upper(), args.med_win, args.avg_win, args.kalman, args.kf_q, args.kf_r)
