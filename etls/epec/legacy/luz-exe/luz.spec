# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path.cwd()
back_resultados_dir = (project_dir / ".." / "back-resultados").resolve()


a = Analysis(
    ['main.py'],
    pathex=[str(project_dir), str(back_resultados_dir)],
    binaries=[],
    datas=[],
    hiddenimports=['procesos', 'procesos.logcall_consolidator'],
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
    name='luz',
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
)
