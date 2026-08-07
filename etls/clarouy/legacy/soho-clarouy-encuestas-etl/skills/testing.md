# Skill: testing

> Load this skill when writing tests or verifying module behavior.

---

## Current Testing State

- No automated test suite exists
- `pytest` is installed but unused
- Manual verification is the current approach

---

## Manual Verification Protocol

### Step 1: Run standalone procesos file
```bash
python back-<module>/procesos/<file>.py
```
Verify no exceptions, check console output.

### Step 2: Run full module
```bash
python back-<module>/main.py
```

### Step 3: Verify outputs
- Output files exist
- Expected columns present
- Row counts reasonable
- No empty required fields

---

## Future pytest Layout (if implemented)

```
tests/
├── __init__.py
├── back-base/
│   ├── __init__.py
│   ├── test_base_generator.py
│   └── test_phone_extractor.py
└── back-resultados/
    ├── __init__.py
    ├── test_retell_manager.py
    ├── test_tipif_generator.py
    ├── test_roman_manager.py
    └── test_data_merger.py
```

### Test file naming
- `test_<module_name>.py`
- Test functions: `test_<what_is_tested>()`

### Test function pattern
```python
def test_funcion_esperada():
    # Arrange
    input_data = ...
    
    # Act
    result = funcion(input_data)
    
    # Assert
    assert result == expected
```

---

## Functions to Prioritize for Testing

### back-base
- `consolidar_por_cliente()` — aggregation logic
- `deduplicar_por_telefonos()` — deduplication logic
- `leer_csv_con_codificacion()` — encoding detection

### back-resultados
- `buscar_campo_recursivo()` — JSON navigation
- `merge_datos_inteligente()` — ROMAN merge logic
- `normalizar_booleano()` — type conversion

---

## What NOT to Test

- File I/O (use integration tests manually)
- Retell API calls directly (mock them)
- XLSX formatting (manual verification)
- Encoding chain (already tested manually)

---

## Mocking Example

```python
from unittest.mock import patch, Mock

@patch('requests.Session.get')
def test_obtener_datos_retell(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'call_id': 'call_123',
        'custom_analysis_data': {...}
    }
    mock_get.return_value = mock_response
    
    result = obtener_datos_llamada_retell('call_123', 'fake_key')
    
    assert result['call_id'] == 'call_123'
```
