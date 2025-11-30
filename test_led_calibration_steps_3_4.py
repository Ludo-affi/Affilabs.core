"""Isolated LED Calibration Steps 3 and 4 Test"""

import logging
from typing import Dict, Tuple
import numpy as np
import time

# Use project calibration helpers for ROI and hardware interactions
try:
    from src.utils.calibration_6step import acquire_raw_spectrum, roi_signal
except Exception:
    acquire_raw_spectrum = None
    roi_signal = None

# Import reusable LED methods
try:
    from src.utils.led_methods import LEDconverge, LEDnormalizationintensity, DetectorParams as LedDetectorParams
except Exception:
    LEDconverge = None
    LEDnormalizationintensity = None
    LedDetectorParams = None

def _acquire_raw_spectrum_local(usb, ctrl, channel: str, led_intensity: int,
                                integration_time_ms: float | None = None,
                                num_scans: int = 1,
                                pre_led_delay_ms: float = 45.0,
                                post_led_delay_ms: float = 5.0,
                                use_batch_command: bool = False):
    try:
        if integration_time_ms is not None:
            usb.set_integration(integration_time_ms)
            time.sleep(0.010)
        if use_batch_command:
            vals = {'a':0,'b':0,'c':0,'d':0}
            vals[channel] = led_intensity
            ctrl.set_batch_intensities(**vals)
        else:
            ctrl.set_intensity(ch=channel, raw_val=led_intensity)
        time.sleep(pre_led_delay_ms/1000.0)
        spectrum = usb.read_intensity()
        if use_batch_command:
            ctrl.set_batch_intensities(a=0,b=0,c=0,d=0)
        else:
            ctrl.set_intensity(ch=channel, raw_val=0)
        time.sleep(post_led_delay_ms/1000.0)
        return spectrum
    except Exception as e:
        logger.error(f"Acquire failed for {channel}: {e}")
        return None

def _roi_signal_local(spectrum: np.ndarray, wave_min_index: int, wave_max_index: int, method: str = 'median', top_n: int | None = None) -> float:
    roi = spectrum[wave_min_index:wave_max_index]
    if roi is None or len(roi) == 0:
        return 0.0
    if top_n is not None and top_n > 0:
        # Take average of top-N strongest pixels in ROI
        n = min(top_n, len(roi))
        # Partial sort for performance
        top_vals = np.partition(roi, -n)[-n:]
        return float(np.mean(top_vals))
    if method == 'median':
        return float(np.median(roi))
    return float(np.mean(roi))

def load_oem_polarizer_positions_local(device_config: dict, detector_serial: str) -> Dict[str, int]:
    """Load S/P servo positions from device_config dict with safe fallbacks.

    Looks in `hardware.servo_s_position`/`hardware.servo_p_position`, then
    `oem_calibration.polarizer_s_position`/`polarizer_p_position`, then
    `polarizer.s_position`/`p_position`. Falls back to S=120, P=60 with warning.
    """
    # Normalize to dict
    cfg = device_config if isinstance(device_config, dict) else {}
    s_pos = None
    p_pos = None
    if 'hardware' in cfg:
        s_pos = cfg['hardware'].get('servo_s_position')
        p_pos = cfg['hardware'].get('servo_p_position')
    if s_pos is None or p_pos is None:
        oem = cfg.get('oem_calibration', {})
        s_pos = oem.get('polarizer_s_position', s_pos)
        p_pos = oem.get('polarizer_p_position', p_pos)
    if s_pos is None or p_pos is None:
        pol = cfg.get('polarizer', {})
        s_pos = pol.get('s_position', s_pos)
        p_pos = pol.get('p_position', p_pos)
    if s_pos is None or p_pos is None:
        logger.warning("⚠️ OEM servo positions not found in device_config; using defaults S=120°, P=60°")
        s_pos, p_pos = 120, 60
    return {'s_position': int(s_pos), 'p_position': int(p_pos)}

def servo_initiation_to_s(ctrl, device_config: dict, detector_serial: str) -> Dict[str, int]:
    """Initialize servo for S-mode using device_config positions.

    - Reads S/P positions from device_config via `load_oem_polarizer_positions_local`
    - Parks to 1° quietly
    - Moves explicitly to S-position
    - Locks S-mode via firmware command (uses EEPROM positions)

    Returns the positions dict `{s_position, p_position}` for logging/verification.
    Raises on hard failure to ensure fail-fast behavior.
    """
    positions = load_oem_polarizer_positions_local(device_config, detector_serial)
    s_pos = positions["s_position"]
    p_pos = positions["p_position"]
    try:
        # Ensure LEDs are OFF before moving servo
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass
        # Park to 1°, then move to S/P explicit positions if supported
        if hasattr(ctrl, 'servo_move_calibration_only'):
            logger.info("Parking polarizer to 1° (quiet reset)...")
            ok1 = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.50)
            logger.info(f"Moving polarizer to S/P positions S={s_pos}°, P={p_pos}° explicitly...")
            ok2 = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(0.50)
            if not (ok1 and ok2):
                raise RuntimeError("Servo pre-position sequence did not confirm moves")
        else:
            logger.warning("Controller lacks calibration-only servo move; skipping explicit pre-positioning")
        # Lock S-mode via firmware (uses EEPROM positions written at startup)
        ok3 = ctrl.set_mode('s')
        time.sleep(0.30)
        if not ok3:
            raise RuntimeError("Firmware S-mode lock (ss) did not confirm")
        logger.info("S-mode active; LEDs off and servo positioned for S")
        return positions
    except Exception as e:
        logger.error(f"Servo initiation failed: {e}")
        # Attempt normal S-mode switch as fallback
        try:
            ctrl.set_mode('s')
            time.sleep(0.30)
            logger.info("Fallback: S-mode active via firmware")
            return positions
        except Exception as e2:
            logger.error(f"Fallback S-mode failed: {e2}")
            raise

