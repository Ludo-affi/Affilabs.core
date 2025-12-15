"""Enhanced Spectral Data Collection Tool for ML Training

Collects S-mode and P-mode spectral data with:
- Real-time optimal processing (dark → denoise S&P → transmission)
- Live quality metrics display
- Interactive sensor labeling
- Structured training data output

Usage:
    python collect_training_data.py --device "demo P4SPR 2.0" --label used_current
    python collect_training_data.py --device "demo P4SPR 2.0" --label new_sealed --sensor-id "BATCH-001"
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

from settings import (
    MAX_WAVELENGTH,
    MIN_WAVELENGTH,
    SPR_PEAK_EXPECTED_MAX,
    SPR_PEAK_EXPECTED_MIN,
)

# Hardware imports
from utils.controller import PicoP4SPR
from utils.device_configuration import DeviceConfiguration
from utils.usb4000_oceandirect import USB4000OceanDirect

# Configuration
SAVGOL_WINDOW = 51
SAVGOL_POLYORDER = 3
# nm-based search window for SPR minimum (aligned with main app)
SEARCH_NM_MIN = SPR_PEAK_EXPECTED_MIN
SEARCH_NM_MAX = SPR_PEAK_EXPECTED_MAX
CENTROID_WINDOW_NM = 4.0  # total window around minimum for centroid calculation (nm)
SPECTRA_PER_MODE = 480  # 2 minutes @ 4 Hz
TARGET_RATE = 4.0  # Hz

# Sensor state options
SENSOR_STATES = {
    "new_sealed": "Factory sealed, never opened",
    "new_unsealed": "Opened but unused",
    "used_good": "Normal use, working well",
    "used_current": "Current sensor in use",
    "used_recycled": "Reused cartridge, not fresh",
    "contaminated": "Visible contamination",
    "degraded": "Old, expired, or damaged",
}


class OptimalProcessor:
    """Optimal SPR spectral processing pipeline."""

    @staticmethod
    def denoise_spectrum(spectrum: np.ndarray) -> np.ndarray:
        """Apply Savitzky-Golay filter."""
        return savgol_filter(spectrum, SAVGOL_WINDOW, SAVGOL_POLYORDER)

    @staticmethod
    def process_transmission(
        s_raw: np.ndarray,
        p_raw: np.ndarray,
        s_dark: np.ndarray,
        p_dark: np.ndarray,
    ) -> np.ndarray:
        """Process S and P mode spectra to transmission.
        Pipeline: dark correction → denoise S&P → transmission calculation
        """
        # Dark correction
        s_corr = s_raw - s_dark
        p_corr = p_raw - p_dark

        # Denoise S and P separately
        s_clean = OptimalProcessor.denoise_spectrum(s_corr)
        p_clean = OptimalProcessor.denoise_spectrum(p_corr)

        # Calculate transmission
        s_safe = np.where(s_clean < 1, 1, s_clean)
        transmission = p_clean / s_safe

        return transmission

    @staticmethod
    def find_minimum_centroid_nm(
        transmission: np.ndarray,
        wavelengths_nm: np.ndarray,
        search_min_nm: float = SEARCH_NM_MIN,
        search_max_nm: float = SEARCH_NM_MAX,
        window_nm: float = CENTROID_WINDOW_NM,
        right_decay_gamma: float | None = None,
    ) -> float:
        """Find minimum wavelength using weighted centroid within an nm-based window.

        If right_decay_gamma is provided (>0), apply exponential downweighting on the
        right side of the minimum to reflect LED spectrum asymmetry:
            weights = (max(t_window) - t_window) * exp(-gamma * max(0, λ - λ_min))
        """
        # Build nm-based search mask within provided wavelengths
        search_mask = (wavelengths_nm >= search_min_nm) & (
            wavelengths_nm <= search_max_nm
        )
        if not np.any(search_mask):
            # Fallback to full range if expected range not within masked wavelengths
            search_mask = np.ones_like(wavelengths_nm, dtype=bool)

        trans_search = transmission[search_mask]
        wl_search = wavelengths_nm[search_mask]

        # Argmin in nm region
        min_idx_rel = int(np.argmin(trans_search))
        min_wl = float(wl_search[min_idx_rel])

        # Build centroid window around min wavelength (symmetric total width)
        half = float(window_nm) / 2.0
        window_mask = (wl_search >= (min_wl - half)) & (wl_search <= (min_wl + half))
        w_window = wl_search[window_mask]
        t_window = trans_search[window_mask]

        # Invert to convert dip into peak weights
        t_max = float(np.max(t_window))
        inv = t_max - t_window
        # Optional right-side decay to reduce influence of high-λ tail
        if right_decay_gamma is not None and right_decay_gamma > 0:
            delta = w_window - min_wl
            taper = np.exp(-float(right_decay_gamma) * np.maximum(0.0, delta))
            inv = inv * taper
        inv_sum = np.sum(inv)
        if inv_sum <= 0:
            # Degenerate case: return min_wl directly
            return min_wl

        centroid_nm = float(np.sum(w_window * inv) / inv_sum)
        return centroid_nm

    @staticmethod
    def find_extremum_centroid_nm(
        transmission: np.ndarray,
        wavelengths_nm: np.ndarray,
        search_min_nm: float = SEARCH_NM_MIN,
        search_max_nm: float = SEARCH_NM_MAX,
        window_nm: float = CENTROID_WINDOW_NM,
        right_decay_gamma: float | None = None,
        mode: str = "min",
    ) -> float:
        """Generalized centroid around an extremum (min or max) within an nm window.

        mode:
          - 'min': centroid around transmission minimum (default)
          - 'max': centroid around transmission maximum
        """
        # Build nm-based search mask
        search_mask = (wavelengths_nm >= search_min_nm) & (
            wavelengths_nm <= search_max_nm
        )
        if not np.any(search_mask):
            search_mask = np.ones_like(wavelengths_nm, dtype=bool)

        trans_search = transmission[search_mask]
        wl_search = wavelengths_nm[search_mask]

        if mode == "max":
            idx_rel = int(np.argmax(trans_search))
            center_wl = float(wl_search[idx_rel])
        else:
            idx_rel = int(np.argmin(trans_search))
            center_wl = float(wl_search[idx_rel])

        # Centroid window around chosen extremum
        half = float(window_nm) / 2.0
        window_mask = (wl_search >= (center_wl - half)) & (
            wl_search <= (center_wl + half)
        )
        w_window = wl_search[window_mask]
        t_window = trans_search[window_mask]

        if mode == "max":
            # Weights higher near the maximum value
            t_min = float(np.min(t_window))
            weights = t_window - t_min
        else:
            # Weights higher near the minimum value
            t_max = float(np.max(t_window))
            weights = t_max - t_window

        if right_decay_gamma is not None and right_decay_gamma > 0:
            delta = w_window - center_wl
            taper = np.exp(-float(right_decay_gamma) * np.maximum(0.0, delta))
            weights = weights * taper

        wsum = float(np.sum(weights))
        if wsum <= 0:
            return center_wl
        return float(np.sum(w_window * weights) / wsum)

    @staticmethod
    def compute_fwhm_nm(
        transmission: np.ndarray,
        wavelengths_nm: np.ndarray,
        search_min_nm: float = SEARCH_NM_MIN,
        search_max_nm: float = SEARCH_NM_MAX,
        mode: str = "min",
        smooth: bool = True,
        smooth_window: int | None = None,
        smooth_poly: int = 2,
        baseline_percentile: float = 95.0,
        depth_fraction: float = 0.5,
    ) -> float:
        """Compute FWHM (nm) of the SPR dip in the transmission array.

        Definition (min mode): width between the two wavelengths where T crosses
        T_half = T_min + f * (T_baseline - T_min), where T_baseline is
        estimated as a high percentile of transmission within the search window.

        For mode='max', the symmetric definition is used with maxima and a low-percentile baseline.

        Returns NaN if crossings cannot be found on both sides after robust fallbacks.
        """
        # Mask to expected region
        mask = (wavelengths_nm >= search_min_nm) & (wavelengths_nm <= search_max_nm)
        if not np.any(mask):
            mask = np.ones_like(wavelengths_nm, dtype=bool)

        t = transmission[mask]
        wl = wavelengths_nm[mask]
        if t.size < 5:
            return float("nan")

        # Optional light smoothing specifically for crossings detection
        if smooth:
            n = int(t.size)
            # Auto window: ~n/30 rounded to nearest odd, clamped [7, 51]
            if smooth_window is None:
                approx = max(7, min(51, max(3, n // 30) * 2 + 1))
                smooth_window = int(approx if approx % 2 == 1 else approx + 1)
            try:
                if smooth_window >= 5 and smooth_window < n:
                    t = savgol_filter(
                        t,
                        smooth_window,
                        min(smooth_poly, smooth_window - 1),
                    )
            except Exception:
                # Fall back silently on any filter issue
                pass

        # Determine extremum and baseline depending on mode
        if mode == "max":
            i_ext = int(np.argmax(t))
            t_ext = float(t[i_ext])
            # baseline near the lower envelope for a peak
            t_base = float(np.percentile(t, 100.0 - baseline_percentile))
            if t_base >= t_ext:
                t_base = float(np.min(t))
                if t_base >= t_ext:
                    return float("nan")
            # level at fraction between base and max
            thresh = t_ext - depth_fraction * (t_ext - t_base)
        else:
            i_ext = int(np.argmin(t))
            t_ext = float(t[i_ext])
            # baseline near the upper envelope for a dip
            t_base = float(np.percentile(t, baseline_percentile))
            if t_base <= t_ext:
                t_base = float(np.max(t))
                if t_base <= t_ext:
                    return float("nan")
            # level at fraction between min and base
            thresh = t_ext + depth_fraction * (t_base - t_ext)

        # Find left crossing (search from min to lower indices)
        def _crossing_left(idx_center: int, level: float) -> float | None:
            for k in range(idx_center - 1, -1, -1):
                y0 = t[k]
                y1 = t[k + 1] if k + 1 < len(t) else y0
                if (y0 - level) == 0:
                    return float(wl[k])
                if (y0 - level) * (y1 - level) <= 0:
                    x0 = wl[k]
                    x1 = wl[k + 1] if k + 1 < len(t) else wl[k]
                    if y1 != y0:
                        frac = (level - y0) / (y1 - y0)
                    else:
                        frac = 0.0
                    return float(x0 + frac * (x1 - x0))
            return None

        # Find right crossing (search from min to higher indices)
        def _crossing_right(idx_center: int, level: float) -> float | None:
            for k in range(idx_center, len(t) - 1):
                y0 = t[k]
                y1 = t[k + 1]
                if (y0 - level) == 0:
                    return float(wl[k])
                if (y0 - level) * (y1 - level) <= 0:
                    x0 = wl[k]
                    x1 = wl[k + 1]
                    if y1 != y0:
                        frac = (level - y0) / (y1 - y0)
                    else:
                        frac = 0.0
                    return float(x0 + frac * (x1 - x0))
            return None

        # Try a series of nearby depth fractions for robustness
        candidate_fracs = [depth_fraction, 0.45, 0.55, 0.4, 0.6]
        left_idx = right_idx = None
        for frac in candidate_fracs:
            level = (
                (t_ext - frac * (t_ext - t_base))
                if mode == "max"
                else (t_ext + frac * (t_base - t_ext))
            )
            left_idx = _crossing_left(i_ext, level)
            right_idx = _crossing_right(i_ext, level)
            if left_idx is not None and right_idx is not None:
                break

        # If still missing one side, fall back to nearest-level heuristic per side
        if left_idx is None:
            # Nearest-level fallback inside left segment
            left_window = t[:i_ext] if i_ext > 0 else None
            if left_window is not None and left_window.size > 0:
                k = int(np.argmin(np.abs(left_window - (thresh))))
                left_idx = float(wl[k])
            # Boundary extrapolation using the first two points (may extrapolate past wl[0])
            if left_idx is None and len(t) >= 2:
                y0, y1 = float(t[0]), float(t[1])
                x0, x1 = float(wl[0]), float(wl[1])
                if y1 != y0:
                    left_idx = float(x0 + (thresh - y0) * (x1 - x0) / (y1 - y0))
        if right_idx is None:
            # Nearest-level fallback inside right segment
            right_window = t[i_ext + 1 :] if i_ext + 1 < len(t) else None
            if right_window is not None and right_window.size > 0:
                k = int(np.argmin(np.abs(right_window - (thresh)))) + i_ext + 1
                right_idx = float(wl[k])
            # Boundary extrapolation using the last two points (may extrapolate past wl[-1])
            if right_idx is None and len(t) >= 2:
                y0, y1 = float(t[-2]), float(t[-1])
                x0, x1 = float(wl[-2]), float(wl[-1])
                if y1 != y0:
                    right_idx = float(x0 + (thresh - y0) * (x1 - x0) / (y1 - y0))

        if left_idx is None or right_idx is None:
            return float("nan")

        return float(right_idx - left_idx)

    @staticmethod
    def calculate_quality_metrics_nm(
        positions_nm: np.ndarray,
        mean_transmission: np.ndarray,
        wavelengths_nm: np.ndarray,
    ) -> dict:
        """Calculate quality metrics for sensorgram in nm units."""
        # Peak-to-peak variation in nm
        p2p_nm = np.ptp(positions_nm)

        # Standard deviation in nm
        std_nm = np.std(positions_nm)

        # Mean position (nm)
        mean_nm = np.mean(positions_nm)

        # High-frequency noise (differential, nm)
        hf_noise_nm = np.std(np.diff(positions_nm))

        # Peak depth (at nearest nm index to mean) as magnitude relative to 1
        nearest_idx = int(np.argmin(np.abs(wavelengths_nm - mean_nm)))
        peak_depth = float(abs(1.0 - mean_transmission[nearest_idx]))

        # SNR-like metric (unitless)
        snr = float(mean_nm / std_nm) if std_nm > 0 else 0.0

        return {
            "p2p_nm": float(p2p_nm),
            "std_nm": float(std_nm),
            "mean_position_nm": float(mean_nm),
            "hf_noise_nm": float(hf_noise_nm),
            "peak_depth": float(peak_depth),
            "snr": float(snr),
        }

    @staticmethod
    def detrend_positions_linear(
        timestamps: np.ndarray,
        positions_nm: np.ndarray,
    ) -> np.ndarray:
        """Remove linear drift trend from positions using least-squares fit."""
        if positions_nm.size < 3:
            return positions_nm.copy()
        t = np.asarray(timestamps, dtype=float)
        p = np.asarray(positions_nm, dtype=float)
        # Normalize time to improve conditioning
        t0 = t[0]
        ts = t - t0
        coeffs = np.polyfit(ts, p, 1)  # slope, intercept
        baseline = np.polyval(coeffs, ts)
        return p - baseline

    @staticmethod
    def find_extremum_zero_crossing_nm(
        transmission: np.ndarray,
        wavelengths_nm: np.ndarray,
        search_min_nm: float,
        search_max_nm: float,
        mode: str = "min",
        smooth: bool = True,
        smooth_window: int | None = None,
        smooth_poly: int = 2,
    ) -> float:
        """Estimate extremum by zero-crossing of dT/dλ within search range.

        - For mode='min' (dip), pick zero-crossing near argmin where derivative goes - → +.
        - For mode='max' (peak), pick zero-crossing near argmax where derivative goes + → -.
        Fallback: return argmin/argmax wavelength if no valid crossing found.
        """
        mask = (wavelengths_nm >= search_min_nm) & (wavelengths_nm <= search_max_nm)
        if not np.any(mask):
            mask = np.ones_like(wavelengths_nm, dtype=bool)
        wl = wavelengths_nm[mask]
        t = transmission[mask]
        if wl.size < 5:
            return float(wl[np.argmin(t)] if mode != "max" else wl[np.argmax(t)])
        if smooth:
            n = wl.size
            if smooth_window is None:
                approx = max(7, min(51, max(3, n // 30) * 2 + 1))
                smooth_window = int(approx if approx % 2 == 1 else approx + 1)
            try:
                if smooth_window >= 5 and smooth_window < n:
                    t = savgol_filter(
                        t,
                        smooth_window,
                        min(smooth_poly, smooth_window - 1),
                    )
            except Exception:
                pass

        # Derivative w.r.t wavelength
        g = np.gradient(t, wl)
        idx_ext = int(np.argmax(t)) if mode == "max" else int(np.argmin(t))

        # Scan for zero crossings
        zc_candidates = []
        for k in range(len(g) - 1):
            if mode == "max":
                cond = g[k] > 0 and g[k + 1] <= 0
            else:
                cond = g[k] < 0 and g[k + 1] >= 0
            if cond:
                x0, x1 = wl[k], wl[k + 1]
                y0, y1 = g[k], g[k + 1]
                if y1 != y0:
                    frac = -y0 / (y1 - y0)
                else:
                    frac = 0.0
                zc_wl = float(x0 + frac * (x1 - x0))
                zc_candidates.append((k, zc_wl))

        if not zc_candidates:
            return float(wl[idx_ext])

        # Pick the zero-crossing closest to the extremum index
        best = min(zc_candidates, key=lambda kv: abs(kv[0] - idx_ext))
        return float(best[1])


class TrainingDataCollector:
    """Collects and processes spectral data for ML training."""

    def __init__(
        self,
        device_name: str,
        sensor_state: str,
        sensor_id: str | None = None,
        notes: str | None = None,
        centroid_window_nm: float = CENTROID_WINDOW_NM,
        right_decay_gamma: float | None = None,
        apply_bias_correction: bool = False,
        biascorr_baseline_nm: float = 8.0,
        peak_mode: str = "min",
        defer_hardware: bool = False,
        search_min_nm: float = SEARCH_NM_MIN,
        search_max_nm: float = SEARCH_NM_MAX,
        temporal_mean_window: int = 0,
        fwhm_baseline_percentile: float = 95.0,
    ):
        self.device_name = device_name
        self.sensor_state = sensor_state
        self.sensor_id = (
            sensor_id or f"SENSOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.notes = notes or ""
        # Physics-aware centroid options
        self.centroid_window_nm = float(centroid_window_nm)
        self.right_decay_gamma = (
            float(right_decay_gamma) if right_decay_gamma is not None else None
        )
        self.apply_bias_correction = bool(apply_bias_correction)
        self.biascorr_baseline_nm = float(biascorr_baseline_nm)
        self.peak_mode = peak_mode if peak_mode in ("min", "max") else "min"
        # Search bounds for extremum & FWHM
        self.search_min_nm = float(search_min_nm)
        self.search_max_nm = float(search_max_nm)
        # Optional temporal smoothing window for metrics (0 disables)
        self.temporal_mean_window = int(max(0, temporal_mean_window))
        # FWHM baseline percentile
        self.fwhm_baseline_percentile = float(fwhm_baseline_percentile)

        # Initialize hardware
        print("\n" + "=" * 80)
        print("TRAINING DATA COLLECTION TOOL")
        print("=" * 80)
        print(f"\nDevice: {device_name}")
        print(
            f"Sensor State: {sensor_state} - {SENSOR_STATES.get(sensor_state, 'Unknown')}",
        )
        print(f"Sensor ID: {self.sensor_id}")
        if self.notes:
            print(f"Notes: {self.notes}")

        if not defer_hardware:
            print("\nInitializing hardware...")
            self.spr_device = PicoP4SPR()
            self.spectrometer = USB4000OceanDirect()

            # Connect to hardware
            if not self.spr_device.open():
                raise RuntimeError("Failed to connect to PicoP4SPR controller")
            print("✓ Controller connected")

            if not self.spectrometer.connect():
                raise RuntimeError("Failed to connect to USB4000 spectrometer")
            print("✓ Spectrometer connected")

            # Initialize wavelength mask (same as main app)
            wavelengths = np.array(self.spectrometer.get_wavelengths())
            self.wavelength_mask = (wavelengths >= MIN_WAVELENGTH) & (
                wavelengths <= MAX_WAVELENGTH
            )
            print(
                f"✓ Wavelength filter: {np.sum(self.wavelength_mask)} pixels ({MIN_WAVELENGTH}-{MAX_WAVELENGTH} nm)",
            )
            # Store masked wavelengths for nm-based processing
            self.masked_wavelengths = wavelengths[self.wavelength_mask]
        else:
            # Defer hardware init; will set masked_wavelengths later from data shape
            self.spr_device = None
            self.spectrometer = None
            self.wavelength_mask = None
            self.masked_wavelengths = None

        # Output directory
        self.output_dir = Path("training_data") / sensor_state
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"✓ Output directory: {self.output_dir}")
        print("\nCentroid configuration:")
        print(f"  Window: {self.centroid_window_nm:.1f} nm")
        print(
            f"  Right decay gamma: {self.right_decay_gamma if self.right_decay_gamma is not None else 0}",
        )
        if self.apply_bias_correction:
            print(
                f"  Bias correction: ENABLED (baseline window {self.biascorr_baseline_nm:.1f} nm)",
            )
        else:
            print("  Bias correction: DISABLED")
        print(f"  Peak tracking mode: {self.peak_mode.upper()}")
        print(
            f"  Search range: [{self.search_min_nm:.1f}, {self.search_max_nm:.1f}] nm",
        )
        if self.temporal_mean_window >= 2:
            print(f"  Temporal mean window (metrics): {self.temporal_mean_window}")

    def collect_dark_spectrum(self, mode: str) -> np.ndarray:
        """Collect dark spectrum with LED off."""
        print(f"\nCollecting {mode}-mode dark spectrum (LED OFF)...")

        # Turn off all LEDs
        self.spr_device.turn_off_channels()
        time.sleep(0.5)

        # Collect dark frames
        dark_frames = []
        for i in range(10):
            spectrum = self.spectrometer.acquire_spectrum()
            if spectrum is not None:
                dark_frames.append(
                    spectrum[self.wavelength_mask],
                )  # Apply wavelength filter
            time.sleep(0.1)

        dark = np.mean(dark_frames, axis=0)
        print(f"✓ Dark spectrum collected (averaged {len(dark_frames)} frames)")

        return dark

    def collect_mode_data(
        self,
        mode: str,
        channel: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Collect spectral data for S-mode or P-mode.

        Returns:
            (spectra, dark, timestamps)

        """
        print(f"\n{'='*80}")
        print(f"COLLECTING {mode.upper()}-MODE DATA - CHANNEL {channel.upper()}")
        print(f"{'='*80}")

        # Set up channel and polarization
        self.spr_device.turn_on_channel(channel.lower())
        time.sleep(0.2)

        # CRITICAL FIX: Actually move the polarizer!
        if mode == "s":
            print("  → Setting polarizer to S-mode...")
            self.spr_device.set_mode("s")
            time.sleep(2.0)  # Wait for servo to move
        else:
            print("  → Setting polarizer to P-mode...")
            self.spr_device.set_mode("p")
            time.sleep(2.0)  # Wait for servo to move

        time.sleep(0.5)

        # Collect dark spectrum
        dark = self.collect_dark_spectrum(mode)

        # Load calibrated LED intensity and integration time from device_config.json
        print("\nLoading calibrated LED parameters from device_config.json...")

        device_config = DeviceConfiguration()
        calibration = device_config.load_led_calibration()

        # Always consult the device-config minimum integration time as a safety floor
        min_integration_ms = None
        try:
            min_integration_ms = float(device_config.get_min_integration_time())
        except Exception:
            # Fallback if device config doesn't expose it for some reason
            min_integration_ms = 50.0

        if calibration:
            # Get calibrated LED intensity for this channel
            # Note: device_config.json stores lowercase channel keys ('a', 'b', 'c', 'd')
            led_intensity = calibration["s_mode_intensities"].get(channel.lower(), 128)
            # Prefer calibrated integration time, but enforce the minimum from device config
            integration_time_ms = int(
                calibration.get("integration_time_ms", min_integration_ms),
            )

            if integration_time_ms < min_integration_ms:
                print(
                    f"  -> Calibration integration time {integration_time_ms} ms < device-config minimum {min_integration_ms} ms; using minimum",
                )
                integration_time_ms = int(min_integration_ms)

            print(f"  -> Using calibrated LED intensity: {led_intensity}")
            print(
                f"  -> Using integration time: {integration_time_ms} ms (source: device_config{' - calibrated' if 'integration_time_ms' in calibration else ''})",
            )

            # Set integration time (convert ms to seconds)
            self.spectrometer.set_integration_time(integration_time_ms / 1000.0)

            # Use calibrated LED intensity
            print(f"\nTurning on LED for {mode}-mode...")
            self.spr_device.set_intensity(channel.lower(), led_intensity)
        else:
            # No calibration found - use conservative defaults coming from device config
            print("WARNING: No LED calibration found in device_config.json")
            print("  -> Using fallback LED intensity: 128 (safe default)")
            print(
                f"  -> Using device-config minimum integration time: {min_integration_ms} ms",
            )
            print("  -> Run calibration in main app first for optimal data collection!")

            self.spectrometer.set_integration_time(min_integration_ms / 1000.0)
            self.spr_device.set_intensity(channel.lower(), 128)

        time.sleep(1.0)
        # Collect spectra
        print(f"\nCollecting {SPECTRA_PER_MODE} spectra @ {TARGET_RATE} Hz...")
        print("Progress: ", end="", flush=True)

        spectra = []
        timestamps = []
        start_time = time.time()

        for i in range(SPECTRA_PER_MODE):
            spectrum = self.spectrometer.acquire_spectrum()
            if spectrum is None:
                print(f"\n⚠️  Warning: Failed to acquire spectrum {i+1}")
                continue

            # Apply wavelength filter (same as main app)
            spectrum = spectrum[self.wavelength_mask]

            timestamp = time.time() - start_time

            spectra.append(spectrum)
            timestamps.append(timestamp)

            # Progress indicator
            if (i + 1) % 48 == 0:  # Every 12 seconds
                print(f"{i+1}...", end="", flush=True)

            # Rate limiting
            target_interval = 1.0 / TARGET_RATE
            elapsed = time.time() - start_time
            expected_time = (i + 1) * target_interval
            sleep_time = expected_time - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

        total_time = time.time() - start_time
        actual_rate = len(spectra) / total_time

        print("\n✓ Collection complete!")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Actual rate: {actual_rate:.2f} Hz")
        print(f"  Spectra collected: {len(spectra)}")

        return np.array(spectra), dark, np.array(timestamps)

    def process_and_visualize(
        self,
        s_spectra: np.ndarray,
        p_spectra: np.ndarray,
        s_dark: np.ndarray,
        p_dark: np.ndarray,
        s_timestamps: np.ndarray,
        p_timestamps: np.ndarray,
        channel: str = "A",
    ) -> dict:
        """Process data with optimal pipeline and create visualization (nm-based)."""
        print("\n" + "=" * 80)
        print("PROCESSING WITH OPTIMAL PIPELINE")
        print("=" * 80)

        n_spectra = len(s_spectra)
        positions_nm = np.zeros(n_spectra)
        positions_zc_nm = np.zeros(n_spectra)
        fwhm_nm = np.zeros(n_spectra)
        transmissions = []

        print("\nProcessing spectra...")
        for i in range(n_spectra):
            transmission = OptimalProcessor.process_transmission(
                s_spectra[i],
                p_spectra[i],
                s_dark,
                p_dark,
            )
            transmissions.append(transmission)
            # FWHM of current transmission dip
            fwhm_nm[i] = OptimalProcessor.compute_fwhm_nm(
                transmission,
                self.masked_wavelengths,
                search_min_nm=self.search_min_nm,
                search_max_nm=self.search_max_nm,
                mode=self.peak_mode,
                smooth=True,
                baseline_percentile=self.fwhm_baseline_percentile,
            )
            positions_nm[i] = OptimalProcessor.find_extremum_centroid_nm(
                transmission,
                self.masked_wavelengths,
                search_min_nm=self.search_min_nm,
                search_max_nm=self.search_max_nm,
                window_nm=self.centroid_window_nm,
                right_decay_gamma=self.right_decay_gamma,
                mode=self.peak_mode,
            )
            # Zero-crossing method for comparison
            positions_zc_nm[i] = OptimalProcessor.find_extremum_zero_crossing_nm(
                transmission,
                self.masked_wavelengths,
                search_min_nm=self.search_min_nm,
                search_max_nm=self.search_max_nm,
                mode=self.peak_mode,
                smooth=True,
            )

        transmissions = np.array(transmissions)

        # Optional mean bias correction against small baseline window
        bias_offset_nm = 0.0
        if self.apply_bias_correction:
            baseline_positions = np.zeros(n_spectra)
            for i in range(n_spectra):
                baseline_positions[i] = OptimalProcessor.find_extremum_centroid_nm(
                    transmissions[i],
                    self.masked_wavelengths,
                    search_min_nm=self.search_min_nm,
                    search_max_nm=self.search_max_nm,
                    window_nm=self.biascorr_baseline_nm,
                    right_decay_gamma=None,
                    mode=self.peak_mode,
                )
            bias_offset_nm = float(np.mean(positions_nm) - np.mean(baseline_positions))
            positions_nm = positions_nm - bias_offset_nm

        # Calculate quality metrics (nm)
        mean_transmission = np.mean(transmissions, axis=0)
        metrics = OptimalProcessor.calculate_quality_metrics_nm(
            positions_nm,
            mean_transmission,
            self.masked_wavelengths,
        )

        # Detrended metrics (remove linear drift)
        detrended = OptimalProcessor.detrend_positions_linear(
            s_timestamps,
            positions_nm,
        )
        metrics["p2p_nm_detrended"] = float(np.ptp(detrended))
        metrics["std_nm_detrended"] = float(np.std(detrended))

        # Temporal moving average for metrics (optional)
        if self.temporal_mean_window >= 2:
            w = int(self.temporal_mean_window)
            kernel = np.ones(w, dtype=float) / float(w)
            pad = w // 2
            pos_padded = np.pad(positions_nm, (pad, pad), mode="edge")
            pos_ma = np.convolve(pos_padded, kernel, mode="valid")
            metrics["p2p_nm_smoothed"] = float(np.ptp(pos_ma))
            metrics["std_nm_smoothed"] = float(np.std(pos_ma))
            metrics["hf_noise_nm_smoothed"] = float(np.std(np.diff(pos_ma)))

        # Zero-crossing method metrics
        metrics["zc_p2p_nm"] = float(np.ptp(positions_zc_nm))
        metrics["zc_std_nm"] = float(np.std(positions_zc_nm))
        # Detrended for zero-crossing
        detrended_zc = OptimalProcessor.detrend_positions_linear(
            s_timestamps,
            positions_zc_nm,
        )
        metrics["zc_p2p_nm_detrended"] = float(np.ptp(detrended_zc))
        metrics["zc_std_nm_detrended"] = float(np.std(detrended_zc))

        # FWHM analysis and width-bias correction estimate
        valid = ~np.isnan(fwhm_nm)
        if np.any(valid):
            mean_w = float(np.nanmean(fwhm_nm))
            std_w = float(np.nanstd(fwhm_nm))
            # Correlate position with FWHM
            pos_d = positions_nm[valid]
            w_d = fwhm_nm[valid]
            w_dev = w_d - np.mean(w_d)
            # Linear regression slope (nm position per nm width)
            denom = float(np.var(w_dev)) if np.var(w_dev) > 0 else 0.0
            if denom > 0:
                slope = float(np.cov(pos_d, w_dev, bias=True)[0, 1] / denom)
                pos_corrected = positions_nm - slope * (np.nan_to_num(fwhm_nm - mean_w))
                metrics["p2p_nm_corrected"] = float(np.ptp(pos_corrected))
                metrics["std_nm_corrected"] = float(np.std(pos_corrected))
                # Pearson r
                r = float(np.corrcoef(pos_d, w_d)[0, 1])
                metrics["pos_fwhm_corr"] = r
                metrics["fwhm_slope_nm_per_nm"] = slope
            else:
                metrics["p2p_nm_corrected"] = metrics["p2p_nm"]
                metrics["std_nm_corrected"] = metrics["std_nm"]
                metrics["pos_fwhm_corr"] = 0.0
                metrics["fwhm_slope_nm_per_nm"] = 0.0
            metrics["fwhm_mean_nm"] = mean_w
            metrics["fwhm_std_nm"] = std_w
        else:
            metrics["fwhm_mean_nm"] = float("nan")
            metrics["fwhm_std_nm"] = float("nan")
            metrics["pos_fwhm_corr"] = 0.0
            metrics["fwhm_slope_nm_per_nm"] = 0.0
            metrics["p2p_nm_corrected"] = metrics["p2p_nm"]
            metrics["std_nm_corrected"] = metrics["std_nm"]

        # Attach bias offset info for metadata
        if self.apply_bias_correction:
            metrics["bias_offset_applied_nm"] = float(bias_offset_nm)
        else:
            metrics["bias_offset_applied_nm"] = 0.0

        # Convert to RU estimate (rough)
        ru_per_nm = 355
        metrics["p2p_ru_estimate"] = metrics["p2p_nm"] * ru_per_nm

        print("\n" + "=" * 80)
        print("QUALITY METRICS")
        print("=" * 80)
        print(
            f"Peak-to-peak:      {metrics['p2p_nm']:.2f} nm  (~{metrics['p2p_ru_estimate']:.0f} RU)",
        )
        print(f"Std deviation:     {metrics['std_nm']:.2f} nm")
        print(f"HF noise:          {metrics['hf_noise_nm']:.2f} nm")
        print(f"Mean position:     {metrics['mean_position_nm']:.2f} nm")
        print(f"Peak depth:        {metrics['peak_depth']:.2%}")
        print(f"SNR:               {metrics['snr']:.1f}")
        # Detrended stats
        if "p2p_nm_detrended" in metrics:
            print(f"P-P (detrended):   {metrics['p2p_nm_detrended']:.2f} nm")
            print(f"Std (detrended):   {metrics['std_nm_detrended']:.2f} nm")
        # Smoothed stats
        if "p2p_nm_smoothed" in metrics:
            print(f"P-P (smoothed):    {metrics['p2p_nm_smoothed']:.2f} nm")
            print(f"Std (smoothed):    {metrics['std_nm_smoothed']:.2f} nm")
            print(f"HF (smoothed):     {metrics['hf_noise_nm_smoothed']:.2f} nm")
        # Zero-crossing comparison
        if "zc_p2p_nm" in metrics:
            print(
                f"ZC P-P / Std:      {metrics['zc_p2p_nm']:.2f} / {metrics['zc_std_nm']:.2f} nm",
            )
        if "zc_p2p_nm_detrended" in metrics:
            print(f"ZC P-P (det):      {metrics['zc_p2p_nm_detrended']:.2f} nm")
        # Width analysis summary
        if "fwhm_mean_nm" in metrics:
            print(
                f"FWHM (mean ± std): {metrics['fwhm_mean_nm']:.2f} ± {metrics['fwhm_std_nm']:.2f} nm",
            )
            print(f"pos~FWHM corr (r): {metrics['pos_fwhm_corr']:.2f}")
            print(
                f"P-P corrected:     {metrics.get('p2p_nm_corrected', metrics['p2p_nm']):.2f} nm",
            )

        # Quality assessment (based on RU estimate)
        print("\n" + "=" * 80)
        print("QUALITY ASSESSMENT")
        print("=" * 80)
        if metrics["p2p_ru_estimate"] < 500:
            print("✓ GOOD: Low noise")
        elif metrics["p2p_ru_estimate"] < 1000:
            print("⚠ ACCEPTABLE: Moderate noise")
        else:
            print("✗ POOR: High noise")

        if metrics["peak_depth"] > 0.3:
            print("✓ GOOD: Strong SPR signal")
        elif metrics["peak_depth"] > 0.15:
            print("⚠ ACCEPTABLE: Moderate SPR signal")
        else:
            print("✗ POOR: Weak SPR signal")

        # Create visualization (with zero-crossing overlay)
        self._create_visualization(
            positions_nm,
            s_timestamps,
            transmissions,
            metrics,
            channel=channel,
            positions_zc_nm=positions_zc_nm,
        )

        return metrics

    def _create_visualization(
        self,
        positions_nm: np.ndarray,
        timestamps: np.ndarray,
        transmissions: np.ndarray,
        metrics: dict,
        channel: str = "A",
        positions_zc_nm: np.ndarray | None = None,
    ):
        """Create comprehensive visualization (nm-based)."""
        fig = plt.figure(figsize=(16, 10))

        # Sensorgram (nm)
        ax1 = plt.subplot(2, 3, 1)
        ax1.plot(
            timestamps,
            positions_nm,
            "b-",
            linewidth=1.5,
            alpha=0.8,
            label="Centroid",
        )
        if positions_zc_nm is not None and len(positions_zc_nm) == len(positions_nm):
            ax1.plot(
                timestamps,
                positions_zc_nm,
                color="orange",
                linestyle="--",
                linewidth=1.2,
                alpha=0.9,
                label="Zero-crossing",
            )
        ax1.set_xlabel("Time (s)", fontsize=11)
        ax1.set_ylabel("Resonance Position (nm)", fontsize=11)
        ax1.set_title(
            f"Sensorgram\nP-P: {metrics['p2p_nm']:.2f} nm",
            fontsize=12,
            fontweight="bold",
        )
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)

        # Add quality indicator (RU thresholds)
        quality_color = (
            "green"
            if metrics["p2p_ru_estimate"] < 500
            else "orange"
            if metrics["p2p_ru_estimate"] < 1000
            else "red"
        )
        ax1.axhline(
            y=np.mean(positions_nm),
            color=quality_color,
            linestyle="--",
            alpha=0.3,
            linewidth=2,
        )

        # Position histogram
        ax2 = plt.subplot(2, 3, 2)
        ax2.hist(positions_nm, bins=50, color="steelblue", alpha=0.7, edgecolor="black")
        ax2.set_xlabel("Position (nm)", fontsize=11)
        ax2.set_ylabel("Count", fontsize=11)
        ax2.set_title(
            f"Position Distribution\nStd: {metrics['std_nm']:.2f} nm",
            fontsize=12,
            fontweight="bold",
        )
        ax2.grid(True, alpha=0.3, axis="y")

        # Mean transmission spectrum (vs wavelength)
        ax3 = plt.subplot(2, 3, 3)
        mean_trans = np.mean(transmissions, axis=0)
        wl = self.masked_wavelengths
        # Optionally invert for visualization (peak-up look)
        try:
            from settings import INVERT_TRANSMISSION_VISUAL
        except Exception:
            INVERT_TRANSMISSION_VISUAL = True

        plot_trans = (1.0 - mean_trans) if INVERT_TRANSMISSION_VISUAL else mean_trans
        ax3.plot(wl, plot_trans, "r-", linewidth=2)
        ax3.axvline(
            x=metrics["mean_position_nm"],
            color="blue",
            linestyle="--",
            label=f"Mean: {metrics['mean_position_nm']:.1f} nm",
        )
        ax3.set_xlabel("Wavelength (nm)", fontsize=11)
        ax3.set_ylabel(
            "Absorbance-like" if INVERT_TRANSMISSION_VISUAL else "Transmission",
            fontsize=11,
        )
        ax3.set_title(
            (
                f"Mean Absorbance-like Spectrum\nDepth: {metrics['peak_depth']:.2%}"
                if INVERT_TRANSMISSION_VISUAL
                else f"Mean Transmission Spectrum\nDepth: {metrics['peak_depth']:.2%}"
            ),
            fontsize=12,
            fontweight="bold",
        )
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3)

        # Transmission heatmap (wavelength on y-axis)
        ax4 = plt.subplot(2, 3, 4)
        vis_transmissions = (
            (1.0 - transmissions) if INVERT_TRANSMISSION_VISUAL else transmissions
        )
        im = ax4.imshow(
            vis_transmissions.T,
            aspect="auto",
            cmap="viridis",
            interpolation="nearest",
            extent=(timestamps[0], timestamps[-1], wl[-1], wl[0]),
        )
        ax4.plot(
            timestamps,
            positions_nm,
            "r-",
            linewidth=2,
            alpha=0.8,
            label=(
                ("Minimum" if self.peak_mode == "min" else "Maximum") + " (Centroid)"
            ),
        )
        if positions_zc_nm is not None and len(positions_zc_nm) == len(positions_nm):
            ax4.plot(
                timestamps,
                positions_zc_nm,
                color="white",
                linestyle="--",
                linewidth=1.5,
                alpha=0.9,
                label=(
                    ("Minimum" if self.peak_mode == "min" else "Maximum")
                    + " (Zero-crossing)"
                ),
            )
        ax4.set_xlabel("Time (s)", fontsize=11)
        ax4.set_ylabel("Wavelength (nm)", fontsize=11)
        ax4.set_title(
            "Absorbance-like Time Series"
            if INVERT_TRANSMISSION_VISUAL
            else "Transmission Time Series",
            fontsize=12,
            fontweight="bold",
        )
        ax4.legend(fontsize=9)
        plt.colorbar(
            im,
            ax=ax4,
            label=("Absorbance-like" if INVERT_TRANSMISSION_VISUAL else "Transmission"),
        )

        # Noise analysis (nm)
        ax5 = plt.subplot(2, 3, 5)
        position_diff = np.diff(positions_nm)
        ax5.plot(timestamps[1:], position_diff, "g-", linewidth=1, alpha=0.7)
        ax5.set_xlabel("Time (s)", fontsize=11)
        ax5.set_ylabel("Position Change (nm)", fontsize=11)
        ax5.set_title(
            f"High-Frequency Noise\nStd: {metrics['hf_noise_nm']:.2f} nm",
            fontsize=12,
            fontweight="bold",
        )
        ax5.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax5.grid(True, alpha=0.3)

        # Metrics summary
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis("off")

        summary = (
            "COLLECTION SUMMARY\n\n"
            f"Sensor State: {self.sensor_state}\n"
            f"Sensor ID: {self.sensor_id}\n"
            f"Device: {self.device_name}\n\n"
            "QUALITY METRICS:\n"
            f"Peak-to-peak: {metrics['p2p_nm']:.2f} nm\n"
            f"  (~{metrics['p2p_ru_estimate']:.0f} RU estimate)\n"
            f"Std deviation: {metrics['std_nm']:.2f} nm\n"
            f"HF noise: {metrics['hf_noise_nm']:.2f} nm\n"
            f"Mean position: {metrics['mean_position_nm']:.2f} nm\n"
            f"Peak depth: {metrics['peak_depth']:.1%}\n"
            f"SNR: {metrics['snr']:.1f}\n\n"
            "PROCESSING:\n"
            "Pipeline: dark → denoise S&P → transmission\n"
            "Denoising: Savgol (w=51, p=3)\n"
            f"Peak finding: Centroid ({self.peak_mode})\n\n"
            f"STATUS: {'GOOD ✓' if metrics['p2p_ru_estimate'] < 500 else 'ACCEPTABLE ⚠' if metrics['p2p_ru_estimate'] < 1000 else 'POOR ✗'}\n"
        )

        ax6.text(
            0.1,
            0.5,
            summary,
            transform=ax6.transAxes,
            fontsize=10,
            verticalalignment="center",
            family="monospace",
            bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.3, pad=1),
        )

        plt.suptitle(
            f"Training Data Collection - {self.sensor_state.upper()}\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            fontsize=14,
            fontweight="bold",
        )

        plt.tight_layout()

        # Save figure
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        fig_path = (
            self.output_dir / f"{timestamp_str}_channel_{channel}_visualization.png"
        )
        plt.savefig(fig_path, dpi=150, bbox_inches="tight")
        print(f"\n✓ Visualization saved: {fig_path}")

        plt.show(block=False)
        plt.pause(0.1)

    def save_data(
        self,
        channel: str,
        s_spectra: np.ndarray,
        p_spectra: np.ndarray,
        s_dark: np.ndarray,
        p_dark: np.ndarray,
        s_timestamps: np.ndarray,
        p_timestamps: np.ndarray,
        metrics: dict,
    ):
        """Save collected data and metadata."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save S-mode data
        s_file = self.output_dir / f"{timestamp_str}_channel_{channel}_s_mode.npz"
        np.savez_compressed(
            s_file,
            spectra=s_spectra,
            dark=s_dark,
            timestamps=s_timestamps,
        )
        print(f"✓ Saved S-mode data: {s_file}")

        # Save P-mode data
        p_file = self.output_dir / f"{timestamp_str}_channel_{channel}_p_mode.npz"
        np.savez_compressed(
            p_file,
            spectra=p_spectra,
            dark=p_dark,
            timestamps=p_timestamps,
        )
        print(f"✓ Saved P-mode data: {p_file}")

        # Save metadata
        # Enrich with timing details from device configuration for traceability
        try:
            device_config = DeviceConfiguration()
            cfg_dict = device_config.to_dict()
            timing_params = cfg_dict.get("timing_parameters", {})
            optical_cal = cfg_dict.get("optical_calibration", {})

            hardware_timing = {
                "device_config_led_delay_ms": optical_cal.get("led_delay_ms", None),
                "per_channel_led_delays_ms": {
                    "a": timing_params.get("led_a_delay_ms", None),
                    "b": timing_params.get("led_b_delay_ms", None),
                    "c": timing_params.get("led_c_delay_ms", None),
                    "d": timing_params.get("led_d_delay_ms", None),
                },
                "min_integration_time_ms": timing_params.get(
                    "min_integration_time_ms",
                    None,
                ),
                "led_rise_fall_time_ms": timing_params.get(
                    "led_rise_fall_time_ms",
                    None,
                ),
                "afterglow_correction_enabled": optical_cal.get(
                    "afterglow_correction_enabled",
                    None,
                ),
            }
        except Exception:
            hardware_timing = None

        metadata = {
            "timestamp": timestamp_str,
            "datetime": datetime.now().isoformat(),
            "sensor_state": self.sensor_state,
            "sensor_state_description": SENSOR_STATES.get(self.sensor_state, "Unknown"),
            "sensor_id": self.sensor_id,
            "notes": self.notes,
            "device_name": self.device_name,
            "channel": channel,
            "collection_params": {
                "spectra_per_mode": SPECTRA_PER_MODE,
                "target_rate_hz": TARGET_RATE,
                "actual_rate_hz": len(s_timestamps) / s_timestamps[-1],
            },
            "processing_params": {
                "pipeline": "dark → denoise S&P → transmission",
                "denoising": f"Savgol (window={SAVGOL_WINDOW}, polyorder={SAVGOL_POLYORDER})",
                "peak_finding": f"Centroid ({self.peak_mode})",
                "search_range_nm": [SEARCH_NM_MIN, SEARCH_NM_MAX],
                "centroid_window_nm": self.centroid_window_nm,
                "right_decay_gamma": self.right_decay_gamma,
                "apply_bias_correction": self.apply_bias_correction,
                "biascorr_baseline_nm": self.biascorr_baseline_nm,
                "bias_offset_applied_nm": metrics.get("bias_offset_applied_nm", 0.0),
            },
            "hardware_timing": hardware_timing,
            "quality_metrics": metrics,
        }

        metadata_file = (
            self.output_dir / f"{timestamp_str}_channel_{channel}_metadata.json"
        )
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"✓ Saved metadata: {metadata_file}")

        return timestamp_str

    def collect_full_dataset(self, channels: list = ["A"], prompt: bool = True):
        """Collect complete dataset for specified channels."""
        print("\n" + "=" * 80)
        print("STARTING COLLECTION")
        print("=" * 80)
        print(f"Channels: {', '.join(channels)}")
        print(f"Spectra per mode: {SPECTRA_PER_MODE}")
        print(
            f"Estimated time per channel: ~{(SPECTRA_PER_MODE / TARGET_RATE * 2) / 60:.1f} minutes",
        )

        if prompt:
            input("\nPress ENTER to start collection...")

        for channel in channels:
            print(f"\n\n{'#'*80}")
            print(f"# CHANNEL {channel}")
            print(f"{'#'*80}")

            # Collect S-mode
            s_spectra, s_dark, s_timestamps = self.collect_mode_data("s", channel)

            # Small pause between modes
            print("\nPausing before P-mode collection...")
            time.sleep(2)

            # Collect P-mode
            p_spectra, p_dark, p_timestamps = self.collect_mode_data("p", channel)

            # Process and analyze
            metrics = self.process_and_visualize(
                s_spectra,
                p_spectra,
                s_dark,
                p_dark,
                s_timestamps,
                p_timestamps,
                channel=channel,
            )

            # Save data
            print("\n" + "=" * 80)
            print("SAVING DATA")
            print("=" * 80)
            timestamp_str = self.save_data(
                channel,
                s_spectra,
                p_spectra,
                s_dark,
                p_dark,
                s_timestamps,
                p_timestamps,
                metrics,
            )

            print(f"\n✓ Channel {channel} complete!")

            if channel != channels[-1]:
                print("\nPrepare for next channel...")
                time.sleep(3)

        print("\n" + "=" * 80)
        print("COLLECTION COMPLETE!")
        print("=" * 80)
        print(f"\nAll data saved to: {self.output_dir}")

        # Turn off LEDs
        self.spr_device.turn_off_channels()

    def cleanup(self):
        """Clean up hardware connections."""
        try:
            self.spr_device.turn_off_channels()
            print("\n✓ LEDs turned off")
        except:
            pass

        try:
            if hasattr(self.spr_device, "close"):
                self.spr_device.close()
        except:
            pass

        try:
            if hasattr(self.spectrometer, "disconnect"):
                self.spectrometer.disconnect()
        except:
            pass


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description="Collect training data for ML sensor classification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sensor States:
  new_sealed      Factory sealed, never opened
  new_unsealed    Opened but unused
  used_good       Normal use, working well
  used_current    Current sensor in use
  used_recycled   Reused cartridge, not fresh
  contaminated    Visible contamination
  degraded        Old, expired, or damaged

Examples:
  python collect_training_data.py --device "demo P4SPR 2.0" --label used_current
  python collect_training_data.py --device "demo P4SPR 2.0" --label new_sealed --sensor-id "BATCH-001"
  python collect_training_data.py --device "demo P4SPR 2.0" --label used_recycled --notes "After 50 assays"
        """,
    )

    parser.add_argument(
        "--device",
        type=str,
        required=True,
        help='Device name (e.g., "demo P4SPR 2.0")',
    )
    parser.add_argument(
        "--label",
        type=str,
        required=True,
        choices=list(SENSOR_STATES.keys()),
        help="Sensor state label",
    )
    parser.add_argument(
        "--sensor-id",
        type=str,
        default=None,
        help="Sensor ID or batch number (optional)",
    )
    parser.add_argument(
        "--notes",
        type=str,
        default=None,
        help="Additional notes (optional)",
    )
    parser.add_argument(
        "--channels",
        type=str,
        default="A,B,C,D",
        help='Channels to collect (comma-separated, e.g., "A,B,C,D")',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print integration time and LED intensity per channel without connecting to hardware",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not wait for ENTER; start collection immediately",
    )
    # Physics-aware centroid options
    parser.add_argument(
        "--centroid-window-nm",
        type=float,
        default=4.0,
        help="Total window width (nm) around minimum for centroid (default 4.0)",
    )
    parser.add_argument(
        "--right-decay-gamma",
        type=float,
        default=0.0,
        help="Exponential decay gamma on right side (0 disables)",
    )
    parser.add_argument(
        "--apply-bias-correction",
        action="store_true",
        help="Align centroid mean to a small baseline window",
    )
    parser.add_argument(
        "--biascorr-baseline-nm",
        type=float,
        default=8.0,
        help="Baseline window width (nm) used for bias correction when enabled",
    )
    # Peak tracking mode
    parser.add_argument(
        "--peak-mode",
        type=str,
        choices=["min", "max"],
        default="min",
        help="Track minimum (dip) or maximum (peak) of transmission",
    )
    # Spectral denoising controls
    parser.add_argument(
        "--savgol-window",
        type=int,
        default=None,
        help="Savitzky–Golay window (odd, >=5). Larger = smoother spectrum",
    )
    parser.add_argument(
        "--savgol-polyorder",
        type=int,
        default=None,
        help="Savitzky–Golay polynomial order (usually 2–3)",
    )
    # Peak search range override
    parser.add_argument(
        "--search-min-nm",
        type=float,
        default=None,
        help="Override minimum wavelength for extremum search (nm)",
    )
    parser.add_argument(
        "--search-max-nm",
        type=float,
        default=None,
        help="Override maximum wavelength for extremum search (nm)",
    )
    # Temporal smoothing for metrics (moving average on positions)
    parser.add_argument(
        "--temporal-mean-window",
        type=int,
        default=0,
        help="Moving average window on positions for reported metrics (0 disables)",
    )
    # FWHM baseline percentile override
    parser.add_argument(
        "--fwhm-baseline-percentile",
        type=float,
        default=None,
        help="Percentile for FWHM baseline (default 95.0; lower when using peak mode)",
    )
    # Convenience preset for recommended physics-aware centroid settings
    parser.add_argument(
        "--physics-aware-centroid",
        action="store_true",
        help="Enable recommended preset: window=100 nm, right-decay-gamma=0.02, bias correction baseline=8 nm",
    )
    # Reprocess existing datasets without acquiring new spectra
    parser.add_argument(
        "--reprocess-latest",
        action="store_true",
        help="Re-run processing and visualization on the latest saved dataset for the given label and channels",
    )

    args = parser.parse_args()

    channels = [ch.strip().upper() for ch in args.channels.split(",")]

    # Apply convenience preset if requested
    if args.physics_aware_centroid:
        # Apply recommended defaults
        args.centroid_window_nm = 100.0
        args.right_decay_gamma = 0.02
        args.apply_bias_correction = True
        args.biascorr_baseline_nm = 8.0
        print("\nPhysics-aware centroid preset ENABLED:")
        print("  → centroid_window_nm=100.0")
        print("  → right_decay_gamma=0.02")
        print("  → apply_bias_correction=True (baseline 8.0 nm)")

    # Dry-run path: report planned settings without touching hardware
    if args.dry_run:
        print("\n" + "=" * 80)
        print("TRAINING DATA COLLECTION TOOL - DRY RUN")
        print("=" * 80)
        print(f"\nDevice: {args.device}")
        print(
            f"Sensor State: {args.label} - {SENSOR_STATES.get(args.label, 'Unknown')}",
        )
        if args.sensor_id:
            print(f"Sensor ID: {args.sensor_id}")
        if args.notes:
            print(f"Notes: {args.notes}")

        device_config = DeviceConfiguration()
        calibration = device_config.load_led_calibration()
        try:
            min_integration_ms = float(device_config.get_min_integration_time())
        except Exception:
            min_integration_ms = 50.0

        print("\nLoaded device configuration")
        print(f"  → Minimum integration time (device-config): {min_integration_ms} ms")

        for ch in channels:
            ch_key = ch.lower()
            if calibration:
                led_intensity = calibration["s_mode_intensities"].get(ch_key, 128)
                integration_time_ms = int(
                    calibration.get("integration_time_ms", min_integration_ms),
                )
                if integration_time_ms < min_integration_ms:
                    integration_time_ms = int(min_integration_ms)
                print(f"\nChannel {ch}:")
                print(f"  LED intensity (device-config calibrated): {led_intensity}")
                print(
                    f"  Integration time (enforced min): {integration_time_ms} ms ({integration_time_ms/1000.0:.3f} s)",
                )
            else:
                print(f"\nChannel {ch}:")
                print("  LED intensity (fallback): 128")
                print(
                    f"  Integration time (device-config minimum): {min_integration_ms} ms ({min_integration_ms/1000.0:.3f} s)",
                )

        print(
            "\nNo hardware actions were performed. Use without --dry-run to start collection.",
        )
        return

    # Create collector
    # Resolve search range with overrides if provided
    search_min_nm = (
        args.search_min_nm if args.search_min_nm is not None else SEARCH_NM_MIN
    )
    search_max_nm = (
        args.search_max_nm if args.search_max_nm is not None else SEARCH_NM_MAX
    )

    # Allow runtime override of spectral denoising parameters
    if args.savgol_window is not None or args.savgol_polyorder is not None:
        global SAVGOL_WINDOW, SAVGOL_POLYORDER
        if args.savgol_window is not None:
            w = int(args.savgol_window)
            w = max(w, 5)
            if w % 2 == 0:
                w += 1
            SAVGOL_WINDOW = w
        if args.savgol_polyorder is not None:
            p = int(args.savgol_polyorder)
            p = max(p, 1)
            SAVGOL_POLYORDER = p
        print(
            f"\nSpectral denoising (Savitzky–Golay): window={SAVGOL_WINDOW}, polyorder={SAVGOL_POLYORDER}",
        )

    collector = TrainingDataCollector(
        device_name=args.device,
        sensor_state=args.label,
        sensor_id=args.sensor_id,
        notes=args.notes,
        centroid_window_nm=args.centroid_window_nm,
        right_decay_gamma=(
            args.right_decay_gamma if args.right_decay_gamma > 0 else None
        ),
        apply_bias_correction=bool(args.apply_bias_correction),
        biascorr_baseline_nm=args.biascorr_baseline_nm,
        peak_mode=args.peak_mode,
        defer_hardware=bool(args.reprocess_latest),
        search_min_nm=search_min_nm,
        search_max_nm=search_max_nm,
        temporal_mean_window=(args.temporal_mean_window or 0),
        fwhm_baseline_percentile=(
            args.fwhm_baseline_percentile
            if args.fwhm_baseline_percentile is not None
            else 95.0
        ),
    )

    try:
        if args.reprocess_latest:
            print("\n" + "=" * 80)
            print("REPROCESSING LATEST SAVED DATA")
            print("=" * 80)

            for ch in channels:
                ch = ch.upper()
                ch_lower = ch.lower()
                base = collector.output_dir
                # Find latest S/P files for this channel
                s_files = sorted(base.glob(f"*_channel_{ch}_s_mode.npz"))
                p_files = sorted(base.glob(f"*_channel_{ch}_p_mode.npz"))
                if not s_files or not p_files:
                    print(
                        f"⚠ No saved data found for channel {ch} in {base} — skipping",
                    )
                    continue
                s_file = s_files[-1]
                p_file = p_files[-1]
                print(f"→ Using S file: {s_file.name}")
                print(f"→ Using P file: {p_file.name}")

                s_npz = np.load(s_file)
                p_npz = np.load(p_file)

                s_spectra = s_npz["spectra"]
                s_dark = s_npz["dark"]
                s_timestamps = s_npz["timestamps"]

                p_spectra = p_npz["spectra"]
                p_dark = p_npz["dark"]
                p_timestamps = p_npz["timestamps"]

                # If wavelengths are not available (deferred hardware), synthesize from bounds
                if collector.masked_wavelengths is None:
                    n_pix = int(s_spectra.shape[1])
                    collector.masked_wavelengths = np.linspace(
                        MIN_WAVELENGTH,
                        MAX_WAVELENGTH,
                        n_pix,
                    )

                # Process and visualize
                collector.process_and_visualize(
                    s_spectra,
                    p_spectra,
                    s_dark,
                    p_dark,
                    s_timestamps,
                    p_timestamps,
                    channel=ch,
                )
            print("\nReprocessing complete.")
        else:
            # Run full collection
            collector.collect_full_dataset(
                channels=channels,
                prompt=(not args.no_prompt),
            )

        print("\n" + "=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print("\nData collection complete. Ready for ML training when you have")
        print("collected data from multiple sensor states.")

    except KeyboardInterrupt:
        print("\n\n⚠️ Collection interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during collection: {e}")
        import traceback

        traceback.print_exc()
    finally:
        collector.cleanup()
        print("\n✓ Cleanup complete")


if __name__ == "__main__":
    main()
