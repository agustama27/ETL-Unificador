"""Contract tests for clean_base — first coverage for this repo.

Pin the client-facing contract: first CSV in the input dir, rows with
negative "Dias atraso" dropped, "Cel" prefixed with +549, `;`-delimited
fixed-name output.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from procesos.clean_base import clean_base  # noqa: E402


def _write_input(directory: Path, rows: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "base.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_clean_base_filters_negatives_and_prefixes_cel(tmp_path: Path) -> None:
    _write_input(tmp_path / "in", [
        "DNI;Dias atraso;Cel",
        "30111222;30;3517710632",
        "30111223;-5;3517710633",
    ])

    result = clean_base(input_dir=str(tmp_path / "in"),
                        output_dir=str(tmp_path / "out"),
                        output_filename="fravega_base.csv")

    text = result.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert result.name == "fravega_base.csv"
    assert ";" in lines[0]
    assert len(lines) == 2
    assert "+5493517710632" in lines[1]
    assert "30111223" not in text


def test_clean_base_requires_contract_columns(tmp_path: Path) -> None:
    _write_input(tmp_path / "in", ["DNI;Otra", "30111222;x"])

    with pytest.raises(KeyError):
        clean_base(input_dir=str(tmp_path / "in"), output_dir=str(tmp_path / "out"))


def test_clean_base_fails_without_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        clean_base(input_dir=str(tmp_path / "vacia"), output_dir=str(tmp_path / "out"))
