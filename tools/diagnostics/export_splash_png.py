"""Export the Affilabs.core splash screen to a PNG file.

Usage:
    .venv/Scripts/python.exe tools/diagnostics/export_splash_png.py
    .venv/Scripts/python.exe tools/diagnostics/export_splash_png.py --out _data/splash.png
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from affilabs.utils.splash_screen import create_splash_screen

parser = argparse.ArgumentParser(description="Export splash screen to PNG")
parser.add_argument("--out", default="_data/splash_export.png", help="Output PNG path")
args = parser.parse_args()

out_path = Path(args.out)
out_path.parent.mkdir(parents=True, exist_ok=True)

_, pixmap, _ = create_splash_screen()
saved = pixmap.save(str(out_path), "PNG")

if saved:
    print(f"Saved: {out_path.resolve()}")
else:
    print("ERROR: pixmap.save() returned False — check path/permissions", file=sys.stderr)
    sys.exit(1)
