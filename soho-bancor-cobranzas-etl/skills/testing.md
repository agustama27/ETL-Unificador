# Skill: testing

> Load this skill when writing tests or verifying module behaviour in this project.

---

## Current State

**No automated test suite exists.** `pytest 9.0.2` is installed but there are no test files yet.

All verification is currently **manual** — running `main.py` and inspecting output files.

---

## Manual Verification Protocol

This is the required verification approach until automated tests are added.

### Step 1 — Run standalone procesos/ file
Every `procesos/*.py` file has a `if __name__ == "__main__"` block. Run it first:
```bash
python back-base/procesos/base_generator.py
python back-resultados/procesos/retell_manager.py
python back-cargaMasiva/procesos/mapeador.py
```

### Step 2 — Run the full module
```bash
python back-base/main.py
python back-resultados/main.py
python back-cargaMasiva/main.py
```

### Step 3 — Verify outputs

| Module | Expected output | Checks |
|--------|----------------|--------|
| `back-base` | `base-generada/con-filtros/base_bancor_DDMMAAAA.csv` | Row count printed, no UnicodeDecodeError |
| `back-base` | `base-generada/con-filtros/telefonos_x_cliente_DDMMAAAA.csv` | One number per line, no duplicates |
| `back-resultados` | `results/gestiones_bancor_DDMMAAAA.csv` | Exactly 28 columns, no NaN values |
| `back-cargaMasiva` | `output/YYYY-MM-DD_EVOLTIS.xlsx` | Sheet "MODELO envio", exactly 13 columns |
| `back-cargaMasiva` | `output/YYYY-MM-DD_EVOLTIS.csv` | CSV backup exists alongside XLSX |

---

## If Adding Automated Tests (pytest)

### File Layout (when tests are created)
```
soho-bancor-cobranzas-etl/
├── tests/
│   ├── __init__.py
│   ├── back_base/
│   │   ├── test_base_generator.py
│   │   └── test_phone_extractor.py
│   ├── back_resultados/
│   │   ├── test_retell_manager.py
│   │   ├── test_data_merger.py
│   │   └── test_tipif_generator.py
│   ├── back_cargaMasiva/
│   │   ├── test_mapeador.py
│   │   ├── test_validador.py
│   │   └── test_excel_generator.py
│   └── fixtures/
│       ├── sample_bancor.csv     ← small representative sample (4-5 rows)
│       ├── sample_calls.csv      ← 3 call_ids for testing
│       └── sample_roman.csv      ← 3 ROMAN rows
```

### Naming Conventions
- Test files: `test_<module_name>.py`
- Test functions: `test_<function_name>_<scenario>()`
- Fixtures: `sample_<data_name>` — minimal CSV files with 3-5 rows

### Test Function Pattern
```python
import pytest
import pandas as pd
from pathlib import Path
from procesos.base_generator import consolidar_por_cliente

def test_consolidar_por_cliente_suma_montos():
    """Two products for same client should sum MontoAdeudado."""
    df = pd.DataFrame({
        'Cliente_BT': ['CLI001', 'CLI001'],
        'MontoAdeudado': [1000.0, 500.0],
        'OFERTA_Importe': [800.0, 400.0],
        'Dias_Mora': [30, 15],
        'NumeroOperacion': ['OP001', 'OP002'],
        'AgrupadorProducto': ['Préstamo', 'Tarjeta'],
        'CUIL': ['20123456789', '20123456789'],
    })
    resultado = consolidar_por_cliente(df)
    assert len(resultado) == 1
    assert resultado.iloc[0]['MontoAdeudado'] == 1500.0
    assert resultado.iloc[0]['OFERTA_Importe'] == 1200.0
    assert resultado.iloc[0]['Dias_Mora'] == 30

def test_consolidar_por_cliente_concatena_operaciones():
    """NumeroOperacion should be comma-joined unique values."""
    df = pd.DataFrame({
        'Cliente_BT': ['CLI001', 'CLI001'],
        'NumeroOperacion': ['OP001', 'OP002'],
        # ... other required columns
    })
    resultado = consolidar_por_cliente(df)
    assert 'OP001' in resultado.iloc[0]['NumeroOperacion']
    assert 'OP002' in resultado.iloc[0]['NumeroOperacion']
```

### Mocking API Calls
For tests involving Retell.ai API:
```python
from unittest.mock import patch, MagicMock

def test_procesar_llamada_individual_retorna_datos_vacios_en_error():
    """Failed API calls should return empty dicts, not raise exceptions."""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = ConnectionError("Network error")
        resultado = procesar_llamada_individual("call_test123", "fake_key")
        call_id, datos, estado = resultado
        assert call_id == "call_test123"
        assert datos == {'variables_dinamicas': {}, 'postcall': {}}
        assert estado == 'error'
```

### Key Functions to Test (Priority)
When starting to write tests, prioritize:

1. `base_generator.consolidar_por_cliente()` — sum/max/concat logic
2. `base_generator.deduplicar_por_telefono()` — keep highest debt client
3. `mapeador.mapear_registro()` — state mapping correctness
4. `validador.validar_registro()` — CUIT validation, state/sub-state rules
5. `data_merger.merge_datos_inteligente()` — ROMAN priority rules

---

## Running Tests (once created)

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific module's tests
python -m pytest tests/back_cargaMasiva/ -v

# Run with output capture disabled (shows print statements)
python -m pytest tests/ -v -s
```

---

## What NOT to Test

- File I/O in output folders (use tmp_path fixture if needed)
- The Retell.ai API itself (always mock)
- XLSX formatting details (borders, bold) — too brittle
- Encoding chain exhaustion (trust the existing pattern)
