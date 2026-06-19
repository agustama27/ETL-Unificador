from __future__ import annotations

import os
import time
import importlib
from pathlib import Path

modulo = importlib.import_module("core.procesar_tipificaciones")


def test_resolve_tipificaciones_input_path_prefers_explicit_input(tmp_path: Path) -> None:
    explicit = tmp_path / "input.csv"
    explicit.write_text("col\nvalue\n", encoding="utf-8")

    resolved = modulo.resolve_tipificaciones_input_path(explicit)

    assert resolved == explicit


def test_resolve_tipificaciones_input_path_uses_latest_file(monkeypatch, tmp_path: Path) -> None:
    roman_dir = tmp_path / "roman"
    older = roman_dir / "older.csv"
    newer = roman_dir / "newer.csv"
    roman_dir.mkdir(parents=True, exist_ok=True)
    older.write_text("a\n1\n", encoding="utf-8")
    newer.write_text("a\n2\n", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 60, now - 60))
    os.utime(newer, (now, now))

    monkeypatch.setattr(modulo, "DEFAULT_INPUT_DIR", roman_dir)

    resolved = modulo.resolve_tipificaciones_input_path(None)

    assert resolved == newer


def test_procesar_tipificaciones_logcall_con_cruce_por_callrefid(tmp_path: Path) -> None:
    from core.modelos import ConfigTipificaciones

    logcall = tmp_path / "LOGCALL_202605111611_NARANJA.csv"
    logcall.write_text(
        "\n".join(
            [
                '"CALLREFID","PHONE"',
                '"2615303001","5493517359990"',
            ]
        ),
        encoding="utf-8",
    )

    cruce = tmp_path / "roman.csv"
    cruce.write_text(
        "\n".join(
            [
                "call_refid,[Entrada] id_dni,[Entrada] id_producto,[Salida] Tipificaciones,[Salida] observaciones",
                "2615303001,DU00011209685,DU00011209685,Promesa de pago,Obs",
            ]
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    result = modulo.procesar_tipificaciones(
        logcall,
        ConfigTipificaciones(output_dir=out_dir, cruce_origen="roman", cruce_path=cruce),
    )

    assert result.status == "success"
    output_text = result.output_path.read_text(encoding="cp1252")
    assert "|26|" in output_text
    assert "DU00011209685" in output_text
    assert "Cliente no responde. Intento de contacto sin éxito." in output_text


def test_procesar_tipificaciones_combina_roman_y_logcall(tmp_path: Path) -> None:
    from core.modelos import ConfigTipificaciones

    roman = tmp_path / "roman.csv"
    roman.write_text(
        "\n".join(
            [
                "call_id,call_refid,[Entrada] id_dni,[Entrada] id_producto,[Salida] Tipificaciones,[Salida] observaciones",
                "call_a,call_a,DU1,PR1,Promesa de pago,Obs roman",
            ]
        ),
        encoding="utf-8",
    )

    logcall = tmp_path / "LOGCALL_202605111611_NARANJA.csv"
    logcall.write_text(
        "\n".join(
                [
                    '"CALLREFID","PHONE"',
                    '"call_a","5493517359990"',
                ]
            ),
            encoding="utf-8",
        )

    out_dir = tmp_path / "out"
    result = modulo.procesar_tipificaciones(
        roman,
        ConfigTipificaciones(output_dir=out_dir, cruce_origen="logcall", cruce_path=logcall),
    )

    assert result.status == "success"
    output_text = result.output_path.read_text(encoding="cp1252")
    assert output_text.count("\n") >= 2
    assert "|12|" in output_text
    assert "|26|" in output_text
    assert "Cliente no responde. Intento de contacto sin éxito." in output_text


def test_procesar_tipificaciones_logcall_sin_match_omite_por_nroproducto_faltante(tmp_path: Path) -> None:
    from core.modelos import ConfigTipificaciones

    roman = tmp_path / "roman.csv"
    roman.write_text(
        "\n".join(
            [
                "call_id,call_refid,[Entrada] id_dni,[Entrada] id_producto,[Salida] Tipificaciones,[Salida] observaciones",
                "call_a,call_a,DU1,PR1,Promesa de pago,Obs roman",
            ]
        ),
        encoding="utf-8",
    )

    logcall = tmp_path / "LOGCALL_202605111611_NARANJA.csv"
    logcall.write_text('"CALLREFID","PHONE"\n"call_b","5493517000000"\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    result = modulo.procesar_tipificaciones(
        roman,
        ConfigTipificaciones(output_dir=out_dir, cruce_origen="logcall", cruce_path=logcall),
    )

    assert result.status == "success"
    assert result.total_output_rows == 1
    assert result.omitted_by_reason.get("missing_nroproducto") == 1
