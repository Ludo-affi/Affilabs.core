"""Test Acquisition Timing Based on Latest QC Calibration.

This script validates that the acquisition timing matches the calibration parameters.
It checks:
1. LED timing (ON period)
2. Detector timing (wait before, window duration)
3. Integration time vs num_scans fit
4. Pre-arm optimization
5. Total cycle time per channel
"""

import json
from pathlib import Path

# ANSI color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def load_latest_calibration():
    """Load the latest calibration parameters."""
    cal_path = Path("calibration_results/latest_calibration.json")
    if not cal_path.exists():
        print(f"{RED}✗ Calibration file not found: {cal_path}{RESET}")
        return None

    with open(cal_path) as f:
        return json.load(f)


def load_settings():
    """Load current settings from settings module."""
    try:
        import settings
        return {
            'LED_ON_TIME_MS': getattr(settings, 'LED_ON_TIME_MS', 250.0),
            'DETECTOR_WAIT_MS': getattr(settings, 'DETECTOR_WAIT_MS', 60.0),
            'SAFETY_BUFFER_MS': getattr(settings, 'SAFETY_BUFFER_MS', 10.0),
        }
    except ImportError:
        print(f"{YELLOW}⚠ Could not import settings, using defaults{RESET}")
        return {
            'LED_ON_TIME_MS': 250.0,
            'DETECTOR_WAIT_MS': 60.0,
            'SAFETY_BUFFER_MS': 10.0,
        }


