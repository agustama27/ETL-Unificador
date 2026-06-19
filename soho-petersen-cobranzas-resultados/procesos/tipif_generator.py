"""
Generates per-bank CSV files with the "gestiones" structure, using data from ROMAN.

Flow:
- Load ROMAN CSV rows via roman_merger.load_roman_rows
- Map columns to the required gestion schema
- Split rows by banco_gestionado into 4 CSVs under `debug/gestiones_totales_AAAAMMDD/`

Output columns (in order) match `Estructura del archivo de gestiones - Ejemplos v2(Hoja1).csv`:
Usuario asignado; GESTION_RELACIONADA; TIPO_PROMESA; NRO_CLIENTE; SUCURSAL; ACCION;
EFECTO; CONTACTO; MOTIVO_ATRASO; OBSERVACIONES_GESTION; NRO_PRODUCTO; SUC_PRODUCTO;
TIPO_PROD; FECHA_ALTA; FECHA_PROMESA; MONTO_PROMESA; CANAL_DE_PAGO; PUNTAJE_PROMESA;
OBSERVACIONES_PROMESA
"""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from procesos.paths import get_project_root
from procesos.roman_merger import find_latest_roman_export, load_roman_rows

# Banks to split by
BANKS = ["Santa Fe", "Entre Ríos", "Santa Cruz", "San Juan"]

# Column order required by destino
COLUMNS = [
    "Usuario asignado",
    "GESTION_RELACIONADA",
    "TIPO_PROMESA",
    "NRO_CLIENTE",
    "SUCURSAL",
    "ACCION",
    "EFECTO",
    "CONTACTO",
    "MOTIVO_ATRASO",
    "OBSERVACIONES_GESTION",
    "NRO_PRODUCTO",
    "SUC_PRODUCTO",
    "TIPO_PROD",
    "FECHA_ALTA",
    "FECHA_PROMESA",
    "MONTO_PROMESA",
    "CANAL_DE_PAGO",
    "PUNTAJE_PROMESA",
    "OBSERVACIONES_PROMESA",
    "fecha_llamada_original",  # Campo adicional para preservar la fecha original
]


def _to_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        cleaned = val.strip()
        return "" if cleaned.lower() == "null" else cleaned
    return str(val)


def _sanitize_text_field(text_str: str) -> str:
    """
    Sanitiza campos de texto para CSV:
    1. Remueve comillas (simples y dobles) del texto
    2. Reemplaza ";" por "," para evitar conflictos con el separador CSV
    
    Esta función debe aplicarse a TODOS los campos de texto antes de escribir el CSV.
    
    Args:
        text_str: String con el texto a sanitizar
        
    Returns:
        String sanitizado sin comillas y con ";" reemplazado por ","
    """
    if not text_str:
        return text_str
    
    # Remover comillas (simples y dobles)
    text_sanitizada = text_str.replace('"', '').replace("'", "")
    # Reemplazar punto y coma por coma
    text_sanitizada = text_sanitizada.replace(";", ",")
    
    return text_sanitizada


def _normalize_and_truncate_text(text: str, max_length: int = 100) -> str:
    """
    Normalize text by removing accents/tildes and special characters, then truncate to max_length.
    
    Steps:
    1. Remove accents/tildes using NFKD normalization
    2. Remove special characters (keep only alphanumeric, spaces, and basic punctuation)
    3. Truncate to max_length characters
    """
    if not text:
        return ""
    
    # Step 1: Remove accents/tildes using NFKD normalization
    normalized = unicodedata.normalize("NFKD", text)
    # Remove combining characters (accents)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    
    # Step 2: Remove special characters, keep alphanumeric, spaces, and basic punctuation
    # Allow: letters, numbers, spaces, commas, periods, colons, semicolons, hyphens, parentheses
    cleaned = re.sub(r'[^\w\s,.:;()\-]', '', without_accents)
    # Clean up multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Step 3: Truncate to max_length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    
    return cleaned


def _is_zero_number(val) -> bool:
    """
    Returns True if val represents numeric zero (0, 0.0, "0", "0,00", etc).
    """
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return float(val) == 0.0
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() == "null":
            return False
        # tolerate comma decimal separator
        s = s.replace(",", ".")
        try:
            return float(s) == 0.0
        except ValueError:
            return False
    return False


