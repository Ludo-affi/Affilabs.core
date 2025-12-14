"""
Validate LED prediction model with empirical measurements
Uses intensity predictions from 3-stage model and measures actual counts
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000

def load_prediction_model():
    """Load the most recent prediction model."""
    data_dir = Path(__file__).parent / "spr_calibration" / "data"
    
    # Find most recent prediction model file
    model_files = sorted(data_dir.glob("led_prediction_model_*.json"), reverse=True)
    
    if not model_files:
        raise FileNotFoundError("No prediction model found! Run led_prediction_model.py first.")
    
    with open(model_files[0], 'r') as f:
        data = json.load(f)
    
    print(f"Loaded model from: {model_files[0].name}\n")
    return data

def measure_led(controller, spectrometer, led_char, intensity, integration_time_ms, dark_counts):
    """Measure single LED at given intensity."""
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)
    
    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.2)
    
    # Enable channels and turn on specific LED
    controller._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)
    intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    intensities[led_char] = intensity
    controller.set_batch_intensities(**intensities)
    time.sleep(0.5)
    
    # Measure (average of 3 scans, then average top 10 pixels)
    spectrum = spectrometer.intensities(num_scans=3)
    import numpy as np
    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts
    saturated = int((spectrum >= 65535).sum())
    
    return corrected, saturated

def measure_all_leds(controller, spectrometer, intensity, integration_time_ms, dark_counts):
    """Measure all 4 LEDs at same intensity."""
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)
    
    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.2)
    
    # Enable all channels and set intensities
    controller._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)
    controller.set_batch_intensities(a=intensity, b=intensity, c=intensity, d=intensity)
    time.sleep(0.5)
    
    # Measure (average of 3 scans, then average top 10 pixels)
    spectrum = spectrometer.intensities(num_scans=3)
    import numpy as np
    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts
    saturated = int((spectrum >= 65535).sum())
    
    return corrected, saturated

def main():
    print("=" * 80)
    print("LED PREDICTION MODEL VALIDATION")
    print("=" * 80)
    print("\nValidating intensity predictions from 3-stage model\n")
    
    # Load prediction model
    model = load_prediction_model()
    predictions = model['target_60k_intensities']
    
    # Connect hardware
    controller = PicoP4SPR()
    spectrometer = USB4000()
    
    if not controller.open():
        print("❌ Failed to connect to controller")
        return
    
    if not spectrometer.open():
        print("❌ Failed to connect to spectrometer")
        controller.close()
        return
    
    print("✓ Hardware connected\n")
    
    target_counts = 60000
    
    # Test integration times
    test_times = [20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    print("=" * 80)
    print("PREDICTED INTENSITIES (from 3-stage model)")
    print("=" * 80)
    print(f"\n{'Time(ms)':>10} {'All 4':>10} {'LED A':>10} {'LED B':>10} {'LED C':>10} {'LED D':>10}")
    print("-" * 80)
    
    for time_ms in test_times:
        pred = predictions[str(time_ms)]
        print(f"{time_ms:>10} {pred['all_4']:>10.1f} {pred['LED_A']:>10.1f} "
              f"{pred['LED_B']:>10.1f} {pred['LED_C']:>10.1f} {pred['LED_D']:>10.1f}")
    
    # Measure dark current at each time
    print("\n" + "=" * 80)
    print("MEASURING DARK CURRENT")
    print("=" * 80)
    
    dark_counts = {}
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    
    for time_ms in test_times:
        spectrometer.set_integration(float(time_ms))
        time.sleep(0.5)
        spectrum = spectrometer.intensities(num_scans=3)
        import numpy as np
        top_10_indices = np.argpartition(spectrum, -10)[-10:]
        dark = float(spectrum[top_10_indices].mean())
        dark_counts[time_ms] = dark
        print(f"  {time_ms}ms: {dark:.0f} counts")
    
    # Test each integration time with individual LEDs
    print("\n" + "=" * 80)
    print("INDIVIDUAL LED VALIDATION")
    print("=" * 80)
    
    individual_results = []
    
    for time_ms in test_times:
        print(f"\n{time_ms}ms integration:")
        pred = predictions[str(time_ms)]
        dark = dark_counts[time_ms]
        
        for led_name, led_char in [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd')]:
            predicted_intensity = pred[f'LED_{led_name}']
            
            # Skip if predicted intensity is maxed out (can't measure accurately)
            if predicted_intensity >= 255:
                print(f"  LED {led_name}: I=255 (maxed) - SKIP")
                continue
            
            intensity = int(round(predicted_intensity))
            measured, saturated = measure_led(controller, spectrometer, led_char, intensity, time_ms, dark)
            
            error = measured - target_counts
            error_pct = (error / target_counts) * 100
            
            status = "✓" if abs(error_pct) <= 5 else "~" if abs(error_pct) <= 10 else "✗"
            sat_warn = f" ⚠SAT:{saturated}" if saturated > 0 else ""
            
            print(f"  LED {led_name}: I={intensity:>3} → {measured:>8.0f} counts "
                  f"(err: {error:>+6.0f}, {error_pct:>+5.1f}%) {status}{sat_warn}")
            
            individual_results.append({
                'time_ms': time_ms,
                'led': led_name,
                'predicted_intensity': predicted_intensity,
                'actual_intensity': intensity,
                'measured_counts': measured,
                'target_counts': target_counts,
                'error': error,
                'error_pct': error_pct,
                'saturated': saturated
            })
    
    # Test "All 4 LEDs together"
    print("\n" + "=" * 80)
    print("ALL 4 LEDs TOGETHER VALIDATION")
    print("=" * 80)
    print(f"\n{'Time(ms)':>10} {'Pred I':>10} {'Measured':>12} {'Target':>12} {'Error':>12} {'Err%':>8} {'Sat':>6}")
    print("-" * 80)
    
    combined_results = []
    
    for time_ms in test_times:
        pred = predictions[str(time_ms)]
        dark = dark_counts[time_ms]
        
        predicted_intensity = pred['all_4']
        intensity = int(round(predicted_intensity))
        
        measured, saturated = measure_all_leds(controller, spectrometer, intensity, time_ms, dark)
        
        error = measured - target_counts
        error_pct = (error / target_counts) * 100
        
        status = "✓" if abs(error_pct) <= 5 else "~" if abs(error_pct) <= 10 else "✗"
        sat_warn = " ⚠ SAT" if saturated > 0 else ""
        
        print(f"{time_ms:>10} {intensity:>10} {measured:>12.0f} {target_counts:>12.0f} "
              f"{error:>12.0f} {error_pct:>8.1f}% {saturated:>6} {status}{sat_warn}")
        
        combined_results.append({
            'time_ms': time_ms,
            'predicted_intensity': predicted_intensity,
            'actual_intensity': intensity,
            'measured_counts': measured,
            'target_counts': target_counts,
            'error': error,
            'error_pct': error_pct,
            'saturated': saturated
        })
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    # Individual LEDs statistics
    individual_valid = [r for r in individual_results if r['saturated'] == 0]
    
    if individual_valid:
        print(f"\nIndividual LEDs ({len(individual_valid)} unsaturated measurements):")
        errors = [abs(r['error_pct']) for r in individual_valid]
        mean_error = sum(errors) / len(errors)
        max_error = max(errors)
        within_5pct = sum(1 for e in errors if e <= 5)
        within_10pct = sum(1 for e in errors if e <= 10)
        
        print(f"  Mean absolute error: {mean_error:.1f}%")
        print(f"  Max absolute error:  {max_error:.1f}%")
        print(f"  Within ±5%:  {within_5pct}/{len(individual_valid)} ({within_5pct/len(individual_valid)*100:.0f}%)")
        print(f"  Within ±10%: {within_10pct}/{len(individual_valid)} ({within_10pct/len(individual_valid)*100:.0f}%)")
    
    # All 4 LEDs statistics
    combined_valid = [r for r in combined_results if r['saturated'] == 0]
    
    if combined_valid:
        print(f"\nAll 4 LEDs Together ({len(combined_valid)} unsaturated measurements):")
        errors = [abs(r['error_pct']) for r in combined_valid]
        mean_error = sum(errors) / len(errors)
        max_error = max(errors)
        within_5pct = sum(1 for e in errors if e <= 5)
        within_10pct = sum(1 for e in errors if e <= 10)
        
        print(f"  Mean absolute error: {mean_error:.1f}%")
        print(f"  Max absolute error:  {max_error:.1f}%")
        print(f"  Within ±5%:  {within_5pct}/{len(combined_valid)} ({within_5pct/len(combined_valid)*100:.0f}%)")
        print(f"  Within ±10%: {within_10pct}/{len(combined_valid)} ({within_10pct/len(combined_valid)*100:.0f}%)")
    
    print("\n" + "=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)
    
    if individual_valid:
        ind_mean = sum(abs(r['error_pct']) for r in individual_valid) / len(individual_valid)
        if ind_mean <= 5:
            print("\n✓ Individual LED predictions: EXCELLENT (≤5% error)")
        elif ind_mean <= 10:
            print("\n~ Individual LED predictions: GOOD (≤10% error)")
        else:
            print("\n✗ Individual LED predictions: NEEDS IMPROVEMENT (>10% error)")
    
    if combined_valid:
        comb_mean = sum(abs(r['error_pct']) for r in combined_valid) / len(combined_valid)
        if comb_mean <= 5:
            print("✓ All 4 LEDs predictions: EXCELLENT (≤5% error)")
        elif comb_mean <= 10:
            print("~ All 4 LEDs predictions: GOOD (≤10% error)")
        else:
            print("✗ All 4 LEDs predictions: NEEDS IMPROVEMENT (>10% error)")
            print("  → Optical interference effects require empirical correction")
    
    # Save results
    output_file = f"led_model_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = Path(__file__).parent / "spr_calibration" / "data" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'target_counts': target_counts,
            'dark_counts': dark_counts,
            'individual_results': individual_results,
            'combined_results': combined_results,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_path}")
    
    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    controller.close()
    spectrometer.close()
    print("\n✓ Hardware closed")

if __name__ == "__main__":
    main()
