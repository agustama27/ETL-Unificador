# Skill: data-model

> Load this skill when working with CSV/DataFrame column contracts, field types, encoding, or serialisation in this project.

---

## Column Contracts

These are the fixed, authoritative column lists for each module's output. Do not add, remove, or rename columns without updating the corresponding contract here and in the relevant `AGENTS.md`.

### Module 1 — `back-base` output: `base_bancor_DDMMAAAA.csv`

**Filtered base (con-filtros) — 20 columns:**
```
Cliente_BT, CUIL, NumeroDocumento, ClienteNombre, NumeroTelefono,
NumeroCelular, NumeroTrabajo, Mail, Nro Cuenta, AgrupadorProducto,
ModuloCodigo, NumeroOperacion, Dias_Mora, MontoAdeudado, OFERTA_Importe,
SaldoCapital, Sucursal_Cuenta, IVAInteresAdeudado, InteresAdeudado, Cuenta
```

**Complete base (sin-filtros) — 22 columns:** same as above plus:
```
Estado Cuenta, Tasa_40
```

**Consolidation rules:**

| Field | Rule |
|-------|------|
| `MontoAdeudado` | `sum` |
| `OFERTA_Importe` | `sum` |
| `Dias_Mora` | `max` |
| `NumeroOperacion` | `','.join(unique values)` |
| `AgrupadorProducto` | `','.join(unique values)` |
| All other fields | `first` |

### Module 2 — `back-resultados` output: `gestiones_bancor_DDMMAAAA.csv`

**Fixed 28 columns (order matters):**
```
call_id, AgrupadorProducto, CUIL, ClienteNombre, Cliente_BT, Cuenta,
Dias_Mora, IVAInteresAdeudado, InteresAdeudado, Mail, MontoAdeudado,
NumeroOperacion, OFERTA_Importe, SaldoCapital, Sucursal_Cuenta,
fecha_hoy, fecha_limite_sistema, fecha_manana, hora_actual, user_number,
Comentarios, DESCRIPCION, ESTADO, Email_valido, Fecha_compromiso,
Monto_compromiso, SUBESTADO, compromiso_de_pago_logrado
```