def _format_money_spanish(val) -> str:
    """
    Format money value in Spanish format: thousands separator = point, decimal separator = comma.
    Examples: 164906.64 -> "164.906,64", 100862.71 -> "100.862,71"
    If zero or empty, returns empty string.
    """
    if _is_zero_number(val):
        return ""
    
    # Convert to float if possible
    try:
        if isinstance(val, str):
            # Replace comma with point if it's a string number
            num_str = val.strip().replace(",", ".")
            num_val = float(num_str)
        else:
            num_val = float(val)
    except (ValueError, TypeError):
        # If can't convert, return as string
        return _to_str(val)
    
    # Format with 2 decimal places
    formatted = f"{num_val:,.2f}"
    # Replace comma (thousands) with point, and point (decimal) with comma
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def _money_or_empty(val) -> str:
    """
    MONTO_PROMESA rule: if equals zero, output empty (null in CSV).
    Otherwise, return formatted Spanish money format.
    """
    return _format_money_spanish(val)


def _is_promesa_de_pago(efecto: str) -> bool:
    """
    Check if EFECTO indicates a payment promise.
    """
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "PROMESA DE PAGO" or efecto_upper == "PROMESA_DE_PAGO"


def _get_contacto(efecto: str) -> str:
    """
    Determina el valor del campo CONTACTO basado en el EFECTO.
    
    Reglas:
    - Si EFECTO es "NOTIFICADO FLIAR" → "FAMILIAR"
    - Si EFECTO es "TELEFONO EQUIVOCADO" → "BLANK"
    - Para cualquier otro EFECTO → "CLIENTE"
    
    Args:
        efecto: Valor del campo EFECTO
        
    Returns:
        "FAMILIAR" si EFECTO es "NOTIFICADO FLIAR", "CLIENTE" en caso contrario
    """
    if not efecto:
        return "CLIENTE"
    
    efecto_upper = efecto.upper().strip()
    if efecto_upper == "NOTIFICADO FLIAR":
        return "FAMILIAR"
    elif efecto_upper == "TELEFONO EQUIVOCADO":
        return "BLANK"
    
    return "CLIENTE"


def _get_tipo_prod(producto: str) -> str:
    """
    Mapea la variable dinámica "producto" al código TIPO_PROD correspondiente.
    
    Reglas:
    - "Tarjeta de Crédito" → "27"
    - "Préstamos" → "4"
    - "Cuenta Corriente" → "1"
    - Si hay múltiples productos separados por coma, tomar solo el primero
    - Si no coincide con ninguno, retornar ""
    """
    if not producto:
        return ""
    
    # Normalizar: trim y tomar solo el primer producto si hay múltiples separados por coma
    producto_limpio = producto.strip()
    if "," in producto_limpio:
        producto_limpio = producto_limpio.split(",")[0].strip()
    
    # Normalizar para comparación: eliminar tildes y convertir a mayúsculas
    normalized = unicodedata.normalize("NFKD", producto_limpio)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    producto_normalizado = without_accents.upper().strip()
    
    # Mapeo de productos a códigos (usando texto normalizado sin tildes)
    if "TARJETA" in producto_normalizado and "CREDITO" in producto_normalizado:
        return "27"
    elif "PRESTAMO" in producto_normalizado:
        return "4"
    elif "CUENTA" in producto_normalizado and "CORRIENTE" in producto_normalizado:
        return "1"
    
    return ""


def _es_dia_habil(fecha: datetime) -> bool:
    """
    Verifica si una fecha es día hábil (lunes a viernes).
    
    Args:
        fecha: Fecha a verificar (datetime)
        
    Returns:
        True si es día hábil (lunes a viernes), False si es fin de semana
    """
    # weekday(): 0=lunes, 1=martes, ..., 4=viernes, 5=sábado, 6=domingo
    return fecha.weekday() < 5


def _ultimo_dia_habil_en_rango(fecha_inicio: datetime, dias_rango: int = 10) -> datetime:
    """
    Encuentra el último día hábil dentro de un rango de días desde una fecha de inicio.
    
    Args:
        fecha_inicio: Fecha de inicio del rango
        dias_rango: Número de días corridos a considerar (default: 10)
        
    Returns:
        Último día hábil encontrado dentro del rango, o fecha_inicio si no hay días hábiles
    """
    fecha_fin = fecha_inicio + timedelta(days=dias_rango - 1)
    
    # Buscar desde el final del rango hacia atrás
    fecha_actual = fecha_fin
    dias_buscados = 0
    
    while dias_buscados < dias_rango:
        if _es_dia_habil(fecha_actual):
            return fecha_actual
        fecha_actual -= timedelta(days=1)
        dias_buscados += 1
    
    # Si no se encontró ningún día hábil (caso extremo), retornar fecha_inicio
    return fecha_inicio


