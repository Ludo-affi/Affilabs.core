#!/usr/bin/env python3
"""Complete fix for perform_alternative_calibration()"""

with open("utils/led_calibration.py", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

# Step 1: Add pre_led_delay_ms and post_led_delay_ms parameters to function signature
# Find line 2793 (afterglow_correction line)
for i, line in enumerate(lines):
    if (
        i > 2790
        and "afterglow_correction=None" in line
        and "Optional: pre-loaded AfterglowCorrection" in line
    ):
        print(f"Found afterglow line at {i+1}: {line.strip()}")
        # Add comma if not present
        if not line.rstrip().endswith(","):
            lines[i] = line.rstrip() + ",\n"
        # Insert new parameters
        lines.insert(
            i + 1,
            "    pre_led_delay_ms: float = 45.0,  # PRE LED delay: settling time after LED on (default 45ms)\n",
        )
        lines.insert(
            i + 2,
            "    post_led_delay_ms: float = 5.0,  # POST LED delay: dark time after LED off (default 5ms)\n",
        )
        print("✅ Parameters added")
        break

# Step 2: Add debug prints at function entry
# Find "result = LEDCalibrationResult()" around line 2847
for i, line in enumerate(lines):
    if (
        i > 2840
        and i < 2860
        and "result = LEDCalibrationResult()" in line
        and "perform_alternative" in "".join(lines[max(0, i - 50) : i])
    ):
        print(f"Found result = LEDCalibrationResult() at {i+1}")
        # Insert debug prints after this line
        lines.insert(i + 1, "\n")
        lines.insert(i + 2, '    print("\\n" + "="*80)\n')
        lines.insert(
            i + 3,
            '    print("🔥🔥🔥 perform_alternative_calibration() ENTERED")\n',
        )
        lines.insert(i + 4, '    print("="*80 + "\\n")\n')
        lines.insert(i + 5, "\n")
        print("✅ Entry prints added")
        break

# Step 3: Add debug print in try block
# Find the try: statement after the above insertion
for i, line in enumerate(lines):
    if i > 2850 and i < 2870 and line.strip() == "try:":
        print(f"Found try: at {i+1}")
        # Insert print after try:
        lines.insert(i + 1, '        print("🔥 Entering try block...")\n')
        print("✅ Try block print added")
        break

# Step 4: Add exception handler prints
# Find "except Exception as e:" near end of function
for i in range(len(lines) - 1, 0, -1):
    line = lines[i]
    if (
        "except Exception as e:" in line
        and "LED calibration failed (Global LED Intensity Method)" in lines[i + 1]
    ):
        print(f"Found except block at {i+1}")
        # Insert debug prints
        lines.insert(i + 1, '        print("\\n" + "="*80)\n')
        lines.insert(
            i + 2,
            '        print("❌❌❌ EXCEPTION IN perform_alternative_calibration()")\n',
        )
        lines.insert(i + 3, '        print("="*80)\n')
        lines.insert(i + 4, '        print(f"Exception: {e}")\n')
        lines.insert(i + 5, "        import traceback\n")
        lines.insert(i + 6, "        traceback.print_exc()\n")
        lines.insert(i + 7, '        print("="*80 + "\\n")\n')
        print("✅ Exception handler prints added")
        break

# Write back
with open("utils/led_calibration.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("\n✅ All changes applied successfully!")
print(f"   Final file: {len(lines)} lines")
