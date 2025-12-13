"""Servo control with optimized speed presets for polarizer calibration.

Three speed modes optimized for servo calibration workflow:
- COARSE: 20-position sweep (12-¶ steps) - initial S-position finding (2s sweep)
- MEDIUM: 30-position sweep (6-¶ steps) - P-position refinement (1.5s sweep)
- FINE: 60-position sweep (3-¶ steps) - precise P-position detection (4.5s sweep)

Total calibration time: <20 seconds (including 2 sweeps + refinement)
"""

import time
from typing import Optional, Dict, List
from affilabs.utils.logger import logger


# Speed preset configurations for servo calibration
SPEED_PRESETS = {
    'coarse': {
        'description': '20-position sweep for initial S-finding',
        'step_size': 12,  # 240-¶/20 = 12-¶ per step (0-240-¶ range)
        'step_delay': 0.1,  # 100ms per position
        'range': (0, 240),  # Extended range to cover full rotation
        'positions': 20,
        'sweep_time': 2.0,  # 20 positions +˘ 100ms = 2 seconds
        'use_case': 'Fast initial sweep to locate S-position peak'
    },
    'medium': {
        'description': '30-position sweep for P-position refinement',
        'step_size': 6,  # 180-¶/30 = 6-¶ per step
        'step_delay': 0.05,  # 50ms per position (2x faster)
        'range': (0, 180),
        'positions': 30,
        'sweep_time': 1.5,  # 30 positions +˘ 50ms = 1.5 seconds
        'use_case': 'Medium sweep around expected P-position (-¶15-¶)'
    },
    'fine': {
        'description': '60-position sweep for precise P-position detection',
        'step_size': 3,  # 180-¶/60 = 3-¶ per step
        'step_delay': 0.075,  # 75ms per position (2x faster than before)
        'range': (0, 180),
        'positions': 60,
        'sweep_time': 4.5,  # 60 positions +˘ 75ms = 4.5 seconds
        'use_case': 'Fine sweep for precise circular/barrel P-position (-¶5-6-¶)'
    },
    'fast': {
        'description': 'Quick movement between known S/P positions',
        'step_size': 180,  # Jump directly to target
        'step_delay': 0.05,  # Minimal delay
        'range': (0, 180),
        'use_case': 'Normal SGÂˆP switching, rapid positioning (non-calibration)'
    }
}


def move_servo_with_speed(ctrl, start_angle: int, end_angle: int, speed: str = 'fast'):
    """Move servo with predefined speed preset.

    Args:
        ctrl: Controller instance
        start_angle: Starting angle (0-240 degrees for coarse, 0-180 for others)
        end_angle: Target angle (0-240 degrees for coarse, 0-180 for others)
        speed: Speed preset - 'coarse', 'medium', 'fine', or 'fast'

    Examples:
        # Fast SGÂ∆P switching
        move_servo_with_speed(ctrl, start_angle=10, end_angle=100, speed='fast')

        # Coarse sweep for initial S-finding (0-240-¶)
        move_servo_with_speed(ctrl, start_angle=0, end_angle=240, speed='coarse')

        # Medium sweep for P-position refinement
        move_servo_with_speed(ctrl, start_angle=5, end_angle=175, speed='medium')

        # Fine sweep for precise detection
        move_servo_with_speed(ctrl, start_angle=5, end_angle=175, speed='fine')
    """
    if speed not in SPEED_PRESETS:
        raise ValueError(f"Speed must be one of {list(SPEED_PRESETS.keys())}, got '{speed}'")

    preset = SPEED_PRESETS[speed]
    step_size = preset['step_size']
    step_delay = preset['step_delay']

    # Determine direction
    if end_angle > start_angle:
        angles = range(start_angle, end_angle + 1, step_size)
    else:
        angles = range(start_angle, end_angle - 1, -step_size)

    angles_list = list(angles)

    if speed == 'fast':
        # Fast mode: just jump to target
        logger.debug(f"G‹Ì Fast move: {start_angle}-¶ GÂ∆ {end_angle}-¶")
        ctrl.servo_move_calibration_only(s=end_angle, p=end_angle)
        ctrl.set_mode('s')
        time.sleep(0.6)
    else:
        # Medium/Slow mode: step through positions
        logger.info(f"=Éˆ‰ {speed.upper()} sweep: {start_angle}-¶ GÂ∆ {end_angle}-¶ ({len(angles_list)} steps)")

        for angle in angles_list:
            ctrl.servo_move_calibration_only(s=angle, p=angle)
            ctrl.set_mode('s')
            time.sleep(step_delay)

        # Ensure we end exactly at target
        if angles_list[-1] != end_angle:
            ctrl.servo_move_calibration_only(s=end_angle, p=end_angle)
            ctrl.set_mode('s')
            time.sleep(step_delay)


