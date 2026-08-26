"""Extractors: un adapter por archivo fuente real de Autologica, cada uno
devuelve un DataFrame en el esquema canónico (`schema.CANONICAL_COLUMNS`).

Cada fuente real es un reporte agrupado (header corrido, filas de
subtotal, celdas combinadas) — no una tabla plana. Cada adapter aísla su
propio desorden; nada aguas abajo (transform/consolidate/load) sabe que
estas fuentes eran reportes de Autologica. Ver docs/SPEC.md sección 2.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping, Optional

import pandas as pd
import pypdf

from . import schema
from .codigos_area import area_code_for_locality, postal_code_for_locality
from .utils import (
    classify_currency_from_flag,
    complete_national_phone,
    locate_header_row,
    normalize_client_name,
    normalize_phone,
    parse_currency_amount,
    parse_date,
)

logger = logging.getLogger(__name__)

_CLIENTE_ID_RE = re.compile(r"\((\d+)\)")
# Export "ficha por página": la celda posterior a `Cliente:` trae nombre e ID
# juntos, p. ej. `CLIENTE EJEMPLO (123)`.
_REPORT_CLIENTE_RE = re.compile(r"^(?P<nombre>.+?)\s*\((?P<id>\d+)\)$")
_SUBTOTAL_RE = re.compile(r"^Cliente:\s")
# Nombre limpio en la fila de subtotal del pivot ("Cliente: X" seguido,
# a veces pegado, de "Recuento: N").
_SUBTOTAL_NOMBRE_RE = re.compile(r"^Cliente:\s*(.+?)\s*(?:Recuento:.*)?$")
_REMITO_CLIENTE_RE = re.compile(r"^(\d+)\s+(.+)$")
_REPUESTOS_DETALLE_RE = re.compile(
    r"^(?P<remito>\d+)\s+(?P<cliente>.+?)REPUESTOS\s+"
    r"(?P<fecha>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"\$?\s*(?P<precio>\d{1,3}(?:\.\d{3})*,\d{2})\s+"
    r"\$?\s*(?P<iva>\d{1,3}(?:\.\d{3})*,\d{2})\s+"
    r"\$?\s*(?P<total>\d{1,3}(?:\.\d{3})*,\d{2})"
    r"(?P<factura_flag>.*)$"
)


@dataclass(frozen=True)
class ExtractionDiagnostics:
    """Conteos seguros de exclusiones, sin datos de clientes."""

    excluded_ars_by_source: Mapping[str, int]
    excluded_unknown_by_source: Mapping[str, int]

    def summary(self) -> str:
        entries = ", ".join(
            f"{source}={count}" for source, count in sorted(self.excluded_ars_by_source.items())
        )
        return f"ARS excluidos: {entries}"


@dataclass(frozen=True)
class SourceExtraction:
    rows: pd.DataFrame
    diagnostics: ExtractionDiagnostics


def _empty_canonical_df() -> pd.DataFrame:
    return pd.DataFrame(columns=schema.CANONICAL_COLUMNS)


def _source_extraction(
    rows: pd.DataFrame, source: str, *, excluded_ars: int = 0, excluded_unknown: int = 0
) -> SourceExtraction:
    return SourceExtraction(
        rows=rows,
        diagnostics=ExtractionDiagnostics(
            excluded_ars_by_source={source: excluded_ars},
            excluded_unknown_by_source={source: excluded_unknown},
        ),
    )


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def _norm_header(cell) -> str:
    if _is_blank(cell):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(cell).strip().upper())


def _find_col(
    header_norm: list[str],
    *,
    equals: Optional[str] = None,
    startswith: Optional[str] = None,
    contains: Optional[str] = None,
) -> Optional[int]:
    for i, h in enumerate(header_norm):
        if equals is not None and h == equals:
            return i
        if startswith is not None and h.startswith(startswith):
            return i
        if contains is not None and contains in h:
            return i
    return None


def _extract_cliente_id(*candidates) -> Optional[str]:
    for candidate in candidates:
        if _is_blank(candidate):
            continue
        m = _CLIENTE_ID_RE.search(str(candidate))
        if m:
            return m.group(1)
    return None


class SaldosGeneralesExtractor:
    """`saldos julio 2026 (1).xls` — cuenta corriente general.

    Formato `.xls` legado, header corrido (no en fila 0), con filas de
    título/filtro antes. ID Autologica en la celda contigua al nombre.
    Única fuente que aporta teléfono principal e ID Autologica.
    """

    fuente = schema.FUENTE_SALDOS_GENERALES
    _CSV_HEADER = (
        "CLIENTE", "IDAUTOLOGICA", "TELEFONO", "SALDODOLARES", "ULTIMOCOMPROBANTE", "FECHA"
    )

    def extract(self, path: Path) -> SourceExtraction:
        if path.suffix.lower() == ".csv":
            return self._extract_csv(path)
        return self._extract_xls(path)

    def _extract_xls(self, path: Path) -> pd.DataFrame:
        raw = pd.read_excel(path, header=None, engine="xlrd")
        rows = raw.values.tolist()
        header_idx = locate_header_row(rows, {"CLIENTE"})
        header_norm = [_norm_header(c) for c in rows[header_idx]]

        col_cliente = header_norm.index("CLIENTE")
        col_telefono = _find_col(header_norm, startswith="TEL")
        col_saldo = _find_col(header_norm, equals="SALDODOLARES")
        col_comprobante = _find_col(header_norm, contains="COMPROBANTE")
        col_fecha = _find_col(header_norm, equals="FECHA")
        if col_saldo is None:
            raise ValueError(
                f"{self.fuente}: no se encontro la columna 'Saldo DOLARES' en el "
                f"header ({rows[header_idx]}) de {path.name}"
            )

        out_rows: list[dict] = []
        discarded = 0
        for row in rows[header_idx + 1 :]:
            cliente_raw = row[col_cliente]
            if _is_blank(cliente_raw) or not str(cliente_raw).strip():
                continue  # fila vacia de cierre de reporte, no es un dato invalido

            monto = parse_currency_amount(row[col_saldo])
            if monto is None:
                logger.warning("%s: fila descartada, saldo no parseable", self.fuente)
                discarded += 1
                continue

            cliente_id = _extract_cliente_id(
                row[col_cliente + 1] if col_cliente + 1 < len(row) else None,
                cliente_raw,
            )

            out_rows.append(
                {
                    schema.COL_CLIENTE_RAW: str(cliente_raw).strip(),
                    schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                    schema.COL_CLIENTE_ID: cliente_id,
                    schema.COL_TELEFONO_RAW: row[col_telefono] if col_telefono is not None else None,
                    schema.COL_PRODUCTO: "Cuenta Corriente",
                    schema.COL_CONCEPTO: "Cuenta Corriente",
                    schema.COL_FECHA: parse_date(row[col_fecha]) if col_fecha is not None else None,
                    schema.COL_REMITO: row[col_comprobante] if col_comprobante is not None else None,
                    schema.COL_MONTO_ORIGINAL: monto,
                    schema.COL_DIAS_MORA_FUENTE: None,
                    schema.COL_PRIORIDAD_RAW: None,
                    schema.COL_FUENTE: self.fuente,
                }
            )

        logger.info("%s: %d filas validas, %d descartadas", self.fuente, len(out_rows), discarded)
        if not out_rows:
            return _source_extraction(_empty_canonical_df(), self.fuente)
        return _source_extraction(pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente)

    def _extract_csv(self, path: Path) -> SourceExtraction:
        """Despacha entre los dos layouts CSV CP1252/coma admitidos."""
        text = self._read_csv_text(path)
        if self._is_report_export(text):
            return self._extract_csv_report(path, text)
        return self._extract_csv_sectioned(path, text)

    def _read_csv_text(self, path: Path) -> str:
        try:
            content = path.read_bytes()
            if content.startswith(b"\xef\xbb\xbf"):
                raise ValueError("BOM no admitido")
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                pass
            else:
                if any(byte >= 128 for byte in content):
                    raise ValueError("codificación UTF-8 no admitida")
            return content.decode("cp1252")
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise self._csv_error(path, str(error)) from error

    @staticmethod
    def _is_report_export(text: str) -> bool:
        """El export "ficha por página" arranca con los dos títulos del
        reporte en la misma línea; el seccionado, con una sección sola."""
        first_line = text.splitlines()[0] if text else ""
        try:
            first_row = next(csv.reader(io.StringIO(first_line)), [])
        except csv.Error:
            return False
        headers = {_norm_header(cell) for cell in first_row}
        return {"SALDOSDEPROVEEDORES", "SALDOSDECLIENTES"} <= headers

    def _extract_csv_sectioned(self, path: Path, text: str) -> SourceExtraction:
        """Adapta exclusivamente el reporte seccionado CP1252/coma aprobado."""
        try:
            rows = list(
                csv.reader(
                    io.StringIO(text, newline=""),
                    delimiter=",",
                    strict=True,
                )
            )
        except csv.Error as error:
            raise self._csv_error(path, str(error)) from error

        out_rows: list[dict] = []
        discarded = 0
        index = 0
        while index < len(rows):
            title = rows[index]
            if len(title) != 1 or _norm_header(title[0]) != "SALDOSDECLIENTES":
                raise self._csv_error(path, "sección o ancho de fila no admitido")
            if index + 2 >= len(rows) or tuple(_norm_header(cell) for cell in rows[index + 1]) != self._CSV_HEADER:
                raise self._csv_error(path, "firma de encabezado no admitida")
            index += 2
            detail_count = 0
            while index < len(rows) and not (len(rows[index]) == 1 and _norm_header(rows[index][0]) == "SALDOSDECLIENTES"):
                row = rows[index]
                if len(row) != len(self._CSV_HEADER):
                    raise self._csv_error(path, "ancho de detalle no admitido")
                cliente, cliente_id_raw, telefono, saldo, comprobante, fecha = row
                if (
                    not cliente.strip()
                    or not _extract_cliente_id(cliente_id_raw)
                    or not comprobante.strip()
                    or parse_date(fecha) is None
                ):
                    raise self._csv_error(path, "valor requerido ausente")
                monto = parse_currency_amount(saldo)
                if monto is not None:
                    out_rows.append({
                        schema.COL_CLIENTE_RAW: cliente.strip(), schema.COL_CLIENTE_KEY: normalize_client_name(cliente),
                        schema.COL_CLIENTE_ID: _extract_cliente_id(cliente_id_raw), schema.COL_TELEFONO_RAW: telefono,
                        schema.COL_PRODUCTO: "Cuenta Corriente", schema.COL_CONCEPTO: "Cuenta Corriente",
                        schema.COL_FECHA: parse_date(fecha), schema.COL_REMITO: comprobante,
                        schema.COL_MONTO_ORIGINAL: monto,
                        schema.COL_DIAS_MORA_FUENTE: None, schema.COL_PRIORIDAD_RAW: None, schema.COL_FUENTE: self.fuente,
                    })
                else:
                    discarded += 1
                detail_count += 1
                index += 1
            if not detail_count:
                raise self._csv_error(path, "sección sin detalles")
        logger.info("%s: %d filas validas, %d descartadas", self.fuente, len(out_rows), discarded)
        if not out_rows:
            raise self._csv_error(path, "reporte sin filas canónicas")
        return _source_extraction(pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente)

    def _extract_csv_report(self, path: Path, text: str) -> SourceExtraction:
        """Adapta el export "ficha por página" del reporte Saldos de clientes.

        Cada página trae un bloque `Cliente:` → `NOMBRE (ID)` y `Teléfono:` →
        valor, seguido en la línea siguiente por la fila de saldos, cuyas
        primeras celdas son Saldo PESOS, Saldo DOLARES, último comprobante y
        fecha. Solo se toma el Saldo DOLARES (invariante USD-only); el saldo
        en pesos se ignora sin registrar datos de la fila.

        El export real puede venir cortado a mitad del header de la última
        página (comilla sin cerrar al EOF). Esa cola se descarta con un
        warning **solo** si no contiene un bloque de cliente; si lo contiene,
        la corrida aborta para no perder deuda en silencio.
        """
        logical_rows, truncated_tail = _logical_csv_lines(text)
        if truncated_tail is not None and "Cliente:" in truncated_tail:
            raise self._csv_error(path, "línea final truncada con datos de cliente")
        cola_rescatada = False

        out_rows: list[dict] = []
        discarded = 0
        sin_saldo_usd = 0
        telefonos_completados = 0
        telefonos_incompletos = 0
        cps_sin_mapear: Counter = Counter()
        pending: Optional[tuple[str, str, Optional[str], str]] = None

        def _completar_telefono(
            telefono_raw: Optional[str], localidad: str
        ) -> Optional[str]:
            """Los teléfonos de este export suelen venir como local pelado, sin
            característica; se completan con la de la localidad del cliente
            (misma fila del reporte). Determinista y auditable: si no da un
            nacional de 10 dígitos, queda el crudo original."""
            nonlocal telefonos_completados, telefonos_incompletos
            if telefono_raw is None:
                return None
            area = area_code_for_locality(localidad)
            completado = complete_national_phone(telefono_raw, area)
            if completado is not None:
                if completado != re.sub(r"\D", "", str(telefono_raw)):
                    telefonos_completados += 1
                return completado
            telefonos_incompletos += 1
            # El CP sin mapear es la causa accionable del fallo: se acumula
            # para poder ampliar AREA_POR_CP con datos de la corrida en vez de
            # adivinar qué localidad faltó.
            if area is None:
                cp = postal_code_for_locality(localidad)
                if cp:
                    cps_sin_mapear[cp] += 1
            return telefono_raw
        for logical in logical_rows:
            try:
                row = next(csv.reader(io.StringIO(logical, newline=""), strict=True), [])
            except csv.Error as error:
                raise self._csv_error(path, str(error)) from error
            cells = [str(cell).strip() for cell in row]
            if "Cliente:" in cells:
                if pending is not None:
                    raise self._csv_error(path, "bloque de cliente sin fila de saldos")
                pending = self._parse_report_client_block(path, row, cells)
                continue
            if pending is None:
                continue  # preambulo del reporte o pagina de totales sin cliente
            cliente_raw, cliente_id, telefono_raw, localidad = pending
            pending = None
            telefono_raw = _completar_telefono(telefono_raw, localidad)
            if len(cells) < 5 or not cells[3] or parse_date(cells[4]) is None:
                raise self._csv_error(path, "fila de saldos con estructura no admitida")
            if not cells[2]:
                sin_saldo_usd += 1
                continue  # cliente sin saldo USD: fuera del universo del ETL
            monto = parse_currency_amount(cells[2])
            if monto is None:
                logger.warning("%s: fila descartada, saldo no parseable", self.fuente)
                discarded += 1
                continue
            out_rows.append(
                {
                    schema.COL_CLIENTE_RAW: cliente_raw,
                    schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                    schema.COL_CLIENTE_ID: cliente_id,
                    schema.COL_TELEFONO_RAW: telefono_raw,
                    schema.COL_PRODUCTO: "Cuenta Corriente",
                    schema.COL_CONCEPTO: "Cuenta Corriente",
                    schema.COL_FECHA: parse_date(cells[4]),
                    schema.COL_REMITO: cells[3],
                    schema.COL_MONTO_ORIGINAL: monto,
                    schema.COL_DIAS_MORA_FUENTE: None,
                    schema.COL_PRIORIDAD_RAW: None,
                    schema.COL_FUENTE: self.fuente,
                }
            )
        if pending is not None:
            # El corte del export dejó al último cliente sin su fila de saldos.
            # Se rescata el importe USD si quedó entero; el comprobante y la
            # fecha no se inventan, así que la fila entra sin fecha y su
            # DiasMora queda en 0, igual que las de Maquinarias. Si el corte
            # partió el importe, no hay nada confiable que rescatar: se aborta.
            saldo_truncado = _rescatar_saldo_truncado(truncated_tail)
            if saldo_truncado is None:
                raise self._csv_error(path, "bloque de cliente sin fila de saldos")
            cola_rescatada = True
            cliente_raw, cliente_id, telefono_raw, localidad = pending
            telefono_raw = _completar_telefono(telefono_raw, localidad)
            monto = parse_currency_amount(saldo_truncado) if saldo_truncado else None
            if monto is None:
                sin_saldo_usd += 1
            else:
                out_rows.append(
                    {
                        schema.COL_CLIENTE_RAW: cliente_raw,
                        schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                        schema.COL_CLIENTE_ID: cliente_id,
                        schema.COL_TELEFONO_RAW: telefono_raw,
                        schema.COL_PRODUCTO: "Cuenta Corriente",
                        schema.COL_CONCEPTO: "Cuenta Corriente",
                        schema.COL_FECHA: None,
                        schema.COL_REMITO: None,
                        schema.COL_MONTO_ORIGINAL: monto,
                        schema.COL_DIAS_MORA_FUENTE: None,
                        schema.COL_PRIORIDAD_RAW: None,
                        schema.COL_FUENTE: self.fuente,
                    }
                )
            # Sin identidades ni importes: el cliente rescatado se ve en la
            # salida; el warning solo avisa que su fecha no existe.
            logger.warning(
                "%s: fila de saldos truncada al final del export; se rescato el "
                "importe USD del ultimo cliente, sin fecha (DiasMora queda en 0)",
                self.fuente,
            )
        if truncated_tail is not None and not cola_rescatada:
            logger.warning(
                "%s: línea final truncada sin bloque de cliente, descartada", self.fuente
            )

        # Warnings (no info): completar un teléfono altera datos de contacto
        # y debe quedar a la vista de la corrida, igual que una fusión de
        # clientes. Solo conteos agregados, sin números ni identidades.
        if telefonos_completados:
            logger.warning(
                "%s: %d telefono(s) completado(s) con la caracteristica de su localidad",
                self.fuente, telefonos_completados,
            )
        if telefonos_incompletos:
            # El detalle por CP es lo que vuelve accionable el warning: sin
            # el, ampliar AREA_POR_CP es adivinar. El CP identifica una
            # localidad, no a un cliente, asi que no viola el criterio de no
            # exponer datos de fila que sigue el resto del modulo.
            detalle = (
                "; CP sin mapear: "
                + ", ".join(f"{cp}({n})" for cp, n in cps_sin_mapear.most_common())
                if cps_sin_mapear
                else ""
            )
            logger.warning(
                "%s: %d telefono(s) siguen incompletos "
                "(localidad sin mapear o largo invalido)%s",
                self.fuente, telefonos_incompletos, detalle,
            )
        logger.info(
            "%s: %d filas validas, %d descartadas, %d sin saldo USD",
            self.fuente, len(out_rows), discarded, sin_saldo_usd,
        )
        if not out_rows:
            raise self._csv_error(path, "reporte sin filas canónicas")
        return _source_extraction(
            pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente
        )

    def _parse_report_client_block(
        self, path: Path, row: list, cells: list[str]
    ) -> tuple[str, str, Optional[str], str]:
        idx = cells.index("Cliente:")
        nombre_cell = cells[idx + 1] if idx + 1 < len(cells) else ""
        match = _REPORT_CLIENTE_RE.match(nombre_cell)
        if not match:
            raise self._csv_error(path, "bloque de cliente sin nombre e ID de Autologica")
        telefono_raw: Optional[str] = None
        if "Teléfono:" in cells:
            tel_idx = cells.index("Teléfono:")
            if tel_idx + 1 < len(row) and str(row[tel_idx + 1]).strip():
                telefono_raw = str(row[tel_idx + 1])
        # La localidad viene como `CP - NOMBRE` tres celdas después del
        # nombre; se usa solo para resolver la característica del teléfono.
        localidad = cells[idx + 4] if idx + 4 < len(cells) else ""
        return match.group("nombre"), match.group("id"), telefono_raw, localidad

    def _csv_error(self, path: Path, cause: str) -> ValueError:
        return ValueError(f"{self.fuente}: CSV inválido: {path.name}: {cause}")


# El export "ficha por pagina" corta el archivo al final: la ultima linea
# logica siempre queda con una comilla sin cerrar. Cuando ese corte cae sobre
# la fila de saldos de un cliente, el importe USD suele haber quedado entero,
# y es el unico dato de esa fila que representa deuda.
_CAMPO_CSV_COMPLETO = re.compile(r'"([^"]*)"')


def _rescatar_saldo_truncado(tail: Optional[str]) -> Optional[str]:
    """Devuelve el Saldo DOLARES de una fila de saldos truncada, o None.

    Solo acepta campos cerrados por comillas: si el corte partio el importe,
    no se completa ni se adivina y el llamador aborta. La fila de saldos se
    reconoce porque su primera celda es vacia, que es lo que la distingue del
    encabezado de una pagina nueva (arranca con el titulo del reporte).
    """
    if not tail:
        return None
    campos = _CAMPO_CSV_COMPLETO.findall(tail)
    if len(campos) < 3 or campos[0].strip():
        return None
    return campos[2].strip()


def _logical_csv_lines(text: str) -> tuple[list[str], Optional[str]]:
    """Reagrupa líneas físicas en líneas lógicas CSV: una comilla sin
    cerrar continúa en la línea siguiente. Devuelve además la cola final
    si el archivo termina con una comilla abierta (export truncado)."""
    logical: list[str] = []
    buffer: list[str] = []
    for line in text.splitlines():
        buffer.append(line)
        joined = "\n".join(buffer)
        if joined.count('"') % 2 == 0:
            logical.append(joined)
            buffer = []
    if buffer:
        return logical, "\n".join(buffer)
    return logical, None


class MaquinariasExtractor:
    """`IA (1).xlsx` — saldos de maquinarias financiadas, ya en USD.

    Header corrido (no en fila 0). Trae teléfono principal y alternativo;
    si el principal es inválido se prueba el alternativo antes de dejar
    el campo vacío.
    """

    fuente = schema.FUENTE_MAQUINARIAS

    def extract(self, path: Path) -> SourceExtraction:
        raw = pd.read_excel(path, header=None)
        rows = raw.values.tolist()
        header_idx = locate_header_row(rows, {"CLIENTES"})
        header_norm = [_norm_header(c) for c in rows[header_idx]]

        col_cliente = header_norm.index("CLIENTES")
        col_producto = _find_col(header_norm, equals="UNIDAD")
        col_monto = _find_col(header_norm, equals="USD")
        col_telefono = _find_col(header_norm, equals="TELEFONO")
        col_telefono_alt = _find_col(header_norm, contains="ALTERNATIVO")
        if col_monto is None:
            raise ValueError(
                f"{self.fuente}: no se encontro la columna 'USD' en el header "
                f"({rows[header_idx]}) de {path.name}"
            )

        out_rows: list[dict] = []
        discarded = 0
        for row in rows[header_idx + 1 :]:
            cliente_raw = row[col_cliente]
            if _is_blank(cliente_raw) or not str(cliente_raw).strip():
                continue

            monto = parse_currency_amount(row[col_monto])
            if monto is None:
                logger.warning("%s: fila descartada, USD no parseable", self.fuente)
                discarded += 1
                continue

            telefono_principal = row[col_telefono] if col_telefono is not None else None
            telefono_alt = row[col_telefono_alt] if col_telefono_alt is not None else None
            telefono_raw = (
                telefono_principal
                if normalize_phone(telefono_principal)
                else (telefono_alt if normalize_phone(telefono_alt) else None)
            )

            out_rows.append(
                {
                    schema.COL_CLIENTE_RAW: str(cliente_raw).strip(),
                    schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                    schema.COL_CLIENTE_ID: None,
                    schema.COL_TELEFONO_RAW: telefono_raw,
                    schema.COL_PRODUCTO: str(row[col_producto]).strip() if col_producto is not None else "",
                    schema.COL_CONCEPTO: "Maquinaria",
                    schema.COL_FECHA: None,
                    schema.COL_REMITO: None,
                    schema.COL_MONTO_ORIGINAL: monto,
                    schema.COL_DIAS_MORA_FUENTE: None,
                    schema.COL_PRIORIDAD_RAW: None,
                    schema.COL_FUENTE: self.fuente,
                }
            )

        logger.info("%s: %d filas validas, %d descartadas", self.fuente, len(out_rows), discarded)
        if not out_rows:
            return _source_extraction(_empty_canonical_df(), self.fuente)
        return _source_extraction(pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente)


def _digitos_puros(value) -> Optional[str]:
    """Devuelve el valor como string de dígitos si es un entero puro
    (int, float entero o string numérico), o None."""
    if _is_blank(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else None
    text = str(value).strip()
    return text if text.isdigit() else None


def _celda_remito(value) -> str:
    return str(int(value)) if isinstance(value, (int, float)) else str(value).strip()


def _parse_servicios_detail_row(
    row: list,
) -> Optional[tuple[str, str, Optional[str], object, float]]:
    """Heurística por fila (no por hoja fija): ubica la fecha por tipo de
    dato, toma el último valor numérico posterior como `Total`, y separa
    remito/cliente de las celdas previas — layout combinado (remito y
    cliente pegados en una celda, con posible truncamiento a ~29
    caracteres), separado en columnas, o plano con columna `Código`
    entre remito y cliente (ver docs/SPEC.md sección 2.3). Devuelve
    `(remito, cliente, codigo, fecha, total)`; `codigo` es el ID de
    Autologica cuando la fila lo trae."""
    fecha_idx = next(
        (i for i, v in enumerate(row) if isinstance(v, (datetime, date, pd.Timestamp))),
        None,
    )
    if fecha_idx is None:
        return None
    fecha = row[fecha_idx]

    numeric_after = [v for v in row[fecha_idx + 1 :] if isinstance(v, (int, float)) and not _is_blank(v)]
    if not numeric_after:
        return None
    total = float(numeric_after[-1])

    pre = [v for v in row[:fecha_idx] if not _is_blank(v)]
    codigo: Optional[str] = None
    if len(pre) == 1 and isinstance(pre[0], str):
        m = _REMITO_CLIENTE_RE.match(pre[0].strip())
        if not m:
            return None
        remito, cliente_raw = m.group(1), m.group(2).strip()
    elif (
        len(pre) >= 3
        and _digitos_puros(pre[1]) is not None
        and str(pre[2]).strip()
        and _digitos_puros(pre[2]) is None
    ):
        # Formato plano `Remito | Código | Cliente | ...`: el código es el
        # ID de Autologica; tomarlo como nombre partiría la identidad.
        remito = _celda_remito(pre[0])
        codigo = _digitos_puros(pre[1])
        cliente_raw = str(pre[2]).strip()
    elif len(pre) >= 2:
        remito = _celda_remito(pre[0])
        cliente_raw = str(pre[1]).strip()
    else:
        return None

    if not cliente_raw:
        return None
    return remito, cliente_raw, codigo, fecha, total


class RemitosServiciosExtractor:
    """`Remitos - Servicios - (1).xlsx` — multi-hoja, formato pivot.

    Cada hoja puede tener un layout de columnas distinto; se detecta por
    fila (tipo de dato), no por nombre de columna fijo. Filas de
    subtotal (`Cliente: X ...`) se descartan como dato, solo indican
    contexto.
    """

    fuente = schema.FUENTE_REMITOS_SERVICIOS

    def extract(self, path: Path) -> SourceExtraction:
        xls = pd.ExcelFile(path)
        out_rows: list[dict] = []
        discarded = 0
        for sheet_name in xls.sheet_names:
            raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for row in raw.values.tolist()[1:]:  # fila 0 = header en cada hoja
                first_cell = row[0]
                if _is_blank(first_cell):
                    continue
                if isinstance(first_cell, str) and _SUBTOTAL_RE.match(first_cell.strip()):
                    continue  # subtotal de pivot: agregado, no se usa como dato

                parsed = _parse_servicios_detail_row(row)
                if parsed is None:
                    logger.warning("%s: fila descartada, no se pudo interpretar", self.fuente)
                    discarded += 1
                    continue

                remito, cliente_raw, codigo, fecha_raw, total = parsed
                out_rows.append(
                    {
                        schema.COL_CLIENTE_RAW: cliente_raw,
                        schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                        schema.COL_CLIENTE_ID: codigo,
                        schema.COL_TELEFONO_RAW: None,
                        schema.COL_PRODUCTO: "Servicios",
                        schema.COL_CONCEPTO: "Servicios",
                        schema.COL_FECHA: parse_date(fecha_raw),
                        schema.COL_REMITO: remito,
                        schema.COL_MONTO_ORIGINAL: total,
                        schema.COL_DIAS_MORA_FUENTE: None,
                        schema.COL_PRIORIDAD_RAW: None,
                        schema.COL_FUENTE: self.fuente,
                    }
                )

        logger.info("%s: %d filas validas, %d descartadas", self.fuente, len(out_rows), discarded)
        if not out_rows:
            return _source_extraction(_empty_canonical_df(), self.fuente)
        return _source_extraction(pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente)


def _split_codigo_cliente(
    glued: str, nombres_limpios: set[str]
) -> tuple[Optional[str], str]:
    """Separa el código de cliente que la extracción de texto del PDF pega
    al nombre en las líneas de detalle (`111FERRARESE MARTIN`).

    Primero intenta contra los nombres limpios de las filas de subtotal del
    mismo PDF (ground truth del archivo: resuelve incluso nombres que
    legítimamente empiezan con dígitos). Si no hay match, heurística: la
    corrida inicial de dígitos es el código siempre que lo que siga no
    empiece con dígito. Devuelve `(codigo, nombre)`; el código es el ID de
    Autologica del cliente.
    """
    candidatos = (n for n in nombres_limpios if glued.endswith(n))
    for nombre in sorted(candidatos, key=len, reverse=True):
        prefijo = glued[: len(glued) - len(nombre)].strip()
        if not prefijo:
            return None, nombre
        if prefijo.isdigit():
            return prefijo, nombre
    match = re.match(r"^(\d+)\s?(?=\D)(.+)$", glued)
    if match:
        return match.group(1), match.group(2).strip()
    return None, glued


class RemitosRepuestosExtractor:
    """`REMITOS - REPUESTOS (1).pdf` — el `.xlsx` equivalente tiene
    corrupción real de texto por celdas superpuestas y se descarta
    deliberadamente (ver docs/SPEC.md sección 2.1); este adapter ni
    siquiera lo abre, usa el PDF."""

    fuente = schema.FUENTE_REMITOS_REPUESTOS

    def extract(self, path: Path) -> SourceExtraction:
        reader = pypdf.PdfReader(str(path))
        lines = [
            line.strip()
            for page in reader.pages
            for line in (page.extract_text() or "").split("\n")
        ]

        # Primer pase: nombres limpios de los subtotales del pivot. Son la
        # referencia para separar el código de cliente que la extracción de
        # texto pega al nombre en las líneas de detalle.
        nombres_subtotal: set[str] = set()
        for line in lines:
            m = _SUBTOTAL_NOMBRE_RE.match(line)
            if m and m.group(1).strip():
                nombres_subtotal.add(m.group(1).strip())

        out_rows: list[dict] = []
        discarded = 0
        excluded_ars = 0
        excluded_unknown = 0
        for line in lines:
            if not line or not line[0].isdigit():
                continue  # header de pagina, subtotal o continuacion de contexto

            m = _REPUESTOS_DETALLE_RE.match(line)
            if not m:
                logger.warning("%s: linea de PDF descartada por formato inválido", self.fuente)
                discarded += 1
                continue

            currency = classify_currency_from_flag(m.group("factura_flag"))
            if currency == "ARS":
                excluded_ars += 1
                continue
            if currency != "USD":
                excluded_unknown += 1
                continue

            codigo, cliente_raw = _split_codigo_cliente(
                m.group("cliente").strip(), nombres_subtotal
            )
            total = parse_currency_amount(m.group("total"))
            if not cliente_raw or total is None:
                discarded += 1
                continue

            out_rows.append(
                {
                    schema.COL_CLIENTE_RAW: cliente_raw,
                    schema.COL_CLIENTE_KEY: normalize_client_name(cliente_raw),
                    schema.COL_CLIENTE_ID: codigo,
                    schema.COL_TELEFONO_RAW: None,
                    schema.COL_PRODUCTO: "Repuestos",
                    schema.COL_CONCEPTO: "Repuestos",
                    schema.COL_FECHA: parse_date(m.group("fecha")),
                    schema.COL_REMITO: m.group("remito"),
                    schema.COL_MONTO_ORIGINAL: total,
                    schema.COL_DIAS_MORA_FUENTE: None,
                    schema.COL_PRIORIDAD_RAW: None,
                    schema.COL_FUENTE: self.fuente,
                }
            )

        logger.info("%s: %d filas validas, %d descartadas", self.fuente, len(out_rows), discarded)
        if not out_rows:
            return _source_extraction(_empty_canonical_df(), self.fuente,
                                      excluded_ars=excluded_ars, excluded_unknown=excluded_unknown)
        return _source_extraction(pd.DataFrame(out_rows, columns=schema.CANONICAL_COLUMNS), self.fuente,
                                  excluded_ars=excluded_ars, excluded_unknown=excluded_unknown)


def extract_all_sources(
    saldos_path: Path,
    maquinarias_path: Path,
    repuestos_path: Path,
    servicios_path: Path,
) -> Iterable[SourceExtraction]:
    """Corre los adapters y devuelve filas USD más diagnósticos agregados."""
    return (
        SaldosGeneralesExtractor().extract(saldos_path),
        MaquinariasExtractor().extract(maquinarias_path),
        RemitosRepuestosExtractor().extract(repuestos_path),
        RemitosServiciosExtractor().extract(servicios_path),
    )
