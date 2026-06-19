from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


BACK_BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_BASE_DIR))
from back_base_etl.cleaners import clean_telefono  # noqa: E402
from back_base_etl.transformers import transform  # noqa: E402


def _base_row(**overrides) -> dict[str, object]:
    row: dict[str, object] = {
        "dni": "30111222",
        "nombre_apellido": "Test User",
        "deuda_vencida_tc": "10",
        "deuda_vencida_nd": "20",
        "total_vencida": "30",
        "deuda_total_tc": "40",
        "deuda_total_nd": "50",
        "total_deuda": "60",
        "estrategia": "E1",
        "nroproducto": "1001",
        "marca_plan": "plan x",
        "telefono1": "",
        "telefono2": "",
        "telefono3": "",
        "telefono4": "",
        "email1": "",
        "email2": "",
        "email3": "",
        "cajon": "M30",
        "ecosistema": "eco",
        "asignacion": "mora avanzada",
    }
    row.update(overrides)
    return row


def test_clean_telefono_normalizes_excel_dot_zero_suffix() -> None:
    assert clean_telefono("5491122334455.0") == "5491122334455"


@pytest.mark.parametrize(
    ("raw_phone", "expected"),
    [
        ("+54 9 11 2233-4455", "5491122334455"),
        ("54 (11) 2233-4455", "541122334455"),
    ],
)
def test_clean_telefono_accepts_mobile_and_landline_with_symbols(
    raw_phone: str,
    expected: str,
) -> None:
    assert clean_telefono(raw_phone) == expected


@pytest.mark.parametrize(
    "raw_phone",
    [
        "551122334455",
        "549112233445",
        "54112233445",
    ],
)
def test_clean_telefono_rejects_wrong_prefix_or_length(raw_phone: str) -> None:
    assert clean_telefono(raw_phone) == ""


def test_transform_preserves_phone_with_excel_dot_zero_suffix() -> None:
    df = pd.DataFrame([_base_row(telefono1="5491122334455.0")])

    result = transform(df)

    assert result.iloc[0]["tel_1"] == "5491122334455"


def test_transform_discards_invalid_phone_and_keeps_valid_normalized_phone() -> None:
    df = pd.DataFrame(
        [
            _base_row(
                telefono1="abc",
                telefono2="54 (11) 2233-4455",
            )
        ]
    )

    result = transform(df)

    assert result.iloc[0]["tel_1"] == ""
    assert result.iloc[0]["tel_2"] == "541122334455"