**Origin of each field:**
- `call_id` → from calls/*.csv input
- `AgrupadorProducto` → `retell_llm_dynamic_variables`
- `CUIL` → `retell_llm_dynamic_variables`
- `ClienteNombre` → `retell_llm_dynamic_variables`
- `ESTADO`, `SUBESTADO`, `DESCRIPCION` → `custom_analysis_data` (postcall)
- `compromiso_de_pago_logrado`, `Monto_compromiso`, `Fecha_compromiso` → dynamic variables
- `fecha_hoy`, `fecha_limite_sistema`, `fecha_manana`, `hora_actual` → dynamic variables (injected before call)

### Module 3 — `back-cargaMasiva` output: CRM format

**Exact 13 columns (order is critical — CRM import requires this):**
```
Clase de Operación, Estado, Sub- Estado, CUIT, Cuenta,
Desc. Acuerdo Comercial, Acuerdo Comercial, Responsable,
Descripción, Persona de Contacto, Juzgado, Garante, Notas
```

**Note**: `"Sub- Estado"` has a space before "Estado". This is intentional — matches Bancor's CRM template exactly.

---

## Field Types and Formats

### Numeric fields

| Field | Format | Notes |
|-------|--------|-------|
| `MontoAdeudado` | European: `647114,99` | Comma as decimal separator |
| `OFERTA_Importe` | European: `15000,00` | Comma as decimal separator |
| `CUIT` | 11-digit integer string: `20123456789` | No hyphens, no spaces |
| `Responsable` | 10-digit code: `5000000786` | From `RESPONSABLES` dict |
| `NumeroCelular` | Numeric string: `3511234567` | No hyphens, no spaces |
| `Dias_Mora` | Integer | Max across products |

### Date fields

| Field | Format |
|-------|--------|
| `fecha_hoy` | `DD/MM/YYYY` |
| `fecha_limite_sistema` | `DD/MM/YYYY` |
| `fecha_manana` | `DD/MM/YYYY` |
| `Fecha_compromiso` | `DD/MM/YYYY` or empty |
| Output file date suffix | `DDMMAAAA` (e.g., `15012026`) |
| Output file name prefix | `YYYY-MM-DD` (e.g., `2026-01-15`) |

---

## ROMAN Merge Rules

When `USE_ROMAN=true`, ROMAN data takes priority for typification fields:

### Fields ROMAN can overwrite (`CAMPOS_SOBRESCRIBIBLES`):
- `ESTADO`, `SUBESTADO`, `DESCRIPCION`, `OBSERVACIONES` — typification
- `Fecha_compromiso`, `Monto_compromiso`, `compromiso_de_pago_logrado` — payment commitment
- `Email_valido` — validation

### Fields ROMAN can NEVER modify (`CAMPOS_PROTEGIDOS`):
- `call_id`, `AgrupadorProducto`, `CUIL`, `ClienteNombre`, `Cliente_BT`, `Cuenta`, `user_number`

### Overwrite condition:
A ROMAN value overwrites a Retell value only if the ROMAN value is **not** in `VALORES_VACIOS`:
```python
VALORES_VACIOS = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-']
```

---

## State/Sub-state Catalog

### States without sub-state (`ESTADOS_SIN_SUBESTADO`):
`E0004`, `E0005`, `E0006`, `E0014`, `E0020`, `E0021`, `E0022`, `E0023`, `E0024`, `E0025`, `E0026`, `E0027`, `E0028`, `E0029`, `E0030`, `E0003`

### States with mandatory sub-state (`ESTADOS_CON_SUBESTADO`):

| State code | State name | Valid sub-states |
|---|---|---|
| `E0012` | Promesa de Pago Pactada | `E001` (Parcial), `E002` (Parcial Acordado), `E003` (Total) |
| `E0002` | Gestión de Refinanciación | `E001` (En curso), `E002` (Enviada a Bancor), `E003` (Enviada a liquidar) |

---

## CSV Encoding Protocol

### Reading (input files from Bancor or ROMAN):
Try encodings in this order:
```python
['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']
```
Last resort: `encoding='latin-1', errors='replace'`

### Writing (all outputs):
Always `encoding='utf-8'`, `sep=';'`, `decimal=','`

### Retell.ai API input CSVs:
Try `utf-8` first, then the encoding chain above.

---

## Validation Rules

### CUIT
```python
# Valid CUIT: exactly 11 numeric digits
import re
def cuit_valido(cuit: str) -> bool:
    cuit_limpio = re.sub(r'[^0-9]', '', str(cuit))
    return len(cuit_limpio) == 11
```

### Descripción (CRM field)
- Max 100 characters
- Truncate at 100 if longer: `descripcion[:100]`

### Phone numbers
- Remove hyphens: `telefono.replace('-', '')`
- Replace invalid value `3519999999` with empty string

### Boolean fields (`compromiso_de_pago_logrado`)
Normalize with:
```python
def normalizar_booleano(valor) -> bool:
    if isinstance(valor, bool): return valor
    if isinstance(valor, str):
        return valor.lower().strip() in ['true', 'sí', 'si', 'yes', '1']
    if isinstance(valor, (int, float)): return bool(valor)
    return False
```

---

## Serialisation Rules

### DataFrame → CSV
```python
df.to_csv(path, sep=';', decimal=',', encoding='utf-8', index=False, na_rep='')
```

### DataFrame → XLSX (CRM format)
- Use `openpyxl` directly (not `df.to_excel()`) to control formatting
- Sheet name: `"MODELO envio"` (exact, required by Bancor CRM)
- Header row: bold
- All cells: thin borders
- Freeze top row: `ws.freeze_panes = "A2"`

### Empty values
- In DataFrames: `''` (empty string), never `NaN`
- In XLSX cells: empty string
- In JSON API payload: treat `None`, `''`, `'null'`, `'NULL'`, `'n/a'` as missing
