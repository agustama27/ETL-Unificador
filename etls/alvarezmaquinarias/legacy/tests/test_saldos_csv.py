"""Contrato estricto del adaptador CSV de saldos con fixtures sintéticos."""

from datetime import date
from pathlib import Path

import pytest

from scripts.generate_sample_data import (
    _maquinarias_rows,
    _remitos_servicios_sheets,
    _saldos_generales_rows,
    _write_remitos_repuestos_pdf,
    _write_saldos_csv,
    _write_xls,
    _write_xlsx,
)
from src.etl import schema
from src.etl.config import PipelineConfig
from src.etl.extractors import SaldosGeneralesExtractor
from src.etl.pipeline import run_pipeline
from src.etl.utils import complete_national_phone, to_international_phone


def test_saldos_csv_maps_two_synthetic_sections_equivalently_to_xls(tmp_path: Path) -> None:
    xls_source = tmp_path / "saldos.xls"
    csv_source = tmp_path / "saldos.csv"
    _write_xls(xls_source, _saldos_generales_rows())
    _write_saldos_csv(csv_source)

    xls_rows = SaldosGeneralesExtractor().extract(xls_source).rows
    csv_rows = SaldosGeneralesExtractor().extract(csv_source).rows
    matching_xls = xls_rows[xls_rows[schema.COL_CLIENTE_ID].isin(["101", "102"])]

    assert csv_rows.reset_index(drop=True).to_dict("records") == matching_xls.reset_index(
        drop=True
    ).to_dict("records")


def test_saldos_csv_preserves_quoted_crlf_fields(tmp_path: Path) -> None:
    source = tmp_path / "saldos.csv"
    sections = [
        [
            ["Saldos de clientes"],
            ["Cliente", "ID Autologica", "Telefono", "Saldo DOLARES", "Ultimo comprobante", "Fecha"],
            ["CLIENTE SINTETICO", "(201)", "3537\r\n411234", "100,00", "CD201", "01/01/2026"],
        ]
    ]
    _write_saldos_csv(source, sections)

    rows = SaldosGeneralesExtractor().extract(source).rows

    assert rows.loc[0, schema.COL_TELEFONO_RAW] == "3537\r\n411234"


def test_saldos_xls_override_name_retains_legacy_canonical_rows(tmp_path: Path) -> None:
    run_date = date(2026, 8, 4)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    input_dir.mkdir(parents=True)
    default_source = input_dir / "saldos.xls"
    override_source = input_dir / "cierre.xls"
    source_rows = _saldos_generales_rows()
    _write_xls(default_source, source_rows)
    _write_xls(override_source, source_rows)
    for filename in ("maquinarias.xlsx", "repuestos.pdf", "servicios.xlsx"):
        (input_dir / filename).write_bytes(b"synthetic-required-source")

    default_config = PipelineConfig.for_dated_run(
        project_root=tmp_path, run_date=run_date, source_names={},
        reference_date=date(2026, 7, 31), overwrite=False,
    )
    override_config = PipelineConfig.for_dated_run(
        project_root=tmp_path, run_date=run_date, source_names={"saldos": "cierre.xls"},
        reference_date=date(2026, 7, 31), overwrite=False,
    )

    default_rows = SaldosGeneralesExtractor().extract(default_config.saldos_generales_path).rows
    override_rows = SaldosGeneralesExtractor().extract(override_config.saldos_generales_path).rows

    assert override_rows.to_dict("records") == default_rows.to_dict("records")


