"""Fix Optical Calibration - Remove incomplete/old calibration file.

This script removes the old optical calibration file that is missing channel 'd'.
After running this, the system will detect the missing file and prompt you to
run a fresh optical calibration with all 4 channels.

Usage:
    python fix_optical_calibration.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.device_integration import get_device_optical_calibration_path


def main():
    """Remove old optical calibration file and show status."""
    print("=" * 70)
    print("OPTICAL CALIBRATION FIX UTILITY")
    print("=" * 70)
    print()

    # Get optical calibration path
    try:
        optical_cal_path = get_device_optical_calibration_path()

        if not optical_cal_path:
            print("❌ No device detected or device manager not initialized")
            print("   Please connect hardware first")
            return

        print("📁 Device optical calibration path:")
        print(f"   {optical_cal_path}")
        print()

        if not optical_cal_path.exists():
            print("✅ No optical calibration file exists")
            print("   System is ready for fresh calibration")
            print()
            print("NEXT STEPS:")
            print("1. Start the main application")
            print("2. Connect hardware")
            print("3. Click 'Run Optical Calibration...' in Advanced Settings")
            print("4. System will offer to run optical calibration first (recommended)")
            print("5. Calibration will include all 4 channels with S-mode intensities")
            return

        # File exists - check if it has all channels
        import json

        with open(optical_cal_path) as f:
            data = json.load(f)

        channels = list(data.get("channel_data", {}).keys())
        print("📊 Current optical calibration file:")
        print(f"   Channels: {channels}")
        print(f"   Created: {data.get('metadata', {}).get('created', 'unknown')}")
        print()

        if len(channels) < 4 or "d" not in channels:
            print("⚠️  ISSUE DETECTED: Missing channel 'd'")
            print(f"   Found only: {channels}")
            print("   Expected: ['a', 'b', 'c', 'd']")
            print()

            response = input("Delete old calibration file? (y/n): ").strip().lower()
            if response == "y":
                # Backup first
                backup_path = optical_cal_path.with_suffix(".json.backup")
                import shutil

                shutil.copy2(optical_cal_path, backup_path)
                print(f"✅ Backup created: {backup_path}")

                # Delete
                optical_cal_path.unlink()
                print("✅ Deleted old optical calibration file")
                print()
                print("NEXT STEPS:")
                print("1. Start the main application")
                print("2. Connect hardware")
                print("3. Click 'Run Optical Calibration...' in Advanced Settings")
                print("4. System will detect missing file and offer optimized workflow")
                print("5. New calibration will include all 4 channels with S-mode")
            else:
                print("❌ Calibration file NOT deleted")
                print("   System will continue using incomplete calibration")
        else:
            print("✅ Optical calibration file is complete (all 4 channels)")
            print()
            # Check if it has S-mode LED intensities
            led_intensities = data.get("metadata", {}).get(
                "led_intensities_s_mode",
                None,
            )
            polarization = data.get("metadata", {}).get("polarization_mode", "unknown")

            print(f"   Polarization mode: {polarization}")
            if led_intensities:
                print(f"   S-mode LED intensities: {led_intensities}")
                print("   ✅ Ready for optimized LED calibration workflow")
            else:
                print("   ⚠️  No S-mode LED intensities saved")
                print("   Consider regenerating for optimized workflow")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
