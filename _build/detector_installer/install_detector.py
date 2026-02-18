"""
Phase Photonics ST00012 Detector Installer
==========================================

This script installs the Phase Photonics detector support files into a target workspace.

Usage:
    python install_detector.py [target_directory]
    
If no target directory is specified, it will install to the current working directory.

Files installed:
    - utils/Sensor64bit.dll         (Native driver library)
    - utils/phase_photonics_wrapper.py  (Python API wrapper)
    - utils/__init__.py             (Package init if needed)
"""

import sys
import shutil
from pathlib import Path


# Installation configuration
INSTALLER_DIR = Path(__file__).parent
FILES_TO_INSTALL = [
    ("Sensor64bit.dll", "utils/Sensor64bit.dll"),
    ("phase_photonics_wrapper.py", "utils/phase_photonics_wrapper.py"),
]


def create_init_file(target_utils_dir: Path):
    """Create or update __init__.py in the utils directory."""
    init_file = target_utils_dir / "__init__.py"

    import_line = "from .phase_photonics_wrapper import SpectrometerAPI"

    if init_file.exists():
        content = init_file.read_text()
        if import_line not in content:
            # Append import to existing file
            with open(init_file, 'a') as f:
                f.write(f"\n# Phase Photonics Detector Support\n{import_line}\n")
            print(f"  Updated: {init_file}")
        else:
            print(f"  Skipped: {init_file} (already contains import)")
    else:
        # Create new init file
        content = f'''"""Utils package with Phase Photonics detector support."""

# Phase Photonics Detector Support
{import_line}
'''
        init_file.write_text(content)
        print(f"  Created: {init_file}")


def install_detector(target_dir: Path):
    """Install detector files to target directory."""
    print("=" * 60)
    print("Phase Photonics ST00012 Detector Installer")
    print("=" * 60)
    print()

    # Validate target directory
    if not target_dir.exists():
        print(f"Creating target directory: {target_dir}")
        target_dir.mkdir(parents=True)

    target_utils_dir = target_dir / "utils"
    if not target_utils_dir.exists():
        print(f"Creating utils directory: {target_utils_dir}")
        target_utils_dir.mkdir(parents=True)

    print()
    print("Installing files...")
    print("-" * 40)

    # Install each file
    for src_name, dest_rel_path in FILES_TO_INSTALL:
        src_path = INSTALLER_DIR / src_name
        dest_path = target_dir / dest_rel_path

        if not src_path.exists():
            print(f"  ERROR: Source file not found: {src_path}")
            continue

        # Create destination directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(src_path, dest_path)
        print(f"  Installed: {dest_rel_path}")

    # Create/update __init__.py
    print()
    print("Configuring package...")
    print("-" * 40)
    create_init_file(target_utils_dir)

    print()
    print("=" * 60)
    print("Installation Complete!")
    print("=" * 60)
    print()
    print("Usage example:")
    print("-" * 40)
    print("""
from utils.phase_photonics_wrapper import SpectrometerAPI

# Initialize API
api = SpectrometerAPI("./utils/Sensor64bit.dll")

# Connect to detector
handle = api.usb_initialize("ST00012")

# Set integration time (microseconds)
api.usb_set_interval(handle, 10000)

# Set averaging (number of scans)
api.usb_set_averaging(handle, 1)

# Read spectrum
ret, spectrum = api.usb_read_pixels(handle)

# Disconnect
api.usb_deinit(handle)
""")
    print()
    print("Calibration coefficients for ST00012:")
    print("  [536.2118491060357, 0.10261733564399202,")
    print("   2.947529336201839e-06, -4.848287053280828e-09]")
    print()


def main():
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).resolve()
    else:
        target_dir = Path.cwd()

    print(f"Target directory: {target_dir}")
    print()

    # Confirm installation
    response = input("Proceed with installation? [Y/n]: ").strip().lower()
    if response and response != 'y':
        print("Installation cancelled.")
        return

    print()
    install_detector(target_dir)


if __name__ == "__main__":
    main()
