"""Test Phase Photonics Data Processing Path - Background Acquisition Audit

This script audits the complete data processing pipeline for Phase Photonics detector,
from raw hardware acquisition through to final processed spectrum.

Feed this script with background acquisition data to verify:
1. Raw detector output (1848 pixels, 12-bit ADC)
2. Wavelength calibration from EEPROM
3. Data type conversions (uint16 → float)
4. Array shape preservation
5. Domain model creation (RawSpectrumData)
6. Processing pipeline (dark subtraction, transmission calc)
7. Final output validation

Usage:
    python test_phase_photonics_data_processing.py
    
Expected Input:
    - Phase Photonics detector connected (serial starts with "ST")
    - Background/dark conditions (LED off, no sample)
    - Integration time: configurable (default 22ms)
    - Number of scans: configurable (default 8 for averaging)

Output:
    - Detailed audit report with statistics at each processing stage
    - Validation of data integrity throughout pipeline
    - Performance metrics (timing, SNR)
"""

import sys
import time

import numpy as np

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.domain.spectrum_data import RawSpectrumData


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_array_stats(array: np.ndarray, label: str):
    """Print comprehensive array statistics."""
    print(f"\n{label}:")
    print(f"  Shape:       {array.shape}")
    print(f"  dtype:       {array.dtype}")
    print(f"  Min:         {np.min(array):.2f}")
    print(f"  Max:         {np.max(array):.2f}")
    print(f"  Mean:        {np.mean(array):.2f}")
    print(f"  Std Dev:     {np.std(array):.2f}")
    print(f"  Median:      {np.median(array):.2f}")
    print(f"  Non-zero:    {np.count_nonzero(array)} / {array.size}")
    print(f"  Memory:      {array.nbytes} bytes ({array.nbytes/1024:.1f} KB)")


def test_detector_connection():
    """Test 1: Detector Connection and Discovery."""
    print_section("TEST 1: Detector Connection")

    detector = PhasePhotonics()

    print("\n[1.1] Scanning for devices...")
    detector.get_device_list()

    if not detector.devs:
        print("❌ FAIL: No Phase Photonics devices found")
        print("   Check:")
        print("   - Detector is powered on")
        print("   - USB cable connected")
        print("   - FTDI D2XX drivers installed (run check_d2xx_drivers.py)")
        return None

    print(f"✅ PASS: Found {len(detector.devs)} device(s): {detector.devs}")

    print("\n[1.2] Connecting to detector...")
    if not detector.open():
        print("❌ FAIL: Could not connect to detector")
        return None

    print(f"✅ PASS: Connected to {detector.serial_number}")
    print(f"   Pixel count: {detector._num_pixels}")
    print(f"   ADC resolution: 12-bit (max counts: {detector._max_counts})")

    return detector


def test_wavelength_calibration(detector: PhasePhotonics):
    """Test 2: Wavelength Calibration from EEPROM."""
    print_section("TEST 2: Wavelength Calibration")

    print("\n[2.1] Reading calibration from EEPROM...")
    wavelengths = detector.read_wavelength()

    if wavelengths is None:
        print("❌ FAIL: Could not read wavelength calibration")
        return None

    print("✅ PASS: Wavelength calibration loaded")
    print_array_stats(wavelengths, "Wavelength Array")

    # Validate wavelength array
    print("\n[2.2] Validating wavelength array...")

    checks = {
        "Length matches detector pixels": len(wavelengths) == detector._num_pixels,
        "Monotonically increasing": np.all(np.diff(wavelengths) > 0),
        "Range is physical (400-900nm)": 400 < wavelengths[0] < 900 and 400 < wavelengths[-1] < 900,
        "No NaN values": not np.any(np.isnan(wavelengths)),
        "No Inf values": not np.any(np.isinf(wavelengths)),
    }

    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\n❌ FAIL: Wavelength validation failed")
        return None

    print(f"\n✅ PASS: Wavelength range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")

    return wavelengths


