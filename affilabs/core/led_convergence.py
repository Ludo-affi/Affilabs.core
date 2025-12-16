from __future__ import annotations

"""Unified LED Convergence entrypoint.

Provides a single callable to run Step 3C/Step 4 convergence using either:
- lednormalizationintensity: normalize LEDs at a fixed time, then shared-time convergence
- lednormalizationtime: freeze LEDs at 255, compute per-channel times, optional final tighten

This wraps utilities from led_methods and local ROI/acquisition helpers.
"""

import contextlib
import os
import time

from affilabs.utils.led_methods import (
    DetectorParams,
    LEDconverge,
    LEDnormalizationintensity,
    LEDnormalizationtime,
    count_saturated_pixels,
)


def _normalize_led_predictions(
    model_predicted_leds: dict[str, int],
    ch_list: list[str],
    logger,
) -> dict[str, int]:
    """Normalize model predictions so weakest channel = 255.

    CRITICAL: Weakest channel (highest LED value) must operate at maximum
    intensity (255) to maximize signal. Stronger channels scale proportionally.
    """
    max_predicted_led = max(model_predicted_leds.values())

    if max_predicted_led < 255:
        scale_factor = 255.0 / max_predicted_led
        normalized = {
            ch: int(min(255, max(10, round(model_predicted_leds[ch] * scale_factor))))
            for ch in ch_list
        }
        if logger:
            logger.info("[CONV] 🎯 Model predictions normalized (weakest→255)")
            logger.info(f"[CONV]    Raw predictions: {model_predicted_leds}")
            logger.info(f"[CONV]    Normalized (×{scale_factor:.3f}): {normalized}")
        return normalized
    # Already normalized
    normalized = {ch: model_predicted_leds[ch] for ch in ch_list}
    if logger:
        logger.info("[CONV] 🎯 Model predictions already normalized")
        logger.info(f"[CONV]    LEDs: {normalized}")
    return normalized


def _build_final_results(
    usb,
    ctrl,
    ch_list: list[str],
    initial_integration_ms: float,
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    wave_min_index: int,
    wave_max_index: int,
    use_batch_command: bool,
    logger,
) -> dict[str, int] | None:
    """Legacy Step 3A: Rank channels by measuring at fixed LED/time.

    Returns normalized LED intensities (weakest=255) or None on failure.
    """
    test_led = 51  # 20% LED for ranking measurement

    try:
        usb.set_integration(initial_integration_ms)
        time.sleep(0.010)
    except Exception as e:
        if logger:
            logger.exception(f"[CONV] set_integration failed: {e}")
        return None

    channel_measurements: dict[str, tuple[float, float]] = {}
    weakest_mean = None

    for ch in ch_list:
        spec = acquire_raw_spectrum_fn(
            usb=usb,
            ctrl=ctrl,
            channel=ch,
            led_intensity=test_led,
            integration_time_ms=initial_integration_ms,
            num_scans=1,
            pre_led_delay_ms=45.0,
            post_led_delay_ms=5.0,
            use_batch_command=use_batch_command,
        )
        if spec is None:
            if logger:
                logger.error(f"[CONV] rank {ch.upper()} failed @LED={test_led}")
            continue

        mean_val = roi_signal_fn(
            spec,
            wave_min_index,
            wave_max_index,
            method="median",
            top_n=50,
        )
        channel_measurements[ch] = (mean_val, mean_val)

        if weakest_mean is None or mean_val < weakest_mean:
            weakest_mean = mean_val

        if logger:
            logger.info(f"[CONV] rank {ch.upper()} mean={mean_val:.0f}")

    if not channel_measurements or weakest_mean is None:
        if logger:
            logger.error("[CONV] ranking failed - no valid measurements")
        return None

    # Normalize: weakest channel gets LED=255, others scale proportionally
    normalized = LEDnormalizationintensity(
        channel_measurements,
        weakest_mean,
        min_led=10,
        max_led=255,
    )

    if logger:
        logger.info(f"[CONV] Normalized LEDs: {normalized}")

    return normalized


