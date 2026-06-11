# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the XRF Correction Factor Tool (Windows, one-folder).

Build from the project root (xrf_tool/) with:
    pyinstaller packaging/XRF-CF-Tool.spec --noconfirm
"""

block_cipher = None

# PyInstaller's bundled hooks already pull in everything scipy / openpyxl / numpy /
# matplotlib need at runtime, so we don't collect_submodules (which would also drag
# in their test suites and bloat the build).
hiddenimports = []

a = Analysis(
    ["..\\main.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim heavy, unused modules to keep the bundle smaller / build faster.
    excludes=[
        "tkinter", "pandas", "pytest",
        "scipy.stats.tests", "numpy.tests", "scipy.spatial.tests",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.QtNetwork", "PySide6.QtBluetooth",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XRF-CF-Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # windowed app, no console
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
    upx=False,
    upx_exclude=[],
    name="XRF-CF-Tool",
)
