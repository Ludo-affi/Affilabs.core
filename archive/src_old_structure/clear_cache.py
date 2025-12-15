"""Aggressive Python cache cleaner for development.
Run this if you're experiencing persistent cache issues.
"""

import shutil
from pathlib import Path


def clear_all_cache(root_dir="."):
    """Remove all Python cache files and directories."""
    root = Path(root_dir).resolve()

    removed_dirs = []
    removed_files = []

    print("🧹 Aggressive Cache Cleaner")
    print("=" * 60)
    print(f"Scanning: {root}")
    print()

    # Remove __pycache__ directories
    for pycache in root.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
            removed_dirs.append(str(pycache.relative_to(root)))
        except Exception as e:
            print(f"⚠️  Could not remove {pycache}: {e}")

    # Remove .pyc files
    for pyc in root.rglob("*.pyc"):
        try:
            pyc.unlink()
            removed_files.append(str(pyc.relative_to(root)))
        except Exception as e:
            print(f"⚠️  Could not remove {pyc}: {e}")

    # Remove .pyo files
    for pyo in root.rglob("*.pyo"):
        try:
            pyo.unlink()
            removed_files.append(str(pyo.relative_to(root)))
        except Exception as e:
            print(f"⚠️  Could not remove {pyo}: {e}")

    # Remove .pyd files (compiled extensions - be careful!)
    for pyd in root.rglob("*.pyd"):
        # Skip venv directories
        if ".venv" not in str(pyd) and "venv" not in str(pyd):
            try:
                pyd.unlink()
                removed_files.append(str(pyd.relative_to(root)))
            except Exception as e:
                print(f"⚠️  Could not remove {pyd}: {e}")

    print(f"✓ Removed {len(removed_dirs)} __pycache__ directories")
    print(f"✓ Removed {len(removed_files)} bytecode files")
    print()

    if removed_dirs or removed_files:
        print("Cache cleared successfully!")
    else:
        print("No cache files found (already clean)")

    return len(removed_dirs) + len(removed_files) > 0


if __name__ == "__main__":
    # Clear from current directory
    clear_all_cache()

    print()
    print("=" * 60)
    print("✅ Ready to run application with fresh imports")
    print()
    print("Run: python -B main_simplified.py")
