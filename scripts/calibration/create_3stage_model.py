"""
Create 3-Stage Linear LED Calibration Model
===========================================

Extracts LED response models from calibration results and creates a
simplified 3-stage linear model for fast LED intensity calculations.

The 3-stage model uses slopes at different integration times:
  - Stage 1: 10ms integration time
  - Stage 2: 20ms integration time  
  - Stage 3: 30ms integration time

Model equation: counts = slope_10ms × intensity × (time_ms / 10)

Usage:
    python scripts/calibration/create_3stage_model.py [--input CALIBRATION_FILE]

If no input file specified, uses calibration_results/latest_calibration.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import numpy as np

def extract_led_slopes(calibration_data: dict) -> dict:
    """Extract LED response slopes from calibration data.
    
    Args:
        calibration_data: Full calibration results dictionary
        
    Returns:
        Dictionary with led_models and dark_counts_per_time
    """
    
    # Extract LED response models
    led_models = {}
    
    if "led_response_models" in calibration_data:
        for channel, model_data in calibration_data["led_response_models"].items():
            if "model" in model_data:
                model = model_data["model"]
                slope = model.get("slope", 0)
                intercept = model.get("intercept", 0)
                
                # Calculate slopes at 10ms, 20ms, 30ms
                # Model: counts = slope * intensity + intercept
                # At 10ms baseline: slope_10ms = slope
                # At 20ms: slope_20ms = slope * 2 (assuming linear scaling)
                # At 30ms: slope_30ms = slope * 3
                
                led_models[channel.upper()] = [
                    [10.0, slope],
                    [20.0, slope * 2.0],
                    [30.0, slope * 3.0],
                    [50.0, slope * 5.0],
                    [100.0, slope * 10.0]
                ]
    
    # Extract dark counts per integration time
    dark_counts_per_time = {}
    
    if "dark_noise_data" in calibration_data:
        dark_data = calibration_data["dark_noise_data"]
        
        # Average dark counts across spectrum
        if "dark_counts" in dark_data:
            dark_counts = dark_data["dark_counts"]
            if isinstance(dark_counts, list):
                avg_dark = float(np.mean(dark_counts))
            else:
                avg_dark = float(dark_counts)
                
            # Extrapolate for different integration times
            # Assuming dark counts scale linearly with integration time
            base_integration = calibration_data.get("integration_time", 10.0)
            dark_rate = avg_dark / base_integration if base_integration > 0 else 0
            
            for time_ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
                dark_counts_per_time[str(time_ms)] = dark_rate * time_ms
    
    return {
        "led_models": led_models,
        "dark_counts_per_time": dark_counts_per_time
    }

def create_3stage_model(input_file: Path = None) -> None:
    """Create 3-stage model from calibration results.
    
    Args:
        input_file: Path to calibration results JSON file
    """
    
    # Determine input file
    if input_file is None:
        input_file = Path("calibration_results/latest_calibration.json")
    else:
        input_file = Path(input_file)
    
    if not input_file.exists():
        print(f"❌ Error: Calibration file not found: {input_file}")
        print("\nRun calibration first to generate calibration data.")
        return
    
    print("="*80)
    print("CREATING 3-STAGE LINEAR LED CALIBRATION MODEL")
    print("="*80)
    print(f"Input: {input_file}")
    print()
    
    # Load calibration data
    with open(input_file, 'r') as f:
        calibration_data = json.load(f)
    
    # Extract detector info
    detector_serial = calibration_data.get("calibration_metadata", {}).get("detector_serial", "FLMT09116")
    timestamp_str = calibration_data.get("calibration_metadata", {}).get("timestamp", "")
    
    print(f"Detector: {detector_serial}")
    print(f"Calibration time: {timestamp_str}")
    print()
    
    # Extract LED slopes and dark counts
    model_data = extract_led_slopes(calibration_data)
    
    if not model_data["led_models"]:
        print("❌ Error: No LED response models found in calibration data")
        print("\nThe calibration file must contain 'led_response_models' section.")
        return
    
    # Display extracted models
    print("LED Response Models (slopes):")
    for channel, slopes in model_data["led_models"].items():
        print(f"  Channel {channel}:")
        for time_ms, slope in slopes:
            print(f"    {int(time_ms):3d}ms: {slope:8.2f} counts/intensity")
    print()
    
    print("Dark Counts per Integration Time:")
    for time_ms, counts in sorted(model_data["dark_counts_per_time"].items(), key=lambda x: int(x[0])):
        print(f"  {int(time_ms):3d}ms: {counts:8.2f} counts")
    print()
    
    # Create output filename with timestamp
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    output_dir = Path("led_calibration_official/spr_calibration/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"led_calibration_3stage_{timestamp}.json"
    
    # Save 3-stage model
    with open(output_file, 'w') as f:
        json.dump(model_data, f, indent=2)
    
    print("="*80)
    print("✅ 3-STAGE MODEL CREATED SUCCESSFULLY")
    print("="*80)
    print(f"Output: {output_file}")
    print()
    print("This model can now be used for fast LED intensity calculations:")
    print("  counts = slope_10ms × intensity × (time_ms / 10)")
    print()

if __name__ == "__main__":
    # Parse command line arguments
    input_file = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ["-h", "--help"]:
            print(__doc__)
            sys.exit(0)
        elif sys.argv[1] in ["--input", "-i"]:
            if len(sys.argv) > 2:
                input_file = sys.argv[2]
            else:
                print("❌ Error: --input requires a file path")
                sys.exit(1)
        else:
            input_file = sys.argv[1]
    
    create_3stage_model(input_file)
