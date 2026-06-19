# AGENTS.md — back-cargaMasiva

> **Module**: CRM bulk upload generation (MODULE 3)
> **Read this before**: Modifying any file inside `back-cargaMasiva/`.

---

## Module Purpose

Final ETL stage. Transforms Retell.ai call results + ROMAN human-management data into the **13-column `.xlsx` format** required by Bancor's CRM bulk upload system.

**Output file**: `output/YYYY-MM-DD_EVOLTIS.xlsx` (plus `.csv` backup)
**Delivery**: Email to `Mora_Prejudicial_Estudios@bancor.com.ar` every Wednesday and Friday before 12:30 hs.
**Subject**: `"Cargas masivas CRM (FECHA) (NOMBRE ESTUDIO)"`

---

## Directory Layout

```
back-cargaMasiva/
├── AGENTS.md                          ← You are here
├── main.py                            ← Entry point: orchestrates 5 steps
├── requirements.txt                   ← openpyxl, pandas, python-dotenv, requests, tqdm
├── README.md                          ← User-facing documentation
├── .env                               ← RETELL_API_KEY (gitignored)
├── calls/                             ← INPUT: CSV with call_ids from Retell.ai export
│   └── export_*.csv
├── roman/                             ← INPUT: CSV with ROMAN human-management data
│   └── historial_llamadas*.csv
├── output/                            ← OUTPUT: final files for Bancor CRM
│   └── YYYY-MM-DD_EVOLTIS.xlsx
│   └── YYYY-MM-DD_EVOLTIS.csv        ← CSV backup
├── plantilla/                         ← Reference: CRM format example
│   └── Carga Masiva Gestiones CRM Bancor - ejemplo(MODELO envio).csv
└── procesos/
    ├── __init__.py
    ├── config_catalogos.py            ← CRM catalogs: states, sub-states, responsible codes
    ├── mapeador.py                    ← Descriptive states → CRM codes
    ├── validador.py                   ← CUIT, state, sub-state validations
    ├── excel_generator.py             ← XLSX generation with openpyxl
    └── local_adapters.py              ← Reuses back-resultados/ modules via sys.path injection
```

---

## Key Files

### `main.py`
Orchestrates 5 steps:
1. Fetch call data from Retell.ai API (`obtener_datos_llamadas_retell_local()`)
2. Read ROMAN data if `USE_ROMAN=true` (`obtener_datos_roman_local()`)
3. Merge Retell + ROMAN data (`merge_datos_inteligente()`)
4. Map each record to CRM format (`mapear_registro()`)
5. Validate records and generate XLSX (`validar_y_generar_excel()`)

### `procesos/config_catalogos.py` (176 lines)
Pure-data config. Key constants:
- `CLASE_OPERACION = "ZCE1"` — always fixed in column 1
- `ESTADOS_SIN_SUBESTADO` — 16 states that don't require a sub-state
- `ESTADOS_CON_SUBESTADO` — 2 states requiring mandatory sub-state: `E0012`, `E0002`
- `SUBESTADOS_POR_ESTADO` — valid sub-states per state (`E001`, `E002`, `E003`)
- `MAPEO_ESTADOS_RETELL_A_CRM` — descriptive name (Retell/ROMAN) → `(estado_code, subestado_code)` tuple
- `RESPONSABLES` — studio name → CRM responsible code (10 studios registered)
- `COLUMNAS_SALIDA` — exact 13-column order required by CRM
- `MAX_DESCRIPCION = 100` — max chars for `Descripción` field
- `LONGITUD_CUIT = 11` — CUIT must be exactly 11 digits

**Critical**: `"Sub- Estado"` has a space before "Estado" — this matches the CRM template exactly. Do not change.

### `procesos/mapeador.py`
Key function:
- `mapear_registro(datos_llamada)` → dict with 13 CRM columns
  - Maps `ESTADO` descriptive → `(E0012, E003)` via `MAPEO_ESTADOS_RETELL_A_CRM`
  - Fills `Clase de Operación` always as `"ZCE1"`
  - Fills `Responsable` from `ESTUDIO` env var via `RESPONSABLES` dict
  - Truncates `Descripción` to 100 chars
  - Returns `None` if the state maps to `ESTADOS_A_DESCARTAR`

