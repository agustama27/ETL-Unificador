# Plan de Desarrollo — SOHO_Chat-NARANJAX_MA

**Proyecto:** ETL Chat Naranja X Mora Avanzada (RM)  
**Repo:** `SOHO_Chat-NARANJAX_MA` (Bitbucket · workspace evoltis)  
**Objetivo:** Adaptar el ETL de voz para producir el archivo `NARANJAX_MA_CHAT_ROMAN_YYMMDD`, optimizado para lookup por DNI desde el agente de chat en Retell.

---

## 1. Contexto y diferencias respecto al ETL de voz

El ETL de voz (`SOHO-NARANJAX_MA-ETL`) produce un archivo **ROMAN con una fila por producto** (`nroproducto`). El agente de voz hace lookup por número de teléfono en el inbound.

El agente de chat opera de manera diferente:

| Dimensión | ETL voz | ETL chat |
|---|---|---|
| Granularidad del output | 1 fila por `nroproducto` | 1 fila por `dni` (DU completo) |
| Lookup | Por número de teléfono | Por DNI (ingresado por el usuario) |
| Datos de deuda | `total_vencida` del estado | Jerarquía: planes > pagos > API |
| Planes | Columnas `plan_1..7` planas | Igual + flag `tiene_planes` |
| Horario | No aplica | 9hs–20hs AR (evaluado en N8N) |

El repo `SOHO_Chat-NARANJAX_MA` ya es una copia del de voz. **No se modifica la salida ROMAN existente.** Se agrega una nueva ruta de output de tipo CHAT en paralelo.

---

## 2. Resumen de cambios por archivo

| Archivo | Tipo de cambio | Prioridad |
|---|---|---|
| `back-base/back_base_etl/constants.py` | Agregar constantes CHAT | Alta |
| `back-base/back_base_etl/transformers.py` | Agregar `build_chat_output()` | Alta |
| `back-base/back_base_etl/update_estado.py` | Agregar columna `fuente_deuda` | Alta |
| `core/modelos.py` | Agregar `output_chat` a `ResultadoDia` | Media |
| `core/procesar_dia.py` | Agregar rama de output CHAT | Alta |
| `back-base/ejecutar_dia.py` | Agregar arg `--chat` y `--planes_disponibles` | Media |

---

## 3. Cambios detallados por archivo

### 3.1 `back-base/back_base_etl/constants.py`

Agregar al final del archivo, debajo de `OUTPUT_FILENAME_E1KIA`:

```python
# ── CHAT output ────────────────────────────────────────────────────────────────

OUTPUT_FILENAME_CHAT_ROMAN = "NARANJAX_MA_CHAT_ROMAN_"

# Columnas base del output CHAT (una fila por DNI/DU consolidado).
# Las columnas dinámicas plan_1..N se agregan igual que en ROMAN.
OUTPUT_COLUMNS_CHAT = [
    "id_dni",
    "nombre_cliente",
    "cantidad_productos",
    "productos_json",        # JSON serializado: [{"prod": "...", "plan": "Con|Sin"}]
    "monto_total_vencido",   # según jerarquía: planes > pagos > API (0 si api)
    "monto_deuda_tc",        # suma de monto_deuda_total_tc_ars del DU
    "monto_deuda_nd",        # suma de monto_deuda_total_nd_ars del DU
    "dias_mora",             # extraído del cajón del primer producto
    "tipo_cajon",            # cajón del primer producto
    "tipo_ecosistema",       # ecosistema del primer producto
    "estado_prelegal",       # "Sí" si estrategia contiene PRELEGAL; "No" en caso contrario
    "fuente_deuda",          # "planes" | "pagos" | "api"
    "tiene_planes",          # "True" | "False" (base del día; horario evaluado en N8N)
    "fecha_limite_sistema",  # fecha de ejecución ISO
]
```

> **Nota:** `monto_total_vencido = 0` cuando `fuente_deuda = "api"`. N8N consulta la API en runtime y sobreescribe ese valor antes de devolver las variables al agente.

---

### 3.2 `back-base/back_base_etl/update_estado.py`

Agregar la columna `fuente_deuda` al estado para que `build_chat_output()` pueda derivarla correctamente.

**Ubicación:** en la función `update_estado()`, justo antes del `return estado`.

