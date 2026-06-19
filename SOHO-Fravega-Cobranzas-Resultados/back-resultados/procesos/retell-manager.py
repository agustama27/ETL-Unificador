"""
Retell CSV enricher (standalone template)

Qué hace:
- Lee un CSV export de Retell que tenga una columna "Call ID"
- Por cada Call ID consulta la API de Retell (get call)
- Extrae dynamic variables + postcall variables (según ubicaciones típicas)
- Genera un CSV enriquecido, expandiendo keys como columnas
- Deja una columna retell_error cuando falla una llamada

Config por env vars (opcional):
- RETELL_API_KEY (requerida)
- RETELL_BASE_URL (default: https://api.retellai.com)
- RETELL_CALL_PATH_TEMPLATE (opcional, acepta coma-separado; default: /v2/calls/{call_id})
- RETELL_AUTH_HEADER (default: Authorization)
- RETELL_AUTH_SCHEME (default: Bearer)  # usar "" si la API key va "raw"

También soporta .env local (sin dependencias) si no está RETELL_API_KEY.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =========================
# CONFIG MANUAL (solo esto)
# =========================
INPUT_DIR = Path("retell")     # carpeta donde está el export CSV
OUTPUT_DIR = Path("results")   # carpeta destino del CSV enriquecido
INPUT_GLOB = "export_*.csv"    # patrón para elegir el CSV (toma el más nuevo)
CALL_ID_COLUMN = "Call ID"     # nombre de columna
SLEEP_SECONDS = 0.0            # rate-limit opcional
INCLUDE_RAW_RESPONSE = False   # si True agrega columna retell_raw_response
DEBUG_EXTRACTION = os.getenv("RETELL_DEBUG", "false").lower() in ("true", "1", "yes")  # Habilitar con RETELL_DEBUG=1
DOTENV_PATHS = [Path(".env")]  # opcional: agregá más paths si querés

# =========================
# CONFIG ROMAN (opcional)
# =========================
ROMAN_DIR = Path("roman")      # carpeta donde está el export CSV de ROMAN
# Patron para archivos ROMAN: acepta export_roman_*.csv o historial_llamadas_*.csv
ROMAN_GLOB = os.getenv("ROMAN_GLOB_PATTERN", "*.csv")  # patrón para elegir el CSV (cualquier CSV en roman/)


DEFAULT_RETELL_BASE_URL = "https://api.retellai.com"
DEFAULT_CALL_PATH_TEMPLATE = "/v2/calls/{call_id}"
FALLBACK_CALL_PATH_TEMPLATES = [
    "/calls/{call_id}",
    "/v2/get-call/{call_id}",
    "/call/{call_id}",
]


class RetellAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def load_dotenv(dotenv_path: Path, *, override: bool = False) -> bool:
    if not dotenv_path.exists() or not dotenv_path.is_file():
        return False

    for raw_line in dotenv_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        # comment inline solo para valores no-quoted
        if value and value[0] not in {"'", '"'} and " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value

    return True


def ensure_api_key() -> str:
    api_key = os.getenv("RETELL_API_KEY", "").strip()
    if api_key:
        return api_key

    for p in DOTENV_PATHS:
        load_dotenv(p, override=False)

    api_key = os.getenv("RETELL_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("Missing RETELL_API_KEY env var (or .env)")
    return api_key


def parse_call_path_templates(raw_value: Optional[str]) -> List[str]:
    templates: List[str] = []
    if raw_value:
        for part in raw_value.split(","):
            part = part.strip()
            if part:
                templates.append(part)

    if not templates:
        templates.append(DEFAULT_CALL_PATH_TEMPLATE)

    for fb in FALLBACK_CALL_PATH_TEMPLATES:
        if fb not in templates:
            templates.append(fb)
    return templates


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _first_present(*values: Any) -> Any:
    for v in values:
        if v is None:
            continue
        if v == "":
            continue
        return v
    return None


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _is_primitive(val: Any) -> bool:
    return isinstance(val, (str, int, float, bool)) or val is None


def _collect_keys(dicts: Iterable[Dict[str, Any]]) -> List[str]:
    keys: List[str] = []
    seen: set[str] = set()
    for d in dicts:
        if not isinstance(d, dict):
            continue
        for k in d.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


@dataclass(frozen=True)
class RetellClient:
    api_key: str
    base_url: str = DEFAULT_RETELL_BASE_URL
    call_path_template: str = DEFAULT_CALL_PATH_TEMPLATE
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    timeout_seconds: float = 30.0

    def _build_url(self, call_id: str) -> str:
        base = self.base_url.rstrip("/")
        path = self.call_path_template.format(call_id=call_id)
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}"

    def _headers(self) -> Dict[str, str]:
        if self.auth_scheme:
            auth_value = f"{self.auth_scheme} {self.api_key}"
        else:
            auth_value = self.api_key
        return {self.auth_header: auth_value, "Accept": "application/json"}

    def get_call(self, call_id: str) -> Dict[str, Any]:
        url = self._build_url(call_id)
        req = urllib.request.Request(url=url, method="GET", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    raise RetellAPIError(
                        f"Invalid JSON from Retell for call_id={call_id}",
                        status_code=getattr(resp, "status", None),
                        body=raw,
                    ) from e
        except urllib.error.HTTPError as e:
            body = None
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = None
            raise RetellAPIError(
                f"Retell HTTP error for call_id={call_id}: {e.code}",
                status_code=e.code,
                body=body,
            ) from e
        except urllib.error.URLError as e:
            raise RetellAPIError(f"Retell connection error for call_id={call_id}: {e.reason}") from e


def get_call_with_candidates(client: RetellClient, call_id: str, path_templates: List[str]) -> Dict[str, Any]:
    last_error: Optional[RetellAPIError] = None
    for template in path_templates:
        temp_client = replace(client, call_path_template=template)
        try:
            return temp_client.get_call(call_id)
        except RetellAPIError as e:
            last_error = e
            # Si no es 404, cortamos (por ej 401/403)
            if e.status_code and e.status_code != 404:
                raise
            continue
    if last_error:
        raise last_error
    raise RetellAPIError("Unknown error fetching call")


def _find_recursive(obj: Any, target_key: str, max_depth: int = 10) -> Optional[Any]:
    """
    Busca recursivamente un key en el objeto JSON.
    Retorna el primer valor encontrado que sea un dict (para variables dinámicas).
    """
    if max_depth <= 0:
        return None
    
    if isinstance(obj, dict):
        # Si encontramos el key directamente y es un dict, lo retornamos
        if target_key in obj:
            value = obj[target_key]
            if isinstance(value, dict):
                return value
        
        # Buscar recursivamente en todos los valores
        for v in obj.values():
            result = _find_recursive(v, target_key, max_depth - 1)
            if result is not None:
                return result
    
    elif isinstance(obj, list):
        for item in obj:
            result = _find_recursive(item, target_key, max_depth - 1)
            if result is not None:
                return result
    
    return None


def _merge_dicts(*dicts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combina múltiples dicts en uno solo, dando prioridad a los primeros.
    """
    result: Dict[str, Any] = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


