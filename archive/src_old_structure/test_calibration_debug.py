"""Debug script to test calibration and show error details.

Run this from the src directory to diagnose calibration failures.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controllers.controller_hal import ControllerHAL
from hardware.spectrometer_usb2000 import USB2000Plus_Detector

from utils.calibration_6step import run_full_6step_calibration


def main():
    print("\n" + "=" * 80)
    print("CALIBRATION DEBUG TEST")
    print("=" * 80 + "\n")

    # Initialize hardware
    print("1. Initializing spectrometer...")
    usb = USB2000Plus_Detector()
    if not usb.connect():
        print("❌ Failed to connect to spectrometer")
        return 1
    print("✅ Spectrometer connected\n")

    print("2. Initializing controller...")
    ctrl = ControllerHAL("cavro")
    if not ctrl.connect():
        print("❌ Failed to connect to controller")
        usb.disconnect()
        return 1
    print("✅ Controller connected\n")

    try:
        print("3. Running LED calibration...")
        print("-" * 80 + "\n")

        # Load device configuration
        from utils.device_configuration import DeviceConfiguration

        device_serial = usb.serial_number
        device_config = DeviceConfiguration(device_serial=device_serial)

        result = run_full_6step_calibration(
            usb,
            ctrl,
            "cavro",
            device_config=device_config,
            detector_serial=device_serial,
        )

        print("\n" + "-" * 80)
        print("CALIBRATION COMPLETE")
        print("=" * 80)
        print("\nResult:")
        print(f"  success: {result.success}")
        print(f"  ch_error_list: {result.ch_error_list}")
        print(f"  spr_fwhm: {result.spr_fwhm}")
        print(f"  s_mode_intensity: {result.s_mode_intensity}")
        print(f"  p_mode_intensity: {result.p_mode_intensity}")
        print(f"  integration_time: {result.integration_time}")

        if not result.success:
            print("\n❌ CALIBRATION FAILED")
            print(
                f"   Channels with errors: {', '.join([ch.upper() for ch in result.ch_error_list])}",
            )
            print("\n   Review the log output above for specific error messages.")
            print("   Look for lines with ❌ or ⚠️ to identify the issues.")
            return 1
        print("\n✅ CALIBRATION SUCCESSFUL")
        return 0

    except Exception as e:
        print(f"\n❌ Exception during calibration: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        print("\n4. Cleaning up...")
        ctrl.disconnect()
        usb.disconnect()
        print("✅ Hardware disconnected\n")


if __name__ == "__main__":
    sys.exit(main())
