"""Servicio reusable para comparar cobertura telefonica entre dos CSV.

Input: CSV source (BANCOR_E1KIA) y CSV target (BANCOR_ROMAN).
Output: resultado estructurado con estado, resumen y faltantes detectados.
"""

from pathlib import Path
import argparse
import re
from threading import Event
import unicodedata
from collections.abc import Callable
from typing import Any, TypedDict

import pandas as pd


ENCODINGS = ["latin-1", "iso-8859-1", "cp1252", "utf-8", "utf-16"]
CSV_DELIMITERS = (";", ",")
EMPTY_MARKERS = {"", "nan", "none", "nat", "null"}
PHONE_KEYWORDS = ("telefono", "celular", "phone", "tel", "movil", "mobile", "whatsapp")
PHONE_EXACT_ALIASES = {
    "numerotelefono",
    "numerocelular",
    "numerotrabajo",
    "telefono",
    "celular",
    "phone",
}
CSV_OUTPUT_COLUMNS = (
    "numero_referencia",
    "equivalencias_normalizadas",
    "apariciones_source",
    "ejemplo_valor_original",
    "columna_origen_ejemplo",
    "fila_origen_ejemplo",
)

ProgressCallback = Callable[[int, str], None]


class PhoneCompareCancelledError(Exception):
    """Senial interna para cancelacion cooperativa del comparador."""


class MissingPhoneRow(TypedDict):
    numero_referencia: str
    equivalencias_normalizadas: str
    apariciones_source: int
    ejemplo_valor_original: str
    columna_origen_ejemplo: str
    fila_origen_ejemplo: int


class PhoneCompareSummary(TypedDict):
    source_apariciones: int
    target_apariciones: int
    source_unicos: int
    target_unicos: int
    faltantes_apariciones: int
    faltantes_unicos: int


class PhoneCompareResult(TypedDict):
    ok: bool
    status: str
    message: str
    no_anomaly: bool
    summary: PhoneCompareSummary
    source_columns: list[str]
    target_columns: list[str]
    source_columns_mode: str
    target_columns_mode: str
    missing_examples: list[MissingPhoneRow]
    missing_rows: list[MissingPhoneRow]
    output_report_path: str
    warnings: list[str]
    logs: list[str]
    error: str


def _puntuar_candidato_csv(df_data: pd.DataFrame) -> int:
    """Asigna puntaje a un DataFrame para elegir parsing CSV mas plausible."""
    score = len(df_data.columns)
    inferred_columns = inferir_columnas_telefono(df_data)
    if inferred_columns:
        score += 100 + len(inferred_columns)
    if len(df_data.columns) == 1:
        only_column = str(df_data.columns[0])
        if ";" in only_column or "," in only_column:
            score -= 50
    return score


def _normalizar_nombres_columnas(df_data: pd.DataFrame) -> pd.DataFrame:
    """Normaliza encabezados para remover BOM/espacios sin romper columnas."""
    rename_map: dict[Any, str] = {}
    taken_names = set(str(column) for column in df_data.columns)

    for column in df_data.columns:
        cleaned = str(column).replace("\ufeff", "").replace("ï»¿", "").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned or cleaned == column:
            continue
        if cleaned in taken_names or cleaned in rename_map.values():
            continue
        rename_map[column] = cleaned
        taken_names.add(cleaned)

    if not rename_map:
        return df_data
    return df_data.rename(columns=rename_map)