def test_timing_validation(cal_data, settings):
    """Validate acquisition timing against calibration."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}ACQUISITION TIMING VALIDATION{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

    # Extract calibration parameters
    integration_time = cal_data['integration_times']['p_integration_time']
    num_scans = cal_data['timing_parameters']['num_scans']

    print(f"{BLUE}Calibration Parameters:{RESET}")
    print(f"  Integration Time: {integration_time:.1f} ms")
    print(f"  Num Scans: {num_scans}")

    print(f"\n{BLUE}Live Settings (Timing Architecture):{RESET}")
    print(f"  LED ON Time: {settings['LED_ON_TIME_MS']:.1f} ms")
    print(f"  Detector Wait: {settings['DETECTOR_WAIT_MS']:.1f} ms (before first read)")
    print(f"  Safety Buffer: {settings['SAFETY_BUFFER_MS']:.1f} ms")

    # Calculate timing windows
    seabreeze_overhead = 7.0  # ms per scan (USB + readout)
    single_read_time = integration_time + seabreeze_overhead
    total_acquisition_time = num_scans * single_read_time

    # Detection window = LED_ON - WAIT - BUFFER
    detector_on_time = settings['LED_ON_TIME_MS'] - settings['DETECTOR_WAIT_MS']
    detector_window = detector_on_time - settings['SAFETY_BUFFER_MS']

    print(f"\n{BLUE}Calculated Timing:{RESET}")
    print(f"  Single Read: {integration_time:.1f}ms integration + {seabreeze_overhead:.1f}ms overhead = {single_read_time:.1f}ms")
    print(f"  Total Acquisition: {num_scans} × {single_read_time:.1f}ms = {total_acquisition_time:.1f} ms")
    print(f"  Detector ON Time: {settings['LED_ON_TIME_MS']:.1f}ms - {settings['DETECTOR_WAIT_MS']:.1f}ms = {detector_on_time:.1f}ms")
    print(f"  Detection Window: {detector_on_time:.1f}ms - {settings['SAFETY_BUFFER_MS']:.1f}ms = {detector_window:.1f}ms")

    # Test 1: Does acquisition fit in detection window?
    print(f"\n{BLUE}Test 1: Acquisition Fits in Detection Window{RESET}")
    if total_acquisition_time <= detector_window:
        margin = detector_window - total_acquisition_time
        print(f"  {GREEN}✓ PASS{RESET}: Acquisition ({total_acquisition_time:.1f}ms) fits with {margin:.1f}ms margin")
    else:
        overage = total_acquisition_time - detector_window
        print(f"  {RED}✗ FAIL{RESET}: Acquisition ({total_acquisition_time:.1f}ms) exceeds window by {overage:.1f}ms")
        max_scans = int(detector_window / single_read_time)
        print(f"  {YELLOW}→ Num scans will be reduced from {num_scans} to {max_scans}{RESET}")

    # Test 2: LED settling time before detection
    print(f"\n{BLUE}Test 2: LED Settling Time{RESET}")
    if settings['DETECTOR_WAIT_MS'] >= 50:
        print(f"  {GREEN}✓ PASS{RESET}: {settings['DETECTOR_WAIT_MS']:.1f}ms wait allows LED stabilization")
    elif settings['DETECTOR_WAIT_MS'] >= 35:
        print(f"  {YELLOW}⚠ MARGINAL{RESET}: {settings['DETECTOR_WAIT_MS']:.1f}ms may not be enough for full LED settling")
    else:
        print(f"  {RED}✗ FAIL{RESET}: {settings['DETECTOR_WAIT_MS']:.1f}ms is too short for LED stabilization")

    # Test 3: Detection window position
    detection_start = settings['DETECTOR_WAIT_MS']
    detection_end = detection_start + total_acquisition_time
    led_stable_region_start = 50  # LEDs typically stable after 50ms

    print(f"\n{BLUE}Test 3: Detection Window Position{RESET}")
    print(f"  LED ON: 0ms → {settings['LED_ON_TIME_MS']:.1f}ms")
    print(f"  Detection: {detection_start:.1f}ms → {detection_end:.1f}ms")

    if detection_start >= led_stable_region_start:
        print(f"  {GREEN}✓ PASS{RESET}: Detection starts after LED stabilization ({led_stable_region_start}ms)")
    else:
        print(f"  {YELLOW}⚠ WARNING{RESET}: Detection starts at {detection_start:.1f}ms, may catch LED settling transient")

    if detection_end <= settings['LED_ON_TIME_MS']:
        print(f"  {GREEN}✓ PASS{RESET}: Detection completes before LED OFF")
    else:
        print(f"  {RED}✗ FAIL{RESET}: Detection extends {detection_end - settings['LED_ON_TIME_MS']:.1f}ms beyond LED ON period!")

    # Test 4: Pre-arm optimization validity
    print(f"\n{BLUE}Test 4: Pre-Arm Optimization{RESET}")
    has_per_channel = bool(cal_data['integration_times']['channel_integration_times'])
    if has_per_channel:
        print(f"  {YELLOW}⚠ DISABLED{RESET}: Using per-channel integration times")
        print("  → Integration set individually for each channel")
    else:
        print(f"  {GREEN}✓ ENABLED{RESET}: Single integration time for all channels")
        print("  → Integration set ONCE before cycle (saves ~7ms × 4 = 28ms/cycle)")

    # Test 5: Total cycle time per channel
    print(f"\n{BLUE}Test 5: Total Cycle Time per Channel{RESET}")

    # Cycle timing (new architecture):
    # 1. Set LED intensity (batch command): ~5ms
    # 2. Wait for LED stabilization: DETECTOR_WAIT_MS
    # 3. Acquire spectrum: total_acquisition_time
    # 4. LED stays ON until end: remaining time

    led_command_time = 5.0  # Batch command time
    set_integration_time = 0 if not has_per_channel else 7.0  # Only if per-channel mode

    cycle_time_per_channel = (
        led_command_time +
        set_integration_time +
        settings['DETECTOR_WAIT_MS'] +
        total_acquisition_time
    )

    # Pre-arm happens once before all channels
    pre_arm_overhead = 7.0 if not has_per_channel else 0
    total_4ch_cycle = (cycle_time_per_channel * 4) + pre_arm_overhead

    print("  Per Channel:")
    print(f"    LED Batch Command: {led_command_time:.1f}ms")
    if has_per_channel:
        print(f"    Set Integration: {set_integration_time:.1f}ms")
    print(f"    Detector Wait: {settings['DETECTOR_WAIT_MS']:.1f}ms")
    print(f"    Acquisition: {total_acquisition_time:.1f}ms")
    print(f"  {GREEN}→ Total per channel: {cycle_time_per_channel:.1f}ms{RESET}")

    if not has_per_channel:
        print(f"\n  Pre-Arm (once per cycle): {pre_arm_overhead:.1f}ms")

    print(f"  {GREEN}→ Total 4-channel cycle: {total_4ch_cycle:.1f}ms ({1000/total_4ch_cycle:.2f} Hz){RESET}")

    # Summary
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}SUMMARY{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")

    all_passed = True

    if total_acquisition_time > detector_window:
        all_passed = False
        print(f"{RED}✗ Acquisition time exceeds detection window{RESET}")

    if detection_end > settings['LED_ON_TIME_MS']:
        all_passed = False
        print(f"{RED}✗ Detection extends beyond LED ON period{RESET}")

    if all_passed:
        print(f"{GREEN}✓ All timing constraints satisfied{RESET}")
        print(f"{GREEN}✓ Acquisition will use calibration parameters without modification{RESET}")
    else:
        print(f"\n{YELLOW}Recommendations:{RESET}")
        if total_acquisition_time > detector_window:
            required_led_time = settings['DETECTOR_WAIT_MS'] + total_acquisition_time + settings['SAFETY_BUFFER_MS']
            print(f"  → Increase LED_ON_TIME_MS to at least {required_led_time:.1f}ms")
            print("  → OR accept that num_scans will be reduced to fit window")

        if detection_start < led_stable_region_start:
            print(f"  → Consider increasing DETECTOR_WAIT_MS to {led_stable_region_start:.1f}ms for better LED stabilization")

    return all_passed


def main():
    """Run timing validation tests."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}ACQUISITION TIMING TEST - QC PARAMETER VALIDATION{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")

    # Load calibration and settings
    cal_data = load_latest_calibration()
    if not cal_data:
        return

    settings_data = load_settings()

    # Run tests
    success = test_timing_validation(cal_data, settings_data)

    print(f"\n{BLUE}{'='*80}{RESET}")
    if success:
        print(f"{GREEN}✓ ALL TESTS PASSED{RESET}")
    else:
        print(f"{RED}✗ SOME TESTS FAILED - Review recommendations above{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")


if __name__ == "__main__":
    main()
