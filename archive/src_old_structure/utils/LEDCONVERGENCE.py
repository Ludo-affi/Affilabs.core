"""Unified LED Convergence entrypoint.

Provides a single callable to run Step 3C/Step 4 convergence using either:
- lednormalizationintensity: normalize LEDs at a fixed time, then shared-time convergence
- lednormalizationtime: freeze LEDs at 255, compute per-channel times, optional final tighten

This wraps utilities from led_methods and local ROI/acquisition helpers.
"""

from typing import Dict, List, Tuple
import os
import time

from utils.led_methods import (
    LEDconverge,
    LEDnormalizationintensity,
    LEDnormalizationtime,
    DetectorParams,
    count_saturated_pixels,
)


def run_convergence(
    usb,
    ctrl,
    ch_list: List[str],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    strategy: str = "intensity",  # "intensity" or "time"
    initial_integration_ms: float = 70.0,
    target_percent: float = 0.40,
    tolerance_percent: float = 0.05,
    tighten_final: bool = False,
    use_batch_command: bool = False,
    logger=None,
) -> Tuple[float | None, Dict[str, Dict[str, float]], bool]:
    """Run LED calibration convergence using selected strategy.

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
            logger.info(f"[CONV] ENTER run_convergence strategy={strategy} target={target_percent*100:.2f}% tol=±{tolerance_percent*100:.2f}%")
            logger.info(f"[CONV] init_int={initial_integration_ms:.2f}ms channels={ch_list}")
            logger.info(f"[CONV] ROI={wave_min_index}:{wave_max_index} detector_max={detector_params.max_counts}")
            if max_iter_override is not None:
                logger.info(f"[CONV] overrides: CAL_MAX_ITERATIONS={max_iter_override}")
            if os.getenv("CAL_TARGET_PERCENT") is not None or os.getenv("CAL_TOL_PERCENT") is not None:
                logger.info(f"[CONV] overrides: CAL_TARGET_PERCENT={os.getenv('CAL_TARGET_PERCENT')} CAL_TOL_PERCENT={os.getenv('CAL_TOL_PERCENT')}")
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
                logger.exception(f"run_convergence(time): LEDnormalizationtime crashed: {e}")
            return None, {}, False
        results: Dict[str, Dict[str, float]] = {}
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
            sig = roi_signal_fn(spec, wave_min_index, wave_max_index, method='median', top_n=50)
            results[ch] = {
                'final_led': 255,
                'final_integration_ms': Tch,
                'final_top50_counts': float(sig),
                'final_percentage': float((sig / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0),
            }
        if logger:
            try:
                logger.info(f"[CONV] time_strategy results={results}")
            except Exception:
                pass
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
                sat_px = count_saturated_pixels(spec_final, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                sat_summary[ch] = int(sat_px)
            sat_total = sum(sat_summary.values()) if sat_summary else 0
            if logger:
                logger.info(f"[CONV] final_saturation total_saturated_pixels={sat_total} per_channel={sat_summary}")
        except Exception:
            pass
        ok_counts = all(target_counts*(1.0 - tolerance_percent) <= results[ch]['final_top50_counts'] <= target_counts*(1.0 + tolerance_percent) for ch in results)
        ok = ok_counts and (sat_total == 0)
        if logger:
            try:
                flat = {ch: {k: round(v,2) if isinstance(v,float) else v for k,v in results[ch].items()} for ch in results}
                logger.info(f"[CONV] SUMMARY {{'strategy':'time','shared_integration_ms':0.0,'ok':{ok},'sat_total':{sat_total},'sat_warn':{bool(sat_total>0)},'channels':{flat}}}")
            except Exception:
                pass
        return None, results, ok

    # intensity strategy: compute normalized LEDs then run shared-time convergence
    # Step 3A ranking at fixed LED and time
    test_led = 51  # ranking LED (20%)
    try:
        usb.set_integration(initial_integration_ms)
        time.sleep(0.010)
    except Exception as e:
        if logger:
            logger.exception(f"[CONV] set_integration failed: {e}")
        return initial_integration_ms, {}, False
    channel_measurements: Dict[str, Tuple[float, float]] = {}
    weakest_mean = None
    for ch in ch_list:
        # measure at fixed LED
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
                logger.error(f"[CONV] rank {ch.upper()} spectrum None @LED={test_led} T={initial_integration_ms:.1f}ms")
            continue
        mean_val = roi_signal_fn(spec, wave_min_index, wave_max_index, method='mean', top_n=None)
        max_val = roi_signal_fn(spec, wave_min_index, wave_max_index, method='max', top_n=None) if hasattr(roi_signal_fn, '__call__') else float(mean_val)
        channel_measurements[ch] = (float(mean_val), float(max_val))
        if logger:
            try:
                logger.info(f"[CONV] rank {ch.upper()} mean={mean_val:.0f} max={max_val:.0f} LED={test_led} T={initial_integration_ms:.1f}ms")
            except Exception:
                pass
        if weakest_mean is None or mean_val < weakest_mean:
            weakest_mean = float(mean_val)

    if weakest_mean is None:
        if logger:
            logger.error("[CONV] ranking produced no valid measurements; abort")
        return initial_integration_ms, {}, False

    normalized_leds = LEDnormalizationintensity(channel_measurements, weakest_mean, min_led=10, max_led=255)
    if logger:
        try:
            logger.info(f"[CONV] normalized_leds={normalized_leds}")
        except Exception:
            pass

    # Optional preflight verification at normalized LEDs (single pass)
    try:
        usb.set_integration(initial_integration_ms)
        time.sleep(0.010)
        if logger:
            logger.info(f"[CONV] preflight @normalized_leds T={initial_integration_ms:.1f}ms")
        for ch in ch_list:
            try:
                spec_pf = acquire_raw_spectrum_fn(
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
                if spec_pf is None:
                    if logger:
                        logger.error(f"[CONV] preflight {ch.upper()} read None @LED={normalized_leds.get(ch, 255)} T={initial_integration_ms:.1f}ms")
                    continue
                sig_pf = roi_signal_fn(spec_pf, wave_min_index, wave_max_index, method='median', top_n=50)
                sat_pf = count_saturated_pixels(spec_pf, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                if logger:
                    pct_pf = (sig_pf / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0
                    logger.info(f"[CONV] preflight {ch.upper()} top50 {sig_pf:.0f} ({pct_pf:.1f}%) {'SAT' if sat_pf>0 else 'OK'} LED={normalized_leds.get(ch, 255)}")
            except Exception:
                if logger:
                    logger.debug(f"[CONV] preflight {ch.upper()} measurement failed", exc_info=True)
    except Exception:
        if logger:
            logger.debug("[CONV] preflight block failed (continuing)", exc_info=True)

    # Run shared-time convergence
    try:
        if logger:
            logger.info("[CONV] calling LEDconverge shared-time")
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
            max_iterations=max_iter_override if max_iter_override is not None else 10,
            step_name="Step 4",
            use_batch_command=use_batch_command,
            adjust_leds=True,
            logger=logger,
        )
    except Exception as e:
        if logger:
            logger.exception(f"[CONV] LEDconverge crashed: {e}")
        return initial_integration_ms, {}, False

    # Format per-channel results
    results = {}
    for ch, sig in ch_signals.items():
        results[ch] = {
            'final_led': int(normalized_leds.get(ch, 255)),
            'final_integration_ms': float(shared_int),
            'final_top50_counts': float(sig),
            'final_percentage': float((sig / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0),
        }

    # Final saturation summary at converged settings (flag-only; never stops)
    sat_summary = {}
    sat_total = 0
    try:
        for ch in ch_list:
            spec_final = acquire_raw_spectrum_fn(
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
            if spec_final is None:
                continue
            sat_px = count_saturated_pixels(spec_final, wave_min_index, wave_max_index, detector_params.saturation_threshold)
            sat_summary[ch] = int(sat_px)
        sat_total = sum(sat_summary.values()) if sat_summary else 0
        if logger:
            logger.info(f"[CONV] final_saturation total_saturated_pixels={sat_total} per_channel={sat_summary}")
    except Exception:
        # Non-fatal: keep going without saturation summary
        pass

    # Combine pass criteria: counts within tolerance AND zero saturation
    ok_counts = ok
    ok = ok_counts and (sat_total == 0)

    if logger:
        try:
            logger.info(f"[CONV] shared_int={shared_int:.2f}ms ok={ok} results={results}")
            # Structured summary line for parsing, including saturation flag
            flat = {ch: {k: round(v,2) if isinstance(v,float) else v for k,v in results[ch].items()} for ch in results}
            sat_warn = bool(sat_total > 0)
            logger.info(f"[CONV] SUMMARY {{'strategy':'intensity','shared_integration_ms':{shared_int:.2f},'ok':{ok},'sat_total':{sat_total},'sat_warn':{sat_warn},'channels':{flat}}}")
        except Exception:
            pass
    return shared_int, results, ok
