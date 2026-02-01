"""Apply Phase 10 (Font Weight) consolidation."""

file_path = "affilabs/affilabs_core_ui.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# Phase 10: Font Weight Consolidation
# Replace hardcoded font-weight: 700; with {Fonts.WEIGHT_BOLD}
replacements = [
    ('font-weight: 700;', 'font-weight: {Fonts.WEIGHT_BOLD};'),
]

font_weight_count = 0
for old_str, new_str in replacements:
    count = content.count(old_str)
    if count > 0:
        content = content.replace(old_str, new_str)
        font_weight_count += count
        print(f"Replaced {count}× '{old_str}' → '{new_str}'")

if content != original_content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✓ Phase 10: {font_weight_count} font-weight replacements")
else:
    print("No changes made")
