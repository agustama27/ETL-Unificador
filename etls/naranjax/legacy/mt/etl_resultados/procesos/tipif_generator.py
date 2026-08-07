from __future__ import annotations

import csv
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


# Directorios base dentro de etl_resultados
BASE_DIR = Path(__file__).resolve().parent.parent
ROMAN_DIR = BASE_DIR / "roman"
RESULTADOS_DIR = BASE_DIR / "resultados"

# Tipificaciones de Roman
PROMISE_TIPIFICATIONS = {
    # Promesa de pago
    "cpc - d1 - confirma pago",
    "cpc - d5 - confirma pago",
    "promesa de pago",
}

DIFFICULTY_TIPIFICATIONS = {
    # Dificultad de pago
    "cpc - d5 - no confirma pago",
    "cpc - d5 - pregunta si pagara",
    "dificultad de pago",
}

PAID_TIPIFICATIONS = {
    # Ya pago
    "cpc - d1 - ya pago",
}

NOANSWER_TIPIFICATIONS = {
    # No contesta
    "noanswer",
}

CALLBACK_TIPIFICATIONS = {
    # Volver a llamar (no contacto con titular)
    "ncpc - pregunta se es familiar directo",
    "ncpc - no conoce la persona",
}

CPC_PERSON_TIPIFICATIONS = {
    # CPC - Es la persona
    "cpc - es la persona",
}


