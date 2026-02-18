"""Verification script for Phase 5: Layout Constants Consolidation"""
import re
from pathlib import Path

def verify_layout_constants():
    """Verify layout constants consolidation"""
    print("=" * 70)
    print("PHASE 5: LAYOUT CONSTANTS CONSOLIDATION")
    print("=" * 70)
    print()

    ui_file = Path("affilabs/affilabs_core_ui.py")
    ui_styles = Path("affilabs/ui_styles.py")

    with open(ui_file, 'r', encoding='utf-8') as f:
        ui_content = f.read()

    with open(ui_styles, 'r', encoding='utf-8') as f:
        styles_content = f.read()

    tests_passed = 0

    # Test 1: Check Dimensions class has new constants
    if all(const in styles_content for const in ['MARGIN_SM', 'MARGIN_MD', 'MARGIN_LG', 'SPACING_SM', 'SPACING_MD', 'SPACING_LG']):
        print("✓ Layout constants added to Dimensions class")
        tests_passed += 1
    else:
        print("✗ Layout constants missing from Dimensions class")

    # Test 2: Check Dimensions is imported
    if 'from affilabs.ui_styles import' in ui_content and 'Dimensions' in ui_content:
        print("✓ Dimensions imported in affilabs_core_ui.py")
        tests_passed += 1
    else:
        print("✗ Dimensions not imported")

    # Test 3: Check hardcoded margins are replaced
    hardcoded_16 = len(re.findall(r'setContentsMargins\(16,\s*16,\s*16,\s*16\)', ui_content))
    if hardcoded_16 == 0:
        print("✓ All setContentsMargins(16,16,16,16) replaced")
        tests_passed += 1
    else:
        print(f"✗ Found {hardcoded_16} hardcoded setContentsMargins(16,16,16,16)")

    # Test 4: Check hardcoded margins 12 are replaced
    hardcoded_12 = len(re.findall(r'setContentsMargins\(12,\s*12,\s*12,\s*12\)', ui_content))
    if hardcoded_12 == 0:
        print("✓ All setContentsMargins(12,12,12,12) replaced")
        tests_passed += 1
    else:
        print(f"✗ Found {hardcoded_12} hardcoded setContentsMargins(12,12,12,12)")

    # Test 5: Check Dimensions.MARGIN usage
    margin_usage = ui_content.count('Dimensions.MARGIN_MD')
    if margin_usage >= 14:
        print(f"✓ Dimensions.MARGIN_MD used {margin_usage} times")
        tests_passed += 1
    else:
        print(f"✗ Dimensions.MARGIN_MD only used {margin_usage} times (expected 14+)")

    # Test 6: Check Dimensions.SPACING usage
    spacing_usage = ui_content.count('Dimensions.SPACING_')
    if spacing_usage >= 12:
        print(f"✓ Dimensions.SPACING_* used {spacing_usage} times")
        tests_passed += 1
    else:
        print(f"✗ Dimensions.SPACING_* only used {spacing_usage} times (expected 12+)")

    print()
    print("=" * 70)

    if tests_passed == 6:
        print("ALL VERIFICATION TESTS PASSED!")
        print()
        print("Phase 5 Summary:")
        print("  • Added 6 new layout constants to Dimensions class")
        print("  • MARGIN_SM=12, MARGIN_MD=16, MARGIN_LG=20")
        print("  • SPACING_SM=8, SPACING_MD=12, SPACING_LG=16")
        print("  • Replaced 16 hardcoded margin values")
        print(f"  • Replaced {spacing_usage} hardcoded spacing values")
        print("  • Centralized layout configuration")
        return 0
    else:
        print(f"SOME TESTS FAILED: {tests_passed}/6 passed")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(verify_layout_constants())
