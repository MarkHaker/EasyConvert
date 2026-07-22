# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for EasyConvert.
# Portable: uses SPECPATH (the directory containing this .spec file),
# so it works for anyone who clones the repo and places ffmpeg.exe / ffprobe.exe
# next to the script.
#
# Build with:
#   pyinstaller --noconfirm --windowed --onefile ogg_to_mp3.spec
#
# Requirements next to this file: ogg_to_mp3.py, ico.ico, ffmpeg.exe, ffprobe.exe

import os
from PyInstaller.utils.hooks import collect_all

spec_dir = SPECPATH  # noqa: F821 (defined by PyInstaller)
script = os.path.join(spec_dir, 'ogg_to_mp3.py')
icon = os.path.join(spec_dir, 'ico.ico')

datas = []
binaries = [
    (os.path.join(spec_dir, 'ffmpeg.exe'), '.'),
    (os.path.join(spec_dir, 'ffprobe.exe'), '.'),
]
hiddenimports = []

for pkg in ('tkinterdnd2', 'imageio_ffmpeg', 'pydub'):
    tmp = collect_all(pkg)
    datas += tmp[0]
    binaries += tmp[1]
    hiddenimports += tmp[2]


a = Analysis(
    [script],
    pathex=[spec_dir],
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
    name='ogg_to_mp3',
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
    icon=[icon],
)