def _extract_date_from_filename(file_path: Path) -> str:
    """
    Extrae la fecha del nombre del archivo CSV.

    Patrones soportados:
    - historial_llamadas_YYYY-MM-DDTHH-MM-SS.csv → dd/mm/yyyy
    - export_XXXXX.csv → usar fecha de modificación del archivo

    Args:
        file_path: Path al archivo CSV

    Returns:
        Fecha en formato "dd/mm/yyyy"
    """
    filename = file_path.stem

    # Patrón: historial_llamadas_YYYY-MM-DDTHH-MM-SS
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match:
        year, month, day = match.groups()
        return f"{day}/{month}/{year}"

    # Patrón: export_XXXXX o cualquier otro
    # Usar fecha de modificación del archivo
    mtime = file_path.stat().st_mtime
    fecha_dt = datetime.fromtimestamp(mtime)
    return fecha_dt.strftime("%d/%m/%Y")


def _validate_fecha_promesa(fecha_promesa_str: str, fecha_actual: datetime) -> str:
    """
    Valida que FECHA_PROMESA sea un día hábil dentro del rango de 10 días corridos desde hoy.
    
    Reglas:
    - La fecha debe estar dentro del rango de 10 días corridos desde hoy
    - La fecha debe ser un día hábil (lunes a viernes)
    - Si la fecha está dentro del rango pero no es hábil, se ajusta al último día hábil disponible
    - Si la fecha es anterior a hoy, se ajusta al primer día hábil dentro del rango
    - Si está vacía o no se puede parsear, retorna vacío
    
    Args:
        fecha_promesa_str: Fecha en formato "dd/mm/yyyy"
        fecha_actual: Fecha actual (datetime)
        
    Returns:
        Fecha validada y ajustada en formato "dd/mm/yyyy" o "" si está vacía/no válida
    """
    if not fecha_promesa_str or not fecha_promesa_str.strip():
        return ""
    
    fecha_promesa_str = fecha_promesa_str.strip()
    
    # Intentar parsear la fecha en formato dd/mm/yyyy
    try:
        fecha_promesa = datetime.strptime(fecha_promesa_str, "%d/%m/%Y")
    except ValueError:
        # Si no se puede parsear, retornar vacío
        return ""
    
    # Normalizar fechas (solo fecha, sin hora)
    fecha_actual_sin_hora = fecha_actual.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_promesa_sin_hora = fecha_promesa.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calcular el rango válido: desde hoy hasta hoy + 9 días (10 días corridos total)
    fecha_limite_inferior = fecha_actual_sin_hora
    fecha_limite_superior = fecha_actual_sin_hora + timedelta(days=9)
    
    # Si la fecha promesa es anterior a hoy, ajustar al primer día hábil dentro del rango
    if fecha_promesa_sin_hora < fecha_limite_inferior:
        # Buscar el primer día hábil desde hoy
        fecha_candidata = fecha_limite_inferior
        dias_buscados = 0
        while dias_buscados < 10:
            if _es_dia_habil(fecha_candidata):
                return fecha_candidata.strftime("%d/%m/%Y")
            fecha_candidata += timedelta(days=1)
            dias_buscados += 1
        # Si no se encontró (caso extremo), usar el último día hábil del rango
        return _ultimo_dia_habil_en_rango(fecha_limite_inferior, 10).strftime("%d/%m/%Y")
    
    # Si la fecha está fuera del rango superior (más de 10 días), ajustar al último día hábil del rango
    if fecha_promesa_sin_hora > fecha_limite_superior:
        return _ultimo_dia_habil_en_rango(fecha_limite_inferior, 10).strftime("%d/%m/%Y")
    
    # Si la fecha está dentro del rango pero no es día hábil, ajustar al último día hábil disponible
    if not _es_dia_habil(fecha_promesa_sin_hora):
        # Buscar el último día hábil disponible en todo el rango
        # Primero intentar buscar hacia atrás desde la fecha promesa (más cercano)
        fecha_candidata = fecha_promesa_sin_hora
        dias_buscados = 0
        
        # Buscar hacia atrás desde la fecha promesa hasta encontrar un día hábil
        while dias_buscados < 10 and fecha_candidata >= fecha_limite_inferior:
            if _es_dia_habil(fecha_candidata):
                return fecha_candidata.strftime("%d/%m/%Y")
            fecha_candidata -= timedelta(days=1)
            dias_buscados += 1
        
        # Si no se encontró hacia atrás, usar el último día hábil disponible en todo el rango
        return _ultimo_dia_habil_en_rango(fecha_limite_inferior, 10).strftime("%d/%m/%Y")
    
    # Si está dentro del rango y es día hábil, retornar la fecha original
    return fecha_promesa_str


