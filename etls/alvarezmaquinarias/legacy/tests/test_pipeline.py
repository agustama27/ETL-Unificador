"""Test end-to-end del ETL sobre los datos fake "sucios" de
scripts/generate_sample_data.py, que replican la estructura real de
Autologica (header corrido, ID de cliente, subtotales de pivot, PDF de
repuestos) — ver docs/SPEC.md.

Cubre las reglas de negocio críticas: consolidación multi-fuente,
    aislamiento de registros USD y exclusión de ARS,
prioridad, días de mora, descarte explícito de filas inválidas y
exclusión de teléfonos inválidos del listado Approach.
"""

from datetime import date, datetime
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_sample_data import (
    _maquinarias_rows,
    _remitos_servicios_sheets,
    _saldos_generales_rows,
    _write_remitos_repuestos_pdf,
    _write_xls,
    _write_xlsx,
)
from src.etl import schema
from src.etl.config import PipelineConfig
from src.etl.loaders import ApproachLoader, RomanCsvLoader
from src.etl.pipeline import extract, load, run_pipeline, transform, verify_phone_parity
from src.etl.transformers import (
    ClientPhoneDirectory,
    build_detail,
    consolidate_by_client,
    resolve_duplicate_clients,
)
from src.etl.utils import classify_currency_from_flag, parse_currency_amount

REFERENCE_DATE = date(2026, 7, 28)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_xls(raw / "saldos.xls", _saldos_generales_rows())
    _write_xlsx(raw / "ia.xlsx", {"Sheet1": _maquinarias_rows()})
    _write_xlsx(raw / "servicios.xlsx", _remitos_servicios_sheets())
    _write_remitos_repuestos_pdf(raw / "repuestos.pdf")
    return raw


@pytest.fixture
def config(raw_dir: Path, tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        saldos_generales_path=raw_dir / "saldos.xls",
        maquinarias_path=raw_dir / "ia.xlsx",
        remitos_repuestos_path=raw_dir / "repuestos.pdf",
        remitos_servicios_path=raw_dir / "servicios.xlsx",
        output_dir=tmp_path / "output",
        reference_date=REFERENCE_DATE,
    )


def test_extract_localiza_header_corrido_y_descarta_filas_invalidas(config: PipelineConfig):
    result = extract(config)
    # saldos generales: 11 filas de datos (1 sin cliente, ignorada; 1 monto invalido, descartada) -> quedan 9 validas
    assert len(result.saldos_generales) == 9
    # maquinarias: 4 filas (1 monto invalido, descartada) -> quedan 3 validas
    assert len(result.maquinarias) == 3
    # repuestos PDF: solo la línea USD entra; ARS se excluye en extracción.
    assert len(result.remitos_repuestos) == 1
    assert result.diagnostics.excluded_ars_by_source == {
        schema.FUENTE_SALDOS_GENERALES: 0,
        schema.FUENTE_MAQUINARIAS: 0,
        schema.FUENTE_REMITOS_REPUESTOS: 1,
        schema.FUENTE_REMITOS_SERVICIOS: 0,
    }
    # servicios: 6 filas de detalle en 2 hojas (subtotales ignorados) -> quedan 6
    assert len(result.remitos_servicios) == 6


def test_saldos_generales_captura_id_autologica(config: PipelineConfig):
    result = extract(config)
    fila = result.saldos_generales[
        result.saldos_generales[schema.COL_CLIENTE_RAW] == "AGRO GANADERA FAKE S.A."
    ].iloc[0]
    assert fila[schema.COL_CLIENTE_ID] == "101"


def test_consolida_cliente_presente_en_tres_fuentes(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    fila = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "AGRO GANADERA FAKE S.A."
    ].iloc[0]

    # Todas las filas admitidas ya vienen en USD y conservan su importe.
    esperado = round(150000.00 + 12000.00 + 545.10, 2)
    assert fila[schema.OUT_SALDO_EXIGIBLE_USD] == pytest.approx(esperado, abs=0.01)
    # el desglose por deuda va en el array Productos "producto:monto;..."
    assert fila[schema.OUT_CANTIDAD_PRODUCTOS] == 3
    assert "NH 8030:12000.00" in fila[schema.OUT_PRODUCTOS]
    assert "Cuenta Corriente:150000.00" in fila[schema.OUT_PRODUCTOS]


