"""Diagnostic script to trace integration time flow from calibration to live mode.

This script will:
1. Load calibration data from device_config.json
2. Check calib_state.integration value
3. Check if integration_per_channel exists
4. Calculate expected smart boost
5. Verify what should be passed to data acquisition
"""

import json
import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.device_configuration import DeviceConfiguration
from settings import (
    LIVE_MODE_TARGET_INTENSITY_PERCENT,
    TARGET_INTENSITY_PERCENT,
    LIVE_MODE_MAX_BOOST_FACTOR,
    LIVE_MODE_MIN_BOOST_FACTOR,
    MIN_INTEGRATION
)


def main():
    print("=" * 80)
    print("INTEGRATION TIME FLOW DIAGNOSTIC")
    print("=" * 80)
    print()

    # Step 1: Load from device_config.json
    print("STEP 1: Loading calibration from device_config.json")
    print("-" * 80)

    device_config = DeviceConfiguration()
    cal_data = device_config.load_led_calibration()

    if not cal_data:
        print("❌ ERROR: No calibration data found in device_config.json")
        return

    integration_ms = cal_data.get('integration_time_ms')
    s_mode_intensities = cal_data.get('s_mode_intensities', {})

    print(f"✅ Found calibration data:")
    print(f"   Integration time: {integration_ms} ms")
    print(f"   S-mode LED intensities: {s_mode_intensities}")
    print()

    # Step 2: Check calibration mode
    print("STEP 2: Determining calibration mode")
    print("-" * 80)

    config_data = device_config.config
    preferred_mode = config_data.get('calibration', {}).get('preferred_calibration_mode', 'unknown')

    print(f"Preferred calibration mode: {preferred_mode}")
    print()

    # Check if this is truly global mode
    if integration_ms and integration_ms > MIN_INTEGRATION:
        print(f"✅ GLOBAL MODE DETECTED:")
        print(f"   - Single integration time: {integration_ms}ms")
        print(f"   - All channels use same integration")
        print(f"   - LEDs are balanced per channel")
        is_global = True
    else:
        print(f"⚠️ PER-CHANNEL MODE or INVALID:")
        print(f"   - Integration time too low or missing")
        is_global = False
    print()

    # Step 3: Calculate smart boost
    if is_global:
        print("STEP 3: Calculating smart boost for live mode")
        print("-" * 80)

        integration_seconds = integration_ms / 1000.0

        # Calculate boost factor
        desired_boost = LIVE_MODE_TARGET_INTENSITY_PERCENT / TARGET_INTENSITY_PERCENT
        boost_factor = max(LIVE_MODE_MIN_BOOST_FACTOR,
                          min(desired_boost, LIVE_MODE_MAX_BOOST_FACTOR))

        live_integration_seconds = integration_seconds * boost_factor
        live_integration_ms = live_integration_seconds * 1000.0

        print(f"Calibration settings:")
        print(f"   Target intensity: {TARGET_INTENSITY_PERCENT}% (S-pol baseline)")
        print(f"   Integration time: {integration_ms:.1f}ms")
        print()
        print(f"Live mode optimization:")
        print(f"   Target intensity: {LIVE_MODE_TARGET_INTENSITY_PERCENT}% (P-pol compensated)")
        print(f"   Desired boost: {desired_boost:.2f}×")
        print(f"   Applied boost: {boost_factor:.2f}× (capped between {LIVE_MODE_MIN_BOOST_FACTOR}-{LIVE_MODE_MAX_BOOST_FACTOR})")
        print(f"   Boosted integration: {integration_ms:.1f}ms → {live_integration_ms:.1f}ms")
        print()

        # Step 4: What should be passed
        print("STEP 4: Expected data flow")
        print("-" * 80)
        print(f"✅ CORRECT FLOW:")
        print(f"   1. state_machine loads: integration_ms = {integration_ms:.1f}ms")
        print(f"   2. state_machine calculates: live_integration_seconds = {live_integration_seconds:.6f}s")
        print(f"   3. state_machine passes to DataAcquisitionWrapper:")
        print(f"      - self.data_acquisition.live_integration_seconds = {live_integration_seconds:.6f}s")
        print(f"   4. DataAcquisitionWrapper.grab_data() uses:")
        print(f"      - desired_live = getattr(self, 'live_integration_seconds', None)")
        print(f"      - Sets spectrometer to {live_integration_ms:.1f}ms")
        print()

        print(f"❌ INCORRECT FLOW (what's happening now):")
        print(f"   1. System checks for integration_per_channel dict")
        print(f"   2. Finds integration_per_channel with 5ms values (wrong!)")
        print(f"   3. Uses 5ms instead of {live_integration_ms:.1f}ms")
        print(f"   4. Result: Signal is 5× too low compared to S-ref at 26ms")
        print()

    # Step 5: Check for interfering per-channel data
    print("STEP 5: Checking for interfering per-channel data")
    print("-" * 80)

    # Check if device_config has per-channel integration times stored
    if 'led_calibration' in config_data:
        led_cal = config_data['led_calibration']
        if 'per_channel_integration_times' in led_cal:
            per_ch = led_cal['per_channel_integration_times']
            print(f"⚠️ WARNING: Found per_channel_integration_times in device_config:")
            for ch, val in per_ch.items():
                print(f"   {ch.upper()}: {val*1000 if val < 1 else val:.1f}ms")
            print()
            print(f"💡 FIX: These should be REMOVED for global mode calibration!")
            print(f"   They are overriding the correct {live_integration_ms:.1f}ms boost.")
        else:
            print(f"✅ No per_channel_integration_times found (correct for global mode)")
    print()

    # Step 6: Verification checklist
    print("STEP 6: Verification checklist before starting live mode")
    print("-" * 80)
    print("Before starting live data acquisition, verify:")
    print()
    print("1. ✅ Check logs for: 'Loaded cached integration time: XXms'")
    print(f"   Expected: {integration_ms}ms")
    print()
    print("2. ✅ Check logs for: 'SMART BOOST APPLIED (from cached calibration)'")
    print(f"   Expected boost: {boost_factor:.2f}×")
    print(f"   Expected live integration: {live_integration_ms:.1f}ms")
    print()
    print("3. ✅ Check logs for: 'Passed smart boost integration time to DataAcquisitionWrapper'")
    print(f"   Expected: {live_integration_ms:.1f}ms")
    print()
    print("4. ✅ Check logs for: 'LIVE MODE: Set integration XXms'")
    print(f"   Expected: {live_integration_ms:.1f}ms (NOT 5ms!)")
    print()
    print("5. ❌ If you see 'Channel X: Set integration 5.0ms':")
    print("   - integration_per_channel dict is interfering")
    print("   - Remove per_channel_integration_times from device_config")
    print("   - Restart application")
    print()

    print("=" * 80)
    print("END OF DIAGNOSTIC")
    print("=" * 80)


if __name__ == "__main__":
    main()