def _extract_fecha_from_datetime(fecha_hora_str: str) -> str:
    """
    Extrae la fecha de un string con formato "dd/mm/yyyy, HH:MM" o similar.

    Args:
        fecha_hora_str: String con fecha y hora (ej: "28/01/2026, 15:41")

    Returns:
        Solo la fecha en formato "dd/mm/yyyy", o el string original si no se puede extraer
    """
    if not fecha_hora_str:
        return ""

    # Intentar extraer la fecha antes de la coma
    if "," in fecha_hora_str:
        fecha_part = fecha_hora_str.split(",")[0].strip()
        return fecha_part

    # Si no tiene coma, verificar si ya es solo fecha (dd/mm/yyyy)
    if re.match(r'^\d{2}/\d{2}/\d{4}$', fecha_hora_str.strip()):
        return fecha_hora_str.strip()

    return fecha_hora_str


def _map_row(row: Dict[str, str], fecha_alta_default: str) -> Dict[str, str]:
    """
    Map a ROMAN row to the gestion schema.  Missing values -> "".

    Args:
        row: Fila normalizada de ROMAN (claves: EFECTO, nro_cliente, sucursal, etc.)
        fecha_alta_default: Fecha por defecto a usar para FECHA_ALTA si no hay fecha_llamada
                            (formato "dd/mm/yyyy")
    """
    efecto = _to_str(row.get("EFECTO"))

    # Determinar FECHA_ALTA: usar fecha_llamada de la fila si existe, sino usar default
    fecha_llamada_raw = _to_str(row.get("fecha_llamada"))
    if fecha_llamada_raw:
        fecha_alta = _extract_fecha_from_datetime(fecha_llamada_raw)
    else:
        fecha_alta = fecha_alta_default
    is_promesa = _is_promesa_de_pago(efecto)
    
    # Para PROMESA DE PAGO: si MONTO_PROMESA está vacío, usar deuda_vencida como fallback
    monto_promesa = _to_str(row.get("MONTO_PROMESA"))
    if is_promesa and not monto_promesa:
        monto_promesa = _to_str(row.get("deuda_vencida"))
    
    # Para PROMESA DE PAGO: si MOTIVO_ATRASO está vacío, usar texto predeterminado
    motivo_atraso = _to_str(row.get("MOTIVO_ATRASO"))
    if is_promesa:
        motivo_atraso = "Otros"
    
    # Mapear variable dinámica "producto" a TIPO_PROD
    producto = _to_str(row.get("producto"))
    tipo_prod = _get_tipo_prod(producto)
    
    # Validar FECHA_PROMESA: debe ser mayor a la fecha actual
    fecha_promesa_raw = _to_str(row.get("FECHA_PROMESA"))
    fecha_actual_dt = datetime.now()
    fecha_promesa_validada = ""
    if is_promesa:
        fecha_promesa_validada = _validate_fecha_promesa(fecha_promesa_raw, fecha_actual_dt)
    
    # Mapear campos base
    mapped = {
        "Usuario asignado": "scesano",
        "GESTION_RELACIONADA": "",
        "TIPO_PROMESA": "PRINCIPAL",
        "NRO_CLIENTE": _to_str(row.get("nro_cliente")),
        "SUCURSAL": _to_str(row.get("sucursal")),
        "ACCION": "LLAMADA SALIENTE",
        "EFECTO": efecto,
        "CONTACTO": _get_contacto(efecto),
        "MOTIVO_ATRASO": _normalize_and_truncate_text(motivo_atraso),
        "OBSERVACIONES_GESTION": _normalize_and_truncate_text(_to_str(row.get("OBSERVACIONES_GESTION"))),
        "NRO_PRODUCTO": _to_str(row.get("nro_producto")),
        "SUC_PRODUCTO": _to_str(row.get("sucursal")),
        "TIPO_PROD": tipo_prod,
        "FECHA_ALTA": fecha_alta,
        "FECHA_PROMESA": fecha_promesa_validada,
        "MONTO_PROMESA": _money_or_empty(monto_promesa),
        "CANAL_DE_PAGO": _to_str(row.get("CANAL_DE_PAGO")) if is_promesa else "",
        "PUNTAJE_PROMESA": "9" if is_promesa else "",
        "OBSERVACIONES_PROMESA": "Promesa de pago registrada" if is_promesa else "",
        "fecha_llamada_original": fecha_llamada_raw if fecha_llamada_raw else "",  # Preservar fecha original
    }
    
    # Sanitizar TODOS los campos de texto (remover comillas y reemplazar punto y coma)
    campos_texto = [
        "Usuario asignado",
        "GESTION_RELACIONADA",
        "TIPO_PROMESA",
        "ACCION",
        "EFECTO",
        "CONTACTO",
        "MOTIVO_ATRASO",
        "OBSERVACIONES_GESTION",
        "OBSERVACIONES_PROMESA",
    ]
    for campo in campos_texto:
        if campo in mapped:
            mapped[campo] = _sanitize_text_field(mapped[campo])
    
    return mapped


