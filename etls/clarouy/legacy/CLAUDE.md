# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**soho-clarouy-encuestas-etl** is a Python 3.12+ ETL system that processes post-contact surveys for Claro Uruguay. It integrates data from Retell.ai (automated AI voice surveys) and ROMAN (human management system) to produce structured CSV analysis files. The actual project code lives inside `soho-clarouy-encuestas-etl/`.

## Running the Modules

```bash
# Install dependencies
pip install -r soho-clarouy-encuestas-etl/back-base/requirements.txt
pip install -r soho-clarouy-encuestas-etl/back-resultados/requirements.txt

# Module 1: Process client base
python soho-clarouy-encuestas-etl/back-base/main.py

# Module 2: Process survey results (requires RETELL_API_KEY in back-resultados/.env)
python soho-clarouy-encuestas-etl/back-resultados/main.py

# Run individual process files for standalone testing
python soho-clarouy-encuestas-etl/back-base/procesos/base_generator.py
python soho-clarouy-encuestas-etl/back-resultados/procesos/retell_manager.py
```

No automated test suite exists. Verification is manual: run `main.py` or individual `procesos/*.py` files and check output.

## Architecture

Two independent pipeline stages in a single repo:

**back-base/** — Transforms raw Claro Uruguay client CSVs into a deduplicated calling base.
- `main.py` orchestrates: read CSV → clean/consolidate → deduplicate phones → extract phone list
- `procesos/base_generator.py` — CSV reading, cleaning, client consolidation
- `procesos/phone_extractor.py` — Extract unique MSISDNs for Retell
- Input: `base-recibida/` → Output: `base-generada/con-filtros/`

**back-resultados/** — Queries Retell.ai API, optionally merges ROMAN data, produces 26-column survey CSV.
- `main.py` orchestrates the full pipeline
- `procesos/retell_manager.py` — Parallel API calls (100 workers via ThreadPoolExecutor), recursive JSON field search
- `procesos/tipif_generator.py` — Builds the 26-column DataFrame
- `procesos/roman_manager.py` — ROMAN CSV normalization and validation
- `procesos/data_merger.py` — Intelligent Retell+ROMAN merge (ROMAN overwrites typification fields, protected fields like call_id/msisdn never modified)
- `procesos/config_encuesta.py` — Pure-data config: column order, field mappings, enums, helpers
- Input: `calls/` + `roman/` → Output: `results/encuestas_clarouy_DDMMAAAA.csv`

**skills/** — 6 reusable AI instruction sets (bug-fix, code-conventions, data-model, feature-implementation, testing, skill-creator). Read the relevant skill file before modifying code.

## Key Conventions

- **No OOP**: All logic in top-level functions. Exception: `@dataclass` for stats containers.
- **Paths**: Always relative using `Path(__file__).parent.parent` — never hardcoded absolute paths.
- **CSV output (European format)**: `sep=';'`, `decimal=','`, `encoding='utf-8'`, `index=False`, `na_rep=''`
- **CSV input**: Multi-encoding chain `['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']` with auto separator detection.
- **Type hints**: Required on all function signatures. Use `X | None` syntax (Python 3.10+).
- **Error handling**: `print()` for status (no logging library). Recoverable errors: print + continue. Fatal: `raise`. Never bare `except:`.
- **Environment variables**: Via `python-dotenv`. Secrets in `.env` (gitignored).
- **Naming**: `snake_case` functions/variables, `UPPER_SNAKE_CASE` constants, `df_` prefix for DataFrames.
- **File layout**: Docstring → stdlib imports → third-party → local → constants → functions → `if __name__ == "__main__"` standalone test block.
- **Language**: Spanish acceptable for domain terms; English for technical terms.

## Data Model

- **MSISDN format**: `5989XXXXXXXX` (12 digits, Uruguay country code)
- **Customer ID**: `CLAROUY-XXXXXXX`
- **Output date suffix**: `DDMMAAAA` (e.g., `15012026`)
- **26 fixed output columns** (order matters): defined in `config_encuesta.py:COLUMNAS_SALIDA`
- **ROMAN merge**: matched by `call_id`; overwrites `CAMPOS_SOBRESCRIBIBLES` only when ROMAN value not in `VALORES_VACIOS`; `CAMPOS_PROTEGIDOS` (call_id, msisdn, customer_id, campaign_id) never modified.

## Environment Variables

| Variable | Location | Description |
|----------|----------|-------------|
| `RETELL_API_KEY` | `back-resultados/.env` | Required for Retell.ai API |
| `USE_ROMAN` | `back-resultados/.env` | `true`/`false`, enables ROMAN merge (default: `true`) |