def _find_all_dicts_with_primitives(obj: Any, exclude_keys: Optional[set[str]] = None, max_depth: int = 8, current_path: str = "") -> List[Tuple[str, Dict[str, Any]]]:
    """
    Encuentra todos los dicts en el payload que contengan valores primitivos.
    Retorna una lista de tuplas (path, dict) para debugging.
    """
    if max_depth <= 0:
        return []
    
    exclude = exclude_keys or {
        "transcript", "transcripts", "call_transcript", "conversation", 
        "dialogue", "messages", "events", "logs", "recording_url",
        "audio", "timestamps", "created_at", "updated_at",
        "id", "call_id", "caller_id", "callee_id", "status", "direction",
        "start_time", "end_time", "duration", "cost", "phone_number",
    }
    
    result: List[Tuple[str, Dict[str, Any]]] = []
    
    if isinstance(obj, dict):
        # Verificar si este dict tiene valores primitivos y no está en exclude
        primitive_keys = [k for k, v in obj.items() if _is_primitive(v) and k not in exclude]
        if primitive_keys:
            # Crear un dict solo con las keys primitivas
            filtered_dict = {k: obj[k] for k in primitive_keys}
            if filtered_dict:
                result.append((current_path or "root", filtered_dict))
        
        # Buscar recursivamente
        for k, v in obj.items():
            if k not in exclude:
                new_path = f"{current_path}.{k}" if current_path else k
                result.extend(_find_all_dicts_with_primitives(v, exclude_keys, max_depth - 1, new_path))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            result.extend(_find_all_dicts_with_primitives(item, exclude_keys, max_depth - 1, f"{current_path}[{i}]"))
    
    return result