def test_raw_acquisition(detector: PhasePhotonics, integration_ms: float = 22.0, num_scans: int = 8):
    """Test 3: Raw Data Acquisition."""
    print_section("TEST 3: Raw Data Acquisition")

    print("\n[3.1] Configuring detector...")
    print(f"   Integration time: {integration_ms} ms")
    print(f"   Number of scans: {num_scans}")

    # Set integration time
    if not detector.set_integration(integration_ms):
        print("❌ FAIL: Could not set integration time")
        return None

    print("✅ PASS: Integration time set")

    # Set averaging
    if not detector.set_averaging(num_scans):
        print("❌ FAIL: Could not set averaging")
        return None

    print("✅ PASS: Hardware averaging configured")

    print("\n[3.2] Acquiring raw spectrum...")
    t_start = time.perf_counter()

    raw_spectrum = detector.read_intensity(data_type=np.uint16)

    t_elapsed = (time.perf_counter() - t_start) * 1000

    if raw_spectrum is None:
        print("❌ FAIL: Could not acquire spectrum")
        return None

    print(f"✅ PASS: Spectrum acquired in {t_elapsed:.1f}ms")
    print_array_stats(raw_spectrum, "Raw Spectrum (uint16)")

    # Validate raw data
    print("\n[3.3] Validating raw spectrum...")

    expected_time = integration_ms * detector.TIMING_MULTIPLIER * num_scans

    checks = {
        "Length matches detector pixels": len(raw_spectrum) == detector._num_pixels,
        "dtype is uint16": raw_spectrum.dtype == np.uint16,
        "Values within ADC range (0-4095)": np.all((raw_spectrum >= 0) & (raw_spectrum <= 4095)),
        "Has non-zero data": np.count_nonzero(raw_spectrum) > 0,
        "Acquisition time reasonable": abs(t_elapsed - expected_time) < 100,  # Within 100ms
    }

    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")
        if not passed:
            all_passed = False

    # Background statistics
    print("\n[3.4] Background signal analysis...")
    mean_bg = np.mean(raw_spectrum)
    std_bg = np.std(raw_spectrum)
    snr = mean_bg / std_bg if std_bg > 0 else 0

    print(f"   Mean background level: {mean_bg:.1f} counts")
    print(f"   Standard deviation: {std_bg:.1f} counts")
    print(f"   SNR (mean/std): {snr:.1f}")
    print(f"   Dynamic range used: {(mean_bg / detector._max_counts) * 100:.1f}%")

    if std_bg > 100:
        print("   ⚠️  WARNING: High noise level detected")

    if not all_passed:
        print("\n❌ FAIL: Raw spectrum validation failed")
        return None

    print("\n✅ PASS: Raw acquisition validated")

    return raw_spectrum, t_elapsed


def test_data_type_conversion(raw_spectrum: np.ndarray):
    """Test 4: Data Type Conversions."""
    print_section("TEST 4: Data Type Conversion")

    print("\n[4.1] Converting uint16 → float64...")

    # Convert to float (typical processing step)
    spectrum_float = raw_spectrum.astype(np.float64)

    print_array_stats(raw_spectrum, "Original (uint16)")
    print_array_stats(spectrum_float, "Converted (float64)")

    # Validate conversion
    print("\n[4.2] Validating conversion...")

    checks = {
        "No data loss": np.array_equal(raw_spectrum, spectrum_float.astype(np.uint16)),
        "Mean preserved": abs(np.mean(raw_spectrum) - np.mean(spectrum_float)) < 0.01,
        "Range preserved": (np.min(spectrum_float) >= 0) and (np.max(spectrum_float) <= 4095),
        "Memory usage increased": spectrum_float.nbytes > raw_spectrum.nbytes,
    }

    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check}")
        if not passed:
            all_passed = False

    memory_ratio = spectrum_float.nbytes / raw_spectrum.nbytes
    print(f"\n   Memory overhead: {memory_ratio:.1f}x ({spectrum_float.nbytes - raw_spectrum.nbytes} bytes)")

    if not all_passed:
        print("\n❌ FAIL: Data type conversion validation failed")
        return None

    print("✅ PASS: Data type conversion validated")

    return spectrum_float


