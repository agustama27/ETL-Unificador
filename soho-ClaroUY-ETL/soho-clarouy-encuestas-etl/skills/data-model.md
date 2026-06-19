# Skill: data-model

> Load this skill when working with CSV/DataFrame column contracts, field types, encoding, or serialisation in this project.

---

## Column Contracts

These are the fixed, authoritative column lists for each module's output. Do not add, remove, or rename columns without updating the corresponding contract here and in the relevant `AGENTS.md`.

### Module 1 — `back-base` output: `base_clarouy_DDMMAAAA.csv`

**Base consolidada (un registro por cliente):**
```
customer_id, msisdn, nombre_cliente, <otros campos de cliente>
```

**Archivo de teléfonos: `telefonos_x_cliente_DDMMAAAA.csv`**
- Una línea por teléfono válido
- Formato: `5989XXXXXXXX` (sin espacios, sin guiones)
- Sin header

### Module 2 — `back-resultados` output: `encuestas_clarouy_DDMMAAAA.csv`

**Fixed 26 columns (order matters):**
```
call_id, msisdn, customer_id, nombre_cliente, campaign_id,
encuesta_completada, motivo_cierre, fecha_hora, global_experience,
descripcion_inicial, comentario_mejora, sin_comentarios, detalle_experiencia,
tipo_experiencia, categoria, subcategoria, es_cobertura,
texto_domicilio_cliente, domicilio_validado, domicilio_normalizado,
domicilio_intentos, inconveniente_continua, pudiste_solucionarlo,
derivar_a_asesor, skill_destino, id_caso_reclamo
```

---

## Field Types and Formats

### Numeric fields

| Field | Format | Notes |
|-------|--------|-------|
| `msisdn` | String: `5989XXXXXXXX` | Uruguay phone format, 12 digits including country code |
| `customer_id` | String: `CLAROUY-XXXXXXX` | Internal client ID |
| `domicilio_intentos` | Integer | Number of address capture attempts |
| `skill_destino` | Integer | Skill ID for call derivation |

### Date fields

| Field | Format |
|-------|--------|
| `fecha_hora` | `DD/MM/YYYY HH:MM` or empty |
| Output file date suffix | `DDMMAAAA` (e.g., `15012026`) |

---

## ROMAN Merge Rules

When `USE_ROMAN=true`, ROMAN data takes priority for typification fields:

### Fields ROMAN can overwrite (`CAMPOS_SOBRESCRIBIBLES`):
- `motivo_cierre`, `global_experience`, `tipo_experiencia`, `categoria`, `subcategoria` — tipification
- `descripcion_inicial`, `comentario_mejora`, `detalle_experiencia` — experience comments
- `texto_domicilio_cliente`, `domicilio_validado`, `domicilio_normalizado`, `domicilio_intentos` — address
- `encuesta_completada`, `fecha_hora`, `sin_comentarios`, `es_cobertura` — closure
- `inconveniente_continua`, `pudiste_solucionarlo`, `derivar_a_asesor`, `skill_destino`, `id_caso_reclamo`

### Fields ROMAN can NEVER modify (`CAMPOS_PROTEGIDOS`):
- `call_id`, `msisdn`, `customer_id`, `campaign_id`

### Overwrite condition:
A ROMAN value overwrites a Retell value only if the ROMAN value is **not** in `VALORES_VACIOS`:
```python
VALORES_VACIOS = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-', 'nan', 'NaN', 'None']
```

---

## Enums Valid for Survey Fields

### global_experience
`MUY_BUENA`, `PODRIA_MEJORAR`, `TUVO_INCONVENIENTES`, `NO_ENTENDIA`

### motivo_cierre
`OK_RECHAZO_CLIENTE`, `DERIVADO_ASESOR`, `FALLIDA_NULL_REC`

### tipo_experiencia
`MEJORA`, `INCONVENIENTE`

### categoria
`COBERTURA_SERVICIO`, `PORTABILIDAD`, `FACTURACION`, `ACTIVACION`, `ATENCION_CLIENTES`, `OTROS`

---

## CSV Encoding Protocol

### Reading (input files):
Try encodings in this order:
```python
['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
```
Last resort: `encoding='utf-8', errors='replace'`

### Writing (all outputs):
Always `encoding='utf-8'`, `sep=';'`, `decimal=','`

### Separator detection:
Try `,` first, if DataFrame has 1 column, retry with `;`.

---

## Validation Rules

### msisdn (phone number)
- Remove all non-digits: `re.sub(r'\D', '', msisdn)`
- Format expected: 12 digits starting with `5989`

### customer_id
- Format expected: `CLAROUY-XXXXXXX`
- Validate prefix and numeric part

### Boolean fields
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

### Empty values
- In DataFrames: `''` (empty string), never `NaN`
- In JSON API payload: treat `None`, `''`, `'null'`, `'NULL'`, `'n/a'` as missing
