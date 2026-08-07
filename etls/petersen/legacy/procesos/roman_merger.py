"""
Módulo para carga de datos de ROMAN.

ROMAN es la fuente única de datos de llamadas. Este módulo implementa la carga
y normalización de los exports CSV de ROMAN al formato interno que usa el
pipeline de tipificaciones.

Columnas ROMAN soportadas:
- "ID de Llamada": identificador único de la llamada
- Prefijos "[Entrada]": variables dinámicas de la llamada
- Prefijos "[Salida]": variables post-call / resultados
- "Fecha y Hora": timestamp de la llamada
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional


def _normalize_value(val: Any) -> str:
    """Normaliza un valor para comparación/uso."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("null", "none", "-"):
        return ""
    return s


def _normalize_nro_cliente(val: Any) -> str:
    """
    Normaliza un número de cliente evitando notación científica.

    ROMAN exporta ``[Salida] Nro Cliente`` como float y a veces aparece
    como ``3.00011879323e+11``. Esta función lo convierte al entero
    original como string, sin perder dígitos.
    """
    s = _normalize_value(val)
    if not s:
        return ""

    if "e" in s.lower() or "E" in s:
        try:
            from decimal import Decimal

            return format(Decimal(s), "f").rstrip("0").rstrip(".")
        except Exception:
            return s

    if s.endswith(".0"):
        return s[:-2]

    return s


def _normalize_call_id(val: Any) -> str:
    """
    Normaliza el identificador de llamada (Call ID) para comparación robusta
    entre Retell y ROMAN.

    Reglas:
    - Convierte a string y hace strip de espacios.
    - Elimina caracteres BOM y saltos de línea/carriage return.
    - Normaliza a minúsculas.
    - Si empieza con el prefijo "call_", compara solo por el sufijo.
    """
    if val is None:
        return ""

    s = str(val).strip()

    if not s:
        return ""

    # Remover BOM y caracteres invisibles comunes
    s = s.replace("\ufeff", "").replace("\r", "").replace("\n", "").strip()

    # Normalizar a minúsculas para evitar problemas de mayúsculas/minúsculas
    s = s.lower()

    # Si viene con prefijo "call_", usar solo el sufijo para comparar
    if s.startswith("call_"):
        s = s[len("call_") :]

    return s


