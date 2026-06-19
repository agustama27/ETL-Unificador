# AGENTS.md — back-resultados

> **Module**: Retell.ai call results processing (MODULE 2)
> **Read this before**: Modifying any file inside `back-resultados/`.

---

## Module Purpose

Queries the Retell.ai API for each `call_id`, extracts dynamic variables and postcall analysis data, optionally merges with ROMAN human-management data, and produces a standardised 28-column CSV for internal review and reporting.

**Output file**: `results/gestiones_bancor_DDMMAAAA.csv`

---

## Directory Layout

```
back-resultados/
├── AGENTS.md                          ← You are here
├── main.py                            ← Entry point: orchestrates full pipeline
├── requirements.txt                   ← pandas, requests, python-dotenv, tqdm
├── README.md                          ← User-facing documentation
├── .env                               ← RETELL_API_KEY (gitignored)
├── calls/                             ← INPUT: CSV with call_ids (gitignored data)
│   └── export_*.csv                   ← Exported from Retell.ai dashboard
├── results/                           ← OUTPUT: 28-column gestiones CSVs
│   └── gestiones_bancor_DDMMAAAA.csv
└── procesos/
    ├── retell_manager.py              ← Parallel Retell.ai API queries (~470 lines)
    ├── tipif_generator.py             ← 28-column CSV builder (~264 lines)
    ├── roman_manager.py               ← ROMAN CSV reader and normalizer (~309 lines)
    ├── data_merger.py                 ← Retell + ROMAN intelligent merge (~335 lines)
    └── config_roman.py                ← ROMAN field mappings and config (109 lines)
```

---

## Key Files

### `main.py`
Orchestrates the pipeline:
1. Read call_ids from `calls/*.csv`
2. Query Retell.ai API in parallel → raw call data
3. Generate base tipification DataFrame (28 columns)
4. If `USE_ROMAN=true`: read ROMAN CSV, merge with Retell data
5. Write `results/gestiones_bancor_DDMMAAAA.csv`

### `procesos/retell_manager.py` (~470 lines)
Key functions:
- `obtener_datos_llamadas_retell(call_ids, api_key)` — parallel fetch with `ThreadPoolExecutor(max_workers=100)`
- `buscar_campo_recursivo(data, campo)` — navigates arbitrarily nested JSON to find a field
- `leer_call_ids_csv(carpeta_calls)` — reads and validates the input CSV
- DNS monkey-patching via `socket.getaddrinfo` for connection reuse
- Timeout: 30s per request; handles HTTP errors gracefully (skips failed calls)

Accepted column names for call_id: `Call ID`, `ID de Llamada`, `call_id`, `CallID`, `callId`

### `procesos/tipif_generator.py` (~264 lines)
Key functions:
- `generar_csv_tipificacion(datos_retell)` — builds 28-column DataFrame from raw API results
- `encontrar_archivo_mas_reciente(carpeta)` — finds the latest `base_bancor_*.csv` to enrich client data
- Excluded columns from Retell payload: `lk-call-info`, `lk-real-ip`, `lk-transport`
- Column prefix stripping: removes `var_` and `postcall_` prefixes

### `procesos/roman_manager.py` (~309 lines)
Key functions:
- `leer_datos_roman(carpeta_roman)` — reads ROMAN CSV with multi-encoding fallback
- `normalizar_datos_roman(df)` — standardises column names using `MAPEO_COLUMNAS_ROMAN`
- `filtrar_roman_valido(df)` — removes rows with empty `call_id`

### `procesos/data_merger.py` (~335 lines)
Key functions:
- `merge_retell_roman(df_retell, df_roman)` → `(DataFrame, MergeStats)`
- `MergeStats` dataclass: tracks matched, unmatched, overwritten counts
- Merge key: `call_id`
- Priority: ROMAN values overwrite Retell values for `CAMPOS_SOBRESCRIBIBLES` (only if ROMAN value is non-empty)

### `procesos/config_roman.py` (109 lines)
Pure-data config module. Key constants:
- `MAPEO_COLUMNAS_ROMAN` — dict mapping ROMAN column names → Retell column names
- `CAMPOS_TIPIFICACION` — `['ESTADO', 'SUBESTADO', 'DESCRIPCION', 'OBSERVACIONES']`
- `CAMPOS_COMPROMISO` — `['Fecha_compromiso', 'Monto_compromiso', 'compromiso_de_pago_logrado']`
- `CAMPOS_SOBRESCRIBIBLES` — full list of fields ROMAN can overwrite
- `CAMPOS_PROTEGIDOS` — fields NEVER modified by ROMAN (client data + call metadata)
- `VALORES_VACIOS` — `[None, '', 'null', 'NULL', 'n/a', 'N/A', '-']`
- `es_valor_valido(valor)` — returns False for empty/null values
- `normalizar_booleano(valor)` — converts diverse inputs to bool