def servo_move_1_then(ctrl, s_target: int, p_target: int) -> bool:
    """Simple servo helper: park to 1°, then move to provided S/P targets.

    No device_config lookup. Intended for mid-run moves where positions are
    already known. Returns True if both moves reported success, else False.
    """
    try:
        if hasattr(ctrl, 'servo_move_calibration_only'):
            ok1 = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.30)
            ok2 = ctrl.servo_move_calibration_only(s=int(s_target), p=int(p_target))
            time.sleep(0.30)
            return bool(ok1 and ok2)
        # Fallback: if calibration-only not available, attempt set_mode lock to S/P
        # Note: This path does not guarantee explicit angles.
        return False
    except Exception as e:
        logger.warning(f"servo_move_1_then failed: {e}")
        return False

def resolve_device_config_for_detector(usb) -> dict:
    """Locate and return the device-specific config dict for the connected detector.

    - Reads global config via `src.utils.common.get_config`
    - Matches by detector serial if the config system supports multiple devices
    - Returns a dict with at least `hardware.servo_s_position`/`servo_p_position` present

    If specific device entries are not supported, returns the single config dict.
    """
    try:
        from src.utils.common import get_config
        cfg = get_config()
        # If cfg already contains hardware positions, return it
        if isinstance(cfg, dict):
            hw = cfg.get('hardware', {})
            if 'servo_s_position' in hw and 'servo_p_position' in hw:
                return cfg
        # Fallback: construct minimal dict with defaults
        return {'hardware': {'servo_s_position': 120, 'servo_p_position': 60}}
    except Exception as e:
        logger.warning(f"resolve_device_config_for_detector failed: {e}")
        return {'hardware': {'servo_s_position': 120, 'servo_p_position': 60}}

logger = logging.getLogger("steps_3_4_test")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

class DetectorParams:
    def __init__(self, max_counts: float, saturation_threshold: float, min_integration_time: float, max_integration_time: float):
        self.max_counts = max_counts
        self.saturation_threshold = saturation_threshold
        self.min_integration_time = min_integration_time
        self.max_integration_time = max_integration_time

def get_detector_params(usb) -> DetectorParams:
    # Try attributes, else fall back to reasonable defaults
    max_counts = getattr(usb, 'max_counts', 65535)
    saturation_threshold = getattr(usb, 'saturation_threshold', int(max_counts*0.90))
    # Integration time in ms bounds
    min_int = getattr(usb, 'min_integration_ms', 5.0)
    max_int = getattr(usb, 'max_integration_ms', 1000.0)
    return DetectorParams(max_counts, saturation_threshold, min_int, max_int)

def _set_integration_and_log(usb, requested_ms: float):
    try:
        usb.set_integration(requested_ms)
        time.sleep(0.010)
        applied = None
        # Prefer explicit getter if available
        if hasattr(usb, 'get_integration_ms'):
            try:
                applied = float(usb.get_integration_ms())
            except Exception:
                applied = None
        # Fallback: attribute snapshot some drivers expose
        if applied is None and hasattr(usb, 'integration_ms'):
            try:
                applied = float(getattr(usb, 'integration_ms'))
            except Exception:
                applied = None
        if applied is not None:
            logger.info(f"Integration set: requested={requested_ms:.2f} ms, applied={applied:.2f} ms")
        else:
            logger.info(f"Integration set: requested={requested_ms:.2f} ms (applied unknown)")
    except Exception as e:
        logger.warning(f"Failed to set integration {requested_ms:.2f} ms: {e}")

def determine_channel_list(device_type: str, single_mode: bool, single_ch: str) -> list[str]:
    if single_mode:
        return [single_ch]
    return ['a','b','c','d']

def switch_mode_safely(ctrl, mode: str, turn_off_leds: bool=True):
    try:
        # Set mode and allow servo to settle
        ctrl.set_mode(mode)
        time.sleep(0.150)
        if turn_off_leds:
            # Send LED off and verify (if firmware supports query)
            ctrl.turn_off_channels()
            time.sleep(0.050)
            if hasattr(ctrl, 'get_all_led_intensities'):
                try:
                    led_state = ctrl.get_all_led_intensities()
                    # Treat intensity <=1 as off (firmware tolerance), ignore 'd' if -1
                    channels_to_check = {ch: val for ch, val in led_state.items() if ch != 'd' and val is not None}
                    all_off = all(int(val) <= 1 for val in channels_to_check.values()) if channels_to_check else True
                    if not all_off:
                        logger.warning(f"⚠️ LED off verification failed: {led_state}")
                        # Retry once
                        ctrl.turn_off_channels()
                        time.sleep(0.100)
                        led_state2 = ctrl.get_all_led_intensities()
                        channels_to_check2 = {ch: val for ch, val in led_state2.items() if ch != 'd' and val is not None}
                        all_off2 = all(int(val) <= 1 for val in channels_to_check2.values()) if channels_to_check2 else True
                        if not all_off2:
                            raise RuntimeError(f"LEDs did not turn off after retries: {led_state2}")
                except Exception as e:
                    logger.warning(f"LED off verification unavailable/failed: {e}")
    except Exception as e:
        logger.error(f"Failed to set mode {mode}: {e}")
        raise

def count_saturated_pixels(spectrum: np.ndarray, wave_min_index: int, wave_max_index: int, saturation_threshold: float) -> int:
    roi = spectrum[wave_min_index:wave_max_index]
    return int(np.sum(roi >= saturation_threshold))

