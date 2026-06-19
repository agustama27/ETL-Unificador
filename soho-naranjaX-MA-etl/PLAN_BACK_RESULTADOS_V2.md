# Plan de Desarrollo — back-resultados v2
## Naranja X · Mora Avanzada · ETL Tipificaciones IA → PCT

**Fecha:** 2026-04-28  
**Estado:** Listo para desarrollo  
**Contexto:** Reescritura completa del módulo `back-resultados` para adaptarse al nuevo input
(historial de llamadas de ROMAN) y al nuevo formato de salida PCT de 7 columnas.

---

## 1. Resumen de cambios respecto a v1

| Aspecto | v1 (actual) | v2 (nuevo) |
|---|---|---|
| **Input** | CSV propio con columnas canónicas simples | Export de ROMAN: columnas con prefijos `[Salida]` / `[Entrada]` |
| **Output** | `.txt` sin header, 4 columnas, tab-separated | CSV con header, 7 columnas |
| **Columnas salida** | `id_doc_prefijo`, `codigo_tip`, `codigo_campania`, `id_producto` | `DNI`, `ID_PRODUCTO`, `PRODUCTO`, `FECHA_PROMESA`, `MONTO_PROMESA`, `CALL_REFID`, `OBSERVACIONES` |
| **Tipificaciones** | 3 mapeadas | 12 mapeadas completas |
| **Lógica TC/ND** | Expansión por branch con modo `PURO`/`ECOSISTEMICO` | Eliminada — una fila por llamada |
| **Código campaña** | Parámetro CLI obligatorio | Eliminado |
| **Fecha compromiso** | No existía | Reformateo `DD/MM/YY` → `YYYYMMDD` |
| **Observaciones** | No existía | Truncado a 1500 caracteres |

---

## 2. Arquitectura de archivos

```
back-resultados/
├── back_resultados_etl/
│   ├── __init__.py          (sin cambios)
│   ├── constants.py         ← REESCRIBIR COMPLETO
│   ├── cleaners.py          ← REESCRIBIR (quitar lógica branch, agregar fecha/texto)
│   ├── io.py                ← REESCRIBIR (nuevo parser de columnas ROMAN, nuevo writer)
│   ├── transformers.py      ← REESCRIBIR COMPLETO
│   └── validators.py        ← MODIFICAR (simplificar, quitar assignment_mode)
├── tests/
│   ├── fixtures/
│   │   ├── historial_minimo.csv          ← CREAR (fixture nuevo formato ROMAN)
│   │   ├── historial_missing_cols.csv    ← CREAR
│   │   └── historial_todos_tipos.csv     ← CREAR (una fila por cada tipificación)
│   ├── test_tipificaciones_mapping.py    ← REESCRIBIR
│   └── test_tipificaciones_pct_contract.py ← REESCRIBIR
└── etl_tipificaciones_ia_voz_pct.py      ← MODIFICAR (quitar --campaign_code)
```

**Archivos de core a actualizar:**
```
core/
├── modelos.py               ← MODIFICAR (actualizar ConfigTipificaciones)
└── procesar_tipificaciones.py ← MODIFICAR (adaptar a nueva firma)
```

---

## 3. Especificación de módulos

### 3.1 `constants.py` — reescritura completa

