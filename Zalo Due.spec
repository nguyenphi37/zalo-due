# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

native_helpers = [
    (f'native/build/{arch}/{name}', f'native/build/{arch}')
    for arch in ('x86', 'x64')
    for name in ('DueHook.dll', 'DueLaunch.exe', 'DueProbe.exe')
]
for source, _ in native_helpers:
    if not Path(source).is_file() or Path(source).stat().st_size == 0:
        raise SystemExit(f'Missing or empty native helper: {source}')

datas = [
    ('app/ui', 'ui'),
    *native_helpers,
    ('assets/zalo.ico', 'assets'),
]
binaries = []
hiddenimports = []
for package in ('webview', 'pythonnet', 'clr_loader'):
    collected_datas, collected_binaries, collected_hidden = collect_all(package)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hidden


a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='Zalo Due',
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
    icon=['assets/zalo.ico'],
)