### `procesos/validador.py`
Key function:
- `validar_registro(registro)` → `(bool, list[str])` — (is_valid, list of error messages)
  - CUIT must be 11 numeric digits (no hyphens, no spaces)
  - `Estado` must be in `TODOS_LOS_ESTADOS`
  - `Sub- Estado` must be in `SUBESTADOS_POR_ESTADO[estado]` when state is in `ESTADOS_CON_SUBESTADO`
  - `Sub- Estado` must be empty when state is in `ESTADOS_SIN_SUBESTADO`
  - `Responsable` must be in `RESPONSABLES.values()`
  - `Descripción` must not exceed 100 chars

### `procesos/excel_generator.py`
Key function:
- `crear_excel_carga_masiva(registros, output_path)` → generates `.xlsx`
  - Sheet name: `"MODELO envio"` (matches CRM import requirement exactly)
  - Formatting: bold header row, borders on all cells, freeze top row
  - Also generates `.csv` backup in same folder

### `procesos/local_adapters.py` (177 lines)
Architectural bridge — allows `back-cargaMasiva` to reuse `back-resultados` code:
- Loads `.env` from `../back-resultados/.env` (fallback: local `.env`)
- Injects `../back-resultados/procesos` into `sys.path`
- Imports: `retell_manager`, `roman_manager`, `data_merger`
- Wraps with local paths: `obtener_datos_llamadas_retell_local()`, `obtener_datos_roman_local()`

---

## Data Model

### Input: calls/*.csv
- Column: `call_id` (or any accepted alias from `retell_manager.py`)
- Separator: `,` (primary) or `;` (fallback)
- Multiple CSV files are merged (all call_ids from all files processed)

### Input: roman/*.csv
- Most recently modified CSV is used (by `st_mtime`)
- Expected column: `ID de Llamada` (mapped → `call_id`)
- Separator: `,` (primary) or `;` (fallback)

### Output: 13-column CRM format

| # | Column | Type | Rule |
|---|--------|------|------|
| 1 | `Clase de Operación` | Text | Always `"ZCE1"` |
| 2 | `Estado` | Text | CRM code (e.g., `E0012`) — required |
| 3 | `Sub- Estado` | Text | CRM code (e.g., `E003`) — conditional |
| 4 | `CUIT` | Number | 11 digits, no separators — required |
| 5 | `Cuenta` | Number | From client data — optional |
| 6 | `Desc. Acuerdo Comercial` | Text | Optional |
| 7 | `Acuerdo Comercial` | Number | Optional |
| 8 | `Responsable` | Number | Studio code from `RESPONSABLES` — required |
| 9 | `Descripción` | Text | Max 100 chars — required |
| 10 | `Persona de Contacto` | Text | Optional |
| 11 | `Juzgado` | Text | Optional |
| 12 | `Garante` | Text | Optional |
| 13 | `Notas` | Text | Optional |

### State/Sub-state Mapping (from Retell descriptive names to CRM codes)

Key mappings in `MAPEO_ESTADOS_RETELL_A_CRM`:

| Retell state | CRM Estado | CRM Sub-Estado |
|---|---|---|
| `promesa_de_pago_acordada` | `E0012` | `E003` (Total) |
| `promesa_parcial` | `E0012` | `E001` (Parcial) |
| `no_contesta` | `E0005` | — |
| `contacto_con_titular` | `E0025` | — |
| `sin_voluntad_de_pago` | `E0023` | — |
| `llamada_interrumpida` | → discarded | — |
| `datos_erroneos` | → discarded | — |

### Registered Studios (RESPONSABLES)