def converge_integration_time(usb, ctrl, ch_list: list, led_intensities: Dict[str,int], initial_integration_ms: float,
                              target_percent: float, tolerance_percent: float, detector_params: DetectorParams,
                              wave_min_index: int, wave_max_index: int, max_iterations: int=5, step_name: str='Step 4') -> Tuple[float, Dict[str,float], bool]:
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    min_sig = (target_percent - tolerance_percent) * detector_max
    max_sig = (target_percent + tolerance_percent) * detector_max
    current = initial_integration_ms
    last_signals: Dict[str,float] = {}
    for i in range(max_iterations):
        usb.set_integration(current)
        time.sleep(0.010)
        signals: Dict[str,float] = {}
        saturated_any = False
        sat_per_ch: Dict[str,int] = {}
        for ch in ch_list:
            spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(usb, ctrl, ch, led_intensities[ch], current, 1, 45.0, 5.0, False)
            if spec is None:
                continue
            # Use average of top-50 strongest ROI pixels to drive optimization
            sig = (roi_signal or _roi_signal_local)(spec, wave_min_index, wave_max_index, method='median', top_n=50)
            signals[ch] = sig
            sat = count_saturated_pixels(spec, wave_min_index, wave_max_index, detector_params.saturation_threshold)
            sat_per_ch[ch] = sat
            saturated_any = saturated_any or (sat>0)
            logger.info(f"{step_name} iter {i+1}: S-{ch.upper()} top50 {sig:.0f} counts ({sig/detector_max*100:.1f}%) {'SAT' if sat>0 else 'OK'} (sat_px={sat})")

        # Log saturation trend totals
        if sat_per_ch:
            total_sat = sum(sat_per_ch.values())
            logger.info(f"{step_name} iter {i+1}: total_saturated_pixels={total_sat} per_channel={sat_per_ch}")
        if signals and all(min_sig <= signals[ch] <= max_sig for ch in signals) and not saturated_any:
            return current, signals, True
        # Per-channel LED correction at fixed time to steer toward target (furthest-first prioritization)
        if signals:
            # Rank channels by absolute error from target
            errors = {ch: abs(signals[ch] - target) for ch in ch_list if ch in signals}
            ranked = sorted(errors.items(), key=lambda kv: kv[1], reverse=True)
            furthest = {ch for ch, _ in ranked[:2]}  # top-2 furthest channels
            for ch, sig in signals.items():
                if min_sig <= sig <= max_sig:
                    continue
                # Larger adjustment bounds for furthest channels; smaller for others
                lower, upper = (0.80, 1.20) if ch in furthest else (0.92, 1.08)
                desired_ratio = target / sig if sig > 0 else 1.0
                desired_ratio = max(lower, min(upper, desired_ratio))
                new_int = int(max(10, min(255, led_intensities[ch] * desired_ratio)))
                # Additional reduction if saturated
                if sat_per_ch.get(ch, 0) > 0:
                    new_int = int(max(10, min(255, new_int * 0.85)))
                if new_int != led_intensities[ch]:
                    logger.info(f"{step_name} iter {i+1}: adjust LED {ch.upper()} {led_intensities[ch]} → {new_int} ({'furthest' if ch in furthest else 'normal'})")
                    led_intensities[ch] = new_int

        # adjust integration modestly based on MEDIAN to reduce bias from stronger channels
        avg = np.median(list(signals.values())) if signals else target
        if saturated_any:
            current *= 0.95
        else:
            factor = target/avg if avg>0 else 1.0
            factor = max(0.95, min(1.05, factor))
            current *= factor
        current = max(detector_params.min_integration_time, min(detector_params.max_integration_time, current))
    return current, signals, False

# Attempt to import typical app initialization (controller + usb)
try:
    from src.core.hardware_manager import HardwareManager  # if exists in project
except Exception:
    HardwareManager = None


def _init_hardware():
    """Initialize controller and spectrometer.

    Preferred: use HardwareManager if present. Otherwise, directly open real hardware
    (PicoP4SPR controller and USB4000 spectrometer) and load `device_config` via `get_config`.
    All paths fail fast with clear errors if any prerequisite is missing.
    """
    # Try HardwareManager path
    if HardwareManager is not None:
        hm = HardwareManager()
        hm.scan_and_connect()
        t0 = time.time()
        while time.time() - t0 < 5.0:
            if hm.ctrl and hm.usb:
                break
            time.sleep(0.25)
        usb = hm.usb
        ctrl = hm.ctrl
        device_config = getattr(hm, 'device_config', None)
        if usb and ctrl and device_config:
            return usb, ctrl, device_config
        # If HM didn’t yield all pieces, fall through to direct init

    # Direct real-hardware init (no mocks)
    try:
        from src.utils.controller import PicoP4SPR
        ctrl = PicoP4SPR()
        if not ctrl.open():
            logger.error("❌ Controller not connected (PicoP4SPR open failed)")
            return None, None, None
    except Exception as e:
        logger.error(f"❌ Controller init failed: {e}")
        return None, None, None

    try:
        from src.utils.usb4000_wrapper import USB4000
        usb = USB4000()
        if not usb.open():
            logger.error("❌ Spectrometer not connected (USB4000 open failed)")
            return None, None, None
    except Exception as e:
        logger.error(f"❌ Spectrometer init failed: {e}")
        return None, None, None

    # Load device_config (allow fallback positions if missing)
    try:
        from src.utils.common import get_config
        from src.settings.settings import CONFIG_FILE
        device_config = get_config()
        logger.info(f"Device config path: {CONFIG_FILE}")
        if isinstance(device_config, dict):
            logger.info(f"device_config top-level keys: {list(device_config.keys())}")
            logger.info(f"device_config.hardware before check: {device_config.get('hardware', {})}")
        hardware = device_config.get('hardware', {}) if isinstance(device_config, dict) else {}
        if not hardware or ('servo_s_position' not in hardware or 'servo_p_position' not in hardware):
            logger.warning("⚠️ device_config missing 'hardware.servo_s_position'/'servo_p_position' — using safe defaults (S=120°, P=60°)")
            # Inject fallback positions into a minimal hardware dict
            if isinstance(device_config, dict):
                device_config.setdefault('hardware', {})
                device_config['hardware'].setdefault('servo_s_position', 120)
                device_config['hardware'].setdefault('servo_p_position', 60)
                logger.info(f"device_config.hardware after fallback: {device_config['hardware']}")
            else:
                # Non-dict config; create a minimal dict
                device_config = {'hardware': {'servo_s_position': 120, 'servo_p_position': 60}}
    except Exception as e:
        logger.error(f"❌ Failed to load device_config: {e}")
        return None, None, None

    return usb, ctrl, device_config


