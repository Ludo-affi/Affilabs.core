"""Phase 7: Replace hardcoded button heights with Dimensions constants"""
from pathlib import Path

def replace_hardcoded_heights():
    """Replace hardcoded setFixedHeight values with Dimensions constants"""

    ui_file = Path("affilabs/affilabs_core_ui.py")

    with open(ui_file, 'r', encoding='utf-8') as f:
        content = f.read()

    original_length = len(content)

    # Replace height values (order by frequency/specificity)
    replacements = [
        ('setFixedHeight(24)', 'setFixedHeight(Dimensions.HEIGHT_BUTTON_SM)'),
        ('setFixedHeight(28)', 'setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)'),
        ('setFixedHeight(32)', 'setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)'),
        ('setFixedHeight(36)', 'setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)'),
        ('setFixedHeight(40)', 'setFixedHeight(Dimensions.HEIGHT_BUTTON_XL)'),
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
    print("PHASE 7: BUTTON HEIGHT CONSOLIDATION")
    print("=" * 70)
    print()

    changes = replace_hardcoded_heights()

    if changes > 0:
        print(f"\n✓ Successfully replaced {changes} hardcoded height values")
    else:
        print("\n✗ No changes made")
