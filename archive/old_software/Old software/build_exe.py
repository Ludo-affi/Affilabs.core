"""Build script to create executable for ezControl-AI software."""
import PyInstaller.__main__
import sys
from pathlib import Path

# Get the directory containing this script
script_dir = Path(__file__).parent

# Define paths
main_script = str(script_dir / "main" / "main.py")
icon_file = str(script_dir / "ui" / "img" / "affinite2.ico")

# PyInstaller arguments
args = [
    main_script,
    '--name=ezControl-AI',
    '--windowed',  # No console window
    '--onefile',   # Single executable file
    f'--icon={icon_file}',
    '--add-data=ui;ui',  # Include UI files
    '--add-data=settings.py;.',  # Include settings
    '--hidden-import=PySide6',
    '--hidden-import=pyqtgraph',
    '--hidden-import=numpy',
    '--hidden-import=scipy',
    '--hidden-import=seabreeze',
    '--hidden-import=serial',
    '--hidden-import=pump_controller',
    '--collect-all=PySide6',
    '--collect-all=pyqtgraph',
    '--noconfirm',  # Replace output directory without asking
    '--clean',  # Clean cache before building
]

print("Building ezControl-AI executable...")
print(f"Main script: {main_script}")
print(f"Icon: {icon_file}")
print("\nThis may take several minutes...")

PyInstaller.__main__.run(args)

print("\n✓ Build complete!")
print(f"Executable location: {script_dir / 'dist' / 'ezControl-AI.exe'}")