def load_roman_data(roman_csv_path: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    Carga datos de ROMAN indexados por Call ID.

    Args:
        roman_csv_path: Ruta al archivo CSV exportado de ROMAN

    Returns:
        Dict con {call_id: {campos_mapeados}}
    """
    roman_csv_path = Path(roman_csv_path)
    roman_data: Dict[str, Dict[str, Any]] = {}

    with roman_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            call_id = _normalize_call_id(
                _ci_get(row, "ID de Llamada") or _ci_get(row, "Call ID")
            )
            if not call_id:
                continue
            roman_data[call_id] = _map_roman_row(row)

    return roman_data


def _normalize_key(key: str) -> str:
    """Normaliza un nombre de columna para comparación flexible."""
    return key.lower().replace("_", " ")


def _ci_get(row: Dict[str, Any], key: str) -> Any:
    """
    Dict get flexible para CSV row lookups.

    Ignora diferencias de mayúsculas/minúsculas y trata espacios y
    underscores como equivalentes, para soportar distintos formatos
    de export de ROMAN (ej: "BANCO GESTIONADO" vs "BANCO_GESTIONADO").
    """
    val = row.get(key)
    if val is not None:
        return val
    norm_key = _normalize_key(key)
    for k, v in row.items():
        if _normalize_key(k) == norm_key:
            return v
    return None


def _map_roman_row(row: Dict[str, Any]) -> Dict[str, str]:
    """Mapea una fila cruda del CSV de ROMAN al formato interno normalizado."""
    efecto_val = (
        _ci_get(row, "[Salida] EFECTO")
        or _ci_get(row, "[Salida] Efecto")
        or _ci_get(row, "[Salida] efecto")
    )

    return {
        "BANCO_GESTIONADO": _normalize_value(_ci_get(row, "[Salida] BANCO GESTIONADO")),
        "EFECTO": _normalize_value(efecto_val),
        "MONTO_PROMESA": _normalize_value(_ci_get(row, "[Salida] MONTO PROMESA")),
        "FECHA_PROMESA": _normalize_value(_ci_get(row, "[Salida] FECHA PROMESA")),
        "MOTIVO_ATRASO": _normalize_value(_ci_get(row, "[Salida] MOTIVO ATRASO")),
        "OBSERVACIONES_GESTION": _normalize_value(_ci_get(row, "[Salida] OBSERVACIONES GESTION")),
        "OBSERVACIONES_PROMESA": _normalize_value(_ci_get(row, "[Salida] OBSERVACIONES PROMESA")),
        "CANAL_DE_PAGO": _normalize_value(_ci_get(row, "[Salida] CANAL DE PAGO")),
        "COMPROMISO_DE_PAGO_LOGRADO": _normalize_value(_ci_get(row, "[Salida] COMPROMISO DE PAGO LOGRADO")),
        "CUSTOMER_EMAIL": _normalize_value(_ci_get(row, "[Salida] CUSTOMER EMAIL")),
        "SIN_DATOS": _normalize_value(_ci_get(row, "[Salida] SIN DATOS")),
        "nro_cliente": (
            _normalize_nro_cliente(_ci_get(row, "[Entrada] Nro Cliente"))
            or _normalize_nro_cliente(_ci_get(row, "[Salida] Nro Cliente"))
        ),
        "sucursal": _normalize_value(_ci_get(row, "[Entrada] Sucursal")),
        "nro_producto": _normalize_value(_ci_get(row, "[Entrada] Nro Producto")),
        "producto": _normalize_value(_ci_get(row, "[Entrada] Producto")),
        "deuda_vencida": _normalize_value(_ci_get(row, "[Entrada] Deuda Vencida")),
        "customer_name": _normalize_value(_ci_get(row, "[Entrada] Customer Name")),
        "dias_mora": _normalize_value(_ci_get(row, "[Entrada] Dias Mora")),
        "email_registrado": _normalize_value(_ci_get(row, "[Entrada] Email Registrado")),
        "fecha_llamada": _normalize_value(
            _ci_get(row, "Fecha y Hora") or _ci_get(row, "Fecha")
        ),
    }


def load_roman_rows(roman_csv_path: str | Path) -> List[Dict[str, str]]:
    """
    Carga todas las filas del CSV de ROMAN como lista de diccionarios normalizados.

    A diferencia de ``load_roman_data`` (que indexa por Call ID para merge),
    esta función devuelve una fila por registro, lista para alimentar
    directamente a ``_map_row`` en el pipeline de tipificaciones.

    Args:
        roman_csv_path: Ruta al archivo CSV exportado de ROMAN

    Returns:
        Lista de diccionarios con claves normalizadas (BANCO_GESTIONADO,
        EFECTO, nro_cliente, sucursal, etc.)
    """
    roman_csv_path = Path(roman_csv_path)
    rows: List[Dict[str, str]] = []

    with roman_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(_map_roman_row(row))

    return rows


def merge_with_roman(
    retell_rows: List[Dict[str, Any]], 
    roman_data: Dict[str, Dict[str, Any]],
    call_id_column: str = "Call ID",
    report_dir: str | Path | None = None,
) -> List[Dict[str, Any]]:
    """
    Merge filas de Retell con datos de ROMAN, priorizando ROMAN cuando existe.
    
    Estrategia:
    - Para cada fila de Retell, buscar si existe en ROMAN por Call ID
    - Si existe, sobrescribir campos con valores de ROMAN (solo si no están vacíos)
    - Si no existe, mantener datos de Retell
    - Agregar campo "_source" indicando origen de los datos
    
    Args:
        retell_rows: Lista de filas enriquecidas de Retell
        roman_data: Dict de datos de ROMAN indexado por Call ID
        call_id_column: Nombre de la columna que contiene el Call ID
        report_dir: Directorio donde guardar el reporte de actualizaciones (opcional)
        
    Returns:
        Lista de filas merged con campo adicional "_source" indicando origen
    """
    merged_rows: List[Dict[str, Any]] = []
    
    stats = {
        "total_retell": len(retell_rows),
        "found_in_roman": 0,
        "only_in_retell": 0,
        "fields_updated": 0,
    }
    
    # Registro detallado de cambios para el reporte
    changes_log: List[Dict[str, Any]] = []
    
    # Campos que se pueden sobrescribir desde ROMAN
    # Estos son los campos que típicamente se modifican manualmente
    fields_to_override = [
        "BANCO_GESTIONADO",
        "EFECTO",
        "MONTO_PROMESA",
        "FECHA_PROMESA",
        "MOTIVO_ATRASO",
        "OBSERVACIONES_GESTION",
        "OBSERVACIONES_PROMESA",
        "CANAL_DE_PAGO",
        "COMPROMISO_DE_PAGO_LOGRADO",
        "CUSTOMER_EMAIL",
        "SIN_DATOS",
        "nro_cliente",
        "sucursal",
        "nro_producto",
        "producto",
        "deuda_vencida",
        "fecha_llamada",  # Fecha y hora original de la llamada
    ]
    
    for retell_row in retell_rows:
        # Normalizar Call ID desde Retell con la misma lógica que en ROMAN
        call_id = _normalize_call_id(retell_row.get(call_id_column))
        
        if call_id and call_id in roman_data:
            # Existe en ROMAN - priorizar datos de ROMAN
            roman_row = roman_data[call_id]
            
            # Crear nueva fila combinada: base de Retell + override de ROMAN
            merged_row = dict(retell_row)  # Copiar Retell como base
            
            # Registro de cambios para esta llamada
            call_changes: List[Dict[str, str]] = []
            
            # Override con datos de ROMAN (solo campos no vacíos)
            for field in fields_to_override:
                roman_value = roman_row.get(field, "")
                if roman_value:  # Solo override si ROMAN tiene valor
                    old_value = str(merged_row.get(field, "") or "")
                    new_value = str(roman_value)
                    if new_value != old_value:
                        stats["fields_updated"] += 1
                        call_changes.append({
                            "campo": field,
                            "valor_retell": old_value,
                            "valor_roman": new_value,
                        })
                    merged_row[field] = roman_value
            
            # Si hubo cambios, agregar al log
            if call_changes:
                changes_log.append({
                    "call_id": call_id,
                    "nro_cliente": merged_row.get("nro_cliente", ""),
                    "banco": merged_row.get("BANCO_GESTIONADO", ""),
                    "cambios": call_changes,
                })
            
            merged_row["_source"] = "ROMAN"
            stats["found_in_roman"] += 1
            merged_rows.append(merged_row)
        else:
            # Solo existe en Retell
            merged_row = dict(retell_row)
            merged_row["_source"] = "RETELL_ONLY"
            stats["only_in_retell"] += 1
            merged_rows.append(merged_row)
    
    # Imprimir estadísticas
    print("\n" + "=" * 60)
    print("[INFO] ESTADÍSTICAS DE MERGE RETELL + ROMAN")
    print("=" * 60)
    print(f"   • Total llamadas en Retell:           {stats['total_retell']}")
    print(f"   • Encontradas en ROMAN (actualizadas): {stats['found_in_roman']} "
          f"({stats['found_in_roman']/stats['total_retell']*100:.1f}%)")
    print(f"   • Solo en Retell (sin actualizar):     {stats['only_in_retell']} "
          f"({stats['only_in_retell']/stats['total_retell']*100:.1f}%)")
    print(f"   • Campos actualizados desde ROMAN:     {stats['fields_updated']}")
    print(f"   • Llamadas con cambios:                {len(changes_log)}")
    print("=" * 60 + "\n")
    
    # Guardar reporte detallado de cambios
    if report_dir and changes_log:
        _save_changes_report(changes_log, report_dir, stats)
    
    return merged_rows


def _save_changes_report(
    changes_log: List[Dict[str, Any]], 
    report_dir: str | Path,
    stats: Dict[str, int],
) -> Path:
    """
    Guarda un reporte CSV detallado con todos los cambios realizados durante el merge.
    
    El reporte incluye:
    - Call ID de cada llamada actualizada
    - Número de cliente
    - Banco
    - Campo modificado
    - Valor original (Retell)
    - Valor actualizado (ROMAN)
    """
    from datetime import datetime
    
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"reporte_cambios_roman_{timestamp}.csv"
    
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        
        # Header
        writer.writerow([
            "Call ID",
            "Nro Cliente", 
            "Banco",
            "Campo Modificado",
            "Valor Retell (Original)",
            "Valor ROMAN (Actualizado)",
        ])
        
        # Datos
        for entry in changes_log:
            call_id = entry["call_id"]
            nro_cliente = entry["nro_cliente"]
            banco = entry["banco"]
            
            for cambio in entry["cambios"]:
                writer.writerow([
                    call_id,
                    nro_cliente,
                    banco,
                    cambio["campo"],
                    cambio["valor_retell"],
                    cambio["valor_roman"],
                ])
    
    # También guardar resumen por campo
    summary_path = report_dir / f"resumen_cambios_roman_{timestamp}.csv"
    
    # Contar cambios por campo
    field_counts: Dict[str, int] = {}
    for entry in changes_log:
        for cambio in entry["cambios"]:
            campo = cambio["campo"]
            field_counts[campo] = field_counts.get(campo, 0) + 1
    
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Campo", "Cantidad de Cambios", "Porcentaje del Total"])
        
        total_cambios = sum(field_counts.values())
        for campo, count in sorted(field_counts.items(), key=lambda x: -x[1]):
            pct = (count / total_cambios * 100) if total_cambios > 0 else 0
            writer.writerow([campo, count, f"{pct:.1f}%"])
        
        writer.writerow([])
        writer.writerow(["TOTALES", "", ""])
        writer.writerow(["Total llamadas en Retell", stats["total_retell"], ""])
        writer.writerow(["Llamadas encontradas en ROMAN", stats["found_in_roman"], ""])
        writer.writerow(["Llamadas solo en Retell", stats["only_in_retell"], ""])
        writer.writerow(["Total campos actualizados", stats["fields_updated"], ""])
        writer.writerow(["Llamadas con cambios", len(changes_log), ""])
    
    print(f"[WRITE] Reporte de cambios guardado en:")
    print(f"   • Detalle: {report_path.name}")
    print(f"   • Resumen: {summary_path.name}")
    
    return report_path


def find_latest_roman_export(roman_dir: str | Path, *, glob_patterns: List[str] | None = None) -> Optional[Path]:
    """
    Encuentra el export más reciente de ROMAN en el directorio.

    Args:
        roman_dir: Directorio donde buscar exports de ROMAN
        glob_patterns: (OBSOLETO) Lista de patrones glob para buscar archivos.
                       Si es None, se tomarán **todos** los archivos .csv del directorio
                       y se elegirá el más reciente por fecha de modificación.

    Returns:
        Path al archivo más reciente, o None si no se encuentra ninguno
    """
    roman_dir = Path(roman_dir)
    if not roman_dir.exists():
        return None

    # Si no se especifican patrones, tomar todos los CSV del directorio
    if glob_patterns is None:
        candidates: List[Path] = list(roman_dir.glob("*.csv"))
    else:
        candidates = []
        for pattern in glob_patterns:
            candidates.extend(roman_dir.glob(pattern))

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def get_roman_data_if_available(
    roman_dir: str | Path | None,
    *,
    verbose: bool = True,
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Intenta cargar datos de ROMAN si el directorio existe y tiene exports.
    
    Esta función es un wrapper conveniente que maneja los casos donde ROMAN
    puede no estar disponible (directorio no existe, sin archivos, etc.)
    
    Args:
        roman_dir: Directorio donde buscar exports de ROMAN (puede ser None)
        verbose: Si True, imprime mensajes de estado
        
    Returns:
        Dict con datos de ROMAN indexados por Call ID, o None si no está disponible
    """
    if roman_dir is None:
        if verbose:
            print("[WARN]  ROMAN: No se especificó directorio, usando solo datos de Retell")
        return None
    
    roman_dir = Path(roman_dir)
    if not roman_dir.exists():
        if verbose:
            print(f"[WARN]  ROMAN: Directorio '{roman_dir}' no existe, usando solo datos de Retell")
        return None
    
    roman_path = find_latest_roman_export(roman_dir)
    if roman_path is None:
        if verbose:
            print(f"[WARN]  ROMAN: No se encontró export en '{roman_dir}', usando solo datos de Retell")
        return None
    
    if verbose:
        print(f"[CSV] ROMAN: Cargando datos de '{roman_path.name}'")
    
    roman_data = load_roman_data(roman_path)
    
    if verbose:
        print(f"[DONE] ROMAN: {len(roman_data)} llamadas cargadas")
    
    return roman_data
