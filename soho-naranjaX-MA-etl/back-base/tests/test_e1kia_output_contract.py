from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_BASE_DIR = REPO_ROOT / "back-base"
sys.path.insert(0, str(BACK_BASE_DIR))

from back_base_etl.constants import OUTPUT_FILENAME_E1KIA  # noqa: E402
from back_base_etl.io import save_output  # noqa: E402
from back_base_etl.transformers import build_e1kia_output  # noqa: E402


def test_e1kia_example_contract_header_and_delimiter() -> None:
    sample = pd.DataFrame([{"tel_1": "5411", "tel_2": "54911", "tel_3": ""}])
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(
            save_output(
                sample,
                tmpdir,
                prefix=OUTPUT_FILENAME_E1KIA,
                date_format="%y%m%d",
                suffix="_sinestrategia.csv",
            )
        )
        first_line = output_path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == "tel_1;tel_2;tel_3"


def test_build_e1kia_output_keeps_expected_columns_order_and_values() -> None:
    roman = pd.DataFrame(
        [
            {"tel_1": "5411", "tel_2": "54911", "tel_3": "5433", "id_dni": "1"},
            {"tel_1": "", "tel_2": "54922", "tel_3": "", "id_dni": "2"},
        ]
    )

    e1kia = build_e1kia_output(roman)

    assert list(e1kia.columns) == ["tel_1", "tel_2", "tel_3"]
    assert e1kia.to_dict(orient="records") == [
        {"tel_1": "5411", "tel_2": "54911", "tel_3": "5433"},
        {"tel_1": "", "tel_2": "54922", "tel_3": ""},
    ]


def test_save_output_e1kia_exact_naming_pattern(tmp_path: Path) -> None:
    e1kia = pd.DataFrame([{"tel_1": "5411", "tel_2": "54911", "tel_3": ""}])
    output_path = Path(
        save_output(
            e1kia,
            str(tmp_path),
            prefix=OUTPUT_FILENAME_E1KIA,
            date_format="%y%m%d",
            suffix="_sinestrategia.csv",
        )
    )

    assert re.match(r"^NARANJAX_MA_E1KIA_\d{6}_sinestrategia\.csv$", output_path.name)
    reloaded = pd.read_csv(output_path, sep=";", dtype=str, keep_default_na=False)
    assert list(reloaded.columns) == ["tel_1", "tel_2", "tel_3"]