```python
# Columnas requeridas en el input (historial ROMAN)
# Notar: el reader las mapea desde los nombres con prefijo [Salida]/[Entrada]
REQUIRED_SOURCE_COLUMNS = [
    "call_id",
    "id_cliente",           # [Entrada] id_cliente
    "tipificaciones",       # [Salida] Tipificaciones
    "observaciones",        # [Salida] observaciones
    "call_refid",           # Call ID (sin prefijo)
]

# Columnas opcionales — pueden estar vacías según tipificación
OPTIONAL_SOURCE_COLUMNS = [
    "fecha_compromiso_tc",  # [Salida] fecha_compromiso_tc
    "fecha_compromiso_nd",  # [Salida] fecha_compromiso_nd
    "monto_compromiso",     # [Salida] Monto_compromiso  ← PENDIENTE (puede estar vacío)
    "id_nro_producto",      # campo de back-base (JOIN pendiente)
]

# Schema de salida PCT
OUTPUT_COLUMNS = [
    "DNI",
    "ID_PRODUCTO",
    "PRODUCTO",
    "FECHA_PROMESA",
    "MONTO_PROMESA",
    "CALL_REFID",
    "OBSERVACIONES",
]

OUTPUT_FILENAME_PREFIX = "NARANJAX_PCT_"
OUTPUT_FILENAME_EXTENSION = ".csv"
OBSERVACIONES_MAX_CHARS = 1500

# Mapeo completo: Tipificación IA → Código PCT
# Aplica igual para TC y ND (ya no hay bifurcación por branch)
TIPIF_MAP = {
    "PROMESA_DE_PAGO":      "12",
    "DIFICULTAD_DE_PAGO":   "47",
    "SIN_VOLUNTAD_DE_PAGO": "17",
    "NO_RECONOCE_DEUDA":    "15",
    "MANIFIESTA_PAGO":      "37",
    "NOTIFICADO_TITULAR":   "8",
    "NOTIFICADO_FAMILIAR":  "8",
    "CONOCE_TITULAR":       "8",
    "NO_RESPONDE":          "11",
    "CONTESTADOR":          "11",
    "FALLECIDO":            "16",
    "NO_ES_TITULAR":        "61",
}

# Mapeo de columnas ROMAN → nombres canónicos internos
# Clave: nombre canónico | Valor: lista de variantes posibles en el CSV
COLUMN_ALIASES = {
    "call_id":              {"Call ID", "call_id", "CallID"},
    "id_cliente":           {"[Entrada] id_cliente", "id_cliente"},
    "tipificaciones":       {"[Salida] Tipificaciones", "[Salida] tipificaciones", "Tipificaciones"},
    "observaciones":        {"[Salida] observaciones", "[Salida] OBSERVACIONES", "observaciones"},
    "fecha_compromiso_tc":  {"[Salida] fecha_compromiso_tc", "fecha_compromiso_tc"},
    "fecha_compromiso_nd":  {"[Salida] fecha_compromiso_nd", "fecha_compromiso_nd"},
    "monto_compromiso":     {"[Salida] Monto_compromiso", "[Salida] monto_compromiso", "Monto_compromiso"},
    "id_nro_producto":      {"id_nro_producto", "NROPRODUCTO", "nro_producto"},
}
```

---

### 3.2 `cleaners.py` — funciones nuevas/modificadas

**Eliminar:** `normalize_product_branch`, `synthesize_branch_product_id`, `format_document_with_prefix`, `clean_product_id`

**Mantener:** `to_clean_str`, `normalize_upper_snake`, `normalize_result_key`

**Agregar:**

```python
def format_fecha_compromiso(value: str) -> str:
    """
    Convierte fecha de compromiso al formato YYYYMMDD para PCT.
    
    Entrada esperada: 'DD/MM/YY'  (ej: '02/05/26')
    Salida:           'YYYYMMDD'  (ej: '20260502')
    
    Retorna '' si el valor está vacío o no parseable.
    """

def truncate_observaciones(value: str, max_chars: int = OBSERVACIONES_MAX_CHARS) -> str:
    """
    Trunca el texto de observaciones al máximo permitido por PCT.
    No corta palabras a la mitad — corta en el último espacio antes del límite.
    """

def resolve_fecha_promesa(fecha_tc: str, fecha_nd: str) -> str:
    """
    Determina la fecha a usar en FECHA_PROMESA.
    
    Regla:
    - Si solo hay fecha_tc → usar fecha_tc
    - Si solo hay fecha_nd → usar fecha_nd  
    - Si hay ambas → usar fecha_tc (TC tiene prioridad, confirmar con cliente)
    - Si ninguna → retornar ''
    """
```

---

### 3.3 `io.py` — reescritura completa

**`load_input(filepath)`**
- Soportar `.csv` y `.txt` con separadores auto-detectados (igual que v1)
- Normalizar nombres de columnas usando `COLUMN_ALIASES` → mapear a nombres canónicos internos
- Validar que las `REQUIRED_SOURCE_COLUMNS` estén presentes post-normalización
- Columnas opcionales: incluir si existen, rellenar con `''` si no existen
- Retornar DataFrame con columnas canónicas (sin prefijos `[Salida]`/`[Entrada]`)

**`save_output(df, output_dir)`**
- Generar archivo `NARANJAX_PCT_YYYYMMDD.csv`
- Con header (`DNI,ID_PRODUCTO,PRODUCTO,...`)
- Separador: coma
- Encoding: UTF-8 sin BOM
- Fin de línea: `\n`

---

### 3.4 `transformers.py` — reescritura completa

**Eliminar:** `resolve_assignment_mode`, `plan_branches`, `resolve_tipificacion` (con branch)

**Nueva función principal `transform(source_df)`:**

