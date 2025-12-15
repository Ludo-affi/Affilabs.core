"""Test per-channel integration times."""

from utils.controller import PicoP4SPR
from utils.device_configuration import DeviceConfiguration
from utils.spr_calibrator import SPRCalibrator
from utils.usb4000_oceandirect import USB4000OceanDirect

# Connect hardware
ctrl = PicoP4SPR()
if not ctrl.open():
    print("Failed to open controller")
    exit(1)

usb = USB4000OceanDirect()
if not usb:
    print("Failed to open spectrometer")
    exit(1)

# Create calibrator
cfg = DeviceConfiguration()
device_config = cfg.to_dict()
if not device_config:
    print("No device config found, creating minimal config...")
    device_config = {"device_type": "UNKNOWN", "baseline": {}}
calibrator = SPRCalibrator(
    ctrl,
    usb,
    device_config.get("device_type", "UNKNOWN"),
    device_config,
)

# Calibrate wavelengths
if not calibrator.step_2_calibrate_wavelength_range():
    print("Failed to calibrate wavelengths")
    exit(1)

# Run test with per-channel integration times
print("\n" + "=" * 80)
print("RUNNING TEST WITH PER-CHANNEL INTEGRATION TIMES")
print("=" * 80)
print("A: 50ms, B: 120ms, C: 19ms, D: 19ms")
print("LED: 255 (all channels)")
print("Delays: 100ms on / 5ms off")
print("=" * 80 + "\n")

result = calibrator.diagnostic_s_roi_stability_test(
    ch_list=["a", "b", "c", "d"],
    duration_sec=60.0,
    led_value=255,
    led_on_delay_ms=100,
    led_off_delay_ms=5,
    integration_time_ms_by_ch={"a": 50, "b": 120, "c": 19, "d": 19},
)

if result:
    print("\n✅ Test completed successfully!")
else:
    print("\n❌ Test failed!")
    exit(1)
