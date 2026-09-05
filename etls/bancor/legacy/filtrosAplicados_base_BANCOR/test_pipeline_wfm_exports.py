from datetime import date, datetime
from pathlib import Path
import sys
import threading

import pandas as pd
import pytest

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


def _build_multiproduct_offer_df() -> pd.DataFrame:
    """Crea productos retenidos con cobertura total, parcial y sin oferta."""
    fecha_acuerdo_reciente = datetime.now().strftime("%d/%m/%Y")
    filas = [
        ("20397353843", "CLI203", "Prestamo", "OP203-1", 20_000_000, 8_000_000.10, "5493517000001", 100),
        ("20397353843", "CLI203", "Tarjeta", "OP203-2", 20_000_000, 8_096_401.63, "5493517000001", 200),
        ("23435613519", "CLI234", "Hipotecario", "OP234-1", 2_000_000, 1_000_000, "5493517000002", 300),
        ("23435613519", "CLI234", "Prendario", "OP234-2", 2_000_000, 1_088_962.67, "5493517000002", 400),
        ("20121556309", "CLI201", "Prestamo", "OP201-1", 2_000_000, 1_000_000, "5493517000003", 500),
        ("20121556309", "CLI201", "Tarjeta", "OP201-2", 2_000_000, 689_412.66, "5493517000003", 600),
        ("20121556309", "CLI201", "Cuenta corriente", "OP201-3", 2_000_000, 0, "5493517000003", 700),
        ("20900000000", "CLI000", "Sin oferta A", "OP000-1", 500, "", "5493517000004", 800),
        ("20900000000", "CLI000", "Sin oferta B", "OP000-2", 500, -1, "5493517000004", 900),
        ("20999999999", "CLIWIN", "Ganador", "OPWIN", 1_000, 100, "5493517999999", 111),
        ("20888888888", "CLILOS", "Perdedor", "OPLOS", 500, 50, "5493517999999", 222),
        ("20777777777", "CLIACT", "Acuerdo vigente", "OPACT", 1_000, 500, "5493517000005", 333),
    ]
    registros = []
    for cuil, cliente, producto, operacion, deuda, oferta, celular, anticipo in filas:
        registros.append(
            {
                "CUIL": cuil,
                "Cliente_BT": cliente,
                "ClienteNombre": f"Cliente {cliente}",
                "NumeroDocumento": "30111222",
                "NumeroCelular": celular,
                "Mail": "cliente@correo.com",
                "Nro Cuenta": "12345",
                "Cuenta": "CTA",
                "Estado Cuenta": "Vigente",
                "Campaña_REF": "CAMPANA45",
                "TipoAsignacion": "NORMAL",
                "AgrupadorProducto": producto,
                "NumeroOperacion": operacion,
                "MontoAdeudado": deuda,
                "OFERTA_Importe": oferta,
                "AnticipoMinimo": anticipo,
                "Dias_Mora": 30,
                "Gestion_Estado": "07. Promesa de Pago Pactada" if cliente == "CLIACT" else "",
                "Fecha_Gestion": fecha_acuerdo_reciente if cliente == "CLIACT" else "",
            }
        )
    return pd.DataFrame(registros)


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
    assert df_salida.loc[0, "tipo_campana_ref"] == "CAMPAÑA45%"
    assert "resumen_productos" in df_salida.columns
    assert df_salida.loc[0, "resumen_productos"].startswith("[")
    assert df_salida.loc[0, "resumen_productos"].endswith("]")


def test_generar_csv_roman_preserva_productos_y_agregados_por_cuil(tmp_path: Path) -> None:
    df_entrada = _build_multiproduct_offer_df()

    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")

    assert artifact["status"] == "generated"
    path_csv = Path(artifact["path"])
    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    assert list(df_salida.columns)[19:21] == ["monto_total_oferta", "alcance_oferta"]
    assert list(df_salida.columns) == ROMAN_OUTPUT_COLUMNS

    esperado = {
        "20397353843": ("16096401.73", "total", 2),
        "23435613519": ("2088962.67", "total", 2),
        "20121556309": ("1689412.66", "parcial", 3),
        "20900000000": ("", "", 2),
    }
    for cuil, (total, alcance, bloques) in esperado.items():
        fila = df_salida.loc[df_salida["id_cuil"] == cuil].iloc[0]
        assert fila["monto_total_oferta"] == total
        assert fila["alcance_oferta"] == alcance
        assert fila["resumen_productos"].count("OfertaImporte:") == bloques

    resumen_sin_oferta = df_salida.loc[df_salida["id_cuil"] == "20900000000", "resumen_productos"].iloc[0]
    assert resumen_sin_oferta.count("OfertaImporte:NO") == 2
    fila_sin_oferta = df_salida.loc[df_salida["id_cuil"] == "20900000000"].iloc[0]
    assert fila_sin_oferta["oferta_importe"] == "no"
    assert fila_sin_oferta["tipo_campana_ref"] == "CAMPAÑA45%"
    assert "CLIACT" not in set(df_salida["id_cliente_bt"])
    assert "CLILOS" not in set(df_salida["id_cliente_bt"])
    assert "CLIWIN" in set(df_salida["id_cliente_bt"])
    contenido = path_csv.read_text(encoding="utf-8")
    assert contenido.splitlines()[0].split(";") == ROMAN_OUTPUT_COLUMNS
    assert "16096401.73" in contenido
    assert "16096401,73" not in contenido
    assert ";nan;" not in contenido.lower()


