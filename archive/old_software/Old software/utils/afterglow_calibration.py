"""LED afterglow calibration workflow.

Measures LED phosphor decay after turning a channel off, across a grid
of integration times. Fits an exponential decay per channel and per
integration time to produce parameters tau (ms), amplitude, and baseline.

The resulting dict matches the structure consumed by
`afterglow_correction.AfterglowCorrection`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit


@dataclass
class AfterglowFit:
    tau_ms: float
    amplitude: float
    baseline: float
    r_squared: float


def _exp_decay(
    t_ms: np.ndarray,
    baseline: float,
    amplitude: float,
    tau_ms: float,
) -> np.ndarray:
    return baseline + amplitude * np.exp(-t_ms / max(tau_ms, 1e-6))


def _fit_decay(t_ms: np.ndarray, y: np.ndarray) -> AfterglowFit:
    # Robust initial guesses
    y0 = float(y[0])
    y_end = float(np.nanmean(y[-max(3, len(y) // 10) :]))
    amp0 = max(y0 - y_end, 1.0)
    tau0 = 20.0  # ms, typical

    bounds = (
        [y_end - abs(0.25 * amp0), 0.0, 1.0],  # baseline, amplitude, tau
        [y_end + abs(0.25 * amp0), 1e9, 500.0],
    )
    try:
        popt, _pcov = curve_fit(
            _exp_decay,
            t_ms,
            y,
            p0=[y_end, amp0, tau0],
            bounds=bounds,
            maxfev=5000,
        )
        baseline, amplitude, tau_ms = map(float, popt)
        y_hat = _exp_decay(t_ms, baseline, amplitude, tau_ms)
        ss_res = float(np.nansum((y - y_hat) ** 2))
        ss_tot = float(np.nansum((y - np.nanmean(y)) ** 2)) or 1.0
        r2 = 1.0 - ss_res / ss_tot
        return AfterglowFit(
            tau_ms=tau_ms,
            amplitude=amplitude,
            baseline=baseline,
            r_squared=r2,
        )
    except Exception:
        # Fallback: simple estimates
        return AfterglowFit(tau_ms=tau0, amplitude=amp0, baseline=y_end, r_squared=0.0)


def run_afterglow_calibration(
    *,
    ctrl,
    usb,
    wave_min_index: int,
    wave_max_index: int,
    channels: list[str],
    integration_grid_ms: list[float],
    get_intensity: Callable[[], np.ndarray] | None = None,
    pre_on_duration_s: float = 0.25,
    acquisition_duration_ms: int = 250,
    settle_delay_s: float = 0.10,
    led_intensities: dict[str, int] | None = None,
) -> dict:
    """Measure afterglow decay curves and fit per channel and integration.

    Args:
        ctrl: LED controller with set_mode, set_intensity, turn_off_channels
        usb: USB4000 (or adapter) with set_integration(ms), read_intensity()
        wave_min_index, wave_max_index: ROI bounds for intensity metric
        channels: list of channels to calibrate, e.g., ['a','b','c','d']
        integration_grid_ms: list of integration times to measure
        get_intensity: optional override to read intensity (returns np.ndarray)
        pre_on_duration_s: LED on-time before switch-off (to saturate phosphor)
        acquisition_duration_ms: time window after switch-off to sample decay
        settle_delay_s: small delay after changes to stabilize
        led_intensities: optional per-channel intensity to use during pre-on

    Returns:
        Dict with metadata and channel_data suitable for AfterglowCorrection.

    """
    if get_intensity is None:

        def get_intensity():
            return usb.read_intensity()

    out = {
        "metadata": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "device_serial": getattr(usb, "serial_number", "unknown"),
            "pre_on_duration_s": pre_on_duration_s,
            "acquisition_duration_ms": acquisition_duration_ms,
            "integration_grid_ms": integration_grid_ms,
        },
        "channel_data": {ch: {"integration_time_data": []} for ch in channels},
    }

    # Ensure P mode to match measurement conditions
    try:
        ctrl.set_mode("p")
    except Exception:
        pass

    duration_s = acquisition_duration_ms / 1000.0
    for int_ms in integration_grid_ms:
        usb.set_integration(float(int_ms))
        time.sleep(settle_delay_s)
        for ch in channels:
            try:
                # Pre-on to charge phosphor
                if led_intensities and ch in led_intensities:
                    ctrl.set_intensity(ch=ch, raw_val=int(led_intensities[ch]))
                else:
                    ctrl.set_intensity(ch=ch, raw_val=255)
                time.sleep(pre_on_duration_s)

                # Switch off and start timing
                ctrl.turn_off_channels()
                t0 = time.perf_counter()
                t_pts: list[float] = []
                y_pts: list[float] = []

                # Sample decay using repeated spectrometer reads
                while (time.perf_counter() - t0) < duration_s:
                    sp = get_intensity()
                    if sp is None:
                        continue
                    roi = sp[wave_min_index:wave_max_index]
                    # Use mean ROI intensity as scalar metric
                    y_val = float(np.nanmean(roi))
                    t_now = (time.perf_counter() - t0) * 1000.0  # ms
                    t_pts.append(t_now)
                    y_pts.append(y_val)

                # Convert and clean
                t_arr = np.asarray(t_pts, dtype=float)
                y_arr = np.asarray(y_pts, dtype=float)
                # Drop NaNs and non-positive counts
                m = np.isfinite(t_arr) & np.isfinite(y_arr)
                t_arr = t_arr[m]
                y_arr = y_arr[m]
                if t_arr.size < 5:
                    continue

                # Fit exponential decay
                fit = _fit_decay(t_arr, y_arr)

                out["channel_data"][ch]["integration_time_data"].append(
                    {
                        "integration_time_ms": float(int_ms),
                        "tau_ms": float(fit.tau_ms),
                        "amplitude": float(fit.amplitude),
                        "baseline": float(fit.baseline),
                        "r_squared": float(fit.r_squared),
                    },
                )

                time.sleep(settle_delay_s)
            except Exception:
                # Continue with other channels/points
                time.sleep(0.05)
                continue

    return out
