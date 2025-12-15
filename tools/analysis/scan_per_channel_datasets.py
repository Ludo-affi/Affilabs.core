"""Scan per-channel datasets and compute resonance stability metrics.

This script pairs S/P NPZ files in training_data/used_current by timestamp
and channel, builds transmission with the same settings as the main pipeline
(dark correction, optional dynamic SG on transmission), and computes the
resonance wavelength using the current width-bias centroid path in
utils.spr_data_processor.SPRDataProcessor.

It prints, for each run, the mean/std/p2p of the resonance (nm) and highlights
the best candidates, so we can locate the dataset that achieved ~0.003 nm std
and ~0.011 nm p-p around ~01:00.
"""

from __future__ import annotations

import json

# Ensure repository root is on sys.path for absolute imports
import sys
from pathlib import Path
from pathlib import Path as _Path

import numpy as np

sys.path.append(str(_Path(__file__).resolve().parents[2]))

from settings.settings import (
    SPR_PEAK_EXPECTED_MAX,
    SPR_PEAK_EXPECTED_MIN,
)
from utils.spr_data_processor import SPRDataProcessor

DATA_DIR = Path("training_data") / "used_current"


def load_npz_safe(path: Path) -> dict[str, np.ndarray]:
    data = np.load(path)
    return {k: data[k] for k in data.files}


def pair_runs_by_timestamp_channel(
    base: Path,
) -> list[tuple[str, str, Path, Path, Path | None]]:
    """Return list of (timestamp, channel, s_npz, p_npz, metadata_json)."""
    runs: dict[tuple[str, str], dict[str, Path]] = {}
    for npz in base.glob("*_channel_*_s_mode.npz"):
        name = npz.name
        try:
            timestamp = name.split("_channel_")[0]
            channel = name.split("_channel_")[1].split("_")[0]
        except Exception:
            continue
        runs.setdefault((timestamp, channel), {})["s"] = npz

    for npz in base.glob("*_channel_*_p_mode.npz"):
        name = npz.name
        try:
            timestamp = name.split("_channel_")[0]
            channel = name.split("_channel_")[1].split("_")[0]
        except Exception:
            continue
        runs.setdefault((timestamp, channel), {})["p"] = npz

    out: list[tuple[str, str, Path, Path, Path | None]] = []
    for (ts, ch), files in sorted(runs.items()):
        s_npz = files.get("s")
        p_npz = files.get("p")
        if not s_npz or not p_npz:
            continue
        meta = base / f"{ts}_channel_{ch}_metadata.json"
        out.append((ts, ch, s_npz, p_npz, meta if meta.exists() else None))
    return out


def build_processor(wavelengths: np.ndarray) -> SPRDataProcessor:
    # Compute Fourier weights with helper to avoid mismatch
    fourier_weights = SPRDataProcessor.calculate_fourier_weights(len(wavelengths))
    return SPRDataProcessor(
        wave_data=wavelengths,
        fourier_weights=fourier_weights,
        med_filt_win=5,
    )


def compute_resonance_series(
    proc: SPRDataProcessor,
    wl: np.ndarray,
    s_npz: Path,
    p_npz: Path,
) -> tuple[np.ndarray, np.ndarray]:
    s = load_npz_safe(s_npz)
    p = load_npz_safe(p_npz)

    # Infer keys robustly
    # Expect spectra: (N, M), dark: (M,), timestamps: (N,) or times
    s_spectra = s.get("spectra")
    p_spectra = p.get("spectra")
    if s_spectra is None or p_spectra is None:
        raise ValueError(f"Missing 'spectra' arrays in {s_npz.name} or {p_npz.name}")

    # Dark may be shaped (M,) or (1, M)
    s_dark = s.get("dark")
    p_dark = p.get("dark")
    if s_dark is None or p_dark is None:
        # Fall back to zeros if dark not present
        s_dark = np.zeros(s_spectra.shape[1], dtype=np.float64)
        p_dark = np.zeros(p_spectra.shape[1], dtype=np.float64)
    s_dark = np.asarray(s_dark).reshape(-1)
    p_dark = np.asarray(p_dark).reshape(-1)

    # Timestamps: prefer 'timestamps', else 'times', else arange
    t = p.get("timestamps")
    if t is None:
        t = p.get("times")
    if t is None:
        t = np.arange(p_spectra.shape[0], dtype=np.float64)
    t = np.asarray(t).reshape(-1)

    if s_spectra.shape != p_spectra.shape:
        raise ValueError(f"S/P shape mismatch: {s_spectra.shape} vs {p_spectra.shape}")

    n = s_spectra.shape[0]
    positions = np.zeros(n, dtype=np.float64)

    # Pre-subtract each mode's own dark; then let calculate_transmission do dynamic SG
    for i in range(n):
        s_corr = s_spectra[i] - s_dark
        p_corr = p_spectra[i] - p_dark
        # Calculate transmission percentage with denoise=True to apply dynamic SG
        trans = proc.calculate_transmission(
            p_corr,
            s_corr,
            dark_noise=None,
            denoise=True,
        )
        # Restrict to expected range indices
        pos_nm = proc.find_resonance_wavelength(trans, channel="a")
        positions[i] = float(pos_nm) if np.isfinite(pos_nm) else np.nan

    return positions, t


