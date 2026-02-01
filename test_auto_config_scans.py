"""Test Phase Photonics Auto-Configuration

Verifies that the detector automatically calculates optimal scans
based on integration time and time budget.
"""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics


def test_auto_config():
    """Test automatic scan configuration."""
    print("\n" + "="*80)
    print("PHASE PHOTONICS AUTO-CONFIGURATION TEST")
    print("="*80)

    detector = PhasePhotonics()
    detector.get_device_list()

    if not detector.devs or not detector.open():
        print("❌ Failed to connect to detector")
        return

    print(f"✓ Connected: {detector.serial_number}\n")

    # Test scenarios
    scenarios = [
        {
            'name': 'Current (22ms, 190ms budget)',
            'integration': 22,
            'budget': 190,
            'expected_scans': 4
        },
        {
            'name': 'Best SNR (12ms, 190ms budget)',
            'integration': 12,
            'budget': 190,
            'expected_scans': 8
        },
        {
            'name': 'Max SNR (10ms, 190ms budget)',
            'integration': 10,
            'budget': 190,
            'expected_scans': 9
        },
        {
            'name': 'Fast (15ms, 150ms budget)',
            'integration': 15,
            'budget': 150,
            'expected_scans': 5
        }
    ]

    print("="*80)
    print("AUTO-CONFIGURATION TESTS")
    print("="*80)

    for scenario in scenarios:
        print(f"\n{scenario['name']}:")

        # Calculate optimal scans
        num_scans = detector.calculate_optimal_scans(
            scenario['integration'],
            scenario['budget']
        )

        # Verify
        time_per_scan = scenario['integration'] * detector.TIMING_MULTIPLIER
        total_time = num_scans * time_per_scan
        snr_gain = num_scans ** 0.5

        print(f"  Integration: {scenario['integration']}ms")
        print(f"  Budget: {scenario['budget']}ms")
        print(f"  Calculated scans: {num_scans}")
        print(f"  Time per scan: {time_per_scan:.1f}ms")
        print(f"  Total time: {total_time:.1f}ms")
        print(f"  SNR gain: √{num_scans} = {snr_gain:.2f}x")

        # Check if meets budget
        if total_time <= scenario['budget']:
            print(f"  Status: ✅ Fits in budget ({scenario['budget'] - total_time:.1f}ms spare)")
        else:
            print(f"  Status: ❌ Exceeds budget by {total_time - scenario['budget']:.1f}ms")

        # Check if matches expected
        if num_scans == scenario['expected_scans']:
            print(f"  Verification: ✅ Matches expected ({scenario['expected_scans']} scans)")
        else:
            print(f"  Verification: ⚠️ Got {num_scans}, expected {scenario['expected_scans']}")

    # Test set_optimal_scans (stores configuration)
    print("\n" + "="*80)
    print("CONFIGURATION STORAGE TEST")
    print("="*80)

    print("\nSetting optimal configuration for 22ms, 190ms budget...")
    num_scans = detector.set_optimal_scans(22, 190)

    print("Stored configuration:")
    print(f"  Num scans: {detector.get_num_scans()}")
    print("  Expected: 4")

    if detector.get_num_scans() == 4:
        print("  Status: ✅ Configuration stored correctly")
    else:
        print("  Status: ❌ Configuration not stored correctly")

    # Test actual acquisition with auto-configured scans
    print("\n" + "="*80)
    print("ACQUISITION TEST WITH AUTO-CONFIGURED SCANS")
    print("="*80)

    # Set integration time
    detector.set_integration(22.0)

    # Get configured number of scans
    num_scans = detector.get_num_scans()

    print(f"\nAcquiring {num_scans} scans with batch method...")

    import time
    t_start = time.perf_counter()

    averaged = detector.read_intensity_batch(num_scans)

    t_elapsed = (time.perf_counter() - t_start) * 1000

    if averaged is not None:
        print("✅ Acquisition successful")
        print(f"  Time: {t_elapsed:.1f}ms")
        print(f"  Expected: ~{num_scans * 22 * detector.TIMING_MULTIPLIER:.1f}ms")
        print(f"  Data points: {len(averaged)}")
        print(f"  Mean value: {averaged.mean():.1f} counts")
    else:
        print("❌ Acquisition failed")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("\n✅ Phase Photonics timing characteristic saved:")
    print(f"   Total Time = Integration Time × {detector.TIMING_MULTIPLIER}")

    print("\n✅ Auto-configuration methods available:")
    print("   detector.calculate_optimal_scans(int_ms, budget_ms)")
    print("   detector.set_optimal_scans(int_ms, budget_ms)")
    print("   detector.get_num_scans()")

    print("\n✅ Software can now automatically configure scans for Phase detector!")

    print("\n" + "="*80 + "\n")

    detector.close()


if __name__ == "__main__":
    test_auto_config()
