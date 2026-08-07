from __future__ import annotations

from pathlib import Path

from back_base_etl.io import load_pagos


def test_load_pagos_legacy_semicolon_format(tmp_path: Path) -> None:
    pagos = tmp_path / "pagos_legacy.csv"
    pagos.write_text(
        "nroproducto;recupero;tipo_pago;cajon_asig_prod;cajon_actual_prod\n"
        "1001;SI;PAGO_LINK;M90;\n",
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert list(df.columns) == [
        "nroproducto",
        "recupero",
        "tipo_pago",
        "cajon_asig_prod",
        "cajon_actual_prod",
        "importe_pago",
        "dt_actual",
        "dv_actual",
        "deuda_vencida",
    ]
    assert len(df) == 1
    assert df.iloc[0]["nroproducto"] == "1001"
    assert df.iloc[0]["tipo_pago"] == "PAGO_LINK"


def test_load_pagos_evoltis_comma_format(tmp_path: Path) -> None:
    pagos = tmp_path / "evoltis_avanzada_pagos_detalle_20260428.csv"
    pagos.write_text(
        '"PROVEEDOR","DNI","NROPRODUCTO","CAJON_ASIGNACION_CLIENTE","CAJON_ASIG_PROD","CAJON_ACTUAL_PROD","RECUPERO","PRODUCTO","DOCUMENTO","FECHA_PAGO","IMPORTE_PAGO"\n'
        '"DEELO","DU35214453","DU00035214453","M120","M90","M60","SI","NARANJA",35214453,"2026-04-25",565356\n',
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert list(df.columns) == [
        "nroproducto",
        "recupero",
        "tipo_pago",
        "cajon_asig_prod",
        "cajon_actual_prod",
        "importe_pago",
        "dt_actual",
        "dv_actual",
        "deuda_vencida",
    ]
    assert len(df) == 1
    assert df.iloc[0]["nroproducto"] == "DU00035214453"
    assert df.iloc[0]["recupero"] == "SI"
    assert df.iloc[0]["importe_pago"] == "565356"
    assert df.iloc[0]["cajon_asig_prod"] == "M90"
    assert df.iloc[0]["cajon_actual_prod"] == "M60"


def test_load_pagos_comma_format_with_quoted_spaced_headers_and_bom(tmp_path: Path) -> None:
    pagos = tmp_path / "pagos_quoted_headers.csv"
    pagos.write_text(
        '\ufeff"PROVEEDOR", "dni", "NROPRODUCTO", "CAJON_ASIG_PROD", "CAJON_ACTUAL_PROD", "RECUPERO", "PRODUCTO", "IMPORTE_PAGO"\n'
        '"DEELO", "35214453", "DU00035214453", "M90", "M60", "SI", "PAGO_LINK", "565356"\n',
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert list(df.columns) == [
        "nroproducto",
        "recupero",
        "tipo_pago",
        "cajon_asig_prod",
        "cajon_actual_prod",
        "importe_pago",
        "dt_actual",
        "dv_actual",
        "deuda_vencida",
    ]
    assert len(df) == 1
    assert df.iloc[0]["nroproducto"] == "DU00035214453"
    assert df.iloc[0]["recupero"] == "SI"
    assert df.iloc[0]["tipo_pago"] == "PAGO_LINK"
    assert df.iloc[0]["importe_pago"] == "565356"
    assert df.iloc[0]["cajon_asig_prod"] == "M90"
    assert df.iloc[0]["cajon_actual_prod"] == "M60"


def test_load_pagos_reparses_collapsed_single_header_column(tmp_path: Path) -> None:
    pagos = tmp_path / "pagos_collapsed_header.csv"
    pagos.write_text(
        '"proveedor,\"dni\",\"nroproducto\",\"cajon_asig_prod\",\"recupero\",\"producto\""\n'
        '"DEELO","35214453","DU00035214453","M90","SI","PAGO_LINK"\n',
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert list(df.columns) == [
        "nroproducto",
        "recupero",
        "tipo_pago",
        "cajon_asig_prod",
        "cajon_actual_prod",
        "importe_pago",
        "dt_actual",
        "dv_actual",
        "deuda_vencida",
    ]
    assert len(df) == 1
    assert df.iloc[0]["nroproducto"] == "DU00035214453"
    assert df.iloc[0]["recupero"] == "SI"
    assert df.iloc[0]["tipo_pago"] == "PAGO_LINK"


def test_load_pagos_reparses_collapsed_header_with_unbalanced_quotes(tmp_path: Path) -> None:
    pagos = tmp_path / "pagos_collapsed_unbalanced.csv"
    pagos.write_text(
        '"proveedor,\"dni\",\"nroproducto\",\"cajon_asig_prod\",\"recupero\",\"producto\"\n'
        '"DEELO","35214453","DU00035214453","M90","SI","PAGO_LINK"\n',
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert list(df.columns) == [
        "nroproducto",
        "recupero",
        "tipo_pago",
        "cajon_asig_prod",
        "cajon_actual_prod",
        "importe_pago",
        "dt_actual",
        "dv_actual",
        "deuda_vencida",
    ]
    assert len(df) == 1
    assert df.iloc[0]["nroproducto"] == "DU00035214453"
    assert df.iloc[0]["tipo_pago"] == "PAGO_LINK"


def test_load_pagos_maps_dt_actual_and_dv_actual_aliases(tmp_path: Path) -> None:
    pagos = tmp_path / "pagos_dt_dv.csv"
    pagos.write_text(
        "nroproducto;recupero;tipo_pago;cajon_asig_prod;deuda_total_actual;deuda_vencida_actual\n"
        "1001;NO;PAGO_LINK;M90;1500,50;120,25\n",
        encoding="utf-8",
    )

    df = load_pagos(str(pagos))

    assert df.iloc[0]["dt_actual"] == "1500,50"
    assert df.iloc[0]["dv_actual"] == "120,25"
    assert df.iloc[0]["importe_pago"] == "0"