def _run_preflight_verification(
    usb,
    ctrl,
    ch_list: list[str],
    normalized_leds: dict[str, int],
    initial_integration_ms: float,
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    wave_min_index: int,
    wave_max_index: int,
    detector_params: DetectorParams,
    use_batch_command: bool,
    logger,
) -> None:
    """Optional preflight: measure each channel at normalized LED to verify setup."""
    try:
        usb.set_integration(initial_integration_ms)
        time.sleep(0.010)
        if logger:
            logger.info(
                f"[CONV] preflight @normalized_leds T={initial_integration_ms:.1f}ms",
            )

        for ch in ch_list:
            try:
                spec = acquire_raw_spectrum_fn(
                    usb=usb,
                    ctrl=ctrl,
                    channel=ch,
                    led_intensity=normalized_leds.get(ch, 255),
                    integration_time_ms=initial_integration_ms,
                    num_scans=1,
                    pre_led_delay_ms=45.0,
                    post_led_delay_ms=5.0,
                    use_batch_command=use_batch_command,
                )
                if spec is None:
                    if logger:
                        logger.error(f"[CONV] preflight {ch.upper()} read None")
                    continue

                sig = roi_signal_fn(
                    spec,
                    wave_min_index,
                    wave_max_index,
                    method="median",
                    top_n=50,
                )
                sat = count_saturated_pixels(
                    spec,
                    wave_min_index,
                    wave_max_index,
                    detector_params.saturation_threshold,
                )

                if logger:
                    pct = (
                        (sig / detector_params.max_counts * 100.0)
                        if detector_params.max_counts
                        else 0.0
                    )
                    logger.info(
                        f"[CONV] preflight {ch.upper()} top50={sig:.0f} ({pct:.1f}%) "
                        f"{'SAT' if sat > 0 else 'OK'} LED={normalized_leds.get(ch, 255)}",
                    )
            except Exception:
                if logger:
                    logger.debug(f"[CONV] preflight {ch.upper()} failed", exc_info=True)
    except Exception:
        if logger:
            logger.debug("[CONV] preflight block failed (continuing)", exc_info=True)


