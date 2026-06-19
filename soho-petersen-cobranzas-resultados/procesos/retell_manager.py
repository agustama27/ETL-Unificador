"""
Utilities to enrich Retell CSV exports with per-call variables fetched from Retell API.

Expected workflow:
- A CSV export exists under `back-generacion-resultados/retell/` with a column named "Call ID".
- For each Call ID, we call Retell "get call" endpoint and extract:
  - dynamic variables
  - post-call variables / post-call analysis variables

Configuration (env vars):
- RETELL_API_KEY: required
- RETELL_BASE_URL: optional (default: https://api.retellai.com)
- RETELL_CALL_PATH_TEMPLATE: optional (default: /v2/calls/{call_id})
  - Example alternatives depending on your Retell setup:
    - /calls/{call_id}
    - /v2/get-call/{call_id}
- RETELL_AUTH_HEADER: optional (default: Authorization)
- RETELL_AUTH_SCHEME: optional (default: Bearer)  # set empty string if API key should be sent raw

This module also supports loading env vars from a `.env` file (no external deps):
- If RETELL_API_KEY is missing from the environment, we will attempt to load `.env`
  from (in order): `back-generacion-resultados/.env`, repo root `.env`.
"""

from __future__ import annotations

import csv
import json
import os
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_RETELL_BASE_URL = "https://api.retellai.com"
DEFAULT_CALL_ID_COLUMN = "Call ID"
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


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _first_present(*values: Any) -> Any:
    for v in values:
        if v is None:
            continue
        # treat empty dict/list as present (still meaningful), but empty string as absent
        if v == "":
            continue
        return v
    return None


def load_dotenv(dotenv_path: str | Path, *, override: bool = False) -> bool:
    """
    Minimal `.env` loader (no external deps).
    - Supports lines like: KEY=VALUE, export KEY=VALUE
    - Supports quoted values: KEY="value", KEY='value'
    - Ignores empty lines and comments (# ...)
    Returns True if the file existed and was loaded, False otherwise.
    """
    path = Path(dotenv_path)
    if not path.exists() or not path.is_file():
        return False

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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

        # remove inline comment for unquoted values: KEY=value # comment
        if value and value[0] not in {"'", '"'} and " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value

    return True


def load_default_dotenv_locations(*, override: bool = False) -> Optional[Path]:
    """
    Attempts to load `.env` from common locations.
    Returns the Path that was loaded, or None if not found.
    """
    # This file lives in: back-generacion-resultados/procesos/retell_manager.py
    base_dir = Path(__file__).resolve().parents[1]  # back-generacion-resultados
    repo_root = base_dir.parent

    candidates = [base_dir / ".env", repo_root / ".env"]
    for p in candidates:
        if load_dotenv(p, override=override):
            return p
    return None


def parse_call_path_templates(raw_value: Optional[str]) -> List[str]:
    """
    Accepts comma-separated templates; returns a list with fallbacks appended.
    """
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


# Cache para el contexto SSL (se crea una sola vez)
_ssl_context_cache: Optional[ssl.SSLContext] = None


def _get_ssl_context() -> ssl.SSLContext:
    """
    Crea y retorna un contexto SSL para las conexiones HTTPS.
    Intenta múltiples métodos para manejar certificados correctamente en diferentes sistemas.
    """
    global _ssl_context_cache
    
    if _ssl_context_cache is not None:
        return _ssl_context_cache
    
    # Método 1: Intentar usar certifi si está disponible
    try:
        import certifi
        _ssl_context_cache = ssl.create_default_context(cafile=certifi.where())
        return _ssl_context_cache
    except ImportError:
        pass
    except Exception:
        pass
    
    # Método 2: Usar el contexto por defecto del sistema
    try:
        _ssl_context_cache = ssl.create_default_context()
        return _ssl_context_cache
    except Exception:
        pass
    
    # Método 3: Crear un contexto más permisivo (para Windows principalmente)
    try:
        # Intentar usar PROTOCOL_TLS_CLIENT si está disponible (Python 3.10+)
        if hasattr(ssl, 'PROTOCOL_TLS_CLIENT'):
            _ssl_context_cache = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            # Para versiones anteriores de Python, usar PROTOCOL_TLS
            _ssl_context_cache = ssl.SSLContext(ssl.PROTOCOL_TLS)
        _ssl_context_cache.check_hostname = False
        _ssl_context_cache.verify_mode = ssl.CERT_NONE
        return _ssl_context_cache
    except Exception:
        pass
    
    # Método 4: Fallback final - contexto sin verificación
    _ssl_context_cache = ssl._create_unverified_context()
    return _ssl_context_cache


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
        return {
            self.auth_header: auth_value,
            "Accept": "application/json",
        }

    def get_call(self, call_id: str, max_retries: int = 3, retry_delay: float = 2.0) -> Dict[str, Any]:
        url = self._build_url(call_id)
        last_error: Optional[Exception] = None

        # Obtener el contexto SSL (se crea una sola vez y se cachea)
        ssl_context = _get_ssl_context()

        for attempt in range(max_retries):
            req = urllib.request.Request(url=url, method="GET", headers=self._headers())
            try:
                # Usar el contexto SSL al abrir la conexión
                with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=ssl_context) as resp:
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
            except (TimeoutError, OSError) as e:
                # Retry on timeout or network errors
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise RetellAPIError(
                    f"Retell timeout after {max_retries} retries for call_id={call_id}: {e}",
                    status_code=None,
                    body=None,
                ) from e

        # Should not reach here, but just in case
        if last_error:
            raise RetellAPIError(
                f"Retell failed after {max_retries} retries for call_id={call_id}",
                status_code=None,
                body=None,
            ) from last_error
        raise RetellAPIError(f"Unknown error fetching call_id={call_id}")


