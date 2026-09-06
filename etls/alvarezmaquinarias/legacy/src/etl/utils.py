"""Utilidades puras de limpieza y parsing (sin dependencias de I/O)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional

import pandas as pd

_LEGAL_SUFFIXES = (
    "SOCIEDAD ANONIMA",
    "SOCIEDAD DE RESPONSABILIDAD LIMITADA",
    "SOCIEDAD EN COMANDITA SIMPLE",
    "SAS",
    "SRL",
    "SA",
    "SH",
    "SCS",
)
_NON_ALNUM_SPACE = re.compile(r"[^A-Z0-9 ]")
_MULTISPACE = re.compile(r"\s+")
# Un unico separador solo agrupa miles si los grupos son de tres digitos
# exactos (`17.264`, `17,264`). Ver parse_currency_amount.
_GRUPOS_DE_MILES = re.compile(r"^-?\d{1,3}(?:[.,]\d{3})+$")
# Marca de moneda, pegada al numero o separada. Sin `\b`: en `USD1.149,20` no
# hay frontera de palabra entre la D y el 1, asi que exigirla dejaba el
# prefijo puesto y el importe entero sin parsear. Las variantes largas van
# primero para que `U$S`/`US$` no se coman solo el `$`.
_MARCA_DE_MONEDA = re.compile(r"(?i)\s*(?:USD|U\$S|US\$|\$)\s*")


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _cerrar_corrida_de_iniciales(run: list[str]) -> list[str]:
    """Cierra una corrida de letras sueltas separando la sigla societaria.

    La corrida puede mezclar la inicial de un nombre con la sigla: en
    `ALESSO GERMAN R S.H.` quedan `R`, `S`, `H` juntos, y pegarlos enteros
    daba `RSH`, que el stripper de sufijos no reconoce. La misma sociedad
    escrita `SH` sin puntos producía `ALESSO GERMAN R` — dos claves para el
    mismo deudor, que es justo lo que esta normalización viene a evitar.

    Se corta por el sufijo **más largo** que quede al final de la corrida;
    las iniciales que lo preceden vuelven como tokens sueltos.
    """
    for corte in range(len(run)):
        candidato = "".join(run[corte:])
        if candidato in _LEGAL_SUFFIXES:
            # Las iniciales que preceden a la sigla se unen entre si, igual
            # que si la sigla no estuviera: `MOLINO J M S.A.S.` y
            # `MOLINO J M SAS` tienen que dar la misma clave.
            previas = ["".join(run[:corte])] if corte else []
            return previas + [candidato]
    return ["".join(run)]


def _merge_initial_runs(tokens: list[str]) -> list[str]:
    """Reune corridas de tokens de una sola letra en un token único.

    Sacar la puntuación convierte `S.A.` en dos tokens (`S`, `A`) y el
    stripper de sufijos deja de reconocerlo: `TIGONBU S.A.` y `TIGONBU SA`
    terminaban con claves distintas y el cliente se duplicaba. Reunir la
    corrida devuelve `SA` y las dos grafías vuelven a ser la misma.

    Cuando la corrida arranca con iniciales de un nombre —el patrón de las
    sociedades de hecho, `... GERMAN R S.H.`— la sigla se separa del resto
    (ver `_cerrar_corrida_de_iniciales`).
    """
    merged: list[str] = []
    run: list[str] = []
    for token in tokens:
        if len(token) == 1 and token.isalpha():
            run.append(token)
            continue
        if run:
            merged.extend(_cerrar_corrida_de_iniciales(run))
            run = []
        merged.append(token)
    if run:
        merged.extend(_cerrar_corrida_de_iniciales(run))
    return merged


def normalize_client_name(raw_name: Optional[str]) -> str:
    """Clave de join determinística: mayúsculas, sin acentos/puntuación
    ni sufijos societarios. Ver docs/ASSUMPTIONS.md sección 3."""
    if raw_name is None or (isinstance(raw_name, float) and pd.isna(raw_name)):
        return ""
    text = _strip_accents(str(raw_name)).upper()
    text = _NON_ALNUM_SPACE.sub(" ", text)
    text = _MULTISPACE.sub(" ", text).strip()

    tokens = _merge_initial_runs(text.split(" ")) if text else []
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def display_name(raw_name: Optional[str]) -> str:
    """Nombre legible para reportes (no se usa para matching)."""
    if raw_name is None or (isinstance(raw_name, float) and pd.isna(raw_name)):
        return ""
    return _MULTISPACE.sub(" ", str(raw_name)).strip()


def normalize_phone(
    raw_phone: Optional[str], min_digits: int = 8, max_digits: int = 13
) -> Optional[str]:
    """Devuelve solo dígitos si el teléfono es válido, o None.

    No corrige ni completa prefijos: solo valida longitud (ver
    docs/ASSUMPTIONS.md sección 4).
    """
    if raw_phone is None or (isinstance(raw_phone, float) and pd.isna(raw_phone)):
        return None
    digits = re.sub(r"\D", "", str(raw_phone))
    if min_digits <= len(digits) <= max_digits:
        return digits
    return None


def to_international_phone(raw_phone: Optional[str]) -> Optional[str]:
    """Formatea un teléfono argentino a formato internacional de celular:
    `54` + `9` + número nacional de 10 dígitos (código de área + abonado).

    Decisión de negocio: las 4 bases no distinguen fijo de celular, y son
    números de contacto para una campaña de llamadas/WhatsApp, así que
    **todos** se tratan como celular (prefijo `549`). Los números que no
    son un nacional de 10 dígitos (incompletos, sin código de área) se
    consideran inválidos y devuelven None (quedan fuera de las salidas).

    Un nacional de 10 dígitos nunca empieza con `0` (prefijo de larga
    distancia) ni con `15` (notación local de celular: ninguna
    característica argentina empieza con 15); esos son falsos válidos y
    también devuelven None.

    Ej.: `3385464768` -> `5493385464768`.
    """
    digits = normalize_phone(raw_phone)
    if digits is None or len(digits) != 10 or digits.startswith(("0", "15")):
        return None
    return "549" + digits


def complete_national_phone(
    raw_phone: Optional[str], area_code: Optional[str]
) -> Optional[str]:
    """Reconstruye el nacional de 10 dígitos de un teléfono incompleto.

    Correcciones deterministas — se reordena lo que ya está en el número,
    nunca se inventan dígitos:

    - quita los prefijos internacionales `549`/`54` y el `0` de larga
      distancia
    - quita el `15` de la notación local de celular (al inicio, o después
      del código de área si se conoce)
    - antepone `area_code` (la característica de la localidad del cliente)
      cuando el número es un local pelado

    Devuelve None si el resultado no da exactamente 10 dígitos.
    """
    if raw_phone is None or (isinstance(raw_phone, float) and pd.isna(raw_phone)):
        return None
    digits = re.sub(r"\D", "", str(raw_phone))
    if digits.startswith("549") and len(digits) >= 13:
        digits = digits[3:]
    elif digits.startswith("54") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    area = str(area_code) if area_code else None

    if len(digits) == 10 and not digits.startswith(("0", "15")):
        return digits
    if digits.startswith("15"):
        digits = digits[2:]
    elif area and digits.startswith(area) and digits[len(area) : len(area) + 2] == "15":
        digits = area + digits[len(area) + 2 :]
    if len(digits) == 10 and not digits.startswith(("0", "15")):
        return digits
    if area and len(area) + len(digits) == 10:
        return area + digits
    return None


def parse_currency_amount(raw_value) -> Optional[float]:
    """Parsea montos en formato AR (`$1.200,50`) o con marca de moneda,
    separada (`USD 850,00`) o pegada al numero (`USD1.149,20`, `U$S1.149,20`).

    Devuelve None si el valor está vacío o no es parseable (fila inválida,
    se descarta aguas arriba en vez de asumir 0).

    Las fuentes mezclan convención argentina (`17.264,70`) e inglesa
    (`17,264.70`) — el export de saldos trae las dos en el mismo archivo —
    así que la convención **no se puede deducir de la fuente**. Se deduce de
    la forma del valor, que es lo único confiable:

    - Con ambos separadores, el que está más a la derecha es el decimal y el
      otro agrupa miles. Asumir siempre coma decimal leía `17,264.70` como
      17,2647: el error de escala /1000 que llegó al agente de voz.
    - Con un solo separador es ambiguo, y se resuelve por la forma del
      agrupamiento: grupos de tres dígitos exactos (`17.264`) son miles;
      cualquier otra cosa (`965.47`, `853,01`) es decimal.

    Ver docs/ASSUMPTIONS.md sección 2.
    """
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    text = str(raw_value).strip()
    text = _MARCA_DE_MONEDA.sub("", text).strip()
    if not text:
        return None

    ultimo_punto = text.rfind(".")
    ultima_coma = text.rfind(",")
    if ultimo_punto >= 0 and ultima_coma >= 0:
        if ultima_coma > ultimo_punto:  # 17.264,70 -> decimal es la coma
            text = text.replace(".", "").replace(",", ".")
        else:  # 17,264.70 -> decimal es el punto
            text = text.replace(",", "")
    elif ultimo_punto >= 0 or ultima_coma >= 0:
        if _GRUPOS_DE_MILES.fullmatch(text):  # 17.264 / 17,264
            text = text.replace(".", "").replace(",", "")
        else:  # 965.47 / 853,01
            text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def classify_currency_from_flag(raw_value, dollar_marker: str = "DOLAR") -> str:
    """Clasifica el flag sin retener datos de la fila de origen."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return "UNKNOWN"
    text = _strip_accents(str(raw_value)).upper()
    if dollar_marker in text:
        return "USD"
    if "PESO" in text or "FACTURA" in text:
        return "ARS"
    return "UNKNOWN"