def leer_csv_con_codificacion(path_csv: Path, separador: str = ";") -> tuple[pd.DataFrame, str]:
    """Lee CSV con cadena de codificaciones y fallback errors='replace'.

    Args:
        path_csv: Ruta del archivo CSV a leer.
        separador: Separador CSV esperado.

    Returns:
        Tupla (DataFrame, codificacion_utilizada).
    """
    delimiters_ordered = [separador] + [delimiter for delimiter in CSV_DELIMITERS if delimiter != separador]
    best_candidate: tuple[int, pd.DataFrame, str, str] | None = None

    for encoding in ENCODINGS:
        for delimiter in delimiters_ordered:
            try:
                df_data = pd.read_csv(path_csv, sep=delimiter, encoding=encoding, low_memory=False, dtype=str)
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

            df_data = _normalizar_nombres_columnas(df_data)
            score = _puntuar_candidato_csv(df_data)
            if best_candidate is None or score > best_candidate[0]:
                best_candidate = (score, df_data, encoding, delimiter)

    if best_candidate is not None:
        _, df_data, encoding, delimiter = best_candidate
        return df_data, f"{encoding};sep={delimiter}"

    with open(path_csv, "r", encoding="latin-1", errors="replace") as source_file:
        for delimiter in delimiters_ordered:
            source_file.seek(0)
            try:
                df_data = pd.read_csv(source_file, sep=delimiter, low_memory=False, dtype=str)
            except Exception:
                continue
            df_data = _normalizar_nombres_columnas(df_data)
            return df_data, f"latin-1(errors=replace);sep={delimiter}"

    raise ValueError(f"No se pudo leer el CSV: {path_csv}")


