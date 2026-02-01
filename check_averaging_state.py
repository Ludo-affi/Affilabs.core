"""Check if Phase Photonics detector state shows averaging setting

This test verifies if the usb_set_averaging() call actually changes the 
detector's internal state.
"""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger


def check_averaging_state():
    """Check detector state before/after setting averaging."""
    print("\n" + "="*80)
    print("DETECTOR STATE CHECK - Hardware Averaging")
    print("="*80)

    try:
        # Connect
        detector = PhasePhotonics()
        detector.get_device_list()

        if not detector.devs or not detector.open():
            print("❌ Failed to connect to detector")
            return

        print(f"✓ Connected: {detector.serial_number}\n")

        # Get API instance
        api = detector.api
        handle = detector.spec

        # Check usb_set_averaging return code
        print("Testing usb_set_averaging() return codes...")

        print("\nSetting averaging to 1...")
        result1 = api.usb_set_averaging(handle, 1)
        print(f"  Return code: {result1} (0 = success)")

        print("\nSetting averaging to 8...")
        result8 = api.usb_set_averaging(handle, 8)
        print(f"  Return code: {result8} (0 = success)")

        print("\nSetting averaging to 255 (max)...")
        result255 = api.usb_set_averaging(handle, 255)
        print(f"  Return code: {result255} (0 = success)")

        print("\nSetting averaging to 300 (invalid - should fail)...")
        result_invalid = api.usb_set_averaging(handle, 300)
        print(f"  Return code: {result_invalid} (should be non-zero error)")

        print("\n" + "="*80)
        print("ANALYSIS")
        print("="*80)

        if result1 == 0 and result8 == 0 and result255 == 0:
            print("\n  ✅ usb_set_averaging() accepts valid values")
        else:
            print("\n  ❌ usb_set_averaging() failing on valid inputs")
            print(f"    result1={result1}, result8={result8}, result255={result255}")

        if result_invalid != 0:
            print("  ✅ usb_set_averaging() correctly rejects invalid value (300)")
        else:
            print("  ⚠ usb_set_averaging() accepted invalid value 300")

        print("\n  However, this doesn't prove averaging is actually working!")
        print("  The noise reduction test showed detector returns identical scans.")
        print("  This suggests usb_set_averaging() may be a no-op in firmware.")

        print("\n" + "="*80 + "\n")

        detector.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("State check failed")
        raise


if __name__ == "__main__":
    check_averaging_state()
