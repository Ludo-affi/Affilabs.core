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
        ('affilabs/utils/Sensor64bit.dll', 'affilabs/utils'),
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
        'tinydb',
        'pydantic',
        'pandas',
        'requests',
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

# Filter out dev/test artifacts from bundled data to reduce .exe size
# These patterns match against the destination path inside the bundle
_exclude_patterns = [
    'servo_polarizer_calibration/test_data',       # ~916KB dev analysis PNGs/CSVs
    'servo_polarizer_calibration/README',           # dev docs
    'servo_polarizer_calibration/requirements',     # dev deps
    'standalone_tools/compression_training_data',   # ~3.1MB training data (generated at runtime)
    'standalone_tools/README',                      # dev docs
    'led_calibration_official/1_create_model',      # OEM-only scripts
    'led_calibration_official/2_test_model',        # OEM-only scripts
    'led_calibration_official/apply_corrections',   # OEM-only scripts
    'led_calibration_official/test_corrections',    # OEM-only scripts
    'led_calibration_official/CALIBRATION_UPDATES', # dev docs
]
a.datas = [d for d in a.datas
           if not any(pat in d[0] for pat in _exclude_patterns)]

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui\\img\\affinite2.ico'],
)
