# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETL pipeline for processing Naranja collections (cobranzas) phone data. Takes pipe-delimited TXT files, normalizes Argentine phone numbers to international format, and produces semicolon-delimited CSVs sorted by phone count for collections campaigns.

## Running the ETL

```bash
# Run the full pipeline (auto-detects newest TXT in back-base/base_recibida/)
python main.py

# Run individual steps with explicit file paths
python -m procesos.base_generator <path_to_input.txt>
python -m procesos.phone_extractor <path_to_base_naranja.csv>
```

**No external dependencies** — uses only Python standard library. Requires Python 3.12+.

## Data Flow

```
back-base/base_recibida/<newest>.txt   (pipe-delimited, 33 columns)
        │
        ▼  procesos/base_generator.py
back-base/base_procesada/base_naranja_DDMMAAAA.csv   (semicolon-delimited, normalized phones)
        │
        ▼  procesos/phone_extractor.py
back-base/base_procesada/telefonos_naranja_DDMMAAAA.csv   (DNI + TEL 1-6, sorted by phone count desc)
```

Both input and output directories are git-ignored (only `.gitkeep` is tracked).

## Architecture

- **`main.py`** — orchestrates both steps, handles FileNotFoundError/ValueError
- **`procesos/base_generator.py`** — reads newest `.txt` from `back-base/base_recibida/`, normalizes TEL 1–6, converts delimiter `|` → `;`, outputs dated CSV
- **`procesos/phone_extractor.py`** — reads newest `base_naranja_*.csv`, extracts phone columns, sorts by populated phone count descending

### Phone Normalization Logic (`_normalizar_telefono`)

- **CEL (mobile):** prepends `549`, strips leading `0`
- **TEL (landline):** prepends `54`, strips leading `0`
- Matches last 4 digits of value against `telephone_number` fields across groups to resolve area codes
- Supports a `grupo_preferido` parameter to bias group matching order

### File Discovery

Both modules auto-select the newest matching file by `os.path.getmtime` when no explicit path is given — useful for unattended batch runs.

## Back-resultados

Procesa LOGCALL + historial_llamadas + base M30 y genera archivo USUOLOS.

### Ejecutar

```bash
python main.py --back

# Modo estricto de calidad PHONE (falla si PHONE irrecuperable supera umbral)
python main.py --back --strict-phone-quality --max-phone-irrecoverable-ratio 0.05
```

### Inputs esperados (auto-discovery por mtime)

- `back-resultados/back_recibida/logcall/LOGCALL_*.csv`
- `back-resultados/back_recibida/historial/historial_llamadas*.csv`
- `back-base/base_recibida/<newest>.txt` (M30OLOS original pipe-delimited, 33 columnas)

Tambien se pueden pasar rutas explicitas:

```bash
python main.py --back --logcall <path> --historial <path> --m30 <path>
```

### Output

- `back-resultados/back_procesada/DEELO_NAR_USUEVOLTIS_YYYYMMDD_HH.txt`
- `back-resultados/back_procesada/_anomalias_YYYYMMDD_HHMMSS.txt`

### Cambios del feedback 13/05/2026

- El output usa prefijo `DEELO_NAR_USUEVOLTIS_`.
- Columna 8 fija en `USUEVOLTIS` y columna 36 fija en `EVOLTIS`.
- Columna 7 ahora es correlativo `1..N` por lote (ordenado por timestamp).
- Las columnas 15-16-17 salen del M30OLOS original (area, numero, tipo), con match por E.164 y fallback por ultimos 8 digitos.
- Columna 4 para `PROMISE` aplica padding a `DU` + 11 digitos.
- Columna 28 normaliza montos a coma decimal sin separadores de miles.

## Output Conventions

- Date suffix format: `DDMMAAAA` (day-month-year, e.g., `27022026`)
- Semicolon delimiter chosen for Excel compatibility in Argentina/LATAM locales
- `telefonos_naranja_*.csv` header: `TEL 1;TEL 2;TEL 3;TEL 4;TEL 5;TEL 6;DNI`
