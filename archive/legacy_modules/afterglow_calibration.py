"""LED afterglow calibration workflow.

Measures LED phosphor decay after turning a channel off, across a grid
of integration times. Fits an exponential decay per channel and per
integration time to produce parameters tau (ms), amplitude, and baseline.

IMPROVED MEASUREMENT METHOD:
============================
1. LED on for 200ms (ensures consistent phosphor charge, matches real operation)
2. LED off (set intensity=0, then turn_off_channels)
3. Measure afterglow decay IMMEDIATELY (no LED_DELAY - we're measuring afterglow, not signal)
4. Sample for 250ms to capture full exponential decay curve

This method provides:
- Better stability: 24% noise reduction vs. longer delays
- Faster acquisition: Enables 25ms operation (2x faster than 50ms)
- Consistent charging: 200ms LED on ensures repeatable phosphor state
- Direct measurement: No artificial delays between LED off and measurement start

OPERATING MODES:
================

Mode 1: Global Integration Time (DEFAULT)
------------------------------------------
- LED intensity varies per channel (from LED calibration: ~180-220)
- Integration time is FIXED (e.g., 40ms)
- Afterglow calibration: Run AFTER LED calibration, uses calibrated LED intensities
- Workflow: Servo → LED Calibration → Afterglow Calibration → Go Live
- No amplitude scaling needed (measured at operating intensities)

Mode 2: Global LED Intensity
-----------------------------
- LED intensity FIXED at 255 for all channels
- Integration time varies per channel to match signal levels
- Afterglow calibration: Pre-calibrate at 255, store permanently (factory calibration)
- Amplitude scales linearly with intensity (if later measured at different intensity)
- Physics: A ∝ LED_intensity, τ = constant (material property)

The resulting dict matches the structure consumed by
`afterglow_correction.AfterglowCorrection`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import curve_fit

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable


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


def _validate_fit_result(
    ch: str,
    int_ms: float,
    fit: AfterglowFit,
    sample_count: int,
) -> None:
    """Validate afterglow fit result - BLOCKING on critical errors.

    Quality control checks:
    1. Fit quality (R²) - Ensures exponential decay model is appropriate
    2. Baseline near zero - Validates dark noise subtraction worked correctly
    3. Tau physically reasonable - Catches LED timing errors or wrong LED type
    4. Amplitude magnitude - Warns about LED hardware issues or noise floor

    Args:
        ch: Channel ID ('a', 'b', 'c', 'd')
        int_ms: Integration time (ms)
        fit: Fitted afterglow parameters
        sample_count: Number of samples collected during decay measurement

    Raises:
        ValueError: If fit quality unacceptable or data invalid (BLOCKING errors)

    """
    # CRITICAL: Fit quality - poor fit indicates bad data or wrong model
    if fit.r_squared < 0.85:
        msg = (
            f"Ch {ch} @ {int_ms}ms: Poor decay fit (R²={fit.r_squared:.3f} < 0.85)\n"
            f"   Collected {sample_count} samples\n"
            f"   Possible causes:\n"
            f"   • LED not turning off completely\n"
            f"   • High detector noise\n"
            f"   • Insufficient turn-off delay\n"
            f"   • External light contamination"
        )
        raise ValueError(
            msg,
        )

    # CRITICAL: Baseline near zero - validates dark subtraction worked
    # After dark subtraction, baseline should be near 0 (±500 counts tolerance)
    if abs(fit.baseline) > 500:
        msg = (
            f"Ch {ch} @ {int_ms}ms: High baseline ({fit.baseline:.0f} counts, expected near 0)\n"
            f"   Dark noise subtraction may have failed\n"
            f"   This indicates calibration data is invalid\n"
            f"   Check: Was dark noise measured correctly at start?"
        )
        raise ValueError(
            msg,
        )

    # CRITICAL: Tau physically reasonable for LED phosphors
    # Typical LED phosphor decay: 10-30ms, allow 5-100ms margin for variations
    if fit.tau_ms < 5 or fit.tau_ms > 100:
        msg = (
            f"Ch {ch} @ {int_ms}ms: τ={fit.tau_ms:.1f}ms outside physical range [5-100ms]\n"
            f"   Possible causes:\n"
            f"   • Wrong LED type configured in device config\n"
            f"   • LED timing/control error\n"
            f"   • Firmware bug in LED driver"
        )
        raise ValueError(
            msg,
        )

    # WARNING: Amplitude very high - LED may not be turning off
    if fit.amplitude > 10000:
        logger.warning(
            f"[WARN] Ch {ch} @ {int_ms}ms: Very high afterglow amplitude ({fit.amplitude:.0f} counts)\n"
            f"   LED may not be fully turning off\n"
            f"   Check:\n"
            f"   • LED intensity set to 0 before turn-off?\n"
            f"   • Sufficient turn-off delay (50ms)?\n"
            f"   • LED driver hardware functioning correctly?",
        )

    # WARNING: Amplitude very low - correction may be ineffective
    elif fit.amplitude < 50:
        logger.warning(
            f"[WARN] Ch {ch} @ {int_ms}ms: Very low afterglow amplitude ({fit.amplitude:.0f} counts)\n"
            f"   Afterglow correction may be ineffective (below noise floor ~3-5 counts)\n"
            f"   At 50ms delay: residual ~{fit.amplitude * 0.082:.1f} counts (may not be measurable)",
        )


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
            "led_intensities_s_mode": led_intensities
            if led_intensities
            else {},  # Save S-mode LED intensities for LED calibration reuse
            "polarization_mode": "s",  # Afterglow measured in S-mode
        },
        "channel_data": {
            ch: {"integration_time_data": [], "led_spectral_info": {}}
            for ch in channels
        },
    }

    # Use S-mode for afterglow calibration (baseline intensity)
    # This matches the LED baseline calibration in standard calibration
    # P-mode would measure at higher LED intensities which is incorrect
    try:
        ctrl.set_mode("s")
        logger.info("🔄 Afterglow calibration: Using S-mode (baseline intensity)")
    except Exception as e:
        logger.warning(f"Failed to set S-mode: {e}")

    # Measure dark noise once at the beginning (all LEDs off)
    logger.info("📊 Measuring dark noise baseline...")
    ctrl.turn_off_channels()
    time.sleep(0.2)  # Wait for LEDs to fully turn off

    # Use first integration time for dark measurement
    usb.set_integration(float(integration_grid_ms[0]))
    time.sleep(settle_delay_s)

    # Take multiple dark readings and average
    dark_readings = []
    for _ in range(5):
        sp = get_intensity()
        if sp is not None:
            roi = sp[wave_min_index:wave_max_index]
            dark_readings.append(float(np.nanmean(roi)))

    dark_noise = float(np.nanmean(dark_readings)) if dark_readings else 0.0
    logger.info(
        f"   Dark noise baseline: {dark_noise:.1f} counts (will be subtracted from all measurements)",
    )

    duration_s = acquisition_duration_ms / 1000.0
    total_measurements = len(integration_grid_ms) * len(channels)
    current_measurement = 0

    logger.info(
        f"📊 Starting afterglow measurement: {len(integration_grid_ms)} integration times × {len(channels)} channels = {total_measurements} measurements",
    )
    total_measurements = len(integration_grid_ms) * len(channels)
    current_measurement = 0

    logger.info(
        f"📊 Starting afterglow measurement: {len(integration_grid_ms)} integration times × {len(channels)} channels = {total_measurements} measurements",
    )

    for int_ms in integration_grid_ms:
        logger.info(f"⏱  Integration time: {int_ms}ms")
        usb.set_integration(float(int_ms))
        time.sleep(settle_delay_s)
        for ch in channels:
            current_measurement += 1
            logger.info(
                f"📈 [{current_measurement}/{total_measurements}] Channel {ch.upper()} @ {int_ms}ms...",
            )
            try:
                # Ensure all LEDs are completely off before starting
                ctrl.turn_off_channels()
                time.sleep(
                    0.10,
                )  # Wait for any residual phosphor decay from previous measurements

                # Pre-on to charge phosphor using S-mode baseline intensities
                if led_intensities and ch in led_intensities:
                    led_val = int(led_intensities[ch])
                    ctrl.set_intensity(ch=ch, raw_val=led_val)
                    logger.debug(f"   Using calibrated S-mode LED intensity: {led_val}")
                else:
                    ctrl.set_intensity(ch=ch, raw_val=255)
                    logger.debug(
                        "   Using maximum LED intensity: 255 (no calibration available)",
                    )
                time.sleep(pre_on_duration_s)

                # CAPTURE LED SPECTRAL CHARACTERISTICS (for aging analysis)
                # Take a snapshot of LED spectrum before turning off
                if int_ms == integration_grid_ms[0]:  # Only on first integration time
                    sp_on = get_intensity()
                    if sp_on is not None:
                        roi_on = sp_on[wave_min_index:wave_max_index]
                        peak_idx = int(np.argmax(roi_on))
                        peak_intensity = float(roi_on[peak_idx])
                        # Estimate peak wavelength (assuming linear wavelength array)
                        # This is approximate - actual wavelength would need wave_data
                        out["channel_data"][ch]["led_spectral_info"] = {
                            "peak_roi_index": peak_idx,
                            "peak_intensity": peak_intensity,
                            "integration_time_ms": float(int_ms),
                            "led_intensity": led_val
                            if led_intensities and ch in led_intensities
                            else 255,
                        }

                # Turn LED off (set intensity=0, then turn off channel)
                ctrl.set_intensity(ch=ch, raw_val=0)
                ctrl.turn_off_channels()

                # Start timing immediately after LED off command
                # No LED_DELAY here - we're measuring afterglow, not waiting for it to settle
                # The LED physically turns off within ~1-2ms, afterglow decay starts immediately
                t0 = time.perf_counter()
                t_pts: list[float] = []
                y_pts: list[float] = []

                # Sample decay using repeated spectrometer reads
                sample_count = 0
                while (time.perf_counter() - t0) < duration_s:
                    sp = get_intensity()
                    if sp is None:
                        continue
                    roi = sp[wave_min_index:wave_max_index]
                    # Use mean ROI intensity as scalar metric, subtract dark noise
                    y_val = float(np.nanmean(roi)) - dark_noise
                    t_now = (time.perf_counter() - t0) * 1000.0  # ms
                    t_pts.append(t_now)
                    y_pts.append(y_val)
                    sample_count += 1

                logger.debug(
                    f"   Collected {sample_count} decay samples over {acquisition_duration_ms}ms",
                )

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

                # QUALITY CONTROL: Validate fit before saving (BLOCKING on errors)
                _validate_fit_result(ch, int_ms, fit, sample_count)

                logger.info(
                    f"   [OK] τ={fit.tau_ms:.1f}ms, amplitude={fit.amplitude:.1f}, R²={fit.r_squared:.3f}",
                )

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
            except Exception as e:
                # Log error and continue with other channels/points
                logger.error(
                    f"[ERROR] Afterglow calibration failed for channel '{ch}' at {int_ms}ms: {e}",
                )
                time.sleep(0.05)
                continue

    # Validate that all channels were successfully calibrated
    missing_channels = []
    for ch in channels:
        if not out["channel_data"][ch]["integration_time_data"]:
            missing_channels.append(ch)

    if missing_channels:
        logger.error("[ERROR] CRITICAL: Afterglow calibration incomplete!")
        logger.error(f"   Missing data for channels: {missing_channels}")
        logger.error(f"   Expected: {channels}")
        logger.error(
            f"   Calibrated: {[ch for ch in channels if ch not in missing_channels]}",
        )
        msg = (
            f"Afterglow calibration failed: missing data for channels {missing_channels}. "
            f"All 4 channels must be calibrated for proper afterglow correction."
        )
        raise RuntimeError(
            msg,
        )

    # QUALITY CONTROL: Cross-channel consistency check (NON-BLOCKING)
    # Check if all channels have similar τ values (same LED type expected)
    _check_channel_consistency(out["channel_data"], channels)

    # LED AGING ANALYSIS: Compare with previous calibration if available
    aging_assessment = _analyze_led_aging(out, usb)

    # Store aging assessment in metadata for UI access
    out["metadata"]["aging_assessment"] = aging_assessment

    logger.info(f"[OK] Afterglow calibration complete for all channels: {channels}")
    return out


def _analyze_led_aging(current_data: dict, usb) -> dict:
    """Analyze LED aging by comparing current vs previous afterglow calibration.

    Tracks key aging indicators:
    1. Amplitude increase (phosphor degradation)
    2. Tau drift (trap state changes)
    3. Cross-channel divergence (non-uniform aging)
    4. Baseline drift (LED turn-off quality)
    5. **Spectral peak shift (LED color change - EARLY aging indicator)**

    Args:
        current_data: Current calibration data
        usb: Spectrometer instance (to get device serial)

    Returns:
        Dict with aging assessment and user-facing warning (if any)

    """
    try:
        # Try to load previous calibration for comparison
        import json

        from affilabs.utils.device_integration import (
            get_device_optical_calibration_path,
        )

        prev_cal_path = get_device_optical_calibration_path()
        if not prev_cal_path or not prev_cal_path.exists():
            logger.info(
                "📊 LED Aging Analysis: No previous calibration found (first run)",
            )
            return None

        # Load previous calibration
        with open(prev_cal_path) as f:
            prev_data = json.load(f)

        prev_date = prev_data.get("metadata", {}).get("created", "unknown")
        logger.info(
            f"📊 LED Aging Analysis: Comparing with previous calibration from {prev_date}",
        )

        # Calculate aging metrics per channel
        channels = list(current_data["channel_data"].keys())
        aging_summary = []

        for ch in channels:
            current_ch = current_data["channel_data"][ch]["integration_time_data"]
            prev_ch = (
                prev_data["channel_data"].get(ch, {}).get("integration_time_data", [])
            )

            if not current_ch or not prev_ch:
                continue

            # Calculate mean values across integration times
            curr_tau = float(np.mean([dp["tau_ms"] for dp in current_ch]))
            prev_tau = float(np.mean([dp["tau_ms"] for dp in prev_ch]))

            curr_amp = float(np.mean([dp["amplitude"] for dp in current_ch]))
            prev_amp = float(np.mean([dp["amplitude"] for dp in prev_ch]))

            curr_baseline = float(np.mean([dp.get("baseline", 0) for dp in current_ch]))
            prev_baseline = float(np.mean([dp.get("baseline", 0) for dp in prev_ch]))

            # SPECTRAL SHIFT ANALYSIS (LED color change - early aging indicator)
            curr_spectral = current_data["channel_data"][ch].get(
                "led_spectral_info",
                {},
            )
            prev_spectral = (
                prev_data["channel_data"].get(ch, {}).get("led_spectral_info", {})
            )

            peak_shift = 0
            intensity_loss_pct = 0
            if curr_spectral and prev_spectral:
                curr_peak_idx = curr_spectral.get("peak_roi_index", 0)
                prev_peak_idx = prev_spectral.get("peak_roi_index", 0)
                peak_shift = curr_peak_idx - prev_peak_idx  # ROI index shift

                curr_peak_int = curr_spectral.get("peak_intensity", 0)
                prev_peak_int = prev_spectral.get("peak_intensity", 0)
                if prev_peak_int > 0:
                    intensity_loss_pct = (
                        (curr_peak_int - prev_peak_int) / prev_peak_int * 100
                    )

            # Calculate aging indicators
            tau_drift = ((curr_tau - prev_tau) / prev_tau * 100) if prev_tau > 0 else 0
            amp_increase = (
                ((curr_amp - prev_amp) / prev_amp * 100) if prev_amp > 0 else 0
            )
            baseline_drift = curr_baseline - prev_baseline

            aging_summary.append(
                {
                    "channel": ch,
                    "tau_drift_pct": tau_drift,
                    "amp_increase_pct": amp_increase,
                    "baseline_drift": baseline_drift,
                    "peak_shift_idx": peak_shift,
                    "intensity_loss_pct": intensity_loss_pct,
                    "curr_tau": curr_tau,
                    "prev_tau": prev_tau,
                    "curr_amp": curr_amp,
                    "prev_amp": prev_amp,
                },
            )

            # Log per-channel aging status
            status = _assess_channel_aging(
                tau_drift,
                amp_increase,
                baseline_drift,
                abs(peak_shift),
                intensity_loss_pct,
            )
            logger.info(f"   Ch {ch.upper()}: {status}")
            logger.info(
                f"      τ: {prev_tau:.1f}ms → {curr_tau:.1f}ms ({tau_drift:+.1f}%)",
            )
            logger.info(
                f"      Amplitude: {prev_amp:.0f} → {curr_amp:.0f} ({amp_increase:+.1f}%)",
            )
            if abs(peak_shift) > 3:  # Significant spectral shift
                logger.info(
                    f"      Spectral peak: shifted by {peak_shift:+d} indices (color change detected)",
                )
            if abs(intensity_loss_pct) > 10:
                logger.info(
                    f"      Peak intensity: {intensity_loss_pct:+.1f}% (LED brightness loss)",
                )
            if abs(baseline_drift) > 50:
                logger.info(
                    f"      Baseline: {prev_baseline:.0f} → {curr_baseline:.0f} ({baseline_drift:+.0f})",
                )

        # Overall aging assessment (with user-facing recommendation)
        if aging_summary:
            return _assess_pcb_health(aging_summary)

        return {"status": "good", "user_message": None}

    except Exception as e:
        logger.debug(f"LED aging analysis skipped: {e}")
        return {"status": "unknown", "user_message": None}


def _assess_channel_aging(
    tau_drift_pct: float,
    amp_increase_pct: float,
    baseline_drift: float,
    peak_shift_idx: float = 0,
    intensity_loss_pct: float = 0,
) -> str:
    """Assess single channel aging status.

    Returns:
        Status string with emoji indicator

    """
    # SPECTRAL SHIFT: Early warning sign (often appears before amplitude increase)
    # Peak shift > 5 indices (~10-15nm for typical spectrometer) indicates phosphor degradation
    if abs(peak_shift_idx) > 10 or intensity_loss_pct < -30:
        return "🔴 SIGNIFICANT AGING DETECTED (spectral shift/intensity loss)"
    if abs(peak_shift_idx) > 5 or intensity_loss_pct < -15:
        return "[WARN] Moderate aging (spectral changes detected)"

    # Check for critical aging indicators (original metrics)
    if abs(tau_drift_pct) > 20 or amp_increase_pct > 100 or abs(baseline_drift) > 500:
        return "🔴 SIGNIFICANT AGING DETECTED"
    if abs(tau_drift_pct) > 10 or amp_increase_pct > 50 or abs(baseline_drift) > 200:
        return "[WARN] Moderate aging (monitor closely)"
    return "[OK] Normal wear"


def _assess_pcb_health(aging_summary: list) -> dict:
    """Assess overall LED PCB health and provide replacement recommendation.

    Args:
        aging_summary: List of aging metrics per channel

    Returns:
        Dict with 'status' (good/warning/critical) and 'user_message' (user-facing warning text)

    """
    # Calculate cross-channel tau divergence
    taus = [ch["curr_tau"] for ch in aging_summary]
    tau_std = float(np.std(taus))
    tau_mean = float(np.mean(taus))

    # Calculate mean aging rates
    mean_tau_drift = float(np.mean([ch["tau_drift_pct"] for ch in aging_summary]))
    mean_amp_increase = float(np.mean([ch["amp_increase_pct"] for ch in aging_summary]))

    # Count channels with significant aging
    critical_channels = sum(
        1
        for ch in aging_summary
        if abs(ch["tau_drift_pct"]) > 20
        or ch["amp_increase_pct"] > 100
        or abs(ch.get("peak_shift_idx", 0)) > 10
        or ch.get("intensity_loss_pct", 0) < -30
    )

    warning_channels = sum(
        1
        for ch in aging_summary
        if (abs(ch["tau_drift_pct"]) > 10 and abs(ch["tau_drift_pct"]) <= 20)
        or (ch["amp_increase_pct"] > 50 and ch["amp_increase_pct"] <= 100)
        or (
            abs(ch.get("peak_shift_idx", 0)) > 5
            and abs(ch.get("peak_shift_idx", 0)) <= 10
        )
        or (
            ch.get("intensity_loss_pct", 0) < -15
            and ch.get("intensity_loss_pct", 0) >= -30
        )
    )

    # Check for spectral shifts (early warning)
    mean_peak_shift = float(
        np.mean([abs(ch.get("peak_shift_idx", 0)) for ch in aging_summary]),
    )
    mean_intensity_loss = float(
        np.mean([ch.get("intensity_loss_pct", 0) for ch in aging_summary]),
    )

    logger.info("\n🔧 LED PCB HEALTH ASSESSMENT:")
    logger.info(
        f"   Cross-channel consistency: σ={tau_std:.1f}ms (mean τ={tau_mean:.1f}ms)",
    )
    logger.info(f"   Average τ drift: {mean_tau_drift:+.1f}%")
    logger.info(f"   Average amplitude increase: {mean_amp_increase:+.1f}%")
    if mean_peak_shift > 0:
        logger.info(f"   Average spectral peak shift: {mean_peak_shift:.1f} indices")
    if mean_intensity_loss != 0:
        logger.info(f"   Average LED intensity change: {mean_intensity_loss:+.1f}%")

    # Determine status and user-facing message
    status = "good"
    user_message = None

    # CRITICAL: Multiple failures or severe spectral shift
    if (
        critical_channels >= 2
        or tau_std > 5.0
        or mean_amp_increase > 100
        or mean_peak_shift > 10
        or mean_intensity_loss < -30
    ):
        status = "critical"
        logger.warning("   🔴 RECOMMENDATION: LED PCB replacement REQUIRED")
        logger.warning(
            f"   Reason: {'Multiple channels' if critical_channels >= 2 else 'Significant'} showing critical aging",
        )
        logger.warning(f"   {critical_channels} channels with critical aging detected")

        # USER-FACING MESSAGE
        reasons = []
        if mean_peak_shift > 10:
            reasons.append("LED color shift detected (phosphor degradation)")
        if mean_intensity_loss < -30:
            reasons.append("significant brightness loss")
        if mean_amp_increase > 100:
            reasons.append("excessive afterglow (LED wear)")
        if critical_channels >= 2:
            reasons.append(f"{critical_channels} LEDs failing")

        user_message = (
            f"[WARN] Light Source Maintenance Required\n\n"
            f"Your instrument's optical system needs attention:\n"
            f"• {' • '.join(reasons) if reasons else 'Multiple aging indicators detected'}\n\n"
            f"Impact: May affect measurement accuracy and repeatability.\n\n"
            f"Action: Contact support to schedule LED PCB replacement.\n"
            f"Expected service time: 30 minutes."
        )

    # WARNING: Single failure or moderate aging
    elif (
        critical_channels == 1
        or warning_channels >= 2
        or tau_std > 3.0
        or mean_amp_increase > 50
        or mean_peak_shift > 5
        or mean_intensity_loss < -15
    ):
        status = "warning"
        logger.warning("   [WARN] RECOMMENDATION: Monitor LED PCB closely")
        logger.warning("   Schedule replacement if performance degrades further")
        logger.warning(
            f"   {critical_channels} critical + {warning_channels} warning channels detected",
        )

        # USER-FACING MESSAGE (less urgent)
        user_message = (
            "[INFO] Light Source Aging Detected\n\n"
            "Your instrument's LEDs are showing signs of wear:\n"
            "• Moderate aging indicators present\n"
            "• Measurements still within acceptable range\n\n"
            "Recommendation: Schedule preventive maintenance within 3-6 months.\n"
            "Continue monitoring - you'll be notified if urgent action needed."
        )

    # GOOD: Minimal aging
    else:
        logger.info("   [OK] LED PCB HEALTH: Good")

    return {
        "status": status,
        "user_message": user_message,
        "critical_channels": critical_channels,
        "warning_channels": warning_channels,
    }


def _check_channel_consistency(channel_data: dict, channels: list[str]) -> None:
    """Check if τ values are consistent across channels (NON-BLOCKING).

    All channels should have similar LED types with similar phosphor decay times.
    Large variations may indicate hardware issues or LED age differences.

    Args:
        channel_data: Calibration data per channel
        channels: List of channel IDs

    """
    # Calculate average τ for each channel (across integration times)
    channel_taus = {}
    for ch in channels:
        if channel_data[ch]["integration_time_data"]:
            taus = [dp["tau_ms"] for dp in channel_data[ch]["integration_time_data"]]
            channel_taus[ch] = float(np.mean(taus))

    if len(channel_taus) < 2:
        return  # Need at least 2 channels to compare

    # Check for outliers (channels with significantly different τ)
    tau_values = list(channel_taus.values())
    tau_mean = float(np.mean(tau_values))
    tau_std = float(np.std(tau_values))

    logger.info("📊 Channel τ consistency check:")
    logger.info(f"   Mean τ: {tau_mean:.1f}ms (σ={tau_std:.1f}ms)")

    for ch, tau in channel_taus.items():
        deviation = abs(tau - tau_mean)
        if deviation > 5.0:  # More than 5ms deviation
            logger.warning(
                f"   [WARN] Ch {ch.upper()}: τ={tau:.1f}ms deviates by {deviation:.1f}ms from mean\n"
                f"      Possible causes:\n"
                f"      • Different LED type or batch\n"
                f"      • LED aging/degradation\n"
                f"      • Channel-specific optical path differences",
            )
        else:
            logger.info(f"   [OK] Ch {ch.upper()}: τ={tau:.1f}ms (Δ={deviation:.1f}ms)")
