# Plan de Desarrollo — Fase 2
## ETL Naranja X Mora Avanzada — Integración de Archivos Diarios y Planes

---

## Contexto y estado actual

El proyecto tiene dos módulos funcionando:

- **`back-base/`** — ETL que transforma la base mensual (`Formato completo de archivo de entrada.xlsx`) al formato SOHO (`NARANJAX_CARTERA_YYYYMMDD.csv`). Produce 23 columnas, una fila por cliente.
- **`back-resultados/`** — ETL que convierte tipificaciones del agente de IA al formato PCT de Naranja X (`NARANJAX_PCT_YYYYMMDD.txt`).

**Lo que falta construir en esta fase:**

Actualmente el archivo de salida ROMAN (`NARANJAX_MA_ROMAN_YYMMDD.csv`) usa los montos de la base mensual. Esos montos son fórmulas Excel no evaluadas (`=+G2+F2`) y no están actualizados al día del discado.

La Fase 2 resuelve esto incorporando los dos archivos diarios y generando el ROMAN con datos frescos y las columnas de planes.

---

## Conclusiones de negocio que guían esta fase

| Decisión | Detalle |
|---|---|
| Fuente de verdad para montos | **PLANES** — `DEUDA_TOTAL` y `DEUDA_VENCIDA` ya contemplan el descuento del pago del día |
| Uso del archivo de PAGOS | Solo para `RECUPERO`, `TIPO_PAGO` y `CAJON_ACTUAL_PROD` |
| Estructura del archivo de planes | Múltiples filas por cliente (una por opción de cuotas), pero `DEUDA_TOTAL`, `DEUDA_VENCIDA` y `CAJON` son constantes entre filas del mismo producto |
| Planes en el archivo de salida | Una sola fila por cliente en ROMAN, con columnas adicionales para cada plan disponible |
| Clientes a excluir | Los que tienen `CAJON = CAN` en el archivo de planes (cancelados) |

---

## Arquitectura de la Fase 2

```
[Base mensual]          [Archivo PAGOS diario]     [Archivo PLANES diario]
      │                         │                           │
      │  datos de contacto      │  RECUPERO                 │  montos actualizados
      │  teléfonos, emails      │  TIPO_PAGO                │  CAJON real
      │  segmentación           │  CAJON_ACTUAL_PROD        │  opciones de plan
      └──────────────┬──────────┘           └───────────────┘
                     │
              [update_estado()]         ← módulo nuevo
                     │
              [Estado diario]           ← una fila por cliente, datos frescos
                     │
              [transform_roman()]       ← extensión del transformer actual
                     │
        NARANJAX_MA_ROMAN_YYYYMMDD.csv  ← salida con columnas de planes agregadas
```

---

## Estructura de archivos a crear/modificar

```
back-base/
├── etl/
│   ├── constants.py          MODIFICAR — agregar columnas nuevas de planes y pagos
│   ├── transformers.py       MODIFICAR — incorporar lógica de planes y pagos
│   ├── io.py                 MODIFICAR — agregar load_planes() y load_pagos()
│   ├── cleaners.py           SIN CAMBIOS
│   └── validators.py         MODIFICAR — agregar validaciones de archivos diarios
│
├── etl_naranjax.py           MODIFICAR — orquestar los tres archivos de entrada
│
└── tests/
    ├── test_planes_pivot.py  NUEVO — tests del pivot de planes
    ├── test_update_estado.py NUEVO — tests de la lógica de merge
    └── fixtures/             NUEVO — archivos de prueba reducidos
```

---

## Tareas detalladas

### TAREA 1 — `io.py`: funciones de carga de archivos diarios

**Archivo:** `back-base/etl/io.py`

Agregar dos funciones nuevas:

```python
def load_planes(filepath: str) -> pd.DataFrame:
    """
    Carga el archivo de cartera con planes (xlsx).
    Hoja: default_1
    Columnas esperadas (por nombre, no por índice):
      DNI, TIPO_DOC, NRODOC, ENTIDAD, NROPRODUCTO, CAJON,
      DEUDA_TOTAL, DEUDA_VENCIDA, PLAN, IMPORTE_ENTREGA,
      IMPORTE_CUOTA, ULTIMO_ENVIO_PROPUESTA
    Retorna DataFrame con esas columnas normalizadas a lowercase.
    """

def load_pagos(filepath: str) -> pd.DataFrame:
    """
    Carga el archivo de pagos diarios (csv, separador ;).
    Columnas mínimas requeridas:
      NROPRODUCTO, RECUPERO, TIPO_PAGO, CAJON_ACTUAL_PROD,
      DT_ACTUAL, DV_ACTUAL
    Retorna DataFrame con columnas normalizadas a lowercase.
    """
```

**Validaciones mínimas en cada función:**
- Verificar que existan las columnas requeridas, sino lanzar `ValueError` descriptivo.
- Loggear cantidad de filas cargadas.

---

### TAREA 2 — Lógica de pivot de planes

**Archivo nuevo:** `back-base/etl/planes_pivot.py`

Este es el módulo más importante de la fase. Toma el DataFrame de planes (N filas por cliente) y lo convierte en un DataFrame de una fila por cliente con columnas dinámicas para cada plan.

```python
def pivot_planes(df_planes: pd.DataFrame) -> pd.DataFrame:
    """
    Input:  DataFrame con N filas por NROPRODUCTO (una por plan disponible)
    Output: DataFrame con 1 fila por NROPRODUCTO y columnas:
    
      nroproducto
      cajon_planes          ← CAJON del archivo de planes (es constante entre filas)
      deuda_total_planes    ← DEUDA_TOTAL (es constante entre filas)
      deuda_vencida_planes  ← DEUDA_VENCIDA (es constante entre filas)
      plan_1_cuotas         ← PLAN de la primera opción (menor cuota)
      plan_1_entrega        ← IMPORTE_ENTREGA de la primera opción
      plan_1_cuota_mensual  ← IMPORTE_CUOTA de la primera opción
      plan_2_cuotas
      plan_2_entrega
      plan_2_cuota_mensual
      ...hasta plan_N (según el máximo de planes que tenga cualquier cliente)
    """
```

**Reglas del pivot:**
- Ordenar los planes de cada cliente de **menor a mayor cantidad de cuotas** antes de asignar plan_1, plan_2, etc.
- Si un cliente tiene menos planes que el máximo, rellenar con vacío (`""`).
- Excluir clientes con `CAJON = CAN` — no deben aparecer en el output.
- El número máximo de columnas de plan se determina dinámicamente del archivo del día (no hardcodeado).

**Función auxiliar:**

```python
def get_plan_column_names(max_plans: int) -> list[str]:
    """
    Genera la lista de nombres de columna para N planes.
    Ejemplo con max_plans=6:
    ['plan_1_cuotas', 'plan_1_entrega', 'plan_1_cuota_mensual',
     'plan_2_cuotas', 'plan_2_entrega', 'plan_2_cuota_mensual', ...]
    """
```

---

### TAREA 3 — `update_estado()`: merge de los tres archivos

**Archivo nuevo:** `back-base/etl/update_estado.py`

```python
def update_estado(
    df_base: pd.DataFrame,
    df_planes_pivot: pd.DataFrame,
    df_pagos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combina los tres DataFrames aplicando las reglas de precedencia.
    
    Clave de join: id_nro_producto (base) = nroproducto (planes y pagos)
    
    Reglas:
    1. Partir de df_base como base (datos de contacto, segmentación)
    2. Para clientes con match en planes:
       - Actualizar: monto_deuda_total_ars ← deuda_total_planes
       - Actualizar: monto_total_vencido_ars ← deuda_vencida_planes
       - Actualizar: tipo_cajon ← cajon_planes
       - Agregar: columnas plan_1..plan_N
    3. Para clientes con match en pagos:
       - Agregar: recupero ← RECUPERO
       - Agregar: tipo_pago ← TIPO_PAGO
       - Actualizar tipo_cajon con CAJON_ACTUAL_PROD solo si no viene de planes
         (planes tiene precedencia sobre pagos para el cajón)
    4. Clientes sin match en planes → mantener montos de la base mensual,
       loggear advertencia.
    5. Clientes con CAJON=CAN en planes → excluir del output final.
    
    Retorna df_base enriquecido con todas las columnas nuevas.
    """
```