def test_saldos_csv_logs_discarded_unparseable_balance_count(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    source = tmp_path / "saldos.csv"
    sections = [
        [
            ["Saldos de clientes"],
            ["Cliente", "ID Autologica", "Telefono", "Saldo DOLARES", "Ultimo comprobante", "Fecha"],
            ["CLIENTE VALIDO", "(301)", "3537411234", "100,00", "CD301", "01/01/2026"],
            ["CLIENTE INVALIDO", "(302)", "3537411235", "no-es-monto", "CD302", "01/01/2026"],
        ]
    ]
    _write_saldos_csv(source, sections)

    caplog.set_level("INFO")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert len(rows) == 1
    assert "saldos_generales: 1 filas validas, 1 descartadas" in caplog.text


def test_saldos_csv_logs_discarded_balance_count_before_empty_result_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = tmp_path / "saldos.csv"
    sections = [
        [
            ["Saldos de clientes"],
            ["Cliente", "ID Autologica", "Telefono", "Saldo DOLARES", "Ultimo comprobante", "Fecha"],
            ["CLIENTE INVALIDO", "(401)", "3537411235", "no-es-monto", "CD401", "01/01/2026"],
        ]
    ]
    _write_saldos_csv(source, sections)

    caplog.set_level("INFO")
    with pytest.raises(ValueError, match="reporte sin filas canónicas"):
        SaldosGeneralesExtractor().extract(source)

    assert "saldos_generales: 0 filas validas, 1 descartadas" in caplog.text


@pytest.mark.parametrize(
    ("payload", "cause"),
    [
        ("Saldos de clientes\nCliente;ID Autologica\n", "firma de encabezado"),
        ("Saldos de clientes\nCliente,Cliente,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\n", "firma de encabezado"),
        ("detalle huérfano\n", "sección o ancho"),
        ("Saldos de clientes\nCliente,ID Autologica,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\nA,(1),1,10,CD,01/01/2026,extra\n", "ancho de detalle"),
        ("Saldos de clientes\nCliente,ID Autologica,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\nA,(1),1,no-es-monto,CD,01/01/2026\n", "sin filas canónicas"),
    ],
)
def test_saldos_csv_rejects_unsafe_layouts_without_row_leaks(
    tmp_path: Path, payload: str, cause: str
) -> None:
    source = tmp_path / "saldos.csv"
    source.write_bytes(payload.encode("cp1252"))

    with pytest.raises(ValueError, match=cause) as error:
        SaldosGeneralesExtractor().extract(source)

    assert str(error.value).startswith("saldos_generales: CSV inválido: saldos.csv:")
    assert "no-es-monto" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xef\xbb\xbfSaldos de clientes\r\n",
        "Saldos de clientes\nCliente,ID Autologica,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\nJosé,(1),1,10,CD,01/01/2026\n".encode("utf-8"),
        b'Saldos de clientes\r\nCliente,ID Autologica,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\r\n"sin cierre\r\n',
    ],
)
def test_saldos_csv_rejects_bom_utf8_and_malformed_quotes_without_leaks(
    tmp_path: Path, payload: bytes
) -> None:
    source = tmp_path / "saldos.csv"
    source.write_bytes(payload)

    with pytest.raises(ValueError) as error:
        SaldosGeneralesExtractor().extract(source)

    assert str(error.value).startswith("saldos_generales: CSV inválido: saldos.csv:")
    assert "José" not in str(error.value)
    assert "sin cierre" not in str(error.value)


@pytest.mark.parametrize(
    "detail",
    [
        ",(1),1,10,CD,01/01/2026", "A,,1,10,CD,01/01/2026",
        "A,(1),1,10,,01/01/2026", "A,(1),1,10,CD,fecha-inválida",
    ],
)
def test_saldos_csv_rejects_missing_or_invalid_required_values(
    tmp_path: Path, detail: str
) -> None:
    source = tmp_path / "saldos.csv"
    source.write_text(
        "Saldos de clientes\nCliente,ID Autologica,Telefono,Saldo DOLARES,Ultimo comprobante,Fecha\n"
        f"{detail}\n", encoding="cp1252", newline=""
    )

    with pytest.raises(ValueError, match="valor requerido"):
        SaldosGeneralesExtractor().extract(source)


def _reporte_pagina(cliente: str, telefono: str, pesos: str, dolares: str,
                    comprobante: str, fecha: str, localidad: str = "x") -> str:
    """Dos líneas físicas sintéticas del export "ficha por página": header de
    página con el bloque de cliente al final, y la fila de saldos."""
    header = (
        '"Saldos de proveedores","Saldos de clientes","Emitido:","12/08/2026  8:20",'
        '"Desde: Autologica","","","Cliente","Proveedor","","","Categoría de cliente","",'
        '"Teléfono","Saldo PESOS","Saldo DOLARES","Ultimo comprobante","Fecha","",'
        '"Saldo PESOS (Otras suc.)","Saldo DOLARES (Otras suc.)","",'
        f'"Proveedor:","Cliente:","{cliente}","x","x","{localidad}","Teléfono:","{telefono}",'
        '"Categoría de cliente:","NO CATEGORIZADO"'
    )
    datos = (
        f'"","{pesos}","{dolares}","{comprobante}","{fecha}","",'
        '"Total proveedor","Total cliente","0,00","0,00"'
    )
    return header + "\r\n" + datos + "\r\n"


