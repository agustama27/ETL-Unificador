from datetime import datetime
from pathlib import Path
import threading

import pandas as pd

from filtrosAplicados_base_BANCOR.procesos import pipeline_wfm


ROMAN_OUTPUT_COLUMNS = list(pipeline_wfm.COLUMNAS_SALIDA_ROMAN)


def _build_input_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Cliente_BT": "CLI001",
                "MontoAdeudado": 1500,
                "Fecha_Entrega": "15/04/2026",
                "NumeroTelefono": "543516000000",
                "NumeroCelular": "5493517000000",
                "NumeroOperacion": "OP001",
                "AgrupadorProducto": "Prestamo",
            },
            {
                "Cliente_BT": "CLI002",
                "MontoAdeudado": 900,
                "Fecha_Entrega": "16/04/2026",
                "NumeroTelefono": "543516000000",
                "NumeroCelular": "5493516000000",
                "NumeroOperacion": "OP002",
                "AgrupadorProducto": "Tarjeta",
            },
        ]
    )


def _build_back_base_contract_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Cliente_BT": "CLI010",
                "CUIL": "20123456789",
                "NumeroDocumento": "30111222",
                "ClienteNombre": "Cliente Prueba",
                "NumeroTelefono": "543516000000",
                "NumeroCelular": "5493517000000",
                "NumeroTrabajo": "543514000000",
                "Mail": "cliente@correo.com",
                "Nro Cuenta": "00012345",
                "AgrupadorProducto": "Prestamo",
                "Campaña_REF": "CAMPAÑA45$",
                "ModuloCodigo": "201",
                "NumeroOperacion": "OP010",
                "Dias_Mora": "30",
                "MontoAdeudado": 1200,
                "OFERTA_Importe": 900,
                "SaldoCapital": 1000,
                "Sucursal_Cuenta": "001",
                "IVAInteresAdeudado": 10,
                "InteresAdeudado": 100,
                "Cuenta": "CTA-10",
                "Estado Cuenta": "Vigente",
                "Tasa_40": "NO",
            }
        ]
    )


def test_build_run_context_deterministico() -> None:
    contexto = pipeline_wfm._build_run_context(datetime(2026, 4, 21, 10, 11, 12))
    assert contexto["fecha_ddmmyyyy"] == "21042026"
    assert contexto["fecha_yyyymmdd"] == "20260421"
    assert contexto["fecha_carpeta"] == "21-04-2026"
    assert contexto["timestamp"] == "101112"


def test_generar_csv_roman_contrato_basico(tmp_path: Path) -> None:
    df_data = _build_input_df()

    artifact = pipeline_wfm._generar_csv_roman(df_data, tmp_path, "20260421")

    assert artifact["status"] == "generated"
    assert artifact["filename"] == "BANCOR_ROMAN_20260421.csv"

    path_csv = Path(artifact["path"])
    assert path_csv.exists()

    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8")
    assert list(df_salida.columns) == ROMAN_OUTPUT_COLUMNS
    assert len(df_salida) == len(df_data)
    assert set(df_salida["oferta_importe"].astype(str).unique()) <= {"si", "no"}


def test_generar_csv_roman_compatibilidad_header_y_orden_back_base(tmp_path: Path) -> None:
    df_data = _build_back_base_contract_df()

    artifact = pipeline_wfm._generar_csv_roman(df_data, tmp_path, "20260421")

    assert artifact["status"] == "generated"
    path_csv = Path(artifact["path"])

    primera_linea = path_csv.read_text(encoding="utf-8").splitlines()[0]
    assert primera_linea.count(";") == len(ROMAN_OUTPUT_COLUMNS) - 1

    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8")
    assert list(df_salida.columns) == ROMAN_OUTPUT_COLUMNS
    assert df_salida.loc[0, "tipo_campana_ref"] == "CAMPAÑA45$"
    assert "resumen_productos" in df_salida.columns
    assert df_salida.loc[0, "resumen_productos"].startswith("[")
    assert df_salida.loc[0, "resumen_productos"].endswith("]")


def test_normalizar_tipo_campana_ref_remueve_diacriticos_y_simbolos() -> None:
    assert pipeline_wfm._normalizar_tipo_campana_ref("CAMPAÑA45$") == "CAMPANA45"
    assert pipeline_wfm._normalizar_tipo_campana_ref("CAMPAÑA30%") == "CAMPANA30"


def test_generar_csv_e1kia_contrato_y_sufijo_canonico(tmp_path: Path) -> None:
    df_data = _build_input_df()

    artifact = pipeline_wfm._generar_csv_e1kia(df_data, tmp_path, "20260421")

    assert artifact["status"] == "generated"
    assert artifact["filename"] == "BANCOR_E1KIA_20260421_sinestrategia.csv"

    path_csv = Path(artifact["path"])
    assert path_csv.exists()

    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8")
    assert list(df_salida.columns) == ["tel_fijo", "tel_celular"]

    numeros = []
    for columna in ("tel_fijo", "tel_celular"):
        for valor in df_salida[columna].fillna(""):
            valor_str = str(valor).strip()
            if valor_str:
                numeros.append(valor_str)
    assert len(numeros) == len(set(numeros))


