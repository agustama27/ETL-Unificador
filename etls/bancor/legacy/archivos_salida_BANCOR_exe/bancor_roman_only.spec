# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve().parent
back_resultados_procesos = project_root / "back-resultados" / "procesos"
back_carga_procesos = project_root / "back-cargaMasiva" / "procesos"


a = Analysis(
    ['main.py'],
    pathex=[
        '.',
        str(back_resultados_procesos),
        str(back_carga_procesos),
    ],
    binaries=[],
    datas=[],
    hiddenimports=[
        'ui.app',
        'procesos.pipeline_roman_only',
        'roman_manager',
        'retell_manager',
        'config_roman',
        'mapeador',
        'validador',
        'excel_generator',
        'config_catalogos',
        'logcall_manager',
    ],
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
    name='Resultados_BANCOR',
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