def extract_retell_variables(call_payload: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Extrae variables dinámicas y postcall del payload de Retell.
    
    Variables dinámicas: Busca específicamente en "retell_llm_dynamic_variables" 
    y también en ubicaciones típicas como "dynamic_variables".
    
    Variables postcall: Busca en ubicaciones típicas de postcall_variables.
    """
    # 1. PRIORIDAD: Buscar retell_llm_dynamic_variables (lo que el usuario necesita)
    dynamic_variables = _first_present(
        call_payload.get("retell_llm_dynamic_variables"),
        _dig(call_payload, "call", "retell_llm_dynamic_variables"),
        _dig(call_payload, "metadata", "retell_llm_dynamic_variables"),
        _dig(call_payload, "data", "retell_llm_dynamic_variables"),
    )
    
    # 2. Si no encontramos retell_llm_dynamic_variables, buscar recursivamente
    if not dynamic_variables or not isinstance(dynamic_variables, dict):
        dynamic_variables = _find_recursive(call_payload, "retell_llm_dynamic_variables")
    
    # 3. Si aún no encontramos, buscar en ubicaciones típicas de dynamic_variables (fallback)
    if not dynamic_variables or not isinstance(dynamic_variables, dict):
        dynamic_variables = _first_present(
            call_payload.get("dynamic_variables"),
            _dig(call_payload, "call", "dynamic_variables"),
            _dig(call_payload, "metadata", "dynamic_variables"),
            _dig(call_payload, "data", "dynamic_variables"),
        )
        # Buscar recursivamente si no encontramos
        if not dynamic_variables or not isinstance(dynamic_variables, dict):
            dynamic_variables = _find_recursive(call_payload, "dynamic_variables")
    
    # 4. Buscar postcall_variables en ubicaciones típicas (mantener funcionalidad existente)
    postcall_variables = _first_present(
        call_payload.get("postcall_variables"),
        call_payload.get("post_call_variables"),
        _dig(call_payload, "call_analysis", "custom_analysis_data"),
        _dig(call_payload, "post_call_analysis"),
        _dig(call_payload, "call", "post_call_analysis"),
        _dig(call_payload, "call", "postcall_variables"),
        _dig(call_payload, "analysis", "custom_analysis_data"),
        _dig(call_payload, "data", "postcall_variables"),
        _dig(call_payload, "data", "post_call_variables"),
    )
    
    # 5. Si no encontramos postcall en ubicaciones típicas, buscar recursivamente
    if not postcall_variables or not isinstance(postcall_variables, dict):
        postcall_variables = _find_recursive(call_payload, "postcall_variables")
        if not postcall_variables:
            postcall_variables = _find_recursive(call_payload, "post_call_variables")
        if not postcall_variables:
            postcall_variables = _find_recursive(call_payload, "custom_analysis_data")
    
    if DEBUG_EXTRACTION:
        print(f"[DEBUG] Variables dinámicas (retell_llm_dynamic_variables) extraídas: {list(dynamic_variables.keys()) if dynamic_variables else 'ninguna'}", file=sys.stderr)
        print(f"[DEBUG] Variables postcall extraídas: {list(postcall_variables.keys()) if postcall_variables else 'ninguna'}", file=sys.stderr)
    
    return dynamic_variables, postcall_variables


def find_latest_csv(folder: Path, *, glob_pattern: str) -> Path:
    candidates = list(folder.glob(glob_pattern))
    if not candidates:
        raise FileNotFoundError(f"No CSV found in {folder} matching {glob_pattern!r}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_call_ids_from_csv(csv_path: Path, *, call_id_column: str) -> List[str]:
    call_ids: List[str] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {csv_path}")

        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        if call_id_column not in normalized:
            raise KeyError(f"Column {call_id_column!r} not found. Available: {sorted(normalized.keys())}")
        real_col = normalized[call_id_column]

        for row in reader:
            raw = (row.get(real_col) or "").strip()
            if raw:
                call_ids.append(raw)

    # de-dup preservando orden
    seen: set[str] = set()
    out: List[str] = []
    for cid in call_ids:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


# =========================
# ROMAN MERGE FUNCTIONS
# =========================

# Columnas alternativas para identificar llamadas en ROMAN
ROMAN_CALL_ID_COLUMNS = ["Call ID", "ID de Llamada"]


def read_roman_csv(roman_csv: Path, *, call_id_column: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Lee el CSV de ROMAN y retorna un diccionario indexado por Call ID.
    
    Args:
        roman_csv: Path al CSV de ROMAN
        call_id_column: Nombre de la columna que contiene el Call ID (opcional, 
                        si no se especifica busca "Call ID" o "ID de Llamada")
        
    Returns:
        Diccionario {call_id: {column_name: value, ...}}
    """
    roman_data: Dict[str, Dict[str, Any]] = {}
    
    with roman_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        
        if not reader.fieldnames:
            raise ValueError(f"CSV de ROMAN sin encabezado: {roman_csv}")
        
        # Normalizar nombres de columnas
        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        
        # Buscar la columna de Call ID
        real_call_id_col = None
        
        if call_id_column:
            # Si se especifica una columna, usarla
            if call_id_column in normalized:
                real_call_id_col = normalized[call_id_column]
        else:
            # Buscar entre las alternativas conocidas
            for alt_col in ROMAN_CALL_ID_COLUMNS:
                if alt_col in normalized:
                    real_call_id_col = normalized[alt_col]
                    break
        
        if not real_call_id_col:
            expected_cols = [call_id_column] if call_id_column else ROMAN_CALL_ID_COLUMNS
            raise KeyError(
                f"Columna de Call ID no encontrada en ROMAN. "
                f"Buscando: {expected_cols}. Disponibles: {sorted(normalized.keys())}"
            )
        
        for row in reader:
            call_id = (row.get(real_call_id_col) or "").strip()
            if call_id:
                # Guardar toda la fila con columnas normalizadas
                roman_data[call_id] = {k.strip(): v for k, v in row.items() if k}
    
    return roman_data


# Columnas de [Salida] que deben IGNORARSE porque son duplicados de [Entrada]
# Estas columnas a veces tienen valores incorrectos (0, vacío) que no deben sobrescribir
ROMAN_IGNORE_OUTPUT_COLUMNS = {
    "[Salida] Dni Cliente",  # El DNI de salida a veces es 0, usar [Entrada] Dni Cliente
}


def _normalize_roman_column(col_name: str) -> Optional[str]:
    """
    Normaliza el nombre de columna de ROMAN para matchear con las columnas internas.
    
    Convierte columnas como "[Entrada] Dni Cliente" -> "dni_cliente"
    y "[Salida] Tipificacion" -> "Tipificacion"
    
    Returns:
        Nombre de columna normalizado, o None si la columna debe ignorarse
    """
    col = col_name.strip()
    
    # Ignorar columnas de salida que son duplicados con datos incorrectos
    if col in ROMAN_IGNORE_OUTPUT_COLUMNS:
        return None
    
    # Remover prefijos [Entrada] y [Salida]
    if col.startswith("[Entrada] "):
        col = col[10:]  # len("[Entrada] ") = 10
    elif col.startswith("[Salida] "):
        col = col[9:]   # len("[Salida] ") = 9
    
    # Convertir a snake_case minúsculas para variables dinámicas típicas
    # Pero mantener capitalización para ciertas columnas como "Tipificacion"
    # Lista de columnas que deben mantener su capitalización
    keep_case = {"Tipificacion", "Call ID"}
    
    if col not in keep_case:
        # Convertir espacios a underscore y a minúsculas
        col = col.replace(" ", "_").lower()
    
    return col


def merge_with_roman(
    results: Dict[str, Dict[str, Any]],
    roman_data: Dict[str, Dict[str, Any]],
    *,
    dyn_keys: List[str],
    post_keys: List[str],
) -> Tuple[Dict[str, Dict[str, Any]], int, List[Dict[str, Any]]]:
    """
    Hace merge de los datos enriquecidos con los datos de ROMAN.
    ROMAN tiene prioridad: si un Call ID existe en ROMAN, sus datos sobrescriben los de Retell.
    
    Args:
        results: Diccionario de resultados enriquecidos de Retell {call_id: {dyn, post, error, raw}}
        roman_data: Diccionario de datos de ROMAN {call_id: {column: value, ...}}
        dyn_keys: Lista de nombres de columnas de variables dinámicas
        post_keys: Lista de nombres de columnas de variables postcall
        
    Returns:
        Tupla (results_merged, count_updated, changes_log) donde:
        - results_merged: Diccionario con datos actualizados
        - count_updated: Cantidad de llamadas actualizadas desde ROMAN
        - changes_log: Lista con detalles de los cambios realizados
    """
    merged_results = results.copy()
    updated_count = 0
    changes_log: List[Dict[str, Any]] = []
    
    # Crear mapeo de columnas normalizadas de ROMAN
    # Esto permite que "[Entrada] Dni Cliente" matchee con "dni_cliente"
    all_target_keys = set(dyn_keys + post_keys)
    
    for call_id, roman_row in roman_data.items():
        if call_id not in merged_results:
            # La llamada no existe en Retell, ignorar
            continue
        
        # Obtener datos actuales de Retell
        current = merged_results[call_id]
        current_dyn = current.get("dyn") or {}
        current_post = current.get("post") or {}
        
        # Copiar datos actuales
        new_dyn = dict(current_dyn) if isinstance(current_dyn, dict) else {}
        new_post = dict(current_post) if isinstance(current_post, dict) else {}
        
        had_updates = False
        call_changes: List[Dict[str, str]] = []
        
        # Iterar sobre columnas de ROMAN y sobrescribir
        for roman_col, roman_value in roman_row.items():
            if roman_col == CALL_ID_COLUMN:
                continue  # No sobrescribir el Call ID
            
            normalized_col = _normalize_roman_column(roman_col)
            
            # Si la columna debe ignorarse, saltar
            if normalized_col is None:
                continue
            
            # Solo actualizar si el valor de ROMAN no está vacío
            roman_value_stripped = (roman_value or "").strip()
            if not roman_value_stripped or roman_value_stripped == "-":
                continue
            
            # Verificar si la columna normalizada está en las keys dinámicas o postcall
            if normalized_col in dyn_keys:
                old_value = new_dyn.get(normalized_col, "")
                if old_value != roman_value_stripped:
                    new_dyn[normalized_col] = roman_value_stripped
                    had_updates = True
                    call_changes.append({
                        "campo": normalized_col,
                        "anterior": old_value,
                        "nuevo": roman_value_stripped
                    })
            elif normalized_col in post_keys:
                old_value = new_post.get(normalized_col, "")
                if old_value != roman_value_stripped:
                    new_post[normalized_col] = roman_value_stripped
                    had_updates = True
                    call_changes.append({
                        "campo": normalized_col,
                        "anterior": old_value,
                        "nuevo": roman_value_stripped
                    })
            # También actualizar si la columna original está en las keys
            elif roman_col in dyn_keys:
                old_value = new_dyn.get(roman_col, "")
                if old_value != roman_value_stripped:
                    new_dyn[roman_col] = roman_value_stripped
                    had_updates = True
                    call_changes.append({
                        "campo": roman_col,
                        "anterior": old_value,
                        "nuevo": roman_value_stripped
                    })
            elif roman_col in post_keys:
                old_value = new_post.get(roman_col, "")
                if old_value != roman_value_stripped:
                    new_post[roman_col] = roman_value_stripped
                    had_updates = True
                    call_changes.append({
                        "campo": roman_col,
                        "anterior": old_value,
                        "nuevo": roman_value_stripped
                    })
        
        if had_updates:
            merged_results[call_id] = {
                **current,
                "dyn": new_dyn if new_dyn else current_dyn,
                "post": new_post if new_post else current_post,
                "roman_updated": True,
            }
            updated_count += 1
            changes_log.append({
                "call_id": call_id,
                "changes": call_changes
            })
    
    return merged_results, updated_count, changes_log


def try_load_roman_data(base_dir: Path) -> Optional[Tuple[Dict[str, Dict[str, Any]], Path]]:
    """
    Intenta cargar datos de ROMAN si existe un archivo en la carpeta roman/.
    
    Args:
        base_dir: Directorio base donde buscar la carpeta roman/
        
    Returns:
        Tupla (roman_data, roman_csv_path) si existe, None si no hay archivo
    """
    roman_dir = base_dir / ROMAN_DIR
    
    if not roman_dir.exists():
        return None
    
    try:
        roman_csv = find_latest_csv(roman_dir, glob_pattern=ROMAN_GLOB)
        print(f"[ROMAN] Encontrado export de ROMAN: {roman_csv.name}")
        roman_data = read_roman_csv(roman_csv)
        print(f"        Llamadas en ROMAN: {len(roman_data)}")
        return roman_data, roman_csv
    except FileNotFoundError:
        print(f"[INFO] No se encontro export de ROMAN en {roman_dir}, usando solo datos de Retell")
        return None


def enrich_csv(input_csv: Path, output_csv: Path, *, roman_dir: Optional[Path] = None) -> Path:
    api_key = ensure_api_key()

    client = RetellClient(
        api_key=api_key,
        base_url=os.getenv("RETELL_BASE_URL", DEFAULT_RETELL_BASE_URL).strip() or DEFAULT_RETELL_BASE_URL,
        auth_header=os.getenv("RETELL_AUTH_HEADER", "Authorization").strip() or "Authorization",
        auth_scheme=os.getenv("RETELL_AUTH_SCHEME", "Bearer"),
        call_path_template=DEFAULT_CALL_PATH_TEMPLATE,
    )
    path_templates = parse_call_path_templates(os.getenv("RETELL_CALL_PATH_TEMPLATE"))

    call_ids = read_call_ids_from_csv(input_csv, call_id_column=CALL_ID_COLUMN)

    results: Dict[str, Dict[str, Any]] = {}
    dyn_dicts: List[Dict[str, Any]] = []
    post_dicts: List[Dict[str, Any]] = []

    for call_id in call_ids:
        try:
            payload = get_call_with_candidates(client, call_id, path_templates)
            dyn, post = extract_retell_variables(payload)

            results[call_id] = {
                "dyn": dyn,
                "post": post,
                "error": None,
                "raw": payload if INCLUDE_RAW_RESPONSE else None,
            }
            if isinstance(dyn, dict):
                dyn_dicts.append(dyn)
            if isinstance(post, dict):
                post_dicts.append(post)

        except RetellAPIError as e:
            results[call_id] = {
                "dyn": None,
                "post": None,
                "error": {"message": str(e), "status_code": e.status_code, "body": e.body},
                "raw": None,
            }

        if SLEEP_SECONDS and SLEEP_SECONDS > 0:
            time.sleep(SLEEP_SECONDS)

    # Obtener keys de variables dinámicas y postcall
    dyn_keys = _collect_keys(dyn_dicts)
    post_keys = _collect_keys(post_dicts)

    # =========================
    # MERGE CON ROMAN (si existe)
    # =========================
    roman_updated_count = 0
    base_dir = input_csv.parent.parent  # Subir de retell/ a back-resultados/
    
    # Usar roman_dir si se proporciona, sino usar el default
    effective_roman_dir = roman_dir if roman_dir else base_dir / ROMAN_DIR
    
    roman_result = try_load_roman_data(base_dir) if roman_dir is None else None
    if roman_dir is not None and roman_dir.exists():
        try:
            roman_csv = find_latest_csv(roman_dir, glob_pattern=ROMAN_GLOB)
            print(f"[ROMAN] Encontrado export de ROMAN: {roman_csv.name}")
            roman_data = read_roman_csv(roman_csv)
            print(f"        Llamadas en ROMAN: {len(roman_data)}")
            roman_result = (roman_data, roman_csv)
        except FileNotFoundError:
            print(f"[INFO] No se encontro export de ROMAN en {roman_dir}, usando solo datos de Retell")
            roman_result = None
    
    if roman_result is None:
        roman_result = try_load_roman_data(base_dir)
    
    if roman_result:
        roman_data, roman_csv = roman_result
        results, roman_updated_count, changes_log = merge_with_roman(
            results, 
            roman_data, 
            dyn_keys=dyn_keys, 
            post_keys=post_keys
        )
        if roman_updated_count > 0:
            print(f"[ROMAN] Actualizadas {roman_updated_count} llamadas con datos de ROMAN")
            print()
            print("[DETALLE DE CAMBIOS]")
            print("-" * 80)
            for change_info in changes_log:
                call_id_short = change_info["call_id"][:35]
                print(f"\n  Llamada: {call_id_short}...")
                for change in change_info["changes"]:
                    campo = change["campo"]
                    # Convertir a string para evitar errores con números
                    anterior_str = str(change["anterior"]) if change["anterior"] else "(vacio)"
                    nuevo_str = str(change["nuevo"]) if change["nuevo"] else "(vacio)"
                    # Truncar valores muy largos
                    anterior = anterior_str[:60] + "..." if len(anterior_str) > 60 else anterior_str
                    nuevo = nuevo_str[:60] + "..." if len(nuevo_str) > 60 else nuevo_str
                    print(f"    [{campo}]")
                    print(f"      Retell: '{anterior}'")
                    print(f"      ROMAN:  '{nuevo}'")
            print("-" * 80)
            print()
        else:
            print(f"[INFO] No se encontraron actualizaciones en ROMAN para las llamadas procesadas")

    with input_csv.open("r", encoding="utf-8-sig", newline="") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {input_csv}")

        out_fieldnames = list(reader.fieldnames)

        extra_cols = ["retell_error"]
        if INCLUDE_RAW_RESPONSE:
            extra_cols.append("retell_raw_response")

        for key in dyn_keys + post_keys + extra_cols:
            if key not in out_fieldnames:
                out_fieldnames.append(key)

        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        real_col = normalized.get(CALL_ID_COLUMN)
        if not real_col:
            raise KeyError(f"Column {CALL_ID_COLUMN!r} not found. Available: {sorted(normalized.keys())}")

        with output_csv.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=out_fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in reader:
                call_id = (row.get(real_col) or "").strip()
                extra = results.get(call_id) if call_id else None

                if extra:
                    dyn = extra["dyn"]
                    post = extra["post"]

                    if isinstance(dyn, dict):
                        for k, v in dyn.items():
                            row[k] = v if _is_primitive(v) else _compact_json(v)
                    if isinstance(post, dict):
                        for k, v in post.items():
                            row[k] = v if _is_primitive(v) else _compact_json(v)

                    row["retell_error"] = _compact_json(extra["error"]) if extra["error"] is not None else ""
                    if INCLUDE_RAW_RESPONSE:
                        row["retell_raw_response"] = _compact_json(extra["raw"]) if extra["raw"] is not None else ""
                else:
                    row.setdefault("retell_error", "")
                    if INCLUDE_RAW_RESPONSE:
                        row.setdefault("retell_raw_response", "")

                writer.writerow(row)

    return output_csv


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_dir = (base_dir / INPUT_DIR).resolve()
    output_dir = (base_dir / OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_csv = find_latest_csv(input_dir, glob_pattern=INPUT_GLOB)
    output_csv = output_dir / f"{input_csv.stem}_enriched.csv"

    out = enrich_csv(input_csv, output_csv)
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()