def test_generar_csv_roman_mantiene_consolidacion_y_anticipo_existentes(tmp_path: Path) -> None:
    df_entrada = _build_multiproduct_offer_df()

    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")
    df_salida = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    fila = df_salida.loc[df_salida["id_cuil"] == "20121556309"].iloc[0]
    assert fila["monto_adeudado_ars"] == "6000000"
    assert fila["monto_entrega_ars"] == "500"


def test_generar_csv_roman_serializa_oferta_total_mayor_deuda_y_advierte(tmp_path: Path) -> None:
    df_entrada = pd.DataFrame(
        [
            {
                "CUIL": "20000000001",
                "Cliente_BT": "CLIOVER",
                "MontoAdeudado": 100,
                "OFERTA_Importe": 150,
                "AgrupadorProducto": "Tarjeta",
                "NumeroOperacion": "OPOVER",
                "NumeroCelular": "5493517000099",
            }
        ]
    )

    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")

    assert artifact["status"] == "generated"
    path_csv = Path(artifact["path"])
    assert path_csv.exists()
    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    assert df_salida.loc[0, "monto_total_oferta"] == "150.00"
    assert df_entrada.loc[0, "OFERTA_Importe"] == 150

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert any("CUIL 20000000001 tiene monto_total_oferta mayor al monto adeudado" in warning for warning in warnings)


def test_validar_roman_advierte_invariantes_de_oferta_y_cardinalidad(tmp_path: Path) -> None:
    df_entrada = _build_multiproduct_offer_df()
    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")
    path_csv = Path(artifact["path"])

    warnings_validos = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert warnings_validos == ["VALIDACION ROMAN: OK - variables obligatorias/opcionales verificadas."]

    df_invalido = pd.read_csv(path_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    indice = df_invalido.index[df_invalido["id_cuil"] == "20121556309"][0]
    df_invalido.loc[indice, "monto_total_oferta"] = "9999999,99"
    df_invalido.loc[indice, "alcance_oferta"] = "parcial"
    df_invalido.loc[indice, "resumen_productos"] = "[Prestamo DeudaVencida:2000000.00 OfertaImporte:1000000.00]"
    indice_sin_oferta = df_invalido.index[df_invalido["id_cuil"] == "20900000000"][0]
    df_invalido.loc[indice_sin_oferta, "monto_total_oferta"] = "invalido"
    path_invalido = tmp_path / "roman_invalido.csv"
    df_invalido.to_csv(path_invalido, sep=";", encoding="utf-8", index=False)

    warnings_invalidos = pipeline_wfm._validar_variables_roman_obligatorias(path_invalido, df_entrada)
    assert any("alcance_oferta inconsistente" in warning for warning in warnings_invalidos)
    assert any("monto_total_oferta inconsistente" in warning for warning in warnings_invalidos)
    assert any("monto_total_oferta invalido" in warning for warning in warnings_invalidos)
    assert any("mayor al monto adeudado" in warning for warning in warnings_invalidos)
    assert any("bloques de resumen" in warning for warning in warnings_invalidos)


def test_validar_roman_advierte_orden_de_columnas(tmp_path: Path) -> None:
    df_entrada = _build_multiproduct_offer_df()
    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")
    df_salida = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    path_desordenado = tmp_path / "roman_desordenado.csv"
    df_salida[list(reversed(df_salida.columns))].to_csv(path_desordenado, sep=";", encoding="utf-8", index=False)

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_desordenado)
    assert any("orden de columnas" in warning for warning in warnings)


def test_pipeline_wfm_mantiene_contrato_xlsx_al_agregar_campos_roman(tmp_path: Path, monkeypatch) -> None:
    df_entrada = _build_input_df()
    input_path = tmp_path / "input.xlsx"
    df_entrada.to_excel(input_path, index=False)
    monkeypatch.setattr(pipeline_wfm, "obtener_carpeta_base", lambda: tmp_path)

    resultado = pipeline_wfm.ejecutar_pipeline_wfm(input_path, [4])

    assert resultado["status"] == "success"
    df_xlsx = pd.read_excel(resultado["output_path"])
    assert list(df_xlsx.columns) == list(df_entrada.columns)
    assert "monto_total_oferta" not in df_xlsx.columns
    assert "alcance_oferta" not in df_xlsx.columns


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("CAMPAÑA20%", "CAMPAÑA20%"),
        ("campaña 30 $", "CAMPAÑA30%"),
        ("Campana35", "CAMPAÑA35%"),
        ("CAMPAÑA45$", "CAMPAÑA45%"),
        ("", ""),
        (None, ""),
        ("NO APLICA", ""),
    ],
)
def test_normalizar_tipo_campana_ref_emite_formato_canonico(
    valor: object,
    esperado: str,
) -> None:
    assert pipeline_wfm._normalizar_tipo_campana_ref(valor) == esperado


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


# ── Oferta de Cancelacion Anticipada (OFERTA_PREVENTA) ──────────────────────────
# Casos 1..12 de la seccion 5 del PRD (docs/oferta-preventa/PRD-oferta-preventa-etl.md).

VIGENTE = date(2026, 9, 30)
VENCIDA = date(2026, 10, 1)


