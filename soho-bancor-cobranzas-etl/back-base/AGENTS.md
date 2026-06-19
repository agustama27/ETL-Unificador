# AGENTS.md — back-base

> **Module**: Client base processing (MODULE 1)
> **Read this before**: Modifying any file inside `back-base/`.

---

## Module Purpose

Receives raw Bancor client CSVs from `base-recibida/` and produces two clean calling bases:

1. **Filtered base** (`con-filtros/`): Only clients with `OFERTA_Importe > 0` AND `ModuloCodigo == "201"`. Used for automated AI calls via Retell.ai.
2. **Complete base** (`sin-filtros/`): All clients with `MontoAdeudado > 0`. Includes 2 extra columns (`Estado Cuenta`, `Tasa_40`). Used for broader reporting.

Each base produces:
- `base_bancor_DDMMAAAA.csv` — one row per consolidated client
- `telefonos_x_cliente_DDMMAAAA.csv` — deduplicated mobile numbers for dialing
- `debug/debug_*.csv` — one row per product (pre-consolidation, for auditing)
- `backup/descartados_por_telefono_DDMMAAAA.csv` — clients discarded by phone deduplication

---

## Directory Layout

```
back-base/
├── AGENTS.md                          ← You are here
├── main.py                            ← Entry point: orchestrates 4 steps
├── requirements.txt                   ← pandas>=2.0.0
├── README.md                          ← User-facing documentation
├── clientes_monto_cero.md             ← Analysis: 77 clients with MontoAdeudado=0
├── llamadas_monto_cero.md             ← 21 call_ids to zero-debt clients
├── base-recibida/                     ← INPUT: raw Bancor CSVs (gitignored data)
│   └── GYM_Evoltis_DD-MM(GYM_NN).csv ← Naming pattern from Bancor
├── base-generada/
│   ├── con-filtros/                   ← OUTPUT: filtered base
│   │   ├── base_bancor_DDMMAAAA.csv
│   │   ├── telefonos_x_cliente_DDMMAAAA.csv
│   │   ├── debug/
│   │   └── backup/
│   └── sin-filtros/                   ← OUTPUT: complete base
│       ├── base_bancor_completa_DDMMAAAA.csv
│       ├── telefonos_x_cliente_DDMMAAAA.csv
│       ├── debug/
│       └── backup/
└── procesos/
    ├── base_generator.py              ← Core ETL logic (~731 lines)
    └── phone_extractor.py             ← Phone deduplication logic
```

---

## Key Files

### `main.py`
Orchestrates 4 steps in sequence:
1. `procesar_base()` — filtered base (con-filtros)
2. `procesar_base_completa()` — complete base (sin-filtros)
3. `extraer_telefonos(base_con_filtros)` — phone file for filtered base
4. `extraer_telefonos(base_sin_filtros)` — phone file for complete base

### `procesos/base_generator.py` (~828 lines)
Core ETL. Key functions:
- `leer_csv_con_codificacion(path)` — multi-encoding CSV reader
- `procesar_base(carpeta_entrada, carpeta_salida)` — applies filters, consolidates clients
- `procesar_base_completa(carpeta_entrada, carpeta_salida)` — same without ModuloCodigo filter; also applies active-agreement exclusion filter
- `filtrar_acuerdos_vigentes(df)` — excludes product rows with active agreements (≤ 7 days old); used exclusively by `procesar_base_completa()`
- `consolidar_por_cliente(df)` — merges multi-product rows into one row per `Cliente_BT`
- `deduplicar_por_telefonos(df, backup_path)` — removes clients sharing phone numbers

### `procesos/phone_extractor.py`
- `extraer_telefonos(base_path, output_path)` — reads `NumeroCelular` column, deduplicates, outputs plain list

---

## Data Model

### Input CSV (from Bancor)
- Encoding: `latin-1` (primary) — may need fallback chain
- Separator: `;`
- Decimal: `,` (European)
- Key columns used: `Cliente_BT`, `CUIL`, `NumeroDocumento`, `ClienteNombre`, `NumeroTelefono`, `NumeroCelular`, `NumeroTrabajo`, `Mail`, `Nro Cuenta`, `AgrupadorProducto`, `ModuloCodigo`, `NumeroOperacion`, `Dias_Mora`, `MontoAdeudado`, `OFERTA_Importe`
- Extra columns (sin-filtros only): `Estado Cuenta`, `Tasa_40`
- Filter-only columns (sin-filtros only, not in output): `Gestion_Estado`, `Fecha_Gestion`

