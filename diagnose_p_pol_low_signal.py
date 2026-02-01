"""Diagnose why P-pol channels C and D have extremely low signals.

This script tests:
1. Servo position (is P-pol actually at P position?)
2. LED response per channel in both S and P positions
3. Whether C/D LEDs are working at all
"""

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.detector_factory import create_detector
import time
import numpy as np

print("=" * 80)
print("P-POL LOW SIGNAL DIAGNOSTIC")
print("=" * 80)

# Initialize hardware
hwm = HardwareManager()
hwm._connect_controller()
if hwm.ctrl is None:
    print("❌ Failed to connect to controller")
    exit(1)

ctrl = hwm.ctrl
device_id = getattr(ctrl, 'device_id', getattr(ctrl, 'controller_id', 'Unknown'))
print(f"✓ Controller connected: {device_id}")

# Create detector
class MockApp:
    pass

app = MockApp()
detector = create_detector(app, {})
if detector is None:
    print("❌ Failed to connect to detector")
    ctrl.close()
    exit(1)

print(f"✓ Detector connected: {detector.serial_number if hasattr(detector, 'serial_number') else 'Unknown'}")

# Set integration time
integration_ms = 20
detector.set_integration(integration_ms)
print(f"✓ Integration time: {integration_ms}ms")

# Enable all LED channels
print("\nEnabling all LED channels...")
for ch in ['a', 'b', 'c', 'd']:
    ctrl.turn_on_channel(ch)
time.sleep(0.1)

# Get servo positions from device config
# Use ST00011 since that's the detector we have connected
device_id = detector.serial_number if hasattr(detector, 'serial_number') else "ST00011"
print(f"\nDevice: {device_id}")