```
Para cada fila del historial:

1. Normalizar tipificación:
   resultado_key = normalize_result_key(row["tipificaciones"])
   
2. Resolver código PCT:
   codigo_pct = TIPIF_MAP.get(resultado_key)
   → Si no hay mapeo: omitir fila, loggear "unmapped_tipificacion"

3. Construir DNI:
   dni = to_clean_str(row["id_cliente"])
   → Si vacío: omitir fila, loggear "missing_dni"

4. Resolver PRODUCTO:
   producto = to_clean_str(row.get("id_nro_producto", ""))
   → Si vacío: usar '' (pendiente JOIN con back-base)

5. Resolver FECHA_PROMESA:
   fecha = resolve_fecha_promesa(
       row.get("fecha_compromiso_tc", ""),
       row.get("fecha_compromiso_nd", "")
   )
   fecha_formateada = format_fecha_compromiso(fecha)

6. Resolver MONTO_PROMESA:
   monto = to_clean_str(row.get("monto_compromiso", ""))
   → Si vacío: usar '' (pendiente campo en agente)

7. Truncar OBSERVACIONES:
   obs = truncate_observaciones(row.get("observaciones", ""))

8. CALL_REFID:
   call_refid = to_clean_str(row["call_id"])

9. Emitir fila de salida
```

**Observabilidad (mantener igual que v1):**
- `total_input_rows`
- `total_output_rows`
- `omitted_rows_total`
- `omitted_by_reason` → razones posibles: `missing_dni`, `unmapped_tipificacion`
- `warning_count`

---

### 3.5 `validators.py` — simplificación

**Eliminar:** `validate_default_assignment_mode`, `validate_effective_campaign_code`, `row_omission_reason` (con branch)

**Mantener/adaptar:**
```python
def validate_required_columns(columns: list[str]) -> None:
    """Igual que v1 pero usando las nuevas REQUIRED_SOURCE_COLUMNS."""

def validate_dni(dni: str) -> bool:
    """Retorna True si el DNI no está vacío después de limpiar."""
```

---

### 3.6 `etl_tipificaciones_ia_voz_pct.py` — CLI simplificado

**Eliminar argumentos:** `--campaign_code`, `--default_assignment_mode`

**Mantener:** `--input`, `--output_dir`, `--log_level`

```
python etl_tipificaciones_ia_voz_pct.py \
    --input historial_llamadas.csv \
    --output_dir ./base-generada
```

---

### 3.7 `core/modelos.py` — actualizar `ConfigTipificaciones`

```python
# Antes:
@dataclass(frozen=True)
class ConfigTipificaciones:
    output_dir: Path
    campaign_code: str
    default_assignment_mode: str

# Después:
@dataclass(frozen=True)
class ConfigTipificaciones:
    output_dir: Path
    # campaign_code y default_assignment_mode eliminados
```

---

## 4. Fixtures de tests

### `historial_minimo.csv`
Una fila con todos los campos requeridos y una tipificación válida.
Usar los datos reales del `historial_llamadas (17).csv` disponible.

### `historial_missing_cols.csv`
CSV sin la columna `[Salida] Tipificaciones` → debe fallar con error claro.

### `historial_todos_tipos.csv`
12 filas, una por cada tipificación del enum. Verificar que todas producen
un código PCT válido y ninguna es omitida por `unmapped_tipificacion`.

---

## 5. Tests a escribir

### `test_tipificaciones_mapping.py` — tests unitarios

| Test | Qué verifica |
|---|---|
| `test_todas_tipificaciones_mapeadas` | Todas las 12 tipificaciones del enum tienen entrada en `TIPIF_MAP` |
| `test_normalize_accentos_y_espacios` | `"  Promesa de pago "` → `"PROMESA_DE_PAGO"` |
| `test_format_fecha_compromiso_valida` | `"02/05/26"` → `"20260502"` |
| `test_format_fecha_compromiso_vacia` | `""` → `""` |
| `test_format_fecha_compromiso_invalida` | fecha malformada → `""` + warning |
| `test_truncate_observaciones_largo` | texto de 2000 chars → truncado en 1500 sin cortar palabra |
| `test_truncate_observaciones_corto` | texto de 100 chars → sin cambios |
| `test_resolve_fecha_solo_tc` | fecha_tc presente, fecha_nd vacío → usa fecha_tc |
| `test_resolve_fecha_solo_nd` | fecha_tc vacío, fecha_nd presente → usa fecha_nd |
| `test_resolve_fecha_ambas` | ambas presentes → usa fecha_tc |
| `test_resolve_fecha_ninguna` | ambas vacías → `""` |
| `test_column_alias_salida_tipificaciones` | `[Salida] Tipificaciones` → mapea a `tipificaciones` |
| `test_column_alias_entrada_id_cliente` | `[Entrada] id_cliente` → mapea a `id_cliente` |

