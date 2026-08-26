"""Reglas de negocio: importes USD, resolución de teléfono,
días de mora, prioridad y consolidación por cliente.

Ver docs/ASSUMPTIONS.md para el detalle de cada regla.
"""

from __future__ import annotations

import difflib
import itertools
import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

import pandas as pd

from . import schema
from .config import PipelineConfig
from .utils import (
    days_overdue,
    display_name,
    is_high_priority,
    normalize_phone,
    to_international_phone,
)


logger = logging.getLogger(__name__)

# Un nombre a 1 caracter del techo tambien cuenta como cortado: si el corte
# cae sobre un espacio, el `.strip()` del extractor se lo come.
_TOLERANCIA_TRUNCADO = 1
# Umbral para aceptar dos grafias como el mismo nombre cuando ademas
# comparten telefono (cubre erratas tipo EMANUEL/EMMANUEL).
_RATIO_MISMO_NOMBRE = 0.90


class ClientPhoneDirectory:
    """Maestro cliente → teléfono, construido a partir de las fuentes
    que sí traen teléfono (Saldos generales, Maquinarias). Los remitos,
    que no traen teléfono, se resuelven contra este maestro por
    `cliente_key`."""

    def __init__(self) -> None:
        self._phone_by_key: dict[str, str] = {}
        self._display_name_by_key: dict[str, str] = {}

    def register(self, sources: Iterable[pd.DataFrame], min_digits: int, max_digits: int) -> None:
        """Gana el mejor teléfono, no el primero.

        `normalize_phone` admite de 8 a 13 dígitos pero `to_international_phone`
        exige un nacional de 10: entre los dos umbrales hay una franja de
        números que entran al maestro y después no sirven para la salida. Con
        *first-wins* un local pelado de 8 dígitos bloqueaba al de 10 que traía
        otra fuente, y el cliente quedaba sin teléfono teniendo uno bueno.
        Un candidato internacionalizable reemplaza a uno que no lo es; entre
        dos igual de buenos gana el primero, para que la corrida sea
        determinística y no dependa del orden de las fuentes.
        """
        for df in sources:
            for _, row in df.iterrows():
                key = row[schema.COL_CLIENTE_KEY]
                if not key:
                    continue
                self._display_name_by_key.setdefault(
                    key, display_name(row[schema.COL_CLIENTE_RAW])
                )
                phone = normalize_phone(
                    row.get(schema.COL_TELEFONO_RAW), min_digits, max_digits
                )
                if not phone:
                    continue
                guardado = self._phone_by_key.get(key)
                if guardado is None or (
                    to_international_phone(phone) and not to_international_phone(guardado)
                ):
                    self._phone_by_key[key] = phone

    def lookup_phone(self, cliente_key: str) -> Optional[str]:
        return self._phone_by_key.get(cliente_key)

    def lookup_display_name(self, cliente_key: str, fallback: str) -> str:
        return self._display_name_by_key.get(cliente_key, fallback)


def build_detail(
    canonical_dfs: Iterable[pd.DataFrame],
    phone_directory: ClientPhoneDirectory,
    config: PipelineConfig,
) -> pd.DataFrame:
    """Une los 4 DataFrames canónicos y agrega las columnas calculadas:
    teléfono resuelto, monto en USD, días de mora y prioridad."""
    combined = pd.concat(list(canonical_dfs), ignore_index=True)
    if combined.empty:
        return combined.assign(
            **{
                schema.COL_TELEFONO: pd.Series(dtype="object"),
                schema.COL_MONTO_USD: pd.Series(dtype="float"),
                schema.COL_DIAS_MORA: pd.Series(dtype="int"),
                schema.COL_PRIORIDAD: pd.Series(dtype="bool"),
            }
        )

    combined[schema.COL_TELEFONO] = combined.apply(
        lambda r: normalize_phone(
            r[schema.COL_TELEFONO_RAW], config.telefono_min_digitos, config.telefono_max_digitos
        )
        or phone_directory.lookup_phone(r[schema.COL_CLIENTE_KEY]),
        axis=1,
    )
    combined[schema.COL_MONTO_USD] = combined.apply(
        lambda r: round(float(r[schema.COL_MONTO_ORIGINAL]), 2),
        axis=1,
    )
    combined[schema.COL_DIAS_MORA] = combined.apply(
        lambda r: _resolve_dias_mora(r, config.reference_date), axis=1
    )
    combined[schema.COL_PRIORIDAD] = combined[schema.COL_PRIORIDAD_RAW].apply(is_high_priority)
    return combined


