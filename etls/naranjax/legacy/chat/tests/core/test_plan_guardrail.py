from __future__ import annotations

from pathlib import Path
import sys
import importlib

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from core.modelos import ArchivosDia, ConfigDia

procesar_dia_module = importlib.import_module("core.procesar_dia")


def test_procesar_dia_flags_inconsistency_when_roman_drops_plan_data(monkeypatch, tmp_path: Path) -> None:
    base_df = pd.DataFrame(
        [
            {
                "nroproducto": "100",
                "nombre_apellido": "Cliente Uno",
                "dni": "30111222",
                "cajon": "M90",
                "deuda_total": 1000.0,
                "deuda_vencida": 100.0,
            }
        ]
    )
    planes_df = pd.DataFrame(
        [
            {
                "nroproducto": "100",
                "cajon_planes": "M90",
                "deuda_total_planes": 1000.0,
                "deuda_vencida_planes": 100.0,
                "plan_1_cuotas": "3",
                "plan_1_entrega": 100.0,
                "plan_1_cuota_mensual": 300.0,
            }
        ]
    )
    planes_df.attrs["plan_columns"] = ["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"]
    planes_df.attrs["excluded_nroproductos_can"] = []
    planes_df.attrs["input_plan_rows"] = 1
    planes_df.attrs["max_plans"] = 1

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", lambda *_args, **_kwargs: base_df.copy())
    monkeypatch.setattr(procesar_dia_module, "detectar_archivos_diarios", lambda *_args, **_kwargs: {"planes": None, "pagos": None, "no_reconocidos": []})
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "pivot_planes", lambda *_args, **_kwargs: planes_df.copy())
    monkeypatch.setattr(procesar_dia_module, "iter_planes_chunks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "guardar_estado", lambda *_args, **_kwargs: ("vigente.csv", "snapshot.csv"))
    monkeypatch.setattr(procesar_dia_module, "save_output", lambda *_args, **_kwargs: str(tmp_path / "roman.csv"))
    monkeypatch.setattr(procesar_dia_module, "aplicar_filtros", lambda df, **_kwargs: (df.copy(), {"cajon_fuera_scope": 0}))

    def _transform_with_empty_plans(df, plan_columns=None, output_columns_base=None, logger=None):
        output = pd.DataFrame({"nombre_cliente": ["Cliente Uno"]})
        for column in plan_columns or []:
            output[column] = ""
        return output

    monkeypatch.setattr(procesar_dia_module, "transform", _transform_with_empty_plans)

    config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    archivos = ArchivosDia(
        fecha="20260428",
        mes="202604",
        input_base=tmp_path / "base.xlsx",
        diarios_dir=tmp_path,
        planes=tmp_path / "planes.xlsx",
        pagos=None,
    )

    result = procesar_dia_module.procesar_dia(config=config, archivos=archivos)

    assert result.status == "error"
    assert result.errores
    assert "PLANES fail-fast" in result.errores[0] or "PLANES inconsistency detected" in result.errores[0]
