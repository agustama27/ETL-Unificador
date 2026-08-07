# AGENTS.md — Project Root

> **For AI agents**: Read this file first. It describes the project structure, component layout, available skills, and how the agentic system is organized. Each component with its own `AGENTS.md` is listed below — read the relevant one before acting.

---

## What Is This Project?

**soho-bancor-cobranzas-etl** is a Python ETL system that automates debt-collection data processing for **Banco de Córdoba (Bancor)**. It integrates data from automated AI calls (**Retell.ai**) and from the human-management system (**ROMAN**), producing clean datasets and CRM-ready upload files sent to Bancor every Wednesday and Friday before 12:30 hs.

- **Primary language(s)**: Python 3.12
- **Type**: single-repo, multi-module (4 independent pipeline stages)
- **Main responsibilities**:
  - Clean and consolidate the raw Bancor client CSV into a deduplicated calling base
  - Query the Retell.ai API in parallel and extract call outcomes
  - Merge Retell results with ROMAN human-management data
  - Generate the 13-column `.xlsx` file required by the Bancor CRM
  - (In progress) Generate payment-coupon `.xlsm` files from a VBA-macro template

---

## Repository Layout

```
soho-bancor-cobranzas-etl/
├── AGENTS.md                        ← You are here (root agent guidance)
├── README.md                        ← General project overview
│
├── .claude/
│   ├── settings.json                ← Claude Code permissions
│   └── agents/
│       └── data-arquitect.md        ← Persistent-memory AI agent definition
│
├── agents/                          ← Agent persona definitions (loaded by workflows)
│   └── <agent-name>.md
│
├── workflows/                       ← Agentic workflow definitions
│   └── <workflow>.md
│
├── skills/                          ← AI Skills: loaded on-demand by agents
│   ├── bug-fix.md
│   ├── code-conventions.md
│   ├── data-model.md
│   ├── feature-implementation.md
│   ├── testing.md
│   └── skill-creator.md
│
├── prompts/
│   └── prompt_etl_cargas_masivas_crm.md   ← Original prompt that generated back-cargaMasiva/
│
├── back-base/                       ← MODULE 1: Client base processing (has own AGENTS.md)
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── README.md
│   ├── base-recibida/               ← INPUT: raw Bancor CSVs
│   ├── base-generada/               ← OUTPUT: filtered/complete processed CSVs
│   │   ├── con-filtros/
│   │   └── sin-filtros/
│   └── procesos/
│       ├── base_generator.py        ← Core ETL logic (828 lines)
│       └── phone_extractor.py       ← Phone deduplication
│
├── back-resultados/                 ← MODULE 2: Retell.ai call results (has own AGENTS.md)
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── README.md
│   ├── .env                         ← RETELL_API_KEY (gitignored)
│   ├── calls/                       ← INPUT: CSV with call_ids
│   ├── results/                     ← OUTPUT: 28-column gestiones CSV
│   └── procesos/
│       ├── retell_manager.py        ← Parallel API query (100 workers)
│       ├── tipif_generator.py       ← 28-column CSV generator
│       ├── roman_manager.py         ← ROMAN data normalisation
│       ├── data_merger.py           ← Retell + ROMAN intelligent merge
│       └── config_roman.py          ← ROMAN field mappings and config
│
├── back-cargaMasiva/                ← MODULE 3: CRM bulk upload (has own AGENTS.md)
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── README.md
│   ├── .env                         ← RETELL_API_KEY (gitignored)
│   ├── calls/                       ← INPUT: CSV with call_ids from Retell
│   ├── roman/                       ← INPUT: CSV with ROMAN data
│   ├── output/                      ← OUTPUT: YYYY-MM-DD_EVOLTIS.xlsx + .csv backup
│   ├── plantilla/                   ← Reference template (CRM format)
│   └── procesos/
│       ├── config_catalogos.py      ← CRM state/sub-state/responsible catalogs
│       ├── mapeador.py              ← Descriptive states → CRM codes
│       ├── validador.py             ← CUIT, state, sub-state validations
│       ├── excel_generator.py       ← XLSX generation with openpyxl
│       └── local_adapters.py        ← Adapters that reuse back-resultados/ code
│
└── back-cupones/                    ← MODULE 4: Coupon generation — IN PROGRESS (has own AGENTS.md)
    ├── AGENTS.md
    ├── template/
    │   └── CUPON BANCOR - Template.xlsm   ← VBA-macro template from Bancor
    └── procesos/
        ├── cupon_generator.py       ← EMPTY — pending implementation
        ├── analizar_template.py     ← Utility: inspect .xlsm structure
        └── resumen_campos_template.md     ← Documented field mapping for the template
```

> **Convention**: Every top-level module that a coding agent may modify MUST have its own `AGENTS.md` describing its internal layout, conventions, and testing approach.

---

## End-to-End Data Flow

```
[Bancor raw CSV]
    → back-base/main.py
    → base_bancor_DDMMAAAA.csv + telefonos_x_cliente_DDMMAAAA.csv

[telefonos_x_cliente_*.csv]
    → Retell.ai platform (automated AI calls)
    → [call_ids exported as calls/*.csv]

[call_ids] + [ROMAN CSV (optional)]
    → back-resultados/main.py
    → gestiones_bancor_DDMMAAAA.csv   ← 28 columns, internal review

[call_ids] + [ROMAN CSV (optional)]
    → back-cargaMasiva/main.py
    → YYYY-MM-DD_EVOLTIS.xlsx         ← 13 columns, sent to CRM Bancor
    → Email: Mora_Prejudicial_Estudios@bancor.com.ar (Wed/Fri before 12:30)
```

---

