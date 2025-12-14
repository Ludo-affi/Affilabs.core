"""
Quick hardware test to diagnose LED calibration issue.
Tests controller communication and LED response directly.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_hardware():
    """Test hardware communication directly."""

    print("=" * 70)
    print("HARDWARE COMMUNICATION TEST")
    print("=" * 70)
    print()

    # Import hardware classes
    try:
        from utils.controller import PicoP4SPR, ArduinoController
        from utils.usb4000_wrapper import USB4000
        print("✅ Imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Connect to controller
    print("\n1. CONTROLLER CONNECTION TEST")
    print("-" * 70)
    ctrl = None

    print("   Trying PicoP4SPR...")
    try:
        ctrl = PicoP4SPR()
        if ctrl.open():
            print(f"   ✅ PicoP4SPR connected on port: {ctrl._ser.port if hasattr(ctrl, '_ser') and ctrl._ser else 'unknown'}")
        else:
            print("   ❌ PicoP4SPR failed to open")
            ctrl = None
    except Exception as e:
        print(f"   ❌ PicoP4SPR error: {e}")
        ctrl = None

    if not ctrl:
        print("   Trying ArduinoController...")
        try:
            ctrl = ArduinoController()
            if ctrl.open():
                print(f"   ✅ ArduinoController connected on port: {ctrl._ser.port if hasattr(ctrl, '_ser') and ctrl._ser else 'unknown'}")
            else:
                print("   ❌ ArduinoController failed to open")
                return False
        except Exception as e:
            print(f"   ❌ ArduinoController error: {e}")
            return False

    print(f"   Controller type: {type(ctrl).__name__}")
    print(f"   Has serial port: {hasattr(ctrl, '_ser') and ctrl._ser is not None}")

    # Connect to spectrometer
    print("\n2. SPECTROMETER CONNECTION TEST")
    print("-" * 70)
    try:
        usb = USB4000()
        if usb.open():
            print(f"   ✅ Spectrometer connected")
            print(f"   Model: {getattr(usb, 'model', 'unknown')}")
            print(f"   Serial: {getattr(usb, 'serial_number', 'unknown')}")
        else:
            print("   ❌ Spectrometer failed to open")
            return False
    except Exception as e:
        print(f"   ❌ Spectrometer error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test mode switching
    print("\n3. MODE SWITCHING TEST")
    print("-" * 70)
    try:
        print("   Setting S-mode...")
        ctrl.set_mode('s')
        time.sleep(0.1)
        print("   ✅ S-mode command sent")

        print("   Setting P-mode...")
        ctrl.set_mode('p')
        time.sleep(0.1)
        print("   ✅ P-mode command sent")

        print("   Back to S-mode...")
        ctrl.set_mode('s')
        time.sleep(0.1)
        print("   ✅ Mode switching successful")
    except Exception as e:
        print(f"   ❌ Mode switching failed: {e}")
        return False

    # Test LED commands
    print("\n4. LED COMMAND TEST")
    print("-" * 70)
    channels = ['a', 'b', 'c', 'd']

    for ch in channels:
        print(f"\n   Testing LED {ch.upper()}:")
        try:
            # Turn on LED
            print(f"      Setting intensity to 200/255...")
            result = ctrl.set_intensity(ch=ch, raw_val=200)
            print(f"      Command returned: {result}")
            time.sleep(0.3)

            # Read spectrum
            print(f"      Reading spectrum...")
            spectrum = usb.read_intensity()

            if spectrum is None:
                print(f"      ❌ Spectrometer returned None!")
                continue

            max_signal = float(np.max(spectrum))
            print(f"      Max signal: {max_signal:.0f} counts")

            if max_signal > 100:
                print(f"      ✅ LED {ch.upper()} is working (signal > 100)")
            else:
                print(f"      ⚠️ LED {ch.upper()} weak signal (< 100 counts)")

            # Turn off LED
            print(f"      Turning off...")
            ctrl.set_intensity(ch=ch, raw_val=0)
            time.sleep(0.2)

        except Exception as e:
            print(f"      ❌ Error testing LED {ch.upper()}: {e}")
            import traceback
            traceback.print_exc()

    # Test all LEDs off
    print("\n5. ALL LEDS OFF TEST")
    print("-" * 70)
    try:
        print("   Turning off all channels...")
        ctrl.turn_off_channels()
        time.sleep(0.3)

        print("   Reading dark spectrum...")
        dark_spectrum = usb.read_intensity()

        if dark_spectrum is None:
            print("   ❌ Spectrometer returned None!")
        else:
            dark_max = float(np.max(dark_spectrum))
            print(f"   Dark signal: {dark_max:.0f} counts")
            if dark_max < 1000:
                print("   ✅ Dark signal is low (LEDs are off)")
            else:
                print(f"   ⚠️ Dark signal is high ({dark_max:.0f} counts) - LEDs may still be on")
    except Exception as e:
        print(f"   ❌ Error in dark test: {e}")
        import traceback
        traceback.print_exc()

    # Test rapid LED switching (like calibration does)
    print("\n6. RAPID LED SWITCHING TEST (simulates calibration)")
    print("-" * 70)
    try:
        ctrl.set_mode('s')
        time.sleep(0.1)

        for i, ch in enumerate(channels):
            print(f"   Switch {i+1}/4: LED {ch.upper()} at 150...")
            ctrl.set_intensity(ch=ch, raw_val=150)
            time.sleep(0.1)  # Short delay like calibration

            spectrum = usb.read_intensity()
            if spectrum is None:
                print(f"      ❌ Read failed!")
            else:
                signal = float(np.max(spectrum))
                print(f"      Signal: {signal:.0f} counts")

        print("   ✅ Rapid switching test complete")

    except Exception as e:
        print(f"   ❌ Rapid switching failed: {e}")
        import traceback
        traceback.print_exc()

    # Final cleanup
    print("\n7. CLEANUP")
    print("-" * 70)
    try:
        ctrl.turn_off_channels()
        print("   ✅ All LEDs turned off")
    except:
        pass

    print("\n" + "=" * 70)
    print("HARDWARE TEST COMPLETE")
    print("=" * 70)

    return ctrl, usb


def test_full_calibration(ctrl, usb):
    """Run the actual LED calibration code."""

    print("\n\n" + "=" * 70)
    print("FULL LED CALIBRATION TEST")
    print("=" * 70)
    print()

    try:
        from utils.led_calibration import perform_full_led_calibration
        from utils.device_configuration import DeviceConfiguration
        from settings import INTEGRATION_STEP

        print("✅ Calibration modules imported")

        # Load device configuration
        device_serial = getattr(usb, 'serial_number', None)
        device_config = DeviceConfiguration(device_serial=device_serial)
        print(f"✅ Device config loaded for S/N: {device_serial}")

        # Run calibration
        print("\n🚀 Starting LED calibration...")
        print("   (This will take 30-60 seconds)")
        print()

        cal_result = perform_full_led_calibration(
            usb=usb,
            ctrl=ctrl,
            device_type='P4SPR',
            single_mode=False,
            single_ch='a',
            integration_step=INTEGRATION_STEP,
            stop_flag=None,
            progress_callback=lambda msg: print(f"   Progress: {msg}"),
            device_config=device_config
        )

        print("\n" + "=" * 70)
        print("CALIBRATION RESULTS")
        print("=" * 70)

        if cal_result.success:
            print("\n✅ CALIBRATION SUCCESSFUL!")
            print(f"\n   Integration time: {cal_result.integration_time}ms")
            print(f"   Number of scans: {cal_result.num_scans}")
            print(f"\n   S-mode LED intensities:")
            for ch, intensity in cal_result.ref_intensity.items():
                print(f"      Channel {ch.upper()}: {intensity}/255")

            print(f"\n   P-mode LED intensities:")
            for ch, intensity in cal_result.leds_calibrated.items():
                print(f"      Channel {ch.upper()}: {intensity}/255")

            print(f"\n   Reference signals acquired:")
            for ch, ref_sig in cal_result.ref_sig.items():
                max_signal = float(np.max(ref_sig)) if ref_sig is not None else 0
                print(f"      Channel {ch.upper()}: max={max_signal:.0f} counts")

            if cal_result.ch_error_list:
                print(f"\n   ⚠️ Channels with warnings: {', '.join([c.upper() for c in cal_result.ch_error_list])}")
            else:
                print(f"\n   ✅ All channels passed QC")

            print("\n" + "=" * 70)
            return True

        else:
            print("\n❌ CALIBRATION FAILED")
            print(f"   Error: {cal_result.error if hasattr(cal_result, 'error') else 'Unknown error'}")
            print(f"   Failed channels: {cal_result.ch_error_list}")
            print("\n" + "=" * 70)
            return False

    except Exception as e:
        print(f"\n❌ CALIBRATION EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 70)
        return False


if __name__ == "__main__":
    try:
        # Run hardware tests first
        result = test_hardware()
        if not result or len(result) != 2:
            print("\n❌ Hardware tests failed")
            sys.exit(1)

        ctrl, usb = result
        print("\n✅ Hardware tests passed")

        # Ask user if they want to run full calibration
        print("\n" + "=" * 70)
        response = input("\nRun full LED calibration? (y/n): ").strip().lower()

        if response == 'y':
            success = test_full_calibration(ctrl, usb)
            if success:
                print("\n✅ Full calibration test passed")
                sys.exit(0)
            else:
                print("\n❌ Full calibration test failed")
                sys.exit(1)
        else:
            print("\nSkipping full calibration test")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
