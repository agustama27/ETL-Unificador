from __future__ import annotations

from pathlib import Path

from cli.main import run_cli
from core.modelos import ResultadoDia


def test_cli_reports_missing_input_alias_and_path(tmp_path: Path, capsys, monkeypatch) -> None:
    salida_dir = tmp_path / "salida"
    estado_dir = tmp_path / "estado"
    salida_dir.mkdir()
    estado_dir.mkdir()
    monkeypatch.setattr("cli.main.load_config", lambda: {"carpeta_estado": str(estado_dir), "carpeta_salida": str(salida_dir)})

    base_path = tmp_path / "base_inexistente.xlsx"
    planes_path = tmp_path / "planes_inexistente.xlsx"
    code = run_cli(
        [
            "prog",
            "--base",
            str(base_path),
            "--planes",
            str(planes_path),
            "--fecha",
            "20260430",
        ]
    )

    assert code == 1
    out = capsys.readouterr().out
    assert f"input 'base' -> {base_path}" in out
    assert f"input 'planes' -> {planes_path}" in out


def test_cli_accepts_evoltis_pagos_format_without_validation_failure(tmp_path: Path, capsys, monkeypatch) -> None:
    salida_dir = tmp_path / "salida"
    estado_dir = tmp_path / "estado"
    salida_dir.mkdir()
    estado_dir.mkdir()
    monkeypatch.setattr("cli.main.load_config", lambda: {"carpeta_estado": str(estado_dir), "carpeta_salida": str(salida_dir)})

    base_path = tmp_path / "base.xlsx"
    planes_path = tmp_path / "planes.xlsx"
    pagos_path = tmp_path / "evoltis_avanzada_pagos_detalle_20260428.csv"
    base_path.write_text("fake", encoding="utf-8")
    planes_path.write_text("fake", encoding="utf-8")
    pagos_path.write_text(
        '"PROVEEDOR","DNI","NROPRODUCTO","RECUPERO","PRODUCTO"\n'
        '"DEELO","DU35214453","DU00035214453","SI","NARANJA"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "cli.main.procesar_dia",
        lambda _config, _archivos, log_cb=None: ResultadoDia(status="success", fecha="20260430", mes="202604"),
    )

    code = run_cli(
        [
            "prog",
            "--base",
            str(base_path),
            "--planes",
            str(planes_path),
            "--pagos",
            str(pagos_path),
            "--fecha",
            "20260430",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "no impacta deuda/saldo" in out


def test_cli_inicio_mes_sin_diarios_allows_missing_planes(tmp_path: Path, capsys, monkeypatch) -> None:
    salida_dir = tmp_path / "salida"
    estado_dir = tmp_path / "estado"
    salida_dir.mkdir()
    estado_dir.mkdir()
    monkeypatch.setattr("cli.main.load_config", lambda: {"carpeta_estado": str(estado_dir), "carpeta_salida": str(salida_dir)})

    base_path = tmp_path / "base.xlsx"
    base_path.write_text("fake", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_procesar_dia(_config, archivos, log_cb=None):
        captured["modo_sin_diarios"] = archivos.modo_sin_diarios
        captured["planes"] = archivos.planes
        return ResultadoDia(status="success", fecha="20260501", mes="202605", modo_ejecucion="inicio_mes_sin_diarios")

    monkeypatch.setattr("cli.main.procesar_dia", _fake_procesar_dia)

    code = run_cli(
        [
            "prog",
            "--base",
            str(base_path),
            "--inicio-mes-sin-diarios",
            "--fecha",
            "20260501",
        ]
    )

    assert code == 0
    assert captured["modo_sin_diarios"] is True
    assert captured["planes"] is None
    out = capsys.readouterr().out
    assert "inicio de mes sin diarios" in out.lower()
