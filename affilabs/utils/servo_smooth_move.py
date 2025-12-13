"""Smooth servo movement with intermediate steps for slow sweeps.

Since hobby servos can't control rotation speed directly, this module
creates smooth slow-motion movement by commanding intermediate positions.
"""

import time
from affilabs.utils.logger import logger


def smooth_servo_move(ctrl, start_angle: int, end_angle: int, step_size: int = 5, step_delay: float = 0.1):
    """Move servo smoothly through intermediate positions for slow sweep.

    Hobby servos always move at maximum speed to commanded position.
    To achieve "slow" movement, we command many small steps.

    Args:
        ctrl: Controller instance
        start_angle: Starting angle (0-180 degrees)
        end_angle: Target angle (0-180 degrees)
        step_size: Size of each step (degrees, default 5)
        step_delay: Delay between steps (seconds, default 0.1)

    Example:
        # Slow sweep from 10-ж to 170-ж for calibration
        smooth_servo_move(ctrl, start_angle=10, end_angle=170, step_size=3, step_delay=0.15)
        # Takes ~8 seconds for 160-ж sweep (53 steps +∙ 0.15s)

        # Fast sweep (default)
        smooth_servo_move(ctrl, start_angle=10, end_angle=170, step_size=10, step_delay=0.05)
        # Takes ~0.8 seconds for 160-ж sweep (16 steps +∙ 0.05s)
    """
    # Determine direction
    if end_angle > start_angle:
        angles = range(start_angle, end_angle + 1, step_size)
    else:
        angles = range(start_angle, end_angle - 1, -step_size)

    logger.info(f"=ГЎф Smooth servo move: {start_angle}-ж Gх╞ {end_angle}-ж (step={step_size}-ж, delay={step_delay*1000:.0f}ms)")

    for angle in angles:
        # Move to intermediate position
        ctrl.servo_move_calibration_only(s=angle, p=angle)
        ctrl.set_mode('s')
        time.sleep(step_delay)

    # Ensure we end exactly at target
    if list(angles)[-1] != end_angle:
        ctrl.servo_move_calibration_only(s=end_angle, p=end_angle)
        ctrl.set_mode('s')
        time.sleep(step_delay)

    logger.info(f"Gгр Reached {end_angle}-ж")


def sweep_with_measurements(ctrl, usb, start_angle: int, end_angle: int,
                           step_size: int = 5, step_delay: float = 0.1,
                           measurement_callback=None):
    """Perform slow servo sweep while taking measurements at each step.

    Args:
        ctrl: Controller instance
        usb: Spectrometer instance
        start_angle: Starting angle (degrees)
        end_angle: Target angle (degrees)
        step_size: Angle increment (degrees)
        step_delay: Time at each position (seconds)
        measurement_callback: Function(angle, spectrum) called at each step

    Returns:
        dict: {angle: spectrum} for all measured positions

    Example:
        def analyze_position(angle, spectrum):
            print(f"Angle {angle}-ж: max={spectrum.max():.0f}")

        results = sweep_with_measurements(
            ctrl, usb,
            start_angle=10, end_angle=170,
            step_size=5, step_delay=0.2,
            measurement_callback=analyze_position
        )
    """
    # Determine direction
    if end_angle > start_angle:
        angles = range(start_angle, end_angle + 1, step_size)
    else:
        angles = range(start_angle, end_angle - 1, -step_size)

    measurements = {}

    logger.info(f"=ГЎ╝ Servo sweep with measurements: {start_angle}-ж Gх╞ {end_angle}-ж")
    logger.info(f"   Steps: {len(list(angles))}, Time per step: {step_delay*1000:.0f}ms")

    for i, angle in enumerate(angles):
        # Move to position
        ctrl.servo_move_calibration_only(s=angle, p=angle)
        ctrl.set_mode('s')
        time.sleep(step_delay)  # Allow servo to settle and hold

        # Take measurement
        spectrum = usb.read_intensity()
        measurements[angle] = spectrum

        # Callback for real-time analysis
        if measurement_callback:
            measurement_callback(angle, spectrum)

        if (i + 1) % 10 == 0:
            logger.info(f"   Progress: {i+1}/{len(list(angles))} positions measured")

    logger.info(f"Gгр Sweep complete: {len(measurements)} measurements")
    return measurements