---

### TAREA 4 — `constants.py`: nuevas columnas de output

**Archivo:** `back-base/etl/constants.py`

Agregar:

```python
# Columnas fijas nuevas que agrega la fase 2 (antes de las columnas de plan)
OUTPUT_COLUMNS_PHASE2_FIXED = [
    "recupero",
    "tipo_pago",
]

# Columnas de planes: se generan dinámicamente en runtime
# Patrón: plan_{n}_cuotas, plan_{n}_entrega, plan_{n}_cuota_mensual
PLAN_COLUMN_PATTERN = "plan_{n}_{field}"
PLAN_FIELDS = ["cuotas", "entrega", "cuota_mensual"]

# Nombre del archivo de salida ROMAN
OUTPUT_FILENAME_ROMAN = "NARANJAX_MA_ROMAN_"

# Columnas requeridas en archivo de planes
PLANES_REQUIRED_COLUMNS = [
    "nroproducto", "cajon", "deuda_total",
    "deuda_vencida", "plan", "importe_entrega", "importe_cuota"
]

# Columnas requeridas en archivo de pagos
PAGOS_REQUIRED_COLUMNS = [
    "nroproducto", "recupero", "tipo_pago", "cajon_actual_prod"
]
```

---

### TAREA 5 — `transformers.py`: adaptar transform() para usar el estado enriquecido

**Archivo:** `back-base/etl/transformers.py`

La función `transform()` actual recorre fila a fila y construye el record. Hay que adaptarla para:

1. Recibir el DataFrame ya enriquecido por `update_estado()` (en lugar del crudo de la base).
2. Incluir en el record las columnas nuevas: `recupero`, `tipo_pago`, y las columnas `plan_N_*` dinámicas.
3. Actualizar los campos de monto para que lean de las columnas actualizadas (no de las originales de la base).

**Cambio en la firma:**

```python
# Antes
def transform(df: pd.DataFrame, logger=None) -> pd.DataFrame:

# Después
def transform(df: pd.DataFrame, plan_columns: list[str], logger=None) -> pd.DataFrame:
    """
    plan_columns: lista de nombres de columnas de plan generada por get_plan_column_names()
    Se agregan al output en el orden recibido, después de las columnas fijas.
    """
```

---

### TAREA 6 — `etl_naranjax.py`: orquestador actualizado

**Archivo:** `back-base/etl_naranjax.py`

Actualizar `main()` para aceptar los nuevos argumentos y orquestar el flujo completo:

```python
# Nuevos argumentos CLI
parser.add_argument("--planes", required=False, help="Path al archivo de planes diario")
parser.add_argument("--pagos",  required=False, help="Path al archivo de pagos diario")

# Flujo actualizado
def main():
    # 1. Cargar base mensual (igual que hoy)
    df_base = load_input(args.input)

    # 2. Cargar archivos diarios (opcionales — pueden venir uno, ambos o ninguno)
    df_planes = load_planes(args.planes) if args.planes else None
    df_pagos  = load_pagos(args.pagos)   if args.pagos  else None

    # 3. Pivot de planes
    df_planes_pivot = pivot_planes(df_planes) if df_planes is not None else None

    # 4. Merge de los tres archivos
    df_estado = update_estado(df_base, df_planes_pivot, df_pagos)

    # 5. Determinar columnas de plan del día
    plan_columns = get_plan_column_names(df_planes_pivot) if df_planes_pivot is not None else []

    # 6. Transform y guardar
    df_output = transform(df_estado, plan_columns=plan_columns)
    save_output(df_output, args.output_dir, prefix=OUTPUT_FILENAME_ROMAN)
```

