"""Quick diagnostic to check what smart validation loads."""

import json
from pathlib import Path

import numpy as np

# Load device config
config_path = Path("config/device_config.json")
with open(config_path) as f:
    config = json.load(f)

# Check LED calibration
led_cal = config.get("led_calibration", {})
print("=" * 80)
print("DEVICE_CONFIG.JSON LED_CALIBRATION")
print("=" * 80)
print(f"integration_time_ms: {led_cal.get('integration_time_ms')}")
print(f"s_mode_intensities: {led_cal.get('s_mode_intensities')}")
print(f"s_ref_baseline keys: {list(led_cal.get('s_ref_baseline', {}).keys())}")
print(f"s_ref_wavelengths present: {led_cal.get('s_ref_wavelengths') is not None}")
print(f"s_ref_wavelengths length: {len(led_cal.get('s_ref_wavelengths', []))}")
print(f"dark_noise present: {led_cal.get('dark_noise') is not None}")
print(f"per_channel_integration: {led_cal.get('integration_per_channel')}")
print(f"per_channel_scans: {led_cal.get('scans_per_channel')}")
print(f"live_boost_integration_ms: {led_cal.get('live_boost_integration_ms')}")
print(f"live_boost_factor: {led_cal.get('live_boost_factor')}")
print("=" * 80)

# Simulate smart validation
from utils.spr_calibrator import CalibrationState

cs = CalibrationState()
try:
    integ_ms = float(led_cal.get("integration_time_ms", 0))
    if integ_ms > 0:
        cs.integration = integ_ms / 1000.0
        print(f"✅ cs.integration = {cs.integration * 1000:.1f}ms")
except Exception as e:
    print(f"❌ Failed to set integration: {e}")

try:
    s_leds = led_cal.get("s_mode_intensities", {}) or {}
    if isinstance(s_leds, dict) and s_leds:
        cs.ref_intensity = {ch: int(v) for ch, v in s_leds.items()}
        cs.leds_calibrated = {ch: int(v) for ch, v in s_leds.items()}
        print(f"✅ cs.leds_calibrated = {cs.leds_calibrated}")
except Exception as e:
    print(f"❌ Failed to set LEDs: {e}")

try:
    s_ref = led_cal.get("s_ref_baseline", {}) or {}
    if isinstance(s_ref, dict) and s_ref:
        cs.ref_sig = {ch: np.array(spec) for ch, spec in s_ref.items()}
        print(f"✅ cs.ref_sig keys = {list(cs.ref_sig.keys())}")
except Exception as e:
    print(f"❌ Failed to set ref_sig: {e}")

try:
    wl = led_cal.get("s_ref_wavelengths")
    if wl is not None:
        cs.wavelengths = np.array(wl)
        print(f"✅ cs.wavelengths length = {len(cs.wavelengths)}")
except Exception as e:
    print(f"❌ Failed to set wavelengths: {e}")

try:
    dark = led_cal.get("dark_noise")
    if dark is not None:
        cs.dark_noise = np.array(dark)
        print(f"✅ cs.dark_noise length = {len(cs.dark_noise)}")
    else:
        cs.dark_noise = (
            np.zeros(len(cs.wavelengths)) if len(cs.wavelengths) > 0 else np.zeros(3648)
        )
        print(f"⚠️ cs.dark_noise = zeros ({len(cs.dark_noise)} points)")
except Exception as e:
    print(f"❌ Failed to set dark_noise: {e}")

print("=" * 80)
print(f"cs.is_valid() = {cs.is_valid()}")
print("=" * 80)

# Simulate boost calculation
from settings import (
    LIVE_MODE_MAX_BOOST_FACTOR,
    LIVE_MODE_TARGET_INTENSITY_PERCENT,
    TARGET_INTENSITY_PERCENT,
)

desired_boost = LIVE_MODE_TARGET_INTENSITY_PERCENT / TARGET_INTENSITY_PERCENT
boost_factor = max(1.0, min(desired_boost, LIVE_MODE_MAX_BOOST_FACTOR))
live_integration_seconds = cs.integration * boost_factor

print()
print("🔋 SMART BOOST CALCULATION:")
print(f"   Calibration integration: {cs.integration * 1000:.1f}ms")
print(f"   Target boost: {desired_boost:.2f}×")
print(f"   Applied boost: {boost_factor:.2f}×")
print(f"   Live integration: {live_integration_seconds * 1000:.1f}ms")
print("=" * 80)