def test_deudas_de_remitos_se_consolidan_en_una_entrada_por_categoria(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    fila = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "AGROPECUARIA DEL SUR"
    ].iloc[0]

    # dos remitos de servicios (387.20 + 242.00): la fuente no distingue el
    # concepto, asi que van sumados en una sola entrada, no repetidos
    assert fila[schema.OUT_PRODUCTOS] == "Cuenta Corriente:25000.00;Servicios:629.20"
    assert fila[schema.OUT_CANTIDAD_PRODUCTOS] == 2
    # consolidar el array no altera el saldo total: sigue siendo la suma de todo
    assert fila[schema.OUT_SALDO_EXIGIBLE_USD] == pytest.approx(25629.20, abs=0.01)


def test_productos_con_detalle_real_no_se_consolidan(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)

    fila = transformed.consolidado[
        transformed.consolidado[schema.OUT_NOMBRE_APELLIDO] == "AGRO GANADERA FAKE S.A."
    ].iloc[0]

    # cuenta corriente y maquinaria traen producto real: siguen como entradas
    # separadas aunque el cliente tenga ademas un repuesto
    assert "Cuenta Corriente:150000.00" in fila[schema.OUT_PRODUCTOS]
    assert "NH 8030:12000.00" in fila[schema.OUT_PRODUCTOS]
    assert fila[schema.OUT_CANTIDAD_PRODUCTOS] == 3


def test_columna_productos_remitos_marca_solo_lo_originado_en_remitos(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    con_remito = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "AGRO GANADERA FAKE S.A."
    ].iloc[0]
    assert con_remito[schema.OUT_PRODUCTOS_REMITOS] == "Repuestos:545.10"

    # sin deuda de remitos -> campo vacio, no ausente: el marcado es consistente
    # para todas las filas y sirve como filtro de segmentacion
    sin_remito = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "ESTABLECIMIENTO EL EJEMPLO"
    ].iloc[0]
    assert sin_remito[schema.OUT_PRODUCTOS_REMITOS] == ""

    # todo lo marcado como remito aparece tal cual dentro del array Productos
    for _, fila in consolidado.iterrows():
        for entrada in filter(None, fila[schema.OUT_PRODUCTOS_REMITOS].split(";")):
            assert entrada in fila[schema.OUT_PRODUCTOS]


def test_nombre_truncado_por_el_ancho_de_columna_se_une_al_completo(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    # servicios trae "CONSTRUCTORA LOS ALAMOS SOC" (27 car, el techo de esa
    # fuente); saldos trae el nombre completo. Es un solo cliente.
    filas = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO].str.startswith("CONSTRUCTORA LOS ALAMOS")
    ]
    assert len(filas) == 1
    fila = filas.iloc[0]
    assert fila[schema.OUT_NOMBRE_APELLIDO] == "CONSTRUCTORA LOS ALAMOS SOCIEDAD ANONIMA"
    assert fila[schema.OUT_SALDO_EXIGIBLE_USD] == pytest.approx(4000.00 + 605.00, abs=0.01)
    # gana la variante con ID de Autologica: es el sistema de registro
    assert str(fila[schema.OUT_CLIENTE_ID]) == "107"


def test_errata_de_una_letra_con_mismo_telefono_se_une(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    # "GOMES ANDRES" (maquinarias) y "GOMEZ ANDRES" (saldos) comparten linea
    filas = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO].str.contains("ANDRES", na=False)
    ]
    assert len(filas) == 1
    assert filas.iloc[0][schema.OUT_SALDO_EXIGIBLE_USD] == pytest.approx(5900.00, abs=0.01)