def generate_tipif_files(
    *,
    roman_dir: str | Path,
    results_dir: str | Path | None = None,
    fecha_alta_override: str | None = None,
    include_all_efectos: bool = False,
) -> Dict[str, Path]:
    """
    Produce 4 CSVs (one per bank) in ``debug/gestiones_totales_AAAAMMDD/``.

    Args:
        roman_dir: Directorio con exports de ROMAN (fuente única de datos)
        results_dir: Directorio de salida (opcional, default: debug/gestiones_totales_AAAAMMDD/)
        fecha_alta_override: Fecha a usar para FECHA_ALTA (opcional, formato "dd/mm/yyyy").
                             Si no se proporciona, se extrae automáticamente del nombre del
                             archivo CSV de ROMAN.
        include_all_efectos: Si True, incluye todos los efectos (incluso RELLAMAR)

    Returns:
        Dict {bank: path} con las rutas de los archivos generados
    """
    base_dir = get_project_root()
    if results_dir is None:
        debug_dir = base_dir / "debug"
        fecha_actual = datetime.now()
        nombre_carpeta = f"gestiones_totales_{fecha_actual.strftime('%Y%m%d')}"
        results_dir = debug_dir / nombre_carpeta
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    roman_path = find_latest_roman_export(roman_dir)
    if roman_path is None:
        raise FileNotFoundError(
            f"No se encontró ningún CSV en '{roman_dir}'"
        )

    print(f"[CSV] ROMAN: Cargando datos de '{roman_path.name}'")
    rows = load_roman_rows(roman_path)
    print(f"[DONE] ROMAN: {len(rows)} filas cargadas")

    if fecha_alta_override is None:
        fecha_alta = _extract_date_from_filename(roman_path)
        print(f"[FECHA ALTA] Extraida del archivo: {fecha_alta} (de {roman_path.name})")
    else:
        fecha_alta = fecha_alta_override
        print(f"[FECHA ALTA] Especificada: {fecha_alta}")

    per_bank: Dict[str, List[Dict[str, str]]] = {b: [] for b in BANKS}
    for row in rows:
        bank = _to_str(row.get("BANCO_GESTIONADO"))
        if bank not in per_bank:
            continue

        efecto = _to_str(row.get("EFECTO"))
        if not efecto:
            continue
        if not include_all_efectos and efecto.upper() == "RELLAMAR":
            continue

        nro_cliente = _to_str(row.get("nro_cliente"))
        if not nro_cliente:
            continue

        mapped = _map_row(row, fecha_alta)
        per_bank[bank].append(mapped)

    output_paths: Dict[str, Path] = {}
    for bank, items in per_bank.items():
        out_name = f"gestiones_{bank.replace(' ', '_').replace('í', 'i').replace('Í', 'I')}.csv"
        out_path = results_dir / out_name
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(items)
        output_paths[bank] = out_path

    return output_paths


if __name__ == "__main__":
    base_dir = get_project_root()
    roman_dir = base_dir / "roman"
    result_paths = generate_tipif_files(roman_dir=roman_dir)
    print("Archivos generados:")
    for bank, path in result_paths.items():
        print(f"- {bank}: {path}")

