# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Nazzil.

Build:    pyinstaller nazzil.spec
Output:   dist/Nazzil.exe

Version is read from the VERSION file (single source of truth — same file
that config.py and installer.iss read).
"""

import glob
import os

block_cipher = None

# SPECPATH is provided by PyInstaller and points at the directory of THIS file.
try:
    _here = SPECPATH  # noqa: F821 (provided by PyInstaller)
except NameError:
    _here = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_here, "VERSION"), "r", encoding="utf-8") as _vf:
    APP_VERSION = _vf.read().strip()

# ---- Build the datas list ----
_datas = [
    ('VERSION',         '.'),       # bundled at the root of _MEIPASS
    ('assets/icon.png', 'assets'),
    ('assets/icon.ico', 'assets'),
    ('i18n/ar.json',    'i18n'),
    ('i18n/en.json',    'i18n'),
]

# Bundle every .ttf / .otf dropped into assets/fonts/ so the custom
# ThmanyahSans face is available in the frozen build. The folder is
# created at dev-time; if it's empty we just skip the entries.
_fonts_dir = os.path.join(_here, "assets", "fonts")
if os.path.isdir(_fonts_dir):
    for _font in (glob.glob(os.path.join(_fonts_dir, "*.ttf"))
                  + glob.glob(os.path.join(_fonts_dir, "*.otf"))):
        _datas.append((_font, os.path.join("assets", "fonts")))


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        'yt_dlp',
        'yt_dlp.extractor',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
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
    name='Nazzil',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version_file=None,
)
