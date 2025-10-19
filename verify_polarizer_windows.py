"""
Verify Polarizer Window Assignment (S vs P Mode)

Tests both possible assignments of the two discovered transmission windows:
- Configuration 1: S=50 (Window 1), P=165 (Window 2)
- Configuration 2: S=165 (Window 2), P=50 (Window 1)

Measures S-mode and P-mode signals to determine which configuration
provides proper polarization discrimination (S-mode high, P-mode low).

Expected behavior:
- S-mode should show STRONG signal (polarizer aligned for maximum transmission)
- P-mode should show WEAKER signal (polarizer rotated ~90° for partial blocking)
- S/P ratio should be > 2.0× (ideally 5-20×)

Usage:
    python verify_polarizer_windows.py
"""

import time
import numpy as np
from pathlib import Path
import sys

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from utils.controller import PicoP4SPR
from utils.usb4000_oceandirect import USB4000OceanDirect as USB4000

def test_polarizer_config(ctrl, usb, s_pos, p_pos, config_name):
    """Test a specific S/P position configuration.

    Args:
        ctrl: PicoP4SPR controller instance
        usb: USB4000 spectrometer instance
        s_pos: S-mode servo position (0-255)
        p_pos: P-mode servo position (0-255)
        config_name: Human-readable name for this configuration

    Returns:
        dict with 's_signal', 'p_signal', 'sp_ratio', 's_saturated', 'p_saturated'
    """
    print("\n" + "=" * 80)
    print(f"Testing Configuration: {config_name}")
    print(f"S-position: {s_pos}, P-position: {p_pos}")
    print("=" * 80)

    # Set polarizer positions
    ctrl.servo_set(s=s_pos, p=p_pos)
    time.sleep(0.5)  # Let servo settle

    # Turn on LED channel A at full intensity
    ctrl.set_intensity("a", 255)
    time.sleep(0.2)

    # Test S-mode
    print("\n📊 Testing S-mode...")
    ctrl.set_mode("s")
    time.sleep(0.3)  # Let mode switch settle

    s_spectrum = usb.acquire_spectrum()
    if s_spectrum is None:
        print("   ❌ Failed to acquire S-mode spectrum")
        return None
    s_max = float(np.max(s_spectrum))
    s_mean = float(np.mean(s_spectrum))
    s_saturated = s_max >= 65535

    print(f"   S-mode signal: max={s_max:.1f} counts, mean={s_mean:.1f} counts")
    if s_saturated:
        print(f"   ⚠️  S-mode SATURATED (detector at max)")

    # Test P-mode
    print("\n📊 Testing P-mode...")
    ctrl.set_mode("p")
    time.sleep(0.3)  # Let mode switch settle

    p_spectrum = usb.acquire_spectrum()
    if p_spectrum is None:
        print("   ❌ Failed to acquire P-mode spectrum")
        return None
    p_max = float(np.max(p_spectrum))
    p_mean = float(np.mean(p_spectrum))
    p_saturated = p_max >= 65535

    print(f"   P-mode signal: max={p_max:.1f} counts, mean={p_mean:.1f} counts")
    if p_saturated:
        print(f"   ⚠️  P-mode SATURATED (detector at max)")

    # Calculate S/P ratio
    sp_ratio = s_max / p_max if p_max > 0 else 0.0

    print(f"\n📈 S/P Ratio: {sp_ratio:.2f}×")

    # Evaluate configuration quality
    print("\n🔍 Configuration Quality Assessment:")
    if s_saturated and p_saturated:
        print("   ❌ POOR: Both modes saturated - no discrimination")
        quality = "POOR"
    elif s_max < 10000:
        print("   ❌ POOR: S-mode signal too weak (< 10k counts)")
        quality = "POOR"
    elif sp_ratio < 2.0:
        print(f"   ❌ POOR: S/P ratio too low ({sp_ratio:.2f}× < 2.0×)")
        quality = "POOR"
    elif sp_ratio < 5.0:
        print(f"   ⚠️  FAIR: S/P ratio moderate ({sp_ratio:.2f}×, target > 5.0×)")
        quality = "FAIR"
    elif sp_ratio < 10.0:
        print(f"   ✅ GOOD: S/P ratio strong ({sp_ratio:.2f}×)")
        quality = "GOOD"
    else:
        print(f"   ✨ EXCELLENT: S/P ratio very strong ({sp_ratio:.2f}×)")
        quality = "EXCELLENT"

    return {
        's_signal': s_max,
        'p_signal': p_max,
        'sp_ratio': sp_ratio,
        's_saturated': s_saturated,
        'p_saturated': p_saturated,
        'quality': quality
    }

