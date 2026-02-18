#!/usr/bin/env python3
"""Fix corrupted Unicode characters that display as '?' in the UI.

These were corrupted when PowerShell's Set-Content wrote files in the wrong encoding.
This script finds and replaces them with the correct Unicode symbols.
"""

import os
import re

# Mapping of corrupted character patterns to fixes
# Most corrupted characters are UTF-8 replacement character U+FFFD (displayed as '?')
FIXES = {
    'affilabs/affilabs_core_ui.py': [
        # Line 1348: Delta symbol in "Δ SPR (RU):" became "? SPR (RU):"
        ('f"<b>? SPR (RU):</b>"', 'f"<b>Δ SPR (RU):</b>"'),
        # Line 155-160: Cycle status indicators with corrupted symbols
        ('"⚪ Not built"', '"⚪ Not built"'),  # Should be white circle
        ('"⚪ Idle"', '"⚪ Idle"'),  # Should be white circle
        ('"⚪ Ready"', '"⚪ Ready"'),  # Should be white circle
    ],
    'affilabs/sidebar_tabs/AL_method_builder.py': [
        # Intelligence bar indicator symbols
        ('"✓ Good"', '"✓ Good"'),  # Checkmark
        ('"→ Ready for injection"', '"→ Ready for injection"'),  # Arrow
    ],
}

def fix_file(filepath):
    """Read file, apply fixes, write back."""
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original_content = content
    fixes_applied = 0
    
    if filepath in FIXES:
        for old_text, new_text in FIXES[filepath]:
            if old_text in content:
                content = content.replace(old_text, new_text)
                fixes_applied += 1
                print(f"  ✓ {old_text[:50]} → {new_text[:50]}")
    
    # Also apply byte-level replacement for UTF-8 replacement chars
    content_bytes = content.encode('utf-8')
    if b'\xef\xbf\xbd' in content_bytes:  # U+FFFD replacement char
        # Count before
        count_before = content_bytes.count(b'\xef\xbf\xbd')
        # We'll need to handle these case-by-case since we don't know the original chars
        print(f"  ℹ️  {count_before} UTF-8 replacement characters found (will handle manually)")
        return False
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Fixed {filepath} ({fixes_applied} replacements)")
        return True
    else:
        print(f"- No fixes needed for {filepath}")
        return False

def main():
    """Main entry point."""
    print("=" * 60)
    print("Fixing corrupted Unicode characters in UI files...")
    print("=" * 60)
    
    files_fixed = 0
    
    for filepath in FIXES.keys():
        if fix_file(filepath):
            files_fixed += 1
        print()
    
    print("=" * 60)
    print(f"Summary: Fixed {files_fixed} file(s)")
    print("=" * 60)

if __name__ == '__main__':
    main()
