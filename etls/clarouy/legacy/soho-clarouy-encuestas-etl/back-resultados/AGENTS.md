# AGENTS.md — back-resultados

> **Module**: Retell.ai survey results processing (MODULE 2)
> **Read this before**: Modifying any file inside `back-resultados/`.

---

## Module Purpose

Queries the Retell.ai API for each `call_id`, extracts survey data from dynamic variables and postcall analysis, optionally merges with ROMAN human-management data, and produces a standardised 26-column CSV for internal review.

**Output file**: `results/encuestas_clarouy_DDMMAAAA.csv`

---

## Directory Layout

```
back-resultados/
├── AGENTS.md                          ← You are here
├── main.py                            ← Entry point
├── requirements.txt                   ← pandas, requests, python-dotenv, tqdm
├── .env                               ← RETELL_API_KEY (gitignored)
├── .gitignore
├── calls/                             ← INPUT: CSV with call_ids
├── roman/                             ← INPUT: CSV with ROMAN data (optional)
├── results/                           ← OUTPUT: 26-column surveys CSV
│   └── encuestas_clarouy_DDMMAAAA.csv
└── procesos/
    ├── retell_manager.py              ← Parallel API queries (100 workers)
    ├── tipif_generator.py             ← 26-column CSV builder
    ├── roman_manager.py               ← ROMAN CSV reader/normalizer
    ├── data_merger.py                 ← Retell + ROMAN merge
    └── config_encuesta.py             ← Field mappings and enums
```

---

## Key Files

### `main.py`
Orchestrates the pipeline:
1. Read call_ids from `calls/*.csv`
2. Query Retell.ai API in parallel → raw call data
3. Generate base tipification DataFrame (26 columns)
4. If `USE_ROMAN=true`: read ROMAN CSV, merge with Retell data
5. Write `results/encuestas_clarouy_DDMMAAAA.csv`

### `procesos/retell_manager.py`
- `obtener_call_ids_desde_csv()` — reads input CSV
- `obtener_datos_llamadas_retell()` — parallel fetch with `ThreadPoolExecutor(max_workers=100)`
- `buscar_campo_recursivo()` — navigates arbitrarily nested JSON
- DNS caching via `socket.getaddrinfo`
- Timeout: 10s per request

### `procesos/tipif_generator.py`
- `generar_csv_encuestas()` — main generator
- `generar_dataframe_tipificacion()` — builds 26-column DataFrame
- `aplanar_diccionario()` — flattens nested JSON

### `procesos/roman_manager.py`
- `obtener_datos_roman()` — reads ROMAN CSV with multi-encoding
- `normalizar_datos_roman()` — standardises column names
- `filtrar_roman_valido()` — removes rows with empty call_id

### `procesos/data_merger.py`
- `merge_datos_inteligente()` — Retell + ROMAN merge
- `MergeStats` dataclass — tracks merge statistics
- Merge key: `call_id`

### `procesos/config_encuesta.py`
Pure-data config:
- `COLUMNAS_SALIDA` — 26 fixed columns
- `MAPEO_COLUMNAS_ROMAN` — ROMAN → internal mappings
- `CAMPOS_SOBRESCRIBIBLES` — fields ROMAN can overwrite
- `CAMPOS_PROTEGIDOS` — fields never modified
- `es_valor_valido()`, `normalizar_booleano()` — helpers

---

## Data Model

### Input: calls/*.csv
- Column: `call_id` (or alias)
- Separator: `,` or `;` (auto-detected)
- Encoding: tries `utf-8`, `latin-1`, `iso-8859-1`, `cp1252`, `utf-16`

### Output: encuestas_clarouy_DDMMAAAA.csv (26 columns)
```
call_id, msisdn, customer_id, nombre_cliente, campaign_id,
encuesta_completada, motivo_cierre, fecha_hora, global_experience,
descripcion_inicial, comentario_mejora, sin_comentarios, detalle_experiencia,
tipo_experiencia, categoria, subcategoria, es_cobertura,
texto_domicilio_cliente, domicilio_validado, domicilio_normalizado,
domicilio_intentos, inconveniente_continua, pudiste_solucionarlo,
derivar_a_asesor, skill_destino, id_caso_reclamo
```
- Separator: `;`
- Encoding: `utf-8`
- Decimal: `,`

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RETELL_API_KEY` | Yes | — | API key for Retell.ai |
| `USE_ROMAN` | No | `true` | Enable ROMAN data merge |

---

## ROMAN Merge Rules

- ROMAN data matched by `call_id`
- ROMAN values overwrite Retell values **only** for `CAMPOS_SOBRESCRIBIBLES`
- Overwrite only if ROMAN value not in `VALORES_VACIOS`
- `CAMPOS_PROTEGIDOS` never modified
- Retell is canonical (no records lost)

---

## Coding Rules (module-specific)

1. **Parallel API calls**: `ThreadPoolExecutor(max_workers=100)` + `as_completed()` + `tqdm`
2. **Recursive JSON search**: Use `buscar_campo_recursivo()`
3. **Config changes**: Add mappings to `config_encuesta.py`
4. **No classes** (except `MergeStats`)
5. **Paths**: `Path(__file__).parent.parent / "calls"`
6. **Output**: `sep=';'`, `decimal=','`, `encoding='utf-8'`, `na_rep=''`
7. **Standalone**: Every `procesos/*.py` has `__main__` block

---

## Required Skills

- `code-conventions`
- `data-model`

---

## How to Test

```bash
# 1. Place call_ids CSV in calls/
# 2. Ensure .env has RETELL_API_KEY
# 3. Run the module
python back-resultados/main.py

# 4. Verify output:
# - results/encuestas_clarouy_DDMMAAAA.csv (26 columns)
```

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `RETELL_API_KEY not found` | Missing `.env` | Create `.env` with key |
| No CSV in calls/ | Empty folder | Place CSV with call_ids |
| API calls fail (401) | Invalid key | Check `.env` key |
| Missing columns | Field name changed | Update `buscar_campo_recursivo()` |
| ROMAN merge = 0 | call_id format mismatch | Normalize with `.str.strip()` |
