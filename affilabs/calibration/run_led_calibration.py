"""
LED Bilinear Calibration Runner
================================

User-facing script to run full LED calibration workflow:
1. S-polarization calibration
2. P-polarization calibration
3. Dark spectrum collection
4. Save results to device configuration

Usage:
    python affilabs/calibration/run_led_calibration.py [--target-counts 52000] [--verbose]

Author: Affilabs
Date: December 2025
"""

import sys
from pathlib import Path

# Add parent to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Import from affilabs package
from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000
from affilabs.hardware.controller_adapter import wrap_existing_controller
from affilabs.hardware.spectrometer_adapter import wrap_existing_spectrometer
from affilabs.hardware.optimized_led_controller import create_optimized_controller
from affilabs.calibration.led_bilinear_calibrator import LEDBilinearCalibrator
from affilabs.utils.device_configuration import get_device_config
import argparse


def main():
    """Run full LED bilinear calibration workflow"""

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Run LED bilinear calibration (S-pol, P-pol, darks)'
    )
    parser.add_argument(
        '--target-counts',
        type=int,
        default=52000,
        help='Target detector counts (default: 52000 = 80%% of detector max)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed progress messages'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/device_config.json',
        help='Path to device configuration file'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate calibration plots'
    )
    parser.add_argument(
        '--plot-file',
        type=str,
        default='calibration_results/led_calibration_plot.png',
        help='Path to save plot (default: calibration_results/led_calibration_plot.png)'
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("LED BILINEAR CALIBRATION SYSTEM")
    print("="*80)
    print(f"\nTarget counts: {args.target_counts}")
    print(f"Config file: {args.config}")

    # Initialize hardware
    print("\nConnecting to hardware...")
    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    # Connect
    if not controller.connect():
        print("ERROR: Could not connect to LED controller!")
        return 1

    if not spectrometer.connect():
        print("ERROR: Could not connect to spectrometer!")
        controller.disconnect()
        return 1

    print("[OK] Connected to hardware")

    # Create optimized LED controller
    opt_controller = create_optimized_controller(controller_hw)

    # Enable calibration mode
    if opt_controller.enter_calibration_mode():
        print("[OK] Calibration mode enabled")

    try:
        # Create calibrator
        calibrator = LEDBilinearCalibrator(controller, spectrometer, opt_controller)

        # Run full calibration
        results = calibrator.run_full_calibration(
            target_counts=args.target_counts,
            verbose=args.verbose
        )

        # Save to device configuration
        print(f"\nSaving results to {args.config}...")

        # Convert models to dict format for device config
        models_s = {
            led: {
                'slope': model.slope,
                'offset': model.offset,
                'r_squared': model.r_squared
            }
            for led, model in results['s_pol'].models.items()
        }

        models_p = {
            led: {
                'slope': model.slope,
                'offset': model.offset,
                'r_squared': model.r_squared
            }
            for led, model in results['p_pol'].models.items()
        }

        # Save raw calibration results to JSON
        print("\nSaving calibration results to JSON...")
        json_path = calibrator.save_calibration_results(results)

        # Save to device config
        config = get_device_config(args.config)
        config.save_led_bilinear_models(
            models_s=models_s,
            models_p=models_p,
            target_counts=args.target_counts
        )

        print(f"[OK] Calibration saved to {args.config}")

        # Print summary
        print("\n" + "="*80)
        print("CALIBRATION SUMMARY")
        print("="*80)

        print("\nS-Polarization Models:")
        for led, model in results['s_pol'].models.items():
            print(f"  LED {led}: slope={model.slope:.3f}, offset={model.offset:.1f}, R²={model.r_squared:.6f}")

        print("\nP-Polarization Models:")
        for led, model in results['p_pol'].models.items():
            print(f"  LED {led}: slope={model.slope:.3f}, offset={model.offset:.1f}, R²={model.r_squared:.6f}")

        print("\nDark Spectra Collected:")
        for time_ms, (spectrum, avg_counts) in results['dark_spectra'].items():
            print(f"  T={time_ms:5.2f}ms: {avg_counts:6.0f} counts (dark)")

        # Generate plots if requested
        if args.plot:
            print("\nGenerating calibration plots...")
            from pathlib import Path
            plot_path = Path(args.plot_file)
            plot_path.parent.mkdir(parents=True, exist_ok=True)
            calibrator.plot_calibration_results(results, save_path=str(plot_path))

        print("\n[SUCCESS] LED bilinear calibration complete!")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Calibration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()
        print("\n[OK] Hardware disconnected")


if __name__ == '__main__':
    sys.exit(main())
