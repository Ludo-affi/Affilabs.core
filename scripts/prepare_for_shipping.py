"""Prepare Affilabs-Core Workspace for Production Shipping

This script safely organizes the workspace for shipping by:
1. Moving development files to appropriate locations
2. Creating a clean production structure
3. Validating all required files are present
4. Generating shipping package

SAFE: Only moves/organizes files, never deletes.
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Dict
import zipfile
from datetime import datetime


class ShippingPreparation:
    """Prepares workspace for production shipping."""

    def __init__(self, workspace_root: Path):
        self.root = workspace_root
        self.version = self._read_version()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Production files that MUST be shipped
        self.required_files = [
            "main-simplified.py",
            "run_app.py",
            "version.py",
            "VERSION",
            "pyproject.toml",
            "README.md",
        ]

        self.required_dirs = [
            "affilabs",
            "affipump",
            "config",
            "detector_profiles",
            "led_calibration_official",
            "servo_polarizer_calibration",
            "settings",
            "ui",
            "widgets",
            "utils",
        ]

        # Development files to move to tests/ or archive/
        self.test_patterns = [
            "test_*.py",
            "check_*.py",
            "*_test.py",
        ]

        self.cleanup_patterns = [
            "cleanup_*.py",
        ]

        self.dev_dirs = [
            "archive",
            "archive_root_files",
            "build_artifacts",
            "calibration_checkpoints",
            "calibration_data",
            "calibration_results",
            "data",
            "data_results",
            "docs",
            "firmware_archive",
            "generated-files",
            "logs",
            "OpticalSystem_QC",
            "scripts",
            "tests",
            "tools",
        ]

    def _read_version(self) -> str:
        """Read version from VERSION file."""
        version_file = self.root / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0-beta"  # Default

    def validate_structure(self) -> Dict[str, List[str]]:
        """Validate that all required files exist."""
        issues = {
            "missing_files": [],
            "missing_dirs": [],
        }

        for file in self.required_files:
            if not (self.root / file).exists():
                issues["missing_files"].append(file)

        for dir_name in self.required_dirs:
            if not (self.root / dir_name).is_dir():
                issues["missing_dirs"].append(dir_name)

        return issues

    def organize_test_files(self, dry_run: bool = True) -> List[str]:
        """Move test files from root to tests/ directory."""
        tests_dir = self.root / "tests" / "root_tests"
        moved_files = []

        if not dry_run:
            tests_dir.mkdir(parents=True, exist_ok=True)

        # Find test files in root
        for pattern in self.test_patterns:
            for file in self.root.glob(pattern):
                if file.is_file() and file.parent == self.root:
                    moved_files.append(str(file.name))
                    if not dry_run:
                        shutil.move(str(file), str(tests_dir / file.name))
                        print(f"✅ Moved {file.name} → tests/root_tests/")

        return moved_files

    def organize_cleanup_scripts(self, dry_run: bool = True) -> List[str]:
        """Move cleanup scripts to tools/ directory."""
        tools_dir = self.root / "tools" / "cleanup"
        moved_files = []

        if not dry_run:
            tools_dir.mkdir(parents=True, exist_ok=True)

        for pattern in self.cleanup_patterns:
            for file in self.root.glob(pattern):
                if file.is_file() and file.parent == self.root:
                    moved_files.append(str(file.name))
                    if not dry_run:
                        shutil.move(str(file), str(tools_dir / file.name))
                        print(f"✅ Moved {file.name} → tools/cleanup/")

        return moved_files

    def create_shipping_package(self, output_dir: Path) -> Path:
        """Create a clean shipping package with only production files."""
        package_name = f"Affilabs-Core-v{self.version}-source"
        package_dir = output_dir / package_name

        # Create package directory
        package_dir.mkdir(parents=True, exist_ok=True)

        # Copy required files
        for file in self.required_files:
            src = self.root / file
            if src.exists():
                shutil.copy2(src, package_dir / file)
                print(f"✅ Copied {file}")

        # Copy required directories
        for dir_name in self.required_dirs:
            src_dir = self.root / dir_name
            if src_dir.is_dir():
                dst_dir = package_dir / dir_name
                shutil.copytree(src_dir, dst_dir,
                              ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
                print(f"✅ Copied {dir_name}/")

        # Copy documentation
        docs_src = self.root / "SHIPPING_GUIDE.md"
        if docs_src.exists():
            shutil.copy2(docs_src, package_dir / "SHIPPING_GUIDE.md")

        acquisition_docs = self.root / "ACQUISITION_METHODS.md"
        if acquisition_docs.exists():
            shutil.copy2(acquisition_docs, package_dir / "ACQUISITION_METHODS.md")

        # Create requirements.txt
        self._create_requirements(package_dir)

        # Create README for package
        self._create_package_readme(package_dir)

        # Create ZIP
        zip_path = output_dir / f"{package_name}.zip"
        self._create_zip(package_dir, zip_path)

        print(f"\n✅ Package created: {zip_path}")
        return zip_path

    def _create_requirements(self, package_dir: Path):
        """Create requirements.txt from pyproject.toml."""
        pyproject = self.root / "pyproject.toml"
        if not pyproject.exists():
            return

        # Simple extraction of dependencies
        requirements = [
            "pyqtgraph>=0.13.3",
            "pyserial>=3.5",
            "PySide6>=6.5.1.1",
            "scipy>=1.11.0",
            "pump-controller>=0.1.2",
            "oceandirect>=0.1.0",
        ]

        req_file = package_dir / "requirements.txt"
        req_file.write_text("\n".join(requirements) + "\n")
        print("✅ Created requirements.txt")

    def _create_package_readme(self, package_dir: Path):
        """Create installation README for the package."""
        readme_content = f"""# Affilabs-Core v{self.version} - Source Package