def main():
    print("=" * 80)
    print("POLARIZER WINDOW VERIFICATION")
    print("=" * 80)
    print("Testing both possible S/P window assignments...")
    print()
    print("Window 1 center: ~50 (positions 30-70)")
    print("Window 2 center: ~165 (positions 145-185)")
    print()

    # Initialize hardware
    print("🔌 Connecting to hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000()

    if not ctrl.open():
        print("❌ Failed to connect to PicoP4SPR controller")
        return

    if not usb.connect():
        print("❌ Failed to connect to spectrometer")
        ctrl.close()
        return

    print("✅ Connected to hardware")

    # Set integration time for testing (fast acquisition)
    usb.set_integration_time(0.050)  # 50ms
    print(f"Integration time: 50ms")

    # Test Configuration 1: S=50, P=165
    results_config1 = test_polarizer_config(
        ctrl, usb,
        s_pos=50,
        p_pos=165,
        config_name="Config 1 (S=Window1, P=Window2)"
    )

    if results_config1 is None:
        print("\n❌ Configuration 1 test failed")
        ctrl.set_intensity("a", 0)
        ctrl.close()
        usb.disconnect()
        return

    # Test Configuration 2: S=165, P=50
    results_config2 = test_polarizer_config(
        ctrl, usb,
        s_pos=165,
        p_pos=50,
        config_name="Config 2 (S=Window2, P=Window1)"
    )

    if results_config2 is None:
        print("\n❌ Configuration 2 test failed")
        ctrl.set_intensity("a", 0)
        ctrl.close()
        usb.disconnect()
        return

    # Clean up - turn off LED
    ctrl.set_intensity("a", 0)
    ctrl.close()
    usb.disconnect()

    # Compare results and recommend best configuration
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATION")
    print("=" * 80)
    print()
    print("Configuration 1 (S=50, P=165):")
    print(f"   S-mode: {results_config1['s_signal']:.1f} counts")
    print(f"   P-mode: {results_config1['p_signal']:.1f} counts")
    print(f"   S/P Ratio: {results_config1['sp_ratio']:.2f}×")
    print(f"   Quality: {results_config1['quality']}")
    print()
    print("Configuration 2 (S=165, P=50):")
    print(f"   S-mode: {results_config2['s_signal']:.1f} counts")
    print(f"   P-mode: {results_config2['p_signal']:.1f} counts")
    print(f"   S/P Ratio: {results_config2['sp_ratio']:.2f}×")
    print(f"   Quality: {results_config2['quality']}")
    print()

    # Determine winner
    quality_score = {'POOR': 0, 'FAIR': 1, 'GOOD': 2, 'EXCELLENT': 3}
    score1 = quality_score.get(results_config1['quality'], 0)
    score2 = quality_score.get(results_config2['quality'], 0)

    if score1 > score2:
        winner = "Configuration 1"
        winner_s = 50
        winner_p = 165
        winner_ratio = results_config1['sp_ratio']
    elif score2 > score1:
        winner = "Configuration 2"
        winner_s = 165
        winner_p = 50
        winner_ratio = results_config2['sp_ratio']
    else:
        # Same quality - pick higher S/P ratio
        if results_config1['sp_ratio'] > results_config2['sp_ratio']:
            winner = "Configuration 1"
            winner_s = 50
            winner_p = 165
            winner_ratio = results_config1['sp_ratio']
        else:
            winner = "Configuration 2"
            winner_s = 165
            winner_p = 50
            winner_ratio = results_config2['sp_ratio']

    print("=" * 80)
    print(f"🏆 WINNER: {winner}")
    print("=" * 80)
    print(f"✅ Recommended Polarizer Positions:")
    print(f"   S-position: {winner_s}")
    print(f"   P-position: {winner_p}")
    print(f"   S/P Ratio: {winner_ratio:.2f}×")
    print()
    print("Next Steps:")
    print("1. Update device configuration file with these positions:")
    print(f"   {{")
    print(f'     "polarizer_s_position": {winner_s},')
    print(f'     "polarizer_p_position": {winner_p}')
    print(f"   }}")
    print()
    print("2. Re-run main SPR calibration:")
    print("   python run_app.py")
    print("   Click 'Calibrate' button")
    print()
    print("Expected: With correct polarizer positions, calibration should")
    print("reach 60-80% detector signal and complete successfully!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