### Output: base_bancor_DDMMAAAA.csv (20 columns, con-filtros; 22 columns, sin-filtros)
One row per `Cliente_BT`. Consolidation rules:

| Field | Rule |
|-------|------|
| `MontoAdeudado` | SUM of all products |
| `OFERTA_Importe` | SUM of all products |
| `Dias_Mora` | MAX across products |
| `NumeroOperacion` | Comma-concatenated (unique values) |
| `AgrupadorProducto` | Comma-concatenated (unique values) |
| All other fields | First row of the group |

### Output: telefonos_x_cliente_DDMMAAAA.csv
- No header
- One `NumeroCelular` per line
- No duplicates
- Alphabetically sorted

### Phone Deduplication Logic
When 2+ clients share a phone number (`NumeroTelefono`, `NumeroTrabajo`, or `NumeroCelular`):
- Keep client with highest `MontoAdeudado`
- Tiebreak: keep client with more products (count of commas in `NumeroOperacion`)
- Discarded clients → `backup/descartados_por_telefono_DDMMAAAA.csv`
- Clients with NO phone numbers are always kept

### Special Phone Cleanup
- Remove hyphens: `351-2043044` → `3512043044`
- Replace hardcoded invalid number `3519999999` with empty string (row is kept)

---

## Filters Applied

### Filtered Base (`con-filtros`)
1. `OFERTA_Importe > 0` (European decimal parsed: `647114,99` → `647114.99`)
2. `ModuloCodigo == "201"` (handles both numeric and string values)

### Complete Base (`sin-filtros`)
1. `MontoAdeudado > 0` — excludes clients with no debt or null amount
2. **Active-agreement exclusion** — applied at product-row level, before consolidation:
   - Excludes rows where `Gestion_Estado` is exactly `"07. Promesa de Pago Pactada"` or `"08. Gestión de Refinanciación"`
   - **AND** `Fecha_Gestion` is 7 days or fewer in the past relative to today (`(today - Fecha_Gestion).days <= 7`)
   - Both conditions must be met simultaneously; rows with a missing or unparseable `Fecha_Gestion` are **kept**
   - Implemented in `filtrar_acuerdos_vigentes(df)` — see `base_generator.py:163`
   - `Gestion_Estado` and `Fecha_Gestion` are dropped from the DataFrame after filtering and do **not** appear in the output CSV

---

## Quita de Intereses (ROMAN — sin-filtros only)

The complete base (`BANCOR_ROMAN_YYYYMMDD.csv`) carries **3 extra columns** at the end so the
Retell agent can offer a full payment with an interest discount (criterios 20–25 del PDF
`[BANCOR] COBRANZAS | QUITAS DE INTERESES`):

| Column | Type | Meaning |
|--------|------|---------|
| `aplica_quita` | `si` / `no` | Client is eligible for the discount |
| `monto_quita_ars` | number (2 fixed decimals) or `''` | Final amount to pay **after** discount |
| `fecha_limite_quita` | `YYYY-MM-DD` or `''` | Campaign deadline (config) — only when `aplica_quita == 'si'` |

**Eligibility (`calcular_quita()` in `base_generator.py`)** — `si` only when ALL hold:
1. `Tipo_Mercado == TIPO_MERCADO_ELEGIBLE` (default `"MA"`)
2. client `max(Dias_Mora)` falls in a `RANGOS_QUITA` band (61–365)
3. the computed discount is `> 0`
4. `0 < monto_quita_ars < monto_adeudado_ars`
5. (if `EXCLUIR_SI_TIENE_OFERTA`) the client has no pre-calculated offer

**Discount formula** — `quita = pct_comp·ΣCompensatorio + pct_punit·ΣPunitorios`, where the
percentages come from the matched `RANGOS_QUITA` band; `monto_quita_ars = round(MontoAdeudado_consolidado − quita, 2)`.
It **reuses** the already-consolidated `MontoAdeudado` — never a parallel recalculation.