def _fila_preventa(**overrides) -> dict:
    """Fila base de la cohorte preventa; los tests sobreescriben lo que necesitan."""
    fila = {
        "CUIL": "20111111111",
        "Cliente_BT": "CLIPRE",
        "ClienteNombre": "Cliente Preventa",
        "NumeroDocumento": "30111222",
        "NumeroCelular": "5493517100001",
        "Mail": "cliente@correo.com",
        "Nro Cuenta": "12345",
        "Cuenta": "CTA",
        "Estado Cuenta": "Vigente",
        "Campaña_REF": "CAMPANA30",
        "TipoAsignacion": "NORMAL",
        "AgrupadorProducto": "Prestamo",
        "NumeroOperacion": "OPPRE-1",
        "MontoAdeudado": 100_000,
        "OFERTA_Importe": "",
        "AnticipoMinimo": 1_000,
        "Dias_Mora": 449,
        "PreVenta": "APLICA OFERTA",
        "OFERTA_PREVENTA": 58_330,
        "BanconUsr": "Activo",
    }
    fila.update(overrides)
    return fila


def _salida_preventa(tmp_path: Path, filas: list[dict], fecha_corrida: date = VIGENTE):
    df_entrada = pd.DataFrame(filas)
    artifact = pipeline_wfm._generar_csv_roman(
        df_entrada,
        tmp_path,
        "20260903",
        fecha_corrida=fecha_corrida,
    )
    assert artifact["status"] == "generated", artifact.get("error")
    path_csv = Path(artifact["path"])
    df_salida = pd.read_csv(path_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    return df_salida, path_csv, df_entrada


# Caso 1
def test_preventa_elegible_emite_si_y_montos_completos(tmp_path: Path) -> None:
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa()])

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["monto_total_preventa"] == "58330.00"
    assert fila["alcance_preventa"] == "total"
    assert fila["medio_pago_preventa"] == "cupon"
    assert fila["fecha_limite_preventa"] == "2026-09-30"
    assert fila["tipo_tna_refi_preventa"] == "30"
    assert fila["tipo_bancon_usr"] == "Activo"


# Caso 2
@pytest.mark.parametrize("importe", ["", 0, "no-numerico", None])
def test_preventa_sin_importe_valido_emite_no_y_derivadas_vacias(
    tmp_path: Path,
    importe: object,
) -> None:
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa(OFERTA_PREVENTA=importe)])

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "no"
    for columna in pipeline_wfm.config_preventa.COLUMNAS_DERIVADAS_PREVENTA:
        assert fila[columna] == "", columna


# Caso 3
def test_preventa_requiere_ambas_condiciones(tmp_path: Path) -> None:
    df_salida, _, _ = _salida_preventa(
        tmp_path,
        [_fila_preventa(PreVenta="NO APLICA OFERTA", OFERTA_PREVENTA=58_330)],
    )

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "no"
    assert fila["monto_total_preventa"] == ""


# Caso 4
def test_preventa_corrida_posterior_al_limite_da_de_baja_la_campania(tmp_path: Path) -> None:
    filas = [
        _fila_preventa(),
        _fila_preventa(CUIL="20222222222", Cliente_BT="CLIPRE2", NumeroCelular="5493517100002"),
    ]
    df_salida, _, _ = _salida_preventa(tmp_path, filas, fecha_corrida=VENCIDA)

    assert set(df_salida["oferta_preventa"]) == {"no"}
    for columna in pipeline_wfm.config_preventa.COLUMNAS_DERIVADAS_PREVENTA:
        assert set(df_salida[columna]) == {""}, columna


# Caso 5
def test_preventa_vigente_el_ultimo_dia_inclusive(tmp_path: Path) -> None:
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa()], fecha_corrida=VIGENTE)
    assert df_salida.loc[0, "oferta_preventa"] == "si"
    assert df_salida.loc[0, "fecha_limite_preventa"] == "2026-09-30"


# Caso 6
@pytest.mark.parametrize(
    ("dias_mora", "tna_esperada"),
    [(449, "30"), (571, "20"), (900, "20"), (365, ""), (None, "")],
)
def test_preventa_tna_por_tramo_de_dias_mora(dias_mora: object, tna_esperada: str) -> None:
    assert pipeline_wfm._tna_por_dias_mora(dias_mora) == tna_esperada


def test_preventa_tna_por_dias_mora_usa_el_maximo_del_grupo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # BLQ-1 se resolvio a favor de Campana_REF; este test cubre el ruteo alternativo.
    monkeypatch.setattr(pipeline_wfm.config_preventa, "FUENTE_TNA_REFI_PREVENTA", "dias_mora")
    filas = [
        _fila_preventa(NumeroOperacion="OP-A", Dias_Mora=449, OFERTA_PREVENTA=10_000),
        _fila_preventa(NumeroOperacion="OP-B", Dias_Mora=900, OFERTA_PREVENTA=10_000),
    ]
    df_salida, _, _ = _salida_preventa(tmp_path, filas)

    fila = df_salida.iloc[0]
    assert fila["cnt_dias_mora_max"] == "900"
    assert fila["tipo_tna_refi_preventa"] == "20"


def test_preventa_tna_default_la_rutea_campana_ref(tmp_path: Path) -> None:
    # BLQ-1: aunque Dias_Mora=900 caeria en el tramo del 20 %, manda Campana_REF.
    df_salida, path_csv, df_entrada = _salida_preventa(
        tmp_path,
        [_fila_preventa(Dias_Mora=900, **{"Campaña_REF": "CAMPANA30"})],
    )

    assert df_salida.loc[0, "tipo_campana_ref"] == "CAMPAÑA30%"
    assert df_salida.loc[0, "tipo_tna_refi_preventa"] == "30"

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert any("BLQ-1" in warning and "desacuerdo con Campana_REF" in warning for warning in warnings)


