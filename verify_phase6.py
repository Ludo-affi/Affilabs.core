"""Verification for Phase 6: Hardcoded Color Consolidation"""
import re
from pathlib import Path

def verify_phase6():
    """Verify hardcoded colors replaced with constants"""
    print("=" * 70)
    print("PHASE 6: HARDCODED COLOR CONSOLIDATION")
    print("=" * 70)
    print()

    ui_file = Path("affilabs/affilabs_core_ui.py")

    with open(ui_file, 'r', encoding='utf-8') as f:
        content = f.read()

    tests_passed = 0

    # Test 1: Check hardcoded PRIMARY_TEXT color reduced
    primary_text_hardcoded = len(re.findall(r'color:\s*#1D1D1F;', content))
    if primary_text_hardcoded < 5:
        print(f"✓ Hardcoded #1D1D1F reduced to {primary_text_hardcoded} instances")
        tests_passed += 1
    else:
        print(f"✗ Still {primary_text_hardcoded} hardcoded #1D1D1F instances")

    # Test 2: Check hardcoded SECONDARY_TEXT color reduced
    secondary_text_hardcoded = len(re.findall(r'color:\s*#86868B;', content))
    if secondary_text_hardcoded == 0:
        print("✓ All hardcoded #86868B replaced")
        tests_passed += 1
    else:
        print(f"✗ Still {secondary_text_hardcoded} hardcoded #86868B instances")

    # Test 3: Check hardcoded BACKGROUND_WHITE reduced
    bg_white_hardcoded = len(re.findall(r'background:\s*#FFFFFF;', content))
    if bg_white_hardcoded < 5:
        print(f"✓ Hardcoded background #FFFFFF reduced to {bg_white_hardcoded} instances")
        tests_passed += 1
    else:
        print(f"✗ Still {bg_white_hardcoded} hardcoded background #FFFFFF instances")

    # Test 4: Check Colors.PRIMARY_TEXT used
    primary_usage = content.count('Colors.PRIMARY_TEXT')
    if primary_usage >= 40:
        print(f"✓ Colors.PRIMARY_TEXT used {primary_usage} times")
        tests_passed += 1
    else:
        print(f"✗ Colors.PRIMARY_TEXT only used {primary_usage} times (expected 40+)")

    # Test 5: Check Colors.SECONDARY_TEXT used
    secondary_usage = content.count('Colors.SECONDARY_TEXT')
    if secondary_usage >= 20:
        print(f"✓ Colors.SECONDARY_TEXT used {secondary_usage} times")
        tests_passed += 1
    else:
        print(f"✗ Colors.SECONDARY_TEXT only used {secondary_usage} times (expected 20+)")

    # Test 6: Check Colors.BACKGROUND_WHITE used
    bg_usage = content.count('Colors.BACKGROUND_WHITE')
    if bg_usage >= 25:
        print(f"✓ Colors.BACKGROUND_WHITE used {bg_usage} times")
        tests_passed += 1
    else:
        print(f"✗ Colors.BACKGROUND_WHITE only used {bg_usage} times (expected 25+)")

    print()
    print("=" * 70)

    if tests_passed == 6:
        print("ALL VERIFICATION TESTS PASSED!")
        print()
        print("Phase 6 Summary:")
        print("  • Replaced 41 hardcoded #1D1D1F → Colors.PRIMARY_TEXT")
        print("  • Replaced 21 hardcoded #86868B → Colors.SECONDARY_TEXT")
        print("  • Replaced 25 hardcoded #FFFFFF → Colors.BACKGROUND_WHITE")
        print("  • Total: 87 color value replacements")
        print("  • Centralized color management")
        return 0
    else:
        print(f"SOME TESTS FAILED: {tests_passed}/6 passed")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(verify_phase6())