def test_generar_csv_e1kia_normalizacion_compatibilidad_back_base(tmp_path: Path) -> None:
    df_data = pd.DataFrame(
        [
            {
                "NumeroTelefono": "0351-156000000",
                "NumeroCelular": "351156000000",
            },
            {
                "NumeroTelefono": "3519999999",
                "NumeroCelular": "5493517000000",
            },
            {
                "NumeroTelefono": "543516000000",
                "NumeroCelular": "",
            },
        ]
    )

    artifact = pipeline_wfm._generar_csv_e1kia(df_data, tmp_path, "20260421")
    assert artifact["status"] == "generated"

    df_salida = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str)

    fijos = set(df_salida["tel_fijo"].fillna("").str.strip()) - {""}
    celulares = set(df_salida["tel_celular"].fillna("").str.strip()) - {""}

    assert fijos == {"543516000000"}
    assert celulares == {"5493517000000"}
    assert "3519999999" not in fijos
    assert "3519999999" not in celulares


def test_pipeline_partial_failure_si_falla_un_auxiliar(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    _build_input_df().to_excel(input_path, index=False)

    monkeypatch.setattr(pipeline_wfm, "obtener_carpeta_base", lambda: tmp_path)

    def _roman_fallido(df_salida: pd.DataFrame, carpeta_salida: Path, fecha: str) -> dict:
        _ = (df_salida, carpeta_salida, fecha)
        return {
            "name": "roman",
            "filename": "BANCOR_ROMAN_20260421.csv",
            "path": str(carpeta_salida / "BANCOR_ROMAN_20260421.csv"),
            "status": "failed",
            "error": "fallo simulado",
        }

    monkeypatch.setattr(pipeline_wfm, "_generar_csv_roman", _roman_fallido)

    resultado = pipeline_wfm.ejecutar_pipeline_wfm(input_path, [4])

    assert resultado["status"] == "partial_failure"
    assert resultado["ok"] is False

    artifacts = resultado["artifacts"]
    assert any(item["name"] == "xlsx" and item["status"] == "generated" for item in artifacts)
    assert any(item["name"] == "roman" and item["status"] == "failed" for item in artifacts)
    assert any(item["name"] == "e1kia" and item["status"] == "generated" for item in artifacts)


def test_pipeline_partial_failure_si_fallan_ambos_auxiliares(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    _build_input_df().to_excel(input_path, index=False)

    monkeypatch.setattr(pipeline_wfm, "obtener_carpeta_base", lambda: tmp_path)

    def _roman_fallido(df_salida: pd.DataFrame, carpeta_salida: Path, fecha: str) -> dict:
        _ = (df_salida, carpeta_salida, fecha)
        return {
            "name": "roman",
            "filename": "BANCOR_ROMAN_20260421.csv",
            "path": str(carpeta_salida / "BANCOR_ROMAN_20260421.csv"),
            "status": "failed",
            "error": "fallo roman simulado",
        }

    def _e1kia_fallido(df_salida: pd.DataFrame, carpeta_salida: Path, fecha: str) -> dict:
        _ = (df_salida, carpeta_salida, fecha)
        return {
            "name": "e1kia",
            "filename": "BANCOR_E1KIA_20260421_sinestrategia.csv",
            "path": str(carpeta_salida / "BANCOR_E1KIA_20260421_sinestrategia.csv"),
            "status": "failed",
            "error": "fallo e1kia simulado",
        }

    monkeypatch.setattr(pipeline_wfm, "_generar_csv_roman", _roman_fallido)
    monkeypatch.setattr(pipeline_wfm, "_generar_csv_e1kia", _e1kia_fallido)

    resultado = pipeline_wfm.ejecutar_pipeline_wfm(input_path, [4])

    assert resultado["status"] == "partial_failure"
    assert resultado["ok"] is False

    artifacts_por_nombre = {
        artifact["name"]: artifact
        for artifact in resultado["artifacts"]
        if isinstance(artifact, dict)
    }
    assert artifacts_por_nombre["xlsx"]["status"] == "generated"
    assert artifacts_por_nombre["roman"]["status"] == "failed"
    assert artifacts_por_nombre["roman"]["error"] == "fallo roman simulado"
    assert artifacts_por_nombre["e1kia"]["status"] == "failed"
    assert artifacts_por_nombre["e1kia"]["error"] == "fallo e1kia simulado"


def test_pipeline_coherencia_fecha_en_nombres(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    _build_input_df().to_excel(input_path, index=False)

    monkeypatch.setattr(pipeline_wfm, "obtener_carpeta_base", lambda: tmp_path)

    class _DatetimeFija(datetime):
        @classmethod
        def now(cls, tz=None):
            _ = tz
            return cls(2026, 4, 21, 23, 59, 59)

    monkeypatch.setattr(pipeline_wfm, "datetime", _DatetimeFija)

    resultado = pipeline_wfm.ejecutar_pipeline_wfm(input_path, [4])

    assert resultado["status"] == "success"
    assert "21-04-2026" in resultado["output_path"]
    assert "base_recibida_BANCOR_conFiltros_21042026_235959.xlsx" in resultado["output_path"]

    artifacts_por_nombre = {
        artifact["name"]: artifact
        for artifact in resultado["artifacts"]
        if isinstance(artifact, dict)
    }
    assert artifacts_por_nombre["roman"]["filename"] == "BANCOR_ROMAN_20260421.csv"
    assert artifacts_por_nombre["e1kia"]["filename"] == "BANCOR_E1KIA_20260421_sinestrategia.csv"


def test_pipeline_cancelado_devuelve_estado_cancelled(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.xlsx"
    _build_input_df().to_excel(input_path, index=False)

    monkeypatch.setattr(pipeline_wfm, "obtener_carpeta_base", lambda: tmp_path)

    cancel_event = threading.Event()
    cancel_event.set()

    resultado = pipeline_wfm.ejecutar_pipeline_wfm(
        input_path,
        [4],
        cancel_event=cancel_event,
    )

    assert resultado["ok"] is False
    assert resultado["status"] == "cancelled"
    assert all(artifact.get("status") != "generated" for artifact in resultado.get("artifacts", []))
