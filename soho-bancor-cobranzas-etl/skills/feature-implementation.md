# Skill: feature-implementation

> Load this skill before implementing any new feature or module in this project.

---

## Pre-Implementation Checklist

Before writing a single line of code:

1. **Read the relevant `AGENTS.md`** (root + module)
2. **Load required skills**: `code-conventions`, `data-model`, and this file
3. **Read existing similar files** to understand the patterns in use — do not invent new patterns
4. **Identify the exact input/output contract** — what columns come in, what columns go out
5. **Identify the output file path** — where does the new file get written?
6. **Ask about unknowns** before coding — see `back-cupones/AGENTS.md` "Questions Pending" as an example

---

## File Skeleton

Every new `procesos/*.py` file must follow this skeleton:

```python
"""
One-sentence description of what this module does.

Input: brief description of what it reads
Output: brief description of what it produces
"""
from pathlib import Path
from datetime import datetime
import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────
# Add module-specific constants here

# ── Functions ─────────────────────────────────────────────────────────────────

def funcion_principal(param: tipo) -> tipo:
    """
    One-line summary.

    Args:
        param: Description.

    Returns:
        Description.
    """
    pass


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Minimal standalone test — verify the function runs without errors
    resultado = funcion_principal(valor_test)
    print(f"OK: {resultado}")
```

---

## New Module Registration Steps

When adding a new `procesos/*.py` file:

1. **Create the file** using the skeleton above
2. **Add a standalone `__main__` block** for isolated testing
3. **Import from `main.py`** — do not call it directly from other `procesos/` files (except via `local_adapters.py` for cross-module reuse)
4. **Update the module's `AGENTS.md`** — add the new file to the "Key Files" section
5. **If adding a config entry** (new state mapping, new studio code): update `config_catalogos.py` AND the `data-model.md` skill

---

## Config-First Approach

If the feature involves new codes, mappings, or catalog entries:
1. Add them to the relevant `config_*.py` file FIRST
2. The logic files (`mapeador.py`, `validador.py`) read from config — do not hardcode in logic

Example: Adding a new Retell state `"acuerdo_especial"`:
```python
# In config_catalogos.py — add to MAPEO_ESTADOS_RETELL_A_CRM:
"acuerdo_especial": ("E0012", "E002"),  # Promesa de Pago Pactada - Parcial Acordado
```
No change needed in `mapeador.py` — it already iterates the mapping dict.

---

## Cross-Module Code Reuse

If the new feature needs functions from `back-resultados/procesos/`:
- Add imports to `back-cargaMasiva/procesos/local_adapters.py` — do not duplicate code
- Follow the pattern of `obtener_datos_llamadas_retell_local()` for wrapping with local paths

If a new module needs similar pattern as `back-resultados` for a different context:
- Create a new `local_adapters_<name>.py` following the same pattern
- Never import directly from sibling modules by relative path — always use `sys.path` injection

---

## Dependency Injection (Path Pattern)

Functions should receive paths as parameters, not hardcode them internally:

```python
# CORRECT — testable, flexible
def procesar_base(carpeta_entrada: Path, carpeta_salida: Path) -> pd.DataFrame:
    archivos = list(carpeta_entrada.glob("*.csv"))
    ...

# In main.py:
BASE_DIR = Path(__file__).parent
resultado = procesar_base(BASE_DIR / "base-recibida", BASE_DIR / "base-generada/con-filtros")

# WRONG — hardcodes path, untestable
def procesar_base() -> pd.DataFrame:
    carpeta = Path(__file__).parent / "base-recibida"
    ...
```

---

## Implementing a New Module (e.g., back-cupones)

Follow this order:

1. **Create `requirements.txt`** with minimum dependencies
2. **Create `procesos/<generator>.py`** with skeleton + `__main__` block
3. **Implement one function at a time**, testing standalone after each
4. **Create `main.py`** that orchestrates the steps — see `back-base/main.py` as template
5. **Update `back-cupones/AGENTS.md`** with the final structure
6. **Update root `AGENTS.md`** only if the module layout changes

---

## Output File Naming Convention

```python
from datetime import datetime

fecha = datetime.today().strftime('%d%m%Y')    # DDMMAAAA → "15012026"
fecha_iso = datetime.today().strftime('%Y-%m-%d')  # YYYY-MM-DD → "2026-01-15"

# base-base outputs
output_path = carpeta_salida / f"base_bancor_{fecha}.csv"

# back-resultados outputs
output_path = carpeta_results / f"gestiones_bancor_{fecha}.csv"

# back-cargaMasiva outputs
estudio = os.getenv('ESTUDIO', 'EVOLTIS')
output_path = carpeta_output / f"{fecha_iso}_{estudio}.xlsx"
```

---

## Parallel API Calls Pattern

When implementing functions that call an external API for many records:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

MAX_WORKERS = 100

def obtener_datos_en_paralelo(ids: list[str], api_key: str) -> dict:
    resultados = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(llamar_api_individual, id_, api_key): id_
            for id_ in ids
        }
        with tqdm(total=len(ids), desc="Consultando API", unit="registros") as pbar:
            for future in as_completed(futures):
                id_ = futures[future]
                try:
                    resultado = future.result()
                    resultados[id_] = resultado
                except Exception as e:
                    print(f"  Error en {id_}: {e}")
                    resultados[id_] = {}
                pbar.update(1)
    return resultados
```

---

## Verification Before Finishing

Before marking a feature as done:

```bash
# 1. Run standalone test of the new procesos/ file
python back-<module>/procesos/<new_file>.py

# 2. Run the full module
python back-<module>/main.py

# 3. Confirm output files exist with expected columns
# 4. Confirm no unexpected columns are missing or renamed
# 5. Confirm row counts match expectations
```