```python
# ── Derivar fuente_deuda para el output CHAT ───────────────────────────────────
# "planes" si el producto recibió deuda desde el diario de planes
# "pagos"  si el producto recibió recupero/importe desde el diario de pagos
# "api"    en cualquier otro caso (N8N lo resuelve en runtime)

if "fuente_deuda" not in estado.columns:
    estado["fuente_deuda"] = "api"

# Marca como "planes" si hay columnas de plan con datos
plan_cols_present = [c for c in estado.columns if c.startswith("plan_") and c.endswith("_cuotas")]
if plan_cols_present:
    tiene_plan_mask = (
        estado[plan_cols_present]
        .fillna("")
        .astype(str)
        .apply(lambda s: s.str.strip())
        .ne("")
        .any(axis=1)
    )
    estado.loc[tiene_plan_mask, "fuente_deuda"] = "planes"

# Marca como "pagos" si tiene recupero o importe (solo si no es ya "planes")
recupero_mask = (
    estado["recupero"].fillna("").astype(str).str.strip().ne("")
)
estado.loc[recupero_mask & (estado["fuente_deuda"] == "api"), "fuente_deuda"] = "pagos"
```

---

### 3.3 `back-base/back_base_etl/transformers.py`

Agregar la función `build_chat_output()` al final del archivo, luego de `build_e1kia_output()`.

```python
import json as _json  # agregar al bloque de imports al principio del módulo


def build_chat_output(
    df_roman: pd.DataFrame,
    plan_columns: list[str] | None = None,
    planes_disponibles_hoy: bool = True,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Consolidate ROMAN rows (1 per product) into CHAT rows (1 per DNI/DU).

    Business rules applied here:
    - cantidad_productos: count of products per DNI.
    - monto_total_vencido: sum of monto_deuda_total_ars. Set to 0 when
      fuente_deuda='api' so N8N fills it at runtime.
    - tiene_planes: True only when planes_disponibles_hoy AND at least one
      product has plan data. Horario check (9–20hs AR) is N8N's responsibility.
    - productos_json: serialized list of {prod, plan} per product.
    - estado_prelegal: 'Sí' if any product's tipo_estrategia contains 'PRELEGAL'.
    """
    active_logger = logger or logging.getLogger("etl_naranjax")
    plan_columns = plan_columns or []

    if df_roman.empty:
        active_logger.warning("build_chat_output: empty ROMAN input, returning empty chat dataframe")
        from .constants import OUTPUT_COLUMNS_CHAT
        chat_cols = OUTPUT_COLUMNS_CHAT + plan_columns
        return pd.DataFrame(columns=pd.Index(chat_cols))

    def _is_null_scalar(v) -> bool:
        r = pd.isna(v)
        return bool(r) if isinstance(r, bool) else False

    def _str(v) -> str:
        return "" if _is_null_scalar(v) else str(v).strip()

    def _float(v) -> float:
        try:
            return float(str(v).replace(",", ".").replace("$", "").strip())
        except (ValueError, TypeError):
            return 0.0

    records: list[dict] = []

    # Group by DNI
    group_col = "id_nro_dni" if "id_nro_dni" in df_roman.columns else "id_dni"
    for dni, group in df_roman.groupby(group_col, sort=False):
        first = group.iloc[0]

        # --- cantidad_productos y productos_json ---
        cantidad = len(group)
        productos_list = []
        for _, row in group.iterrows():
            prod = _str(row.get("id_nro_producto") or row.get("id_producto", ""))
            plan_label = _str(row.get("tipo_marca_plan", "Sin"))
            if prod:
                productos_list.append({"prod": prod, "plan": plan_label})
        productos_json = _json.dumps(productos_list, ensure_ascii=False)

        # --- montos (suma del DU) ---
        monto_tc   = sum(_float(r.get("monto_deuda_total_tc_ars") or r.get("monto_deuda_tc", 0)) for _, r in group.iterrows())
        monto_nd   = sum(_float(r.get("monto_deuda_total_nd_ars") or r.get("monto_deuda_nd", 0)) for _, r in group.iterrows())
        monto_total = sum(_float(r.get("monto_deuda_total_ars")   or r.get("monto_deuda_total", 0)) for _, r in group.iterrows())

        # --- fuente_deuda a nivel DU ---
        fuentes = group["fuente_deuda"].fillna("api").astype(str).str.strip().tolist() if "fuente_deuda" in group.columns else ["api"]
        if "planes" in fuentes:
            fuente_deuda = "planes"
        elif "pagos" in fuentes:
            fuente_deuda = "pagos"
        else:
            fuente_deuda = "api"

        # Cuando la fuente es API, N8N obtiene el monto en runtime
        monto_vencido_output = 0.0 if fuente_deuda == "api" else monto_total

        # --- tiene_planes ---
        tiene_plan_raw = any(
            str(first.get(pc, "")).strip() not in ("", "nan")
            for pc in plan_columns
            if pc.startswith("plan_") and pc.endswith("_cuotas")
        )
        tiene_planes = planes_disponibles_hoy and tiene_plan_raw

        # --- estado_prelegal ---
        estrategias = group["tipo_estrategia"].fillna("").astype(str).str.upper().tolist() if "tipo_estrategia" in group.columns else []
        estado_prelegal = "Sí" if any("PRELEGAL" in e for e in estrategias) else "No"

        # --- dias_mora desde cajón ---
        from .cleaners import extract_dias_mora
        dias_mora = extract_dias_mora(first.get("tipo_cajon") or first.get("cajon", ""))

        record: dict = {
            "id_dni":              _str(dni),
            "nombre_cliente":      _str(first.get("customer_name") or first.get("nombre_cliente", "")),
            "cantidad_productos":  str(cantidad),
            "productos_json":      productos_json,
            "monto_total_vencido": str(round(monto_vencido_output, 2)),
            "monto_deuda_tc":      str(round(monto_tc, 2)),
            "monto_deuda_nd":      str(round(monto_nd, 2)),
            "dias_mora":           str(dias_mora),
            "tipo_cajon":          _str(first.get("tipo_cajon") or first.get("cajon", "")),
            "tipo_ecosistema":     _str(first.get("tipo_ecosistema") or first.get("ecosistema", "")),
            "estado_prelegal":     estado_prelegal,
            "fuente_deuda":        fuente_deuda,
            "tiene_planes":        str(tiene_planes),
            "fecha_limite_sistema": _str(first.get("fecha_limite_sistema", "")),
        }

        # Columnas dinámicas de planes (del primer producto del DU)
        for pc in plan_columns:
            record[pc] = _str(first.get(pc, ""))

        records.append(record)

    from .constants import OUTPUT_COLUMNS_CHAT
    chat_cols = OUTPUT_COLUMNS_CHAT + plan_columns
    out = pd.DataFrame(records, columns=pd.Index(chat_cols))
    active_logger.info("build_chat_output: %s DU rows from %s product rows", len(out), len(df_roman))
    return out
```

