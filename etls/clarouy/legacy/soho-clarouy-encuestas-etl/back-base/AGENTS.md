# AGENTS.md — back-base

> **Module**: Client base processing (MODULE 1)
> **Read this before**: Modifying any file inside `back-base/`.

---

## Module Purpose

Receives raw Claro Uruguay client CSVs from `base-recibida/` and produces:

1. **Base consolidada** (`base_clarouy_DDMMAAAA.csv`): One row per client
2. **Teléfonos únicos** (`telefonos_x_cliente_DDMMAAAA.csv`): Deduplicated MSISDN numbers for Retell

---

## Directory Layout

```
back-base/
├── AGENTS.md                          ← You are here
├── main.py                            ← Entry point
├── requirements.txt                   ← pandas>=2.0.0
├── base-recibida/                     ← INPUT: raw Claro Uruguay CSVs
├── base-generada/
│   └── con-filtros/
│       ├── base_clarouy_DDMMAAAA.csv  ← OUTPUT: consolidated base
│       ├── telefonos_x_cliente_DDMMAAAA.csv  ← OUTPUT: phone list
│       └── backup/                    ← Discarded records
└── procesos/
    ├── base_generator.py              ← Core ETL logic
    └── phone_extractor.py             ← Phone extraction
```

---

## Key Files

### `main.py`
Orchestrates 3 steps:
1. `procesar_base()` — read, clean, consolidate
2. `deduplicar_por_telefonos()` — remove duplicate phones
3. `extraer_telefonos()` — extract phone list

### `procesos/base_generator.py`
- `leer_csv_con_codificacion()` — multi-encoding CSV reader
- `buscar_csv_en_carpeta()` — finds latest CSV
- `limpiar_msisdn()` — formats phone to 5989XXXXXXXX
- `generar_customer_id()` — generates CLAROUY-XXXXXXX IDs
- `procesar_base()` — main ETL
- `deduplicar_por_telefonos()` — removes duplicate phones

### `procesos/phone_extractor.py`
- `buscar_base_generada()` — finds base CSV
- `extraer_telefonos()` — extracts unique phones

---

## Data Model

### Input CSV (from Claro Uruguay)
- Encoding: tries `utf-8`, `latin-1`, `iso-8859-1`, `cp1252`, `utf-16`
- Separator: auto-detect `,` or `;`
- Expected columns (flexible): `msisdn`, `telefono`, `customer_id`, `nombre_cliente`, `documento`, `email`, `domicilio`, `plan`, `estado`

### Output: base_clarouy_DDMMAAAA.csv
```
customer_id, msisdn, nombre_cliente, documento, email, domicilio, plan, estado, fecha_alta
```

### Output: telefonos_x_cliente_DDMMAAAA.csv
- One MSISDN per line
- Format: `5989XXXXXXXX`
- No header
- Sorted alphabetically
- No duplicates

---

## Coding Rules (module-specific)

1. **Multi-encoding**: Always try the encoding chain `['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']`
2. **Paths**: Use `Path(__file__).parent.parent` — never hardcode absolute paths
3. **Output**: Always `sep=';'`, `decimal=','`, `encoding='utf-8'`, `na_rep=''`
4. **No classes**: Top-level functions only
5. **MSISDN format**: `5989XXXXXXXX` (12 digits)
6. **Customer ID**: `CLAROUY-XXXXXXX` format

---

## Required Skills

Load before working on this module:
- `code-conventions`
- `data-model`

---

## How to Test

```bash
# 1. Place CSV in base-recibida/
# 2.python back-base/main Run the module
.py

# 3. Verify outputs:
# - base-generada/con-filtros/base_clarouy_DDMMAAAA.csv
# - base-generada/con-filtros/telefonos_x_cliente_DDMMAAAA.csv
```

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| No CSV found | Empty base-recibida | Place CSV in folder |
| UnicodeDecodeError | Wrong encoding | Encoding chain already handles this |
| Empty phone list | No valid MSISDN | Check source CSV has phone column |