def summarize(x: np.ndarray) -> dict[str, float]:
    x_clean = x[np.isfinite(x)]
    if x_clean.size == 0:
        return {"mean": np.nan, "std": np.nan, "p2p": np.nan, "n": 0}
    return {
        "mean": float(np.mean(x_clean)),
        "std": float(np.std(x_clean)),
        "p2p": float(np.ptp(x_clean)),
        "n": int(x_clean.size),
    }


def main():
    pairs = pair_runs_by_timestamp_channel(DATA_DIR)
    if not pairs:
        print(f"No paired S/P runs found in {DATA_DIR}")
        return

    print("Scanning per-channel runs in training_data/used_current ...\n")
    results: list[tuple[str, str, dict[str, float], float | None]] = []

    for ts, ch, s_npz, p_npz, meta in pairs:
        # Load wavelengths from NPZ if present; otherwise skip to next
        # Try S first, then P
        wl = None
        for npz in (s_npz, p_npz):
            try:
                d = np.load(npz)
                if "wavelengths" in d.files:
                    wl = np.array(d["wavelengths"])  # full spectrometer wavelengths
                    break
            except Exception:
                pass

        if wl is None:
            # As last resort, try to infer from spectra length via linear nm grid within expected range
            # This is a fallback; ideally NPZ includes wavelengths
            try:
                d_s = np.load(s_npz)
                m = int(d_s["spectra"].shape[1])
            except Exception:
                print(f"Skipping {ts} ch {ch}: unable to infer wavelengths")
                continue
            wl = np.linspace(
                SPR_PEAK_EXPECTED_MIN - 40.0,
                SPR_PEAK_EXPECTED_MAX + 40.0,
                m,
            )

        # If NPZ wavelengths contain full range, mask to expected sensor range
        mask = (wl >= (SPR_PEAK_EXPECTED_MIN - 40.0)) & (
            wl <= (SPR_PEAK_EXPECTED_MAX + 40.0)
        )
        wl_masked = wl[mask] if np.any(mask) else wl

        proc = build_processor(wavelengths=wl_masked)
        try:
            positions, t = compute_resonance_series(proc, wl_masked, s_npz, p_npz)
            stats = summarize(positions)
            bias_applied = None
            if meta is not None:
                try:
                    m = json.loads(meta.read_text())
                    bias_applied = m.get("processing_params", {}).get(
                        "bias_offset_applied_nm",
                    )
                except Exception:
                    bias_applied = None
            results.append((ts, ch, stats, bias_applied))
            print(
                f"{ts}  ch {ch}  n={stats['n']:3d}  mean={stats['mean']:.3f} nm  std={stats['std']*1000:.2f} pm  p-p={stats['p2p']*1000:.2f} pm"
                + (
                    f"  (bias +{bias_applied:.3f} nm)"
                    if bias_applied is not None
                    else ""
                ),
            )
        except Exception as e:
            print(f"{ts}  ch {ch}  ERROR: {e}")

    # Rank by std then p2p
    ranked = sorted(
        results,
        key=lambda r: (
            np.inf if np.isnan(r[2]["std"]) else r[2]["std"],
            np.inf if np.isnan(r[2]["p2p"]) else r[2]["p2p"],
        ),
    )
    print("\nTop candidates by lowest std:")
    for ts, ch, stats, bias in ranked[:5]:
        print(
            f"- {ts} ch {ch}  std={stats['std']*1000:.2f} pm  p-p={stats['p2p']*1000:.2f} pm  mean={stats['mean']:.3f} nm",
        )

    # Highlight runs near 01:00 specifically
    near_1am = [r for r in results if r[0].split("_")[1].startswith("01")]
    if near_1am:
        print("\nRuns near ~01:00:")
        for ts, ch, stats, _ in near_1am:
            print(
                f"- {ts} ch {ch}  std={stats['std']*1000:.2f} pm  p-p={stats['p2p']*1000:.2f} pm  mean={stats['mean']:.3f} nm",
            )


if __name__ == "__main__":
    main()