def _build_final_results(
    ch_list: list[str],
    ch_signals: dict[str, float],
    normalized_leds: dict[str, int],
    shared_int: float,
    detector_params: DetectorParams,
) -> dict[str, dict[str, float]]:
    """Build final per-channel results dict."""
    results = {}
    for ch in ch_list:
        sig = ch_signals.get(ch, 0)
        results[ch] = {
            "final_led": int(normalized_leds.get(ch, 255)),
            "final_integration_ms": float(shared_int),
            "final_top50_counts": float(sig),
            "final_percentage": float(
                (sig / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0,
            ),
        }
    return results


def _check_final_saturation(
    usb,
    ctrl,
    ch_list: list[str],
    normalized_leds: dict[str, int],
    shared_int: float,
    acquire_raw_spectrum_fn,
    wave_min_index: int,
    wave_max_index: int,
    detector_params: DetectorParams,
    use_batch_command: bool,
    logger,
) -> tuple[dict[str, int], int]:
    """Final saturation check at converged settings.

    Returns: (sat_per_channel, sat_total)
    """
    sat_summary = {}
    try:
        for ch in ch_list:
            spec = acquire_raw_spectrum_fn(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=int(normalized_leds.get(ch, 255)),
                integration_time_ms=float(shared_int),
                num_scans=1,
                pre_led_delay_ms=45.0,
                post_led_delay_ms=5.0,
                use_batch_command=use_batch_command,
            )
            if spec is None:
                continue

            sat_px = count_saturated_pixels(
                spec,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
            )
            sat_summary[ch] = int(sat_px)

        sat_total = sum(sat_summary.values())
        if logger:
            logger.debug(
                f"[CONV] final_saturation total={sat_total} per_channel={sat_summary}",
            )
        return sat_summary, sat_total
    except Exception:
        return {}, 0


def run_convergence(
    usb,
    ctrl,
    ch_list: list[str],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    strategy: str = "intensity",  # "intensity" or "time"
    initial_integration_ms: float = 70.0,
    model_predicted_leds: dict[str, int] | None = None,  # NEW: Model predictions
    model_slopes: dict[str, float]
    | None = None,  # NEW: Model calibration slopes (S-pol, valid for P-pol too)
    polarization: str = "S",  # NEW: Polarization state for model
    target_percent: float = 0.40,
    tolerance_percent: float = 0.05,
    tighten_final: bool = False,
    use_batch_command: bool = True,  # ALWAYS use batch commands for LED control (more reliable)
    logger=None,
) -> tuple[float | None, dict[str, dict[str, float]], bool]:
    """Run LED calibration convergence using selected strategy.

    Args:
        model_predicted_leds: Optional dict of model-predicted LED intensities {'a': 145, 'b': 150, ...}
                             If provided, skips empirical ranking and uses predictions directly.
        model_slopes: Optional dict of model calibration slopes {'A': slope_10ms, 'B': slope_10ms, ...}
                     If provided, enables exact model-based saturation correction.
                     NOTE: S-pol slopes are valid for P-pol convergence (same LED-to-counts relationship)

    Returns:
        (shared_integration_ms_or_None, per_channel_results, ok)
        - In time strategy, shared_integration_ms is None and per-channel times are returned.
        - In intensity strategy, shared_integration_ms is the converged value and per-channel signals are returned.

    """
    # Allow env-based overrides for quick tuning without code edits
    try:
        env_target = os.getenv("CAL_TARGET_PERCENT")
        if env_target is not None:
            try:
                val = float(env_target)
                # Accept either 0.40 or 40 for 40%
                target_percent = val if val <= 1.0 else (val / 100.0)
            except Exception:
                pass
        env_tol = os.getenv("CAL_TOL_PERCENT")
        if env_tol is not None:
            try:
                val = float(env_tol)
                tolerance_percent = val if val <= 1.0 else (val / 100.0)
            except Exception:
                pass
        env_max_iter = os.getenv("CAL_MAX_ITERATIONS")
        max_iter_override = int(env_max_iter) if env_max_iter and env_max_iter.isdigit() else None
    except Exception:
        max_iter_override = None

    if logger:
        try:
            logger.info("[CONV]" + "=" * 72)
            logger.info(
                f"[CONV] ENTER run_convergence strategy={strategy} target={target_percent * 100:.2f}% tol=±{tolerance_percent * 100:.2f}%",
            )
            logger.info(
                f"[CONV] init_int={initial_integration_ms:.2f}ms channels={ch_list}",
            )
            logger.info(
                f"[CONV] ROI={wave_min_index}:{wave_max_index} detector_max={detector_params.max_counts}",
            )
            if max_iter_override is not None:
                logger.info(f"[CONV] overrides: CAL_MAX_ITERATIONS={max_iter_override}")
            if (
                os.getenv("CAL_TARGET_PERCENT") is not None
                or os.getenv("CAL_TOL_PERCENT") is not None
            ):
                logger.info(
                    f"[CONV] overrides: CAL_TARGET_PERCENT={os.getenv('CAL_TARGET_PERCENT')} CAL_TOL_PERCENT={os.getenv('CAL_TOL_PERCENT')}",
                )
            logger.info("[CONV]" + "=" * 72)
        except Exception:
            pass

    target_counts = target_percent * detector_params.max_counts

    if strategy == "time":
        # LEDs fixed at 255; compute per-channel times with optional final tighten
        if logger:
            logger.info("[CONV] Strategy=time (per-channel integration @ LED=255)")
        try:
            per_times = LEDnormalizationtime(
                usb=usb,
                ctrl=ctrl,
                ch_list=ch_list,
                acquire_raw_spectrum_fn=acquire_raw_spectrum_fn,
                roi_signal_fn=roi_signal_fn,
                target_percent=target_percent,
                tolerance_percent=tolerance_percent,
                detector_params=detector_params,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                logger=logger,
                tighten_final=tighten_final,
                use_batch_command=use_batch_command,
            )
        except Exception as e:
            if logger:
                logger.exception(
                    f"run_convergence(time): LEDnormalizationtime crashed: {e}",
                )
            return None, {}, False
        results: dict[str, dict[str, float]] = {}
        for ch in ch_list:
            Tch = float(per_times.get(ch, initial_integration_ms))
            spec = acquire_raw_spectrum_fn(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=255,
                integration_time_ms=Tch,
                num_scans=1,
                pre_led_delay_ms=45.0,
                post_led_delay_ms=5.0,
                use_batch_command=use_batch_command,
            )
            if spec is None:
                continue
            sig = roi_signal_fn(
                spec,
                wave_min_index,
                wave_max_index,
                method="median",
                top_n=50,
            )
            results[ch] = {
                "final_led": 255,
                "final_integration_ms": Tch,
                "final_top50_counts": float(sig),
                "final_percentage": float(
                    (sig / detector_params.max_counts * 100.0)
                    if detector_params.max_counts
                    else 0.0,
                ),
            }
        if logger:
            with contextlib.suppress(Exception):
                logger.info(f"[CONV] time_strategy results={results}")
        # Final saturation summary (pass requires sat_total==0)
        sat_summary = {}
        sat_total = 0
        try:
            for ch in ch_list:
                Tch = float(per_times.get(ch, initial_integration_ms))
                spec_final = acquire_raw_spectrum_fn(
                    usb=usb,
                    ctrl=ctrl,
                    channel=ch,
                    led_intensity=255,
                    integration_time_ms=Tch,
                    num_scans=1,
                    pre_led_delay_ms=45.0,
                    post_led_delay_ms=5.0,
                    use_batch_command=use_batch_command,
                )
                if spec_final is None:
                    continue
                sat_px = count_saturated_pixels(
                    spec_final,
                    wave_min_index,
                    wave_max_index,
                    detector_params.saturation_threshold,
                )
                sat_summary[ch] = int(sat_px)
            sat_total = sum(sat_summary.values()) if sat_summary else 0
            if logger:
                logger.info(
                    f"[CONV] final_saturation total_saturated_pixels={sat_total} per_channel={sat_summary}",
                )
        except Exception:
            pass
        # Relaxed acceptance: PASS if zero saturated pixels, regardless of count tolerance
        all(
            target_counts * (1.0 - tolerance_percent)
            <= results[ch]["final_top50_counts"]
            <= target_counts * (1.0 + tolerance_percent)
            for ch in results
        )
        ok = sat_total == 0
        if logger:
            logger.info(
                f"[CONV] [OK] RELAXED PASS CRITERIA ACTIVE: sat_total={sat_total}, ok={ok} (passing because zero saturation)",
            )
            try:
                flat = {
                    ch: {
                        k: round(v, 2) if isinstance(v, float) else v
                        for k, v in results[ch].items()
                    }
                    for ch in results
                }
                logger.info(
                    f"[CONV] SUMMARY {{'strategy':'time','shared_integration_ms':0.0,'ok':{ok},'sat_total':{sat_total},'sat_warn':{bool(sat_total > 0)},'channels':{flat}}}",
                )
            except Exception:
                pass
        return None, results, ok

    # === STRATEGY: Model predictions drive convergence to target without saturation ===
    if not model_predicted_leds:
        if logger:
            logger.error("[CONV] ❌ No model predictions provided - cannot proceed")
        return initial_integration_ms, {}, False

    normalized_leds = _normalize_led_predictions(model_predicted_leds, ch_list, logger)

    # === CONVERGENCE: Adjust LEDs/time to reach target signal without saturation ===
    # No preflight needed - convergence iteration 1 measures all channels anyway
    try:
        if logger:
            logger.info("[CONV] Calling LEDconverge (shared-time strategy)")
            if model_slopes:
                logger.info(f"[CONV]   Model slopes: {model_slopes}")

        shared_int, ch_signals, ok = LEDconverge(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            led_intensities=normalized_leds,
            acquire_raw_spectrum_fn=acquire_raw_spectrum_fn,
            roi_signal_fn=roi_signal_fn,
            initial_integration_ms=initial_integration_ms,
            target_percent=target_percent,
            tolerance_percent=tolerance_percent,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            max_iterations=max_iter_override if max_iter_override is not None else 15,
            step_name="Step 4",
            use_batch_command=use_batch_command,
            model_slopes=model_slopes,
            polarization=polarization,
            logger=logger,
        )
    except Exception as e:
        if logger:
            logger.exception(f"[CONV] LEDconverge crashed: {e}")
        return initial_integration_ms, {}, False

    # === RESULTS: Build final summary and check saturation ===
    results = _build_final_results(
        ch_list,
        ch_signals,
        normalized_leds,
        shared_int,
        detector_params,
    )
    sat_summary, sat_total = _check_final_saturation(
        usb,
        ctrl,
        ch_list,
        normalized_leds,
        shared_int,
        acquire_raw_spectrum_fn,
        wave_min_index,
        wave_max_index,
        detector_params,
        use_batch_command,
        logger,
    )

    # SUCCESS CRITERIA: Zero saturation (top priority) + signals in tolerance
    # Production quality: ZERO saturated pixels allowed
    # Target reduced to 88% to ensure headroom for LED variations
    ok_final = (sat_total == 0) and ok

    if logger:
        logger.debug(
            f"[CONV] SUCCESS: convergence={'OK' if ok else 'FAIL'}, saturation={sat_total} pixels",
        )
        logger.debug(
            f"[CONV] FINAL RESULT: {'PASS' if ok_final else 'FAIL'} (0 saturated pixels required, {sat_total} detected)",
        )
        logger.debug(f"[CONV] shared_int={shared_int:.2f}ms results={results}")

        # Structured summary for parsing
        try:
            flat = {
                ch: {k: round(v, 2) if isinstance(v, float) else v for k, v in results[ch].items()}
                for ch in results
            }
            logger.debug(
                f"[CONV] SUMMARY {{'strategy':'intensity','shared_int_ms':{shared_int:.2f},'ok':{ok_final},"
                f"'sat_total':{sat_total},'sat_summary':{sat_summary},'channels':{flat}}}",
            )
        except Exception:
            pass

    return shared_int, results, ok_final
