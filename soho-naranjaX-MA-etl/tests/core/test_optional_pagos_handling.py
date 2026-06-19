from __future__ import annotations

from pathlib import Path
import sys
import importlib

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.modelos import ArchivosDia, ConfigDia

procesar_dia_module = importlib.import_module("core.procesar_dia")


def _build_config(tmp_path: Path) -> ConfigDia:
    return ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "salida",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )


def _patch_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("NARANJAX_PLANES_MIN_COVERAGE", "0")
    def _fake_pivot(*_args, **_kwargs):
        df = pd.DataFrame({"nroproducto": ["1001"]})
        df.attrs["input_plan_rows"] = 1
        df.attrs["max_plans"] = 0
        df.attrs["plan_columns"] = []
        return df

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", lambda *_args, **_kwargs: pd.DataFrame({"x": [1]}))
    monkeypatch.setattr(procesar_dia_module, "pivot_planes", _fake_pivot)
    monkeypatch.setattr(procesar_dia_module, "iter_planes_chunks", lambda *_args, **_kwargs: iter(()))
    monkeypatch.setattr(
        procesar_dia_module,
        "update_estado",
        lambda estado, _planes, df_pagos=None, logger=None: estado,
    )
    monkeypatch.setattr(
        procesar_dia_module,
        "aplicar_filtros",
        lambda estado, scope_cajones=None, logger=None: (estado, {"cajon_fuera_scope": 0}),
    )
    monkeypatch.setattr(procesar_dia_module, "transform", lambda df, **_kwargs: df)
    monkeypatch.setattr(procesar_dia_module, "sort_roman_rows", lambda df: df)
    monkeypatch.setattr(procesar_dia_module, "save_output", lambda *_args, **_kwargs: str(Path("dummy.csv")))
    monkeypatch.setattr(procesar_dia_module, "build_e1kia_output", lambda df: df)
    monkeypatch.setattr(
        procesar_dia_module,
        "guardar_estado",
        lambda *_args, **_kwargs: (str(Path("estado_vigente.csv")), str(Path("estado_snapshot.csv"))),
    )
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])


def test_repro_residual_pagos_autodetected_when_enabled(monkeypatch, tmp_path: Path) -> None:
    pagos_residual = tmp_path / "pagos_residual.csv"
    pagos_residual.write_text("nroproducto;otro\n1001;X\n", encoding="utf-8")
    base = tmp_path / "base.xlsx"
    base.write_text("base", encoding="utf-8")
    planes = tmp_path / "planes.xlsx"
    planes.write_text("planes", encoding="utf-8")

    _patch_happy_path(monkeypatch)
    monkeypatch.setattr(
        procesar_dia_module,
        "load_pagos",
        lambda _path: (_ for _ in ()).throw(ValueError("Unsupported PAGOS format: could not map required columns nroproducto")),
    )

    archivos = ArchivosDia(
        fecha="20260505",
        mes="202605",
        input_base=base,
        diarios_dir=tmp_path,
        planes=planes,
        pagos=None,
        usar_pagos=True,
        autodetect_planes=True,
        autodetect_pagos=True,
    )

    resultado = procesar_dia_module.procesar_dia(_build_config(tmp_path), archivos)

    assert resultado.status == "error"
    assert resultado.errores
    assert "Unsupported PAGOS format" in resultado.errores[0]


def test_skips_residual_pagos_when_not_selected_even_if_autodetect_enabled(monkeypatch, tmp_path: Path, caplog) -> None:
    pagos_residual = tmp_path / "pagos_residual.csv"
    pagos_residual.write_text("nroproducto;otro\n1001;X\n", encoding="utf-8")
    base = tmp_path / "base.xlsx"
    base.write_text("base", encoding="utf-8")
    planes = tmp_path / "planes.xlsx"
    planes.write_text("planes", encoding="utf-8")

    _patch_happy_path(monkeypatch)
    monkeypatch.setattr(
        procesar_dia_module,
        "load_pagos",
        lambda _path: (_ for _ in ()).throw(AssertionError("load_pagos should not be called")),
    )

    archivos = ArchivosDia(
        fecha="20260505",
        mes="202605",
        input_base=base,
        diarios_dir=tmp_path,
        planes=planes,
        pagos=None,
        usar_pagos=False,
        autodetect_planes=False,
        autodetect_pagos=True,
    )

    caplog.set_level("INFO", logger="core.procesar_dia")
    resultado = procesar_dia_module.procesar_dia(_build_config(tmp_path), archivos)

    assert resultado.status == "success"
    assert any("PAGOS omitted by user; skipping" in rec.message for rec in caplog.records)
