"""Test saturation analysis in model loader."""

import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

from affilabs.services.led_model_loader import LEDCalibrationModelLoader

print("Testing model loader...")
loader = LEDCalibrationModelLoader()

print("\nLoading model...")
model = loader.load_model('FLMT09792')

print("\nChecking if quality_metrics present...")
print(f"  'quality_metrics' in model_data: {'quality_metrics' in loader.model_data}")

if 'quality_metrics' in loader.model_data:
    print("\nQuality Metrics found:")
    for led_name in ['A', 'B', 'C', 'D']:
        if led_name not in loader.model_data['quality_metrics']:
            continue
        print(f"\n  {led_name}:")
        for time_label, metrics in loader.model_data['quality_metrics'][led_name].items():
            print(f"    {time_label}: {metrics['status']} (linearity={metrics['linearity']:.3f})")

print("\n✓ Test complete")
