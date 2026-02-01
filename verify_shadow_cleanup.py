"""Verification script for shadow effect cleanup"""
import re
from pathlib import Path

def verify_shadow_cleanup():
    """Verify shadow effect helper function cleanup"""
    print("=" * 70)
    print("SHADOW EFFECT CLEANUP VERIFICATION")
    print("=" * 70)
    print()

    ui_file = Path("affilabs/affilabs_core_ui.py")
    ui_styles = Path("affilabs/ui_styles.py")

    # Read files
    with open(ui_file, 'r', encoding='utf-8') as f:
        ui_content = f.read()

    with open(ui_styles, 'r', encoding='utf-8') as f:
        styles_content = f.read()

    tests_passed = 0

    # Test 1: Check for create_card_shadow helper in ui_styles.py
    if 'def create_card_shadow()' in styles_content:
        print("✓ create_card_shadow() helper exists in ui_styles.py")
        tests_passed += 1
    else:
        print("✗ create_card_shadow() helper NOT FOUND in ui_styles.py")

    # Test 2: Check helper is imported in affilabs_core_ui.py
    if 'from affilabs.ui_styles import' in ui_content and 'create_card_shadow' in ui_content:
        print("✓ create_card_shadow imported in affilabs_core_ui.py")
        tests_passed += 1
    else:
        print("✗ create_card_shadow NOT IMPORTED in affilabs_core_ui.py")

    # Test 3: Check helper is used (should find multiple calls)
    helper_calls = ui_content.count('.setGraphicsEffect(create_card_shadow())')
    if helper_calls >= 10:
        print(f"✓ create_card_shadow() called {helper_calls} times")
        tests_passed += 1
    else:
        print(f"✗ create_card_shadow() only called {helper_calls} times (expected 10+)")

    # Test 4: Check old pattern is mostly removed (should be < 3 instances)
    old_pattern_count = len(re.findall(r'shadow\s*=\s*QGraphicsDropShadowEffect\(\)', ui_content))
    if old_pattern_count <= 3:
        print(f"✓ Old shadow pattern mostly removed ({old_pattern_count} remaining)")
        tests_passed += 1
    else:
        print(f"✗ Old shadow pattern still present ({old_pattern_count} instances)")

    # Test 5: Check blur=8 pattern is mostly removed
    blur8_count = len(re.findall(r'shadow\.setBlurRadius\(8\)', ui_content))
    if blur8_count == 0:
        print("✓ shadow.setBlurRadius(8) pattern removed")
        tests_passed += 1
    else:
        print(f"✗ shadow.setBlurRadius(8) still present ({blur8_count} instances)")

    # Test 6: Check file size reduction
    line_count = len(ui_content.splitlines())
    if line_count < 7100:
        print(f"✓ File reduced to {line_count} lines (was 7,124)")
        tests_passed += 1
    else:
        print(f"✗ File has {line_count} lines (expected < 7,100)")

    print()
    print("=" * 70)

    if tests_passed == 6:
        print("ALL VERIFICATION TESTS PASSED!")
        print()
        print("Cleanup Summary:")
        print("  • Created create_card_shadow() helper in ui_styles.py")
        print(f"  • Replaced {helper_calls} instances of manual shadow creation")
        print(f"  • Reduced affilabs_core_ui.py to {line_count} lines")
        print(f"  • Saved ~{7124 - line_count} lines of duplicate code")
        return 0
    else:
        print(f"SOME TESTS FAILED: {tests_passed}/6 passed")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(verify_shadow_cleanup())
