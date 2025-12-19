# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('.venv312/Lib/site-packages/libusb_package/libusb-1.0.dll', '.')],
    datas=[
        ('affilabs/ui', 'affilabs/ui'),
        ('affilabs/config', 'affilabs/config'),
        ('detector_profiles', 'detector_profiles'),
        ('led_calibration_official', 'led_calibration_official'),
        ('servo_polarizer_calibration', 'servo_polarizer_calibration'),
        ('settings', 'settings')
    ],
    hiddenimports=['PySide6', 'pyqtgraph', 'scipy', 'numpy', 'seabreeze', 'seabreeze.cseabreeze', 'libusb_package'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Affilabs-Core',
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
