"""Add comprehensive debugging to calibration flow to diagnose channel B/C failure."""

# Read the calibration file
with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find specific lines and add debug statements after them
insertions = []

for i, line in enumerate(lines):
    # After S-mode calibration completes
    if 'Use the maximum integration time across all channels for consistency' in line:
        insertions.append((i+1, '        print(f"\\n[SEARCH] DEBUG: Completed S-mode calibration loop")\n'))
    
    # Before dark noise
    elif 'Step 2: Measure dark noise AT MAX INTEGRATION TIME' in line and '# Step 2:' in line:
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: About to measure dark noise...")\n'))
    
    # After dark noise
    elif 'Dark noise measurement complete (single measurement for all channels)' in line:
        insertions.append((i+1, '        print(f"\\n[SEARCH] DEBUG: Dark noise complete")\n'))
    
    # Before reference signals
    elif line.strip() == '# Step 4: Measure reference signals':
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: About to measure S-mode reference signals...")\n'))
    
    # Before S-ref QC
    elif 'Performing S-ref optical quality checks' in line:
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: About to perform S-ref QC validation...")\n'))
    
    # Before P-mode calibration
    elif line.strip() == '# Step 6: P-mode calibration - optimize integration time for 80% of max counts':
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: Starting P-mode calibration...")\n'))
    
    # Before P-ref measurement
    elif line.strip() == '# Step 6A: Measure P-mode reference signals using max integration time':
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: About to measure P-mode reference signals...")\n'))
    
    # Before verify_calibration
    elif line.strip() == '# Step 7: Verify P-mode calibration (shared QC function)':
        insertions.append((i, '        print("\\n[SEARCH] DEBUG: About to call verify_calibration...")\n'))

# Insert in reverse order to maintain line numbers
for idx, text in reversed(insertions):
    lines.insert(idx, text)

# Write back
with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"[OK] Added {len(insertions)} debug points to calibration flow")
print("   Debug points added at:")
print("   - S-mode calibration completion")
print("   - Dark noise measurement")
print("   - S-mode reference signals")
print("   - S-ref QC validation")
print("   - P-mode calibration")
print("   - P-mode reference signals")
print("   - verify_calibration call")
print("")
print("Now run the calibration again to see exactly where it fails!")