@dataclass(frozen=True)
class _ClienteFacts:
    """Lo que se sabe de una `cliente_key` para decidir si es la misma
    persona que otra."""

    key: str
    raw: str
    truncado: bool
    tiene_id: bool
    cliente_id: Optional[str]
    telefono: Optional[str]


def _techos_de_longitud(detail: pd.DataFrame) -> dict[str, int]:
    """Largo máximo de nombre observado en cada fuente.

    Las fuentes son reportes con ancho de columna fijo: cuando un nombre
    llega al techo, está cortado. Se mide sobre los datos en vez de fijar
    la constante porque cada corrida puede traer otro ancho de pivot.
    """
    return {
        str(fuente): int(group[schema.COL_CLIENTE_RAW].str.len().max())
        for fuente, group in detail.groupby(schema.COL_FUENTE)
    }


def _client_facts(detail: pd.DataFrame) -> dict[str, _ClienteFacts]:
    techos = _techos_de_longitud(detail)
    facts: dict[str, _ClienteFacts] = {}
    for key, group in detail.groupby(schema.COL_CLIENTE_KEY):
        if not key:
            continue
        raws = [str(r) for r in group[schema.COL_CLIENTE_RAW]]
        truncado = any(
            len(str(r)) >= techos[str(f)] - _TOLERANCIA_TRUNCADO
            for r, f in zip(group[schema.COL_CLIENTE_RAW], group[schema.COL_FUENTE])
        )
        cliente_id = _first_cliente_id(group)
        facts[str(key)] = _ClienteFacts(
            key=str(key),
            raw=max(raws, key=len),
            truncado=truncado,
            tiene_id=cliente_id is not None,
            cliente_id=cliente_id,
            telefono=next((t for t in group[schema.COL_TELEFONO] if t), None),
        )
    return facts


def _es_prefijo_token(corto: str, largo: str) -> bool:
    """Prefijo por palabras completas: `LA LOMA` es prefijo de
    `LA LOMA PRODUCTORA`, pero `MACAGNO MATI` no lo es de nada."""
    return largo.startswith(corto + " ")


def _es_prefijo_caracteres(corto: str, largo: str) -> bool:
    """Prefijo por caracteres: el ancho de columna corta donde cae, y
    `AGROLOGISTICA HUANCHILL` quedó partido en mitad de la palabra."""
    return len(corto) < len(largo) and largo.startswith(corto)


def _es_el_mismo_cliente(a: _ClienteFacts, b: _ClienteFacts) -> Optional[str]:
    """Devuelve el motivo de la fusión, o None si son clientes distintos."""
    # Mismo ID de Autologica: no es heurística, es el sistema de registro
    # diciendo que son la misma cuenta. Va primero porque no admite
    # interpretación y porque cubre los casos que las reglas de nombre no
    # pueden ver: `FINOCCHI`/`FINOCHI` divergen en el caracter 5 (ninguno es
    # prefijo del otro) y sin teléfono la regla de errata nunca se evalúa.
    if a.cliente_id and b.cliente_id and a.cliente_id == b.cliente_id:
        return "mismo ID Autologica"

    prefijo = _es_prefijo_token(a.key, b.key) or _es_prefijo_token(b.key, a.key)

    # Truncamiento: uno es prefijo del otro (por caracteres, porque el corte
    # cae donde cae) Y alguno llegó al techo de su fuente. El techo es lo que
    # hace segura la regla: sin él se fusionarían entidades legítimamente
    # distintas cuyo nombre arranca igual — una SRL y una SAU homónimas, o
    # una persona y la sociedad de hecho que integra.
    if a.truncado or b.truncado:
        if _es_prefijo_caracteres(a.key, b.key) or _es_prefijo_caracteres(b.key, a.key):
            return "truncamiento"

    # Mismo teléfono: solo alcanza si además el nombre es reconociblemente
    # el mismo. Dos clientes distintos pueden compartir línea (una persona
    # y su razón social), y fusionarlos les mezclaría la deuda.
    if a.telefono and a.telefono == b.telefono:
        if prefijo:
            return "telefono+nombre incompleto"
        if difflib.SequenceMatcher(None, a.key, b.key).ratio() >= _RATIO_MISMO_NOMBRE:
            return "telefono+errata"
    return None