# Caso 7
def test_preventa_multiproducto_alcance_parcial_y_total_sumado(tmp_path: Path) -> None:
    filas = [
        _fila_preventa(NumeroOperacion="OP-1", AgrupadorProducto="Prestamo", OFERTA_PREVENTA=10_000),
        _fila_preventa(NumeroOperacion="OP-2", AgrupadorProducto="Tarjeta", OFERTA_PREVENTA=5_500.50),
        _fila_preventa(NumeroOperacion="OP-3", AgrupadorProducto="Cuenta", OFERTA_PREVENTA=""),
    ]
    df_salida, _, _ = _salida_preventa(tmp_path, filas)

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["monto_total_preventa"] == "15500.50"
    assert fila["alcance_preventa"] == "parcial"


def test_preventa_multiproducto_alcance_total_cuando_todos_aplican(tmp_path: Path) -> None:
    filas = [
        _fila_preventa(NumeroOperacion="OP-1", OFERTA_PREVENTA=10_000),
        _fila_preventa(NumeroOperacion="OP-2", OFERTA_PREVENTA=5_000),
    ]
    df_salida, _, _ = _salida_preventa(tmp_path, filas)

    assert df_salida.loc[0, "alcance_preventa"] == "total"
    assert df_salida.loc[0, "monto_total_preventa"] == "15000.00"


# Caso 8
@pytest.mark.parametrize("anticipo", ["CANCELAR", "   ", 58_330, 651_913])
def test_preventa_anticipo_incoherente_suprime_la_refinanciacion(
    tmp_path: Path,
    anticipo: object,
) -> None:
    # BLQ-2: sin TNA ni monto de entrega, el agente ofrece solo cancelacion de contado.
    df_salida, path_csv, df_entrada = _salida_preventa(
        tmp_path,
        [_fila_preventa(AnticipoMinimo=anticipo)],
    )

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["tipo_tna_refi_preventa"] == ""
    assert fila["monto_entrega_ars"] == ""

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert any("BLQ-2" in warning for warning in warnings)


def test_preventa_anticipo_coherente_conserva_la_refinanciacion(tmp_path: Path) -> None:
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa(AnticipoMinimo="   40882.448")])

    fila = df_salida.iloc[0]
    assert fila["tipo_tna_refi_preventa"] == "30"
    assert fila["monto_entrega_ars"] != ""


# Caso 9
@pytest.mark.parametrize(
    ("bancon", "esperado"),
    [("Activo", "Activo"), ("NoActivo", "NoActivo"), ("", ""), (None, "")],
)
def test_preventa_bancon_usr_pasa_sin_transformar(
    tmp_path: Path,
    bancon: object,
    esperado: str,
) -> None:
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa(BanconUsr=bancon)])
    assert df_salida.loc[0, "tipo_bancon_usr"] == esperado


def test_preventa_bancon_usr_vacio_emite_advertencia(tmp_path: Path) -> None:
    df_salida, path_csv, df_entrada = _salida_preventa(tmp_path, [_fila_preventa(BanconUsr="")])
    assert df_salida.loc[0, "tipo_bancon_usr"] == ""

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert any("BLQ-3" in warning for warning in warnings)


# Caso 10
def test_preventa_normaliza_headers_con_encoding_roto_y_variantes(tmp_path: Path) -> None:
    fila = _fila_preventa()
    # Variantes reales: el requerimiento escribe OFERTA_Preventa y la base llega con
    # encoding inconsistente, igual que Campa?a_REF.
    fila["OFERTA_Preventa"] = fila.pop("OFERTA_PREVENTA")
    fila["Pre Venta"] = fila.pop("PreVenta")
    fila["Bancon Usr"] = fila.pop("BanconUsr")

    df_salida, _, _ = _salida_preventa(tmp_path, [fila])

    assert df_salida.loc[0, "oferta_preventa"] == "si"
    assert df_salida.loc[0, "monto_total_preventa"] == "58330.00"
    assert df_salida.loc[0, "tipo_bancon_usr"] == "Activo"


def test_preventa_alias_de_encabezados_resuelven_al_canonico() -> None:
    df = pd.DataFrame(columns=["OFERTA_Preventa", "Pre Venta", "BANCONUSR", "otra"])
    normalizado = pipeline_wfm._normalizar_encabezados_preventa(df)
    assert set(normalizado.columns) == {"OFERTA_PREVENTA", "PreVenta", "BanconUsr", "otra"}


# Caso 11
def test_preventa_invariante_de_consistencia_sin_derivadas_vacias(tmp_path: Path) -> None:
    filas = [
        _fila_preventa(),
        _fila_preventa(
            CUIL="20333333333",
            Cliente_BT="CLINO",
            NumeroCelular="5493517100003",
            PreVenta="NO APLICA OFERTA",
            OFERTA_PREVENTA="",
        ),
    ]
    df_salida, path_csv, df_entrada = _salida_preventa(tmp_path, filas)

    for _, fila in df_salida.iterrows():
        if fila["oferta_preventa"] == "si":
            for columna in pipeline_wfm.config_preventa.COLUMNAS_DERIVADAS_PREVENTA:
                if columna == "tipo_tna_refi_preventa":
                    continue  # puede quedar vacio por BLQ-2
                assert fila[columna] != "", columna
        else:
            for columna in pipeline_wfm.config_preventa.COLUMNAS_DERIVADAS_PREVENTA:
                assert fila[columna] == "", columna

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert not any("oferta_preventa='si' con" in warning for warning in warnings)
    assert not any("oferta_preventa='no' con" in warning for warning in warnings)


