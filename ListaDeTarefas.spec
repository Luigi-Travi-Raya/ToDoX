# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["backend/main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ("frontend/dist", "frontend/dist"),
        ("assets/branding", "assets/branding"),
    ],
    hiddenimports=["pynput.keyboard._win32", "pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ToDoX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/branding/todox.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ToDoX",
)
