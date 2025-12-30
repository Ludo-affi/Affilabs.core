"""Apply Phase 8 (Font Family) and Phase 9 (Border Radius) consolidation."""
import re

file_path = "affilabs/affilabs_core_ui.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

original_content = content

# Phase 8: Font Family Consolidation
# Replace hardcoded font-family strings with Fonts.SYSTEM
replacements_phase8 = [
    (
        'font-family: -apple-system, \'SF Pro Text\', \'Segoe UI\', system-ui, sans-serif;',
        'font-family: {Fonts.SYSTEM};'
    ),
    (
        'font-family: -apple-system, "SF Pro Text", "Segoe UI", system-ui, sans-serif;',
        'font-family: {Fonts.SYSTEM};'
    ),
]

font_family_count = 0
for old_str, new_str in replacements_phase8:
    count = content.count(old_str)
    if count > 0:
        content = content.replace(old_str, new_str)
        font_family_count += count
        print(f"Replaced {count}× '{old_str[:50]}...' → '{new_str}'")

# Phase 9: Border Radius Consolidation
# Replace hardcoded border-radius: 12px; with {Dimensions.BORDER_RADIUS_LG}
border_radius_replacements = [
    ('border-radius: 12px;', 'border-radius: {Dimensions.BORDER_RADIUS_LG};'),
]

border_radius_count = 0
for old_str, new_str in border_radius_replacements:
    count = content.count(old_str)
    if count > 0:
        content = content.replace(old_str, new_str)
        border_radius_count += count
        print(f"Replaced {count}× '{old_str}' → '{new_str}'")

if content != original_content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✓ Phase 8: {font_family_count} font-family replacements")
    print(f"✓ Phase 9: {border_radius_count} border-radius replacements")
    print(f"Total: {font_family_count + border_radius_count} replacements")
else:
    print("No changes made")
