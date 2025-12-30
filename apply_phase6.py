"""Phase 6: Replace hardcoded color values with Colors constants"""
from pathlib import Path
import re

def replace_hardcoded_colors():
    """Replace hardcoded hex colors with Colors class constants"""

    ui_file = Path("affilabs/affilabs_core_ui.py")

    with open(ui_file, 'r', encoding='utf-8') as f:
        content = f.read()

    original_length = len(content)

    # Replace color values (order matters - do specific patterns first)
    replacements = [
        # Primary text color
        ('color: #1D1D1F;', f'color: {{Colors.PRIMARY_TEXT}};'),
        # Secondary text color
        ('color: #86868B;', f'color: {{Colors.SECONDARY_TEXT}};'),
        # Background white
        ('background: #FFFFFF;', f'background: {{Colors.BACKGROUND_WHITE}};'),
        # Background in QFrame stylesheets
        ('{ background: #FFFFFF;', f'{{ background: {{Colors.BACKGROUND_WHITE}};'),
        # Background in QDialog
        ('QDialog { background: #FFFFFF;', f'QDialog {{ background: {{Colors.BACKGROUND_WHITE}};'),
    ]

    changes_made = 0
    for old, new in replacements:
        count = content.count(old)
        if count > 0:
            content = content.replace(old, new)
            changes_made += count
            print(f"  Replaced {count}× '{old}' → '{new}'")

    # Write back
    with open(ui_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\nTotal replacements: {changes_made}")
    print(f"File size: {original_length} → {len(content)} bytes")

    return changes_made

if __name__ == '__main__':
    print("=" * 70)
    print("PHASE 6: HARDCODED COLOR CONSOLIDATION")
    print("=" * 70)
    print()

    changes = replace_hardcoded_colors()

    if changes > 0:
        print(f"\n✓ Successfully replaced {changes} hardcoded color values")
    else:
        print("\n✗ No changes made")