def normalizar_texto(value: Any) -> str:
    """Normaliza texto para comparar nombres de columnas.

    Args:
        value: Valor a normalizar.

    Returns:
        Texto sin acentos, en minuscula y alfanumerico.
    """
    text = str(value).replace("\ufeff", "").replace("ï»¿", "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return "".join(char for char in text if char.isalnum())


def es_columna_telefono(nombre_columna: str) -> bool:
    """Determina si una columna puede contener telefonos.

    Args:
        nombre_columna: Nombre de columna.

    Returns:
        True si parece columna telefonica.
    """
    normalizada = normalizar_texto(nombre_columna)
    if normalizada in PHONE_EXACT_ALIASES:
        return True
    if normalizada.startswith("tel"):
        return True
    return any(keyword in normalizada for keyword in PHONE_KEYWORDS)


def inferir_columnas_telefono(df_data: pd.DataFrame) -> list[str]:
    """Infere columnas de telefonos por nombre.

    Args:
        df_data: DataFrame a analizar.

    Returns:
        Lista de columnas candidatas.
    """
    return [column for column in df_data.columns if es_columna_telefono(column)]


def parsear_columnas_explicitas(columnas_raw: str) -> list[str]:
    """Parsea columnas explicitas separadas por coma.

    Args:
        columnas_raw: Texto con columnas separadas por coma.

    Returns:
        Lista de columnas limpias.
    """
    if not columnas_raw:
        return []
    return [column.strip() for column in str(columnas_raw).split(",") if column.strip()]


def resolver_columnas(df_data: pd.DataFrame, columnas_raw: str, dataset_label: str) -> tuple[list[str], str]:
    """Resuelve columnas de telefono explicitas o inferidas.

    Args:
        df_data: DataFrame donde resolver.
        columnas_raw: Columnas explicitas opcionales.
        dataset_label: Etiqueta para mensajes de error.

    Returns:
        Tupla (columnas_resueltas, modo).
    """
    explicit_columns = parsear_columnas_explicitas(columnas_raw)
    if explicit_columns:
        normalized_map = {normalizar_texto(column): column for column in df_data.columns}
        resolved_columns: list[str] = []
        missing_columns: list[str] = []

        for column in explicit_columns:
            if column in df_data.columns:
                resolved_columns.append(column)
                continue

            normalized = normalizar_texto(column)
            mapped_column = normalized_map.get(normalized)
            if mapped_column is None:
                missing_columns.append(column)
                continue
            resolved_columns.append(mapped_column)

        if missing_columns:
            raise ValueError(
                f"Columnas no encontradas en {dataset_label}: {missing_columns}. "
                f"Columnas disponibles: {list(df_data.columns)}"
            )

        unique_ordered = list(dict.fromkeys(resolved_columns))
        return unique_ordered, "explicitas"

    inferred_columns = inferir_columnas_telefono(df_data)
    if not inferred_columns:
        raise ValueError(
            f"No se detectaron columnas de telefono en {dataset_label}. "
            "Defina columnas manuales para continuar."
        )
    return inferred_columns, "inferidas"


def limpiar_numero(valor: Any) -> str:
    """Limpia un telefono a solo digitos con correcciones basicas.

    Args:
        valor: Valor crudo del telefono.

    Returns:
        Numero en formato solo digitos o vacio.
    """
    if pd.isna(valor):
        return ""

    text = str(valor).strip()
    if text.lower() in EMPTY_MARKERS:
        return ""

    text = re.sub(r"\.0$", "", text)
    digits = re.sub(r"\D", "", text)
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def expandir_equivalencias(numero: str) -> set[str]:
    """Genera equivalencias de telefono para matching 549/54/local.

    Args:
        numero: Numero solo digitos.

    Returns:
        Set con numero y equivalencias aplicables.
    """
    if not numero:
        return set()

    equivalencias = {numero}
    if numero.startswith("549") and len(numero) > 3:
        local = numero[3:]
        equivalencias.add(local)
        equivalencias.add(f"54{local}")
    elif numero.startswith("54") and len(numero) > 2:
        local = numero[2:]
        equivalencias.add(local)
        if local:
            equivalencias.add(f"549{local}")
    else:
        equivalencias.add(f"54{numero}")
        equivalencias.add(f"549{numero}")

    return {value for value in equivalencias if value}


def extraer_telefonos(df_data: pd.DataFrame, columnas: list[str]) -> list[dict[str, Any]]:
    """Extrae telefonos normalizados con metadata de origen.

    Args:
        df_data: Dataset fuente.
        columnas: Columnas de telefono a procesar.

    Returns:
        Lista de registros de telefono con equivalencias.
    """
    phones: list[dict[str, Any]] = []
    for column in columnas:
        for row_index, value in enumerate(df_data[column].tolist(), start=2):
            digits = limpiar_numero(value)
            if not digits:
                continue
            equivalences = expandir_equivalencias(digits)
            phones.append(
                {
                    "row_index": row_index,
                    "column": column,
                    "raw_value": str(value),
                    "digits": digits,
                    "equivalencias": equivalences,
                }
            )
    return phones


def _extraer_telefonos_cancelable(
    df_data: pd.DataFrame,
    columnas: list[str],
    cancel_event: Event | None,
) -> list[dict[str, Any]]:
    phones: list[dict[str, Any]] = []
    for column in columnas:
        for row_index, value in enumerate(df_data[column].tolist(), start=2):
            if row_index % 400 == 0 and cancel_event is not None and cancel_event.is_set():
                raise PhoneCompareCancelledError("Cancelado por usuario")

            digits = limpiar_numero(value)
            if not digits:
                continue
            equivalences = expandir_equivalencias(digits)
            phones.append(
                {
                    "row_index": row_index,
                    "column": column,
                    "raw_value": str(value),
                    "digits": digits,
                    "equivalencias": equivalences,
                }
            )
    return phones


def firma_equivalencias(equivalencias: set[str]) -> str:
    """Construye firma estable para agrupar equivalencias.

    Args:
        equivalencias: Set de equivalencias normalizadas.

    Returns:
        Firma con valores ordenados y unidos por '|'.
    """
    return "|".join(sorted(equivalencias))


def numero_referencia(equivalencias: set[str]) -> str:
    """Selecciona numero representativo de un conjunto de equivalencias.

    Args:
        equivalencias: Equivalencias del numero.

    Returns:
        Numero de referencia.
    """
    return min(equivalencias, key=lambda value: (len(value), value))


def detectar_faltantes(source_phones: list[dict[str, Any]], target_set: set[str]) -> list[dict[str, Any]]:
    """Detecta telefonos source sin match en target.

    Args:
        source_phones: Telefonos extraidos de source.
        target_set: Universo de equivalencias en target.

    Returns:
        Lista de registros faltantes.
    """
    missing = []
    for phone in source_phones:
        if phone["equivalencias"].isdisjoint(target_set):
            missing.append(phone)
    return missing


def _detectar_faltantes_cancelable(
    source_phones: list[dict[str, Any]],
    target_set: set[str],
    cancel_event: Event | None,
) -> list[dict[str, Any]]:
    missing = []
    for index, phone in enumerate(source_phones):
        if index % 400 == 0 and cancel_event is not None and cancel_event.is_set():
            raise PhoneCompareCancelledError("Cancelado por usuario")
        if phone["equivalencias"].isdisjoint(target_set):
            missing.append(phone)
    return missing


def agrupar_faltantes(faltantes: list[dict[str, Any]]) -> list[MissingPhoneRow]:
    """Agrupa faltantes por equivalencias y arma filas para UI/reporte.

    Args:
        faltantes: Lista de faltantes por aparicion.

    Returns:
        Lista agregada de faltantes.
    """
    grouped: dict[str, MissingPhoneRow] = {}
    for item in faltantes:
        firma = firma_equivalencias(item["equivalencias"])
        if firma not in grouped:
            grouped[firma] = {
                "numero_referencia": numero_referencia(item["equivalencias"]),
                "equivalencias_normalizadas": firma,
                "apariciones_source": 0,
                "ejemplo_valor_original": item["raw_value"],
                "columna_origen_ejemplo": item["column"],
                "fila_origen_ejemplo": int(item["row_index"]),
            }
        grouped[firma]["apariciones_source"] += 1

    rows = list(grouped.values())
    rows.sort(key=lambda item: (-item["apariciones_source"], item["numero_referencia"]))
    return rows


def _resultado_error(logs: list[str], mensaje: str) -> PhoneCompareResult:
    summary: PhoneCompareSummary = {
        "source_apariciones": 0,
        "target_apariciones": 0,
        "source_unicos": 0,
        "target_unicos": 0,
        "faltantes_apariciones": 0,
        "faltantes_unicos": 0,
    }
    return {
        "ok": False,
        "status": "ERROR",
        "message": mensaje,
        "no_anomaly": False,
        "summary": summary,
        "source_columns": [],
        "target_columns": [],
        "source_columns_mode": "",
        "target_columns_mode": "",
        "missing_examples": [],
        "missing_rows": [],
        "output_report_path": "",
        "warnings": [],
        "logs": logs,
        "error": mensaje,
    }


def _emitir_progreso(
    progress_callback: ProgressCallback | None,
    porcentaje: int,
    mensaje: str,
) -> int:
    porcentaje_sanitizado = max(0, min(100, int(porcentaje)))
    if progress_callback is not None:
        progress_callback(porcentaje_sanitizado, mensaje)
    return porcentaje_sanitizado


def _cancelar_si_corresponde(
    cancel_event: Event | None,
    logs: list[str],
    progress_callback: ProgressCallback | None,
    porcentaje: int,
) -> None:
    if cancel_event is not None and cancel_event.is_set():
        mensaje = "Cancelado por usuario"
        logs.append(mensaje)
        _emitir_progreso(progress_callback, porcentaje, mensaje)
        raise PhoneCompareCancelledError(mensaje)


def comparar_telefonos_archivos(
    source_path: Path,
    target_path: Path,
    source_columns_raw: str = "",
    target_columns_raw: str = "",
    generar_reporte_csv: bool = False,
    output_report_path: Path | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_event: Event | None = None,
) -> PhoneCompareResult:
    """Compara telefonos de source contra target y detecta faltantes.

    Args:
        source_path: Ruta del archivo source (BANCOR_E1KIA).
        target_path: Ruta del archivo target (BANCOR_ROMAN).
        source_columns_raw: Columnas explicitas source separadas por coma.
        target_columns_raw: Columnas explicitas target separadas por coma.
        generar_reporte_csv: Si True, exporta faltantes a CSV.
        output_report_path: Ruta opcional para reporte CSV.

    Returns:
        Resultado estructurado para consumo de UI.
    """
    logs: list[str] = []
    warnings: list[str] = []
    progreso_actual = _emitir_progreso(progress_callback, 0, "Preparando verificacion")

    try:
        _cancelar_si_corresponde(cancel_event, logs, progress_callback, progreso_actual)

        if not source_path.exists():
            raise FileNotFoundError(f"No existe source: {source_path}")
        if not target_path.exists():
            raise FileNotFoundError(f"No existe target: {target_path}")

        progreso_actual = _emitir_progreso(progress_callback, 10, "Leyendo source")
        df_source, source_encoding = leer_csv_con_codificacion(source_path, separador=";")
        progreso_actual = _emitir_progreso(progress_callback, 25, "Leyendo target")
        df_target, target_encoding = leer_csv_con_codificacion(target_path, separador=";")
        logs.append(f"Source leido con: {source_encoding}")
        logs.append(f"Target leido con: {target_encoding}")
        _cancelar_si_corresponde(cancel_event, logs, progress_callback, progreso_actual)

        progreso_actual = _emitir_progreso(progress_callback, 40, "Resolviendo columnas de telefono")
        source_columns, source_mode = resolver_columnas(df_source, source_columns_raw, "source")
        target_columns, target_mode = resolver_columnas(df_target, target_columns_raw, "target")
        logs.append(f"Columnas source ({source_mode}): {source_columns}")
        logs.append(f"Columnas target ({target_mode}): {target_columns}")
        _cancelar_si_corresponde(cancel_event, logs, progress_callback, progreso_actual)

        progreso_actual = _emitir_progreso(progress_callback, 55, "Extrayendo telefonos de source")
        source_phones = _extraer_telefonos_cancelable(df_source, source_columns, cancel_event)
        progreso_actual = _emitir_progreso(progress_callback, 70, "Extrayendo telefonos de target")
        target_phones = _extraer_telefonos_cancelable(df_target, target_columns, cancel_event)

        target_set: set[str] = set()
        for index, item in enumerate(target_phones):
            if index % 400 == 0 and cancel_event is not None and cancel_event.is_set():
                raise PhoneCompareCancelledError("Cancelado por usuario")
            target_set.update(item["equivalencias"])

        faltantes = _detectar_faltantes_cancelable(source_phones, target_set, cancel_event)
        faltantes_agrupados = agrupar_faltantes(faltantes)
        progreso_actual = _emitir_progreso(progress_callback, 85, "Comparando y agrupando faltantes")
        _cancelar_si_corresponde(cancel_event, logs, progress_callback, progreso_actual)

        source_unique = {firma_equivalencias(item["equivalencias"]) for item in source_phones}
        target_unique = {firma_equivalencias(item["equivalencias"]) for item in target_phones}

        summary: PhoneCompareSummary = {
            "source_apariciones": len(source_phones),
            "target_apariciones": len(target_phones),
            "source_unicos": len(source_unique),
            "target_unicos": len(target_unique),
            "faltantes_apariciones": len(faltantes),
            "faltantes_unicos": len(faltantes_agrupados),
        }

        no_anomaly = len(faltantes_agrupados) == 0
        status = "SIN_ANOMALIAS" if no_anomaly else "CON_ANOMALIAS"
        message = (
            "No se detectaron faltantes en BANCOR_ROMAN."
            if no_anomaly
            else "Se detectaron faltantes en BANCOR_ROMAN."
        )

        report_path = ""
        if generar_reporte_csv:
            progreso_actual = _emitir_progreso(progress_callback, 95, "Generando reporte de faltantes")
            _cancelar_si_corresponde(cancel_event, logs, progress_callback, progreso_actual)
            report_file = output_report_path
            if report_file is None:
                report_file = source_path.parent / "faltantes_phone_compare.csv"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            df_report = pd.DataFrame.from_records(faltantes_agrupados)
            if df_report.empty:
                df_report = pd.DataFrame(columns=pd.Index(CSV_OUTPUT_COLUMNS))
            else:
                df_report = df_report.reindex(columns=CSV_OUTPUT_COLUMNS)
            df_report.to_csv(report_file, sep=";", encoding="utf-8", index=False)
            report_path = str(report_file)
            logs.append(f"Reporte CSV generado: {report_path}")

        if not source_phones:
            warnings.append("No se encontraron telefonos validos en source con las columnas seleccionadas.")
        if not target_phones:
            warnings.append("No se encontraron telefonos validos en target con las columnas seleccionadas.")

        _emitir_progreso(progress_callback, 100, "Verificacion completada")

        return {
            "ok": True,
            "status": status,
            "message": message,
            "no_anomaly": no_anomaly,
            "summary": summary,
            "source_columns": source_columns,
            "target_columns": target_columns,
            "source_columns_mode": source_mode,
            "target_columns_mode": target_mode,
            "missing_examples": faltantes_agrupados[:10],
            "missing_rows": faltantes_agrupados,
            "output_report_path": report_path,
            "warnings": warnings,
            "logs": logs,
            "error": "",
        }
    except PhoneCompareCancelledError as exc:
        summary: PhoneCompareSummary = {
            "source_apariciones": 0,
            "target_apariciones": 0,
            "source_unicos": 0,
            "target_unicos": 0,
            "faltantes_apariciones": 0,
            "faltantes_unicos": 0,
        }
        return {
            "ok": False,
            "status": "CANCELLED",
            "message": str(exc),
            "no_anomaly": False,
            "summary": summary,
            "source_columns": [],
            "target_columns": [],
            "source_columns_mode": "",
            "target_columns_mode": "",
            "missing_examples": [],
            "missing_rows": [],
            "output_report_path": "",
            "warnings": [],
            "logs": logs,
            "error": str(exc),
        }

    except Exception as exc:
        logs.append(f"ERROR: {exc}")
        _emitir_progreso(progress_callback, progreso_actual, f"Error: {exc}")
        return _resultado_error(logs=logs, mensaje=str(exc))


def _construir_parser() -> argparse.ArgumentParser:
    """Crea parser para smoke run local del servicio.

    Returns:
        Instancia de parser configurada.
    """
    parser = argparse.ArgumentParser(description="Smoke test del comparador telefonico para UI.")
    parser.add_argument("--source", required=True, help="CSV source (BANCOR_E1KIA)")
    parser.add_argument("--target", required=True, help="CSV target (BANCOR_ROMAN)")
    parser.add_argument("--source-columns", default="", help="Columnas source separadas por coma")
    parser.add_argument("--target-columns", default="", help="Columnas target separadas por coma")
    parser.add_argument("--output", default="", help="Ruta opcional de reporte CSV de faltantes")
    return parser


if __name__ == "__main__":
    args = _construir_parser().parse_args()
    output_path = Path(args.output) if args.output.strip() else None
    resultado = comparar_telefonos_archivos(
        source_path=Path(args.source),
        target_path=Path(args.target),
        source_columns_raw=args.source_columns,
        target_columns_raw=args.target_columns,
        generar_reporte_csv=output_path is not None,
        output_report_path=output_path,
    )
    print(f"status={resultado['status']}")
    print(f"message={resultado['message']}")
    print(f"summary={resultado['summary']}")
    if resultado["missing_examples"]:
        print(f"missing_examples={resultado['missing_examples'][:3]}")