**Tunables** live in `procesos/config_quita.py` (pure-data module): `TIPO_MERCADO_ELEGIBLE`,
`EXCLUIR_SI_TIENE_OFERTA`, `QUITA_INCLUYE_IVA`, `FECHA_LIMITE_QUITA`, `RANGOS_QUITA`.

**Two pipelines, one formula.** The UI/exe pipeline
(`filtrosAplicados_base_BANCOR/procesos/pipeline_wfm.py`) produces the *deployed* ROMAN and
**imports `calcular_quita` from this module** via its dynamic loader, so both ROMAN outputs stay
aligned with a single source of truth. The raw inputs `Tipo_Mercado`, `Compensatorio`,
`Punitorios` are selected, summed during consolidation, used for the calc, then dropped — they
do **not** appear in the output CSV.

> ⚠️ Pitfalls covered by tests (`tests/back_base/test_calcular_quita.py`):
> the semantic normalizer must keep the exact column names (it would otherwise rename
> `aplica_quita → txt_aplica_quita`), and the boolean detector turns `si/no → true/false`,
> so `aplica_quita` is restored to `si/no` after `columnas_objetivo` — mirroring `oferta_importe`.

---

## Coding Rules (module-specific)

1. **Multi-encoding**: Always try `['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']` with `errors='replace'` fallback — see `leer_csv_con_codificacion()`.
2. **Paths**: Use `Path(__file__).parent.parent / "base-recibida"` — never hardcode absolute paths.
3. **Output encoding**: Always write CSVs with `encoding='utf-8'`, separator `;`, decimal `,`.
4. **No classes**: Use top-level functions only. No OOP.
5. **Numeric fields**: `MontoAdeudado` and `OFERTA_Importe` use European decimal — convert with `str.replace(',', '.')` before `pd.to_numeric()`.
6. **Debug files**: Always generate debug file (one row per product) before consolidation. Never skip this step.
7. **Standalone execution**: Every `procesos/*.py` must have its own `if __name__ == "__main__"` block for isolated testing.

---

## Required Skills

Load these skills before working on this module:

- `code-conventions` — naming, imports, formatting
- `data-model` — CSV column contracts, European format, encoding chains
- `phone-csv-compare` — compare phone coverage between source and target CSVs
- `bug-fix` — if investigating filtering or consolidation bugs

---

## How to Test

No automated tests exist. Manual verification:

```bash
# 1. Place a Bancor CSV in base-recibida/
# 2. Run the module
python back-base/main.py

# 3. Verify outputs exist:
# - base-generada/con-filtros/base_bancor_DDMMAAAA.csv
# - base-generada/con-filtros/telefonos_x_cliente_DDMMAAAA.csv
# - base-generada/sin-filtros/base_bancor_completa_DDMMAAAA.csv
# - base-generada/sin-filtros/telefonos_x_cliente_DDMMAAAA.csv

# 4. Check row counts in console output
# 5. Verify debug files were generated
# 6. If phone deduplication ran, check backup/ folder
```

Expected console output includes:
- Total rows in original CSV
- Rows after each filter
- Active-agreement filter summary: total rows with agreement state, rows excluded (≤7 days), breakdown by state, rows before/after
- Clients consolidated
- Phones before/after deduplication
- Duplicates discarded

---

## Common Issues

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| UnicodeDecodeError | Bancor CSV uses latin-1 | Already handled by encoding chain — check if a new encoding was introduced |
| `OFERTA_Importe` filter removes everything | Column uses period as decimal | Bancor input must use comma as decimal — check source file |
| `ModuloCodigo` filter removes too much | Column has extra spaces or mixed types | `base_generator.py` already strips and casts — check CSV format |
| No output files | No CSVs found in `base-recibida/` | Place the Bancor CSV in the right folder |
| Phone file empty | No valid `NumeroCelular` values after cleanup | Check that the source CSV has populated `NumeroCelular` |
| Agreement filter excludes everything | All rows have recent active agreements | Verify `Fecha_Gestion` format is `D/M/YYYY`; check if input file is unusually recent |
| Agreement filter excludes nothing | `Gestion_Estado` values use different prefix | Confirm exact values in source CSV — expected: `"07. Promesa de Pago Pactada"` / `"08. Gestión de Refinanciación"` |