def _normalize_text(value: str | None) -> str:
    """Normaliza texto para comparaciones flexibles (minúsculas, sin tildes)."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _find_column(header: Sequence[str], search_terms: Iterable[str]) -> int:
    """
    Devuelve el índice de la primera columna cuyo nombre contenga
    alguno de los términos de búsqueda (flexible, sin tildes y sin
    depender del texto exacto).
    """
    normalized_header = [_normalize_text(h) for h in header]
    normalized_terms = [_normalize_text(t) for t in search_terms]

    for idx, col in enumerate(normalized_header):
        for term in normalized_terms:
            if term and term in col:
                return idx

    raise ValueError(
        f"No se encontró ninguna columna que contenga alguno de: {list(search_terms)}"
    )


def _parse_fecha_hora(value: str) -> str:
    """
    Convierte la fecha/hora del reporte de Roman (por ejemplo
    '03/03/2026, 10:14') al formato AAAAMMDDHHMMSS.
    """
    raw = (value or "").strip().strip('"')
    if not raw:
        return ""

    formatos = [
        "%d/%m/%Y, %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y, %H:%M",
        "%d/%m/%Y %H:%M",
    ]

    for fmt in formatos:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y%m%d%H%M%S")
        except ValueError:
            continue

    raise ValueError(f"No se pudo parsear la fecha y hora: {value!r}")


def _parse_fecha_compromiso(value: str) -> str:
    """
    Convierte la fecha de compromiso (DD/MM/AAAA) al formato AAAAMMDDHHMMSS.
    Se asume hora en punto por defecto: 00:00:00.
    """
    raw = (value or "").strip().strip('"')
    if not raw:
        return ""

    formatos = [
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for fmt in formatos:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y%m%d000000")
        except ValueError:
            continue

    raise ValueError(f"No se pudo parsear la fecha de compromiso: {value!r}")


def _split_phone(desde: str) -> tuple[str, str, str]:
    """
    Separa el número de 'Desde' en:
    - número sin prefijo (columna 15)
    - prefijo (columna 16)
    - tipo de teléfono 'CEL' o 'TEL' (columna 17)

    La detección de tipo se basa en el prefijo internacional:
    - +549... -> CEL
    - +54...  -> TEL
    """
    if not desde:
        return "", "", ""

    digits = "".join(c for c in str(desde) if c.isdigit())
    if not digits:
        return "", "", ""

    tel_type = ""
    core = digits

    if digits.startswith("549"):
        tel_type = "CEL"
        core = digits[3:]
    elif digits.startswith("54"):
        tel_type = "TEL"
        core = digits[2:]

    if not core:
        return "", "", tel_type

    # Heurística simple: últimos 7 dígitos como número, el resto como prefijo
    if len(core) > 7:
        numero = core[-7:]
        prefijo = core[:-7]
    else:
        numero = core
        prefijo = ""

    if not tel_type:
        # Fallback sencillo: muchos celulares locales comienzan con '15'
        tel_type = "CEL" if numero.startswith("15") else "TEL"

    return numero, prefijo, tel_type


def _normalize_monto(monto: str) -> str:
    """
    Normaliza el monto al formato de ejemplo de tipificaciones:
    usa coma como separador decimal.
    """
    valor = (monto or "").strip()
    if not valor:
        return ""
    # Si viene con punto decimal, lo convertimos a coma
    if "." in valor and "," not in valor:
        valor = valor.replace(".", ",")
    return valor


def generar_tipificaciones(archivo_roman: str | Path | None = None) -> Path:
    """
    Genera el archivo de tipificaciones en base al reporte de Roman.

    - Lee el CSV de Roman en la carpeta 'roman' (o el pasado por parámetro).
    - Filtra filas según tipificación de salida:
        * CPC - D1 - Confirma pago
        * CPC - D5 - Confirma pago
        * CPC - D5 - No confirma pago
        * CPC - D5 - Pregunta si pagara
        * CPC - D1 - Ya Pago
        * NoAnswer
        * NCPC - Pregunta se es familiar directo
        * NCPC - No conoce la persona
        * CPC - Es la persona
    - Construye un TXT de salida en 'resultados' con 40 columnas
      siguiendo la estructura de ejemplo:
        * PROMISE           -> estructura de promesas de pago
        * PAYMENT DIFFICULTY -> estructura de dificultad de pago
    """
    if archivo_roman is None:
        archivos = list(ROMAN_DIR.glob("*.csv"))
        if not archivos:
            raise FileNotFoundError(f"No se encontraron CSV en {ROMAN_DIR}")
        archivo_roman = max(archivos, key=lambda p: p.stat().st_mtime)
    else:
        archivo_roman = Path(archivo_roman)
        if not archivo_roman.is_absolute():
            archivo_roman = ROMAN_DIR / archivo_roman

    if not archivo_roman.exists():
        raise FileNotFoundError(f"El archivo de Roman no existe: {archivo_roman}")

    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)

    # Nombre de salida similar al ejemplo pero basado en la fecha actual
    fecha_hoy = datetime.now().strftime("%Y%m%d")
    archivo_salida = RESULTADOS_DIR / f"DEELO_NAR_USUOLOS_{fecha_hoy}.txt"

    with open(archivo_roman, "r", encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(f, dialect)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("El archivo de Roman está vacío")

        # Resolver índices de columnas de forma flexible
        try:
            fecha_idx = _find_column(header, ["fecha y hora"])
        except ValueError:
            # Compatibilidad con reportes que traen solo "Fecha"
            fecha_idx = _find_column(header, ["fecha"])
        id_cliente_idx = _find_column(header, ["id cliente", "id_cliente"])
        numero_cuenta_idx = _find_column(
            header, ["numero cuenta", "nro cuenta", "numero_cuenta"]
        )
        desde_idx = _find_column(header, ["desde"])
        tipif_idx = _find_column(header, ["[salida] tipificaciones", "tipificaciones"])
        monto_idx = _find_column(header, ["monto deuda", "monto de deuda", "monto_deuda"])
        try:
            fecha_compromiso_idx = _find_column(
                header,
                ["[salida] fecha compromiso", "fecha compromiso", "fecha_compromiso"],
            )
        except ValueError:
            fecha_compromiso_idx = None

        filas_salida: list[list[str]] = []

        for row in reader:
            if not row:
                continue

            # Aseguramos tamaño suficiente por si hay filas más cortas
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))

            tipif_val = _normalize_text(row[tipif_idx])
            if tipif_val in PROMISE_TIPIFICATIONS:
                tipo_evento = "PROMISE"
            elif tipif_val in DIFFICULTY_TIPIFICATIONS:
                tipo_evento = "PAYMENT_DIFFICULTY"
            elif tipif_val in PAID_TIPIFICATIONS:
                tipo_evento = "PAID"
            elif tipif_val in NOANSWER_TIPIFICATIONS:
                tipo_evento = "NO_ANSWER"
            elif tipif_val in CALLBACK_TIPIFICATIONS:
                tipo_evento = "CALLBACK"
            elif tipif_val in CPC_PERSON_TIPIFICATIONS:
                tipo_evento = "HANGUP"
            else:
                continue

            try:
                fecha_formateada = _parse_fecha_hora(row[fecha_idx])
            except ValueError:
                # Si la fecha no se puede parsear, salteamos la fila
                continue

            id_cliente = (row[id_cliente_idx] or "").strip()
            # Si no hay Id Cliente, no se debe tipificar esta fila
            if not id_cliente or id_cliente == "-":
                continue

            numero_cuenta = (row[numero_cuenta_idx] or "").strip()
            desde_valor = (row[desde_idx] or "").strip()
            monto_valor = _normalize_monto(row[monto_idx])

            telefono_sin_pref, prefijo, tel_type = _split_phone(desde_valor)

            columnas = ["" for _ in range(40)]

            # Asignaciones comunes según especificación del usuario
            columnas[0] = fecha_formateada  # col 1
            columnas[1] = id_cliente  # col 2
            columnas[2] = "NARANJA"  # col 3
            # col 4,5,6 dependen del tipo de evento
            # col 7 en blanco por ahora
            columnas[7] = "USUOLOS"  # col 8
            columnas[8] = "N"  # col 9
            columnas[9] = "MAKE CALL"  # col 10
            columnas[11] = "VOICEBOT"  # col 12
            # col 13 y 14 en blanco
            columnas[14] = telefono_sin_pref  # col 15
            columnas[15] = prefijo  # col 16
            columnas[16] = tel_type  # col 17

            columnas[35] = "DEELO"  # col 36
            columnas[36] = "1"  # col 37
            columnas[38] = "PENDING"  # col 39
            columnas[39] = fecha_formateada  # col 40

            if tipo_evento == "PROMISE":
                # Estructura de promesas de pago
                columnas[3] = numero_cuenta  # col 4
                columnas[4] = "NARANJA"  # col 5
                columnas[5] = "NARANJA"  # col 6
                columnas[10] = "PROMISE"  # col 11
                columnas[27] = monto_valor  # col 28
                # Columna 29: fecha pactada a partir de [Salida] Fecha Compromiso
                fecha_pactada = ""
                if fecha_compromiso_idx is not None:
                    valor_compromiso = (row[fecha_compromiso_idx] or "").strip()
                    if valor_compromiso:
                        try:
                            fecha_pactada = _parse_fecha_compromiso(valor_compromiso)
                        except ValueError:
                            fecha_pactada = ""

                # Si no se pudo obtener una fecha válida, mantener el literal anterior
                columnas[28] = fecha_pactada or "FECHA_PACTADA"  # col 29
                columnas[30] = "N"  # col 31
            elif tipo_evento == "PAYMENT_DIFFICULTY":
                # Estructura de dificultad de pago:
                # columnas 4,5,6,28,29,31 vacías
                columnas[10] = "PAYMENT DIFFICULTY"  # col 11
            elif tipo_evento == "PAID":
                # Estructura igual a PAYMENT DIFFICULTY pero col 11 = PAID
                columnas[10] = "PAID"  # col 11
            elif tipo_evento == "NO_ANSWER":
                # Estructura igual a PAID/PAYMENT_DIFFICULTY pero:
                # col 11 = NO ANSWER, col 12 vacía
                columnas[10] = "NO ANSWER"  # col 11
                columnas[11] = ""  # col 12 vacía
            elif tipo_evento == "CALLBACK":
                # Estructura igual a PAID (dificultad): columnas 4,5,6,28,29,31 vacías
                # pero con texto específico en col 11
                columnas[10] = "VOLVER A LLAMAR"  # col 11
            elif tipo_evento == "HANGUP":
                # Misma estructura que PAID (dificultad), pero texto HANGUP
                columnas[10] = "HANGUP"  # col 11

            filas_salida.append(columnas)

    with open(archivo_salida, "w", encoding="utf-8", newline="") as f_out:
        for cols in filas_salida:
            f_out.write("|".join(cols) + "\n")

    return archivo_salida


def main() -> None:
    """Punto de entrada CLI sencillo."""
    import sys

    archivo = None
    if len(sys.argv) > 1:
        archivo = sys.argv[1]

    try:
        salida = generar_tipificaciones(archivo)
        print(f"Archivo de tipificaciones generado: {salida}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error al generar tipificaciones: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
