from __future__ import annotations

from pathlib import Path
import sys
import importlib

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from core.modelos import ArchivosDia, ConfigDia

procesar_dia_module = importlib.import_module("core.procesar_dia")


def test_procesar_dia_generates_roman_and_e1kia_outputs(monkeypatch, tmp_path: Path) -> None:
    base_df = pd.DataFrame([
        {
            "nroproducto": "100",
            "nombre_apellido": "Cliente Uno",
            "dni": "30111222",
            "cajon": "M90",
            "deuda_total": 1000.0,
            "deuda_vencida": 100.0,
            "telefono1": "5411",
            "telefono2": "54911",
            "telefono3": "5433",
            "telefono4": "",
            "email1": "",
            "email2": "",
            "email3": "",
            "deuda_vencida_tc": 0,
            "deuda_vencida_nd": 0,
            "total_vencida": 0,
            "deuda_total_tc": 0,
            "deuda_total_nd": 0,
            "estrategia": "M90",
            "asignacion": "Elite",
            "ecosistema": "PURO",
            "marca_plan": "SIN PLAN",
        }
    ])

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", lambda *_args, **_kwargs: base_df.copy())
    monkeypatch.setattr(procesar_dia_module, "detectar_archivos_diarios", lambda *_args, **_kwargs: {"planes": None, "pagos": None, "no_reconocidos": []})
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "guardar_estado", lambda *_args, **_kwargs: ("vigente.csv", "snapshot.csv"))
    monkeypatch.setattr(procesar_dia_module, "update_estado", lambda df, *_args, **_kwargs: df.copy())
    monkeypatch.setattr(procesar_dia_module, "aplicar_filtros", lambda df, **_kwargs: (df.copy(), {"cajon_fuera_scope": 0}))

    saved_calls: list[tuple[str, str, str]] = []

    def _save_output(df, output_dir, prefix, date_format="%Y%m%d", suffix=".csv"):
        saved_calls.append((prefix, date_format, suffix))
        filename = f"{prefix}dummy{suffix}"
        return str(Path(output_dir) / filename)

    monkeypatch.setattr(procesar_dia_module, "save_output", _save_output)

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
        planes=None,
        pagos=None,
    )

    result = procesar_dia_module.procesar_dia(config=config, archivos=archivos)

    assert result.status == "success"
    assert result.output_roman is not None
    assert result.output_e1kia is not None
    assert len(saved_calls) == 2
    assert saved_calls[0][0] == "NARANJAX_MA_ROMAN_"
    assert saved_calls[1] == ("NARANJAX_MA_E1KIA_", "%y%m%d", "_sinestrategia.csv")