def test_preventa_validador_detecta_derivadas_incoherentes(tmp_path: Path) -> None:
    df_salida, path_csv, _ = _salida_preventa(tmp_path, [_fila_preventa()])

    df_roto = df_salida.copy()
    df_roto.loc[0, "alcance_preventa"] = ""
    path_roto = tmp_path / "roman_preventa_roto.csv"
    df_roto.to_csv(path_roto, sep=";", encoding="utf-8", index=False)

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_roto)
    assert any("oferta_preventa='si' con 'alcance_preventa' vacio" in warning for warning in warnings)


# Caso 12 - regresion del contrato posicional
def test_preventa_no_mueve_las_columnas_existentes_del_contrato(tmp_path: Path) -> None:
    df_entrada = _build_multiproduct_offer_df()
    artifact = pipeline_wfm._generar_csv_roman(df_entrada, tmp_path, "20260810")
    df_salida = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    columnas = list(df_salida.columns)
    assert columnas[19:21] == ["monto_total_oferta", "alcance_oferta"]
    assert columnas == ROMAN_OUTPUT_COLUMNS
    assert columnas[24:31] == [
        "oferta_preventa",
        "monto_total_preventa",
        "alcance_preventa",
        "tipo_tna_refi_preventa",
        "medio_pago_preventa",
        "fecha_limite_preventa",
        "tipo_bancon_usr",
    ]
    # Base sin las columnas nuevas: la campania no aplica y no ensucia la validacion.
    assert set(df_salida["oferta_preventa"]) == {"no"}


# BLQ-4 - precedencia sobre la oferta vigente
def test_preventa_tiene_precedencia_sobre_oferta_importe(tmp_path: Path) -> None:
    df_salida, path_csv, df_entrada = _salida_preventa(
        tmp_path,
        [_fila_preventa(OFERTA_Importe=70_000)],
    )

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["oferta_importe"] == "no"

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv, df_entrada)
    assert any("BLQ-4" in warning for warning in warnings)


