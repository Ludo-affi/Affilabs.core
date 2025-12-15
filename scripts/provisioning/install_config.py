#!/usr/bin/env python3
"""Customer Device Configuration Installer

Automatically installs device configuration from USB drive to customer's computer.
Run this script from the USB drive that came with your Affinité SPR device.

Author: AI Assistant
Date: October 11, 2025
Version: 1.0

Usage:
    python install_config.py
"""

from __future__ import annotations

import glob
import shutil
import sys
from pathlib import Path


def print_header():
    """Print installer header."""
    print("\n" + "=" * 70)
    print("  Affinité ezControl - Configuration Installer")
    print("  Version 1.0")
    print("=" * 70)
    print()


def find_config_file() -> Path | None:
    """Find device configuration file in current directory."""
    # Look for device_config_*.json
    configs = glob.glob("device_config_*.json")
    if configs:
        return Path(configs[0])

    # Also check for generic name
    generic = Path("device_config.json")
    if generic.exists():
        return generic

    return None


def find_calibration_files() -> list[Path]:
    """Find factory calibration files."""
    calib_files = []

    # Look for calibration files
    patterns = [
        "factory_calibration_*.npz",
        "*_dark.npz",
        "*_reference.npz",
    ]

    for pattern in patterns:
        for file in glob.glob(pattern):
            calib_files.append(Path(file))

    return calib_files


def get_install_directory() -> Path:
    """Determine installation directory based on platform."""
    if sys.platform == "win32":
        # Windows: %USERPROFILE%\ezControl\config
        install_dir = Path.home() / "ezControl" / "config"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/ezControl/config
        install_dir = (
            Path.home() / "Library" / "Application Support" / "ezControl" / "config"
        )
    else:
        # Linux: ~/.ezcontrol/config
        install_dir = Path.home() / ".ezcontrol" / "config"

    return install_dir


def install_configuration(config_file: Path, install_dir: Path) -> bool:
    """Install configuration file."""
    try:
        # Create directory if needed
        install_dir.mkdir(parents=True, exist_ok=True)

        # Destination file
        dest_file = install_dir / "device_config.json"

        # Copy file
        shutil.copy2(config_file, dest_file)

        print(f"✅ Configuration installed: {dest_file}")
        return True

    except Exception as e:
        print(f"❌ Failed to install configuration: {e}")
        return False


def install_calibration_files(calib_files: list[Path], install_dir: Path) -> int:
    """Install calibration files."""
    installed = 0

    try:
        # Create directory if needed
        install_dir.mkdir(parents=True, exist_ok=True)

        for calib_file in calib_files:
            dest_file = install_dir / calib_file.name
            shutil.copy2(calib_file, dest_file)
            print(f"✅ Calibration installed: {calib_file.name}")
            installed += 1

        return installed

    except Exception as e:
        print(f"❌ Failed to install calibration: {e}")
        return installed


def main():
    """Main installation workflow."""
    try:
        print_header()

        print("This installer will set up your ezControl device configuration.")
        print("Please ensure you are running this from the USB drive.")
        print()

        # Step 1: Find configuration file
        print("🔍 Searching for configuration file...")
        config_file = find_config_file()

        if not config_file:
            print("❌ ERROR: Configuration file not found!")
            print()
            print("Please ensure:")
            print("  1. You are running this script from the USB drive")
            print("  2. The USB drive contains a file named device_config_*.json")
            print()
            input("Press Enter to exit...")
            return 1

        print(f"✅ Found configuration: {config_file.name}")
        print()

        # Step 2: Find calibration files
        print("🔍 Searching for calibration files...")
        calib_files = find_calibration_files()

        if calib_files:
            print(f"✅ Found {len(calib_files)} calibration file(s)")
            for file in calib_files:
                print(f"   • {file.name}")
        else:
            print("⚠️  No calibration files found (this is optional)")
        print()

        # Step 3: Determine installation directory
        install_dir = get_install_directory()
        print(f"📁 Installation directory: {install_dir}")
        print()

        # Step 4: Confirm installation
        response = input("Ready to install. Continue? (Y/n): ").strip().lower()
        if response and response != "y":
            print("\n❌ Installation cancelled by user")
            return 0

        print()
        print("=" * 70)
        print("  INSTALLING...")
        print("=" * 70)
        print()

        # Step 5: Install configuration
        if not install_configuration(config_file, install_dir):
            print("\n❌ Installation failed")
            input("Press Enter to exit...")
            return 1

        # Step 6: Install calibration files
        if calib_files:
            installed_count = install_calibration_files(calib_files, install_dir)
            if installed_count > 0:
                print(f"✅ Installed {installed_count} calibration file(s)")

        # Success
        print()
        print("=" * 70)
        print("  ✅ INSTALLATION COMPLETE!")
        print("=" * 70)
        print()
        print("Configuration installed to:")
        print(f"  {install_dir}")
        print()
        print("Next steps:")
        print("  1. Remove the USB drive (optional)")
        print("  2. Launch ezControl application")
        print("  3. Your device should be ready to use!")
        print()

        # Show what was installed
        print("Installed files:")
        print("  • device_config.json")
        for file in calib_files:
            print(f"  • {file.name}")
        print()

        input("Press Enter to exit...")
        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Installation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Installation failed: {e}")
        import traceback

        traceback.print_exc()
        input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