def get_call_with_candidates(client: RetellClient, call_id: str, path_templates: List[str]) -> Dict[str, Any]:
    """
    Tries multiple path templates until one succeeds.
    Stops early on non-404 errors (e.g., 401/403).
    """
    last_error: Optional[RetellAPIError] = None
    for template in path_templates:
        temp_client = replace(client, call_path_template=template)
        try:
            return temp_client.get_call(call_id)
        except RetellAPIError as e:
            last_error = e
            if e.status_code and e.status_code != 404:
                # for auth or server errors, don't continue cycling templates
                raise
            # otherwise try next template
            continue

    if last_error:
        raise last_error
    raise RetellAPIError("Unknown error fetching call")


def find_latest_retell_report(retell_dir: str | Path, *, glob_pattern: str = "export_*.csv") -> Path:
    retell_dir = Path(retell_dir)
    candidates = list(retell_dir.glob(glob_pattern))
    if not candidates:
        raise FileNotFoundError(f"No CSV report found in {retell_dir} matching {glob_pattern!r}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_call_ids_from_csv(report_path: str | Path, *, call_id_column: str = DEFAULT_CALL_ID_COLUMN) -> List[str]:
    report_path = Path(report_path)
    call_ids: List[str] = []
    with report_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {report_path}")

        # tolerate whitespace differences in column names
        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        if call_id_column not in normalized:
            raise KeyError(f"Column {call_id_column!r} not found. Available: {sorted(normalized.keys())}")
        real_col = normalized[call_id_column]

        for row in reader:
            raw = (row.get(real_col) or "").strip()
            if not raw:
                continue
            call_ids.append(raw)

    # de-dup preserving order
    seen: set[str] = set()
    deduped: List[str] = []
    for cid in call_ids:
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(cid)
    return deduped


def extract_retell_variables(call_payload: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Any]]:
    """
    Returns: (dynamic_variables, postcall_variables)
    Since Retell responses can differ by API version, we try a few common locations.
    """
    dynamic_variables = _first_present(
        # Observed in real payloads (Retell "LLM dynamic variables")
        call_payload.get("retell_llm_dynamic_variables"),
        call_payload.get("dynamic_variables"),
        call_payload.get("dynamicVariables"),
        _dig(call_payload, "call", "dynamic_variables"),
        _dig(call_payload, "call", "dynamicVariables"),
        _dig(call_payload, "metadata", "dynamic_variables"),
        _dig(call_payload, "metadata", "dynamicVariables"),
    )

    postcall_variables = _first_present(
        call_payload.get("postcall_variables"),
        call_payload.get("post_call_variables"),
        call_payload.get("postCallVariables"),
        _dig(call_payload, "call_analysis", "custom_analysis_data"),
        _dig(call_payload, "post_call_analysis"),
        _dig(call_payload, "call", "post_call_analysis"),
        _dig(call_payload, "analysis", "custom_analysis_data"),
    )

    return dynamic_variables, postcall_variables


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