def test_preventa_sin_precedencia_conserva_la_oferta_vigente(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_wfm.config_preventa,
        "PRECEDENCIA_SOBRE_OFERTA_VIGENTE",
        False,
    )
    df_salida, _, _ = _salida_preventa(tmp_path, [_fila_preventa(OFERTA_Importe=70_000)])

    fila = df_salida.iloc[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["oferta_importe"] == "si"


# ── Guarda de regresion: literales de branch del conversation flow ──────────────
# Los branch nodes de Retell comparan por IGUALDAD DE STRING. Si esta normalizacion
# se "simplifica" a un trim/upper/sin-acentos generico, produce `CAMPANA 30`, que no
# matchea ningun edge, y el 100 % de las llamadas cae al else_edge sin error ni log.
# Verificado contra `conversation_flow_87ada0e3e5b2` v1.4.5, branch node-1771387916379.

# bytes UTF-8 exactos que espera cada edge del branch (la N con tilde es \xc3\x91).
LITERALES_BRANCH_FLOW = {
    "CAMPAÑA 20": b"CAMPA\xc3\x91A20%",
    "CAMPAÑA 30": b"CAMPA\xc3\x91A30%",
    "CAMPAÑA 35": b"CAMPA\xc3\x91A35%",
    "CAMPAÑA 45": b"CAMPA\xc3\x91A45%",
}


@pytest.mark.parametrize(("valor_base", "bytes_esperados"), sorted(LITERALES_BRANCH_FLOW.items()))
def test_normalizar_tipo_campana_ref_coincide_byte_a_byte_con_el_flow(
    valor_base: str,
    bytes_esperados: bytes,
) -> None:
    emitido = pipeline_wfm._normalizar_tipo_campana_ref(valor_base)
    assert emitido.encode("utf-8") == bytes_esperados
    # La enie tiene que ser la letra, no una N pelada: `CAMPANA30%` no matchea nada.
    assert "Ñ" in emitido
    assert "CAMPANA" not in emitido


def test_normalizar_tipo_campana_ref_no_aplica_cae_al_else_edge() -> None:
    # El edge literal `NO APLICA` y el else_edge van al mismo nodo (node-1771379417075),
    # asi que emitir "" es equivalente y no cambia el destino de la llamada.
    assert pipeline_wfm._normalizar_tipo_campana_ref("NO APLICA") == ""


def test_tna_refi_preventa_es_proyeccion_pura_de_tipo_campana_ref() -> None:
    # tipo_tna_refi_preventa NO es un dato independiente: sale de tipo_campana_ref.
    # El dominio queda abierto a proposito (CAMPAÑA45% y CAMPAÑA35% siguen vigentes).
    for valor_base in LITERALES_BRANCH_FLOW:
        canonico = pipeline_wfm._normalizar_tipo_campana_ref(valor_base)
        esperado = valor_base.replace("CAMPAÑA ", "")
        assert pipeline_wfm._tna_por_campana_ref(canonico) == esperado


# ── Paridad exe-vs-fuentes ─────────────────────────────────────────────────────
# En el ejecutable congelado, `_load_back_base_generator_module()` devuelve None:
# `__file__` apunta al tmpdir de PyInstaller y el arbol de fuentes no viaja adentro.
# Hasta 2026-09-03 eso hacia que `calcular_quita` quedara en None y el exe emitiera
# aplica_quita="no" en el 100 % de las filas, con miles de clientes en el rango de
# mora elegible. El CSV salia valido y equivocado, sin error ni log.
#
# Estos tests simulan ese entorno y exigen que la salida sea IDENTICA.


def _build_quita_elegible_df() -> pd.DataFrame:
    """Clientes con Tipo_Mercado MA y mora en 61-365, sin oferta: quita aplicable."""
    filas = [
        ("20444444441", "CLIQ1", 90, 100_000, 20_000, 10_000, "5493517200001", "3521-441521"),
        ("20444444442", "CLIQ2", 150, 200_000, 40_000, 20_000, "5493517200002", "3521-441522"),
        ("20444444443", "CLIQ3", 300, 300_000, 60_000, 30_000, "5493517200003", "3521-441523"),
        # Mora 500: fuera del rango 61-365, sirve de control negativo de la quita.
        ("20444444444", "CLIQ4", 500, 400_000, 80_000, 40_000, "5493517200004", "3521-441524"),
    ]
    registros = []
    for cuil, cliente, mora, deuda, comp, punit, celular, fijo in filas:
        registros.append(
            {
                "CUIL": cuil,
                "Cliente_BT": cliente,
                "ClienteNombre": f"Cliente {cliente}",
                "NumeroDocumento": "30111222",
                "NumeroTelefono": fijo,
                "NumeroCelular": celular,
                "Mail": "cliente@correo.com",
                "Nro Cuenta": "12345",
                "Cuenta": "CTA",
                "Estado Cuenta": "Vigente",
                "Campaña_REF": "CAMPANA30",
                "TipoAsignacion": "NORMAL",
                "AgrupadorProducto": "Prestamo",
                "NumeroOperacion": f"OP-{cliente}",
                "MontoAdeudado": deuda,
                "OFERTA_Importe": "",
                "AnticipoMinimo": 1_000,
                "Dias_Mora": mora,
                "Tipo_Mercado": "MA",
                "Compensatorio": comp,
                "Punitorios": punit,
                "PreVenta": "APLICA OFERTA",
                "OFERTA_PREVENTA": round(deuda * 0.5833, 2),
                "BanconUsr": "Activo",
            }
        )
    return pd.DataFrame(registros)


def test_quita_se_calcula_sin_depender_del_loader_de_back_base(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """El caso que el exe rompia: sin base_generator, la quita igual se calcula."""
    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)

    artifact = pipeline_wfm._generar_csv_roman(
        _build_quita_elegible_df(), tmp_path, "20260903", fecha_corrida=VIGENTE
    )
    assert artifact["status"] == "generated", artifact.get("error")
    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    elegibles = int((df["aplica_quita"] == "si").sum())
    assert elegibles > 0, (
        "aplica_quita='no' en el 100 % de las filas sin back-base: volvio la "
        "degradacion silenciosa que rompia el exe."
    )
    for _, fila in df[df["aplica_quita"] == "si"].iterrows():
        assert fila["monto_quita_ars"] != ""
        assert fila["fecha_limite_quita"] != ""


def test_paridad_roman_con_y_sin_back_base(tmp_path: Path, monkeypatch) -> None:
    """Misma entrada por los dos caminos: el ROMAN tiene que salir identico.

    Cubre tambien el fallback de `deduplicar_por_telefonos_back_base()` y la pasada
    redundante de prefijos telefonicos.
    """
    df_entrada = _build_quita_elegible_df()
    carpeta_fuentes = tmp_path / "fuentes"
    carpeta_exe = tmp_path / "exe"
    carpeta_fuentes.mkdir()
    carpeta_exe.mkdir()

    artifact_fuentes = pipeline_wfm._generar_csv_roman(
        df_entrada.copy(), carpeta_fuentes, "20260903", fecha_corrida=VIGENTE
    )
    assert artifact_fuentes["status"] == "generated", artifact_fuentes.get("error")
    # Sanity: en el arbol de fuentes el loader tiene que estar funcionando de verdad,
    # si no la comparacion seria trivial (None contra None).
    assert pipeline_wfm._load_back_base_generator_module() is not None

    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)
    artifact_exe = pipeline_wfm._generar_csv_roman(
        df_entrada.copy(), carpeta_exe, "20260903", fecha_corrida=VIGENTE
    )
    assert artifact_exe["status"] == "generated", artifact_exe.get("error")

    df_fuentes = pd.read_csv(Path(artifact_fuentes["path"]), sep=";", dtype=str, keep_default_na=False)
    df_exe = pd.read_csv(Path(artifact_exe["path"]), sep=";", dtype=str, keep_default_na=False)

    assert list(df_exe.columns) == list(df_fuentes.columns)
    assert len(df_exe) == len(df_fuentes)
    for columna in df_fuentes.columns:
        assert list(df_exe[columna]) == list(df_fuentes[columna]), (
            f"La columna '{columna}' difiere entre el camino exe y el camino fuentes."
        )


