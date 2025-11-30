"""Test script for calibration Steps 1-4.

This mimics the actual calibration process to verify:
- Step 1: Hardware validation and LED turn-off
- Step 2: Wavelength range calibration
- Step 3: LED brightness ranking
- Step 4: Integration time optimization
"""

import time
import sys
import numpy as np
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000
from utils.logger import logger

# Settings from calibration_6step.py
MIN_WAVELENGTH = 500
MAX_WAVELENGTH = 800
LED_DELAY = 0.100
RANKING_INTEGRATION_TIME = 0.070  # 70ms
MAX_INTEGRATION = 70  # ms
WEAKEST_TARGET_PERCENT = 70
WEAKEST_MIN_PERCENT = 60
WEAKEST_MAX_PERCENT = 80
STRONGEST_MAX_PERCENT = 95


def test_step_1(ctrl):
    """Step 1: Hardware validation and LED verification."""
    print("\n" + "="*80)
    print("STEP 1: Hardware Validation & LED Verification")
    print("="*80)

    print("\n🔦 Forcing ALL LEDs OFF...")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    print("✅ Verifying LEDs are off...")
    print("   (Query disabled due to firmware bugs - using timing-based validation)")
    time.sleep(0.05)

    print("\n   👀 OBSERVE: Are all LEDs OFF?")
    input("   Press ENTER to confirm all LEDs are OFF...\n")

    print("✅ Step 1 complete: Hardware validated, LEDs confirmed OFF\n")
    return True


def test_step_2(usb):
    """Step 2: Wavelength range calibration."""
    print("="*80)
    print("STEP 2: Wavelength Range Calibration (Detector-Specific)")
    print("="*80)

    print("\nReading wavelength calibration from detector EEPROM...")
    wave_data = usb.read_wavelength()

    if wave_data is None or len(wave_data) == 0:
        print("❌ Failed to read wavelengths from detector")
        return None

    print(f"✅ Full detector range: {wave_data[0]:.1f}-{wave_data[-1]:.1f}nm ({len(wave_data)} pixels)")

    # Detect detector type
    detector_type_str = "Unknown"
    if 186 <= wave_data[0] <= 188 and 884 <= wave_data[-1] <= 886:
        detector_type_str = "Ocean Optics USB4000 (UV-VIS)"
    elif 337 <= wave_data[0] <= 339 and 1020 <= wave_data[-1] <= 1022:
        detector_type_str = "Ocean Optics USB4000 (VIS-NIR)"

    print(f"📊 Detector: {detector_type_str}")

    # Calculate spectral filter (SPR range only)
    wave_min_index = np.searchsorted(wave_data, MIN_WAVELENGTH)
    wave_max_index = np.searchsorted(wave_data, MAX_WAVELENGTH)

    filtered_wave = wave_data[wave_min_index:wave_max_index].copy()

    print(f"✅ SPR filtered range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm ({len(filtered_wave)} pixels)")
    print(f"   Spectral resolution: {(wave_data[-1]-wave_data[0])/len(wave_data):.3f} nm/pixel")

    # Get detector max counts
    max_counts = 65535  # USB4000 standard
    saturation_threshold = int(0.95 * max_counts)

    print(f"✅ Detector parameters:")
    print(f"   Max counts: {max_counts}")
    print(f"   Saturation threshold: {saturation_threshold}")
    print("✅ Step 2 complete\n")

    return {
        'wave_data': filtered_wave,
        'wave_min_index': wave_min_index,
        'wave_max_index': wave_max_index,
        'full_wavelengths': wave_data,
        'max_counts': max_counts,
        'saturation_threshold': saturation_threshold
    }


