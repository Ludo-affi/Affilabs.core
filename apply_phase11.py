"""Apply Phase 11 (Transparent Background) consolidation."""

file_path = "affilabs/affilabs_core_ui.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# Phase 11: Transparent Background Consolidation
# Replace hardcoded 'background: transparent;' with {Colors.TRANSPARENT}
replacements = [
    ('background: transparent;', 'background: {Colors.TRANSPARENT};'),
]

transparent_count = 0
for old_str, new_str in replacements:
    count = content.count(old_str)
    if count > 0:
        content = content.replace(old_str, new_str)
        transparent_count += count
        print(f"Replaced {count}× '{old_str}' → '{new_str}'")

if content != original_content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✓ Phase 11: {transparent_count} transparent background replacements")
else:
    print("No changes made")