**Comportamiento cuando faltan archivos diarios:**
- Si no llega `--planes`: loggear advertencia, usar montos de la base mensual, sin columnas de plan.
- Si no llega `--pagos`: loggear advertencia, columnas `recupero` y `tipo_pago` quedan vacías.
- Si no llega ninguno: el ETL corre igual que hoy (compatibilidad hacia atrás garantizada).

---

### TAREA 7 — Tests

**Archivos nuevos en `back-base/tests/`:**

**`test_planes_pivot.py`**
- Cliente con 6 planes → genera 6 columnas correctamente ordenadas por cuotas
- Cliente con 1 plan → genera 1 columna, el resto vacío
- Cliente con `CAJON=CAN` → excluido del output
- Columnas constantes (DEUDA_TOTAL, CAJON) son iguales en todas las filas del mismo producto

**`test_update_estado.py`**
- Cliente con match en planes y pagos → montos vienen de planes, recupero de pagos
- Cliente sin match en planes → montos de base mensual, warning loggeado
- Cliente con `RECUPERO=SI` → aparece en output con recupero=SI
- Precedencia: cajón de planes pisa cajón de pagos cuando ambos están presentes

**`test_relocation_contract.py`** (existente — actualizar)
- Actualizar `golden_output_header.txt` con las nuevas columnas
- Agregar caso de test con archivos diarios incluidos

**Fixtures necesarios** (`tests/fixtures/`):
- `planes_sample.xlsx` — 10 clientes, variedad de planes (1 a 6), 1 con CAN
- `pagos_sample.csv` — mismos 10 clientes con RECUPERO SI/NO y TIPO_PAGO variado

---

## Orden de implementación recomendado

```
1. io.py          → load_planes() + load_pagos()           (sin dependencias)
2. constants.py   → nuevas constantes                      (sin dependencias)
3. planes_pivot.py → pivot_planes()                        (depende de io)
4. update_estado.py → update_estado()                      (depende de pivot)
5. transformers.py → adaptar transform()                   (depende de update_estado)
6. etl_naranjax.py → orquestador                           (depende de todo)
7. tests          → fixtures + tests nuevos + actualizar golden header
```

---

## Criterios de aceptación de la fase

- [ ] El archivo ROMAN generado tiene una fila por cliente (sin duplicados)
- [ ] Los montos `monto_deuda_total_ars` y `monto_total_vencido_ars` vienen del archivo de planes cuando está disponible
- [ ] El número de columnas de plan varía según el archivo del día (dinámico, no hardcodeado)
- [ ] Los planes están ordenados de menor a mayor cantidad de cuotas
- [ ] Clientes con `CAJON=CAN` no aparecen en el output
- [ ] Si no llegan archivos diarios, el ETL corre con compatibilidad hacia atrás
- [ ] Todos los tests pasan con `pytest back-base/tests/`
- [ ] El golden header del test de contrato se actualiza con las nuevas columnas

---

## Preguntas pendientes con el cliente

| Pregunta | Impacto en código |
|---|---|
| ¿Un cliente con `RECUPERO=SI` debe ser excluido del archivo ROMAN (no llamar) o incluido con ese flag? | Lógica de filtrado en `update_estado()` |
| ¿El `CAJON_ACTUAL_PROD` de pagos pisa al `CAJON` de planes cuando ambos están presentes? | Regla de precedencia en `update_estado()` — hoy el plan tiene prioridad, pero falta confirmación |
| ¿El archivo ROMAN debe incluir las columnas `recupero` y `tipo_pago`, o son solo para uso interno? | Definición del schema de salida |