def test_prefijo_sin_truncamiento_no_fusiona_deudores_distintos(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    # "PEREZ JUAN" es prefijo de "PEREZ JUAN Y HERMANOS SH", pero ninguno de
    # los dos nombres fue cortado (miden 10 y 24 car, lejos del techo de su
    # fuente): son la persona y la sociedad de hecho, dos deudores distintos.
    nombres = set(
        consolidado[
            consolidado[schema.OUT_NOMBRE_APELLIDO].str.startswith("PEREZ JUAN")
        ][schema.OUT_NOMBRE_APELLIDO]
    )
    assert nombres == {"PEREZ JUAN", "PEREZ JUAN Y HERMANOS SH"}


def test_repuestos_pdf_separa_codigo_pegado_al_nombre(tmp_path: Path):
    """La extracción de texto del PDF pega el código de cliente al nombre
    (`111FERRARESE MARTIN`); el adapter lo separa validando contra el
    nombre limpio del subtotal y lo captura como ID de Autologica."""
    pdf = tmp_path / "repuestos.pdf"
    _write_remitos_repuestos_pdf(pdf, [
        "Remito Cliente Detalles Fecha Precio IVA 21% Total Factura relacionada",
        "Cliente: CLIENTE PEGADO SRLRecuento: 1",
        "755 111CLIENTE PEGADO SRLREPUESTOS 15/07/2026  $45,39  $9,53  $54,92PRECIO EN DOLARES",
        # nombre que empieza con digitos: solo el subtotal permite separarlo bien
        "Cliente: 3 MARIAS SARecuento: 1",
        "801 105 3 MARIAS SAREPUESTOS 16/07/2026  $10,00  $2,10  $12,10PRECIO EN DOLARES",
        # sin codigo pegado (formato viejo): queda como esta, sin ID
        "Cliente: SIN CODIGO SASRecuento: 1",
        "802 SIN CODIGO SASREPUESTOS 17/07/2026  $20,00  $4,20  $24,20PRECIO EN DOLARES",
    ])

    from src.etl.extractors import RemitosRepuestosExtractor
    rows = RemitosRepuestosExtractor().extract(pdf).rows

    por_remito = {r[schema.COL_REMITO]: r for _, r in rows.iterrows()}
    assert por_remito["755"][schema.COL_CLIENTE_RAW] == "CLIENTE PEGADO SRL"
    assert por_remito["755"][schema.COL_CLIENTE_ID] == "111"
    assert por_remito["801"][schema.COL_CLIENTE_RAW] == "3 MARIAS SA"
    assert por_remito["801"][schema.COL_CLIENTE_ID] == "105"
    assert por_remito["802"][schema.COL_CLIENTE_RAW] == "SIN CODIGO SAS"
    assert por_remito["802"][schema.COL_CLIENTE_ID] is None


def test_servicios_formato_plano_toma_nombre_y_codigo(tmp_path: Path):
    """El export plano de servicios trae `Remito | Código | Cliente`; el
    código es el ID de Autologica, no el nombre."""
    xlsx = tmp_path / "servicios.xlsx"
    _write_xlsx(xlsx, {"Remitos Servicios": [
        ["Nº Remito", "Código", "Cliente", "Detalles", "Fecha ", "Precio", "IVA 21%", "Total"],
        ["7850", "111", "CLIENTE PLANO SRL", None, datetime(2026, 7, 27), 1000.85, 210.18, 1211.03],
        ["7885", "1707", "OTRO CLIENTE SA", "nota libre", datetime(2026, 7, 28), 100, 21, 121],
    ]})

    from src.etl.extractors import RemitosServiciosExtractor
    rows = RemitosServiciosExtractor().extract(xlsx).rows

    assert list(rows[schema.COL_CLIENTE_RAW]) == ["CLIENTE PLANO SRL", "OTRO CLIENTE SA"]
    assert list(rows[schema.COL_CLIENTE_ID]) == ["111", "1707"]
    assert list(rows[schema.COL_MONTO_ORIGINAL]) == [1211.03, 121.0]


def test_repuesto_ars_se_excluye_antes_de_transformar_o_consolidar(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)

    assert "moneda_original" not in extracted.remitos_repuestos.columns
    assert "1503" not in set(transformed.detalle[schema.COL_REMITO].astype(str))
    assert "DISTRIBUIDORA NORTE SRL" not in set(
        transformed.consolidado[schema.OUT_NOMBRE_APELLIDO]
    )


def test_ars_only_repuestos_do_not_reach_roman_or_e1kia(config: PipelineConfig) -> None:
    _write_remitos_repuestos_pdf(
        config.remitos_repuestos_path,
        lines=[
            "1701 CLIENTE ARS SINTETICO REPUESTOS 15/07/2026  $450,50  $94,60  $545,10Factura relacionada",
        ],
    )

    extracted = extract(config)
    result = run_pipeline(config)
    roman = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")
    approach = pd.read_csv(result.approach_path, sep=";", encoding="utf-8")

    assert extracted.remitos_repuestos.empty
    assert extracted.diagnostics.excluded_ars_by_source[schema.FUENTE_REMITOS_REPUESTOS] == 1
    assert "CLIENTE ARS SINTETICO" not in set(roman[schema.OUT_NOMBRE_APELLIDO])
    assert "Repuestos:545.10" not in set(roman[schema.OUT_PRODUCTOS])
    assert set(approach[schema.OUT_TELEFONO_CLIENTE]) == set(
        roman[schema.OUT_TELEFONO_CLIENTE].dropna()
    )


def test_unknown_currency_repuestos_do_not_reach_outputs(config: PipelineConfig) -> None:
    _write_remitos_repuestos_pdf(
        config.remitos_repuestos_path,
        lines=[
            "1702 CLIENTE DESCONOCIDO SINTETICO REPUESTOS 15/07/2026  $450,50  $94,60  $545,10MONEDA OTRA",
        ],
    )

    extracted = extract(config)
    result = run_pipeline(config)
    roman = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")

    assert extracted.remitos_repuestos.empty
    assert extracted.diagnostics.excluded_unknown_by_source[schema.FUENTE_REMITOS_REPUESTOS] == 1
    assert "CLIENTE DESCONOCIDO SINTETICO" not in set(roman[schema.OUT_NOMBRE_APELLIDO])
    assert "CLIENTE DESCONOCIDO SINTETICO" not in result.diagnostics.summary()


def test_exclusion_diagnostics_are_aggregate_and_non_identifying(
    config: PipelineConfig, caplog: pytest.LogCaptureFixture
):
    caplog.set_level("WARNING")
    result = run_pipeline(config)

    diagnostic = result.diagnostics.summary()
    assert diagnostic == (
        "ARS excluidos: maquinarias=0, remitos_repuestos=1, "
        "remitos_servicios=0, saldos_generales=0"
    )
    assert diagnostic in caplog.text
    assert "1503" not in diagnostic
    assert "102.85" not in diagnostic
    assert "DISTRIBUIDORA" not in diagnostic


def test_zero_ars_exclusions_are_reported_explicitly(config: PipelineConfig) -> None:
    _write_remitos_repuestos_pdf(
        config.remitos_repuestos_path,
        lines=[
            "1703 CLIENTE USD SINTETICO REPUESTOS 15/07/2026  $450,50  $94,60  $545,10PRECIO EN DOLARES",
        ],
    )

    result = run_pipeline(config)

    assert result.diagnostics.summary() == (
        "ARS excluidos: maquinarias=0, remitos_repuestos=0, "
        "remitos_servicios=0, saldos_generales=0"
    )


def test_pipeline_warnings_do_not_expose_source_row_values(
    config: PipelineConfig, caplog: pytest.LogCaptureFixture
):
    caplog.set_level("WARNING")
    run_pipeline(config)

    assert "CLIENTE MONTO INVALIDO" not in caplog.text
    assert "no-es-numero" not in caplog.text
    assert "1504" not in caplog.text


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("PRECIO EN DOLARES", "USD"), ("Factura relacionada", "ARS"), ("MONEDA OTRA", "UNKNOWN")],
)
def test_currency_classifier_accepts_only_explicit_usd_flags(flag: str, expected: str):
    assert classify_currency_from_flag(flag) == expected


