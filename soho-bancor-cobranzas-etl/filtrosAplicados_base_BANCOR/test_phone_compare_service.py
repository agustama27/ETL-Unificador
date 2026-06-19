from pathlib import Path
import threading

import pandas as pd

from filtrosAplicados_base_BANCOR.procesos.phone_compare_service import (
    comparar_telefonos_archivos,
    expandir_equivalencias,
    limpiar_numero,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    df_data = pd.DataFrame(rows)
    df_data.to_csv(path, sep=";", index=False, encoding="utf-8")


def test_normalizacion_numero_y_equivalencias_549_54_local() -> None:
    assert limpiar_numero("5493516000000.0") == "5493516000000"
    assert limpiar_numero("0054 351-600-0000") == "543516000000"
    assert limpiar_numero("nan") == ""

    equivalencias = expandir_equivalencias("5493516000000")
    assert {"5493516000000", "543516000000", "3516000000"}.issubset(equivalencias)


def test_comparar_telefonos_sin_anomalias_por_equivalencias(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    target_csv = tmp_path / "target.csv"

    _write_csv(source_csv, [{"telefono": "5493516000000"}])
    _write_csv(target_csv, [{"telefono": "3516000000"}])

    result = comparar_telefonos_archivos(
        source_path=source_csv,
        target_path=target_csv,
        source_columns_raw="telefono",
        target_columns_raw="telefono",
    )

    assert result["ok"] is True
    assert result["status"] == "SIN_ANOMALIAS"
    assert result["no_anomaly"] is True
    assert result["summary"]["faltantes_unicos"] == 0
    assert result["missing_rows"] == []


def test_comparar_telefonos_con_anomalias(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    target_csv = tmp_path / "target.csv"

    _write_csv(source_csv, [{"telefono": "5493517777777"}])
    _write_csv(target_csv, [{"telefono": "5493516000000"}])

    result = comparar_telefonos_archivos(
        source_path=source_csv,
        target_path=target_csv,
        source_columns_raw="telefono",
        target_columns_raw="telefono",
    )

    assert result["ok"] is True
    assert result["status"] == "CON_ANOMALIAS"
    assert result["no_anomaly"] is False
    assert result["summary"]["faltantes_unicos"] == 1
    assert result["missing_rows"][0]["numero_referencia"] == "3517777777"


def test_comparar_telefonos_input_invalido_devuelve_error(tmp_path: Path) -> None:
    source_csv = tmp_path / "missing_source.csv"
    target_csv = tmp_path / "target.csv"
    _write_csv(target_csv, [{"telefono": "3516000000"}])

    result = comparar_telefonos_archivos(
        source_path=source_csv,
        target_path=target_csv,
        source_columns_raw="telefono",
        target_columns_raw="telefono",
    )

    assert result["ok"] is False
    assert result["status"] == "ERROR"
    assert "No existe source" in result["error"]


def test_comparar_telefonos_cancelado_devuelve_estado_cancelled(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    target_csv = tmp_path / "target.csv"
    _write_csv(source_csv, [{"telefono": "5493516000000"}])
    _write_csv(target_csv, [{"telefono": "3516000000"}])

    cancel_event = threading.Event()
    cancel_event.set()

    result = comparar_telefonos_archivos(
        source_path=source_csv,
        target_path=target_csv,
        source_columns_raw="telefono",
        target_columns_raw="telefono",
        cancel_event=cancel_event,
    )

    assert result["ok"] is False
    assert result["status"] == "CANCELLED"
    assert "Cancelado" in result["message"]


def test_comparar_telefonos_admite_source_e1000ia_con_bom_y_coma(tmp_path: Path) -> None:
    source_csv = tmp_path / "Bancor_21abr_E1000IA_TELEFONOS.csv"
    target_csv = tmp_path / "BANCOR_ROMAN.csv"

    source_csv.write_bytes("NumeroCelular,Comentario\n5493516000000,ok\n".encode("utf-8-sig"))
    _write_csv(target_csv, [{"NumeroTelefono": "3516000000"}])

    result = comparar_telefonos_archivos(
        source_path=source_csv,
        target_path=target_csv,
    )

    assert result["ok"] is True
    assert result["status"] == "SIN_ANOMALIAS"
    assert result["summary"]["faltantes_unicos"] == 0
    assert "NumeroCelular" in result["source_columns"]
    assert any("Source leido con:" in log and "sep=," in log for log in result["logs"])