def test_procesar_dia_inicio_mes_sin_diarios_generates_roman_and_initializes_state(monkeypatch, tmp_path: Path) -> None:
    base_df = pd.DataFrame([
        {
            "nroproducto": "100",
            "nombre_apellido": "Cliente Uno",
            "dni": "30111222",
            "cajon": "M90",
            "deuda_total": 1000.0,
            "deuda_vencida": 100.0,
            "telefono1": "5411",
            "telefono2": "54911",
            "telefono3": "5433",
            "telefono4": "",
            "email1": "",
            "email2": "",
            "email3": "",
            "deuda_vencida_tc": 0,
            "deuda_vencida_nd": 0,
            "total_vencida": 0,
            "deuda_total_tc": 0,
            "deuda_total_nd": 0,
            "estrategia": "M90",
            "asignacion": "Elite",
            "ecosistema": "PURO",
            "marca_plan": "SIN PLAN",
        }
    ])

    state_calls = {"initialized": 0, "cargar_estado_calls": 0}

    def _fake_cargar_estado(*_args, **_kwargs):
        state_calls["cargar_estado_calls"] += 1
        if state_calls["cargar_estado_calls"] == 1:
            raise FileNotFoundError("estado no existe")
        return base_df.copy()

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", _fake_cargar_estado)
    monkeypatch.setattr(procesar_dia_module, "load_input", lambda *_args, **_kwargs: base_df.copy())
    monkeypatch.setattr(
        procesar_dia_module,
        "inicializar_estado",
        lambda *_args, **_kwargs: state_calls.__setitem__("initialized", state_calls["initialized"] + 1),
    )
    monkeypatch.setattr(procesar_dia_module, "detectar_archivos_diarios", lambda *_args, **_kwargs: {"planes": None, "pagos": None, "no_reconocidos": []})
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "guardar_estado", lambda *_args, **_kwargs: ("vigente.csv", "snapshot.csv"))
    monkeypatch.setattr(procesar_dia_module, "update_estado", lambda df, *_args, **_kwargs: df.copy())
    monkeypatch.setattr(procesar_dia_module, "aplicar_filtros", lambda df, **_kwargs: (df.copy(), {"cajon_fuera_scope": 0}))

    saved_payloads: list[pd.DataFrame] = []

    def _save_output(df, output_dir, prefix, date_format="%Y%m%d", suffix=".csv"):
        saved_payloads.append(df.copy())
        filename = f"{prefix}dummy{suffix}"
        return str(Path(output_dir) / filename)

    monkeypatch.setattr(procesar_dia_module, "save_output", _save_output)

    config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    archivos = ArchivosDia(
        fecha="20260501",
        mes="202605",
        input_base=tmp_path / "base.xlsx",
        diarios_dir=tmp_path,
        planes=None,
        pagos=None,
        modo_sin_diarios=True,
    )

    result = procesar_dia_module.procesar_dia(config=config, archivos=archivos)

    assert result.status == "success"
    assert result.modo_ejecucion == "inicio_mes_sin_diarios"
    assert result.output_roman is not None
    assert state_calls["initialized"] == 1
    assert len(saved_payloads) >= 1
    roman_df = saved_payloads[0]
    assert "plan_1_cuotas" in roman_df.columns
    assert roman_df.filter(regex=r"^plan_").fillna("").astype(str).apply(lambda col: col.str.strip()).eq("").all().all()


def test_procesar_dia_rebuilds_empty_state_from_base(monkeypatch, tmp_path: Path) -> None:
    base_df = pd.DataFrame([
        {
            "nroproducto": "100",
            "nombre_apellido": "Cliente Uno",
            "dni": "30111222",
            "cajon": "M90",
            "deuda_total": 1000.0,
            "deuda_vencida": 100.0,
            "telefono1": "5411",
            "telefono2": "54911",
            "telefono3": "5433",
            "telefono4": "",
            "email1": "",
            "email2": "",
            "email3": "",
            "deuda_vencida_tc": 0,
            "deuda_vencida_nd": 0,
            "total_vencida": 0,
            "deuda_total_tc": 0,
            "deuda_total_nd": 0,
            "estrategia": "M90",
            "asignacion": "Elite",
            "ecosistema": "PURO",
            "marca_plan": "SIN PLAN",
        }
    ])

    state_calls = {"cargar_estado_calls": 0, "initialized": 0}

    def _fake_cargar_estado(*_args, **_kwargs):
        state_calls["cargar_estado_calls"] += 1
        if state_calls["cargar_estado_calls"] == 1:
            return pd.DataFrame()
        return base_df.copy()

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", _fake_cargar_estado)
    monkeypatch.setattr(procesar_dia_module, "load_input", lambda *_args, **_kwargs: base_df.copy())
    monkeypatch.setattr(
        procesar_dia_module,
        "inicializar_estado",
        lambda *_args, **_kwargs: state_calls.__setitem__("initialized", state_calls["initialized"] + 1),
    )
    monkeypatch.setattr(procesar_dia_module, "detectar_archivos_diarios", lambda *_args, **_kwargs: {"planes": None, "pagos": None, "no_reconocidos": []})
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "guardar_estado", lambda *_args, **_kwargs: ("vigente.csv", "snapshot.csv"))
    monkeypatch.setattr(procesar_dia_module, "update_estado", lambda df, *_args, **_kwargs: df.copy())
    monkeypatch.setattr(procesar_dia_module, "aplicar_filtros", lambda df, **_kwargs: (df.copy(), {"cajon_fuera_scope": 0}))
    monkeypatch.setattr(
        procesar_dia_module,
        "save_output",
        lambda _df, output_dir, prefix, date_format="%Y%m%d", suffix=".csv": str(Path(output_dir) / f"{prefix}dummy{suffix}"),
    )

    config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    archivos = ArchivosDia(
        fecha="20260504",
        mes="202605",
        input_base=tmp_path / "base.xlsx",
        diarios_dir=tmp_path,
        planes=None,
        pagos=None,
    )

    result = procesar_dia_module.procesar_dia(config=config, archivos=archivos)

    assert result.status == "success"
    assert result.rows_roman == 1
    assert state_calls["initialized"] == 1
    assert state_calls["cargar_estado_calls"] >= 2


