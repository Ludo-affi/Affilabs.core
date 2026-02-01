#!/usr/bin/env python3
"""
Clean up old markdown documentation files
Organizes .md files into archive folders based on type
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Workspace root
WORKSPACE = Path(__file__).parent

# Archive locations
ARCHIVE_FIRMWARE = WORKSPACE / "archive" / "firmware_docs"
ARCHIVE_CALIBRATION = WORKSPACE / "archive" / "calibration_docs"
ARCHIVE_IMPLEMENTATION = WORKSPACE / "archive" / "implementation_docs"
ARCHIVE_TESTING = WORKSPACE / "archive" / "testing_docs"
ARCHIVE_GENERAL = WORKSPACE / "archive" / "general_docs"

# Keep these files (don't archive)
KEEP_FILES = {
    "README.md",
    "LICENSE.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
}

# Keywords for categorization
FIRMWARE_KEYWORDS = ["firmware", "build", "flash", "uf2", "pico", "p4spr", "p4pro", "timer", "isr"]
CALIBRATION_KEYWORDS = ["calibration", "servo", "polarizer", "led", "spr", "convergence"]
IMPLEMENTATION_KEYWORDS = ["implementation", "guide", "integration", "architecture", "design"]
TESTING_KEYWORDS = ["testing", "validation", "test", "debug"]

def categorize_md(filename: str) -> Path:
    """Determine archive location based on filename"""
    lower = filename.lower()

    if any(kw in lower for kw in FIRMWARE_KEYWORDS):
        return ARCHIVE_FIRMWARE
    elif any(kw in lower for kw in CALIBRATION_KEYWORDS):
        return ARCHIVE_CALIBRATION
    elif any(kw in lower for kw in IMPLEMENTATION_KEYWORDS):
        return ARCHIVE_IMPLEMENTATION
    elif any(kw in lower for kw in TESTING_KEYWORDS):
        return ARCHIVE_TESTING
    else:
        return ARCHIVE_GENERAL

def find_md_files():
    """Find all .md files in workspace (excluding specific folders)"""
    exclude_dirs = {".git", ".venv", ".venv312", "node_modules", "__pycache__",
                    "pico-p4spr-firmware", "archive"}

    md_files = []
    for root, dirs, files in os.walk(WORKSPACE):
        # Remove excluded directories from search
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.md'):
                md_files.append(Path(root) / file)

    return md_files

def should_keep(filepath: Path) -> bool:
    """Check if file should be kept (not archived)"""
    # Keep files in specific folders
    if "pico-p4spr-firmware" in str(filepath):
        return True
    if "pico-p4pro-firmware" in str(filepath):
        return True

    # Keep important root files
    if filepath.name in KEEP_FILES:
        return True

    return False

def main():
    print("=" * 70)
    print("Markdown Documentation Cleanup Tool")
    print("=" * 70)

    # Create archive directories
    for archive_dir in [ARCHIVE_FIRMWARE, ARCHIVE_CALIBRATION, ARCHIVE_IMPLEMENTATION,
                        ARCHIVE_TESTING, ARCHIVE_GENERAL]:
        archive_dir.mkdir(parents=True, exist_ok=True)

    # Find all markdown files
    md_files = find_md_files()
    print(f"\nFound {len(md_files)} markdown files")

    # Categorize
    to_archive = []
    to_keep = []

    for filepath in md_files:
        if should_keep(filepath):
            to_keep.append(filepath)
        else:
            archive_dest = categorize_md(filepath.name)
            to_archive.append((filepath, archive_dest))

    print(f"\n📌 Files to KEEP: {len(to_keep)}")
    for f in sorted(to_keep):
        rel_path = f.relative_to(WORKSPACE)
        print(f"  ✓ {rel_path}")

    print(f"\n📦 Files to ARCHIVE: {len(to_archive)}")

    # Group by destination
    by_dest = {}
    for filepath, dest in to_archive:
        if dest not in by_dest:
            by_dest[dest] = []
        by_dest[dest].append(filepath)

    for dest, files in sorted(by_dest.items()):
        dest_name = dest.relative_to(WORKSPACE / "archive")
        print(f"\n  → {dest_name}/")
        for f in sorted(files):
            rel_path = f.relative_to(WORKSPACE)
            print(f"    • {rel_path}")

    # Confirm
    print("\n" + "=" * 70)
    response = input("Archive these files? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        moved_count = 0
        for filepath, dest in to_archive:
            try:
                dest_file = dest / filepath.name

                # Handle duplicates
                if dest_file.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    stem = dest_file.stem
                    dest_file = dest / f"{stem}_{timestamp}.md"

                shutil.move(str(filepath), str(dest_file))
                moved_count += 1
                print(f"✓ Moved: {filepath.name} → {dest.name}/")
            except Exception as e:
                print(f"✗ Error moving {filepath.name}: {e}")

        print(f"\n✅ Successfully archived {moved_count} files")
        print(f"📁 Archive location: {WORKSPACE / 'archive'}")
    else:
        print("\n❌ Operation cancelled")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
