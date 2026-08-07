"""
Generador de CSV de tipificaciones para Fravega Evoltis

Lee el CSV de export de Retell, obtiene las llamadas de la API,
y genera un CSV con las variables dinámicas y postcall específicas.
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Importar funciones de retell-manager
# Como estamos en la misma carpeta, podemos importar directamente
import importlib.util

retell_manager_path = Path(__file__).parent / "retell-manager.py"
spec = importlib.util.spec_from_file_location("retell_manager", retell_manager_path)
retell_manager = importlib.util.module_from_spec(spec)
sys.modules["retell_manager"] = retell_manager
spec.loader.exec_module(retell_manager)

# Configuración
INPUT_DIR = Path("retell")  # carpeta donde está el export CSV
OUTPUT_DIR = Path("results")  # carpeta destino del CSV generado
INPUT_GLOB = "export_*.csv"  # patrón para elegir el CSV (toma el más nuevo)
CALL_ID_COLUMN = "Call ID"  # nombre de columna

# Variables dinámicas a incluir en el CSV
DYNAMIC_VARIABLES = [
    "dni_cliente",
    "credito",
    "monto_exacto",
    "customer_name",
    "user_number",
]

# Variables postcall a incluir en el CSV
POSTCALL_VARIABLES = [
    "fecha_compromiso",
    "Tipificacion",
]


def _is_primitive(val: Any) -> bool:
    """Verifica si un valor es primitivo (str, int, float, bool, None)"""
    return isinstance(val, (str, int, float, bool)) or val is None


def _get_primitive_value(value: Any) -> str:
    """Convierte un valor a string, manejando None y valores no primitivos"""
    if value is None:
        return ""
    if _is_primitive(value):
        return str(value)
    # Si no es primitivo, convertir a JSON compacto
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def generate_tipif_csv(input_csv: Path, output_csv: Path) -> Path:
    """
    Genera el CSV de tipificaciones con las variables específicas.
    
    Args:
        input_csv: Path al CSV de entrada con Call IDs
        output_csv: Path al CSV de salida a generar
        
    Returns:
        Path al CSV generado
    """
    # Obtener API key y crear cliente
    api_key = retell_manager.ensure_api_key()
    
    client = retell_manager.RetellClient(
        api_key=api_key,
        base_url=os.getenv("RETELL_BASE_URL", retell_manager.DEFAULT_RETELL_BASE_URL).strip() or retell_manager.DEFAULT_RETELL_BASE_URL,
        auth_header=os.getenv("RETELL_AUTH_HEADER", "Authorization").strip() or "Authorization",
        auth_scheme=os.getenv("RETELL_AUTH_SCHEME", "Bearer"),
        call_path_template=retell_manager.DEFAULT_CALL_PATH_TEMPLATE,
    )
    path_templates = retell_manager.parse_call_path_templates(os.getenv("RETELL_CALL_PATH_TEMPLATE"))
    
    # Leer call IDs del CSV de entrada
    call_ids = retell_manager.read_call_ids_from_csv(input_csv, call_id_column=CALL_ID_COLUMN)
    
    print(f"[PROCESANDO] {len(call_ids)} llamadas...")
    
    # Obtener datos de cada llamada
    results: Dict[str, Dict[str, Any]] = {}
    
    for idx, call_id in enumerate(call_ids, 1):
        print(f"  [{idx}/{len(call_ids)}] Procesando {call_id}...", end=" ", flush=True)
        
        try:
            # Obtener payload de Retell
            payload = retell_manager.get_call_with_candidates(client, call_id, path_templates)
            
            # Extraer variables dinámicas y postcall
            dyn, post = retell_manager.extract_retell_variables(payload)
            
            # Filtrar solo las variables que necesitamos
            # Inicializar todas las variables con valores vacíos
            filtered_data: Dict[str, Any] = {var: "" for var in DYNAMIC_VARIABLES + POSTCALL_VARIABLES}
            
            # Extraer variables dinámicas solicitadas
            if isinstance(dyn, dict):
                for var_name in DYNAMIC_VARIABLES:
                    if var_name in dyn:
                        filtered_data[var_name] = dyn[var_name]
            
            # Extraer variables postcall solicitadas
            if isinstance(post, dict):
                for var_name in POSTCALL_VARIABLES:
                    if var_name in post:
                        filtered_data[var_name] = post[var_name]
            
            results[call_id] = {
                "data": filtered_data,
                "error": None,
            }
            print("[OK]")
            
        except retell_manager.RetellAPIError as e:
            print(f"[ERROR] {e}")
            # Crear fila con valores vacíos y error
            filtered_data = {var: "" for var in DYNAMIC_VARIABLES + POSTCALL_VARIABLES}
            results[call_id] = {
                "data": filtered_data,
                "error": str(e),
            }
        
        # Rate limiting opcional
        sleep_seconds = float(os.getenv("RETELL_SLEEP_SECONDS", "0.0"))
        if sleep_seconds > 0:
            import time
            time.sleep(sleep_seconds)
    
    # =========================
    # MERGE CON ROMAN (si existe)
    # =========================
    base_dir = input_csv.parent.parent  # Subir de retell/ a back-resultados/
    roman_result = retell_manager.try_load_roman_data(base_dir)
    
    if roman_result:
        roman_data, roman_csv = roman_result
        
        # Convertir results al formato que espera merge_with_roman
        converted_results: Dict[str, Dict[str, Any]] = {}
        for call_id, result in results.items():
            if result["error"] is None:
                data = result["data"]
                # Separar en dynamic y postcall
                dyn = {k: data[k] for k in DYNAMIC_VARIABLES if k in data}
                post = {k: data[k] for k in POSTCALL_VARIABLES if k in data}
                converted_results[call_id] = {
                    "dyn": dyn,
                    "post": post,
                    "error": None,
                    "raw": None
                }
        
        # Aplicar merge
        merged_results, roman_updated_count, changes_log = retell_manager.merge_with_roman(
            converted_results,
            roman_data,
            dyn_keys=DYNAMIC_VARIABLES,
            post_keys=POSTCALL_VARIABLES
        )
        
        # Actualizar results con datos merged
        for call_id, merged in merged_results.items():
            if call_id in results:
                merged_data = {}
                merged_data.update(merged.get("dyn", {}))
                merged_data.update(merged.get("post", {}))
                results[call_id]["data"] = merged_data
        
        if roman_updated_count > 0:
            print(f"\n[ROMAN] Actualizadas {roman_updated_count} llamadas con datos de ROMAN")
            print()
            print("[DETALLE DE CAMBIOS]")
            print("-" * 80)
            for change_info in changes_log:
                call_id_short = change_info["call_id"][:35]
                print(f"\n  Llamada: {call_id_short}...")
                for change in change_info["changes"]:
                    campo = change["campo"]
                    anterior_str = str(change["anterior"]) if change["anterior"] else "(vacio)"
                    nuevo_str = str(change["nuevo"]) if change["nuevo"] else "(vacio)"
                    anterior = anterior_str[:60] + "..." if len(anterior_str) > 60 else anterior_str
                    nuevo = nuevo_str[:60] + "..." if len(nuevo_str) > 60 else nuevo_str
                    print(f"    [{campo}]")
                    print(f"      Retell: '{anterior}'")
                    print(f"      ROMAN:  '{nuevo}'")
            print("-" * 80)
            print()
    
    # Leer el CSV de entrada para mantener el orden y cualquier dato adicional
    input_rows: List[Dict[str, Any]] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {input_csv}")
        
        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        real_call_id_col = normalized.get(CALL_ID_COLUMN)
        if not real_call_id_col:
            raise KeyError(f"Column {CALL_ID_COLUMN!r} not found. Available: {sorted(normalized.keys())}")
        
        for row in reader:
            call_id = (row.get(real_call_id_col) or "").strip()
            input_rows.append({
                "call_id": call_id,
                "original_row": row,
            })
    
    # Generar CSV de salida
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    # Definir columnas del CSV de salida
    output_columns = DYNAMIC_VARIABLES + POSTCALL_VARIABLES
    
    with output_csv.open("w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=output_columns)
        writer.writeheader()
        
        rows_written = 0
        rows_filtered = 0
        
        for input_row_info in input_rows:
            call_id = input_row_info["call_id"]
            result = results.get(call_id)
            
            if result:
                # Crear fila con las variables filtradas
                output_row = {}
                for col in output_columns:
                    value = result["data"].get(col, "")
                    output_row[col] = _get_primitive_value(value)
                
                # Validar que Tipificacion no esté vacía y no sea "no_es_titular"
                tipificacion = output_row.get("Tipificacion", "").strip()
                
                if tipificacion:
                    writer.writerow(output_row)
                    rows_written += 1
                else:
                    rows_filtered += 1
            else:
                # Si no hay resultado, no escribir la fila (está filtrada)
                rows_filtered += 1
    
    print(f"\n[OK] CSV generado: {output_csv}")
    print(f"   Filas incluidas: {rows_written}")
    print(f"   Filas filtradas (Tipificacion vacía o 'no_es_titular'): {rows_filtered}")
    return output_csv


def main() -> None:
    """Función principal"""
    # Calcular rutas desde donde está este script (procesos/)
    base_dir = Path(__file__).resolve().parent.parent  # back-resultados/
    input_dir = base_dir / INPUT_DIR
    output_dir = base_dir / OUTPUT_DIR
    
    # Buscar el CSV más reciente
    try:
        input_csv = retell_manager.find_latest_csv(input_dir, glob_pattern=INPUT_GLOB)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generar nombre del CSV de salida con fecha actual
    fecha_actual = datetime.now().strftime("%Y%m%d")
    output_filename = f"fravega_gestiones_evoltis_{fecha_actual}.csv"
    output_csv = output_dir / output_filename
    
    # Crear directorio de salida si no existe
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar el CSV
    try:
        out = generate_tipif_csv(input_csv, output_csv)
        print(f"[OK] Proceso completado: {out}")
    except Exception as e:
        print(f"[ERROR] Durante la generacion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