### `test_tipificaciones_pct_contract.py` — tests de integración CLI

| Test | Qué verifica |
|---|---|
| `test_output_tiene_header` | Primera línea del CSV = `DNI,ID_PRODUCTO,...` |
| `test_output_7_columnas` | Cada fila tiene exactamente 7 campos |
| `test_dni_directo_desde_id_cliente` | `[Entrada] id_cliente = DU32204249` → `DNI = DU32204249` |
| `test_call_refid_sin_transformar` | `Call ID` pasa directo a `CALL_REFID` |
| `test_fecha_reformateada` | `02/05/26` en input → `20260502` en output |
| `test_observaciones_truncadas` | texto > 1500 chars → truncado en output |
| `test_tipificacion_sin_mapeo_omitida` | tipificación desconocida → fila omitida + warning |
| `test_dni_vacio_omitido` | `id_cliente` vacío → fila omitida + `missing_dni` en counters |
| `test_missing_required_col_falla_rapido` | CSV sin `Tipificaciones` → exit code != 0 |
| `test_sin_campaign_code_ok` | no requiere `--campaign_code` → no falla |
| `test_output_utf8_sin_bom` | archivo generado sin BOM |
| `test_output_sin_crlf` | solo `\n`, no `\r\n` |
| `test_observability_counters_en_log` | stderr contiene `total_input_rows`, `omitted_by_reason` |

---

## 6. Orden de implementación recomendado

```
Paso 1 — constants.py
  └─ Definir TIPIF_MAP, COLUMN_ALIASES, OUTPUT_COLUMNS, REQUIRED_SOURCE_COLUMNS

Paso 2 — cleaners.py
  └─ Agregar format_fecha_compromiso, truncate_observaciones, resolve_fecha_promesa
  └─ Eliminar funciones de branch

Paso 3 — validators.py
  └─ Simplificar a validate_required_columns + validate_dni

Paso 4 — io.py
  └─ load_input con resolución de alias de columnas ROMAN
  └─ save_output con nuevo formato CSV 7 columnas

Paso 5 — transformers.py
  └─ Reescribir transform() con nueva lógica
  └─ Mantener observabilidad (attrs en DataFrame)

Paso 6 — etl_tipificaciones_ia_voz_pct.py
  └─ Quitar --campaign_code y --default_assignment_mode del CLI

Paso 7 — core/modelos.py + core/procesar_tipificaciones.py
  └─ Actualizar ConfigTipificaciones y la llamada a transform()

Paso 8 — Fixtures
  └─ Crear 3 CSVs de prueba

Paso 9 — Tests unitarios (test_tipificaciones_mapping.py)

Paso 10 — Tests de integración (test_tipificaciones_pct_contract.py)
```

---

## 7. Pendientes documentados (no bloquean el desarrollo)

Estos dos ítems pueden implementarse con campos vacíos/stub por ahora
y completarse cuando estén resueltos del lado del cliente:

| Pendiente | Impacto | Solución temporal |
|---|---|---|
| `MONTO_PROMESA` — el agente no captura el monto como campo estructurado | `MONTO_PROMESA` siempre vacío en Promesa de pago | Emitir `''`, agregar campo al agente cuando el cliente lo confirme |
| `PRODUCTO` — el número de producto no está en el historial de ROMAN | `PRODUCTO` siempre vacío | Emitir `''`, implementar JOIN con `NARANJAX_MA_ROMAN_YYYYMMDD.csv` cuando esté diseñado |

---

## 8. Contrato de salida esperado

Ejemplo de fila generada a partir del `historial_llamadas (17).csv` de prueba:

```
DNI,ID_PRODUCTO,PRODUCTO,FECHA_PROMESA,MONTO_PROMESA,CALL_REFID,OBSERVACIONES
DU32204249,12,,20260502,,call_108c246ea49501d60a04a6ff9e9,Se gestionaron ambos productos (TC y ND)...
```

Cuando los pendientes estén resueltos:

```
DNI,ID_PRODUCTO,PRODUCTO,FECHA_PROMESA,MONTO_PROMESA,CALL_REFID,OBSERVACIONES
DU32204249,12,PRE32204249,20260502,180592.17,call_108c246ea49501d60a04a6ff9e9,Se gestionaron...
```