def _write_saldos_reporte_csv(path: Path, body: str, tail: str = "") -> None:
    titulo = ('"Saldos de proveedores","Saldos de clientes","Emitido:","12/08/2026  8:20",'
              '"Desde: Autologica","01/07/2026","31/07/2026"\r\n')
    preambulo = '"","Otras sucursales","Sucursal:","Tipo de cuenta:","0 ","No definido"," "\r\n'
    path.write_bytes((titulo + preambulo + body + tail).encode("cp1252"))


def test_saldos_csv_reporte_por_pagina_mapea_bloques_y_toma_dolares(tmp_path: Path) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE UNO (501)", "3537411234", "9.999,99", "1.234,56",
                           "CD501", "01/07/2026")
    body += _reporte_pagina("CLIENTE DOS (502)", "", "0,00", "850,00", "CD502", "15/06/2026")
    _write_saldos_reporte_csv(source, body)

    rows = SaldosGeneralesExtractor().extract(source).rows

    assert len(rows) == 2
    assert list(rows[schema.COL_CLIENTE_RAW]) == ["CLIENTE UNO", "CLIENTE DOS"]
    assert list(rows[schema.COL_CLIENTE_ID]) == ["501", "502"]
    # Toma Saldo DOLARES, no Saldo PESOS
    assert list(rows[schema.COL_MONTO_ORIGINAL]) == [1234.56, 850.00]
    assert rows.loc[0, schema.COL_TELEFONO_RAW] == "3537411234"
    assert rows.loc[1, schema.COL_TELEFONO_RAW] is None
    assert list(rows[schema.COL_REMITO]) == ["CD501", "CD502"]
    assert rows.loc[0, schema.COL_FECHA] == date(2026, 7, 1)


def test_saldos_csv_reporte_omite_clientes_sin_saldo_usd(tmp_path: Path) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE USD (601)", "", "0,00", "700,00", "CD601", "01/07/2026")
    body += _reporte_pagina("CLIENTE PESOS (602)", "", "5.000,00", "", "CD602", "01/07/2026")
    _write_saldos_reporte_csv(source, body)

    rows = SaldosGeneralesExtractor().extract(source).rows

    assert list(rows[schema.COL_CLIENTE_ID]) == ["601"]


