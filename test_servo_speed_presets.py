"""Test servo speed presets for different use cases."""

import sys
import time
from utils.controller import Controller
from src.utils.servo_speed_presets import (
    move_servo_with_speed,
    switch_sp_mode,
    print_speed_guide,
    SPEED_PRESETS
)
from utils.logger import logger


def test_fast_switching(ctrl):
    """Test fast S↔P mode switching."""
    print("\n" + "=" * 80)
    print("TEST 1: FAST S↔P SWITCHING (Known Positions)")
    print("=" * 80)

    s_pos = 10
    p_pos = 100

    print(f"\nScenario: Quickly switch between S-mode ({s_pos}°) and P-mode ({p_pos}°)")
    print("Use case: Normal operation after calibration complete\n")

    # S → P
    start = time.perf_counter()
    switch_sp_mode(ctrl, target_mode='p', s_position=s_pos, p_position=p_pos)
    sp_time = time.perf_counter() - start
    print(f"S → P: {sp_time:.2f} seconds")

    time.sleep(1)

    # P → S
    start = time.perf_counter()
    switch_sp_mode(ctrl, target_mode='s', s_position=s_pos, p_position=p_pos)
    ps_time = time.perf_counter() - start
    print(f"P → S: {ps_time:.2f} seconds")

    print(f"\n✅ Fast switching: ~{(sp_time + ps_time)/2:.2f}s per switch")


def test_medium_sweep(ctrl):
    """Test medium speed sweep (30 positions)."""
    print("\n" + "=" * 80)
    print("TEST 2: MEDIUM SWEEP (60 Positions)")
    print("=" * 80)

    print("\nScenario: Coarse calibration sweep")
    print("Use case: Initial S/P position search, quick calibration\n")

    start_angle = 10
    end_angle = 170
    expected_positions = (end_angle - start_angle) // SPEED_PRESETS['medium']['step_size']

    print(f"Sweeping {start_angle}° → {end_angle}° with medium speed")
    print(f"Expected positions: ~{expected_positions}")

    start = time.perf_counter()
    move_servo_with_speed(ctrl, start_angle, end_angle, speed='medium')
    duration = time.perf_counter() - start

    print(f"\n✅ Medium sweep: {duration:.2f} seconds for ~{expected_positions} positions")
    print(f"   ({duration/expected_positions:.3f}s per position)")


def test_slow_sweep(ctrl):
    """Test slow speed sweep (60 positions)."""
    print("\n" + "=" * 80)
    print("TEST 3: SLOW SWEEP (30 Positions)")
    print("=" * 80)

    print("\nScenario: Fine calibration sweep")
    print("Use case: Precise S/P detection, stable optical measurements\n")

    start_angle = 10
    end_angle = 170
    expected_positions = (end_angle - start_angle) // SPEED_PRESETS['slow']['step_size']

    print(f"Sweeping {start_angle}° → {end_angle}° with slow speed")
    print(f"Expected positions: ~{expected_positions}")

    start = time.perf_counter()
    move_servo_with_speed(ctrl, start_angle, end_angle, speed='slow')
    duration = time.perf_counter() - start

    print(f"\n✅ Slow sweep: {duration:.2f} seconds for ~{expected_positions} positions")
    print(f"   ({duration/expected_positions:.3f}s per position)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_servo_speed_presets.py <COM_PORT>")
        print("Example: python test_servo_speed_presets.py COM5")
        print()
        print_speed_guide()
        sys.exit(1)

    com_port = sys.argv[1]

    print("=" * 80)
    print("SERVO SPEED PRESETS TEST")
    print("=" * 80)
    print(f"\nConnecting to controller on {com_port}...")

    try:
        ctrl = Controller()
        if not ctrl.connect(com_port):
            print(f"❌ Failed to connect to {com_port}")
            sys.exit(1)

        # Get firmware version
        version = ctrl.get_version()
        print(f"✅ Connected to firmware: {version}")

        # Run all tests
        test_fast_switching(ctrl)
        time.sleep(1)

        test_medium_sweep(ctrl)
        time.sleep(1)

        test_slow_sweep(ctrl)

        # Summary
        print("\n" + "=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)
        print()
        print("Speed Mode    | Positions | Est. Time | Use Case")
        print("-" * 80)
        print("FAST          | 1 (jump)  | ~0.6s     | S↔P switching, known positions")
        print("MEDIUM        | ~30       | ~3s       | Coarse calibration sweep")
        print("SLOW          | ~60       | ~9s       | Fine calibration sweep")
        print()
        print("Recommendation:")
        print("  • Use FAST for normal operation (S↔P switching)")
        print("  • Use MEDIUM for initial calibration (quick sweep)")
        print("  • Use SLOW for fine-tuning or verification")
        print()

        print("Disconnecting from controller...")
        ctrl.disconnect()
        print("✅ Test complete!")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
