"""Build script for creating ezControl executable
Run this with: python build_executable.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description, continue_on_error=False):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print("=" * 60)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=not continue_on_error,
            capture_output=False,
            text=True,
        )
        if result.returncode != 0 and not continue_on_error:
            print(f"ERROR: {description} failed!")
            return False
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        if not continue_on_error:
            return False
        return True


def main():
    """Main build process."""
    print("\n" + "=" * 60)
    print("ezControl Executable Builder")
    print("=" * 60)

    # Check we're in the right directory
    if not Path("main/main.py").exists():
        print("\nERROR: main/main.py not found!")
        print("Please run this script from the 'Old software' directory")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Get Python executable
    python_exe = sys.executable
    print(f"\nUsing Python: {python_exe}")

    # Step 1: Upgrade pip
    if not run_command(
        f'"{python_exe}" -m pip install --upgrade pip',
        "Step 1: Upgrading pip",
    ):
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Step 2: Install PyInstaller and Pillow
    if not run_command(
        f'"{python_exe}" -m pip install pyinstaller pillow',
        "Step 2: Installing build tools (PyInstaller, Pillow)",
    ):
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Step 3: Install core dependencies
    core_deps = ["pyqtgraph", "pyserial", "PySide6", "scipy", "numpy"]
    if not run_command(
        f'"{python_exe}" -m pip install {" ".join(core_deps)}',
        "Step 3: Installing core dependencies",
    ):
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Step 4: Try to install hardware packages (optional)
    hw_deps = ["pump-controller", "oceandirect", "ftd2xx"]
    run_command(
        f'"{python_exe}" -m pip install {" ".join(hw_deps)}',
        "Step 4: Installing hardware packages (optional)",
        continue_on_error=True,
    )

    # Step 5: Clean previous builds
    print("\n" + "=" * 60)
    print("Step 5: Cleaning previous builds")
    print("=" * 60)
    for folder in ["dist", "build"]:
        if Path(folder).exists():
            print(f"Removing {folder}/")
            import shutil

            shutil.rmtree(folder, ignore_errors=True)

    # Step 6: Build with PyInstaller
    if not run_command(
        f'"{python_exe}" -m PyInstaller main.spec',
        "Step 6: Building executable with PyInstaller",
    ):
        print("\n" + "=" * 60)
        print("BUILD FAILED!")
        print("=" * 60)
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Check if build succeeded
    exe_path = Path("dist/ezControl v3.4/ezControl.exe")
    print("\n" + "=" * 60)
    if exe_path.exists():
        print("BUILD SUCCESSFUL!")
        print("=" * 60)
        print(f"\nExecutable created at: {exe_path.absolute()}")
        print("\nYou can copy the entire 'dist\\ezControl v3.4' folder")
        print("to any Windows PC and run ezControl.exe")
    else:
        print("BUILD FAILED!")
        print("=" * 60)
        print("\nExecutable was not created. Check errors above.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