# Read from config or use calibrated values
try:
    import json
    from pathlib import Path
    config_path = Path(f"affilabs/config/devices/{device_id}/device_config.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        s_pos = config['hardware'].get('servo_s_position', 195)
        p_pos = config['hardware'].get('servo_p_position', 32)
        print(f"✓ Loaded positions from config: S={s_pos}, P={p_pos}")
    else:
        print("⚠ Config not found, using ST00011 defaults: S=195, P=32")
        s_pos = 195
        p_pos = 32
except Exception as e:
    print(f"⚠ Error loading config: {e}")
    s_pos = 195
    p_pos = 32

print("\n" + "=" * 80)
print("TEST 1: S-POL POSITION - Individual Channel LED Response")
print("=" * 80)

# Move to S position
ctrl.servo_move_raw_pwm(s_pos)
time.sleep(0.5)
print(f"Servo at S-pol position: {s_pos}")

# Test each LED individually at high intensity
test_led = 255
s_pol_results = {}

for ch in ['a', 'b', 'c', 'd']:
    # Turn on only this channel
    ctrl.set_batch_intensities(
        255 if ch == 'a' else 0,
        255 if ch == 'b' else 0,
        255 if ch == 'c' else 0,
        255 if ch == 'd' else 0
    )
    time.sleep(0.05)

    # Read signal
    spectrum = detector.read_intensity()
    if spectrum is not None:
        max_signal = np.max(spectrum)
        mean_signal = np.mean(spectrum)
        s_pol_results[ch] = {'max': max_signal, 'mean': mean_signal}
        print(f"  Ch {ch.upper()}: LED=255 → Max={max_signal:.0f}, Mean={mean_signal:.0f} counts")
    else:
        print(f"  Ch {ch.upper()}: ❌ Failed to read")
        s_pol_results[ch] = {'max': 0, 'mean': 0}

print("\n" + "=" * 80)
print("TEST 2: P-POL POSITION - Individual Channel LED Response")
print("=" * 80)

# Move to P position
ctrl.servo_move_raw_pwm(p_pos)
time.sleep(0.5)
print(f"Servo at P-pol position: {p_pos}")

p_pol_results = {}

for ch in ['a', 'b', 'c', 'd']:
    # Turn on only this channel
    ctrl.set_batch_intensities(
        255 if ch == 'a' else 0,
        255 if ch == 'b' else 0,
        255 if ch == 'c' else 0,
        255 if ch == 'd' else 0
    )
    time.sleep(0.05)

    # Read signal
    spectrum = detector.read_intensity()
    if spectrum is not None:
        max_signal = np.max(spectrum)
        mean_signal = np.mean(spectrum)
        p_pol_results[ch] = {'max': max_signal, 'mean': mean_signal}
        print(f"  Ch {ch.upper()}: LED=255 → Max={max_signal:.0f}, Mean={mean_signal:.0f} counts")
    else:
        print(f"  Ch {ch.upper()}: ❌ Failed to read")
        p_pol_results[ch] = {'max': 0, 'mean': 0}

# Turn off all LEDs
ctrl.set_batch_intensities(0, 0, 0, 0)

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

# Calculate P/S ratios
print("\nP-pol / S-pol Ratio (P-pol extinction):")
for ch in ['a', 'b', 'c', 'd']:
    s_max = s_pol_results[ch]['max']
    p_max = p_pol_results[ch]['max']

    if s_max > 0:
        ratio = p_max / s_max
        extinction_pct = (1 - ratio) * 100
        status = "✓ OK" if extinction_pct > 50 else "❌ BAD"
        print(f"  Ch {ch.upper()}: P/S = {ratio:.3f} → {extinction_pct:.1f}% extinction {status}")

        if extinction_pct < 50:
            print("       ⚠ WARNING: Poor extinction! P-pol should block >70% of light")
            print("       Possible causes:")
            print(f"         • Servo P position ({p_pos}) is incorrect")
            print("         • Polarizer not aligned properly for this channel")
            print(f"         • LED {ch.upper()} wavelength outside polarizer range")
    else:
        print(f"  Ch {ch.upper()}: ❌ No S-pol signal!")

print("\nChannel Quality Assessment:")
for ch in ['a', 'b', 'c', 'd']:
    s_max = s_pol_results[ch]['max']
    p_max = p_pol_results[ch]['max']

    # Check if channel is working
    if s_max < 1000:
        print(f"  Ch {ch.upper()}: ❌ FAILED - S-pol signal too low ({s_max:.0f})")
        print("       Possible LED failure or connection issue")
    elif p_max > s_max * 0.5:
        print(f"  Ch {ch.upper()}: ❌ FAILED - P-pol not blocking light properly")
        print("       Servo position likely wrong for this channel")
    elif p_max < s_max * 0.2:
        print(f"  Ch {ch.upper()}: ✓ GOOD - Proper S/P separation")
    else:
        print(f"  Ch {ch.upper()}: ⚠ MARGINAL - P-pol extinction could be better")

# Specific diagnosis for C and D
print("\n" + "=" * 80)
print("DIAGNOSIS FOR CHANNELS C AND D")
print("=" * 80)

for ch in ['c', 'd']:
    s_max = s_pol_results[ch]['max']
    p_max = p_pol_results[ch]['max']

    print(f"\nChannel {ch.upper()}:")
    print(f"  S-pol max: {s_max:.0f} counts")
    print(f"  P-pol max: {p_max:.0f} counts")

    if s_max < 1000:
        print(f"  ❌ LED {ch.upper()} appears to be FAILED or disconnected")
        print("     Action: Check LED wiring/connection or replace LED")
    elif p_max > s_max * 0.7:
        print("  ❌ Polarizer not blocking this channel's light")
        print(f"     P-pol position {p_pos} is WRONG for this LED wavelength")
        print("     Action: Re-run servo calibration to find correct P position")
    elif p_max < 100:
        print("  ⚠ P-pol signal extremely low (< 100 counts)")
        print("     This is actually TOO MUCH blocking - polarizer might be at wrong angle")
        print("     Action: Verify P servo position, might need adjustment +/- 5-10 degrees")
    else:
        print("  ℹ️ LED working, but P/S ratio unusual")

# Cleanup
detector.close()
ctrl.close()

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