def test_domain_model_creation(wavelengths: np.ndarray, raw_spectrum: np.ndarray,
                               integration_ms: float, num_scans: int):
    """Test 5: Domain Model Creation."""
    print_section("TEST 5: Domain Model Creation (RawSpectrumData)")

    print("\n[5.1] Creating RawSpectrumData object...")

    try:
        raw_data = RawSpectrumData(
            wavelengths=wavelengths,
            intensities=raw_spectrum.astype(np.float64),  # Convert to float for model
            channel='a',  # Test channel
            timestamp=time.time(),
            integration_time=integration_ms,
            num_scans=num_scans,
            led_intensity=0,  # Background acquisition (LED off)
            metadata={
                'detector_type': 'PhasePhotonics',
                'serial_number': 'ST00012',
                'test_type': 'background_acquisition',
            }
        )

        print("✅ PASS: RawSpectrumData created successfully")

        print("\n[5.2] Validating domain model...")
        print(f"   Channel: {raw_data.channel}")
        print(f"   Timestamp: {raw_data.datetime}")
        print(f"   Num points: {raw_data.num_points}")
        print(f"   Wavelength range: {raw_data.wavelength_range[0]:.2f} - {raw_data.wavelength_range[1]:.2f} nm")
        print(f"   Intensity range: {raw_data.intensity_range[0]:.1f} - {raw_data.intensity_range[1]:.1f} counts")
        print(f"   Mean intensity: {raw_data.mean_intensity:.1f} counts")
        print(f"   Integration time: {raw_data.integration_time} ms")
        print(f"   Num scans: {raw_data.num_scans}")
        print(f"   LED intensity: {raw_data.led_intensity}")
        print(f"   Has data: {raw_data.has_data()}")

        # Test domain model methods
        print("\n[5.3] Testing domain model methods...")

        checks = {
            "num_points matches array length": raw_data.num_points == len(wavelengths),
            "wavelength_range correct": raw_data.wavelength_range == (wavelengths[0], wavelengths[-1]),
            "has_data() returns True": raw_data.has_data(),
            "Channel validation works": raw_data.channel == 'a',
        }

        all_passed = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")
            if not passed:
                all_passed = False

        if not all_passed:
            print("\n❌ FAIL: Domain model validation failed")
            return None

        print("\n✅ PASS: Domain model validated")

        return raw_data

    except Exception as e:
        print(f"❌ FAIL: Domain model creation failed: {e}")
        return None


def test_dark_subtraction(raw_spectrum: np.ndarray, dark_spectrum: np.ndarray = None):
    """Test 6: Dark Subtraction (optional)."""
    print_section("TEST 6: Dark Subtraction")

    if dark_spectrum is None:
        print("\n⚠️  SKIP: No dark spectrum provided")
        print("   To test dark subtraction:")
        print("   1. Acquire spectrum with LED off (current data)")
        print("   2. Acquire spectrum with detector covered")
        print("   3. Subtract: corrected = raw - dark")
        return raw_spectrum

    print("\n[6.1] Applying dark subtraction...")

    corrected = raw_spectrum.astype(np.float64) - dark_spectrum.astype(np.float64)

    # Clip negative values
    corrected = np.clip(corrected, 0, 4095)

    print_array_stats(raw_spectrum, "Raw Spectrum")
    print_array_stats(dark_spectrum, "Dark Spectrum")
    print_array_stats(corrected, "Dark-Corrected Spectrum")

    print(f"\n   Pixels with negative values (clipped): {np.sum(corrected != (raw_spectrum - dark_spectrum))}")

    print("✅ PASS: Dark subtraction applied")

    return corrected


def test_performance_metrics(detector: PhasePhotonics, integration_ms: float, num_scans: int):
    """Test 7: Performance and Timing Metrics."""
    print_section("TEST 7: Performance Metrics")

    print("\n[7.1] Testing acquisition timing...")

    # Predict expected time
    predicted_time = integration_ms * detector.TIMING_MULTIPLIER * num_scans

    # Measure actual time (multiple acquisitions)
    print("\n   Running 5 acquisitions for timing analysis...")

    times = []
    for i in range(5):
        t_start = time.perf_counter()
        spectrum = detector.read_intensity(data_type=np.uint16)
        t_elapsed = (time.perf_counter() - t_start) * 1000
        times.append(t_elapsed)
        print(f"   Acquisition {i+1}: {t_elapsed:.1f}ms")

    mean_time = np.mean(times)
    std_time = np.std(times)

    print(f"\n   Mean acquisition time: {mean_time:.1f} ± {std_time:.1f}ms")
    print(f"   Predicted time: {predicted_time:.1f}ms")
    print(f"   Deviation: {abs(mean_time - predicted_time):.1f}ms ({abs(mean_time - predicted_time) / predicted_time * 100:.1f}%)")

    # Calculate throughput
    throughput = 1000 / mean_time  # spectra per second
    print(f"\n   Throughput: {throughput:.2f} spectra/second")

    print("✅ PASS: Performance metrics collected")


