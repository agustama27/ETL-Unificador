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
6. **Ask about unknowns** before coding

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
3. **Import from `main.py`** — do not call it directly from other `procesos/` files
4. **Update the module's `AGENTS.md`** — add the new file to the "Key Files" section
5. **If adding a config entry**: update the relevant `config_*.py` file

---

## Config-First Approach

If the feature involves new codes, mappings, or catalog entries:
1. Add them to the relevant `config_*.py` file FIRST
2. The logic files read from config — do not hardcode in logic

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
resultado = procesar_base(BASE_DIR / "base-recibida", BASE_DIR / "base-generada")

# WRONG — hardcodes path, untestable
def procesar_base() -> pd.DataFrame:
    carpeta = Path(__file__).parent / "base-recibida"
    ...
```

---

## Output File Naming Convention

```python
from datetime import datetime

fecha = datetime.today().strftime('%d%m%Y')    # DDMMAAAA → "15012026"
fecha_iso = datetime.today().strftime('%Y-%m-%d')  # YYYY-MM-DD → "2026-01-15"

# back-base outputs
output_path = carpeta_salida / f"base_clarouy_{fecha}.csv"

# back-resultados outputs
output_path = carpeta_results / f"encuestas_clarouy_{fecha}.csv"
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