def _canonico(a: _ClienteFacts, b: _ClienteFacts) -> tuple[_ClienteFacts, _ClienteFacts]:
    """Gana el que tiene ID de Autologica (es el sistema de registro); si
    empatan, el que no está truncado; si siguen empatando, el nombre más
    largo. Devuelve `(ganador, perdedor)`."""
    if a.tiene_id != b.tiene_id:
        return (a, b) if a.tiene_id else (b, a)
    if a.truncado != b.truncado:
        return (b, a) if a.truncado else (a, b)
    return (a, b) if len(a.raw) >= len(b.raw) else (b, a)


class _Alias:
    """Union-find mínimo: cada clave apunta a su canónica."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, key: str) -> str:
        self._parent.setdefault(key, key)
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, perdedor: str, ganador: str) -> None:
        raiz_p, raiz_g = self.find(perdedor), self.find(ganador)
        if raiz_p != raiz_g:
            self._parent[raiz_p] = raiz_g


def resolve_duplicate_clients(detail: pd.DataFrame) -> pd.DataFrame:
    """Une las filas que son del mismo cliente pero llegaron con la clave
    partida, y reescribe `cliente_key`/`cliente_raw` a la variante canónica.

    Dos motivos reales, ambos de la fuente (ver docs/ASSUMPTIONS.md 3):
    el nombre viene cortado por el ancho de columna del reporte, o viene
    con una errata y solo el teléfono delata que es la misma persona.
    Cada fusión se loguea para que la corrida sea auditable.
    """
    if detail.empty:
        return detail

    facts = _client_facts(detail)
    alias = _Alias()
    for a, b in itertools.combinations(facts.values(), 2):
        motivo = _es_el_mismo_cliente(a, b)
        if motivo is None:
            continue
        ganador, perdedor = _canonico(a, b)
        alias.union(perdedor.key, ganador.key)
        # warning, no info: el proyecto no configura logging, asi que solo
        # WARNING o mas llega al operador. Fusionar clientes reasigna deuda;
        # tiene que quedar a la vista de la corrida, igual que un descarte.
        logger.warning("cliente duplicado resuelto por %s", motivo)

    resuelto = detail.copy()
    resuelto[schema.COL_CLIENTE_KEY] = resuelto[schema.COL_CLIENTE_KEY].map(
        lambda k: alias.find(str(k)) if k else k
    )
    resuelto[schema.COL_CLIENTE_RAW] = [
        facts[k].raw if k in facts else raw
        for k, raw in zip(resuelto[schema.COL_CLIENTE_KEY], resuelto[schema.COL_CLIENTE_RAW])
    ]
    return resuelto


def _resolve_dias_mora(row: pd.Series, reference_date: date) -> int:
    dias_fuente = row.get(schema.COL_DIAS_MORA_FUENTE)
    if dias_fuente is not None and not pd.isna(dias_fuente):
        return int(dias_fuente)
    return days_overdue(row.get(schema.COL_FECHA), reference_date)


def _producto_label(row: pd.Series) -> str:
    producto = row[schema.COL_PRODUCTO]
    label = str(producto).strip() if producto else ""
    return label or "SinDescripcion"


def _productos_entries(group: pd.DataFrame) -> list[tuple[str, float, bool]]:
    """Entradas `(producto, monto_usd, es_remito)` en orden de aparición.

    Las deudas que vienen de Remitos no traen el concepto individual en la
    fuente: el producto es siempre la categoría ("Servicios", "Repuestos"),
    así que repetirla N veces genera entradas indistinguibles entre sí. Esas
    se suman en una única entrada por categoría. El resto conserva una
    entrada por deuda, porque ahí el producto sí es dato real (la unidad de
    maquinaria, la cuenta corriente)."""
    entries: list[list] = []
    index_by_label: dict[str, int] = {}
    for _, r in group.iterrows():
        label = _producto_label(r)
        monto = float(r[schema.COL_MONTO_USD])
        es_remito = r[schema.COL_FUENTE] in schema.FUENTES_REMITOS
        if es_remito:
            existing = index_by_label.get(label)
            if existing is not None:
                entries[existing][1] += monto
                continue
            index_by_label[label] = len(entries)
        entries.append([label, monto, es_remito])
    return [(label, round(monto, 2), es_remito) for label, monto, es_remito in entries]


def _productos_array(entries: Iterable[tuple[str, float, bool]]) -> str:
    """Serializa las entradas como `producto:monto`, separadas por `;`."""
    return ";".join(f"{label}:{monto:.2f}" for label, monto, _ in entries)


def _first_cliente_id(group: pd.DataFrame) -> Optional[str]:
    for cid in group[schema.COL_CLIENTE_ID]:
        if cid is not None and not (isinstance(cid, float) and pd.isna(cid)) and str(cid).strip():
            return str(cid).strip()
    return None


def consolidate_by_client(
    detail: pd.DataFrame, phone_directory: ClientPhoneDirectory
) -> pd.DataFrame:
    """Un cliente con deuda en varias fuentes queda con una sola fila:
    saldo total sumado (columna aparte), array `producto:monto` con el
    desglose (las deudas de Remitos consolidadas por categoría), días de
    mora = máximo, prioridad = OR. `ProductosRemitos` repite solo las
    entradas originadas en Remitos, y queda vacío si el cliente no tiene.
    Teléfono en formato internacional de celular. Ordenado por prioridad y
    luego saldo descendente."""
    if detail.empty:
        return pd.DataFrame(columns=schema.OUTPUT_COLUMNS)

    grouped = detail.groupby(schema.COL_CLIENTE_KEY)
    rows = []
    for cliente_key, group in grouped:
        # Mismo criterio que ClientPhoneDirectory.register: gana el primero
        # que sirva para la salida, no el primero a secas. Si ninguno pasa se
        # conserva el crudo, que igual queda visible en el detalle aunque
        # to_international_phone lo descarte del ROMAN y del E1KIA.
        telefono = next(
            (t for t in group[schema.COL_TELEFONO] if t and to_international_phone(t)),
            next((t for t in group[schema.COL_TELEFONO] if t), None),
        )
        entries = _productos_entries(group)
        rows.append(
            {
                schema.OUT_NOMBRE_APELLIDO: phone_directory.lookup_display_name(
                    cliente_key, display_name(group[schema.COL_CLIENTE_RAW].iloc[0])
                ),
                schema.OUT_TELEFONO_CLIENTE: to_international_phone(telefono),
                schema.OUT_SALDO_EXIGIBLE_USD: round(float(group[schema.COL_MONTO_USD].sum()), 2),
                schema.OUT_CANTIDAD_PRODUCTOS: int(len(entries)),
                schema.OUT_PRODUCTOS: _productos_array(entries),
                schema.OUT_DIAS_MORA: int(group[schema.COL_DIAS_MORA].max()),
                schema.OUT_FLAG_PRIORIDAD: bool(group[schema.COL_PRIORIDAD].any()),
                schema.OUT_CLIENTE_ID: _first_cliente_id(group),
                schema.OUT_PRODUCTOS_REMITOS: _productos_array(
                    e for e in entries if e[2]
                ),
            }
        )

    result = pd.DataFrame(rows, columns=schema.OUTPUT_COLUMNS)
    return result.sort_values(
        by=[schema.OUT_FLAG_PRIORIDAD, schema.OUT_SALDO_EXIGIBLE_USD],
        ascending=[False, False],
    ).reset_index(drop=True)
