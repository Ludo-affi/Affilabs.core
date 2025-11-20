# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ezControl-AI
Usage: pyinstaller ezControl-AI.spec
"""

block_cipher = None

a = Analysis(
    ['main\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui', 'ui'),
        ('settings.py', '.'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtAsyncio',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.optimize',
        'seabreeze',
        'seabreeze.pyseabreeze',
        'serial',
        'pump_controller',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ezControl-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (windowed application)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui\\img\\affinite2.ico',
)