def test_saldos_csv_reporte_tolera_cola_truncada_sin_cliente(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE UNO (701)", "", "0,00", "100,00", "CD701", "01/07/2026")
    tail = '"Saldos de proveedores","Saldos de clientes","Emitido:","12/08/2026  8:20","'
    _write_saldos_reporte_csv(source, body, tail)

    caplog.set_level("WARNING")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert len(rows) == 1
    assert "línea final truncada sin bloque de cliente" in caplog.text


def test_saldos_csv_reporte_aborta_si_la_cola_truncada_trae_cliente(tmp_path: Path) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE UNO (801)", "", "0,00", "100,00", "CD801", "01/07/2026")
    tail = '"Proveedor:","Cliente:","CLIENTE PERDIDO (802)","x","x","x","Teléfono:","'
    _write_saldos_reporte_csv(source, body, tail)

    with pytest.raises(ValueError, match="truncada con datos de cliente") as error:
        SaldosGeneralesExtractor().extract(source)

    assert "CLIENTE PERDIDO" not in str(error.value)


def test_saldos_csv_reporte_aborta_ante_cliente_sin_id_o_estructura_rota(tmp_path: Path) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE SIN ID", "", "0,00", "100,00", "CD901", "01/07/2026")
    _write_saldos_reporte_csv(source, body)

    with pytest.raises(ValueError, match="sin nombre e ID de Autologica"):
        SaldosGeneralesExtractor().extract(source)

    dos_clientes_seguidos = (
        _reporte_pagina("CLIENTE UNO (901)", "", "0,00", "100,00", "CD901", "01/07/2026")
        .split("\r\n")[0]
        + "\r\n"
    ) * 2
    _write_saldos_reporte_csv(source, dos_clientes_seguidos)

    with pytest.raises(ValueError, match="bloque de cliente sin fila de saldos"):
        SaldosGeneralesExtractor().extract(source)


@pytest.mark.parametrize(
    ("raw", "area", "expected"),
    [
        # local pelado + característica de la localidad
        ("408341", "3385", "3385408341"),
        ("4650092", "358", "3584650092"),
        ("59389412", "11", "1159389412"),
        # notación local de celular: se quita el 15
        ("15254994", "3471", "3471254994"),
        ("155097850", "358", "3585097850"),
        # 15 después de la característica, con 0 de larga distancia
        ("0-3385-15-464768", "3385", "3385464768"),
        ("236154664944", "236", "2364664944"),
        # prefijos internacionales
        ("5493385464768", None, "3385464768"),
        ("543385464768", None, "3385464768"),
        # ya completo: pasa igual, con o sin característica conocida
        ("3385464768", "3385", "3385464768"),
        ("2657564320", None, "2657564320"),
        # falso válido: 10 dígitos que empiezan con 15 son celular local
        ("1556262820", "11", "1156262820"),
        # sin característica no se puede completar un local
        ("408341", None, None),
        # largo imposible: nunca se inventa
        ("408341", "358", None),
        ("12345", "3385", None),
        ("", "3385", None),
        (None, "3385", None),
    ],
)
def test_complete_national_phone_reconstruye_sin_inventar(raw, area, expected) -> None:
    assert complete_national_phone(raw, area) == expected


@pytest.mark.parametrize("falso_valido", ["1556262820", "0358465009"])
def test_to_international_rechaza_falsos_validos_de_10_digitos(falso_valido: str) -> None:
    assert to_international_phone(falso_valido) is None


def test_saldos_csv_reporte_completa_telefonos_por_localidad(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE LOCAL (901)", "408341", "0,00", "100,00",
                           "CD901", "01/07/2026", localidad="6120 - LABOULAYE")
    body += _reporte_pagina("CLIENTE SIN MAPA (902)", "408342", "0,00", "200,00",
                            "CD902", "01/07/2026", localidad="9999 - SIN MAPEO")
    _write_saldos_reporte_csv(source, body)

    caplog.set_level("WARNING")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert rows.loc[0, schema.COL_TELEFONO_RAW] == "3385408341"
    # localidad sin mapear: queda el crudo original, no se adivina
    assert rows.loc[1, schema.COL_TELEFONO_RAW] == "408342"
    assert "1 telefono(s) completado(s) con la caracteristica de su localidad" in caplog.text
    assert "1 telefono(s) siguen incompletos" in caplog.text
    # el CP faltante se nombra: sin eso, ampliar AREA_POR_CP es adivinar
    assert "CP sin mapear: 9999(1)" in caplog.text
    assert "408341" not in caplog.text  # sin datos de fila en los warnings
    assert "408342" not in caplog.text


def test_saldos_csv_reporte_agrupa_los_cp_sin_mapear_por_frecuencia(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """El warning ordena por conteo para que la localidad que más clientes
    deja sin gestionar sea la primera que se agrega a la tabla."""
    source = tmp_path / "saldos.csv"
    body = "".join(
        _reporte_pagina(f"CLIENTE {i} ({900 + i})", "408341", "0,00", "100,00",
                        f"CD{900 + i}", "01/07/2026", localidad=cp)
        for i, cp in enumerate(["9998 - UNO", "9998 - UNO", "9997 - DOS"])
    )
    _write_saldos_reporte_csv(source, body)

    caplog.set_level("WARNING")
    SaldosGeneralesExtractor().extract(source)

    assert "CP sin mapear: 9998(2), 9997(1)" in caplog.text


def test_saldos_csv_reporte_no_duplica_la_caracteristica_ya_presente(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Un número que ya trae característica de la localidad mapeada pasa
    igual: completar es reordenar lo que está, nunca anteponer de más."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE COMPLETO (903)", "3385464768", "0,00", "100,00",
                           "CD903", "01/07/2026", localidad="6120 - LABOULAYE")
    _write_saldos_reporte_csv(source, body)

    caplog.set_level("WARNING")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert rows.loc[0, schema.COL_TELEFONO_RAW] == "3385464768"
    assert "telefono(s) completado(s)" not in caplog.text
    assert "siguen incompletos" not in caplog.text


def test_saldos_csv_reporte_completa_el_cp_5736_agregado_en_la_corrida_1208(
    tmp_path: Path,
) -> None:
    """CP 5736 (Fraga, Dpto. Pringles, San Luis) → 2657, verificado contra
    directorio público tras aparecer en el warning de la corrida 12/08."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE FRAGA (904)", "464768", "0,00", "100,00",
                           "CD904", "01/07/2026", localidad="5736 - FRAGA")
    _write_saldos_reporte_csv(source, body)

    rows = SaldosGeneralesExtractor().extract(source).rows

    assert rows.loc[0, schema.COL_TELEFONO_RAW] == "2657464768"


def test_invalid_saldos_csv_aborts_pipeline_without_creating_exports(tmp_path: Path) -> None:
    _write_xlsx(tmp_path / "maquinarias.xlsx", {"Sheet1": _maquinarias_rows()})
    _write_xlsx(tmp_path / "servicios.xlsx", _remitos_servicios_sheets())
    _write_remitos_repuestos_pdf(tmp_path / "repuestos.pdf")
    source = tmp_path / "saldos.csv"
    source.write_bytes(b"Saldos de clientes\r\nCliente;ID Autologica\r\n")
    config = PipelineConfig(
        saldos_generales_path=source, maquinarias_path=tmp_path / "maquinarias.xlsx",
        remitos_repuestos_path=tmp_path / "repuestos.pdf", remitos_servicios_path=tmp_path / "servicios.xlsx",
        output_dir=tmp_path / "output", reference_date=date(2026, 7, 28),
    )

    with pytest.raises(ValueError, match="saldos_generales: CSV inválido: saldos.csv"):
        run_pipeline(config)

    assert not config.roman_output_path.exists()
    assert not config.approach_output_path.exists()


def test_saldos_csv_rescata_el_importe_de_la_ultima_fila_truncada(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """El export corta siempre al final. Cuando el corte cae sobre la fila de
    saldos del último cliente, su importe USD suele quedar entero: se rescata
    en vez de perder la deuda. El comprobante y la fecha no se inventan."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE ENTERO (801)", "3385464768", "0,00", "100,00",
                           "CD801", "01/07/2026")
    # último cliente: bloque completo, fila de saldos cortada a mitad del
    # comprobante — el importe USD quedó cerrado por comillas
    body += _reporte_pagina("CLIENTE CORTADO (819)", "3385464769", "0,00", "77.25",
                            "CFSR A 0002", "01/07/2026").split("\r\n")[0] + "\r\n"
    tail = '"","114,324.67","77.25","CFSR A 0002-00029070'
    _write_saldos_reporte_csv(source, body, tail)

    caplog.set_level("WARNING")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert list(rows[schema.COL_CLIENTE_ID]) == ["801", "819"]
    rescatada = rows[rows[schema.COL_CLIENTE_ID] == "819"].iloc[0]
    assert rescatada[schema.COL_MONTO_ORIGINAL] == pytest.approx(77.25, abs=0.01)
    # no se inventa lo que el corte se llevó
    assert rescatada[schema.COL_FECHA] is None
    assert rescatada[schema.COL_REMITO] is None
    assert "se rescato el importe USD del ultimo cliente" in caplog.text
    # el warning no expone identidades ni importes de la fila
    assert "819" not in caplog.text
    assert "77.25" not in caplog.text


def test_saldos_csv_aborta_si_el_corte_partio_el_importe(tmp_path: Path) -> None:
    """Si el corte cae dentro del propio importe no hay nada confiable que
    rescatar: completar el número sería inventar deuda."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE ENTERO (802)", "", "0,00", "100,00",
                           "CD802", "01/07/2026")
    body += _reporte_pagina("CLIENTE CORTADO (820)", "", "0,00", "500,00",
                            "CD820", "01/07/2026").split("\r\n")[0] + "\r\n"
    _write_saldos_reporte_csv(source, body, '"","114,324.67","1.234')

    with pytest.raises(ValueError, match="bloque de cliente sin fila de saldos"):
        SaldosGeneralesExtractor().extract(source)


def test_saldos_csv_no_confunde_un_encabezado_truncado_con_una_fila_de_saldos(
    tmp_path: Path,
) -> None:
    """La cola puede ser el encabezado de una página nueva. Ese no trae saldo
    y no debe rescatarse como si lo fuera."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE ENTERO (803)", "", "0,00", "100,00",
                           "CD803", "01/07/2026")
    body += _reporte_pagina("CLIENTE CORTADO (821)", "", "0,00", "500,00",
                            "CD821", "01/07/2026").split("\r\n")[0] + "\r\n"
    tail = '"Saldos de proveedores","Saldos de clientes","Emitido:","25/08/2026","'

    with pytest.raises(ValueError, match="bloque de cliente sin fila de saldos"):
        _write_saldos_reporte_csv(source, body, tail)
        SaldosGeneralesExtractor().extract(source)


