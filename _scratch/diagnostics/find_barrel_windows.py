"""Find barrel polarizer transmission windows with dense sweep.

This script performs a dense servo sweep (every 5 PWM units) to locate
the exact positions of the two transmission windows in a barrel polarizer.
"""

import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from affilabs.utils.hardware_manager import HardwareManager


def measure_signal(hm, num_samples=3):
    """Measure detector signal with averaging."""
    signals = []
    for _ in range(num_samples):
        sig = hm.usb.trigger_and_receive()
        signals.append(sig)
        time.sleep(0.05)
    return sum(signals) / len(signals)


def move_servo_and_wait(hm, pwm, settle_time=1.0):
    """Move servo to PWM position and wait for settling."""
    # Convert PWM to angle for V2.4 firmware
    angle = int(5 + (pwm / 255.0) * 170)

    # Use V2.4 servo command format
    cmd = f"servo:{angle},500"
    success = hm._ctrl.send_command(cmd)

    if not success:
        print(f"⚠️  Servo command failed for PWM {pwm} (angle {angle}°)")
        return False

    time.sleep(settle_time)
    return True


def dense_sweep(hm, step=5, settle_time=1.0):
    """Perform dense sweep from PWM 0 to 255.

    Args:
        hm: Hardware manager
        step: PWM step size (default 5 = 51 positions)
        settle_time: Time to wait after servo movement (seconds)

    Returns:
        list of dicts with {pwm, angle, signal}
    """
    results = []

    print(f"\n{'='*70}")
    print(f"DENSE SERVO SWEEP (step={step} PWM, settle={settle_time}s)")
    print(f"{'='*70}\n")

    # Sweep from 0 to 255
    for pwm in range(0, 256, step):
        angle = int(5 + (pwm / 255.0) * 170)

        # Move servo
        if not move_servo_and_wait(hm, pwm, settle_time):
            continue

        # Measure signal
        signal = measure_signal(hm, num_samples=3)

        results.append({
            "pwm": pwm,
            "angle": angle,
            "signal": signal
        })

        # Print with visual indicator
        bar = "█" * int(signal / 500)  # Scale bar length
        status = "🟢 BRIGHT" if signal > 8000 else "🔴 DARK" if signal < 3500 else "🟡 MID"
        print(f"PWM {pwm:3d} ({angle:3d}°): {signal:7.1f} counts {bar:30s} {status}")

    return results


def analyze_windows(results, dark_threshold=3500, bright_threshold=8000):
    """Analyze results to find transmission windows."""
    print(f"\n{'='*70}")
    print(f"WINDOW ANALYSIS")
    print(f"{'='*70}\n")

    # Find statistics
    signals = [r["signal"] for r in results]
    min_sig = min(signals)
    max_sig = max(signals)
    avg_sig = sum(signals) / len(signals)
    dynamic_range = max_sig / max(min_sig, 1.0)

    print(f"Signal Statistics:")
    print(f"  Min: {min_sig:7.1f} counts")
    print(f"  Max: {max_sig:7.1f} counts")
    print(f"  Avg: {avg_sig:7.1f} counts")
    print(f"  Dynamic range: {dynamic_range:.1f}×")
    print(f"  Range: {max_sig - min_sig:.1f} counts")

    # Find bright windows (signal > bright_threshold)
    bright_positions = [r for r in results if r["signal"] > bright_threshold]
    dark_positions = [r for r in results if r["signal"] < dark_threshold]
    mid_positions = [r for r in results if dark_threshold <= r["signal"] <= bright_threshold]

    print(f"\nPosition Distribution:")
    print(f"  BRIGHT (>{bright_threshold}): {len(bright_positions)} positions")
    print(f"  MID ({dark_threshold}-{bright_threshold}): {len(mid_positions)} positions")
    print(f"  DARK (<{dark_threshold}): {len(dark_positions)} positions")

    if len(bright_positions) >= 2:
        print(f"\n✅ Found {len(bright_positions)} bright positions - BARREL CONFIRMED")
        print(f"\nBright Positions:")
        for r in bright_positions:
            print(f"  PWM {r['pwm']:3d} ({r['angle']:3d}°): {r['signal']:7.1f} counts")

        # Find the TWO brightest (likely S and P windows)
        sorted_bright = sorted(bright_positions, key=lambda x: x["signal"], reverse=True)

        if len(sorted_bright) >= 2:
            window1 = sorted_bright[0]
            window2 = sorted_bright[1]

            # Calculate separation
            pwm_sep = abs(window1["pwm"] - window2["pwm"])
            angle_sep = abs(window1["angle"] - window2["angle"])

            print(f"\n🎯 TWO BRIGHTEST WINDOWS:")
            print(f"  Window 1: PWM {window1['pwm']:3d} ({window1['angle']:3d}°) - {window1['signal']:7.1f} counts")
            print(f"  Window 2: PWM {window2['pwm']:3d} ({window2['angle']:3d}°) - {window2['signal']:7.1f} counts")
            print(f"  Separation: {pwm_sep} PWM ({angle_sep}°)")

            if 70 <= pwm_sep <= 110:  # Expect ~90 PWM separation
                print(f"  ✅ Separation matches barrel polarizer (expect ~90 PWM)")
            else:
                print(f"  ⚠️  Unexpected separation (expect ~90 PWM for barrel)")

            # Recommend S and P positions
            if window1["signal"] > window2["signal"]:
                print(f"\n📋 RECOMMENDED POSITIONS:")
                print(f"  S (brighter): PWM {window1['pwm']:3d} ({window1['angle']:3d}°)")
                print(f"  P (dimmer):   PWM {window2['pwm']:3d} ({window2['angle']:3d}°)")
            else:
                print(f"\n📋 RECOMMENDED POSITIONS:")
                print(f"  S (brighter): PWM {window2['pwm']:3d} ({window2['angle']:3d}°)")
                print(f"  P (dimmer):   PWM {window1['pwm']:3d} ({window1['angle']:3d}°)")

    elif len(bright_positions) == 1:
        print(f"\n⚠️  Found only 1 bright window - other window may be in blind spot")
        print(f"  PWM {bright_positions[0]['pwm']:3d} ({bright_positions[0]['angle']:3d}°): {bright_positions[0]['signal']:7.1f} counts")
        print(f"  Recommend running again with finer step size")

    elif max_sig > dark_threshold:
        print(f"\n⚠️  No bright windows above {bright_threshold} threshold")
        print(f"  Max signal: {max_sig:.1f} counts")
        print(f"  Possible CIRCULAR polarizer or low LED intensity")

    else:
        print(f"\n❌ ALL positions are dark (<{dark_threshold} counts)")
        print(f"  Possible issues:")
        print(f"    - LEDs not turned on")
        print(f"    - Servo not moving")
        print(f"    - Optical path blocked")
        print(f"    - Detector not working")