---

### 3.4 `core/modelos.py`

Agregar el campo `output_chat` a `ResultadoDia`:

```python
@dataclass(frozen=True)
class ResultadoDia:
    # ... campos existentes ...
    output_chat: Path | None = None    # ← NUEVO: path del archivo CHAT ROMAN
```

Y agregar el flag en `ArchivosDia`:

```python
@dataclass(frozen=True)
class ArchivosDia:
    # ... campos existentes ...
    generar_chat: bool = False           # ← NUEVO: activar output CHAT
    planes_disponibles_hoy: bool = True  # ← NUEVO: si llegó la base de planes del día
```

---

### 3.5 `core/procesar_dia.py`

**Imports adicionales:** agregar junto a los imports de `back_base_etl`:

```python
from back_base_etl.constants import OUTPUT_COLUMNS_CHAT, OUTPUT_FILENAME_CHAT_ROMAN
from back_base_etl.transformers import build_chat_output
```

**En la función `procesar_dia()`**, luego de la línea que genera `output_df = sort_roman_rows(output_df)` y antes de `save_output(...)`:

```python
# ── Output CHAT (opcional) ────────────────────────────────────────────────────
output_chat_path: Path | None = None
if archivos.generar_chat:
    LOGGER.info("Generating CHAT output planes_disponibles_hoy=%s", archivos.planes_disponibles_hoy)
    chat_df = build_chat_output(
        df_roman=output_df,
        plan_columns=plan_columns,
        planes_disponibles_hoy=archivos.planes_disponibles_hoy,
        logger=LOGGER,
    )
    output_chat_path = Path(
        save_output(
            chat_df,
            str(config.output_dir),
            prefix=OUTPUT_FILENAME_CHAT_ROMAN,
            date_format="%y%m%d",
        )
    )
    LOGGER.info("CHAT output saved rows=%s path=%s", len(chat_df), output_chat_path)
```

**En el `return ResultadoDia(...)`:**

```python
return ResultadoDia(
    # ... campos existentes ...
    output_chat=output_chat_path,    # ← NUEVO
)
```

---

### 3.6 `back-base/ejecutar_dia.py`

Agregar argumentos CLI al `argparse`:

```python
parser.add_argument(
    "--chat",
    action="store_true",
    default=False,
    help="Generar también el archivo CHAT ROMAN (1 fila por DNI)"
)
parser.add_argument(
    "--sin_planes_hoy",
    action="store_true",
    default=False,
    help="Indica que la base de planes del día NO llegó (tiene_planes=False para todos)"
)
```