def test_telefono_alternativo_se_usa_si_el_principal_es_invalido(config: PipelineConfig):
    extracted = extract(config)
    fila = extracted.maquinarias[
        extracted.maquinarias[schema.COL_CLIENTE_RAW] == "ESTABLECIMIENTO EL EJEMPLO"
    ].iloc[0]
    assert fila[schema.COL_TELEFONO_RAW] == "3537555666"


def test_consolidado_ordenado_por_prioridad_y_saldo(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    flags = list(transformed.consolidado[schema.OUT_FLAG_PRIORIDAD])
    assert flags == sorted(flags, reverse=True)


def test_telefono_invalido_excluido_de_approach_pero_presente_en_roman(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    logistica = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "LOGISTICA BELL VILLE SRL"
    ].iloc[0]
    assert pd.isna(logistica[schema.OUT_TELEFONO_CLIENTE])

    result = load(transformed, config)
    roman_consolidado = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")
    assert "LOGISTICA BELL VILLE SRL" in set(roman_consolidado[schema.OUT_NOMBRE_APELLIDO])

    # el E1KIA solo trae telefonos, asi que la exclusion se comprueba por
    # conteo: el cliente sin telefono valido no aporta ninguna fila
    approach = pd.read_csv(result.approach_path, sep=";", encoding="utf-8")
    llamables = roman_consolidado[schema.OUT_TELEFONO_CLIENTE].dropna()
    assert len(approach) == llamables.nunique()


def test_telefono_en_formato_internacional_celular(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)
    consolidado = transformed.consolidado

    fila = consolidado[
        consolidado[schema.OUT_NOMBRE_APELLIDO] == "AGROPECUARIA DEL SUR"
    ].iloc[0]
    # 3516541234 (10 digitos) -> 549 + numero nacional
    assert fila[schema.OUT_TELEFONO_CLIENTE] == "5493516541234"


@pytest.mark.parametrize(
    ("target", "prefijo"),
    [
        ("roman_path", "ALVAREZ_MAQUINARIAS_ROMAN"),
        ("approach_path", "ALVAREZ_MAQUINARIAS_E1KIA"),
    ],
)
def test_exports_usan_el_naming_pedido_por_cada_consumidor(
    config: PipelineConfig, target: str, prefijo: str
):
    config = replace(config, run_date=date(2026, 8, 4))
    result = run_pipeline(config)

    # <PREFIJO>_YYMMDD.csv con la fecha de la particion, no la de calculo
    assert getattr(result, target).name == f"{prefijo}_260804.csv"


@pytest.mark.parametrize("target", ["roman_path", "approach_path"])
def test_exports_usan_el_formato_de_intercambio_acordado(config: PipelineConfig, target: str):
    result = run_pipeline(config)

    crudo = getattr(result, target).read_bytes()
    # UTF-8 sin BOM: el consumidor pidio ASCII/UTF-8, un BOM rompe ambos
    assert not crudo.startswith(b"\xef\xbb\xbf")
    texto = crudo.decode("utf-8")
    # CRLF en todas las lineas, sin ningun LF suelto
    assert texto.endswith("\r\n")
    assert texto.count("\n") == texto.count("\r\n")

    header = texto.split("\r\n")[0]
    esperado = (
        [schema.OUT_TELEFONO_CLIENTE]
        if target == "approach_path"
        else schema.OUTPUT_COLUMNS
    )
    assert header.split(";") == esperado


def test_roman_empaqueta_productos_en_una_columna_entrecomillada(config: PipelineConfig):
    result = run_pipeline(config)
    roman = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")
    assert schema.OUT_PRODUCTOS in roman.columns
    assert schema.OUT_SALDO_EXIGIBLE_USD in roman.columns

    # el array empaqueta cada deuda como "producto:monto" separadas por ;
    fila = roman[roman[schema.OUT_NOMBRE_APELLIDO] == "AGRO GANADERA FAKE S.A."].iloc[0]
    assert fila[schema.OUT_PRODUCTOS].count(";") == fila[schema.OUT_CANTIDAD_PRODUCTOS] - 1

    # ese ; interno colisiona con el separador: el campo DEBE ir entrecomillado
    # o un parser CSV lo partiria en columnas de mas.
    # Se lee por bytes: read_text() traduce CRLF a LF y disimularia el formato.
    crudo = result.roman_path.read_bytes().decode("utf-8")
    multi = roman[roman[schema.OUT_CANTIDAD_PRODUCTOS] > 1].iloc[0]
    assert f'"{multi[schema.OUT_PRODUCTOS]}"' in crudo
    # y todas las filas siguen siendo filas: el ; entrecomillado no agrega columnas
    assert len(crudo.rstrip("\r\n").split("\r\n")) == len(roman) + 1


def test_e1kia_lista_una_sola_vez_un_telefono_compartido(config: PipelineConfig):
    result = run_pipeline(config)
    roman = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")
    approach = pd.read_csv(result.approach_path, sep=";", encoding="utf-8")

    # dos clientes distintos del Roman comparten linea (ver fixture)
    compartido = roman[roman[schema.OUT_TELEFONO_CLIENTE] == 5493516541234]
    assert len(compartido) == 2
    assert set(compartido[schema.OUT_NOMBRE_APELLIDO]) == {
        "AGROPECUARIA DEL SUR",
        "CAMPO VERDE SRL",
    }

    # ...pero la plataforma marca numeros, no clientes: una sola fila
    tel = approach[schema.OUT_TELEFONO_CLIENTE]
    assert (tel == 5493516541234).sum() == 1
    assert tel.is_unique


def test_e1kia_y_roman_cubren_el_mismo_universo_de_telefonos(config: PipelineConfig):
    result = run_pipeline(config)
    roman = pd.read_csv(result.roman_path, sep=";", encoding="utf-8")
    approach = pd.read_csv(result.approach_path, sep=";", encoding="utf-8")

    assert set(approach[schema.OUT_TELEFONO_CLIENTE]) == set(
        roman[schema.OUT_TELEFONO_CLIENTE].dropna()
    )


def test_load_falla_antes_de_escribir_si_se_rompe_la_paridad(config: PipelineConfig):
    extracted = extract(config)
    transformed = transform(extracted, config)

    # el Roman pierde un telefono que el marcador si tiene: la corrida debe
    # abortar sin dejar archivos parciales
    mutilado = transformed.consolidado.copy()
    llamable = mutilado[schema.OUT_TELEFONO_CLIENTE].notna().idxmax()
    mutilado.loc[llamable, schema.OUT_TELEFONO_CLIENTE] = None

    with pytest.raises(ValueError, match="no coinciden"):
        verify_phone_parity(
            mutilado,
            ApproachLoader().rows_to_export(transformed.consolidado),
        )


def test_run_pipeline_genera_ambos_archivos(config: PipelineConfig):
    result = run_pipeline(config)
    assert result.roman_path.exists()
    assert result.approach_path.exists()

    approach = pd.read_csv(result.approach_path, sep=";", encoding="utf-8")
    # el marcador es una sola columna: el telefono y nada mas
    assert list(approach.columns) == [schema.OUT_TELEFONO_CLIENTE]
    assert approach[schema.OUT_TELEFONO_CLIENTE].notna().all()
    # todos los telefonos del Approach en formato internacional de celular
    assert approach[schema.OUT_TELEFONO_CLIENTE].astype(str).str.startswith("549").all()


@pytest.mark.parametrize(
    ("existing_target", "other_target"),
    [
        ("roman_output_path", "approach_output_path"),
        ("approach_output_path", "roman_output_path"),
    ],
)
def test_run_pipeline_preserves_both_exports_when_one_target_exists(
    config: PipelineConfig, existing_target: str, other_target: str
):
    config.output_dir.mkdir()
    existing_path = getattr(config, existing_target)
    existing_path.write_text("no reemplazar", encoding="utf-8")

    with pytest.raises(FileExistsError, match=existing_path.name):
        run_pipeline(config)

    assert existing_path.read_text(encoding="utf-8") == "no reemplazar"
    assert not getattr(config, other_target).exists()


@pytest.mark.parametrize(
    "existing_target",
    ["roman_output_path", "approach_output_path"],
)
def test_run_pipeline_overwrites_existing_partition_exports_when_explicit(
    config: PipelineConfig, existing_target: str
):
    config = replace(config, overwrite=True)
    config.output_dir.mkdir()
    existing_path = getattr(config, existing_target)
    existing_path.write_text("no reemplazar", encoding="utf-8")

    result = run_pipeline(config)

    assert existing_path.read_bytes() != b"no reemplazar"
    assert result.roman_path.exists()
    assert result.approach_path.exists()


@pytest.mark.parametrize("loader", [RomanCsvLoader, ApproachLoader])
def test_loaders_require_a_prepared_destination_directory(tmp_path: Path, loader):
    destination = tmp_path / "missing" / "export.csv"
    consolidado = pd.DataFrame({schema.OUT_TELEFONO_CLIENTE: ["5493516541234"]})

    with pytest.raises(OSError):
        loader().save(consolidado, destination)

    assert not destination.parent.exists()


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        # convención inglesa: la coma agrupa miles, el punto decimal. Es lo que
        # trae el export CSV de saldos y lo que producía el error de escala
        # /1000 (17,264.70 se leía 17,2647).
        ("17,264.70", 17264.70),
        ("13,373.02", 13373.02),
        ("1,020,500.25", 1020500.25),
        # convención argentina: el punto agrupa miles, la coma decimal
        ("17.264,70", 17264.70),
        ("1.020.500,25", 1020500.25),
        ("853,01", 853.01),
        ("965,47", 965.47),
        # un solo separador con grupos de tres digitos exactos: son miles
        ("17.264", 17264.0),
        ("17,264", 17264.0),
        ("1.020.500", 1020500.0),
        # un solo separador que no agrupa de a tres: es decimal
        ("965.47", 965.47),
        ("17.26", 17.26),
        ("0.5", 0.5),
        ("-1.234,50", -1234.50),
        ("-17.264", -17264.0),
        # numero nativo y prefijos de moneda: sin cambios
        (17264.70, 17264.70),
        ("USD 850,00", 850.00),
        ("$1.200,50", 1200.50),
        ("", None),
        ("no-es-numero", None),
    ],
)
def test_parse_currency_desambigua_la_convencion_por_la_forma(crudo, esperado):
    """Las fuentes mezclan convención AR e inglesa en el mismo archivo, así
    que no se puede deducir del origen: manda la forma del valor."""
    resultado = parse_currency_amount(crudo)
    if esperado is None:
        assert resultado is None
    else:
        assert resultado == pytest.approx(esperado, abs=0.001)