def is_high_priority(raw_value) -> bool:
    """`True` si el flag de prioridad de origen contiene `'ALTA'`."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return False
    return "ALTA" in str(raw_value).upper()


def parse_date(raw_value) -> Optional[date]:
    """Parsea fechas `dd/mm/aaaa` o cualquier tipo ya-datetime de pandas."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return None
    if isinstance(raw_value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(raw_value).date()
    try:
        return datetime.strptime(str(raw_value).strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def days_overdue(debt_date: Optional[date], reference_date: date) -> int:
    if debt_date is None:
        return 0
    return max((reference_date - debt_date).days, 0)


def locate_header_row(rows: list, marker_tokens: set[str], max_scan: int = 20) -> int:
    """Devuelve el índice de la primera fila (entre las primeras
    `max_scan`) donde alguna celda, tras trim+upper, coincide exactamente
    con alguno de `marker_tokens`. Reemplaza asumir header en fila fija —
    ver docs/SPEC.md sección 2.2.

    Lanza `ValueError` si no aparece (fail-fast ante un export con un
    formato completamente distinto al esperado).
    """
    tokens_upper = {t.upper() for t in marker_tokens}
    limit = min(len(rows), max_scan)
    for i in range(limit):
        for cell in rows[i]:
            if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                continue
            if str(cell).strip().upper() in tokens_upper:
                return i
    raise ValueError(
        f"No se encontro fila de header con alguno de los marcadores "
        f"{marker_tokens} en las primeras {limit} filas"
    )
