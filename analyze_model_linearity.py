"""Analyze LED model linearity and identify saturation points."""

import json

# Load model
with open('led_calibration_official/spr_calibration/data/led_calibration_3stage_20260104_185304.json') as f:
    model = json.load(f)

print("=" * 80)
print("LED MODEL LINEARITY ANALYSIS")
print("=" * 80)

for led_name in ['A', 'B', 'C', 'D']:
    print(f"\n{led_name}:")
    stages = model['led_models'][led_name]
    base_slope = stages[0]['slope']  # 10ms slope
    
    print(f"  10ms: {base_slope:8.2f} (baseline)")
    
    for stage in stages[1:]:
        time_ms = stage['time_ms']
        slope = stage['slope']
        expected = base_slope * (time_ms / 10.0)
        ratio = slope / expected if expected > 0 else 0
        linearity = ratio  # How close to linear scaling (1.0 = perfect)
        
        status = "✓" if linearity > 0.95 else "⚠️ " if linearity > 0.85 else "❌"
        print(f"  {time_ms}ms: {slope:8.2f} (expected {expected:8.2f}, ratio={linearity:.3f}) {status}")

print("\n" + "=" * 80)
print("LINEARITY SUMMARY (ratios of 20ms/10ms and 30ms/10ms)")
print("=" * 80)

for led_name in ['A', 'B', 'C', 'D']:
    stages = model['led_models'][led_name]
    base_slope = stages[0]['slope']
    
    if len(stages) >= 3:
        slope_20ms = stages[1]['slope']
        slope_30ms = stages[2]['slope']
        
        linearity_20 = slope_20ms / (base_slope * 2.0) if base_slope > 0 else 0
        linearity_30 = slope_30ms / (base_slope * 3.0) if base_slope > 0 else 0
        avg_linearity = (linearity_20 + linearity_30) / 2.0
        
        print(f"{led_name}: 20ms={linearity_20:.4f}, 30ms={linearity_30:.4f}, avg={avg_linearity:.4f}")
