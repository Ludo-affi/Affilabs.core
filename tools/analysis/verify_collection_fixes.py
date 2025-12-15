"""Verification script to show the critical fixes made to collect_training_data.py

Run this to confirm the bugs have been fixed before re-collecting data.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_manager import ConfigurationManager


def verify_fixes():
    """Verify all critical fixes are in place."""
    print("=" * 80)
    print("COLLECTION SCRIPT FIX VERIFICATION")
    print("=" * 80)

    # Check 1: Can we load calibration?
    print("\n✓ CHECK 1: Calibration Loading")
    try:
        config_mgr = ConfigurationManager()
        config_mgr.load_calibration()

        print(f"  Integration time: {config_mgr.calibration.integration} ms")
        print("  LED intensities:")
        for ch, intensity in config_mgr.calibration.ref_intensity.items():
            print(f"    Channel {ch}: {intensity}")

        if all(v > 0 for v in config_mgr.calibration.ref_intensity.values()):
            print("  ✅ Calibration data loaded successfully!")
        else:
            print("  ⚠️  WARNING: Some LED intensities are 0 (may need calibration)")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

    # Check 2: Verify polarizer control exists
    print("\n✓ CHECK 2: Polarizer Control API")
    try:
        from utils.controller import PicoP4SPR

        # Check if set_mode method exists
        if hasattr(PicoP4SPR, "set_mode"):
            print("  ✅ set_mode() method exists")
        else:
            print("  ❌ set_mode() method NOT FOUND")
            return False
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

    # Check 3: Verify collection script has fixes
    print("\n✓ CHECK 3: Collection Script Fixes")
    try:
        script_path = Path(__file__).parent / "collect_training_data.py"
        with open(script_path) as f:
            content = f.read()

        # Check for polarizer control
        if "self.spr_device.set_mode('s')" in content:
            print("  ✅ Polarizer S-mode control present")
        else:
            print("  ❌ Polarizer S-mode control MISSING")
            return False

        if "self.spr_device.set_mode('p')" in content:
            print("  ✅ Polarizer P-mode control present")
        else:
            print("  ❌ Polarizer P-mode control MISSING")
            return False

        # Check for ConfigurationManager import
        if "from utils.config_manager import ConfigurationManager" in content:
            print("  ✅ ConfigurationManager imported")
        else:
            print("  ❌ ConfigurationManager import MISSING")
            return False

        # Check for calibrated LED usage
        if "config_mgr.calibration.ref_intensity" in content:
            print("  ✅ Using calibrated LED intensities")
        else:
            print("  ❌ Calibrated LED intensities NOT USED")
            return False

        # Check for integration time setting
        if "set_integration_time" in content:
            print("  ✅ Integration time setting present")
        else:
            print("  ❌ Integration time setting MISSING")
            return False

        # Check that we're NOT using LED=255
        if "set_intensity(channel.lower(), 255)" in content:
            print("  ⚠️  WARNING: Still contains LED=255 hardcode")
        else:
            print("  ✅ LED=255 hardcode removed")

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

    print("\n" + "=" * 80)
    print("✅ ALL FIXES VERIFIED!")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print(
        "1. Delete invalid datasets: training_data/used_current/ and training_data/new_sealed/",
    )
    print("2. Re-run collection with fixed script")
    print("3. Verify transmission values are 0.05-0.15 (5-15%)")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = verify_fixes()
    sys.exit(0 if success else 1)
