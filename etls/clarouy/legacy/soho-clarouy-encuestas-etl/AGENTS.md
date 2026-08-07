# AGENTS.md — Project Root

> **For AI agents**: Read this file first. It describes the project structure, component layout, available skills, and how the agentic system is organized.

---

## What Is This Project?

**soho-clarouy-encuestas-etl** is a Python ETL system that automates post-contact survey processing for **Claro Uruguay**. It integrates data from automated AI calls (**Retell.ai**) and from the human-management system (**ROMAN**), producing clean CSV files for internal analysis.

- **Primary language(s)**: Python 3.12
- **Type**: single-repo, multi-module (2 independent pipeline stages)
- **Main responsibilities**:
  - Clean and consolidate the raw Claro Uruguay client CSV into a deduplicated calling base
  - Query the Retell.ai API in parallel and extract survey outcomes
  - Merge Retell results with ROMAN human-management data
  - Generate the 26-column CSV file for internal review

---

## Repository Layout

```
soho-clarouy-encuestas-etl/
├── AGENTS.md                        ← You are here (root agent guidance)
├── README.md                        ← General project overview
│
├── .claude/
│   └── settings.json                ← Claude Code permissions
│
├── skills/                          ← AI Skills: loaded on-demand by agents
│   ├── bug-fix.md
│   ├── code-conventions.md
│   ├── data-model.md
│   ├── feature-implementation.md
│   ├── testing.md
│   └── skill-creator.md
│
├── back-base/                       ← MODULE 1: Client base processing
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── base-recibida/               ← INPUT: raw Claro Uruguay CSVs
│   ├── base-generada/               ← OUTPUT: processed CSVs
│   │   ├── con-filtros/
│   │   │   ├── base_clarouy_DDMMAAAA.csv
│   │   │   └── telefonos_x_cliente_DDMMAAAA.csv
│   │   └── backup/
│   └── procesos/
│       ├── base_generator.py
│       └── phone_extractor.py
│
└── back-resultados/                 ← MODULE 2: Survey results (Retell + ROMAN)
    ├── AGENTS.md
    ├── main.py
    ├── requirements.txt
    ├── .env                         ← RETELL_API_KEY (gitignored)
    ├── .gitignore
    ├── calls/                       ← INPUT: CSV with call_ids
    ├── roman/                      ← INPUT: CSV with ROMAN data
    ├── results/                    ← OUTPUT: 26-column CSV
    │   └── encuestas_clarouy_DDMMAAAA.csv
    └── procesos/
        ├── retell_manager.py        ← Parallel API queries (100 workers)
        ├── tipif_generator.py       ← 26-column CSV builder
        ├── roman_manager.py         ← ROMAN data normalisation
        ├── data_merger.py           ← Retell + ROMAN merge
        └── config_encuesta.py       ← Field mappings and enums
```

---

## End-to-End Data Flow

```
[Claro Uruguay raw CSV]
    → back-base/main.py
    → base_clarouy_DDMMAAAA.csv + telefonos_x_cliente_DDMMAAAA.csv

[telefonos_x_cliente_*.csv]
    → Retell.ai platform (automated AI surveys)
    → [call_ids exported as calls/*.csv]

[call_ids] + [ROMAN CSV (optional)]
    → back-resultados/main.py
    → encuestas_clarouy_DDMMAAAA.csv   ← 26 columns, internal review
```

---

## Component Map

| Component | `AGENTS.md` location | When to read |
|-----------|----------------------|-------------|
| **back-base** | `back-base/AGENTS.md` | Client CSV processing, phone deduplication |
| **back-resultados** | `back-resultados/AGENTS.md` | Retell.ai API calls, ROMAN merge, 26-column output |
| **Root / Cross-module** | `AGENTS.md` (this file) | Skills system, shared patterns |

---

## AI Skills Registry

Skills are on-demand instruction sets. An agent loads a skill by reading the corresponding file in `skills/`.

| Skill name | File | Purpose |
|------------|------|---------|
| `bug-fix` | `skills/bug-fix.md` | Investigation sequence, minimal-change discipline |
| `code-conventions` | `skills/code-conventions.md` | Naming, imports, formatting |
| `data-model` | `skills/data-model.md` | CSV/DataFrame column contracts |
| `feature-implementation` | `skills/feature-implementation.md` | TDD order, file skeleton |
| `testing` | `skills/testing.md` | pytest conventions |
| `skill-creator` | `skills/skill-creator.md` | How to write new skill files |

---

## Coding Agent: General Rules

1. **Read before writing**: Always read the relevant `AGENTS.md` (this file + module).
2. **Load required skills**: Before implementing, load every skill listed.
3. **Evidence-based only**: Do not guess file locations, function names, or behavior.
4. **Minimal blast radius**: Change only what is necessary.
5. **Follow existing patterns**: All modules use top-level functions, `pathlib.Path`, `;`-separated CSVs with European decimal format, and multi-encoding CSV reading.
6. **Test before finishing**: Run the module's `main.py` and confirm it executes without errors.
7. **Never hardcode absolute paths**: Use `Path(__file__).parent.parent` patterns.
8. **Environment variables via dotenv**: Secrets go in `.env` (gitignored).

---

## Key Shared Patterns

| Pattern | Description |
|---------|-------------|
| **Multi-encoding CSV read** | Try `['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']` in order |
| **European CSV format** | Separator `;`, decimal `,` |
| **Relative paths with pathlib** | `Path(__file__).parent.parent / "subfolder"` |
| **Standalone `__main__` blocks** | Every `.py` file in `procesos/` has its own test block |
| **Parallel API calls** | `ThreadPoolExecutor(max_workers=100)` + `as_completed()` + `tqdm` |
| **Recursive JSON field search** | `buscar_campo_recursivo()` navigates nested dicts |
| **Pure-data config modules** | `config_*.py` files contain only dicts, lists, helpers |

---

## Environment Variables

| Variable | Module | Description |
|----------|--------|-------------|
| `RETELL_API_KEY` | back-resultados | API key for Retell.ai — required |
| `USE_ROMAN` | back-resultados | `true`/`false` — enable ROMAN merge (default: `true`) |

---

## Running the Modules

Each module is run independently from the repo root:

```bash
# Module 1 — Process client base
python back-base/main.py

# Module 2 — Process Retell.ai survey results
python back-resultados/main.py
```
