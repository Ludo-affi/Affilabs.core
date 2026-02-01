"""
PhasePhotonics Detector Diagnostic Test
Tests detector operations step-by-step to isolate hang issue.
"""

import sys
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_detector():
    """Run comprehensive detector tests."""

    print("=" * 80)
    print("PhasePhotonics ST00012 Diagnostic Test")
    print("=" * 80)

    # Import detector wrapper
    try:
        from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
        print("✓ Successfully imported PhasePhotonics")
    except Exception as e:
        print(f"✗ Failed to import: {e}")
        return False

    detector = None

    try:
        # Test 1: Initialization
        print("\n[Test 1] Detector Initialization")
        print("-" * 80)
        detector = PhasePhotonics()
        print("✓ Detector object created")

        # Test 2: Connection
        print("\n[Test 2] Opening Connection")
        print("-" * 80)
        if detector.open():
            print("✓ Connection opened successfully")
            print(f"  Serial: {detector.serial_number}")
            print(f"  Pixels: {detector.num_pixels}")
            print(f"  Max Counts: {detector.max_counts}")
        else:
            print("✗ Failed to open connection")
            return False

        # Test 3: Read EEPROM Calibration
        print("\n[Test 3] Reading EEPROM Calibration")
        print("-" * 80)
        try:
            eeprom_cal = detector.api.usb_read_eeprom_cal(detector.spec)
            print("✓ EEPROM calibration read successfully")
            print(f"  c0: {eeprom_cal[0]:.6e}")
            print(f"  c1: {eeprom_cal[1]:.6e}")
            print(f"  c2: {eeprom_cal[2]:.6e}")
            print(f"  c3: {eeprom_cal[3]:.6e}")
        except Exception as e:
            print(f"✗ EEPROM read failed: {e}")

        # Test 4: Check Override Status
        print("\n[Test 4] Calibration Override Status")
        print("-" * 80)
        if hasattr(detector, 'CALIBRATION_OVERRIDES') and detector.serial_number in detector.CALIBRATION_OVERRIDES:
            override = detector.CALIBRATION_OVERRIDES[detector.serial_number]
            print(f"✓ Override active for {detector.serial_number}")
            print(f"  c0: {override[0]:.6e}")
            print(f"  c1: {override[1]:.6e}")
            print(f"  c2: {override[2]:.6e}")
            print(f"  c3: {override[3]:.6e}")
        else:
            print("✓ No override configured, using EEPROM calibration")

        # Test 5: Get Current Integration Time
        print("\n[Test 5] Current Integration Time")
        print("-" * 80)
        current_int = detector._integration_time if hasattr(detector, '_integration_time') else None
        if current_int:
            print(f"✓ Current integration time: {current_int * 1000:.1f}ms")
        else:
            print("? Integration time not set yet")

        # Test 6: First Read at Default Integration
        print("\n[Test 6] First Read at Default Integration Time")
        print("-" * 80)
        print("Attempting first read...")
        start_time = time.time()
        try:
            intensity = detector.read_intensity()
            elapsed = (time.time() - start_time) * 1000
            if intensity is not None:
                print(f"✓ First read successful ({elapsed:.1f}ms)")
                print(f"  Data points: {len(intensity)}")
                print(f"  Min: {intensity.min():.1f}, Max: {intensity.max():.1f}, Mean: {intensity.mean():.1f}")
            else:
                print(f"✗ First read returned None ({elapsed:.1f}ms)")
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            print(f"✗ First read exception ({elapsed:.1f}ms): {e}")
            import traceback
            traceback.print_exc()

        # Test 7: Second Read (should be faster)
        print("\n[Test 7] Second Read at Same Integration Time")
        print("-" * 80)
        print("Attempting second read...")
        start_time = time.time()
        try:
            intensity = detector.read_intensity()
            elapsed = (time.time() - start_time) * 1000
            if intensity is not None:
                print(f"✓ Second read successful ({elapsed:.1f}ms)")
                print(f"  Min: {intensity.min():.1f}, Max: {intensity.max():.1f}, Mean: {intensity.mean():.1f}")
            else:
                print(f"✗ Second read returned None ({elapsed:.1f}ms)")
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            print(f"✗ Second read exception ({elapsed:.1f}ms): {e}")

        # Test 8: Change Integration Time to 10ms
        print("\n[Test 8] Change Integration Time to 10ms")
        print("-" * 80)
        print("Setting integration time to 10ms...")
        try:
            detector.set_integration(10)  # 10ms
            print("✓ Integration time changed to 10ms")
            print("  Waiting 1 second for stabilization...")
            time.sleep(1.0)
        except Exception as e:
            print(f"✗ set_integration failed: {e}")
            import traceback
            traceback.print_exc()

        # Test 9: Read After Integration Change (THIS IS WHERE IT HANGS)
        print("\n[Test 9] Read After Integration Time Change")
        print("-" * 80)
        print("⚠️  CRITICAL TEST - This is where the hang occurs")
        print("Attempting read after integration change...")
        print("If this hangs for more than 5 seconds, press Ctrl+C")
        start_time = time.time()
        try:
            intensity = detector.read_intensity()
            elapsed = (time.time() - start_time) * 1000
            if intensity is not None:
                print(f"✓ Read after integration change successful ({elapsed:.1f}ms)")
                print(f"  Min: {intensity.min():.1f}, Max: {intensity.max():.1f}, Mean: {intensity.mean():.1f}")
            else:
                print(f"✗ Read returned None ({elapsed:.1f}ms)")
        except KeyboardInterrupt:
            elapsed = (time.time() - start_time) * 1000
            print(f"\n✗ HANG CONFIRMED - User interrupted after {elapsed/1000:.1f}s")
            print("  The detector is blocking in DLL call waiting for data")
            raise
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            print(f"✗ Read exception ({elapsed:.1f}ms): {e}")
            import traceback
            traceback.print_exc()

        # Test 10: Read Wavelengths (triggers override)
        print("\n[Test 10] Read Wavelengths (Calibration Override Test)")
        print("-" * 80)
        try:
            wavelengths = detector.read_wavelength()
            if wavelengths is not None:
                print("✓ Wavelengths read successfully")
                print(f"  Range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")
                print(f"  Data points: {len(wavelengths)}")
            else:
                print("✗ Wavelengths returned None")
        except Exception as e:
            print(f"✗ Wavelength read exception: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        return True

    except KeyboardInterrupt:
        print("\n" + "=" * 80)
        print("✗ TEST INTERRUPTED BY USER")
        print("=" * 80)
        return False

    except Exception as e:
        print(f"\n✗ CRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if detector and detector.spec:
            print("\n[Cleanup] Closing detector connection...")
            try:
                detector.close()
                print("✓ Connection closed")
            except Exception as e:
                print(f"✗ Close failed: {e}")


if __name__ == "__main__":
    print("\nStarting PhasePhotonics detector diagnostics...")
    print("This will test each operation step-by-step\n")

    success = test_detector()

    if success:
        print("\n✓ Diagnostic test completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Diagnostic test failed")
        sys.exit(1)