## Component Map

Route your work to the right component based on the issue type:

| Component | `AGENTS.md` location | When to read |
|-----------|----------------------|-------------|
| **back-base** | `back-base/AGENTS.md` | Client CSV processing, phone deduplication, filtering logic |
| **back-resultados** | `back-resultados/AGENTS.md` | Retell.ai API calls, ROMAN merge, 28-column CSV output |
| **back-cargaMasiva** | `back-cargaMasiva/AGENTS.md` | CRM column mapping, XLSX generation, state/code catalogs |
| **back-cupones** | `back-cupones/AGENTS.md` | Payment coupon generation, .xlsm template population |
| **Root / Cross-module** | `AGENTS.md` (this file) | Skills system, shared patterns, cross-module issues |

---

## AI Skills Registry

Skills are on-demand instruction sets. An agent loads a skill by reading the corresponding file in `skills/`. Skills contain conventions, patterns, templates, and testing approaches — agents do NOT need to guess or infer these.

> **Coding agents**: Load the required skills before starting any implementation.

### Available Skills

| Skill name | File | Purpose |
|------------|------|---------|
| `bug-fix` | `skills/bug-fix.md` | Investigation sequence, minimal-change discipline, reproduction test first |
| `code-conventions` | `skills/code-conventions.md` | Naming, imports, formatting, comments — applies to every coding task |
| `data-model` | `skills/data-model.md` | CSV/DataFrame column contracts, field types, validation, serialisation |
| `feature-implementation` | `skills/feature-implementation.md` | TDD order, file skeleton, dependency injection, registration steps |
| `phone-csv-compare` | `skills/phone-csv-compare.md` | Compare phone coverage between two CSVs with `549`/`54` normalization rules |
| `testing` | `skills/testing.md` | pytest conventions, test file layout, mocking, assertion style |
| `skill-creator` | `skills/skill-creator.md` | How to write a new skill file and register it in this table |

> Add a new row whenever you create a new skill file. Keep this table as the single source of truth for skill discovery.
> To create a new skill, load `skill-creator` first — it defines the required structure and registration process.

---

## Coding Agent: General Rules

These rules apply across all modules unless a module-level `AGENTS.md` overrides them.

1. **Read before writing**: Always read the relevant `AGENTS.md` (this file + module) before making changes.
2. **Load required skills**: Before implementing, load every skill listed in your plan's "Required Skills" section.
3. **Evidence-based only**: Do not guess file locations, function names, or behavior. Use tools to read source files.
4. **Minimal blast radius**: Change only what is necessary. Do not refactor unrelated code.
5. **Follow existing patterns**: All modules use top-level functions (not classes), `pathlib.Path` for paths, `;`-separated CSVs with European decimal format, and multi-encoding CSV reading (`latin-1` → `utf-8` fallback chain). Follow these exactly.
6. **Test before finishing**: Run the module's `main.py` (or the relevant `procesos/*.py` standalone block) and confirm it executes without errors.
7. **Never hardcode absolute paths**: Always use `Path(__file__).parent.parent / "folder"` patterns.
8. **Environment variables via dotenv**: Secrets go in `.env` (gitignored). Load with `python-dotenv`. Never commit `.env`.

---

## Key Shared Patterns (apply everywhere)

| Pattern | Description |
|---------|-------------|
| **Multi-encoding CSV read** | Try `['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']` in order; fallback to `errors='replace'` |
| **European CSV format** | Separator `;`, decimal `,` — compatible with Spanish Excel |
| **Relative paths with pathlib** | `Path(__file__).parent.parent / "subfolder"` — never hardcode absolute paths |
| **Standalone `__main__` blocks** | Every `.py` file in `procesos/` has its own `if __name__ == "__main__"` for isolated testing |
| **Parallel API calls** | `ThreadPoolExecutor(max_workers=100)` + `as_completed()` + `tqdm` progress bar |
| **Recursive JSON field search** | `buscar_campo_recursivo()` navigates arbitrarily nested dicts/lists |
| **Pure-data config modules** | `config_*.py` files contain only dicts, lists, and simple utility functions — no classes |
| **Cross-module code reuse** | `back-cargaMasiva/procesos/local_adapters.py` adds `../back-resultados/procesos` to `sys.path` |

---

## Environment Variables

| Variable | Module | Description |
|----------|--------|-------------|
| `RETELL_API_KEY` | back-resultados, back-cargaMasiva | API key for Retell.ai — required |
| `USE_ROMAN` | back-resultados, back-cargaMasiva | `true`/`false` — enable ROMAN data merge (default: `true`) |
| `ESTUDIO` | back-cargaMasiva | Studio name for CRM responsible code (default: `EVOLTIS`) |

---

## Running the Modules

No central automation script. Each module is run independently from the repo root:

```bash
# Module 1 — Process client base
python back-base/main.py

# Module 2 — Process Retell.ai call results
python back-resultados/main.py

# Module 3 — Generate CRM bulk upload file
python back-cargaMasiva/main.py

# Module 4 — Analyse coupon template (utility)
python back-cupones/procesos/analizar_template.py
```

---

## Agentic Workflows

| Workflow file | Trigger | Agent used | Purpose |
|--------------|---------|-----------|---------|
| *(none defined yet)* | — | — | — |

---

## CI/CD Overview

No CI/CD pipeline is currently configured (no `.github/workflows/`, `Dockerfile`, or `Makefile`).

| Pipeline | Trigger | What it checks |
|----------|---------|---------------|
| *(none)* | — | — |

> **Before finishing any task**: Run the affected module's `main.py` locally and confirm it produces the expected output files without errors. `pytest` is installed but no test suite exists yet.
