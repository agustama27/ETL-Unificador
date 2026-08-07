# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


BLOCK_CIPHER = None
PROJECT_ROOT = Path(SPECPATH).parent

hiddenimports = []
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("back_base_etl")
hiddenimports += collect_submodules("back_resultados_etl")

datas = []
assets_dir = PROJECT_ROOT / "packaging" / "assets"
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

a = Analysis(
    [str(PROJECT_ROOT / "naranjax_etl.py")],
    pathex=[
        str(PROJECT_ROOT),
        str(PROJECT_ROOT / "back-base"),
        str(PROJECT_ROOT / "back-resultados"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "test", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="naranjax_etl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
