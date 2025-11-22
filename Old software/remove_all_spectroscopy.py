with open('main/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines to remove entirely (518-522, 1280, 1307, 1500, 1568)
lines_to_remove = [518, 519, 520, 521, 522, 1280, 1307, 1500, 1568]

# Lines to replace (2760-2761)
# These lines check hasattr and should be kept but modified

# Remove lines in reverse order to maintain indices
for line_num in sorted(lines_to_remove, reverse=True):
    idx = line_num - 1  # Convert to 0-indexed
    print(f"Removing line {line_num}: {lines[idx].strip()}")
    del lines[idx]

# Find and replace the hasattr lines (they will have shifted after deletions)
new_lines = []
for i, line in enumerate(lines):
    if "hasattr(self.main_window, 'spectroscopy') and hasattr(self.main_window.spectroscopy" in line:
        print(f"Removing line {i+1}: {line.strip()}")
        # Skip this line and the next one (they're part of the same if block)
        continue
    elif i > 0 and "spectroscopy.set_advanced_smoothing" in line and "hasattr" in lines[i-1]:
        # Skip the second line of the if block
        print(f"Removing line {i+1}: {line.strip()}")
        continue
    else:
        new_lines.append(line)

with open('main/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("\n✅ Removed all spectroscopy references!")
