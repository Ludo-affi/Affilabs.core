"""Check and fix duplicate (intensity, time) pairs in calibration plan"""

import json

# Load plan
with open('LED-Counts relationship/spr_calibration_plan.json', 'r') as f:
    plan = json.load(f)

print("="*80)
print("CHECKING FOR DUPLICATE (INTENSITY, TIME) PAIRS")
print("="*80)

all_good = True

for led_name in ['A', 'B', 'C', 'D']:
    points = plan[led_name]

    # Check for duplicates
    pairs = [(p['intensity'], p['time']) for p in points]
    unique_pairs = set(pairs)

    print(f"\nLED {led_name}:")
    print(f"  Total points: {len(points)}")
    print(f"  Unique (I,T) pairs: {len(unique_pairs)}")

    if len(pairs) != len(unique_pairs):
        all_good = False
        print(f"  ⚠️  DUPLICATES FOUND!")

        # Find duplicates
        seen = {}
        for i, pair in enumerate(pairs):
            if pair in seen:
                print(f"    Duplicate: I={pair[0]}, T={pair[1]} ms")
                print(f"      First occurrence: index {seen[pair]}, target={points[seen[pair]]['target_counts']}")
                print(f"      Duplicate at: index {i}, target={points[i]['target_counts']}")
            else:
                seen[pair] = i
    else:
        print(f"  ✓ No duplicates")

if all_good:
    print("\n✓ No duplicates found in any LED")
else:
    print("\n⚠️  DUPLICATES DETECTED - Plan needs fixing")
    print("\nThe issue: Same (intensity, time) cannot target different counts")
    print("Solution: Remove one of the duplicate entries or adjust intensity/time")