def _fila_canonica(overrides: dict) -> dict:
    """Fila canónica mínima para armar escenarios sin pasar por los adapters."""
    fila = {
        schema.COL_CLIENTE_RAW: "CLIENTE EJEMPLO",
        schema.COL_CLIENTE_KEY: "CLIENTE EJEMPLO",
        schema.COL_CLIENTE_ID: None,
        schema.COL_TELEFONO_RAW: None,
        schema.COL_PRODUCTO: "Cuenta Corriente",
        schema.COL_CONCEPTO: "Cuenta Corriente",
        schema.COL_FECHA: date(2026, 7, 1),
        schema.COL_REMITO: "CD1",
        schema.COL_MONTO_ORIGINAL: 100.0,
        schema.COL_DIAS_MORA_FUENTE: None,
        schema.COL_PRIORIDAD_RAW: None,
        schema.COL_FUENTE: schema.FUENTE_SALDOS_GENERALES,
    }
    fila.update(overrides)
    return fila


def _consolidar(filas: list[dict], config: PipelineConfig) -> pd.DataFrame:
    """Mismo orden que pipeline.transform, sobre filas armadas a mano."""
    canonico = pd.DataFrame(filas, columns=schema.CANONICAL_COLUMNS)
    directorio = ClientPhoneDirectory()
    directorio.register(
        [canonico], config.telefono_min_digitos, config.telefono_max_digitos
    )
    detalle = resolve_duplicate_clients(build_detail([canonico], directorio, config))
    return consolidate_by_client(detalle, directorio)