def slow_calibration_sweep(ctrl, usb, min_angle: int = 10, max_angle: int = 170,
                           step_size: int = 5, step_delay: float = 0.15):
    """Run full servo calibration with slow sweep for better measurements.

    This is a drop-in replacement for fast servo calibration that uses
    smooth slow movement for more stable optical measurements.

    Args:
        ctrl: Controller instance
        usb: Spectrometer instance
        min_angle: Minimum sweep angle (default 10-ж)
        max_angle: Maximum sweep angle (default 170-ж)
        step_size: Step size in degrees (default 5-ж - smaller = slower)
        step_delay: Hold time per position (default 0.15s)

    Returns:
        dict: Calibration results with S and P positions

    Example:
        # Ultra-slow sweep for noisy environments
        result = slow_calibration_sweep(ctrl, usb, step_size=3, step_delay=0.2)
        # Takes ~10 seconds for full sweep

        # Standard slow sweep
        result = slow_calibration_sweep(ctrl, usb, step_size=5, step_delay=0.15)
        # Takes ~5 seconds for full sweep
    """
    import numpy as np

    logger.info("=" * 80)
    logger.info("SLOW SERVO CALIBRATION SWEEP")
    logger.info("=" * 80)

    # Calculate sweep parameters
    num_steps = (max_angle - min_angle) // step_size + 1
    total_time = num_steps * step_delay
    logger.info(f"Configuration:")
    logger.info(f"  Range: {min_angle}-ж to {max_angle}-ж")
    logger.info(f"  Step size: {step_size}-ж")
    logger.info(f"  Steps: {num_steps}")
    logger.info(f"  Estimated time: {total_time:.1f} seconds")
    logger.info("")

    # Perform sweep with measurements
    intensities = []
    angles = []

    def collect_data(angle, spectrum):
        signal = spectrum.max()
        intensities.append(signal)
        angles.append(angle)
        logger.debug(f"  Angle {angle:3d}-ж: signal={signal:6.0f} counts")

    sweep_with_measurements(
        ctrl, usb,
        start_angle=min_angle,
        end_angle=max_angle,
        step_size=step_size,
        step_delay=step_delay,
        measurement_callback=collect_data
    )

    # Analyze results
    intensities = np.array(intensities)
    angles = np.array(angles)

    # Find S position (maximum signal)
    s_idx = np.argmax(intensities)
    s_angle = angles[s_idx]
    s_intensity = intensities[s_idx]

    # Find P position (minimum signal, 90-ж from S for circular polarizer)
    # Look for minimum in range [S-100 to S-80] or [S+80 to S+100]
    p_candidates = []
    for offset in [-90, 90]:
        p_target = s_angle + offset
        if min_angle <= p_target <= max_angle:
            # Find closest measured angle to target
            idx = np.argmin(np.abs(angles - p_target))
            p_candidates.append((angles[idx], intensities[idx]))

    if p_candidates:
        # Choose the one with lower intensity
        p_angle, p_intensity = min(p_candidates, key=lambda x: x[1])
    else:
        logger.error("Could not find valid P position 90-ж from S")
        return None

    logger.info("")
    logger.info("=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"S position: {s_angle}-ж (signal: {s_intensity:.0f} counts)")
    logger.info(f"P position: {p_angle}-ж (signal: {p_intensity:.0f} counts)")
    logger.info(f"S/P ratio: {s_intensity/p_intensity:.2f}")
    logger.info("")

    return {
        'success': True,
        's_position': int(s_angle),
        'p_position': int(p_angle),
        's_intensity': float(s_intensity),
        'p_intensity': float(p_intensity),
        'all_angles': angles.tolist(),
        'all_intensities': intensities.tolist()
    }
