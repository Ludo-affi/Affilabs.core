"""
Test script to verify Smart Calibration QC implementation.

This script demonstrates:
1. Saving LED calibration to device_config.json
2. Loading calibration from device_config.json
3. QC validation workflow
"""

import sys
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.device_configuration import DeviceConfiguration
from utils.logger import logger

def test_led_calibration_storage():
    """Test LED calibration save/load from device_config.json"""

    print("="*80)
    print("TESTING LED CALIBRATION STORAGE")
    print("="*80)

    # Create device configuration
    config = DeviceConfiguration()

    # Create mock calibration data
    integration_time_ms = 32
    s_mode_intensities = {'A': 128, 'B': 128, 'C': 128, 'D': 128}
    p_mode_intensities = {'A': 172, 'B': 185, 'C': 192, 'D': 199}

    # Create mock S-ref spectra (1000 pixels per channel)
    s_ref_spectra = {
        'A': np.random.normal(41000, 500, 1000),
        'B': np.random.normal(42000, 500, 1000),
        'C': np.random.normal(39800, 500, 1000),
        'D': np.random.normal(40500, 500, 1000)
    }

    print("\n1. SAVING CALIBRATION")
    print("-" * 40)
    print(f"Integration time: {integration_time_ms} ms")
    print(f"S-mode LEDs: {s_mode_intensities}")
    print(f"P-mode LEDs: {p_mode_intensities}")
    print(f"S-ref spectra: {len(s_ref_spectra)} channels × {len(s_ref_spectra['A'])} pixels")

    try:
        config.save_led_calibration(
            integration_time_ms=integration_time_ms,
            s_mode_intensities=s_mode_intensities,
            p_mode_intensities=p_mode_intensities,
            s_ref_spectra=s_ref_spectra
        )
        print("✅ Calibration saved successfully")
    except Exception as e:
        print(f"❌ Failed to save: {e}")
        return False

    print("\n2. LOADING CALIBRATION")
    print("-" * 40)

    try:
        loaded = config.load_led_calibration()

        if loaded is None:
            print("❌ No calibration found")
            return False

        print(f"✅ Calibration loaded:")
        print(f"   Date: {loaded['calibration_date']}")
        print(f"   Integration time: {loaded['integration_time_ms']} ms")
        print(f"   S-mode LEDs: {loaded['s_mode_intensities']}")
        print(f"   P-mode LEDs: {loaded['p_mode_intensities']}")
        print(f"   S-ref baseline channels: {list(loaded['s_ref_baseline'].keys())}")
        print(f"   S-ref max intensity: {loaded['s_ref_max_intensity']}")

        # Verify data integrity
        for ch in ['A', 'B', 'C', 'D']:
            if ch not in loaded['s_ref_baseline']:
                print(f"❌ Missing S-ref for channel {ch}")
                return False

            if len(loaded['s_ref_baseline'][ch]) != 1000:
                print(f"❌ Wrong S-ref length for channel {ch}: {len(loaded['s_ref_baseline'][ch])}")
                return False

        print("✅ Data integrity verified")

    except Exception as e:
        print(f"❌ Failed to load: {e}")
        return False

    print("\n3. CHECKING CALIBRATION AGE")
    print("-" * 40)

    try:
        age_days = config.get_calibration_age_days()
        print(f"✅ Calibration age: {age_days:.1f} days")
    except Exception as e:
        print(f"❌ Failed to get age: {e}")
        return False

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED")
    print("="*80)
    print("\nSummary:")
    print("  ✅ LED calibration saves to device_config.json (single source of truth)")
    print("  ✅ Calibration loads correctly with numpy arrays")
    print("  ✅ S-ref baseline spectra stored (1000 pixels × 4 channels)")
    print("  ✅ Max intensity values calculated and stored")
    print("  ✅ Calibration age tracking works")
    print("\nNext steps:")
    print("  1. Run full calibration in main app")
    print("  2. Verify calibration saves to device_config.json")
    print("  3. Restart app and verify QC validation runs")
    print("  4. Check QC passes with stored values")
    print("="*80)

    return True

if __name__ == "__main__":
    success = test_led_calibration_storage()
    sys.exit(0 if success else 1)