Y pasarlos al dataclass:

```python
archivos = ArchivosDia(
    # ... campos existentes ...
    generar_chat=args.chat,
    planes_disponibles_hoy=not args.sin_planes_hoy,
)
```

---

## 4. Schema del archivo `NARANJAX_MA_CHAT_ROMAN_YYMMDD`

Formato de salida: **CSV con separador `,`**, encoding UTF-8, una fila por DNI/DU.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `id_dni` | string | DNI del titular (clave de lookup) | `30123456` |
| `nombre_cliente` | string | Nombre y apellido | `JUAN GOMEZ` |
| `cantidad_productos` | string | Productos en mora del DU | `2` |
| `productos_json` | string (JSON) | Lista de productos con estado de plan | `[{"prod":"TC-001","plan":"Con"}]` |
| `monto_total_vencido` | string | Suma de deuda vencida del DU | `128450.0` (o `0` si fuente=api) |
| `monto_deuda_tc` | string | Deuda TC del DU | `95000.0` |
| `monto_deuda_nd` | string | Deuda ND del DU | `33450.0` |
| `dias_mora` | string | Días de mora (del cajón) | `90` |
| `tipo_cajon` | string | Cajón del primer producto | `M90` |
| `tipo_ecosistema` | string | Ecosistema | `PURO` |
| `estado_prelegal` | string | Si la estrategia es PRELEGAL | `No` |
| `fuente_deuda` | string | Fuente del monto vencido | `planes` / `pagos` / `api` |
| `tiene_planes` | string | Si hay planes disponibles este día | `True` / `False` |
| `fecha_limite_sistema` | string | Fecha de generación ISO | `2026-05-26` |
| `plan_1_cuotas` | string | Primera opción: cantidad de cuotas | `3` |
| `plan_1_entrega` | string | Primera opción: importe de entrega | `15000.0` |
| `plan_1_cuota_mensual` | string | Primera opción: importe por cuota | `38150.0` |
| ... | ... | (hasta plan_7) | ... |

---

## 5. Lógicas de negocio

### 5.1 Consolidación por DNI (DU)

El ROMAN de voz tiene N filas por DNI (una por producto). El CHAT necesita **1 fila por DNI**.

```
DNI 30123456:
  producto TC-001  monto_vencido=95000  plan_1_cuotas=3  fuente_deuda=planes
  producto ND-002  monto_vencido=33450  plan_1_cuotas=""  fuente_deuda=api
```

→ El ETL chat consolida:
```
DNI 30123456:
  cantidad_productos=2
  monto_total_vencido=128450  (suma, fuente=planes porque al menos un producto la tiene)
  tiene_planes=True
  plan_1_cuotas=3  (del primer producto con plan)
  productos_json='[{"prod":"TC-001","plan":"Con"},{"prod":"ND-002","plan":"Sin"}]'
```

### 5.2 Jerarquía de fuente de deuda

Aplicada a nivel DU (no por producto individual):

```
si algún producto del DU tiene datos de planes diarios (plan_1_cuotas != ""):
    fuente_deuda = "planes"
    monto_total_vencido = suma(total_vencida) del estado (ya actualizado por update_estado)

sino si algún producto del DU tiene recupero != "":
    fuente_deuda = "pagos"
    monto_total_vencido = suma(total_vencida) del estado (ya descontado importe_pago)

sino:
    fuente_deuda = "api"
    monto_total_vencido = 0  ← N8N llama a la API en runtime para obtener el valor real
```

### 5.3 Flag `tiene_planes`

Calculado en el ETL con la lógica de días del mes. Evaluado definitivamente en N8N:

```
ETL calcula:
  tiene_planes = planes_disponibles_hoy AND (plan_1_cuotas != "")

N8N valida adicionalmente:
  tiene_planes_final = tiene_planes AND (hora_AR >= 9 AND hora_AR < 20)
```

**Regla crítica:** si `--sin_planes_hoy` → `tiene_planes = False` para TODOS los clientes.

---

## 6. Plan de testing

### Unit tests (carpeta `back-base/tests/`)

