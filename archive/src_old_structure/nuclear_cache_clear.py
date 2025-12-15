#!/usr/bin/env python3
"""Force complete Python cache clear and module reload"""

import os
import shutil

# Remove all __pycache__ directories
count_dirs = 0
count_files = 0

for root, dirs, files in os.walk(r"c:\Users\ludol\ezControl-AI"):
    # Remove .pyc files
    for file in files:
        if file.endswith(".pyc"):
            try:
                os.remove(os.path.join(root, file))
                count_files += 1
            except:
                pass

    # Remove __pycache__ directories
    for dir in dirs:
        if dir == "__pycache__":
            try:
                shutil.rmtree(os.path.join(root, dir))
                count_dirs += 1
            except:
                pass

print(f"✅ Removed {count_files} .pyc files")
print(f"✅ Removed {count_dirs} __pycache__ directories")
print("\n⚠️  CRITICAL: You MUST restart the Python process!")
print("   Close the application completely and start fresh")
print("   Run: python -B main_simplified.py")
