"""Resolución de la hoja de base mensual en el legacy (issue #101).

Contrato: alias primero, fallback a hoja única con encabezados validados, fallo
claro en el resto. Único cambio a código legacy de la migración — ver
``docs/decisions/tolerancia-hoja-asignacion.md``.

Hasta la baja del ETL de Chat había dos copias de ``back_base_etl`` y un test que
verificaba que compartieran el bloque de resolución textualmente. Queda una sola,
así que ese test ya no tiene contra qué comparar.
"""

import importlib
import logging
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

NARANJAX = Path(__file__).resolve().parents[1]
COPIES = {
    "ma": NARANJAX / "legacy/ma/back-base",
}


def _purge_modules() -> None:
    for name in [m for m in sys.modules
                 if m == "back_base_etl" or m.startswith("back_base_etl.")]:
        del sys.modules[name]


@pytest.fixture(params=sorted(COPIES))
def legacy_io(request):
    root = COPIES[request.param]
    sys.path.insert(0, str(root))
    _purge_modules()
    try:
        yield importlib.import_module("back_base_etl.io")
    finally:
        sys.path.remove(str(root))
        _purge_modules()


def _required_headers() -> list[str]:
    constants = importlib.import_module("back_base_etl.constants")
    return [
        constants.INPUT_COLUMN_ALIASES.get(canonical, (canonical,))[0]
        for canonical in constants.INPUT_COLUMNS
        if canonical not in constants.INPUT_OPTIONAL_COLUMNS
    ]


def _workbook(tmp_path: Path, sheets: dict[str, list[str] | None]) -> str:
    book = Workbook()
    for index, (name, headers) in enumerate(sheets.items()):
        sheet = book.active if index == 0 else book.create_sheet()
        sheet.title = name
        if headers:
            sheet.append(headers)
    path = tmp_path / "base.xlsx"
    book.save(path)
    return str(path)


def test_named_sheet_keeps_winning(legacy_io, tmp_path: Path) -> None:
    path = _workbook(tmp_path, {"Asignacion": _required_headers(), "Hoja1": None})

    assert legacy_io._resolve_input_sheet_name(path) == "Asignacion"


def test_single_unnamed_sheet_with_headers_is_used_and_logged(
    legacy_io, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = _workbook(tmp_path, {"Hoja1": _required_headers()})

    with caplog.at_level(logging.WARNING, logger="etl_naranjax"):
        assert legacy_io._resolve_input_sheet_name(path) == "Hoja1"

    assert any("single sheet" in record.getMessage() for record in caplog.records)


def test_single_sheet_without_required_headers_fails(legacy_io, tmp_path: Path) -> None:
    path = _workbook(tmp_path, {"Hoja1": ["columna_cualquiera"]})

    with pytest.raises(ValueError, match="missing required columns"):
        legacy_io._resolve_input_sheet_name(path)


def test_multiple_sheets_without_match_fail_listing_them(legacy_io, tmp_path: Path) -> None:
    path = _workbook(tmp_path, {"Hoja1": _required_headers(), "Hoja2": None})

    with pytest.raises(ValueError, match="Available sheets: Hoja1, Hoja2"):
        legacy_io._resolve_input_sheet_name(path)


def test_la_tolerancia_autorizada_sigue_en_el_legacy() -> None:
    """Guardia contra una resincronización que la pise.

    Ya pasó: sincronizar `io.py` con el upstream borró este bloque de un saque,
    porque el upstream no lo tiene ni debe tenerlo. La tolerancia es un cambio
    propio del Unificador, autorizado en el issue #101.
    """
    fuente = (COPIES["ma"] / "back_base_etl/io.py").read_text("utf-8")

    assert "def _missing_required_input_headers" in fuente
    assert "using the workbook's " in fuente
