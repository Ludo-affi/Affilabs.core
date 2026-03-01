"""Simple LED Calibration — direct proportional-feedback loop, no convergence engine.

PURPOSE
-------
Quick re-convergence after a sensor chip swap (same device, same optical path).
The LED model is NOT used — we start from the caller's current LED values and
iterate with pure physics:  new_led = old_led × (target / measured)

This avoids the engine's model-based initialisation, which fails when the LED
model is stale (e.g. model says C is weak → maxes C's LED → instant saturation).

ALGORITHM (per polarisation mode)
----------------------------------
1. Start from caller-supplied LEDs (or safe defaults: 128 / integration as-is).
2. For up to MAX_ITERATIONS:
   a. Fire each channel at its current LED value, read ROI signal.
   b. Compute ratio = target_counts / measured_signal (clamped to [0.5, 2.0]).
   c. Scale LED: new_led = clamp(round(old_led × ratio), 1, 255).
   d. Lock channels already within tolerance (±TOLERANCE_PCT of target).
   e. Break when all channels locked.
3. Apply saturation back-off: if measured ≥ 98% of sat_threshold → scale LED
   down to land at SAT_BACKOFF_PCT of threshold.
4. Capture S-pol reference spectra with the final LEDs (multi-scan average).
5. Repeat steps 1-3 for P-mode (start from S-mode LEDs as initial guess).
6. Capture dark spectrum, run SpectrumPreprocessor, assemble result.

REQUIREMENTS
------------
- Hardware connected (ctrl + usb).
- Previous calibration data available (for starting LED values and integration
  time).  If not provided, safe defaults are used.
- Prism installed with buffer/water.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

import numpy as np

from affilabs.models.led_calibration_result import LEDCalibrationResult
from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from affilabs.core.hardware_manager import HardwareManager

# ── Tuning constants ──────────────────────────────────────────────────────────
MAX_ITERATIONS    = 6        # Proportional loop iterations per mode
TARGET_PCT        = 0.82     # Aim for 82% of detector max (leaves headroom)
TOLERANCE_PCT     = 0.12     # ±12% counts is "converged"
SAT_BACKOFF_PCT   = 0.80     # Back off to 80% of sat_threshold if saturating
MAX_RATIO         = 2.0      # Cap single-step scale-up
MIN_RATIO         = 0.35     # Cap single-step scale-down (avoid overcorrection)
DETECTOR_WINDOW_MS = 180.0
MAX_NUM_SCANS      = 10


# ── Public entry point ────────────────────────────────────────────────────────

def run_simple_led_calibration(
    hardware_mgr: "HardwareManager",
    progress_callback: Callable[[str, int], None] | None = None,
    current_s_leds: dict[str, int] | None = None,
    current_integration_ms: float | None = None,
    existing_dark: "np.ndarray | None" = None,
) -> LEDCalibrationResult:
    """Run quick LED re-convergence for sensor chip swaps.

    Completely bypasses the convergence engine and LED model.  Uses a direct
    proportional-feedback loop starting from *current_s_leds* (the LED values
    that were running before the chip swap).

    Args:
        hardware_mgr: Connected hardware manager.
        progress_callback: Optional callback(message: str, percent: int).
        current_s_leds: S-mode LED intensities from the previous calibration.
            If None, starts from 128 on every channel.
        current_integration_ms: Integration time from the previous calibration.
            If None, uses 4.5 ms (safe minimum).
        existing_dark: Dark spectrum (ROI-cropped) from previous calibration.
            If provided, Step 7 (dark capture) is skipped and this array is
            reused for reference-spectrum subtraction.

    Returns:
        LEDCalibrationResult — same schema as full calibration result.
    """
    result = LEDCalibrationResult()

    ctrl = hardware_mgr.ctrl
    usb  = hardware_mgr.usb
    if not ctrl or not usb:
        result.error = "Hardware not connected"
        return result

    result.detector_serial = getattr(usb, "serial_number", "UNKNOWN")

    def _prog(msg: str, pct: int) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, pct)

    try:
        _run_simple_calibration(
            usb=usb,
            ctrl=ctrl,
            hardware_mgr=hardware_mgr,
            result=result,
            initial_s_leds=current_s_leds,
            integration_ms=current_integration_ms,
            existing_dark=existing_dark,
            progress_fn=_prog,
        )
    except Exception as exc:
        logger.error("Simple LED calibration failed: %s", exc, exc_info=True)
        result.success = False
        result.error = str(exc)
    finally:
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass

    return result


# ── Core implementation ───────────────────────────────────────────────────────

def _run_simple_calibration(
    usb,
    ctrl,
    hardware_mgr,
    result: LEDCalibrationResult,
    initial_s_leds: dict[str, int] | None,
    integration_ms: float | None,
    existing_dark: "np.ndarray | None",
    progress_fn,
) -> None:
    from affilabs.utils.startup_calibration import acquire_raw_spectrum
    from settings import MIN_WAVELENGTH, MAX_WAVELENGTH

    CH_LIST = ["a", "b", "c", "d"]

    # ── Detector limits ───────────────────────────────────────────────────────
    max_counts = getattr(usb, "max_counts", 65535)
    min_int_ms = getattr(usb, "min_integration_time_ms", 4.5)
    sat_threshold = int(max_counts * 0.95)

    target_counts = max_counts * TARGET_PCT
    tol_lo = target_counts * (1.0 - TOLERANCE_PCT)
    tol_hi = target_counts * (1.0 + TOLERANCE_PCT)

    logger.info("=" * 60)
    logger.info("SIMPLE LED CALIBRATION (proportional loop, no model)")
    logger.info("  Target: %.0f counts (%.0f%%)", target_counts, TARGET_PCT * 100)
    logger.info("  Tolerance: ±%.0f%%", TOLERANCE_PCT * 100)
    logger.info("=" * 60)

    # ── Wavelength ROI ────────────────────────────────────────────────────────
    wave_data = usb.read_wavelength()
    if wave_data is None or len(wave_data) == 0:
        raise RuntimeError("Failed to read wavelength data from detector")

    wmin_i = int(np.argmin(np.abs(wave_data - MIN_WAVELENGTH)))
    wmax_i = int(np.argmin(np.abs(wave_data - MAX_WAVELENGTH)))

    result.wave_data       = wave_data[wmin_i:wmax_i]
    result.wavelengths     = result.wave_data
    result.wave_min_index  = wmin_i
    result.wave_max_index  = wmax_i
    result.detector_max_counts        = max_counts
    result.detector_saturation_threshold = sat_threshold

    # ── Integration time ──────────────────────────────────────────────────────
    if integration_ms and integration_ms >= min_int_ms:
        int_ms = float(integration_ms)
        logger.info("Using caller integration time: %.1f ms", int_ms)
    else:
        int_ms = max(min_int_ms, 4.5)
        logger.info("Using default integration time: %.1f ms", int_ms)

    usb.set_integration(int_ms)
    time.sleep(0.15)

    # ── Device config for servo positions ─────────────────────────────────────
    device_config = hardware_mgr.device_config
    try:
        s_pos = device_config.get_servo_s_position() if device_config else None
        p_pos = device_config.get_servo_p_position() if device_config else None
    except Exception:
        s_pos = None
        p_pos = None

    # ── Step 1: Move to S-mode ────────────────────────────────────────────────
    progress_fn("Simple cal: moving to S-mode…", 10)
    ctrl.turn_off_channels()
    time.sleep(0.1)

    if ctrl.supports_polarizer and s_pos is not None and p_pos is not None:
        ctrl.set_servo_positions(s_pos, p_pos)   # load device PWM values
        time.sleep(0.2)
        ctrl.servo_move_raw_pwm(1)               # park to clear backlash
        time.sleep(0.8)
        ctrl.set_mode("s")
        time.sleep(1.0)                          # settle

    # ── Step 2: S-mode proportional convergence ───────────────────────────────
    progress_fn("Simple cal: S-mode LED adjustment…", 20)

    s_leds = {ch: int(initial_s_leds.get(ch, 128)) if initial_s_leds else 128
              for ch in CH_LIST}
    s_leds = {ch: max(1, min(255, v)) for ch, v in s_leds.items()}

    logger.info("Starting S-mode LEDs: %s", s_leds)

    s_leds, s_signals, s_iters = _proportional_loop(
        usb=usb, ctrl=ctrl,
        ch_list=CH_LIST,
        leds=s_leds,
        integration_ms=int_ms,
        target=target_counts,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        sat_threshold=sat_threshold,
        acquire_fn=acquire_raw_spectrum,
        wave_min=wmin_i,
        wave_max=wmax_i,
        label="S",
    )

    result.s_mode_intensity = dict(s_leds)
    result.ref_intensity    = dict(s_leds)
    result.s_integration_time = int_ms
    result.s_iterations = s_iters

    # ── Step 3: Capture S-pol reference spectra ───────────────────────────────
    progress_fn("Simple cal: capturing S-pol reference…", 45)

    num_scans_s = min(MAX_NUM_SCANS, max(1, int(DETECTOR_WINDOW_MS / int_ms)))
    result.num_scans = num_scans_s

    usb.set_integration(int_ms)
    time.sleep(0.05)

    s_raw_data: dict[str, np.ndarray] = {}
    for ch in CH_LIST:
        spec = acquire_raw_spectrum(
            usb=usb, ctrl=ctrl,
            channel=ch,
            led_intensity=s_leds[ch],
            integration_time_ms=int_ms,
            num_scans=num_scans_s,
            use_batch_command=True,
        )
        if spec is None:
            raise RuntimeError(f"S-pol reference capture failed for channel {ch.upper()}")
        roi = spec[wmin_i:wmax_i]
        # Saturation guard
        if float(np.max(roi)) >= sat_threshold:
            # Back off LED and retry once
            scale = (sat_threshold * SAT_BACKOFF_PCT) / float(np.max(roi))
            s_leds[ch] = max(1, int(s_leds[ch] * scale))
            logger.warning("  %s ref saturated -> backing LED off to %d, retrying", ch.upper(), s_leds[ch])
            spec = acquire_raw_spectrum(
                usb=usb, ctrl=ctrl,
                channel=ch,
                led_intensity=s_leds[ch],
                integration_time_ms=int_ms,
                num_scans=num_scans_s,
                use_batch_command=True,
            )
            if spec is None:
                raise RuntimeError(f"S-pol reference retry failed for channel {ch.upper()}")
            roi = spec[wmin_i:wmax_i]
        s_raw_data[ch] = roi

    result.s_raw_data = s_raw_data

    # ── Step 4: Move to P-mode ────────────────────────────────────────────────
    progress_fn("Simple cal: moving to P-mode…", 55)
    ctrl.turn_off_channels()
    time.sleep(0.1)

    if ctrl.supports_polarizer and s_pos is not None and p_pos is not None:
        ctrl.set_servo_positions(s_pos, p_pos)   # reload positions (safe)
        time.sleep(0.2)
        ctrl.servo_move_raw_pwm(1)               # park to clear backlash
        time.sleep(0.8)
        ctrl.set_mode("p")
        time.sleep(1.0)                          # settle

    # ── Step 5: P-mode proportional convergence ───────────────────────────────
    progress_fn("Simple cal: P-mode LED adjustment…", 65)

    # Start P-mode from S-mode LEDs (reasonable first guess)
    p_leds = dict(s_leds)

    p_leds, p_signals, p_iters = _proportional_loop(
        usb=usb, ctrl=ctrl,
        ch_list=CH_LIST,
        leds=p_leds,
        integration_ms=int_ms,
        target=target_counts,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        sat_threshold=sat_threshold,
        acquire_fn=acquire_raw_spectrum,
        wave_min=wmin_i,
        wave_max=wmax_i,
        label="P",
    )

    result.p_mode_intensity = dict(p_leds)
    result.p_integration_time = int_ms
    result.p_iterations = p_iters

    # ── Step 6: Capture P-pol reference spectra ───────────────────────────────
    progress_fn("Simple cal: capturing P-pol reference…", 80)

    num_scans_p = num_scans_s
    usb.set_integration(int_ms)
    time.sleep(0.05)

    p_raw_data: dict[str, np.ndarray] = {}
    for ch in CH_LIST:
        spec = acquire_raw_spectrum(
            usb=usb, ctrl=ctrl,
            channel=ch,
            led_intensity=p_leds[ch],
            integration_time_ms=int_ms,
            num_scans=num_scans_p,
            use_batch_command=True,
        )
        if spec is not None:
            p_raw_data[ch] = spec[wmin_i:wmax_i]

    result.p_raw_data = p_raw_data

    # ── Step 7: Recycle dark frame ──────────────────────────────────────────
    progress_fn("Simple cal: dark frame…", 88)
    if existing_dark is not None:
        # Recycle the dark from prior full calibration — skip LED-off/read cycle
        result.dark_noise = np.array(existing_dark, dtype=float)
        logger.info("Recycled existing dark frame (%d px)", len(result.dark_noise))
    else:
        # Fallback: capture a fresh dark frame (only when no prior dark available)
        ctrl.turn_off_channels()
        time.sleep(0.05)
        usb.set_integration(int_ms)
        time.sleep(0.05)
        try:
            dark_raw = usb.read_intensity()
            if dark_raw is not None:
                result.dark_noise = np.array(dark_raw[wmin_i:wmax_i], dtype=float)
        except Exception as e:
            logger.warning("Dark frame failed (non-fatal): %s", e)

    # ── Step 8: Build reference spectra via SpectrumPreprocessor ─────────────
    progress_fn("Simple cal: preprocessing references…", 92)

    dark = result.dark_noise
    s_pol_ref: dict[str, np.ndarray] = {}
    p_pol_ref: dict[str, np.ndarray] = {}

    for ch in CH_LIST:
        if ch in s_raw_data:
            roi = s_raw_data[ch].astype(float)
            s_pol_ref[ch] = roi - dark if dark is not None else roi
        if ch in p_raw_data:
            roi = p_raw_data[ch].astype(float)
            p_pol_ref[ch] = roi - dark if dark is not None else roi

    result.s_pol_ref = s_pol_ref
    result.p_pol_ref = p_pol_ref

    # ── Done ──────────────────────────────────────────────────────────────────
    result.leds_calibrated = dict(p_leds)
    result.success = True

    progress_fn("Simple cal: complete", 100)
    logger.info("Simple LED calibration complete -- S-iters=%d  P-iters=%d", s_iters, p_iters)
    logger.info("  S-LEDs: %s", s_leds)
    logger.info("  P-LEDs: %s", p_leds)


# ── Proportional feedback loop ────────────────────────────────────────────────

def _proportional_loop(
    usb, ctrl,
    ch_list: list[str],
    leds: dict[str, int],
    integration_ms: float,
    target: float,
    tol_lo: float,
    tol_hi: float,
    sat_threshold: int,
    acquire_fn,
    wave_min: int,
    wave_max: int,
    label: str,
) -> tuple[dict[str, int], dict[str, float], int]:
    """Proportional-feedback LED adjustment loop.

    Returns (final_leds, final_signals, iterations_used).
    """
    leds = dict(leds)
    locked: set[str] = set()
    signals: dict[str, float] = {}

    for iteration in range(1, MAX_ITERATIONS + 1):
        logger.info("--- %s iteration %d/%d @ %.1fms ---", label, iteration, MAX_ITERATIONS, integration_ms)

        # Measure all unlocked channels
        for ch in ch_list:
            spec = acquire_fn(
                usb=usb, ctrl=ctrl,
                channel=ch,
                led_intensity=leds[ch],
                integration_time_ms=integration_ms,
                num_scans=1,
                use_batch_command=True,
            )
            if spec is None:
                logger.warning("  %s: read failed", ch.upper())
                continue

            sig = float(np.mean(spec[wave_min:wave_max]))
            signals[ch] = sig
            pct = sig / target * 100.0

            if sig >= sat_threshold * 0.98:
                # Saturating — scale down hard
                scale = max(MIN_RATIO, (sat_threshold * SAT_BACKOFF_PCT) / sig)
                new_led = max(1, int(leds[ch] * scale))
                logger.info("  %s: SAT (%.0f) -> LED %d->%d (scale=%.2f)", ch.upper(), sig, leds[ch], new_led, scale)
                leds[ch] = new_led
                locked.discard(ch)
            elif tol_lo <= sig <= tol_hi:
                logger.info("  %s: %.0f counts (%.1f%%) [OK] locked", ch.upper(), sig, pct)
                locked.add(ch)
            else:
                ratio = target / sig if sig > 0 else 1.0
                ratio = max(MIN_RATIO, min(MAX_RATIO, ratio))
                new_led = max(1, min(255, int(round(leds[ch] * ratio))))
                logger.info("  %s: %.0f counts (%.1f%%) -> LED %d->%d", ch.upper(), sig, pct, leds[ch], new_led)
                leds[ch] = new_led
                locked.discard(ch)

        if len(locked) == len(ch_list):
            logger.info("  All channels locked after %d iterations", iteration)
            break

    logger.info("%s final LEDs: %s", label, leds)
    return leds, signals, iteration
