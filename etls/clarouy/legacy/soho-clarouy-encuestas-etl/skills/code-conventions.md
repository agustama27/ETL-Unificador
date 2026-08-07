# Skill: code-conventions

> Load this skill before writing or modifying any Python code in this project.

---

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions | `snake_case` | `procesar_base()`, `leer_csv_con_codificacion()` |
| Variables | `snake_case` | `df_clientes`, `archivo_csv` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_WORKERS`, `CLASE_OPERACION` |
| Module files | `snake_case.py` | `base_generator.py`, `config_catalogos.py` |
| Config dicts | `UPPER_SNAKE_CASE` | `MAPEO_ESTADOS_RETELL_A_CRM`, `RESPONSABLES` |
| DataFrames | Prefix `df_` | `df_base`, `df_roman`, `df_resultado` |

---

## File Structure

Every Python file in `procesos/` must follow this layout:

```python
"""
Module docstring — 1-3 sentences describing what this module does.
"""
# Standard library imports
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os

# Third-party imports
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Local imports (if any)
# from config_catalogos import ESTADOS_SIN_SUBESTADO

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_WORKERS = 100

# ── Functions ─────────────────────────────────────────────────────────────────

def mi_funcion(param: str) -> pd.DataFrame:
    """
    One-line summary.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.
    """
    ...


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Minimal standalone test
    resultado = mi_funcion("test")
    print(f"Resultado: {resultado}")
```

---

## Import Order

1. Standard library (`pathlib`, `os`, `sys`, `datetime`, `concurrent.futures`)
2. Third-party (`pandas`, `openpyxl`, `requests`, `dotenv`, `tqdm`)
3. Local project modules

Separate groups with a blank line. Never use wildcard imports (`from x import *`).

---

## No Classes (except dataclasses for stats)

All logic uses **top-level functions**. No OOP.

Accepted exception: `@dataclass` for lightweight data containers (e.g., `MergeStats` in `data_merger.py`).

```python
# CORRECT
def mapear_registro(datos: dict) -> dict:
    ...

# WRONG — do not use classes for logic
class Mapeador:
    def mapear(self, datos: dict) -> dict:
        ...
```

---

## Paths — Always Relative

```python
# CORRECT
BASE_DIR = Path(__file__).parent.parent
carpeta_calls = BASE_DIR / "calls"
carpeta_output = BASE_DIR / "output"

# WRONG — never hardcode absolute paths
carpeta_calls = Path("C:/Users/agustin/Desktop/soho-clarouy-encuestas-etl/back-resultados/calls")
```

---

## CSV Output Format (European)

All CSV outputs must use:
```python
df.to_csv(
    output_path,
    sep=';',
    decimal=',',
    encoding='utf-8',
    index=False,
    na_rep=''
)
```

- Separator: `;` (semicolon)
- Decimal: `,` (comma) — Spanish Excel compatibility
- Encoding: `utf-8`
- No index column
- Empty values as `''` (not `NaN`, not `null`)

---

## CSV Input: Multi-Encoding Chain

Always use this pattern for reading CSVs from external sources:

```python
ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

def leer_csv_con_codificacion(path: Path, separador: str = ';') -> tuple[pd.DataFrame, str]:
    """Reads a CSV trying multiple encodings. Returns (df, encoding_used)."""
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=separador, encoding=encoding, on_bad_lines='skip')
            return df, encoding
        except (UnicodeDecodeError, Exception):
            continue
    # Last resort: replace undecodable bytes
    df = pd.read_csv(path, sep=separador, encoding='latin-1', on_bad_lines='skip',
                     encoding_errors='replace')
    return df, 'latin-1 (errors replaced)'
```

Also detect separator: try `,` first, if single column re-try with `;`.

---

## Comments and Docstrings

- **Docstrings**: Every public function must have a docstring with `Args:` and `Returns:`.
- **Inline comments**: Use for non-obvious logic, not obvious steps.
- **Section dividers**: Use `# ── Section Name ──────...` (as shown in file structure above).
- **Language**: Spanish is acceptable for domain-specific terms; English for technical terms.

---

## Error Handling

- Use `print()` for progress/status messages (no logging library).
- On recoverable errors (single failed API call, single invalid record): print the error, continue processing.
- On fatal errors (missing required folder, missing API key): `raise` with a descriptive message.
- Never use bare `except:` — always catch specific exceptions or use `except Exception as e`.

```python
# CORRECT
try:
    df = pd.read_csv(path, sep=';', encoding='latin-1')
except (UnicodeDecodeError, pd.errors.ParserError) as e:
    print(f"  Warning: {path.name} — {e}")
    return None

# WRONG
try:
    df = pd.read_csv(path)
except:
    pass
```

---

## Type Hints

Add type hints to all function signatures:

```python
def mapear_registro(datos: dict) -> dict | None:
def leer_csv_con_codificacion(path: Path, separador: str = ';') -> tuple[pd.DataFrame, str]:
def obtener_datos_llamadas_retell(call_ids: list[str], api_key: str) -> dict[str, dict]:
```

Use `from typing import Optional` only for Python <3.10 compatibility. Prefer `X | None` syntax.

---

## Environment Variables

Load with `python-dotenv` at the top of the entry point:

```python
from dotenv import load_dotenv
import os

load_dotenv()  # or load_dotenv(specific_path)
API_KEY = os.getenv('RETELL_API_KEY')
if not API_KEY:
    raise ValueError("RETELL_API_KEY no configurada. Verificar archivo .env")
```

Never hardcode secrets. Never commit `.env` files.