@pytest.mark.parametrize("invertir", [False, True])
def test_telefono_usable_le_gana_al_local_pelado_sin_importar_el_orden(
    config: PipelineConfig, invertir: bool
):
    """El local de 8 dígitos entra al maestro pero no sirve para la salida.
    Con first-wins bloqueaba al nacional de 10 y el cliente salía sin
    teléfono teniendo uno bueno."""
    filas = [
        _fila_canonica({
            schema.COL_TELEFONO_RAW: "4664944",
            schema.COL_FUENTE: schema.FUENTE_SALDOS_GENERALES,
        }),
        _fila_canonica({
            schema.COL_TELEFONO_RAW: "2364664944",
            schema.COL_FUENTE: schema.FUENTE_MAQUINARIAS,
        }),
    ]
    if invertir:
        filas.reverse()

    consolidado = _consolidar(filas, config)

    assert len(consolidado) == 1
    assert consolidado.iloc[0][schema.OUT_TELEFONO_CLIENTE] == "5492364664944"


def test_entre_dos_telefonos_usables_la_salida_es_deterministica(config: PipelineConfig):
    filas = [
        _fila_canonica({schema.COL_TELEFONO_RAW: "2364664944"}),
        _fila_canonica({
            schema.COL_TELEFONO_RAW: "3385464768",
            schema.COL_FUENTE: schema.FUENTE_MAQUINARIAS,
        }),
    ]

    primero = _consolidar(filas, config).iloc[0][schema.OUT_TELEFONO_CLIENTE]
    filas.reverse()
    segundo = _consolidar(filas, config).iloc[0][schema.OUT_TELEFONO_CLIENTE]

    assert primero == "5492364664944"
    # no oscila entre validos: gana el primero que aparece en cada corrida
    assert segundo == "5493385464768"


