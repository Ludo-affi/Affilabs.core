"""Add quality metrics to existing LED calibration model.

Analyzes saturation and linearity for each LED at each integration time.
Updates the model file with quality_metrics field.
"""

import json
from pathlib import Path

# Load existing model
model_file = Path("led_calibration_official/spr_calibration/data/led_calibration_3stage_20260104_185304.json")

with open(model_file) as f:
    model = json.load(f)

print("=" * 80)
print("ADDING QUALITY METRICS TO LED MODEL")
print("=" * 80)
print(f"Model: {model_file.name}")
print(f"Detector: {model.get('detector_serial', 'UNKNOWN')}")
print()

# Calculate quality metrics for each LED
quality_metrics = {}

for led_name in ['A', 'B', 'C', 'D']:
    if led_name not in model['led_models']:
        continue
        
    stages = model['led_models'][led_name]
    if len(stages) < 2:
        continue
    
    # Get base slope (first stage)
    if isinstance(stages[0], dict):
        base_time = stages[0]['time_ms']
        base_slope = stages[0]['slope']
    else:
        base_time = stages[0][0]
        base_slope = stages[0][1]
    
    metrics = {}
    
    for stage in stages[1:]:
        if isinstance(stage, dict):
            time_ms = stage['time_ms']
            slope = stage['slope']
        else:
            time_ms = stage[0]
            slope = stage[1]
        
        expected_slope = base_slope * (time_ms / base_time)
        linearity = slope / expected_slope if expected_slope > 0 else 0
        
        # Flag saturation if linearity drops below thresholds
        status = "good"
        if linearity < 0.70:
            status = "severely_saturated"
        elif linearity < 0.85:
            status = "saturated"
        elif linearity < 0.95:
            status = "degraded"
        
        metrics[f"{int(time_ms)}ms"] = {
            "linearity": round(linearity, 4),
            "status": status,
            "slope": round(slope, 2),
            "expected_slope": round(expected_slope, 2)
        }
    
    quality_metrics[led_name] = metrics

# Add to model
model['quality_metrics'] = quality_metrics

# Display analysis
print("Quality Metrics Added:")
print()
for led_name in ['A', 'B', 'C', 'D']:
    if led_name not in quality_metrics:
        continue
    print(f"{led_name}:")
    for time_label, metrics in quality_metrics[led_name].items():
        status_icon = {
            "good": "OK",
            "degraded": "WARN",
            "saturated": "SAT",
            "severely_saturated": "CRIT"
        }.get(metrics["status"], "?")
        
        print(f"  {time_label}: [{status_icon:4s}] {metrics['status']:20s} "
              f"(linearity={metrics['linearity']:.3f}, "
              f"slope={metrics['slope']:.1f} vs expected {metrics['expected_slope']:.1f})")
    print()

# Save updated model
backup_file = model_file.with_suffix('.json.backup')
model_file.rename(backup_file)
print(f"Backup saved: {backup_file.name}")

with open(model_file, 'w') as f:
    json.dump(model, f, indent=2)

print(f"✓ Updated model saved: {model_file.name}")
print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Count issues
total_stages = 0
degraded = 0
saturated = 0
severely_saturated = 0

for led_metrics in quality_metrics.values():
    for metrics in led_metrics.values():
        total_stages += 1
        if metrics['status'] == 'degraded':
            degraded += 1
        elif metrics['status'] == 'saturated':
            saturated += 1
        elif metrics['status'] == 'severely_saturated':
            severely_saturated += 1

print(f"Total stages analyzed: {total_stages}")
print(f"  Good: {total_stages - degraded - saturated - severely_saturated}")
print(f"  Degraded (0.85-0.95): {degraded}")
print(f"  Saturated (0.70-0.85): {saturated}")
print(f"  Severely saturated (<0.70): {severely_saturated}")
print()

if saturated + severely_saturated > 0:
    print("⚠️  Recommendation: Re-train model with lower LED intensities at long integration times")
    print("   or use only 10ms and 20ms data for channels C and D.")
else:
    print("✓ Model quality is good!")
