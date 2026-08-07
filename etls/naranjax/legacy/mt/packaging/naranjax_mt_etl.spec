import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPECPATH).parent
BACK_RESULTADOS_ROOT = PROJECT_ROOT / "back-resultados"
APP_ICON = os.environ.get("APP_ICON", "")
VERSION_FILE = os.environ.get("APP_VERSION_FILE", "")

hiddenimports = []
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("procesos")
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("ui")
hiddenimports += collect_submodules("cli")
if BACK_RESULTADOS_ROOT.exists():
    hiddenimports += collect_submodules("back_resultados_etl", [str(BACK_RESULTADOS_ROOT)])

datas = []
assets = PROJECT_ROOT / "packaging" / "assets"
if assets.exists():
    datas.append((str(assets), "assets"))


a = Analysis(
    [str(PROJECT_ROOT / "naranjax_mt_etl.py")],
    pathex=[str(PROJECT_ROOT), str(BACK_RESULTADOS_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="naranjax_mt_etl",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=APP_ICON if APP_ICON else None,
    version=VERSION_FILE if VERSION_FILE else None,
)