def test_unico_telefono_de_8_digitos_sigue_saliendo_vacio(config: PipelineConfig):
    """Sin un nacional de 10 dígitos no hay a quién llamar: el
    comportamiento actual es correcto y no debe cambiar."""
    consolidado = _consolidar(
        [_fila_canonica({schema.COL_TELEFONO_RAW: "4664944"})], config
    )

    assert pd.isna(consolidado.iloc[0][schema.OUT_TELEFONO_CLIENTE])


def test_mismo_id_de_autologica_fusiona_aunque_el_nombre_tenga_errata(
    config: PipelineConfig,
):
    """Caso real de la corrida 12/08: FINOCCHI/FINOCHI divergen en el
    caracter 5 (ninguno es prefijo del otro) y ninguna de las dos filas trae
    teléfono, así que ni truncamiento ni telefono+errata los ven. El ID de
    Autologica sí."""
    filas = [
        _fila_canonica({
            schema.COL_CLIENTE_RAW: "FINOCCHI RICARDO HUGO E HIJOS SRL",
            schema.COL_CLIENTE_KEY: "FINOCCHI RICARDO HUGO E HIJOS",
            schema.COL_CLIENTE_ID: "1241",
            schema.COL_MONTO_ORIGINAL: 924.59,
        }),
        _fila_canonica({
            schema.COL_CLIENTE_RAW: "FINOCHI RICARDO HUGO E HIJOS SRL",
            schema.COL_CLIENTE_KEY: "FINOCHI RICARDO HUGO E HIJOS",
            schema.COL_CLIENTE_ID: "1241",
            schema.COL_PRODUCTO: "Repuestos",
            schema.COL_MONTO_ORIGINAL: 351.08,
            schema.COL_FUENTE: schema.FUENTE_REMITOS_REPUESTOS,
        }),
    ]

    consolidado = _consolidar(filas, config)

    assert len(consolidado) == 1
    fila = consolidado.iloc[0]
    assert fila[schema.OUT_SALDO_EXIGIBLE_USD] == pytest.approx(1275.67, abs=0.01)
    assert "Cuenta Corriente:924.59" in fila[schema.OUT_PRODUCTOS]
    assert "Repuestos:351.08" in fila[schema.OUT_PRODUCTOS]
    assert str(fila[schema.OUT_CLIENTE_ID]) == "1241"