def main():
    print("="*70)
    print("BARREL POLARIZER WINDOW FINDER")
    print("="*70)

    # Initialize hardware
    print("\n1️⃣  Initializing hardware...")
    try:
        hm = HardwareManager()
        print(f"   ✅ Hardware manager initialized")
        print(f"   Controller: {hm.device_config.hardware.controller_model}")
        print(f"   Detector: {hm.device_config.hardware.spectrometer_model}")
        print(f"   Polarizer type (config): {hm.device_config.hardware.polarizer_type}")
    except Exception as e:
        print(f"   ❌ Failed to initialize hardware: {e}")
        return

    # Turn on LEDs
    print("\n2️⃣  Turning on LEDs (20% intensity)...")
    try:
        # Use set_batch_intensities for all 4 LEDs
        led_intensity = 51  # 20% of 255
        hm._ctrl.set_batch_intensities([led_intensity] * 4)
        time.sleep(0.5)
        print(f"   ✅ LEDs enabled at {led_intensity}/255 ({led_intensity/255*100:.0f}%)")
    except Exception as e:
        print(f"   ⚠️  LED enable warning: {e}")
        print(f"   Continuing anyway...")

    # Measure dark current
    print("\n3️⃣  Measuring detector dark current (LEDs will be turned off briefly)...")
    try:
        hm._ctrl.set_batch_intensities([0] * 4)
        time.sleep(0.3)
        dark_current = measure_signal(hm, num_samples=5)
        print(f"   Dark current: {dark_current:.1f} counts")

        # Turn LEDs back on
        hm._ctrl.set_batch_intensities([led_intensity] * 4)
        time.sleep(0.5)

        dark_threshold = dark_current * 3.5
        bright_threshold = dark_current * 8.0
        print(f"   Dark threshold: {dark_threshold:.1f} counts")
        print(f"   Bright threshold: {bright_threshold:.1f} counts")
    except Exception as e:
        print(f"   ⚠️  Dark current measurement failed: {e}")
        dark_threshold = 3500
        bright_threshold = 8000
        print(f"   Using default thresholds: dark={dark_threshold}, bright={bright_threshold}")

    # Perform dense sweep
    print("\n4️⃣  Performing dense servo sweep...")
    try:
        results = dense_sweep(hm, step=5, settle_time=0.8)
    except Exception as e:
        print(f"   ❌ Sweep failed: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        # Turn off LEDs
        print("\n[CLEANUP] Turning off LEDs...")
        try:
            hm._ctrl.set_batch_intensities([0] * 4)
            print("   ✅ LEDs turned off")
        except:
            pass

    # Analyze results
    print("\n5️⃣  Analyzing results...")
    analyze_windows(results, dark_threshold, bright_threshold)

    print(f"\n{'='*70}")
    print("SCAN COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