| Studio | CRM Code |
|--------|----------|
| EVOLTIS | 5000000786 |
| KONECTA | 5000000785 |
| GEEX | 5000000784 |
| ALTERMAN | 7000004923 |
| DIAZ YOFRE | 7000002877 |
| JLC | 7000002901 |
| RECOVERY MANAGEMENT | 7000005550 |
| TILLARD | 7000002878 |
| TONELLI | 7000005647 |
| VILATTA | 7000002897 |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RETELL_API_KEY` | Yes | — | Loaded from `back-resultados/.env` first, then local `.env` |
| `USE_ROMAN` | No | `true` | Enable ROMAN data merge |
| `ESTUDIO` | No | `EVOLTIS` | Studio name — must match a key in `RESPONSABLES` exactly |

---

## Architecture: Cross-Module Code Reuse

`back-cargaMasiva` reuses `back-resultados` modules directly:

```
local_adapters.py
  → injects ../back-resultados/procesos into sys.path
  → imports: retell_manager, roman_manager, data_merger
  → wraps with local paths for calls/ and roman/ folders
```

**Consequence**: Any change to `back-resultados/procesos/retell_manager.py`, `roman_manager.py`, or `data_merger.py` automatically affects `back-cargaMasiva` behaviour. Always test both modules after changes to shared code.

---

## Coding Rules (module-specific)

1. **Config-first**: All new state mappings go in `config_catalogos.py`. Never hardcode states or codes in `mapeador.py` or `validador.py`.
2. **`"Sub- Estado"` spelling**: This column name has a space before "Estado". Do not fix the apparent typo — it matches the CRM template exactly.
3. **CUIT handling**: Strip non-numeric characters before validation. Do not add hyphens.
4. **Records discarded** (`ESTADOS_A_DESCARTAR`): Log discarded count but do not raise errors.
5. **Cross-module imports**: Never import `back-resultados` modules directly — always go through `local_adapters.py`.
6. **Output path**: `output/YYYY-MM-DD_ESTUDIO.xlsx` — date from `datetime.today()`, studio from `ESTUDIO` env var.
7. **No classes**: Top-level functions only.
8. **Standalone execution**: Every `procesos/*.py` must have its own `if __name__ == "__main__"` block.

---

## Required Skills

Load these skills before working on this module:

- `code-conventions` — naming, imports, formatting
- `data-model` — 13-column CRM contract, state/sub-state rules, CUIT validation
- `bug-fix` — if investigating mapping errors or validation rejections

---

## How to Test

No automated tests exist. Manual verification:

```bash
# 1. Place call_ids CSV in calls/
# 2. Place ROMAN CSV in roman/ (optional)
# 3. Ensure RETELL_API_KEY in back-resultados/.env
# 4. Run the module
python back-cargaMasiva/main.py

# 5. Verify output:
# - output/YYYY-MM-DD_EVOLTIS.xlsx exists
# - output/YYYY-MM-DD_EVOLTIS.csv exists (backup)
# - Excel has sheet "MODELO envio"
# - 13 columns in correct order
# - No invalid CUITs or states in output
```

Expected console output:
- Call IDs loaded count
- API progress (tqdm bar)
- ROMAN records loaded (if enabled)
- Merge stats (matched, unmatched)
- Records mapped, validated, discarded
- Output file path

---

## Common Issues

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| `RETELL_API_KEY no configurada` | Missing `.env` in `back-resultados/` | Create `back-resultados/.env` with `RETELL_API_KEY=key_...` |
| `ESTUDIO` not in `RESPONSABLES` | Wrong `ESTUDIO` env var value | Check exact studio name in `config_catalogos.py:RESPONSABLES` |
| All records discarded | Retell states not in `MAPEO_ESTADOS_RETELL_A_CRM` | Add new state mapping to `config_catalogos.py` |
| CUIT validation failures | CUIT has hyphens or wrong length | Check source data; `validador.py` strips non-numeric chars automatically |
| Sub-estado validation fails | State code needs sub-state but none provided | Check `ESTADOS_CON_SUBESTADO` — `E0012` and `E0002` always need sub-state |
| Excel has wrong sheet name | `NOMBRE_HOJA` changed | Must be exactly `"MODELO envio"` — CRM import requires this exact name |
