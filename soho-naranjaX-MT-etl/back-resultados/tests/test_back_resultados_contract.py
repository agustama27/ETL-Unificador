"""Contract tests for the --back job (procesos/back_resultados.py).

They drive ``main.py --back`` as a subprocess with synthetic fixtures and pin
the client-approved DEELO_NAR_USUEVOLTIS output contract: pipe-delimited,
CRLF, 40 columns, col 8 USUEVOLTIS, col 36 EVOLTIS, correlativo in col 7.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "main.py"


def _run_back(tmp_path: Path, *, logcall: Path, historial: Path, m30: Path):
    output_dir = tmp_path / "salida"
    completed = subprocess.run(
        [sys.executable, str(ENTRYPOINT), "--back",
         "--logcall", str(logcall), "--historial", str(historial),
         "--m30", str(m30), "--back-output-dir", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return completed, output_dir


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    logcall = tmp_path / "LOGCALL_sintetico.csv"
    logcall.write_text(
        "ACTIGROUP,RESULT,PHONE,CALLREFID,LOGDATE,LOGTIME\n"
        "M,8,5493517710632,ref_sint_1,20260721,0930\n"
        "M,7,5493517710633,ref_sint_2,20260721,0931\n"
        "X,8,5493517710634,ref_excluido,20260721,0932\n",
        encoding="utf-8",
    )
    historial = tmp_path / "historial_llamadas_sintetico.csv"
    historial.write_text(
        "[Entrada] user_number,[Entrada] customer_id,[Salida] Tipificaciones\n",
        encoding="utf-8",
    )
    m30 = tmp_path / "m30_sintetico.txt"
    row = ["C0001", "CLIENTE SINTETICO", "", "5493517710632"] + [""] * 29
    m30.write_text("|".join(row) + "\n", encoding="utf-8")
    return logcall, historial, m30


def test_back_generates_usuolos_contract_and_anomalias(tmp_path: Path) -> None:
    logcall, historial, m30 = _fixtures(tmp_path)

    completed, output_dir = _run_back(
        tmp_path, logcall=logcall, historial=historial, m30=m30
    )

    assert completed.returncode == 0, completed.stderr
    usuolos_files = sorted(output_dir.glob("DEELO_NAR_USUEVOLTIS_*.txt"))
    anomalias_files = sorted(output_dir.glob("_anomalias_*.txt"))
    assert len(usuolos_files) == 1 and len(anomalias_files) == 1

    data = usuolos_files[0].read_bytes()
    assert data.count(b"\r\n") == 2
    lines = data.decode("utf-8").rstrip("\r\n").split("\r\n")
    assert len(lines) == 2

    for index, line in enumerate(lines, start=1):
        cols = line.split("|")
        assert len(cols) == 40
        assert cols[2] == "NARANJA"
        assert cols[6] == str(index)
        assert cols[7] == "USUEVOLTIS"
        assert cols[8] == "N"
        assert cols[9] == "MAKE CALL"
        assert cols[35] == "EVOLTIS"
        assert cols[38] == "PENDING"
        assert cols[0] == "202607210930" or cols[0] == "202607210931"

    results = {line.split("|")[10] for line in lines}
    assert results == {"NO ANSWER", "BUSY"}
    assert "ref_excluido" not in data.decode("utf-8")


def test_back_rejects_non_txt_m30(tmp_path: Path) -> None:
    logcall, historial, _ = _fixtures(tmp_path)
    bad_m30 = tmp_path / "m30.csv"
    bad_m30.write_text("C0001,algo\n", encoding="utf-8")

    completed, _ = _run_back(tmp_path, logcall=logcall, historial=historial, m30=bad_m30)

    assert completed.returncode == 1
    assert "pipe-delimited" in completed.stderr


def test_back_fails_on_missing_logcall(tmp_path: Path) -> None:
    _, historial, m30 = _fixtures(tmp_path)

    completed, _ = _run_back(
        tmp_path, logcall=tmp_path / "ausente.csv", historial=historial, m30=m30
    )

    assert completed.returncode == 1
    assert "Error" in completed.stderr