def run_steps_3_and_4(device_type: str = "P4SPR", single_mode: bool = False, single_ch: str = "a", use_per_channel_time: bool = False, tighten_final: bool = False):
    usb, ctrl, device_config = _init_hardware()
    if usb is None or ctrl is None or device_config is None:
        logger.error("❌ Hardware or device_config not initialized. Aborting test.")
        return

    # Display how servo positions are loaded and what they are
    detector_serial = getattr(usb, "serial", "UNKNOWN")
    positions = load_oem_polarizer_positions_local(device_config, detector_serial)
    s_pos = positions["s_position"]
    p_pos = positions["p_position"]

    logger.info("=" * 80)
    logger.info("POLARIZER POSITIONS (from device_config)")
    logger.info("=" * 80)
    logger.info(f"S-mode position: {s_pos}°")
    logger.info(f"P-mode position: {p_pos}°")
    logger.info("Controller set_mode('s'/'p') will use these preloaded EEPROM positions")
    logger.info("=" * 80 + "\n")

    # Determine channels
    ch_list = determine_channel_list(device_type, single_mode, single_ch)
    logger.info(f"Channels under test: {ch_list}")
    # Explicitly initiate servo to S-mode using detector-specific device_config positions
    try:
        # Resolve correct config for this detector if needed
        device_config_det = resolve_device_config_for_detector(usb)
        servo_initiation_to_s(ctrl, device_config_det, detector_serial)
    except Exception:
        logger.error("Fail-fast: servo initiation could not complete")
        return

    # Step 2 subset: read wavelengths to get ROI
    wave_data = usb.read_wavelength()
    if wave_data is None or len(wave_data) == 0:
        logger.error("Failed to read wavelength data.")
        return
    import numpy as np
    from settings import MIN_WAVELENGTH, MAX_WAVELENGTH, LED_DELAY
    wave_min_index = int(np.searchsorted(wave_data, MIN_WAVELENGTH))
    wave_max_index = int(np.searchsorted(wave_data, MAX_WAVELENGTH))

    # Detector params
    det_params = get_detector_params(usb)
    # Force lower bound to 5 ms to allow optimization for strong channels
    try:
        det_params.min_integration_time = 5.0
    except Exception:
        pass
    logger.info(f"Detector time bounds (forced min): {det_params.min_integration_time}–{det_params.max_integration_time} ms")
    detector_max = det_params.max_counts

    # Switch to S-mode explicitly to match Step 3/4
    switch_mode_safely(ctrl, "s", turn_off_leds=True)
    # Additional safety delay to avoid overlapping with servo motion
    time.sleep(0.100)

    # STEP 3A/3B/3C condensed: Rank brightness and compute normalized LEDs
    logger.info("=" * 80)
    logger.info("STEP 3: Brightness Ranking + Normalization (condensed)")
    logger.info("=" * 80)

    # Fixed ranking integration
    RANK_INT_MS = 70
    usb.set_integration(RANK_INT_MS)
    time.sleep(0.010)

    # Measure mean ROI at LED=51 (20%) for ranking
    test_led = 51
    channel_data = {}
    for ch in ch_list:
        ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        batch_vals = {c: (test_led if c == ch else 0) for c in ['a','b','c','d']}
        ctrl.set_batch_intensities(**batch_vals)
        time.sleep(LED_DELAY)
        spectrum = usb.read_intensity()
        if spectrum is None:
            logger.error(f"{ch.upper()}: read failed")
            continue
        roi = spectrum[wave_min_index:wave_max_index]
        mean_int = float(np.mean(roi))
        max_int = float(np.max(roi))
        channel_data[ch] = (mean_int, max_int)
        logger.info(f"{ch.upper()} ranking: mean={mean_int:.0f} max={max_int:.0f} @ LED={test_led}")

    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(LED_DELAY)

    ranked = sorted(channel_data.items(), key=lambda kv: kv[1][0])
    weakest_ch = ranked[0][0]
    weakest_mean = ranked[0][1][0]

    logger.info("\nRanking (weakest → strongest):")
    for i,(ch,(m,_)) in enumerate(ranked,1):
        ratio = m/weakest_mean if weakest_mean>0 else 1.0
        logger.info(f"  {i}. {ch.upper()} {m:.0f} counts ({ratio:.2f}× weakest)")

    # 3B: Compute integration using 3A data (linear scaling) instead of random midpoint
    target_pct = 0.40
    target_counts = int(target_pct * detector_max)
    # Use weakest_mean at LED=51, T=70ms to predict counts at LED=255
    weakest_ratio_to_255 = 255 / test_led
    predicted_weakest_counts_at_255_70ms = weakest_mean * weakest_ratio_to_255
    # Required scaling on time to reach target at LED=255
    if predicted_weakest_counts_at_255_70ms > 0:
        best_int = 70.0 * (target_counts / predicted_weakest_counts_at_255_70ms)
    else:
        best_int = 70.0
    # Clamp to detector bounds
    best_int = max(det_params.min_integration_time, min(det_params.max_integration_time, best_int))
    usb.set_integration(best_int)
    time.sleep(0.010)
    logger.info(f"Step 3B: Computed integration from 3A data → {best_int:.1f} ms (target {target_counts}, predicted at 255 was {predicted_weakest_counts_at_255_70ms:.0f})")

    # Guard: Step 3B must never saturate. Validate weakest at LED=255 and scale down time proportionally
    # to saturation severity (saturation intensity ∝ number of saturated ROI pixels).
    validation_spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
        usb, ctrl, weakest_ch, 255, best_int, 1, LED_DELAY*1000, 10.0, False
    )
    if validation_spec is not None:
        sat_px = count_saturated_pixels(validation_spec, wave_min_index, wave_max_index, det_params.saturation_threshold)
        roi_len = max(1, (wave_max_index - wave_min_index))
        if sat_px > 0:
            sat_ratio = sat_px / roi_len
            # Proportional reduction: stronger reduction with higher saturation ratio
            # Reduce integration by factor f = 1 - clamp(sat_ratio * 1.5, 0.1..0.8)
            reduction = min(0.8, max(0.1, sat_ratio * 1.5))
            new_int = best_int * (1.0 - reduction)
            logger.warning(f"3B saturation detected on weakest @255: {sat_px}/{roi_len} px (ratio={sat_ratio:.3f}) → reducing integration by {reduction*100:.1f}% to {new_int:.1f} ms")
            best_int = max(det_params.min_integration_time, new_int)
            usb.set_integration(best_int)
            time.sleep(0.010)
            # Recheck once
            validation_spec2 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                usb, ctrl, weakest_ch, 255, best_int, 1, LED_DELAY*1000, 10.0, False
            )
            if validation_spec2 is not None:
                sat_px2 = count_saturated_pixels(validation_spec2, wave_min_index, wave_max_index, det_params.saturation_threshold)
                if sat_px2 > 0:
                    sat_ratio2 = sat_px2 / roi_len
                    logger.warning(f"3B still saturated ({sat_px2}/{roi_len}, ratio={sat_ratio2:.3f}) after reduction; consider further time reduction or lowering LED")
    else:
        logger.warning("3B validation spectrum unavailable; proceeding with computed integration")

    # 3C: Path selection
    # If using per-channel time strategy, freeze LEDs at 255 now; otherwise compute normalized LEDs.
    channel_measurements = {ch: (mean, _max) for ch,(mean,_max) in ranked}
    if use_per_channel_time:
        normalized_leds = {ch: 255 for ch in ch_list}
        logger.info("3C: Using per-channel time strategy — LEDs frozen at 255")
    else:
        # Use inverse of brightness ratios (relative to weakest) to equalize counts at fixed time
        if LEDnormalizationintensity:
            normalized_leds = LEDnormalizationintensity(channel_measurements, weakest_mean, min_led=10, max_led=255)
        else:
            normalized_leds = {}
            for ch,(mean,_max) in ranked:
                brightness_ratio = mean / weakest_mean if weakest_mean>0 else 1.0
                led_val = int(255 / brightness_ratio)
                led_val = max(10, min(255, led_val))
                normalized_leds[ch] = led_val
        for ch,(mean,_max) in ranked:
            ratio = mean / weakest_mean if weakest_mean>0 else 1.0
            logger.info(f"3C {ch.upper()}: ratio {ratio:.2f} → LED={normalized_leds[ch]}")

    # Labeling signals: we will log per-channel top-50 ROI average and percentage
    logger.info("\nSignal Labeling (S-mode, ROI median):")
    sat_thresh = det_params.saturation_threshold
    for ch in ch_list:
        spectrum = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
            usb, ctrl, ch, normalized_leds[ch], best_int, 1, LED_DELAY*1000, 10.0, False
        )
        if spectrum is None:
            continue
        roi = spectrum[wave_min_index:wave_max_index]
        signal = (roi_signal or _roi_signal_local)(roi, 0, len(roi), method="median", top_n=50)
        pct = (signal / detector_max) * 100.0
        sat_px = count_saturated_pixels(roi, 0, len(roi), sat_thresh)
        status = "SAT" if sat_px>0 else "OK"
        # If saturated, reduce this channel's LED intensity proportionally and re-measure once
        if sat_px > 0:
            roi_len = max(1, len(roi))
            sat_ratio = sat_px / roi_len
            reduction = min(0.8, max(0.1, sat_ratio * 1.5))
            new_led = max(10, int(normalized_leds[ch] * (1.0 - reduction)))
            logger.warning(f"{ch.upper()} saturated ({sat_px}/{roi_len}, ratio={sat_ratio:.3f}) → reducing LED by {reduction*100:.1f}% from {normalized_leds[ch]} to {new_led}")
            normalized_leds[ch] = new_led
            spectrum = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                usb, ctrl, ch, normalized_leds[ch], best_int, 1, LED_DELAY*1000, 10.0, False
            )
            if spectrum is not None:
                roi = spectrum[wave_min_index:wave_max_index]
                signal = (roi_signal or _roi_signal_local)(roi, 0, len(roi), method="median", top_n=50)
                pct = (signal / detector_max) * 100.0
                sat_px = count_saturated_pixels(roi, 0, len(roi), sat_thresh)
                status = "SAT" if sat_px>0 else "OK"
        logger.info(f"S-{ch.upper()} @ LED={normalized_leds[ch]}: top50={signal:.0f} counts ({pct:.1f}%) {status}")

    # If requested, run alternative normalization: per-channel integration times at LED=255
    per_channel_time_results = None
    if use_per_channel_time and hasattr(__import__('src.utils.led_methods', fromlist=['LEDnormalizationtime']), 'LEDnormalizationtime'):
        try:
            from src.utils.led_methods import LEDnormalizationtime
            logger.info("\nUsing alternative normalization path: per-channel integration at LED=255")
            per_times = LEDnormalizationtime(
                usb=usb,
                ctrl=ctrl,
                ch_list=ch_list,
                acquire_raw_spectrum_fn=(acquire_raw_spectrum or _acquire_raw_spectrum_local),
                roi_signal_fn=(roi_signal or _roi_signal_local),
                target_percent=0.80,
                tolerance_percent=0.025,
                detector_params=det_params,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                logger=logger,
                tighten_final=tighten_final,
            )
            # Measure signals at LED=255 with computed per-channel times
            per_channel_time_results = {}
            for ch in ch_list:
                Tch = float(per_times.get(ch, best_int))
                spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                    usb, ctrl, ch, 255, Tch, 1, LED_DELAY*1000, 10.0, False
                )
                if spec is None:
                    continue
                sig = (roi_signal or _roi_signal_local)(spec, wave_min_index, wave_max_index, method='median', top_n=50)
                sat = count_saturated_pixels(spec, wave_min_index, wave_max_index, det_params.saturation_threshold)
                final_led_val = 255
                if sat > 0 and abs(Tch - det_params.min_integration_time) <= 0.5:
                    # Reduce LED to clear saturation at minimum time, using math to meet target
                    # scale = clamp(target/signal, 0.30..0.95)
                    target_counts_local = 0.80 * detector_max
                    scale = max(0.30, min(0.95, (target_counts_local / sig) if sig > 0 else 0.5))
                    new_led = int(max(10, min(255, round(255 * scale))))
                    logger.info(f"Per-channel time: {ch.upper()} saturated at min time {Tch:.1f}ms — reducing LED 255→{new_led}")
                    final_led_val = new_led
                    spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                        usb, ctrl, ch, final_led_val, Tch, 1, LED_DELAY*1000, 10.0, False
                    )
                    if spec is not None:
                        sig = (roi_signal or _roi_signal_local)(spec, wave_min_index, wave_max_index, method='median', top_n=50)
                        # Emergency saturation guard: if still saturated, further reduce LED
                        sat2 = count_saturated_pixels(spec, wave_min_index, wave_max_index, det_params.saturation_threshold)
                        if sat2 > 0:
                            # Further math-driven reduction toward target
                            target_counts_local = 0.80 * detector_max
                            scale2 = max(0.30, min(0.95, (target_counts_local / sig) if sig > 0 else 0.5))
                            new_led2 = int(max(10, min(255, round(255 * scale2))))
                            logger.info(f"Per-channel time: {ch.upper()} still saturated — further reducing LED {final_led_val}→{new_led2}")
                            final_led_val = new_led2
                            spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                                usb, ctrl, ch, final_led_val, Tch, 1, LED_DELAY*1000, 10.0, False
                            )
                            if spec is not None:
                                sig = (roi_signal or _roi_signal_local)(spec, wave_min_index, wave_max_index, method='median', top_n=50)
                per_channel_time_results[ch] = {
                    'final_led': int(final_led_val),
                    'final_integration_ms': Tch,
                    'final_top50_counts': float(sig),
                    'final_percentage': float((sig / detector_max * 100.0) if detector_max else 0.0),
                }
            logger.info("Per-channel integration results (LED=255): " + str(per_channel_time_results))
        except Exception as e:
            logger.warning(f"Alternative normalization (per-channel time) failed: {e}")

    # If per-channel time strategy is active, skip global convergence and compute per-channel results
    if per_channel_time_results:
        logger.info("\nSkipping global integration convergence (Step 4) — using per-channel integration times.")
        # Set outputs based on per-channel-time path and persist/plot below
        converged_int = None
        ch_signals = {ch: per_channel_time_results[ch]['final_top50_counts'] for ch in ch_list if ch in per_channel_time_results}
        ok = all(0.80*detector_max*0.975 <= ch_signals[ch] <= 0.80*detector_max*1.025 for ch in ch_signals)
    else:
        # STEP 4: Converge integration across all channels with frozen LEDs
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: S-Mode Integration Time Optimization (LEDs frozen)")
        logger.info("=" * 80)
        logger.info(f"Starting Step 4 with integration {best_int:.1f} ms and normalized LEDs {normalized_leds}")
        target_percent = 0.80
        tolerance = 0.025
        # Track saturation statistics across iterations
        saturation_history = []  # list of dicts per iter: {ch: sat_px}

        # Prefer reusable LEDconverge if available
        if LEDconverge:
            converged_int, ch_signals, ok = LEDconverge(
                usb=usb,
                ctrl=ctrl,
                ch_list=ch_list,
                led_intensities=normalized_leds,
                acquire_raw_spectrum_fn=(acquire_raw_spectrum or _acquire_raw_spectrum_local),
                roi_signal_fn=(roi_signal or _roi_signal_local),
                initial_integration_ms=best_int,
                target_percent=target_percent,
                tolerance_percent=tolerance,
                detector_params=det_params,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                max_iterations=5,
                step_name="Step 4",
                logger=logger,
            )
        else:
            converged_int, ch_signals, ok = converge_integration_time(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            led_intensities=normalized_leds,
            initial_integration_ms=best_int,
            target_percent=target_percent,
            tolerance_percent=tolerance,
            detector_params=det_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            max_iterations=5,
            step_name="Step 4",
            )
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: S-Mode Integration Time Optimization (LEDs frozen)")
    logger.info("=" * 80)
    logger.info(f"Starting Step 4 with integration {best_int:.1f} ms and normalized LEDs {normalized_leds}")
    target_percent = 0.80
    tolerance = 0.025
    # Track saturation statistics across iterations
    saturation_history = []  # list of dicts per iter: {ch: sat_px}

    # Prefer reusable LEDconverge if available
    if LEDconverge:
        converged_int, ch_signals, ok = LEDconverge(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            led_intensities=normalized_leds,
            acquire_raw_spectrum_fn=(acquire_raw_spectrum or _acquire_raw_spectrum_local),
            roi_signal_fn=(roi_signal or _roi_signal_local),
            initial_integration_ms=best_int,
            target_percent=target_percent,
            tolerance_percent=tolerance,
            detector_params=det_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            max_iterations=5,
            step_name="Step 4",
            logger=logger,
        )
    else:
        converged_int, ch_signals, ok = converge_integration_time(
        usb=usb,
        ctrl=ctrl,
        ch_list=ch_list,
        led_intensities=normalized_leds,
        initial_integration_ms=best_int,
        target_percent=target_percent,
        tolerance_percent=tolerance,
        detector_params=det_params,
        wave_min_index=wave_min_index,
        wave_max_index=wave_max_index,
        max_iterations=5,
        step_name="Step 4",
        )

    logger.info("\nStep 4 Result:")
    for ch, sig in ch_signals.items():
        pct = (sig / detector_max * 100.0) if detector_max else 0.0
        logger.info(f"  S-{ch.upper()}: {sig:.0f} counts ({pct:.1f}%)")
    if converged_int is not None:
        logger.info(f"Final S-mode integration: {converged_int:.1f} ms | Converged={ok}")
    else:
        logger.info(f"Per-channel-time strategy used | Within target window for all channels: {ok}")

    # Optional: summarize saturation trend if any were recorded
    try:
        # Recompute saturation per channel at final settings for summary
        sat_summary = {}
        for ch in ch_list:
            spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                usb, ctrl, ch, normalized_leds[ch], converged_int, 1, LED_DELAY*1000, 10.0, False
            )
            if spec is None:
                continue
            roi = spec[wave_min_index:wave_max_index]
            sat_summary[ch] = count_saturated_pixels(roi, 0, len(roi), det_params.saturation_threshold)
        total_sat = sum(sat_summary.values()) if sat_summary else 0
        logger.info(f"Saturation summary at final settings: total_saturated_pixels={total_sat} per_channel={sat_summary}")
    except Exception:
        pass

    # Final adjust-to-target step per channel: mathematically close gap within 1%
    logger.info("\nFinal per-channel fine-tune: math-driven gap closing per channel (<=1% error)")
    final_leds = normalized_leds.copy()
    per_channel_results: Dict[str, Dict[str, float]] = {}
    target_counts = target_percent * detector_max
    # Measure current signals at converged_int
    current_signals: Dict[str, float] = {}
    for ch in ch_list:
        T_for_measure = float(per_channel_time_results[ch]['final_integration_ms']) if per_channel_time_results else converged_int
        led_for_measure = int(per_channel_time_results[ch]['final_led']) if per_channel_time_results else final_leds[ch]
        spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
            usb, ctrl, ch, led_for_measure, T_for_measure, 1, LED_DELAY*1000, 10.0, False
        )
        if spec is None:
            continue
        sig = (roi_signal or _roi_signal_local)(spec, wave_min_index, wave_max_index, method='median', top_n=50)
        current_signals[ch] = sig
    # Try to bring each channel to target using proportional math
    for ch in ch_list:
        sig = current_signals.get(ch, 0.0)
        desired_min = target_counts * (1.0 - 0.01)
        desired_max = target_counts * (1.0 + 0.01)
        final_T_for_ch = float(per_channel_time_results[ch]['final_integration_ms']) if per_channel_time_results else converged_int
        final_led_for_ch = int(per_channel_time_results[ch]['final_led']) if per_channel_time_results else final_leds[ch]
        final_sig_for_ch = sig
        # If using per-channel time strategy, do not change LED from 255; adjust time only
        if per_channel_time_results:
            if sig < desired_min:
                exact_T = final_T_for_ch * (target_counts / sig) if sig > 0 else final_T_for_ch
                exact_T = min(det_params.max_integration_time, max(det_params.min_integration_time, exact_T))
                usb.set_integration(exact_T)
                time.sleep(0.010)
                spec3 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                    usb, ctrl, ch, final_led_for_ch, exact_T, 1, LED_DELAY*1000, 10.0, False
                )
                if spec3 is not None:
                    sig3 = (roi_signal or _roi_signal_local)(spec3, wave_min_index, wave_max_index, method='median', top_n=50)
                    final_sig_for_ch = sig3
                    final_T_for_ch = exact_T
            elif sig > desired_max:
                # Back off time modestly to reduce signal into window
                exact_T = final_T_for_ch * max(0.85, min(0.98, (target_counts / sig) if sig > 0 else 0.95))
                exact_T = max(det_params.min_integration_time, exact_T)
                usb.set_integration(exact_T)
                time.sleep(0.010)
                spec2 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                    usb, ctrl, ch, final_led_for_ch, exact_T, 1, LED_DELAY*1000, 10.0, False
                )
                if spec2 is not None:
                    final_sig_for_ch = (roi_signal or _roi_signal_local)(spec2, wave_min_index, wave_max_index, method='median', top_n=50)
                    # If still saturated at the apparent minimum, reduce LED aggressively
                    sat2 = count_saturated_pixels(spec2, wave_min_index, wave_max_index, det_params.saturation_threshold)
                    if sat2 > 0 and ch.lower() == 'c':
                        # Math-driven LED reduction toward target
                        scale_c = max(0.30, min(0.95, (target_counts / final_sig_for_ch) if final_sig_for_ch > 0 else 0.5))
                        new_led = int(max(10, min(255, round(final_led_for_ch * scale_c))))
                        logger.info(f"Final fine-tune: C saturated at min time — reducing LED {final_led_for_ch}→{new_led}")
                        final_led_for_ch = new_led
                        spec3 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                            usb, ctrl, ch, final_led_for_ch, exact_T, 1, LED_DELAY*1000, 10.0, False
                        )
                        if spec3 is not None:
                            final_sig_for_ch = (roi_signal or _roi_signal_local)(spec3, wave_min_index, wave_max_index, method='median', top_n=50)
                    final_T_for_ch = exact_T
        else:
            # Shared-integration path: allow LED proportional adjustments, then time if capped
            if sig < desired_min:
                ratio_needed = (target_counts / sig) if sig > 0 else 1.0
                proposed_led = int(min(255, max(10, round(final_led_for_ch * ratio_needed))))
                if proposed_led > final_led_for_ch:
                    final_led_for_ch = proposed_led
                    spec2 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                        usb, ctrl, ch, final_led_for_ch, final_T_for_ch, 1, LED_DELAY*1000, 10.0, False
                    )
                    if spec2 is not None:
                        final_sig_for_ch = (roi_signal or _roi_signal_local)(spec2, wave_min_index, wave_max_index, method='median', top_n=50)
                if final_sig_for_ch < desired_min and final_led_for_ch >= 255:
                    exact_T = final_T_for_ch * (target_counts / final_sig_for_ch) if final_sig_for_ch > 0 else final_T_for_ch
                    exact_T = min(det_params.max_integration_time, exact_T)
                    usb.set_integration(exact_T)
                    time.sleep(0.010)
                    spec3 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                        usb, ctrl, ch, final_led_for_ch, exact_T, 1, LED_DELAY*1000, 10.0, False
                    )
                    if spec3 is not None:
                        sig3 = (roi_signal or _roi_signal_local)(spec3, wave_min_index, wave_max_index, method='median', top_n=50)
                        final_sig_for_ch = sig3
                        final_T_for_ch = exact_T
            elif sig > desired_max:
                ratio_needed_down = (target_counts / sig) if sig > 0 else 1.0
                proposed_led = int(max(10, round(final_led_for_ch * ratio_needed_down)))
                if proposed_led < final_led_for_ch:
                    final_led_for_ch = proposed_led
                    spec2 = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                        usb, ctrl, ch, final_led_for_ch, final_T_for_ch, 1, LED_DELAY*1000, 10.0, False
                    )
                    if spec2 is not None:
                        final_sig_for_ch = (roi_signal or _roi_signal_local)(spec2, wave_min_index, wave_max_index, method='median', top_n=50)
        # Record results; restore global integration to converged_int for next channel
        if converged_int is not None:
            usb.set_integration(converged_int)
        time.sleep(0.005)
        final_leds[ch] = final_led_for_ch
        per_channel_results[ch] = {
            'final_led': int(final_led_for_ch),
            'final_integration_ms': float(final_T_for_ch),
            'final_top50_counts': float(final_sig_for_ch),
            'final_percentage': float((final_sig_for_ch / detector_max * 100.0) if detector_max else 0.0),
        }
    logger.info("Final per-channel results (post-adjust): " + str(per_channel_results))

    # If alternative path ran, persist and plot that as well for comparison
    if per_channel_time_results:
        try:
            import json, os
            out_dir = os.path.join(os.getcwd(), 'generated-files')
            os.makedirs(out_dir, exist_ok=True)
            out_path_alt = os.path.join(out_dir, 'step4_results_per_channel_time.json')
            payload_alt = {
                'mode': 'S',
                'strategy': 'per-channel-time@LED255',
                'target_percent': 0.80,
                'detector_max': detector_max,
                'results': per_channel_time_results,
            }
            with open(out_path_alt, 'w', encoding='utf-8') as f:
                json.dump(payload_alt, f, indent=2)
            logger.info(f"Saved per-channel-time results to {out_path_alt}")
        except Exception as e:
            logger.warning(f"Failed to save per-channel-time results: {e}")

        try:
            import os
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            channels = [ch.upper() for ch in ch_list]
            values = [per_channel_time_results[ch]['final_top50_counts'] for ch in ch_list]
            target_line = 0.80 * detector_max
            plt.figure(figsize=(8,4))
            plt.plot(channels, values, marker='o', label='Top-50 ROI counts (LED=255)')
            plt.axhline(target_line, color='green', linestyle='--', label='Target 80%')
            plt.title('Step 4 Results (S-mode) - Per-channel Time')
            plt.ylabel('Counts')
            plt.xlabel('Channel')
            plt.grid(True, alpha=0.3)
            plt.legend()
            out_png = os.path.join(os.getcwd(), 'generated-files', 'step4_plot_per_channel_time.png')
            plt.savefig(out_png, dpi=120, bbox_inches='tight')
            plt.close()
            logger.info(f"Saved per-channel-time plot to {out_png}")
        except Exception as e:
            logger.warning(f"Failed to create per-channel-time plot: {e}")

    # Persist per-channel integration and LED for Step 5
    try:
        import json, os
        out_dir = os.path.join(os.getcwd(), 'generated-files')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'step4_results.json')
        payload = {
            'mode': 'S',
            'target_percent': target_percent,
            'detector_max': detector_max,
            'results': per_channel_results,
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        logger.info(f"Saved Step 4 per-channel results to {out_path}")
    except Exception as e:
        logger.warning(f"Failed to save Step 4 results: {e}")

    # Plot each channel top-50 ROI counts on a single graph
    try:
        import os
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        channels = [ch.upper() for ch in ch_list]
        values = [per_channel_results[ch]['final_top50_counts'] for ch in ch_list]
        target_line = target_counts
        plt.figure(figsize=(8,4))
        plt.plot(channels, values, marker='o', label='Top-50 ROI counts')
        plt.axhline(target_line, color='green', linestyle='--', label=f'Target {int(target_percent*100)}%')
        plt.title('Step 4 Results (S-mode)')
        plt.ylabel('Counts')
        plt.xlabel('Channel')
        plt.grid(True, alpha=0.3)
        plt.legend()
        out_png = os.path.join(os.getcwd(), 'generated-files', 'step4_plot.png')
        plt.savefig(out_png, dpi=120, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved Step 4 plot to {out_png}")
    except Exception as e:
        logger.warning(f"Failed to create plot: {e}")

    # Spectral response plot (S-mode): counts over wavelength, all channels
    try:
        import os
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        wave = usb.read_wavelength()
        if wave is None or len(wave) == 0:
            raise RuntimeError('No wavelength data available')
        plt.figure(figsize=(10,5))
        for ch in ch_list:
            spec = (acquire_raw_spectrum or _acquire_raw_spectrum_local)(
                usb, ctrl, ch, int(per_channel_results[ch]['final_led']), float(per_channel_results[ch]['final_integration_ms']), 1, LED_DELAY*1000, 10.0, False
            )
            if spec is None:
                continue
            plt.plot(wave, spec, label=f"S-{ch.upper()} (LED={per_channel_results[ch]['final_led']}, T={per_channel_results[ch]['final_integration_ms']:.1f}ms)")
        plt.title('Spectral Response (S-mode): Counts vs Wavelength')
        plt.xlabel('Wavelength (nm)')
        plt.ylabel('Counts')
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        out_png2 = os.path.join(os.getcwd(), 'generated-files', 'step4_spectral_s.png')
        plt.savefig(out_png2, dpi=120, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved S-mode spectral plot to {out_png2}")
    except Exception as e:
        logger.warning(f"Failed to create spectral plot: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Isolated LED Calibration Steps 3 and 4 Test")
    parser.add_argument("--per-channel-time", action="store_true", help="Use per-channel integration time strategy (LEDs frozen at 255)")
    parser.add_argument("--tighten-final", action="store_true", help="Run one final math-driven tighten iteration in per-channel-time path")
    args = parser.parse_args()
    run_steps_3_and_4(use_per_channel_time=bool(args.per_channel_time), tighten_final=bool(args.tighten_final))
