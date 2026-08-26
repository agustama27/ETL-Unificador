from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from cartasur_etl.config_store import SavedSettings, load_settings
from cartasur_etl.models import EtlConfig, InputFiles
from cartasur_etl.procesar_dia import procesar_dia
from cartasur_etl.runtime_paths import RuntimePathInputs, resolve_runtime_paths
from cartasur_etl.validators_archivos import validate_for_processing

FIXTURE = "tests/fixtures/CabeceraconDatos.xlsx"


def test_procesar_dia_central_function_generates_outputs(tmp_path):
    logs: list[str] = []
    result = procesar_dia(
        EtlConfig(output_dir=tmp_path / "out", log_dir=tmp_path / "logs", run_date=date(2026, 6, 22)),
        InputFiles(raw_input=Path(FIXTURE)),
        log_cb=logs.append,
    )

    assert result.ok
    assert result.valid_records > 0
    assert (tmp_path / "out" / "CARTA_SUR_ROMAN_260622.csv").exists()
    assert any("Clientes agrupados" in line for line in logs)


def test_runtime_path_priority_explicit_env_settings_defaults(tmp_path, monkeypatch):
    settings = SavedSettings(output_dir=str(tmp_path / "settings-out"), log_dir=str(tmp_path / "settings-logs"))
    monkeypatch.setenv("CARTASUR_ETL_OUTPUT_DIR", str(tmp_path / "env-out"))

    resolved = resolve_runtime_paths(RuntimePathInputs(output_dir=str(tmp_path / "explicit-out")), settings=settings)

    assert resolved.output_dir == (tmp_path / "explicit-out").resolve()
    assert resolved.log_dir == (tmp_path / "settings-logs").resolve()

    resolved_env = resolve_runtime_paths(RuntimePathInputs(), settings=settings)
    assert resolved_env.output_dir == (tmp_path / "env-out").resolve()


def test_load_settings_ignores_stale_state_dir(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"output_dir": str(tmp_path / "out"), "state_dir": str(tmp_path / "state"), "log_dir": str(tmp_path / "logs")}),
        encoding="utf-8",
    )

    loaded = load_settings(settings_path)

    assert not hasattr(loaded, "state_dir")
    assert loaded.output_dir == str(tmp_path / "out")
    assert loaded.log_dir == str(tmp_path / "logs")


def test_validator_reports_missing_file_and_writable_dirs(tmp_path):
    for name in ("out", "logs"):
        (tmp_path / name).mkdir()
    paths = resolve_runtime_paths(
        RuntimePathInputs(input_path=str(tmp_path / "missing.xlsx"), output_dir=str(tmp_path / "out"), log_dir=str(tmp_path / "logs")),
        settings=SavedSettings(),
    )

    result = validate_for_processing(paths, check_preconditions=False)

    assert not result.ok
    assert any("no existe" in error.lower() for error in result.errors)


def test_dual_entrypoint_cli_smoke(tmp_path):
    env = {**os.environ, "PYTHONPATH": "src"}
    completed = subprocess.run(
        [sys.executable, "cartasur_etl.py", "--cli", "--input", FIXTURE, "--output-dir", str(tmp_path), "--run-date", "2026-06-22"],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )

    assert "CARTA_SUR_ROMAN_260622.csv" in completed.stdout
    assert (tmp_path / "CARTA_SUR_ROMAN_260622.csv").exists()