def enrich_retell_report_with_api_data(
    *,
    retell_dir: str | Path,
    report_path: str | Path | None = None,
    output_path: str | Path | None = None,
    call_id_column: str = DEFAULT_CALL_ID_COLUMN,
    sleep_seconds: float = 0.0,
    include_raw_response: bool = False,
    max_workers: int | None = None,
) -> Path:
    """
    Reads a Retell CSV export, fetches per-call variables from Retell API, and writes an enriched CSV.
    
    Args:
        max_workers: Number of parallel threads (default: min(20, total_calls) or from RETELL_MAX_WORKERS env var)
    """
    retell_dir = Path(retell_dir)
    if report_path is None:
        report_path = find_latest_retell_report(retell_dir)
    report_path = Path(report_path)
    print(f"[CSV] Leyendo CSV: {report_path.name}")

    api_key = os.getenv("RETELL_API_KEY", "").strip()
    if not api_key:
        # If user didn't export env vars, try `.env` automatically
        load_default_dotenv_locations(override=False)
        api_key = os.getenv("RETELL_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("Missing RETELL_API_KEY env var")

    client = RetellClient(
        api_key=api_key,
        base_url=os.getenv("RETELL_BASE_URL", DEFAULT_RETELL_BASE_URL).strip() or DEFAULT_RETELL_BASE_URL,
        call_path_template=DEFAULT_CALL_PATH_TEMPLATE,  # actual templates handled below
        auth_header=os.getenv("RETELL_AUTH_HEADER", "Authorization").strip() or "Authorization",
        auth_scheme=os.getenv("RETELL_AUTH_SCHEME", "Bearer"),
    )

    path_templates = parse_call_path_templates(os.getenv("RETELL_CALL_PATH_TEMPLATE", DEFAULT_CALL_PATH_TEMPLATE))

    if output_path is None:
        output_path = report_path.with_name(report_path.stem + "_enriched.csv")
    output_path = Path(output_path)

    # Build a map of call_id -> extracted variables (cache for duplicates in CSV)
    call_ids = read_call_ids_from_csv(report_path, call_id_column=call_id_column)
    total_calls = len(call_ids)
    
    # Determine max_workers (default: min(20, total_calls) or from env)
    if max_workers is None:
        max_workers_env = os.getenv("RETELL_MAX_WORKERS", "").strip()
        if max_workers_env:
            try:
                max_workers = int(max_workers_env)
            except ValueError:
                max_workers = min(20, total_calls)
        else:
            max_workers = min(20, total_calls)
    
    print(f"[INFO] Total de llamadas a procesar: {total_calls}")
    print(f"[PARALLEL] Procesamiento paralelo con {max_workers} workers")
    print(f"[SEARCH] Iniciando enriquecimiento...\n")
    
    results: Dict[str, Dict[str, Any]] = {}
    dyn_dicts: List[Dict[str, Any]] = []
    post_dicts: List[Dict[str, Any]] = []
    
    # Thread-safe counters and lock for logging
    progress_lock = threading.Lock()
    completed_count = 0
    success_count = 0
    error_count = 0
    start_time = time.time()
    
    def process_call_id(call_id: str) -> Tuple[str, Dict[str, Any], Optional[Exception]]:
        """Process a single call_id and return (call_id, result_dict, error)."""
        nonlocal completed_count, success_count, error_count
        call_start = time.time()
        try:
            payload = get_call_with_candidates(client, call_id, path_templates)
            dyn, post = extract_retell_variables(payload)
            result = {
                "retell_dynamic_variables": dyn,
                "retell_postcall_variables": post,
                "retell_error": None,
                "retell_raw_response": payload if include_raw_response else None,
            }
            call_duration = time.time() - call_start
            
            # Thread-safe logging
            with progress_lock:
                completed_count += 1
                success_count += 1
                idx = completed_count
                
                elapsed = time.time() - start_time
                avg_time_per_call = elapsed / idx if idx > 0 else 0
                remaining_calls = total_calls - idx
                eta_seconds = avg_time_per_call * remaining_calls if avg_time_per_call > 0 else 0
                
                # Mostrar progreso cada 10 llamadas o en las primeras 5
                if idx <= 5 or idx % 10 == 0 or idx == total_calls:
                    pct = (idx / total_calls) * 100
                    print(f"[{idx}/{total_calls}] ({pct:.1f}%) [OK] call_id={call_id[:12]}... | "
                          f"Tiempo: {call_duration:.2f}s | "
                          f"ETA: {eta_seconds/60:.1f}min | "
                          f"Éxitos: {success_count} | Errores: {error_count}")
            
            return call_id, result, None
            
        except RetellAPIError as e:
            call_duration = time.time() - call_start
            result = {
                "retell_dynamic_variables": None,
                "retell_postcall_variables": None,
                "retell_error": {
                    "message": str(e),
                    "status_code": e.status_code,
                    "body": e.body,
                },
                "retell_raw_response": None,
            }
            
            # Thread-safe logging for errors
            with progress_lock:
                completed_count += 1
                error_count += 1
                idx = completed_count
                
                elapsed = time.time() - start_time
                avg_time_per_call = elapsed / idx if idx > 0 else 0
                remaining_calls = total_calls - idx
                eta_seconds = avg_time_per_call * remaining_calls if avg_time_per_call > 0 else 0
                
                status_info = f"HTTP {e.status_code}" if e.status_code else "Error"
                print(f"[{idx}/{total_calls}] [ERR] call_id={call_id[:12]}... | "
                      f"{status_info}: {str(e)[:60]}... | "
                      f"Tiempo: {call_duration:.2f}s | "
                      f"ETA: {eta_seconds/60:.1f}min | "
                      f"Éxitos: {success_count} | Errores: {error_count}")
            
            return call_id, result, e
    
    # Process calls in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_call_id = {executor.submit(process_call_id, call_id): call_id for call_id in call_ids}
        
        for future in as_completed(future_to_call_id):
            call_id, result, error = future.result()
            results[call_id] = result
            
            # Collect dicts for column detection (thread-safe append)
            dyn = result.get("retell_dynamic_variables")
            post = result.get("retell_postcall_variables")
            if isinstance(dyn, dict):
                dyn_dicts.append(dyn)
            if isinstance(post, dict):
                post_dicts.append(post)
            
            if sleep_seconds and sleep_seconds > 0:
                time.sleep(sleep_seconds)
    
    total_duration = time.time() - start_time
    print(f"\n[DONE] Procesamiento completado:")
    print(f"   - Total: {total_calls} llamadas")
    print(f"   - Éxitos: {success_count}")
    print(f"   - Errores: {error_count}")
    print(f"   - Tiempo total: {total_duration/60:.2f} minutos ({total_duration:.1f}s)")
    print(f"   - Promedio por llamada: {total_duration/total_calls:.2f}s")
    print(f"\n[WRITE] Escribiendo CSV enriquecido...")

    # Stream-read original CSV and write enriched CSV
    with report_path.open("r", encoding="utf-8-sig", newline="") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {report_path}")

        out_fieldnames = list(reader.fieldnames)
        # Add dynamic/postcall keys as columns so values are not embedded as JSON
        dyn_keys = _collect_keys(dyn_dicts)
        post_keys = _collect_keys(post_dicts)

        extra_cols = ["retell_error"]  # keep error column for visibility
        if include_raw_response:
            extra_cols.append("retell_raw_response")
        for key in dyn_keys + post_keys + extra_cols:
            if key not in out_fieldnames:
                out_fieldnames.append(key)

        # Optionally keep legacy columns if present in header
        legacy_cols = ["retell_dynamic_variables", "retell_postcall_variables"]
        for col in legacy_cols:
            if col in out_fieldnames:
                # keep ordering but avoid duplicates
                continue
        if include_raw_response:
            pass

        normalized = {name.strip(): name for name in reader.fieldnames if name is not None}
        if call_id_column not in normalized:
            raise KeyError(f"Column {call_id_column!r} not found. Available: {sorted(normalized.keys())}")
        real_col = normalized[call_id_column]

        with output_path.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=out_fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in reader:
                call_id = (row.get(real_col) or "").strip()
                extra = results.get(call_id) if call_id else None

                if extra:
                    # expand dynamic variables into columns
                    dyn_vars = extra["retell_dynamic_variables"]
                    if isinstance(dyn_vars, dict):
                        for k, v in dyn_vars.items():
                            row[k] = v if _is_primitive(v) else _compact_json(v)
                    # expand postcall variables into columns
                    post_vars = extra["retell_postcall_variables"]
                    if isinstance(post_vars, dict):
                        for k, v in post_vars.items():
                            row[k] = v if _is_primitive(v) else _compact_json(v)

                    # legacy columns: leave empty (to avoid braces) unless primitive
                    if "retell_dynamic_variables" in row:
                        row["retell_dynamic_variables"] = (
                            dyn_vars if _is_primitive(dyn_vars) else ""
                        )
                    if "retell_postcall_variables" in row:
                        row["retell_postcall_variables"] = (
                            post_vars if _is_primitive(post_vars) else ""
                        )

                    row["retell_error"] = _compact_json(extra["retell_error"]) if extra["retell_error"] is not None else ""
                    if include_raw_response:
                        row["retell_raw_response"] = (
                            _compact_json(extra["retell_raw_response"]) if extra["retell_raw_response"] is not None else ""
                        )
                else:
                    row.setdefault("retell_dynamic_variables", "")
                    row.setdefault("retell_postcall_variables", "")
                    row.setdefault("retell_error", "")
                    if include_raw_response:
                        row.setdefault("retell_raw_response", "")

                writer.writerow(row)

    print(f"[DONE] CSV enriquecido guardado en: {output_path}")
    return output_path


def get_enriched_rows(
    *,
    retell_dir: str | Path,
    report_path: str | Path | None = None,
    call_id_column: str = DEFAULT_CALL_ID_COLUMN,
    sleep_seconds: float = 0.0,
    max_workers: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper: fetches/expands Retell data in memory and returns the rows (list of dicts).
    Uses the same logic as enrich_retell_report_with_api_data but only uses a temporary CSV.
    """
    # Reuse the main function to ensure identical retrieval/flattening, then read the CSV back.
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        enrich_retell_report_with_api_data(
            retell_dir=retell_dir,
            report_path=report_path,
            output_path=temp_path,
            call_id_column=call_id_column,
            sleep_seconds=sleep_seconds,
            include_raw_response=False,
            max_workers=max_workers,
        )
        rows: List[Dict[str, Any]] = []
        with temp_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def get_enriched_rows_with_roman_merge(
    *,
    retell_dir: str | Path,
    roman_dir: str | Path | None = None,
    report_path: str | Path | None = None,
    changes_report_dir: str | Path | None = None,
    call_id_column: str = DEFAULT_CALL_ID_COLUMN,
    sleep_seconds: float = 0.0,
    max_workers: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Obtiene filas enriquecidas de Retell y las mergea con datos de ROMAN.
    
    Esta función combina dos fuentes de datos:
    - Retell (API + CSV): fuente completa de llamadas
    - ROMAN (CSV export): fuente con datos actualizados/corregidos
    
    Estrategia de merge:
    - Si una llamada existe en ambos → priorizar datos de ROMAN
    - Si una llamada solo existe en Retell → usar datos de Retell
    
    Args:
        retell_dir: Directorio con exports de Retell
        roman_dir: Directorio con exports de ROMAN (opcional, si es None no se hace merge)
        report_path: Ruta específica al reporte de Retell (opcional)
        changes_report_dir: Directorio donde guardar el reporte de cambios (opcional)
        call_id_column: Nombre de la columna con el Call ID
        sleep_seconds: Segundos de espera entre llamadas a la API (rate limiting)
        max_workers: Número máximo de threads para procesamiento paralelo
        
    Returns:
        Lista de diccionarios con los datos merged, cada uno con campo "_source"
        indicando si los datos vienen de "ROMAN" o "RETELL_ONLY"
    """
    # Obtener datos de Retell (enriquecidos con API)
    retell_rows = get_enriched_rows(
        retell_dir=retell_dir,
        report_path=report_path,
        call_id_column=call_id_column,
        sleep_seconds=sleep_seconds,
        max_workers=max_workers,
    )
    
    # Si no hay directorio de ROMAN, retornar sin merge
    if roman_dir is None:
        print("[WARN]  ROMAN: No se especificó directorio, usando solo datos de Retell")
        for row in retell_rows:
            row["_source"] = "RETELL_ONLY"
        return retell_rows
    
    # Importar módulo de merge (importación tardía para evitar dependencias circulares)
    from procesos.roman_merger import get_roman_data_if_available, merge_with_roman
    
    # Cargar datos de ROMAN si están disponibles
    roman_data = get_roman_data_if_available(roman_dir, verbose=True)
    
    if roman_data is None:
        # ROMAN no disponible, retornar solo Retell
        for row in retell_rows:
            row["_source"] = "RETELL_ONLY"
        return retell_rows
    
    # Hacer merge priorizando ROMAN (con reporte de cambios si se especificó directorio)
    merged_rows = merge_with_roman(
        retell_rows=retell_rows,
        roman_data=roman_data,
        call_id_column=call_id_column,
        report_dir=changes_report_dir,
    )
    
    return merged_rows