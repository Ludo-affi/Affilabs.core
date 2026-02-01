#!/usr/bin/env python3
"""
cleanup_root_files.py
Clean up .csv, .png, and test*.py files from the root directory.
Organizes them into categorized archive folders.
"""

from pathlib import Path

# Get workspace root
WORKSPACE_ROOT = Path(__file__).parent

# Define archive base directory
ARCHIVE_BASE = WORKSPACE_ROOT / "archive_root_files"

# Define categories for different file types
CATEGORIES = {
    "csv": {
        "optimization": ["optimization", "pipeline", "fourier", "savgol", "batch", "extreme"],
        "results": ["results", "constraint", "strategies", "combination"],
        "general": []  # catch-all
    },
    "png": {
        "analysis": ["analysis", "diagnostic", "study", "comparison"],
        "calibration": ["calibration", "validation", "balancing"],
        "plots": ["plot", "afterglow", "peak", "spectral"],
        "general": []  # catch-all
    },
    "test_py": {
        "firmware": ["firmware", "v2.2", "timer", "led_control", "led_commands"],
        "calibration": ["calibration", "led_calibration", "servo", "polarizer"],
        "optimization": ["optimization", "pipeline", "fourier", "savgol", "batch", "extreme", "speed"],
        "hardware": ["led_", "detector", "timing", "integration", "power_cycle"],
        "ui": ["ui", "live_view", "cursor"],
        "signal": ["signal", "afterglow", "baseline", "transmission", "peak"],
        "general": []  # catch-all
    }
}


def categorize_file(filename, file_type):
    """Determine the category for a file based on keywords."""
    filename_lower = filename.lower()

    for category, keywords in CATEGORIES[file_type].items():
        if category == "general":
            continue
        for keyword in keywords:
            if keyword in filename_lower:
                return category

    return "general"


def find_root_files():
    """Find all CSV, PNG, and test*.py files in the root directory."""
    csv_files = list(WORKSPACE_ROOT.glob("*.csv"))
    png_files = list(WORKSPACE_ROOT.glob("*.png"))
    test_files = list(WORKSPACE_ROOT.glob("test*.py"))

    return {
        "csv": csv_files,
        "png": png_files,
        "test_py": test_files
    }


def organize_files():
    """Organize files by category and display the plan."""
    files = find_root_files()

    plan = {
        "csv": {},
        "png": {},
        "test_py": {}
    }

    # Organize by category
    for file_type, file_list in files.items():
        for file_path in file_list:
            category = categorize_file(file_path.name, file_type)
            if category not in plan[file_type]:
                plan[file_type][category] = []
            plan[file_type][category].append(file_path)

    return plan


def display_plan(plan):
    """Display the archival plan to the user."""
    total_files = sum(len(files) for type_dict in plan.values() for files in type_dict.values())

    if total_files == 0:
        print("✓ No files to archive - root directory is clean!")
        return False

    print(f"Found {total_files} files to archive:\n")

    # Display CSV files
    if plan["csv"]:
        print("CSV FILES:")
        for category, files in sorted(plan["csv"].items()):
            if files:
                print(f"  → {ARCHIVE_BASE / 'csv' / category}/")
                for f in sorted(files):
                    print(f"    • {f.name}")
        print()

    # Display PNG files
    if plan["png"]:
        print("PNG FILES:")
        for category, files in sorted(plan["png"].items()):
            if files:
                print(f"  → {ARCHIVE_BASE / 'png' / category}/")
                for f in sorted(files):
                    print(f"    • {f.name}")
        print()

    # Display test Python files
    if plan["test_py"]:
        print("TEST PYTHON FILES:")
        for category, files in sorted(plan["test_py"].items()):
            if files:
                print(f"  → {ARCHIVE_BASE / 'test_scripts' / category}/")
                for f in sorted(files):
                    print(f"    • {f.name}")
        print()

    print("=" * 70)
    return True


def archive_files(plan):
    """Move files to their archive locations."""
    moved_count = 0
    failed_count = 0

    # Process CSV files
    for category, files in plan["csv"].items():
        if files:
            dest_dir = ARCHIVE_BASE / "csv" / category
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file_path in files:
                try:
                    dest = dest_dir / file_path.name
                    file_path.rename(dest)
                    print(f"✓ Moved: {file_path.name} → csv/{category}/")
                    moved_count += 1
                except Exception as e:
                    print(f"✗ Failed: {file_path.name} - {e}")
                    failed_count += 1

    # Process PNG files
    for category, files in plan["png"].items():
        if files:
            dest_dir = ARCHIVE_BASE / "png" / category
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file_path in files:
                try:
                    dest = dest_dir / file_path.name
                    file_path.rename(dest)
                    print(f"✓ Moved: {file_path.name} → png/{category}/")
                    moved_count += 1
                except Exception as e:
                    print(f"✗ Failed: {file_path.name} - {e}")
                    failed_count += 1

    # Process test Python files
    for category, files in plan["test_py"].items():
        if files:
            dest_dir = ARCHIVE_BASE / "test_scripts" / category
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file_path in files:
                try:
                    dest = dest_dir / file_path.name
                    file_path.rename(dest)
                    print(f"✓ Moved: {file_path.name} → test_scripts/{category}/")
                    moved_count += 1
                except Exception as e:
                    print(f"✗ Failed: {file_path.name} - {e}")
                    failed_count += 1

    print()
    print(f"✅ Successfully archived {moved_count} files")
    if failed_count > 0:
        print(f"❌ Failed to move {failed_count} files")
    print(f"📁 Archive location: {ARCHIVE_BASE}")
    print()
    print("=" * 70)


def main():
    """Main execution function."""
    print("Root Directory Cleanup Tool")
    print("=" * 70)
    print()

    # Organize and display plan
    plan = organize_files()
    has_files = display_plan(plan)

    if not has_files:
        return

    # Ask for confirmation
    response = input("Archive these files? (yes/no): ").strip().lower()

    if response == "yes":
        print()
        archive_files(plan)
    else:
        print("Cancelled - no files were moved.")


if __name__ == "__main__":
    main()
