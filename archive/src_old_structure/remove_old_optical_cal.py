"""Remove old optical calibration file that is missing channel 'd'."""

import json
from pathlib import Path

# Known device from logs
DEVICE_SERIAL = "FLMT09116"


def main():
    print("=" * 70)
    print("OPTICAL CALIBRATION CLEANUP")
    print("=" * 70)
    print()

    # Path to optical calibration
    optical_cal_path = Path(f"config/devices/{DEVICE_SERIAL}/optical_calibration.json")

    if not optical_cal_path.exists():
        print(f"✅ No optical calibration file found for device {DEVICE_SERIAL}")
        print("   Ready for fresh calibration with all 4 channels")
        return 0

    print(f"📂 Device: {DEVICE_SERIAL}")
    print(f"📁 Found: {optical_cal_path}")
    print()

    # Read and check the file
    try:
        with open(optical_cal_path) as f:
            cal_data = json.load(f)

        # Check what channels are present
        channels_present = list(cal_data.keys())
        channels_needed = ["a", "b", "c", "d"]

        print(f"📊 Current channels: {channels_present}")
        print(f"📊 Required channels: {channels_needed}")
        print()

        missing_channels = [ch for ch in channels_needed if ch not in channels_present]

        if missing_channels:
            print(f"❌ INCOMPLETE: Missing channels {missing_channels}")
            print()
            print("This old file will cause errors. It should be removed.")
            print()

            response = (
                input("Remove incomplete optical calibration? (y/n): ").strip().lower()
            )

            if response == "y":
                # Create backup
                backup_path = optical_cal_path.with_suffix(".json.backup")
                optical_cal_path.rename(backup_path)

                print(f"✅ Old file backed up to: {backup_path}")
                print("✅ Incomplete calibration removed")
                print()
                print("NEXT STEPS:")
                print("1. Start the main application")
                print("2. Connect hardware")
                print("3. Click 'Run Optical Calibration...' in Advanced Settings")
                print("4. New calibration will include all 4 channels with S-mode")
                print(
                    "5. LED calibration will automatically validate using saved intensities",
                )
                print()
                print("Expected time: ~10-11 minutes total")
                return 0
            print("❌ Cancelled - old file still present")
            return 1
        print("✅ Optical calibration is complete - all 4 channels present")
        print("   No action needed")
        return 0

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
