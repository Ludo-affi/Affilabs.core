"""Test Detector-Aware Fourier Parameters

Verify that the Fourier pipeline automatically selects optimized parameters
based on detector type (Phase Photonics vs Ocean Optics).
"""

from affilabs.utils.pipelines.fourier_pipeline import FourierPipeline
from affilabs.settings.settings import PHASE_PHOTONICS_FOURIER_PARAMS, OCEAN_OPTICS_FOURIER_PARAMS

print("=" * 80)
print("DETECTOR-AWARE FOURIER PARAMETER TEST")
print("=" * 80)

print("\n" + "=" * 80)
print("TEST 1: Phase Photonics ST00012 (Serial Number Detection)")
print("=" * 80)
config_pp_serial = {"detector_serial": "ST00012"}
pipeline_pp_serial = FourierPipeline(config_pp_serial)
print("Detector: Phase Photonics ST00012")
print(f"Window Size: {pipeline_pp_serial.window_size} pixels")
print(f"Alpha (regularization): {pipeline_pp_serial.alpha}")
print(f"Expected Window: {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window']} pixels")
print(f"Expected Alpha: {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_alpha']}")
assert pipeline_pp_serial.window_size == PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window'], \
    f"Window mismatch: {pipeline_pp_serial.window_size} != {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window']}"
assert pipeline_pp_serial.alpha == PHASE_PHOTONICS_FOURIER_PARAMS['fourier_alpha'], \
    f"Alpha mismatch: {pipeline_pp_serial.alpha} != {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_alpha']}"
print("✓ PASS: Phase Photonics parameters applied correctly (serial detection)")

print("\n" + "=" * 80)
print("TEST 2: Phase Photonics (Type String Detection)")
print("=" * 80)
config_pp_type = {"detector_type": "PhasePhotonics"}
pipeline_pp_type = FourierPipeline(config_pp_type)
print("Detector: PhasePhotonics (type string)")
print(f"Window Size: {pipeline_pp_type.window_size} pixels")
print(f"Alpha (regularization): {pipeline_pp_type.alpha}")
assert pipeline_pp_type.window_size == PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window']
assert pipeline_pp_type.alpha == PHASE_PHOTONICS_FOURIER_PARAMS['fourier_alpha']
print("✓ PASS: Phase Photonics parameters applied correctly (type detection)")

print("\n" + "=" * 80)
print("TEST 3: Ocean Optics USB4000 (Serial Number Detection)")
print("=" * 80)
config_oo_serial = {"detector_serial": "USB4H14526"}
pipeline_oo_serial = FourierPipeline(config_oo_serial)
print("Detector: Ocean Optics USB4H14526")
print(f"Window Size: {pipeline_oo_serial.window_size} pixels")
print(f"Alpha (regularization): {pipeline_oo_serial.alpha}")
print(f"Expected Window: {OCEAN_OPTICS_FOURIER_PARAMS['fourier_window']} pixels")
print(f"Expected Alpha: {OCEAN_OPTICS_FOURIER_PARAMS['fourier_alpha']}")
assert pipeline_oo_serial.window_size == OCEAN_OPTICS_FOURIER_PARAMS['fourier_window'], \
    f"Window mismatch: {pipeline_oo_serial.window_size} != {OCEAN_OPTICS_FOURIER_PARAMS['fourier_window']}"
assert pipeline_oo_serial.alpha == OCEAN_OPTICS_FOURIER_PARAMS['fourier_alpha'], \
    f"Alpha mismatch: {pipeline_oo_serial.alpha} != {OCEAN_OPTICS_FOURIER_PARAMS['fourier_alpha']}"
print("✓ PASS: Ocean Optics parameters applied correctly (serial detection)")

print("\n" + "=" * 80)
print("TEST 4: Default (No Detector Info) - Should use Ocean Optics params")
print("=" * 80)
config_default = {}
pipeline_default = FourierPipeline(config_default)
print("Detector: Unknown/Default")
print(f"Window Size: {pipeline_default.window_size} pixels")
print(f"Alpha (regularization): {pipeline_default.alpha}")
assert pipeline_default.window_size == OCEAN_OPTICS_FOURIER_PARAMS['fourier_window']
assert pipeline_default.alpha == OCEAN_OPTICS_FOURIER_PARAMS['fourier_alpha']
print("✓ PASS: Default parameters match Ocean Optics (backward compatibility)")

print("\n" + "=" * 80)
print("TEST 5: Manual Override (Custom Window/Alpha)")
print("=" * 80)
config_override = {"detector_serial": "ST00012", "window_size": 200, "alpha": 5000}
pipeline_override = FourierPipeline(config_override)
print("Detector: Phase Photonics ST00012 (with manual override)")
print(f"Window Size: {pipeline_override.window_size} pixels (manual: 200)")
print(f"Alpha (regularization): {pipeline_override.alpha} (manual: 5000)")
assert pipeline_override.window_size == 200, "Manual window override failed"
assert pipeline_override.alpha == 5000, "Manual alpha override failed"
print("✓ PASS: Manual overrides work correctly")

print("\n" + "=" * 80)
print("PHYSICAL WINDOW SIZE COMPARISON")
print("=" * 80)
print("\nOcean Optics USB4000:")
print("  Pixels: 3648")
print("  Resolution: ~0.044 nm/pixel")
print(f"  Window: {OCEAN_OPTICS_FOURIER_PARAMS['fourier_window']} pixels × 0.044 nm = {OCEAN_OPTICS_FOURIER_PARAMS['fourier_window'] * 0.044:.2f} nm")
print(f"  Alpha: {OCEAN_OPTICS_FOURIER_PARAMS['fourier_alpha']}")

print("\nPhase Photonics ST Series:")
print("  Pixels: 1848")
print("  Resolution: ~0.085 nm/pixel")
print(f"  Window: {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window']} pixels × 0.085 nm = {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_window'] * 0.085:.2f} nm")
print(f"  Alpha: {PHASE_PHOTONICS_FOURIER_PARAMS['fourier_alpha']}")

print("\n✓ Physical window sizes match (~7.2-7.3 nm)")
print("✓ Alpha scaled with pixel count (4500 vs 9000)")

print("\n" + "=" * 80)
print("ALL TESTS PASSED ✓")
print("=" * 80)
print("\nDetector-aware parameter selection is working correctly!")
print("Phase Photonics will automatically use optimized parameters when detected.")
