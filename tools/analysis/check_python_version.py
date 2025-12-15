"""Python 3.12 Environment Verification Script
Run this to verify your environment is correctly set up for Python 3.12
"""

import sys
from pathlib import Path

print("=" * 60)
print("   Python 3.12 Environment Verification")
print("=" * 60)
print()

# Check Python version
print(f"Python Version: {sys.version}")
print(f"Python Executable: {sys.executable}")
print()

version_info = sys.version_info
major, minor = version_info.major, version_info.minor

# Verify Python 3.12+
if major == 3 and minor >= 12:
    print("✅ CORRECT: Python 3.12+ detected")
elif major == 3 and minor >= 11:
    print("⚠️  WARNING: Python 3.11 detected (should be 3.12)")
    print("   Most features will work but 3.12 is recommended")
else:
    print("❌ ERROR: Python version too old!")
    print(f"   Current: {major}.{minor}")
    print("   Required: 3.12+")
    print()
    print("   Please activate .venv312:")
    print("   .venv312\\Scripts\\Activate.ps1")
    sys.exit(1)

print()

# Check if we're in a virtual environment
in_venv = hasattr(sys, "real_prefix") or (
    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
)

if in_venv:
    print("✅ CORRECT: Running in virtual environment")
    venv_path = Path(sys.prefix)
    print(f"   Virtual Environment: {venv_path}")

    # Check if it's .venv312
    if ".venv312" in str(venv_path):
        print("✅ CORRECT: Using .venv312 environment")
    else:
        print("⚠️  WARNING: Not using .venv312")
        print(f"   Current venv: {venv_path.name}")
else:
    print("⚠️  WARNING: Not running in virtual environment")
    print("   It's recommended to use .venv312")

print()

# Test modern type hints
print("Testing Python 3.12 features...")
try:
    # This should work in Python 3.10+
    exec("def test(x: str | None) -> str | None: return x")
    print("✅ Modern type hints (|) work")
except TypeError as e:
    print(f"❌ Modern type hints failed: {e}")
    print("   This confirms Python version is too old")

# Test datetime.UTC (Python 3.11+)
try:
    from datetime import UTC

    print("✅ datetime.UTC available (Python 3.11+)")
except ImportError:
    print("⚠️  datetime.UTC not available (need Python 3.11+)")

print()
print("=" * 60)

if major == 3 and minor >= 12 and in_venv and ".venv312" in str(sys.prefix):
    print("   ✅ ENVIRONMENT FULLY VERIFIED - READY TO RUN!")
elif major == 3 and minor >= 12:
    print("   ⚠️  Python version OK but check virtual environment")
else:
    print("   ❌ ENVIRONMENT ISSUES DETECTED")
    print("   Run: .venv312\\Scripts\\Activate.ps1")

print("=" * 60)
print()

# Show recommended command to run app
if major == 3 and minor >= 12:
    print("To run the application:")
    print("   Option 1 (Windows):  run_app_312.bat")
    print("   Option 2 (PowerShell): .\\run_app_312.ps1")
    print("   Option 3 (Manual): python main\\main.py")
else:
    print("⚠️  ACTIVATE PYTHON 3.12 FIRST:")
    print("   .venv312\\Scripts\\Activate.ps1")
    print("   Then run: python main\\main.py")

print()