def sweep_for_calibration(ctrl, usb, min_angle: int = 5, max_angle: int = 175,
                         speed: str = 'medium', measurement_callback=None) -> Dict:
    """Perform servo sweep for calibration with speed-optimized measurement.

    Args:
        ctrl: Controller instance
        usb: Spectrometer instance
        min_angle: Start angle (default 5-¶)
        max_angle: End angle (default 175-¶)
        speed: 'medium' (60 positions) or 'slow' (30 positions)
        measurement_callback: Optional function(angle, spectrum, signal)

    Returns:
        dict: {
            'angles': List[int],
            'intensities': List[float],
            'positions': int,
            'duration': float
        }

    Examples:
        # Coarse calibration (30 positions, ~3 seconds)
        result = sweep_for_calibration(ctrl, usb, speed='medium')

        # Fine calibration (60 positions, ~9 seconds)
        result = sweep_for_calibration(ctrl, usb, speed='slow')
    """
    if speed not in ['medium', 'slow']:
        raise ValueError("Calibration sweep must use 'medium' or 'slow' speed")

    preset = SPEED_PRESETS[speed]
    step_size = preset['step_size']
    step_delay = preset['step_delay']

    # Calculate sweep parameters
    angles = list(range(min_angle, max_angle + 1, step_size))
    num_positions = len(angles)
    estimated_time = num_positions * step_delay

    logger.info("=" * 80)
    logger.info(f"SERVO CALIBRATION SWEEP - {speed.upper()} MODE")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  Range: {min_angle}-¶ to {max_angle}-¶")
    logger.info(f"  Mode: {speed.upper()} ({preset['description']})")
    logger.info(f"  Step size: {step_size}-¶")
    logger.info(f"  Positions: {num_positions}")
    logger.info(f"  Estimated time: {estimated_time:.1f} seconds")
    logger.info("")

    start_time = time.perf_counter()
    intensities = []
    measured_angles = []

    for i, angle in enumerate(angles):
        # Move to position
        ctrl.servo_move_calibration_only(s=angle, p=angle)
        ctrl.set_mode('s')
        time.sleep(step_delay)

        # Take measurement
        spectrum = usb.read_intensity()
        if spectrum is None:
            logger.warning(f"  Angle {angle}-¶: No spectrum acquired")
            continue

        signal = float(spectrum.max())
        intensities.append(signal)
        measured_angles.append(angle)

        # Callback for real-time analysis
        if measurement_callback:
            measurement_callback(angle, spectrum, signal)

        # Progress update every 10 positions
        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{num_positions} positions measured")

    duration = time.perf_counter() - start_time

    logger.info("")
    logger.info(f"G£‡ Sweep complete:")
    logger.info(f"   Positions measured: {len(measured_angles)}")
    logger.info(f"   Duration: {duration:.1f} seconds")
    logger.info("")

    return {
        'angles': measured_angles,
        'intensities': intensities,
        'positions': len(measured_angles),
        'duration': duration,
        'speed': speed
    }


def switch_sp_mode(ctrl, target_mode: str, s_position: int, p_position: int):
    """Fast switch between known S and P positions.

    Args:
        ctrl: Controller instance
        target_mode: 's' or 'p'
        s_position: S position in degrees
        p_position: P position in degrees

    Example:
        # Quick switch to P-mode for live acquisition
        switch_sp_mode(ctrl, target_mode='p', s_position=10, p_position=100)

        # Quick switch back to S-mode for calibration
        switch_sp_mode(ctrl, target_mode='s', s_position=10, p_position=100)
    """
    target_angle = s_position if target_mode.lower() == 's' else p_position
    mode_name = 'S-mode' if target_mode.lower() == 's' else 'P-mode'

    logger.debug(f"G‹Ì Fast switch to {mode_name} ({target_angle}-¶)")

    # Use fast movement (direct jump)
    ctrl.servo_move_calibration_only(s=target_angle, p=target_angle)
    ctrl.set_mode(target_mode.lower())
    time.sleep(0.6)  # Standard settling time


def print_speed_guide():
    """Print usage guide for speed presets."""
    print("=" * 80)
    print("SERVO SPEED PRESETS GUIDE")
    print("=" * 80)
    print()

    for speed, config in SPEED_PRESETS.items():
        print(f"{speed.upper()} MODE:")
        print(f"  Description: {config['description']}")
        print(f"  Step size: {config['step_size']}-¶")
        print(f"  Step delay: {config['step_delay']*1000:.0f}ms")
        print(f"  Use case: {config['use_case']}")
        print()

    print("EXAMPLES:")
    print()
    print("# Fast SGÂˆP switching (known positions)")
    print("switch_sp_mode(ctrl, 'p', s_position=10, p_position=100)")
    print("GÂ∆ Takes ~0.6 seconds")
    print()
    print("# Medium sweep (30 positions for coarse calibration)")
    print("sweep_for_calibration(ctrl, usb, speed='medium')")
    print("GÂ∆ Takes ~3 seconds, measures at 30 positions")
    print()
    print("# Slow sweep (60 positions for fine calibration)")
    print("sweep_for_calibration(ctrl, usb, speed='slow')")
    print("GÂ∆ Takes ~9 seconds, measures at 60 positions")
    print()
    print("=" * 80)


if __name__ == "__main__":
    print_speed_guide()