def test_roman_output_uses_dv_actual_as_monto_deuda_vencida_actual_for_clients_with_pago(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_df = pd.DataFrame([
        {
            "nroproducto": "100",
            "nombre_apellido": "Cliente Uno",
            "dni": "30111222",
            "cajon": "M90",
            "deuda_total": 1000.0,
            "deuda_vencida": 100.0,
            "telefono1": "5411",
            "telefono2": "54911",
            "telefono3": "5433",
            "telefono4": "",
            "email1": "",
            "email2": "",
            "email3": "",
            "deuda_vencida_tc": 0,
            "deuda_vencida_nd": 0,
            "total_vencida": 100.0,
            "deuda_total_tc": 0,
            "deuda_total_nd": 0,
            "estrategia": "M90",
            "asignacion": "Elite",
            "ecosistema": "PURO",
            "marca_plan": "SIN PLAN",
            "recupero": "",
            "tipo_pago": "",
        }
    ])

    monkeypatch.setattr(procesar_dia_module, "cargar_estado", lambda *_args, **_kwargs: base_df.copy())
    monkeypatch.setattr(
        procesar_dia_module,
        "detectar_archivos_diarios",
        lambda *_args, **_kwargs: {"planes": None, "pagos": tmp_path / "pagos.csv", "no_reconocidos": []},
    )
    monkeypatch.setattr(procesar_dia_module, "mover_insumos_procesados", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(procesar_dia_module, "guardar_estado", lambda *_args, **_kwargs: ("vigente.csv", "snapshot.csv"))
    monkeypatch.setattr(procesar_dia_module, "update_estado", lambda df, *_args, **_kwargs: df.copy())
    monkeypatch.setattr(procesar_dia_module, "aplicar_filtros", lambda df, **_kwargs: (df.copy(), {"cajon_fuera_scope": 0}))
    monkeypatch.setattr(
        procesar_dia_module,
        "load_pagos",
        lambda *_args, **_kwargs: pd.DataFrame([
            {"nroproducto": "100", "dv_actual": "321.50", "deuda_vencida": "999.99"}
        ]),
    )

    saved_payloads: list[pd.DataFrame] = []

    def _save_output(df, output_dir, prefix, date_format="%Y%m%d", suffix=".csv"):
        if prefix == "NARANJAX_MA_ROMAN_":
            saved_payloads.append(df.copy())
        filename = f"{prefix}dummy{suffix}"
        return str(Path(output_dir) / filename)

    monkeypatch.setattr(procesar_dia_module, "save_output", _save_output)

    config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    archivos = ArchivosDia(
        fecha="20260506",
        mes="202605",
        input_base=tmp_path / "base.xlsx",
        diarios_dir=tmp_path,
        planes=None,
        pagos=tmp_path / "pagos.csv",
        usar_pagos=True,
    )

    result = procesar_dia_module.procesar_dia(config=config, archivos=archivos)

    assert result.status == "success"
    assert saved_payloads
    roman_df = saved_payloads[0]
    assert float(roman_df.iloc[0]["monto_deuda_vencida_actual"]) == 321.5