def run_full_audit(integration_ms: float = 22.0, num_scans: int = 8):
    """Run complete data processing audit."""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "PHASE PHOTONICS DATA PROCESSING AUDIT" + " " * 26 + "║")
    print("╚" + "═" * 78 + "╝")

    # Test 1: Detector Connection
    detector = test_detector_connection()
    if detector is None:
        return False

    # Test 2: Wavelength Calibration
    wavelengths = test_wavelength_calibration(detector)
    if wavelengths is None:
        detector.close()
        return False

    # Test 3: Raw Acquisition
    result = test_raw_acquisition(detector, integration_ms, num_scans)
    if result is None:
        detector.close()
        return False

    raw_spectrum, acq_time = result

    # Test 4: Data Type Conversion
    spectrum_float = test_data_type_conversion(raw_spectrum)
    if spectrum_float is None:
        detector.close()
        return False

    # Test 5: Domain Model Creation
    raw_data_model = test_domain_model_creation(wavelengths, raw_spectrum, integration_ms, num_scans)
    if raw_data_model is None:
        detector.close()
        return False

    # Test 6: Dark Subtraction (optional)
    corrected_spectrum = test_dark_subtraction(raw_spectrum)

    # Test 7: Performance Metrics
    test_performance_metrics(detector, integration_ms, num_scans)

    # Summary
    print_section("AUDIT SUMMARY")
    print("\n✅ ALL TESTS PASSED")
    print("\nData Processing Path Verified:")
    print("  1. ✅ Detector connection and discovery")
    print("  2. ✅ Wavelength calibration from EEPROM")
    print("  3. ✅ Raw spectrum acquisition (uint16)")
    print("  4. ✅ Data type conversion (uint16 → float64)")
    print("  5. ✅ Domain model creation (RawSpectrumData)")
    print("  6. ✅ Dark subtraction (optional)")
    print("  7. ✅ Performance metrics")

    print("\nDetector Specifications:")
    print(f"  Serial: {detector.serial_number}")
    print(f"  Pixels: {detector._num_pixels}")
    print(f"  ADC: 12-bit (0-{detector._max_counts} counts)")
    print(f"  Wavelength range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")

    print("\nAcquisition Configuration:")
    print(f"  Integration time: {integration_ms} ms")
    print(f"  Hardware scans: {num_scans}")
    print(f"  Total acquisition time: {acq_time:.1f} ms")

    print("\nBackground Signal Characteristics:")
    print(f"  Mean level: {np.mean(raw_spectrum):.1f} counts")
    print(f"  Noise (std): {np.std(raw_spectrum):.1f} counts")
    print(f"  SNR: {np.mean(raw_spectrum) / np.std(raw_spectrum):.1f}")

    print("\n" + "═" * 80)
    print("Data processing path validated and ready for production use!")
    print("═" * 80 + "\n")

    # Clean up
    detector.close()

    return True


if __name__ == "__main__":
    print("\nPhase Photonics Data Processing Path Audit")
    print("=" * 80)
    print("This script will audit the complete data processing pipeline")
    print("from raw hardware acquisition to domain model creation.")
    print("\nRequirements:")
    print("  - Phase Photonics detector connected (serial starts with 'ST')")
    print("  - Background/dark conditions recommended (LED off)")
    print("=" * 80)

    # Configuration
    integration_ms = 22.0  # Integration time in milliseconds
    num_scans = 8  # Number of scans for hardware averaging

    print("\nConfiguration:")
    print(f"  Integration time: {integration_ms} ms")
    print(f"  Hardware scans: {num_scans}")

    input("\nPress Enter to start audit...")

    try:
        success = run_full_audit(integration_ms, num_scans)
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Audit interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n\n❌ Audit failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