---

## Data Model

### Input: calls/*.csv
- Column: `call_id` (or any accepted alias — see `retell_manager.py`)
- Separator: `,` (primary) or `;` (fallback)
- Encoding: `utf-8` (primary), then latin-1 fallback chain

### Retell.ai API Response Structure
```
GET https://api.retellai.com/v2/get-call/{call_id}
Authorization: Bearer {RETELL_API_KEY}
```
Key nested fields extracted via `buscar_campo_recursivo()`:
- `retell_llm_dynamic_variables` — client data injected before the call (CUIL, montos, etc.)
- `custom_analysis_data` — postcall AI analysis (ESTADO, SUBESTADO, DESCRIPCION, etc.)

### Output: gestiones_bancor_DDMMAAAA.csv (28 fixed columns)
```
call_id, AgrupadorProducto, CUIL, ClienteNombre, Cliente_BT, Cuenta,
Dias_Mora, IVAInteresAdeudado, InteresAdeudado, Mail, MontoAdeudado,
NumeroOperacion, OFERTA_Importe, SaldoCapital, Sucursal_Cuenta,
fecha_hoy, fecha_limite_sistema, fecha_manana, hora_actual, user_number,
Comentarios, DESCRIPCION, ESTADO, Email_valido, Fecha_compromiso,
Monto_compromiso, SUBESTADO, compromiso_de_pago_logrado
```
- Separator: `;`
- Encoding: `utf-8`
- Empty values: `''` (never NaN)

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RETELL_API_KEY` | Yes | — | API key for Retell.ai — stored in `.env` |
| `USE_ROMAN` | No | `true` | Enable ROMAN data merge |

Load with `python-dotenv`: `load_dotenv()` at the top of `main.py`.

---

## ROMAN Merge Rules

When `USE_ROMAN=true`:
- ROMAN data is matched to Retell data by `call_id`
- ROMAN values overwrite Retell values **only** for `CAMPOS_SOBRESCRIBIBLES`
- A ROMAN value overwrites only if it is NOT in `VALORES_VACIOS`
- `CAMPOS_PROTEGIDOS` (client data, call metadata) are **never** modified
- If a `call_id` exists in Retell but not in ROMAN → row kept, Retell values used
- If a `call_id` exists in ROMAN but not in Retell → row discarded (no call data)

---

## Coding Rules (module-specific)

1. **Parallel API calls**: Always use `ThreadPoolExecutor(max_workers=100)` + `as_completed()` + `tqdm`. Do not switch to sequential.
2. **Recursive JSON search**: Use `buscar_campo_recursivo()` — never assume fixed nesting depth.
3. **Config changes**: Add new field mappings to `config_roman.py` — never hardcode field names in logic files.
4. **No classes** (except `MergeStats` dataclass in `data_merger.py`): Use top-level functions.
5. **Paths**: `Path(__file__).parent.parent / "calls"` — never hardcode absolute paths.
6. **Output**: Always write with `encoding='utf-8'`, separator `;`, `na_rep=''`.
7. **Standalone execution**: Every `procesos/*.py` must have its own `if __name__ == "__main__"` block.

---

## Required Skills

Load these skills before working on this module:

- `code-conventions` — naming, imports, formatting
- `data-model` — 28-column contract, field types, ROMAN merge rules
- `bug-fix` — if investigating API fetch or merge logic issues

---

## How to Test

No automated tests exist. Manual verification:

```bash
# 1. Place a calls CSV in calls/
# 2. Ensure .env has RETELL_API_KEY
# 3. Run the module
python back-resultados/main.py

# 4. Verify output exists:
# - results/gestiones_bancor_DDMMAAAA.csv

# 5. Validate 28 columns are present
# 6. Check console output for error counts (failed API calls)
# 7. If ROMAN is enabled, verify MergeStats printed at end
```

Expected console output:
- Number of call_ids loaded
- tqdm progress bar (X/total API calls)
- Failed call_ids (if any)
- MergeStats: matched, unmatched, fields overwritten
- Output file path and row count

---

## Common Issues

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| `RETELL_API_KEY not found` | Missing `.env` or variable not set | Create `.env` in `back-resultados/` with `RETELL_API_KEY=key_...` |
| `No CSV found in calls/` | Empty calls folder | Export call_ids from Retell.ai dashboard and place CSV in `calls/` |
| All API calls fail (401) | Invalid API key | Check `.env` value; key starts with `key_` |
| Missing columns in output | Retell changed API response structure | Check `buscar_campo_recursivo()` — field name may have changed |
| ROMAN merge matches nothing | `call_id` format mismatch | Verify ROMAN CSV has same call_id format as Retell export |
| `Import tipif_generator could not be resolved` | LSP path issue (not a runtime issue) | This is a static analysis false positive — `main.py` adds `procesos/` to sys.path at runtime |