def test_step_3(ctrl, usb, wave_info):
    """Step 3: LED brightness ranking."""
    print("="*80)
    print("STEP 3: LED Brightness Ranking")
    print("="*80)

    print("\nSwitching to S-mode...")
    if hasattr(ctrl, 'set_mode'):
        ctrl.set_mode('s')
        time.sleep(0.5)
    print("✅ S-mode active")

    print("🔦 Turning off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    print(f"\n🔧 Setting integration time to {RANKING_INTEGRATION_TIME*1000:.0f}ms for LED ranking")
    usb.set_integration(RANKING_INTEGRATION_TIME)
    time.sleep(0.1)

    # Test LED intensity for ranking
    test_led_intensity = int(0.2 * 255)  # 20% = 51
    print(f"\n📊 Testing all LEDs at {test_led_intensity} ({test_led_intensity/255*100:.0f}%)...\n")

    ch_list = ['a', 'b', 'c', 'd']
    channel_data = {}

    wave_min_index = wave_info['wave_min_index']
    wave_max_index = wave_info['wave_max_index']

    for ch in ch_list:
        print(f"\n   Testing LED {ch.upper()}...")

        # Turn on channel
        ctrl.set_intensity(ch=ch, raw_val=test_led_intensity)
        time.sleep(LED_DELAY)

        print(f"      👀 OBSERVE: Only LED {ch.upper()} should be ON now")
        time.sleep(0.5)  # Give user time to observe

        # Read spectrum
        raw_spectrum = usb.read_intensity()

        # Turn off
        ctrl.turn_off_channels()
        time.sleep(LED_DELAY)

        if raw_spectrum is None:
            print(f"   ❌ Failed to read spectrum for {ch.upper()}")
            continue

        # Filter to SPR range
        filtered_spectrum = raw_spectrum[wave_min_index:wave_max_index]

        mean_intensity = float(np.mean(filtered_spectrum))
        max_intensity = float(np.max(filtered_spectrum))

        channel_data[ch] = (mean_intensity, max_intensity, False)
        print(f"      Mean: {mean_intensity:6.0f}, Max: {max_intensity:6.0f}")

    # Rank channels
    ranked_channels = sorted(channel_data.items(), key=lambda x: x[1][0])

    print(f"\n📊 LED Ranking (weakest → strongest):")
    for rank_idx, (ch, (mean, _, _)) in enumerate(ranked_channels, 1):
        ratio = mean / ranked_channels[0][1][0] if ranked_channels[0][1][0] > 0 else 1.0
        print(f"   {rank_idx}. Channel {ch.upper()}: {mean:6.0f} counts ({ratio:.2f}× weakest)")

    weakest_ch = ranked_channels[0][0]
    strongest_ch = ranked_channels[-1][0]
    weakest_intensity = ranked_channels[0][1][0]
    strongest_intensity = ranked_channels[-1][1][0]

    print(f"\n✅ Weakest LED: {weakest_ch.upper()} ({weakest_intensity:.0f} counts)")
    print(f"   → Will be FIXED at LED=255 (maximum) in Step 4")
    print(f"⚠️  Strongest LED: {strongest_ch.upper()} ({strongest_intensity:.0f} counts, {strongest_intensity/weakest_intensity:.2f}× brighter)")
    print(f"   → Will need most dimming (ratio: {strongest_intensity/weakest_intensity:.2f}×)")
    print("✅ Step 3 complete\n")

    return {
        'ranked_channels': ranked_channels,
        'weakest_channel': weakest_ch,
        'strongest_channel': strongest_ch
    }


def test_step_4(ctrl, usb, wave_info, ranking_info):
    """Step 4: Integration time optimization."""
    print("="*80)
    print("STEP 4: Integration Time Optimization (Constrained Dual Optimization)")
    print("="*80)

    weakest_ch = ranking_info['weakest_channel']
    strongest_ch = ranking_info['strongest_channel']

    print(f"\nGoal: Maximize weakest LED signal while preventing strongest LED saturation")
    print(f"Weakest channel: {weakest_ch.upper()} (will be at LED=255)")
    print(f"Strongest channel: {strongest_ch.upper()} (must not saturate)")
    print(f"Constraints: Weakest 60-80%, Strongest <95%, Integration ≤{MAX_INTEGRATION}ms\n")

    # Get detector limits
    min_int = 0.001  # 1ms
    max_int = MAX_INTEGRATION / 1000.0  # 70ms in seconds
    detector_max = wave_info['saturation_threshold']

    print(f"   Weakest LED: {weakest_ch.upper()} (will be optimized at LED=255)")
    print(f"   Strongest LED: {strongest_ch.upper()} (will be tested for saturation)")
    print(f"")
    print(f"   PRIMARY GOAL: Maximize weakest LED signal")
    print(f"      → Target: 70% @ LED=255 ({int(0.70*detector_max):,} counts)")
    print(f"      → Range: 60-80% ({int(0.60*detector_max):,}-{int(0.80*detector_max):,} counts)")
    print(f"")
    print(f"   CONSTRAINT 1: Strongest LED must not saturate")
    print(f"      → Maximum: <95% @ LED=255 ({int(0.95*detector_max):,} counts)")
    print(f"")
    print(f"   CONSTRAINT 2: Integration time ≤ {max_int*1000:.0f}ms")
    print(f"")

    # Define targets
    weakest_target = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)
    weakest_min = int(WEAKEST_MIN_PERCENT / 100 * detector_max)
    weakest_max = int(WEAKEST_MAX_PERCENT / 100 * detector_max)
    strongest_max = int(STRONGEST_MAX_PERCENT / 100 * detector_max)

    wave_min_index = wave_info['wave_min_index']
    wave_max_index = wave_info['wave_max_index']

    # Binary search for optimal integration time
    integration_min = min_int
    integration_max = max_int
    best_integration = None
    best_weakest_signal = 0
    best_strongest_signal = 0

    max_iterations = 15
    print(f"🔍 Binary search: {integration_min*1000:.1f}ms - {integration_max*1000:.1f}ms\n")

    for iteration in range(max_iterations):
        # Test integration time (midpoint)
        test_integration = (integration_min + integration_max) / 2.0
        usb.set_integration(test_integration)
        time.sleep(0.1)

        # Test weakest LED at LED=255
        ctrl.set_intensity(ch=weakest_ch, raw_val=255)
        time.sleep(LED_DELAY)
        spectrum = usb.read_intensity()
        ctrl.turn_off_channels()
        time.sleep(0.05)

        if spectrum is None:
            print("   ❌ Failed to read spectrum")
            break

        weakest_signal = spectrum[wave_min_index:wave_max_index].max()
        weakest_percent = (weakest_signal / detector_max) * 100

        # Test strongest LED at LED=255
        ctrl.set_intensity(ch=strongest_ch, raw_val=255)
        time.sleep(LED_DELAY)
        spectrum = usb.read_intensity()
        ctrl.turn_off_channels()
        time.sleep(0.05)

        if spectrum is None:
            print("   ❌ Failed to read spectrum")
            break

        strongest_signal = spectrum[wave_min_index:wave_max_index].max()
        strongest_percent = (strongest_signal / detector_max) * 100

        print(f"   Iteration {iteration+1}: {test_integration*1000:.1f}ms")
        print(f"      Weakest ({weakest_ch.upper()} @ LED=255): {weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
        print(f"      Strongest ({strongest_ch.upper()} @ LED=255): {strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")

        # Check constraints
        if strongest_signal > strongest_max:
            print(f"      ❌ Strongest LED too high (would saturate) → Reduce integration")
            integration_max = test_integration
            continue

        # Check if weakest LED is in target range
        if weakest_min <= weakest_signal <= weakest_max:
            best_integration = test_integration
            best_weakest_signal = weakest_signal
            best_strongest_signal = strongest_signal
            print(f"      ✅ OPTIMAL! Both constraints satisfied")
            break
        elif weakest_signal < weakest_min:
            print(f"      ⚠️  Weakest LED too low → Increase integration")
            integration_min = test_integration
        else:
            print(f"      ⚠️  Weakest LED too high → Reduce integration")
            integration_max = test_integration

        # Track best so far
        if abs(weakest_signal - weakest_target) < abs(best_weakest_signal - weakest_target):
            best_integration = test_integration
            best_weakest_signal = weakest_signal
            best_strongest_signal = strongest_signal

    if best_integration is None:
        print("\n❌ Failed to find optimal integration time!")
        return None

    # Apply final integration time
    usb.set_integration(best_integration)
    time.sleep(0.1)

    weakest_percent = (best_weakest_signal / detector_max) * 100
    strongest_percent = (best_strongest_signal / detector_max) * 100

    print(f"\n" + "="*80)
    print(f"✅ INTEGRATION TIME OPTIMIZED (S-MODE)")
    print(f"="*80)
    print(f"")
    print(f"   Optimal integration time: {best_integration*1000:.1f}ms")
    print(f"")
    print(f"   Weakest LED ({weakest_ch.upper()} @ LED=255):")
    print(f"      Signal: {best_weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
    print(f"      Status: {'✅ OPTIMAL' if weakest_min <= best_weakest_signal <= weakest_max else '⚠️  Acceptable'}")
    print(f"")
    print(f"   Strongest LED ({strongest_ch.upper()} @ LED=255):")
    print(f"      Signal: {best_strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")
    print(f"      Status: {'✅ Safe (<95%)' if best_strongest_signal < strongest_max else '⚠️  Near saturation!'}")
    print(f"")
    print(f"   This integration time will be used for subsequent steps")
    print(f"="*80)

    return {
        'integration_time': best_integration,
        'weakest_signal': best_weakest_signal,
        'strongest_signal': best_strongest_signal
    }


def main():
    print("="*80)
    print("CALIBRATION TEST: STEPS 1-4")
    print("="*80)
    print("\nThis test mimics the actual calibration process.")
    print("It will perform Steps 1-4 of the 6-step calibration.\n")

    # Initialize controller
    print("Initializing PicoP4SPR controller...")
    ctrl = PicoP4SPR()

    if not ctrl.open():
        print("❌ Failed to open controller")
        return 1

    print(f"✅ Controller connected: {ctrl.name}")
    print(f"   Firmware version: {getattr(ctrl, 'version', 'Unknown')}")

    # Initialize spectrometer
    print("\nInitializing USB4000 spectrometer...")
    usb = USB4000()

    if not usb.open():
        print("❌ Failed to open spectrometer")
        ctrl.close()
        return 1

    print(f"✅ Spectrometer connected")

    try:
        # Step 1: Hardware validation
        if not test_step_1(ctrl):
            return 1

        # Step 2: Wavelength calibration
        wave_info = test_step_2(usb)
        if wave_info is None:
            return 1

        # Step 3: LED brightness ranking
        ranking_info = test_step_3(ctrl, usb, wave_info)
        if ranking_info is None:
            return 1

        # Step 4: Integration time optimization
        opt_info = test_step_4(ctrl, usb, wave_info, ranking_info)
        if opt_info is None:
            return 1

        # Summary
        print("\n" + "="*80)
        print("✅ CALIBRATION STEPS 1-4 COMPLETE")
        print("="*80)
        print(f"\nResults:")
        print(f"   Weakest LED: {ranking_info['weakest_channel'].upper()}")
        print(f"   Strongest LED: {ranking_info['strongest_channel'].upper()}")
        print(f"   Optimal integration time: {opt_info['integration_time']*1000:.1f}ms")
        print(f"   Weakest signal: {opt_info['weakest_signal']:.0f} counts")
        print(f"   Strongest signal: {opt_info['strongest_signal']:.0f} counts")
        print("\nSteps 5-6 would continue with:")
        print("   - Step 5: P-mode integration time and LED balance")
        print("   - Step 6: S-mode reference signal measurement")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up
        print("\nFinal cleanup: Turning off all LEDs...")
        try:
            ctrl.turn_off_channels()
            time.sleep(0.5)
        except:
            pass
        ctrl.close()
        usb.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
