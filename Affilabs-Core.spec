# -*- mode: python ; coding: utf-8 -*-

# Read version from VERSION file
with open('VERSION', 'r') as f:
    VERSION = f.read().strip()

# Find libusb DLL - check common locations
import os
import sys

# Common Python installation paths to check
libusb_dll = None
possible_paths = [
    # Python 3.9 Roaming
    os.path.expanduser(r'~\AppData\Roaming\Python\Python39\site-packages\libusb_package\libusb-1.0.dll'),
    # Python 3.9 Program Files
    r'C:\Program Files\Python39\Lib\site-packages\libusb_package\libusb-1.0.dll',
    # Python 3.12
    r'C:\Users\lucia\AppData\Local\Programs\Python\Python312\Lib\site-packages\libusb_package\libusb-1.0.dll',
]

for path in possible_paths:
    if os.path.exists(path):
        libusb_dll = path
        print(f"Found libusb DLL at: {path}")
        break

if not libusb_dll:
    print("WARNING: libusb-1.0.dll not found in expected locations")
    binaries = []
else:
    binaries = [(libusb_dll, '.')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('VERSION', '.'),
        ('affilabs/ui', 'affilabs/ui'),
        ('affilabs/config', 'affilabs/config'),
        ('affilabs/convergence/models', 'affilabs/convergence/models'),
        ('detector_profiles', 'detector_profiles'),
        ('led_calibration_official', 'led_calibration_official'),
        ('servo_polarizer_calibration', 'servo_polarizer_calibration'),
        ('settings', 'settings'),
        ('standalone_tools', 'standalone_tools'),
    ],
    hiddenimports=[
        'PySide6', 
        'pyqtgraph', 
        'scipy', 
        'scipy.special._cdflib',
        'numpy', 
        'seabreeze', 
        'seabreeze.cseabreeze', 
        'libusb_package', 
        'sklearn', 
        'joblib',
        'standalone_tools',
        'standalone_tools.compression_trainer_ui',
        'standalone_tools.compression_labeller',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pyqtgraph.opengl',  # We don't use OpenGL features
        'tkinter',  # We use PySide6, not tkinter
        'matplotlib.tests',  # Don't need test modules
        'scipy.tests',
        'numpy.tests',
        'pandas.tests',
        'sklearn.tests',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Affilabs-Core-v{VERSION}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui\\img\\affinite2.ico'],
)
