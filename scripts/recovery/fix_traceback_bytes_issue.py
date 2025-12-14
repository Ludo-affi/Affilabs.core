"""
Automated fix for traceback.print_exc() bytes issue.

This script finds all instances of traceback.print_exc() and replaces them
with traceback.format_exc() to avoid TypeError: string argument expected, got 'bytes'
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

def find_print_exc_instances(root_dir: str) -> List[Tuple[str, int, str]]:
    """Find all traceback.print_exc() calls in Python files.

    Returns:
        List of (file_path, line_number, line_content) tuples
    """
    instances = []
    src_dir = Path(root_dir) / "src"

    for py_file in src_dir.rglob("*.py"):
        # Skip test files and legacy files
        if "test_" in py_file.name or "afterglow" in py_file.name.lower():
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                if 'traceback.print_exc()' in line and not line.strip().startswith('#'):
                    instances.append((str(py_file), line_num, line.rstrip()))
        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    return instances

def fix_print_exc_in_file(file_path: str) -> int:
    """Replace traceback.print_exc() with format_exc() in a file.

    Returns:
        Number of replacements made
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        replacements = 0

        # Pattern 1: Simple traceback.print_exc()
        pattern1 = r'(\s+)traceback\.print_exc\(\)'
        replacement1 = r'\1try:\n\1    print(traceback.format_exc())\n\1except:\n\1    pass'

        # Count matches first
        matches = list(re.finditer(pattern1, content))
        if matches:
            # Replace from end to start to preserve positions
            for match in reversed(matches):
                start = match.start()
                end = match.end()
                indent = match.group(1)

                # Build replacement with proper indentation
                new_code = f"{indent}try:\n{indent}    print(traceback.format_exc())\n{indent}except:\n{indent}    pass"
                content = content[:start] + new_code + content[end:]
                replacements += 1

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed {replacements} instance(s) in {file_path}")
            return replacements

        return 0

    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return 0

def main():
    """Main function to find and fix all instances."""
    root_dir = os.path.dirname(os.path.abspath(__file__))

    print("="*80)
    print("TRACEBACK BYTES ISSUE - AUTOMATED FIX")
    print("="*80)

    # Find all instances
    print("\n🔍 Scanning for traceback.print_exc() calls...")
    instances = find_print_exc_instances(root_dir)

    if not instances:
        print("✅ No instances found - all clean!")
        return

    print(f"\n📋 Found {len(instances)} instance(s):\n")
    for file_path, line_num, line_content in instances:
        rel_path = os.path.relpath(file_path, root_dir)
        print(f"  {rel_path}:{line_num}")
        print(f"    {line_content.strip()}")

    # Ask for confirmation
    print("\n" + "="*80)
    response = input("🔧 Fix all instances? (y/n): ")

    if response.lower() != 'y':
        print("Aborted.")
        return

    # Fix all files
    print("\n🔧 Fixing files...\n")
    total_fixed = 0
    files_processed = set()

    for file_path, _, _ in instances:
        if file_path not in files_processed:
            fixed = fix_print_exc_in_file(file_path)
            total_fixed += fixed
            files_processed.add(file_path)

    print("\n" + "="*80)
    print(f"✅ COMPLETE: Fixed {total_fixed} instance(s) in {len(files_processed)} file(s)")
    print("="*80)

if __name__ == '__main__':
    main()
