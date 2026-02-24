# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Project root is one level above the _build/ directory that contains this spec.
# SPECPATH is injected by PyInstaller and equals the directory of the .spec file.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Read version from VERSION file
with open(os.path.join(PROJECT_ROOT, 'VERSION'), 'r') as f:
    VERSION = f.read().strip()

# Find libusb DLL - check common locations

# Find libusb DLL — prefer venv site-packages, then common system paths
libusb_dll = None

# Try to find via installed libusb_package (works for venv and system installs)
try:
    import libusb_package as _lp
    _candidate = os.path.join(os.path.dirname(_lp.__file__), 'libusb-1.0.dll')
    if os.path.exists(_candidate):
        libusb_dll = _candidate
except Exception:
    pass

if not libusb_dll:
    # Fallback: well-known install locations
    possible_paths = [
        os.path.expanduser(r'~\AppData\Local\Programs\Python\Python312\Lib\site-packages\libusb_package\libusb-1.0.dll'),
        os.path.expanduser(r'~\AppData\Local\Programs\Python\Python311\Lib\site-packages\libusb_package\libusb-1.0.dll'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            libusb_dll = path
            break

if not libusb_dll:
    print("WARNING: libusb-1.0.dll not found — USB spectrometer support will be unavailable")
    binaries = []
else:
    print(f"Found libusb DLL at: {libusb_dll}")
    binaries = [(libusb_dll, '.')]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=[
        (os.path.join(PROJECT_ROOT, 'VERSION'), '.'),
        (os.path.join(PROJECT_ROOT, 'affilabs/ui'), 'affilabs/ui'),
        (os.path.join(PROJECT_ROOT, 'affilabs/config'), 'affilabs/config'),
        (os.path.join(PROJECT_ROOT, 'affilabs/data'), 'affilabs/data'),  # Knowledge base, Spark AI data
        (os.path.join(PROJECT_ROOT, 'affilabs/convergence/models'), 'affilabs/convergence/models'),
        (os.path.join(PROJECT_ROOT, 'affilabs/utils/Sensor64bit.dll'), 'affilabs/utils'),
        (os.path.join(PROJECT_ROOT, 'detector_profiles'), 'detector_profiles'),
        (os.path.join(PROJECT_ROOT, 'led_calibration_official'), 'led_calibration_official'),
        (os.path.join(PROJECT_ROOT, 'settings'), 'settings'),
        (os.path.join(PROJECT_ROOT, 'data'), 'data'),  # Spark tips, QA history, runtime data
        # Piper TTS (if exists) - optional for Spark voice
        # (os.path.join(PROJECT_ROOT, 'piper'), 'piper'),  # Uncomment if you have Piper TTS installed
    ],
    hiddenimports=(
        collect_submodules('affilabs') +
        collect_submodules('AffiPump') +
        collect_submodules('mixins') +
        collect_submodules('settings') +
    [
        # Only compression_trainer_ui is imported from standalone_tools (calibration_service.py)
        'standalone_tools',
        'standalone_tools.compression_trainer_ui',
        # Root-level modules
        'affilabs.ui_styles',
        'affilabs.dialogs',
        'affilabs.dialogs.device_config_dialog',
        'PySide6',
        'pyqtgraph',
        'scipy',
        'scipy.special._cdflib',
        'numpy',
        'serial',
        'serial.tools.list_ports',
        'seabreeze',
        'seabreeze.cseabreeze',
        'libusb_package',
        'sklearn',
        'joblib',
        'tinydb',
        'tinydb.queries',
        'tinydb.table',
        'tinydb.storages',
        'pydantic',
        'pandas',
        'requests',
        # Spark AI dependencies
        'affilabs.services.spark',
        'affilabs.services.spark.answer_engine',
        'affilabs.services.spark.pattern_matcher',
        'affilabs.services.spark.knowledge_base',
        'affilabs.services.spark.tinylm',
        'affilabs.services.spark.patterns',
        # cffi - needed by some serial/USB libs
        '_cffi_backend',
    ]),
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
        # TinyLM removed — exclude to prevent accidental bundling
        'torch', 'torchvision', 'torchaudio',
        'transformers', 'tokenizers', 'datasets',
        'huggingface_hub', 'safetensors',
        'sounddevice',
    ],
    noarchive=False,
    optimize=0,
)

# Filter out dev/test artifacts from bundled data to reduce .exe size
# These patterns match against the destination path inside the bundle
_exclude_patterns = [
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(PROJECT_ROOT, 'affilabs', 'ui', 'img', 'affinite2.ico')],
)