def test_ids_de_autologica_distintos_no_fusionan_aunque_el_nombre_sea_parecido(
    config: PipelineConfig,
):
    filas = [
        _fila_canonica({
            schema.COL_CLIENTE_RAW: "FINOCCHI RICARDO HUGO E HIJOS SRL",
            schema.COL_CLIENTE_KEY: "FINOCCHI RICARDO HUGO E HIJOS",
            schema.COL_CLIENTE_ID: "1241",
        }),
        _fila_canonica({
            schema.COL_CLIENTE_RAW: "FINOCHI RICARDO HUGO E HIJOS SRL",
            schema.COL_CLIENTE_KEY: "FINOCHI RICARDO HUGO E HIJOS",
            schema.COL_CLIENTE_ID: "1242",
            schema.COL_FUENTE: schema.FUENTE_MAQUINARIAS,
        }),
    ]

    assert len(_consolidar(filas, config)) == 2


def test_run_pipeline_uses_fixed_exports_in_selected_dated_partition(tmp_path: Path):
    run_date = date(2026, 7, 28)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    input_dir.mkdir(parents=True)
    _write_xls(input_dir / "saldos.xls", _saldos_generales_rows())
    _write_xlsx(input_dir / "maquinarias.xlsx", {"Sheet1": _maquinarias_rows()})
    _write_xlsx(input_dir / "servicios.xlsx", _remitos_servicios_sheets())
    _write_remitos_repuestos_pdf(input_dir / "repuestos.pdf")
    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=REFERENCE_DATE,
        overwrite=False,
    )

    result = run_pipeline(config)

    partition = tmp_path / "outputs" / "2026-07-28"
    assert result.roman_path == partition / "ALVAREZ_MAQUINARIAS_ROMAN_260728.csv"
    assert result.approach_path == partition / "ALVAREZ_MAQUINARIAS_E1KIA_260728.csv"
    assert result.roman_path.exists()
    assert result.approach_path.exists()