def test_saldos_csv_rescata_sin_saldo_usd_no_agrega_fila(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Cliente cortado cuyo Saldo DOLARES venía vacío: queda fuera del ETL
    igual que cualquier otro sin saldo USD, sin abortar la corrida."""
    source = tmp_path / "saldos.csv"
    body = _reporte_pagina("CLIENTE ENTERO (804)", "", "0,00", "100,00",
                           "CD804", "01/07/2026")
    body += _reporte_pagina("CLIENTE CORTADO (822)", "", "0,00", "",
                            "CD822", "01/07/2026").split("\r\n")[0] + "\r\n"
    _write_saldos_reporte_csv(source, body, '"","114,324.67","","CFSR A 0002-000')

    caplog.set_level("WARNING")
    rows = SaldosGeneralesExtractor().extract(source).rows

    assert list(rows[schema.COL_CLIENTE_ID]) == ["804"]
    assert "se rescato el importe USD del ultimo cliente" in caplog.text


@pytest.mark.parametrize(
    ("localidad", "local", "esperado"),
    [
        # verificados contra directorio publico en la corrida del 25/08/2026
        ("6140 - VICUÑA MACKENNA", "464768", "3583464768"),
        # General Deheza es caracteristica de 3 digitos: un local de 6 no
        # reconstruye a 10 y queda como vino, que es el comportamiento seguro
        ("5923 - GENERAL DEHEZA", "464768", None),
        ("5923 - GENERAL DEHEZA", "4647689", "3584647689"),
    ],
)
def test_codigos_de_area_agregados_en_la_corrida_2508(localidad, local, esperado) -> None:
    from src.etl.codigos_area import area_code_for_locality
    assert complete_national_phone(local, area_code_for_locality(localidad)) == esperado


def test_servicios_toma_el_total_aunque_el_importe_venga_como_texto(tmp_path: Path) -> None:
    """La hoja mezcla números nativos de Excel con celdas de texto
    ('USD1.149,20') en el mismo archivo. Exigir número nativo descartaba
    filas enteras con deuda real (caso EL CACIQUE, corrida 01/09/2026)."""
    from datetime import datetime
    from src.etl.extractors import RemitosServiciosExtractor

    source = tmp_path / "servicios.xlsx"
    filas = [
        ["N° Remito", "Código", "Cliente", "Detalles", "Fecha", "Precio", "IVA 21%", "Total"],
        [8000, 111, "CLIENTE NATIVO", None, datetime(2026, 4, 5), 100.0, 21.0, 121.0],
        [8558, 1236, "CLIENTE TEXTO", None, datetime(2026, 4, 5),
         "USD1.149,20", "USD241,33", "USD1.390,53"],
    ]
    _write_xlsx(source, {"Remitos Servicios": filas})

    rows = RemitosServiciosExtractor().extract(source).rows

    assert list(rows[schema.COL_CLIENTE_RAW]) == ["CLIENTE NATIVO", "CLIENTE TEXTO"]
    assert list(rows[schema.COL_MONTO_ORIGINAL]) == pytest.approx([121.0, 1390.53], abs=0.01)
    assert list(rows[schema.COL_CLIENTE_ID]) == ["111", "1236"]


def test_servicios_descarta_la_fila_si_ningun_campo_es_un_importe(tmp_path: Path) -> None:
    """Sin ningún importe posterior a la fecha no hay Total que tomar: la fila
    se descarta con warning en vez de inventar un monto."""
    from datetime import datetime
    from src.etl.extractors import RemitosServiciosExtractor

    source = tmp_path / "servicios.xlsx"
    filas = [
        ["N° Remito", "Código", "Cliente", "Detalles", "Fecha", "Precio", "IVA 21%", "Total"],
        [8000, 111, "CLIENTE VALIDO", None, datetime(2026, 4, 5), 100.0, 21.0, 121.0],
        [8001, 112, "CLIENTE SIN MONTO", None, datetime(2026, 4, 5), "s/d", "s/d", "s/d"],
    ]
    _write_xlsx(source, {"Remitos Servicios": filas})

    rows = RemitosServiciosExtractor().extract(source).rows

    assert list(rows[schema.COL_CLIENTE_RAW]) == ["CLIENTE VALIDO"]