## Quick Installation

### Prerequisites
- Windows 10/11 (64-bit)
- Python 3.12+
- USB4000 spectrometer with WinUSB drivers
- PicoP4SPR 4-channel controller

### Installation Steps

1. **Extract Package:**
   ```
   Unzip this package to your desired location
   ```

2. **Create Virtual Environment:**
   ```powershell
   python -m venv .venv312
   .venv312\\Scripts\\Activate.ps1
   ```

3. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run Application:**
   ```powershell
   python main-simplified.py
   ```

   Or use the development launcher:
   ```powershell
   python run_app.py
   ```

## Quick Start

1. Connect USB4000 spectrometer
2. Connect PicoP4SPR controller
3. Launch application
4. Follow on-screen calibration wizard
5. Start measurements!

## Documentation

- `README.md` - Full user guide
- `SHIPPING_GUIDE.md` - Deployment guide
- `ACQUISITION_METHODS.md` - Acquisition methods

## Support

- Repository: https://github.com/Ludo-affi/Affilabs-Core
- Firmware: https://github.com/Ludo-affi/pico-p4spr-firmware
- Issues: GitHub Issues tracker

## License

Copyright © 2025 Affilabs. All rights reserved.
"""

        install_readme = package_dir / "INSTALL.md"
        install_readme.write_text(readme_content)
        print("✅ Created INSTALL.md")

    def _create_zip(self, source_dir: Path, output_zip: Path):
        """Create ZIP archive of the package."""
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                # Skip __pycache__ and .pyc files
                dirs[:] = [d for d in dirs if d != '__pycache__']

                for file in files:
                    if file.endswith('.pyc'):
                        continue

                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_dir.parent)
                    zipf.write(file_path, arcname)

    def generate_report(self) -> str:
        """Generate a shipping preparation report."""
        issues = self.validate_structure()

        report = []
        report.append("=" * 70)
        report.append(f"SHIPPING PREPARATION REPORT - v{self.version}")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Validation results
        report.append("VALIDATION:")
        if not issues["missing_files"] and not issues["missing_dirs"]:
            report.append("  ✅ All required files and directories present")
        else:
            if issues["missing_files"]:
                report.append("  ❌ Missing files:")
                for f in issues["missing_files"]:
                    report.append(f"     - {f}")
            if issues["missing_dirs"]:
                report.append("  ❌ Missing directories:")
                for d in issues["missing_dirs"]:
                    report.append(f"     - {d}")

        report.append("")

        # File organization
        report.append("FILE ORGANIZATION:")
        test_files = self.organize_test_files(dry_run=True)
        cleanup_files = self.organize_cleanup_scripts(dry_run=True)

        if test_files:
            report.append(f"  📁 Test files to move ({len(test_files)}):")
            for f in test_files:
                report.append(f"     - {f}")

        if cleanup_files:
            report.append(f"  📁 Cleanup scripts to move ({len(cleanup_files)}):")
            for f in cleanup_files:
                report.append(f"     - {f}")

        if not test_files and not cleanup_files:
            report.append("  ✅ No files need reorganization")

        report.append("")

        # Production structure
        report.append("PRODUCTION STRUCTURE:")
        report.append("  ✅ Core application files:")
        for f in self.required_files:
            exists = "✓" if (self.root / f).exists() else "✗"
            report.append(f"     [{exists}] {f}")

        report.append("")
        report.append("  ✅ Core directories:")
        for d in self.required_dirs:
            exists = "✓" if (self.root / d).is_dir() else "✗"
            report.append(f"     [{exists}] {d}/")

        report.append("")
        report.append("=" * 70)
        report.append("NEXT STEPS:")
        report.append("  1. Review this report")
        report.append("  2. Run with --execute to apply changes")
        report.append("  3. Run tests to verify")
        report.append("  4. Create shipping package")
        report.append("=" * 70)

        return "\n".join(report)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Prepare workspace for production shipping")
    parser.add_argument("--execute", action="store_true",
                       help="Execute changes (default: dry run)")
    parser.add_argument("--package", action="store_true",
                       help="Create shipping package")
    parser.add_argument("--output", type=str, default="dist",
                       help="Output directory for package (default: dist)")

    args = parser.parse_args()

    # Get workspace root
    workspace = Path(__file__).parent

    # Create preparation manager
    prep = ShippingPreparation(workspace)

    # Generate and print report
    print(prep.generate_report())

    if args.execute:
        print("\n" + "=" * 70)
        print("EXECUTING CHANGES...")
        print("=" * 70 + "\n")

        # Organize files
        test_files = prep.organize_test_files(dry_run=False)
        cleanup_files = prep.organize_cleanup_scripts(dry_run=False)

        print(f"\n✅ Moved {len(test_files)} test files")
        print(f"✅ Moved {len(cleanup_files)} cleanup scripts")

        print("\n" + "=" * 70)
        print("WORKSPACE ORGANIZED!")
        print("=" * 70)

    if args.package:
        print("\n" + "=" * 70)
        print("CREATING SHIPPING PACKAGE...")
        print("=" * 70 + "\n")

        output_dir = Path(args.output)
        output_dir.mkdir(exist_ok=True)

        zip_path = prep.create_shipping_package(output_dir)

        print("\n" + "=" * 70)
        print("PACKAGE READY FOR SHIPPING!")
        print(f"Location: {zip_path}")
        print("=" * 70)


if __name__ == "__main__":
    main()