| Test | Descripción |
|---|---|
| `test_build_chat_output_consolidacion` | Verifica que 3 filas de producto con el mismo DNI se consolidan en 1 |
| `test_build_chat_output_fuente_planes` | DNI con plan_1_cuotas populated → fuente_deuda=planes |
| `test_build_chat_output_fuente_pagos` | DNI con recupero=SI → fuente_deuda=pagos |
| `test_build_chat_output_fuente_api` | DNI sin planes ni pagos → fuente_deuda=api, monto=0 |
| `test_build_chat_output_sin_planes_hoy` | planes_disponibles_hoy=False → tiene_planes=False para todos |
| `test_build_chat_output_prelegal` | tipo_estrategia con PRELEGAL → estado_prelegal=Sí |
| `test_fuente_deuda_en_update_estado` | Verifica que fuente_deuda se asigna correctamente en update_estado |

### Integration test manual (con datos reales)

```bash
# Primer run: genera ROMAN + CHAT
cd back-base
python ejecutar_dia.py \
  --input "archivo-recibido/base_mensual.xlsx" \
  --planes "diarios/entrada/planes_260526.xlsx" \
  --pagos "diarios/entrada/pagos_260526.csv" \
  --chat \
  --fecha 20260526

# Verificar output
ls base-generada/NARANJAX_MA_CHAT_ROMAN_*.csv

# Run sin planes del día
python ejecutar_dia.py \
  --input "archivo-recibido/base_mensual.xlsx" \
  --chat \
  --sin_planes_hoy \
  --fecha 20260526
```

### Verificaciones post-ETL

```python
import pandas as pd

df = pd.read_csv("base-generada/NARANJAX_MA_CHAT_ROMAN_260526.csv")

# 1. Unicidad de DNI
assert df["id_dni"].nunique() == len(df), "Hay DNIs duplicados en el chat output"

# 2. Distribución de fuentes
print(df["fuente_deuda"].value_counts())

# 3. monto=0 solo cuando fuente=api
assert (df[df["fuente_deuda"] != "api"]["monto_total_vencido"].astype(float) > 0).all(), \
    "Hay montos en 0 en filas que no son fuente=api"

# 4. tiene_planes coherente con plan_1_cuotas
sin_plan_pero_true = df[(df["tiene_planes"] == "True") & (df["plan_1_cuotas"] == "")]
assert len(sin_plan_pero_true) == 0, "tiene_planes=True pero sin datos de plan"
```

---

## 7. Orden de implementación recomendado

```
Paso 1 │ constants.py    │ Agregar OUTPUT_COLUMNS_CHAT y OUTPUT_FILENAME_CHAT_ROMAN
Paso 2 │ update_estado.py│ Agregar columna fuente_deuda con derivación por row
Paso 3 │ transformers.py  │ Implementar build_chat_output()
Paso 4 │ modelos.py      │ Agregar output_chat a ResultadoDia + flags a ArchivosDia
Paso 5 │ procesar_dia.py │ Agregar rama --chat con llamada a build_chat_output()
Paso 6 │ ejecutar_dia.py │ Agregar args --chat y --sin_planes_hoy
Paso 7 │ Tests            │ Unit tests + integration test manual con datos de prueba
Paso 8 │ N8N             │ Configurar workflow de lookup (archivo separado)
Paso 9 │ Retell           │ Agregar tool al conversation-flow apuntando al webhook
```

> **Rama de trabajo recomendada:** `feature/chat-roman-output` sobre `main`.  
> Los cambios en `update_estado.py` (Paso 2) son los de mayor riesgo: asegurarse de que los tests del ETL de voz sigan pasando antes de mergear.

---

## 8. Notas adicionales

### Nombre del archivo y formato de fecha

El sufijo de fecha usa formato `YYMMDD` para consistencia con el ROMAN de voz:

```python
OUTPUT_FILENAME_CHAT_ROMAN = "NARANJAX_MA_CHAT_ROMAN_"
# → NARANJAX_MA_CHAT_ROMAN_260526.csv
```

### Subida a OneDrive

El archivo se sube al mismo OneDrive que el ROMAN de voz. N8N lo descarga por `fileId`. Al implementar la tarea programada del ETL, guardar el `fileId` del archivo más reciente en una variable de entorno o en la configuración del workflow.

### Variables dinámicas del agente

El conversation-flow `Prueba_RM` (v11) actualmente no tiene tools configuradas (`"tools": []`). Antes de conectar el webhook, agregar la tool `lookup_cliente` en Retell con:

- **Method:** POST
- **URL:** `https://flows.evoltis.com/webhook/naranja/chat/inbound`
- **Parameters:** `{ "dni": "string" }` (mapeado desde la variable `{{id_dni}}` extraída por el nodo de captura de DNI)

---

*Documento generado: 2026-05-26 · Proyecto: SOHO_Chat-NARANJAX_MA*
