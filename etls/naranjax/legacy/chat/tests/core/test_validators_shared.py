from __future__ import annotations

from pathlib import Path

from core.validators_archivos import (
    MENSAJE_EXTENSION,
    MENSAJE_CSV_INVALIDO,
    MENSAJE_LOCK,
    MENSAJE_NO_ENCONTRADO,
    MENSAJE_ONEDRIVE,
    aggregate_messages,
    validar_archivo,
    validar_csv_basico,
    validar_estado_mensual,
)


def test_validar_archivo_missing_file_reports_specific_message(tmp_path: Path) -> None:
    issues = validar_archivo(tmp_path / "no-existe.xlsx", (".xlsx",))
    messages = aggregate_messages(issues)
    assert messages == [MENSAJE_NO_ENCONTRADO]


def test_validar_archivo_wrong_extension_reports_specific_message(tmp_path: Path) -> None:
    file_path = tmp_path / "input.docx"
    file_path.write_text("x", encoding="utf-8")
    issues = validar_archivo(file_path, (".xlsx",))
    messages = aggregate_messages(issues)
    assert MENSAJE_EXTENSION in messages


def test_validar_archivo_onedrive_message_shared(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "input.xlsx"
    file_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("core.validators_archivos._is_onedrive_placeholder", lambda _path: True)
    issues = validar_archivo(file_path, (".xlsx",))
    messages = aggregate_messages(issues)
    assert MENSAJE_ONEDRIVE in messages


def test_validar_archivo_lock_message_shared(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "input.xlsx"
    file_path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("core.validators_archivos._is_locked", lambda _path: True)
    issues = validar_archivo(file_path, (".xlsx",))
    messages = aggregate_messages(issues)
    assert MENSAJE_LOCK in messages


def test_validar_estado_mensual_reports_month(tmp_path: Path) -> None:
    issues = validar_estado_mensual(tmp_path, "202604")
    messages = aggregate_messages(issues)
    assert messages == ["No hay estado mensual para 2026-04. Es la primera ejecucion del mes?"]


def test_validar_csv_basico_accepts_semicolon_and_comma(tmp_path: Path) -> None:
    semicolon_file = tmp_path / "pagos_semicolon.csv"
    comma_file = tmp_path / "pagos_comma.csv"
    semicolon_file.write_text("a;b\n1;2\n", encoding="utf-8")
    comma_file.write_text('"a","b"\n"1","2"\n', encoding="utf-8")

    assert validar_csv_basico(semicolon_file) == []
    assert validar_csv_basico(comma_file) == []


def test_validar_csv_basico_reports_invalid_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "pagos_bad.csv"
    bad_file.write_bytes(b"\xff\xfe\x00\x00")

    issues = validar_csv_basico(bad_file)
    messages = aggregate_messages(issues)
    assert messages == [MENSAJE_CSV_INVALIDO]
