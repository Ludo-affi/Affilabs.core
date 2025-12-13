"""Run afterglow calibration to regenerate optical_calibration.json with all 4 channels.

This is a simplified helper script that shows you the command to run.

The actual calibration should be run from the main application or by directly
calling the calibration methods.

Usage:
    python show_afterglow_calibration_steps.py
"""

import sys
from pathlib import Path

print("=" * 80)
print("AFTERGLOW CALIBRATION - REGENERATE ALL 4 CHANNELS")
print("=" * 80)
print()
print("The afterglow calibration requires running from within the main application")
print("because it needs access to all the hardware managers and utilities.")
print()
print("=" * 80)
print("OPTION 1: Run from GUI (RECOMMENDED)")
print("=" * 80)
print()
print("1. Start the main application:")
print("   cd \"c:\\Users\\ludol\\ezControl-AI\\Affilabs.core beta\"")
print("   python main_simplified.py")
print()
print("2. Wait for hardware to connect and calibration to complete")
print()
print("3. After calibration completes, the system should automatically run")
print("   afterglow calibration")
print()
print("4. Verify the result:")
print("   python -c \"import json; data = json.load(open(r'config\\devices\\FLMT09116\\optical_calibration.json')); print('Channels:', list(data['channel_data'].keys()))\"")
print()
print("=" * 80)
print("OPTION 2: Trigger via Python Console in Application")
print("=" * 80)
print()
print("If the application is already running:")
print()
print("1. Open Python console or debugger")
print()
print("2. Run this code:")
print()
print("   # Get calibrator instance from application")
print("   calibrator = app.calibration_coordinator.calibrator")
print()
print("   # Run optical calibration")
print("   success = calibrator._run_optical_calibration()")
print()
print("   if success:")
print("       print('[OK] Optical calibration complete')")
print("   else:")
print("       print('[ERROR] Optical calibration failed')")
print()
print("=" * 80)
print("OPTION 3: Check if Already Done")
print("=" * 80)
print()
print("The optical calibration file might already exist and just need to be")
print("updated with channel 'd' data.")
print()
print("Check current status:")
print()
print("   cd \"c:\\Users\\ludol\\ezControl-AI\\Affilabs.core beta\"")
print("   python -c \"import json; data = json.load(open('config/devices/FLMT09116/optical_calibration.json')); channels = list(data['channel_data'].keys()); print(f'Channels: {channels}'); print(f'Count: {len(channels)}/4')\"")
print()
print("=" * 80)
print("CURRENT FILE STATUS")
print("=" * 80)
print()

# Try to check current status
try:
    import json
    cal_file = Path("config/devices/FLMT09116/optical_calibration.json")

    if cal_file.exists():
        with open(cal_file, 'r') as f:
            data = json.load(f)
            channels = list(data.get('channel_data', {}).keys())

        print(f"[OK] File exists: {cal_file}")
        print(f"   Channels present: {channels}")
        print(f"   Count: {len(channels)}/4")

        if len(channels) == 4:
            print("   [OK] All 4 channels present!")
            print()
            print("   The file seems complete. The error might be from loading it.")
            print("   Try restarting the application.")
        else:
            missing = [ch for ch in ['a', 'b', 'c', 'd'] if ch not in channels]
            print(f"   [ERROR] Missing channels: {missing}")
            print()
            print("   ACTION REQUIRED: Re-run optical calibration using Option 1 or 2 above")

        # Show data point counts
        print()
        print("Data points per channel:")
        for ch in channels:
            num_points = len(data['channel_data'][ch]['integration_time_data'])
            print(f"  Channel {ch}: {num_points} integration times")

    else:
        print(f"[ERROR] File not found: {cal_file}")
        print()
        print("ACTION REQUIRED: Run initial optical calibration using Option 1 above")

except Exception as e:
    print(f"[ERROR] Error checking file: {e}")
    print()
    print("Run from: c:\\Users\\ludol\\ezControl-AI\\Affilabs.core beta")

print()
print("=" * 80)
print()
print("For detailed information, see:")
print("  AFTERGLOW_CHANNEL_D_MISSING_FIX.md")
print()
print("=" * 80)
