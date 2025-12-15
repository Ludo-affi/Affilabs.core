"""Test script to verify baseline correction is working"""

import sys

import numpy as np

sys.path.insert(0, "src")

# Import settings to check current values
from settings import TRANSMISSION_BASELINE_CORRECTION, TRANSMISSION_BASELINE_DEGREE

print("=" * 80)
print("BASELINE CORRECTION TEST")
print("=" * 80)
print(f"TRANSMISSION_BASELINE_CORRECTION = {TRANSMISSION_BASELINE_CORRECTION}")
print(f"TRANSMISSION_BASELINE_DEGREE = {TRANSMISSION_BASELINE_DEGREE}")
print()

# Initialize pipeline (this triggers initialization by importing)
from utils.processing_pipeline import get_pipeline_registry

registry = get_pipeline_registry()
print(f"Active pipeline: {registry.active_pipeline_id}")

pipeline = registry.get_active_pipeline()
print(f"Pipeline type: {type(pipeline).__name__}")
print(f"Pipeline config: {pipeline.config}")
print(f"Baseline correction enabled in pipeline: {pipeline.baseline_correction}")
print(f"Baseline degree in pipeline: {pipeline.baseline_degree}")
print()

# Create test data with spectral tilt
print("Testing transmission calculation with tilted spectrum...")
wavelengths = np.linspace(560, 720, 160)  # Simplified for test

# Create S-ref and P-ref with spectral tilt (higher at low wavelength, lower at high)
s_ref = 50000 - (wavelengths - 560) * 200  # Decreasing from 50k to 18k
p_ref = 30000 - (wavelengths - 560) * 120  # Decreasing proportionally

print(f"S-ref range: {s_ref.min():.0f} - {s_ref.max():.0f} counts")
print(f"P-ref range: {p_ref.min():.0f} - {p_ref.max():.0f} counts")
print()

# Calculate transmission using pipeline
transmission = pipeline.calculate_transmission(p_ref, s_ref)

print(f"Transmission range: {transmission.min():.1f}% - {transmission.max():.1f}%")
print(f"Transmission mean: {transmission.mean():.1f}%")
print(f"Transmission std: {transmission.std():.1f}%")
print()

# Check if transmission is flatter when correction is enabled
# Raw P/S ratio would show tilt, corrected should be flatter
raw_transmission = (p_ref / s_ref) * 100
print(
    f"Raw transmission range: {raw_transmission.min():.1f}% - {raw_transmission.max():.1f}%",
)
print(f"Raw transmission std: {raw_transmission.std():.1f}%")
print()

if TRANSMISSION_BASELINE_CORRECTION:
    print("✅ Baseline correction IS enabled")
    if transmission.std() < raw_transmission.std() * 0.8:
        print("✅ Correction appears to be working (std reduced)")
    else:
        print("⚠️ Correction may not be working as expected")
else:
    print("❌ Baseline correction is NOT enabled (set to False in settings)")
    print("   To enable: Set TRANSMISSION_BASELINE_CORRECTION = True in settings.py")

print()
print("=" * 80)