def test_paridad_roman_con_y_sin_back_base_en_base_multiproducto(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Misma paridad sobre la fixture multiproducto, que ejercita la deduplicacion."""
    df_entrada = _build_multiproduct_offer_df()
    carpeta_fuentes = tmp_path / "fuentes"
    carpeta_exe = tmp_path / "exe"
    carpeta_fuentes.mkdir()
    carpeta_exe.mkdir()

    artifact_fuentes = pipeline_wfm._generar_csv_roman(
        df_entrada.copy(), carpeta_fuentes, "20260810"
    )
    assert artifact_fuentes["status"] == "generated", artifact_fuentes.get("error")
    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)
    artifact_exe = pipeline_wfm._generar_csv_roman(df_entrada.copy(), carpeta_exe, "20260810")
    assert artifact_exe["status"] == "generated", artifact_exe.get("error")

    df_fuentes = pd.read_csv(Path(artifact_fuentes["path"]), sep=";", dtype=str, keep_default_na=False)
    df_exe = pd.read_csv(Path(artifact_exe["path"]), sep=";", dtype=str, keep_default_na=False)

    assert list(df_exe.columns) == list(df_fuentes.columns)
    for columna in df_fuentes.columns:
        assert list(df_exe[columna]) == list(df_fuentes[columna]), (
            f"La columna '{columna}' difiere entre el camino exe y el camino fuentes."
        )


def test_telefonos_llevan_prefijo_sin_back_base(tmp_path: Path, monkeypatch) -> None:
    """El prefijo 54/549 lo aplica codigo local, no la pasada de back-base."""
    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)

    artifact = pipeline_wfm._generar_csv_roman(
        _build_quita_elegible_df(), tmp_path, "20260903", fecha_corrida=VIGENTE
    )
    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    celulares = [valor for valor in df["tel_celular"] if valor.strip()]
    assert celulares
    assert all(valor.startswith("549") for valor in celulares)


def test_requerir_back_base_falla_con_la_causa_real(monkeypatch) -> None:
    """El loader ya no se traga la causa: se puede reportar por que fallo."""
    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)
    monkeypatch.setattr(pipeline_wfm, "_ULTIMO_ERROR_BACK_BASE", "causa de prueba")

    with pytest.raises(pipeline_wfm.BackBaseNoDisponibleError, match="causa de prueba"):
        pipeline_wfm._requerir_back_base()


def test_force_back_base_sync_no_degrada_en_silencio(tmp_path: Path, monkeypatch) -> None:
    """Si se pidio sincronizar contra back-base y no esta, el artifact falla."""
    monkeypatch.setattr(pipeline_wfm, "_load_back_base_generator_module", lambda: None)

    artifact = pipeline_wfm._generar_csv_roman(
        _build_quita_elegible_df(),
        tmp_path,
        "20260903",
        force_back_base_sync=True,
    )
    assert artifact["status"] == "failed"
    assert "base_generator.py no esta disponible" in artifact["error"]


def test_parsear_decimal_paridad_config_quita_vs_base_generator() -> None:
    """config_quita reimplementa _parsear_decimal sin pandas: tiene que dar igual."""
    modulo_bb = pipeline_wfm._load_back_base_generator_module()
    assert modulo_bb is not None, "test valido solo desde el arbol de fuentes"

    casos = [
        "1234.56", "1.234,56", "1,234.56", "  40882.448  ", "CANCELAR", "",
        "nan", "-", ".", ",", "-500", "$ 1.000,50", 0, 0.0, 12, 12.5, None,
        float("nan"), pd.NA, pd.NaT,
    ]
    for valor in casos:
        assert pipeline_wfm.config_quita._parsear_decimal(valor) == modulo_bb._parsear_decimal(valor), valor


def test_config_quita_no_depende_de_pandas() -> None:
    """La condicion que lo hace bundleable con el exe.

    Se verifica importando el modulo en un interprete limpio y comprobando que
    pandas no quedo cargado, en vez de grepear el fuente (el docstring menciona
    pd.NA legitimamente).
    """
    import subprocess

    carpeta = str(Path(pipeline_wfm.config_quita.__file__).parent)
    codigo = (
        "import sys; sys.path.insert(0, r'%s'); import config_quita; "
        "print('pandas' in sys.modules); "
        "print(config_quita.calcular_quita('MA', 90, 20000, 10000, 100000, False))" % carpeta
    )
    salida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.splitlines()

    assert salida[0] == "False", "config_quita arrastro pandas: deja de ser bundleable"
    assert salida[1] == "('si', 90000.0)"


# ── monto_vencido_ars ──────────────────────────────────────────────────────────
# PRESENTACION_MORA_TARDIA la usa como REGLA DE DECISION, no como dato de guion:
#   monto_adeudado_ars == monto_vencido_ars  -> no hubo pago desde la ultima gestion
#   monto_adeudado_ars != monto_vencido_ars  -> hubo pago parcial
# El ETL la calculaba internamente (fallback de MontoAdeudado) y la descartaba.


def _build_vencido_df(filas: list[tuple]) -> pd.DataFrame:
    """(cuil, operacion, producto, adeudado, vencido, celular, fijo)."""
    registros = []
    for cuil, operacion, producto, adeudado, vencido, celular, fijo in filas:
        registros.append(
            {
                "CUIL": cuil,
                "Cliente_BT": f"CLI{cuil[-3:]}",
                "ClienteNombre": "Cliente Vencido",
                "NumeroDocumento": "30111222",
                "NumeroTelefono": fijo,
                "NumeroCelular": celular,
                "Mail": "cliente@correo.com",
                "Nro Cuenta": "12345",
                "Cuenta": "CTA",
                "Estado Cuenta": "Vigente",
                "Campaña_REF": "CAMPANA30",
                "TipoAsignacion": "NORMAL",
                "AgrupadorProducto": producto,
                "NumeroOperacion": operacion,
                "MontoAdeudado": adeudado,
                "MontoVencido": vencido,
                "OFERTA_Importe": "",
                "AnticipoMinimo": 1_000,
                "Dias_Mora": 200,
            }
        )
    return pd.DataFrame(registros)


def test_monto_vencido_ars_esta_en_el_contrato_y_al_final() -> None:
    assert "monto_vencido_ars" in ROMAN_OUTPUT_COLUMNS
    assert ROMAN_OUTPUT_COLUMNS[-1] == "monto_vencido_ars"
    # No movio ningun indice posicional existente.
    assert ROMAN_OUTPUT_COLUMNS[19:21] == ["monto_total_oferta", "alcance_oferta"]


def test_monto_vencido_ars_se_emite_con_el_formato_de_monto_adeudado(tmp_path: Path) -> None:
    filas = [("20555555551", "OPV-1", "Prestamo", 100_000, 100_000, "5493517300001", "3521-441531")]
    artifact = pipeline_wfm._generar_csv_roman(_build_vencido_df(filas), tmp_path, "20260904")
    assert artifact["status"] == "generated", artifact.get("error")

    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    fila = df.iloc[0]
    assert fila["monto_vencido_ars"] == "100000"
    assert fila["monto_vencido_ars"] == fila["monto_adeudado_ars"]


def test_monto_vencido_ars_distingue_pago_parcial(tmp_path: Path) -> None:
    """El caso que la regla del flow tiene que poder detectar."""
    filas = [
        # Sin pago: vencido == adeudado.
        ("20555555551", "OPV-1", "Prestamo", 100_000, 100_000, "5493517300001", "3521-441531"),
        # Con pago parcial: vencido < adeudado.
        ("20555555552", "OPV-2", "Tarjeta", 100_000, 60_000, "5493517300002", "3521-441532"),
    ]
    artifact = pipeline_wfm._generar_csv_roman(_build_vencido_df(filas), tmp_path, "20260904")
    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    sin_pago = df.loc[df["id_cuil"] == "20555555551"].iloc[0]
    con_pago = df.loc[df["id_cuil"] == "20555555552"].iloc[0]
    assert sin_pago["monto_vencido_ars"] == sin_pago["monto_adeudado_ars"]
    assert con_pago["monto_vencido_ars"] != con_pago["monto_adeudado_ars"]
    assert con_pago["monto_vencido_ars"] == "60000"


def test_monto_vencido_ars_se_consolida_sumando_los_productos(tmp_path: Path) -> None:
    """MontoVencido es a nivel producto: emitir grupo.iloc[0] daria un falso pago parcial.

    El 38 % de los CUIL de la base real son multiproducto, y en el 100 % de ellos el
    primer producto difiere de la suma.
    """
    filas = [
        ("20555555553", "OPV-A", "Prestamo", 60_000, 40_000, "5493517300003", "3521-441533"),
        ("20555555553", "OPV-B", "Tarjeta", 40_000, 60_000, "5493517300003", "3521-441533"),
    ]
    artifact = pipeline_wfm._generar_csv_roman(_build_vencido_df(filas), tmp_path, "20260904")
    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    assert len(df) == 1
    fila = df.iloc[0]
    assert fila["monto_adeudado_ars"] == "100000"
    # Suma de los dos productos, no el primero (que seria 40000).
    assert fila["monto_vencido_ars"] == "100000"


def test_validar_roman_advierte_vencido_mayor_al_adeudado(tmp_path: Path) -> None:
    filas = [("20555555554", "OPV-X", "Prestamo", 50_000, 80_000, "5493517300004", "3521-441534")]
    artifact = pipeline_wfm._generar_csv_roman(_build_vencido_df(filas), tmp_path, "20260904")
    path_csv = Path(artifact["path"])

    df = pd.read_csv(path_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    assert df.loc[0, "monto_vencido_ars"] == "80000"
    assert df.loc[0, "monto_adeudado_ars"] == "50000"

    warnings = pipeline_wfm._validar_variables_roman_obligatorias(path_csv)
    assert any(
        "CUIL 20555555554 tiene monto_vencido_ars mayor al monto adeudado" in warning
        for warning in warnings
    )


def test_validar_roman_no_advierte_cuando_vencido_es_consistente(tmp_path: Path) -> None:
    filas = [
        ("20555555551", "OPV-1", "Prestamo", 100_000, 100_000, "5493517300001", "3521-441531"),
        ("20555555552", "OPV-2", "Tarjeta", 100_000, 60_000, "5493517300002", "3521-441532"),
    ]
    artifact = pipeline_wfm._generar_csv_roman(_build_vencido_df(filas), tmp_path, "20260904")
    warnings = pipeline_wfm._validar_variables_roman_obligatorias(Path(artifact["path"]))
    assert not any("monto_vencido_ars mayor" in warning for warning in warnings)


def test_monto_vencido_ars_vacio_si_la_base_no_lo_trae(tmp_path: Path) -> None:
    """Bases sin MontoVencido no rompen el contrato: la columna sale vacia."""
    artifact = pipeline_wfm._generar_csv_roman(_build_multiproduct_offer_df(), tmp_path, "20260810")
    df = pd.read_csv(Path(artifact["path"]), sep=";", encoding="utf-8", dtype=str, keep_default_na=False)

    assert list(df.columns) == ROMAN_OUTPUT_COLUMNS
    assert set(df["monto_vencido_ars"]) == {""}
