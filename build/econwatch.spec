# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for EconWatch: onedir + windowed.

onedir (not onefile) so double-clicking starts instantly: onefile re-extracts
the whole ~57 MB bundle to %TEMP% on every launch, costing 5-10 seconds.
"""

import os

SRC = os.path.normpath(os.path.join(SPECPATH, "..", "src"))

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        "appconfig",
        "chart",
        "data_fetcher",
        "exporter",
        "gui",
        "matplotlib.backends.backend_agg",
        "fredapi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI is tkinter-based; keep tkinter but drop all other GUI toolkits
        # and interactive matplotlib backends
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends.backend_qt5agg",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_gtk3agg",
        "matplotlib.backends.backend_gtk4agg",
        "matplotlib.backends.backend_wxagg",
        "matplotlib.backends.backend_macosx",
        "matplotlib.backends.backend_nbagg",
        "matplotlib.backends.backend_webagg",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir: binaries/datas are collected below
    name="econwatch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed: double-clicking the exe pops no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="econwatch",
)
