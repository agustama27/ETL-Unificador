import subprocess
import sys
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "adapters/naranjax/mt_voice_job.py"
LEGACY = WORKSPACE / "soho-naranjaX-MT-etl"


def _run(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--input", str(input_path),
         "--output_dir", str(output_dir)],
        cwd=LEGACY, capture_output=True, text=True, check=False,
    )


def _write_input(tmp_path: Path, columns: int) -> Path:
    path = tmp_path / "base.txt"
    row = "|".join(["C1", "NOMBRE"] + [""] * (columns - 2))
    path.write_text(row + "\n", encoding="utf-8")
    return path


def test_valid_input_generates_roman_then_e1kia_in_sandbox(tmp_path: Path) -> None:
    output = tmp_path / "output"

    result = _run(_write_input(tmp_path, 33), output)

    assert result.returncode == 0, result.stderr
    roman = list(output.glob("NARANJAX_MT_ROMAN_*.csv"))
    e1kia = list(output.glob("NARANJAX_MT_E1KIA_*.csv"))
    assert len(roman) == 1 and len(e1kia) == 1
    assert len(list(output.iterdir())) == 2
    assert not list(LEGACY.glob("back-base/base_procesada/NARANJAX_MT_*_9*.csv"))


def test_wrong_column_count_fails_like_main(tmp_path: Path) -> None:
    result = _run(_write_input(tmp_path, 3), tmp_path / "output")

    assert result.returncode == 1
    assert "Se esperaban 33 columnas" in result.stderr


def test_empty_input_fails_like_main(tmp_path: Path) -> None:
    empty = tmp_path / "base.txt"
    empty.write_text("", encoding="utf-8")

    result = _run(empty, tmp_path / "output")

    assert result.returncode == 1
    assert "Error:" in result.stderr


def test_missing_input_fails_like_main(tmp_path: Path) -> None:
    result = _run(tmp_path / "absent.txt", tmp_path / "output")

    assert result.returncode == 1
    assert "Error:" in result.stderr
