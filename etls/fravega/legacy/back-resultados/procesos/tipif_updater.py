"""
Actualizador de tipificaciones desde el export de Retell

Lee el CSV de export de Retell y actualiza la columna "Tipificacion"
del archivo de resultados generado por tipif_generator.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


# Configuración
RETELL_DIR = Path("retell")  # carpeta donde está el export CSV
RESULTS_DIR = Path("results")  # carpeta donde está el CSV de resultados
RETELL_GLOB = "export_*.csv"  # patrón para elegir el CSV de Retell
RESULTS_GLOB = "fravega_gestiones_evoltis_*.csv"  # patrón para resultados

# Columnas del export de Retell
RETELL_DNI_COLUMN = "[Entrada] Dni Cliente"
RETELL_TIPIF_COLUMN = "[Salida] Tipificacion"

# Columnas del archivo de resultados
RESULT_DNI_COLUMN = "dni_cliente"
RESULT_TIPIF_COLUMN = "Tipificacion"


def find_latest_csv(directory: Path, glob_pattern: str) -> Path:
    """
    Busca el CSV más reciente en un directorio según el patrón dado.
    
    Args:
        directory: Directorio donde buscar
        glob_pattern: Patrón glob para filtrar archivos
        
    Returns:
        Path al archivo más reciente
        
    Raises:
        FileNotFoundError: Si no se encuentra ningún archivo
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directorio no existe: {directory}")
    
    csv_files = list(directory.glob(glob_pattern))
    if not csv_files:
        raise FileNotFoundError(f"No se encontraron archivos {glob_pattern} en {directory}")
    
    # Ordenar por fecha de modificación, más reciente primero
    csv_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return csv_files[0]


def read_retell_tipificaciones(csv_path: Path) -> Dict[str, str]:
    """
    Lee el CSV de export de Retell y extrae el mapeo DNI -> Tipificacion.
    
    Args:
        csv_path: Path al CSV de export de Retell
        
    Returns:
        Diccionario con DNI como clave y Tipificacion como valor
    """
    tipif_map: Dict[str, str] = {}
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {csv_path}")
        
        # Normalizar nombres de columnas
        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        
        dni_col = normalized.get(RETELL_DNI_COLUMN)
        tipif_col = normalized.get(RETELL_TIPIF_COLUMN)
        
        if not dni_col:
            raise KeyError(f"Columna {RETELL_DNI_COLUMN!r} no encontrada. Disponibles: {sorted(normalized.keys())}")
        if not tipif_col:
            raise KeyError(f"Columna {RETELL_TIPIF_COLUMN!r} no encontrada. Disponibles: {sorted(normalized.keys())}")
        
        for row in reader:
            dni = (row.get(dni_col) or "").strip()
            tipif = (row.get(tipif_col) or "").strip()
            
            # Solo agregar si DNI no está vacío y tipificación es válida (no vacía y no "-")
            if dni and tipif and tipif != "-":
                tipif_map[dni] = tipif
    
    return tipif_map


def update_results_csv(results_path: Path, tipif_map: Dict[str, str]) -> tuple[int, int]:
    """
    Actualiza la columna Tipificacion del CSV de resultados.
    
    Args:
        results_path: Path al CSV de resultados
        tipif_map: Diccionario DNI -> Tipificacion
        
    Returns:
        Tupla (filas_actualizadas, filas_totales)
    """
    # Leer todas las filas
    rows = []
    fieldnames = None
    
    with results_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            raise ValueError(f"CSV sin encabezado: {results_path}")
        
        for row in reader:
            rows.append(row)
    
    # Normalizar nombres de columnas
    normalized = {name.strip(): name for name in fieldnames if name is not None}
    dni_col = normalized.get(RESULT_DNI_COLUMN)
    tipif_col = normalized.get(RESULT_TIPIF_COLUMN)
    
    if not dni_col:
        raise KeyError(f"Columna {RESULT_DNI_COLUMN!r} no encontrada. Disponibles: {sorted(normalized.keys())}")
    if not tipif_col:
        raise KeyError(f"Columna {RESULT_TIPIF_COLUMN!r} no encontrada. Disponibles: {sorted(normalized.keys())}")
    
    # Actualizar tipificaciones
    updated_count = 0
    changes = []  # Lista para guardar los cambios realizados
    
    for row in rows:
        dni = (row.get(dni_col) or "").strip()
        if dni in tipif_map:
            new_tipif = tipif_map[dni]
            old_tipif = row.get(tipif_col, "")
            if old_tipif != new_tipif:
                # Guardar info del cambio
                customer_name = row.get("customer_name", "").strip()
                changes.append({
                    "dni": dni,
                    "nombre": customer_name,
                    "anterior": old_tipif if old_tipif else "(vacio)",
                    "nuevo": new_tipif,
                })
                row[tipif_col] = new_tipif
                updated_count += 1
    
    # Mostrar los cambios realizados
    if changes:
        print(f"\n    Detalle de cambios:")
        for cambio in changes:
            print(f"    [CAMBIO] DNI {cambio['dni']} ({cambio['nombre']}): '{cambio['anterior']}' -> '{cambio['nuevo']}'")
    
    # Escribir el archivo actualizado
    with results_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return updated_count, len(rows)


def update_tipificaciones(retell_csv: Optional[Path] = None, results_csv: Optional[Path] = None) -> Path:
    """
    Actualiza las tipificaciones del archivo de resultados con datos del export de Retell.
    
    Args:
        retell_csv: Path al CSV de Retell (opcional, busca el más reciente si no se especifica)
        results_csv: Path al CSV de resultados (opcional, busca el más reciente si no se especifica)
        
    Returns:
        Path al archivo de resultados actualizado
    """
    # Calcular rutas base desde donde está este script (procesos/)
    base_dir = Path(__file__).resolve().parent.parent  # back-resultados/
    retell_dir = base_dir / RETELL_DIR
    results_dir = base_dir / RESULTS_DIR
    
    # Buscar CSVs si no se especificaron
    if retell_csv is None:
        retell_csv = find_latest_csv(retell_dir, RETELL_GLOB)
    if results_csv is None:
        results_csv = find_latest_csv(results_dir, RESULTS_GLOB)
    
    print(f"[*] Leyendo export de Retell: {retell_csv.name}")
    tipif_map = read_retell_tipificaciones(retell_csv)
    print(f"    Encontradas {len(tipif_map)} tipificaciones validas")
    
    print(f"[*] Actualizando resultados: {results_csv.name}")
    updated, total = update_results_csv(results_csv, tipif_map)
    
    print(f"\n[OK] Actualizacion completada:")
    print(f"     Filas actualizadas: {updated}")
    print(f"     Filas totales: {total}")
    
    return results_csv


def main() -> None:
    """Función principal"""
    import sys
    
    try:
        result = update_tipificaciones()
        print(f"[OK] Archivo actualizado: {result}")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Durante la actualizacion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
