# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs
import os

block_cipher = None

# Build list of data files, only including files that exist
datas = [("main.spec", "."), ("VERSION", ".")]
if os.path.exists("affinite_ezspr.uf2"):
    datas.append(("affinite_ezspr.uf2", "."))

a = Analysis(
    ["main/main.py"],
    pathex=[],
    binaries=collect_dynamic_libs("utils"),
    datas=datas,
    hiddenimports=['afterglow_correction'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

splash = Splash(
    "ui/img/affinite-splash.png",
    binaries=a.binaries,
    datas=a.datas,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    exclude_binaries=True,
    name='ezControl',
    icon='ui/img/affinite2.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    splash.binaries,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ezControl v4.0',
    key='Aff1nit3$oftw@re',
)
