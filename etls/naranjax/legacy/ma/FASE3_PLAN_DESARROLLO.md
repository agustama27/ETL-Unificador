# Plan de Desarrollo — Fase 3
## ETL Naranja X Mora Avanzada — Filtros de negocio, estado persistente y operación diaria

---

## Contexto y estado al cierre de Fase 2

El pipeline produce correctamente el archivo `NARANJAX_MA_ROMAN_YYYYMMDD.csv` con:
- Datos de contacto y segmentación de la base mensual
- Montos actualizados desde el archivo de planes
- Cajón actualizado con precedencia de planes sobre pagos
- Columnas dinámicas de planes (`plan_1_cuotas`, `plan_1_entrega`, etc.)
- Campos `recupero` y `tipo_pago` del archivo de pagos
- Exclusión de clientes con `CAJON=CAN`

Lo que **no resuelve Fase 2** y es el foco de Fase 3:

1. **No hay filtros de negocio aplicados** — el ROMAN incluye clientes que no deberían ser llamados (RECUPERO=SI, cajones fuera del scope de mora avanzada)
2. **No hay estado persistente** — cada ejecución parte de la base mensual desde cero, sin memoria de lo que pasó días anteriores
3. **La operación diaria es manual y frágil** — el operador tiene que ejecutar comandos CLI sabiendo rutas, argumentos y orden de archivos
4. **El archivo PCT de resultados** (`back-resultados/`) tiene el mapa de tipificaciones incompleto y sin conexión con el ROMAN

---

## Decisiones de negocio

| # | Pregunta | Estado | Resolución |
|---|---|---|---|
| D1 | ¿`RECUPERO=SI` excluye del ROMAN o se incluye con flag? | ✅ CERRADA | Excluir del estado persistente. El cliente no vuelve a aparecer en ningún ROMAN del mes. |
| D2 | ¿El cajón válido para esta campaña es solo M90, o también M120 y M150? | ⏳ PENDIENTE | — |
| D3 | ¿`recupero` y `tipo_pago` quedan en el schema público del ROMAN o son solo internos? | ⏳ PENDIENTE | — |
| D4 | ¿Los códigos de tipificación del mapa propuesto son correctos? | ⏳ PENDIENTE | — |

Las tareas 2, 3 y 5 se pueden implementar **sin esperar respuestas pendientes**.

---

## Arquitectura de la Fase 3

```
                    ┌─────────────────────────────┐
                    │     ESTADO PERSISTENTE       │
                    │  estado_YYYYMM.csv           │
                    │  (se actualiza cada día)     │
                    └──────────────┬───────────────┘
                                   │ lee y escribe
                                   ▼
[Base mensual]   [PLANES diario]  [PAGOS diario]
      │                │                │
      └────────────────┴────────────────┘
                       │
               [Fase 2: update_estado()]
                       │
               [Fase 3: aplicar_filtros()]   ← NUEVO
                       │
               [ROMAN filtrado]              ← solo clientes a llamar hoy
                       │
               [guardar_estado()]            ← NUEVO — persiste el estado del día
```

---

## Tareas detalladas

---

### TAREA 1 — Filtros de negocio
**Requiere decisión pendiente: D2**
**D1 resuelta: RECUPERO=SI elimina el cliente del estado persistente**
**Archivo:** `back-base/etl/filtros.py` (módulo nuevo)

Aplicar los filtros que determinan qué clientes se incluyen en el ROMAN del día.

**Importante — dónde se aplica cada filtro:**

| Filtro | Dónde se aplica | Motivo |
|---|---|---|
| F2 — RECUPERO=SI | Dentro de `update_estado()`, antes de `guardar_estado()` | Debe eliminar del estado persistente, no solo del ROMAN |
| F1 — Cajón fuera de scope | En `filtros.py`, después de `update_estado()` | Exclusión del ROMAN del día, no necesariamente del estado |
| F3 — CAN | Ya implementado en Fase 2 en `planes_pivot.py` | No duplicar |

```python
def aplicar_filtros(df: pd.DataFrame, logger=None) -> tuple[pd.DataFrame, dict]:
    """
    Aplica filtros de negocio sobre el estado enriquecido.
    Retorna (df_filtrado, resumen_exclusiones).

    Filtros implementados:

    F1 — Cajón fuera de scope:
         Excluir si tipo_cajon NOT IN scope_cajones
         → clientes que bajaron a mora temprana (M12, M15, M30, M60)
         → estados especiales (SEV, TARDIA*, RECICLADONX)
         [PENDIENTE D2: confirmar lista exacta de cajones válidos]

    F3 — CAN: verificar que no se duplique con Fase 2.

    Retorna también un dict con conteo de excluidos por motivo:
    {
        'cajon_fuera_scope': N,
        'total_incluidos': N,
        'total_excluidos': N
    }
    """
```

**Lógica de F2 — RECUPERO=SI dentro de `update_estado()`:**

```python
# Al final de update_estado(), antes de retornar el estado
recuperados = estado["recupero"] == "SI"
if recuperados.sum() > 0:
    active_logger.info(
        "Excluding %s clients with RECUPERO=SI from persistent state",
        int(recuperados.sum())
    )
    estado = estado[~recuperados].copy()
# El estado sin estos clientes se pasa a guardar_estado()
# → quedan excluidos permanentemente del mes
```

**Comportamiento de reingreso — Opción A (sin reingreso):**
- Una vez que el cliente tiene `RECUPERO=SI` sale del estado y no vuelve.
- Si el sistema de pagos lo reprocesa días después, se ignora silenciosamente.
- Si ocurre un error en el archivo de pagos y un cliente fue excluido incorrectamente, se resuelve mediante rollback manual al snapshot del día anterior (ver Tarea 2).

**Tests requeridos** (`test_filtros.py`):
- Cliente M30 → excluido por cajón fuera de scope
- Cliente M90 → incluido
- Cliente con RECUPERO=SI → excluido del estado en `update_estado()`, no llega a `filtros.py`
- Resumen de exclusiones refleja conteos correctos por motivo

---

### TAREA 2 — Estado persistente diario
**Sin dependencias de decisiones pendientes**
**Archivo nuevo:** `back-base/etl/estado_persistente.py`

Resuelve el problema central de arquitectura: hoy cada ejecución parte desde cero. Con estado persistente, el pipeline acumula información día a día durante el mes. Los clientes excluidos (RECUPERO=SI o CAN) desaparecen del estado y no regresan.

```python
def inicializar_estado(df_base: pd.DataFrame, output_dir: str, mes: str) -> str:
    """
    Crea el archivo de estado del mes a partir de la base mensual.
    Solo se llama una vez al inicio de cada mes cuando llega la base nueva.

    Nombre del archivo: estado_{YYYYMM}.csv
    Ejemplo: estado_202604.csv

    Retorna el path del archivo creado.
    """

def cargar_estado(estado_dir: str, mes: str) -> pd.DataFrame:
    """
    Carga el estado vigente del mes.
    Si no existe, lanza FileNotFoundError con mensaje descriptivo
    que indique al operador que debe inicializar el mes primero.
    """

def guardar_estado(df: pd.DataFrame, estado_dir: str, fecha: str) -> tuple[str, str]:
    """
    Guarda el estado actualizado del día.

    Genera dos archivos:
    1. estado_{YYYYMM}.csv        → estado vigente (se sobreescribe cada día)
    2. estado_{YYYYMMDD}.csv      → snapshot inmutable del día

    El snapshot es la base del rollback manual ante errores.
    Retorna (path_vigente, path_snapshot).
    """
```

**Rollback manual** — no es una función del pipeline sino un procedimiento operativo:
Si un día el archivo de planes o pagos llegó con errores y se excluyeron clientes incorrectamente, el operador copia el snapshot del día anterior sobre el vigente y vuelve a correr el día:

```bash
# Ejemplo: restaurar al estado del día 17 y reprocesar el día 18
cp estados/estado_20260417.csv estados/estado_202604.csv
python ejecutar_dia.py
```

**Estructura de carpetas resultante:**
```
back-base/
└── estados/
    ├── estado_202604.csv          ← estado vigente del mes (se pisa cada día)
    ├── estado_20260417.csv        ← snapshot día 17 (inmutable)
    ├── estado_20260418.csv        ← snapshot día 18 (inmutable)
    └── estado_20260419.csv        ← snapshot día 19 (inmutable)
```

**Tests requeridos** (`test_estado_persistente.py`):
- Inicializar desde base mensual → genera archivo con nombre correcto
- Guardar estado → genera vigente + snapshot con fecha en el nombre
- Snapshot no se sobreescribe si ya existe (es inmutable)
- Cargar estado → carga el vigente del mes
- Cargar estado inexistente → error descriptivo, no KeyError genérico
- Clientes con RECUPERO=SI en update_estado() no aparecen en el estado guardado

---

### TAREA 3 — Orquestador diario simplificado
**Sin dependencias de decisiones pendientes**
**Archivo nuevo:** `back-base/ejecutar_dia.py`

El operador hoy tiene que correr `etl_naranjax.py` con múltiples argumentos CLI. Esto es propenso a errores. El objetivo es que la operación diaria sea un solo comando sin argumentos, o idealmente un doble clic.

```python
#!/usr/bin/env python3
"""
Ejecutar el proceso diario completo.
Uso: python ejecutar_dia.py

Detecta automáticamente:
- La base mensual vigente en /archivo-recibido/
- Los archivos diarios en /diarios/entrada/
- El estado persistente en /estados/

No requiere argumentos. Loggea todo en /logs/YYYYMMDD.log
"""

def detectar_archivos_diarios(input_dir: str) -> dict:
    """
    Escanea la carpeta de entrada y clasifica los archivos encontrados.
    
    Reconoce por nombre:
    - Archivo de planes: contiene 'cartera' o 'planes' en el nombre → xlsx
    - Archivo de pagos: contiene 'pagos' o 'avanzada' en el nombre → csv
    
    Retorna:
    {
        'planes': path o None,
        'pagos': path o None,
        'no_reconocidos': [lista de archivos que no matchearon]
    }
    """

def mover_procesados(archivos: dict, processed_dir: str, fecha: str) -> None:
    """
    Mueve los archivos de entrada a /diarios/procesados/YYYYMMDD/
    una vez que el proceso terminó exitosamente.
    Evita reprocesar archivos si el operador ejecuta dos veces.
    """

def main():
    # 1. Detectar archivos del día en /diarios/entrada/
    # 2. Cargar estado persistente vigente
    # 3. Aplicar update_estado() + filtros()
    # 4. Generar ROMAN en /base-generada/
    # 5. Guardar estado actualizado
    # 6. Mover archivos procesados a /diarios/procesados/YYYYMMDD/
    # 7. Imprimir resumen en pantalla
```

**Estructura de carpetas esperada:**
```
back-base/
├── archivo-recibido/          ← base mensual (se reemplaza 1 vez/mes)
├── diarios/
│   ├── entrada/               ← el operador deposita los archivos aquí
│   └── procesados/
│       ├── 20260417/          ← archivos ya procesados, con fecha
│       └── 20260418/
├── estados/                   ← estado persistente (automático)
├── base-generada/             ← ROMAN del día (output)
└── logs/                      ← un log por día
```

**Tests requeridos** (`test_ejecutar_dia.py`):
- Carpeta con planes + pagos → detecta ambos correctamente
- Carpeta con solo planes → detecta uno, advierte del otro
- Carpeta vacía → error descriptivo, no stacktrace
- Archivo con nombre no reconocido → aparece en `no_reconocidos`
- Doble ejecución el mismo día → segundo run no reprocesa archivos ya movidos

---

### TAREA 4 — Revisión del schema final del ROMAN
**Requiere decisión: D3**
**Archivos:** `back-base/etl/constants.py`, `back-base/tests/golden_output_header.txt`

Una vez confirmado con el cliente si `recupero` y `tipo_pago` van en el schema público:

- **Si van:** el golden header actual ya es correcto, no hay cambios.
- **Si no van:** removerlos de `OUTPUT_COLUMNS` y del golden header. El pipeline los sigue usando internamente para el filtro F2 pero no los escribe en el CSV final.

También en esta tarea: agregar el filtro de cajones al golden header — el ROMAN de mora avanzada solo debería tener M90/M120/M150, nunca M30 o M60.

---

### TAREA 5 — Completar el mapa de tipificaciones en `back-resultados/`
**Sin dependencias de decisiones pendientes**
**Archivo:** `back-resultados/etl/constants.py`

El mapa actual tiene solo 3 tipificaciones por producto, que son claramente placeholders:

```python
# Estado actual — incompleto
TIPIF_MAP_TC = {
    "PROMESA_DE_PAGO": "TCP01",
    "NO_CONTACTO":     "TCNC0",
    "RECHAZA_PAGO":    "TCRP0",
}
TIPIF_MAP_ND = {
    "PROMESA_DE_PAGO": "NDP09",
    "RECHAZA_PAGO":    "NDRP0",
}
```

Hay que completarlo con todos los códigos del archivo `CodigosTipificacionRM.xlsx` que ya fue analizado. El mapa completo propuesto (a validar con el cliente):

```python
TIPIF_MAP_TC = {
    "PROMESA_DE_PAGO":        12,
    "DIFICULTAD_DE_PAGO":     47,
    "NO_RECONOCE_DEUDA":      46,
    "SE_NIEGA_A_PAGAR":       45,
    "YA_PAGO":                37,
    "FALLECIDO":              44,
    "VOLVER_A_LLAMAR":         7,
    "LLAMADA_CORTADA":         8,
    "MENSAJE_OPERADOR":       11,
    "PAGO_POR_CBU":           52,
    "RECORDATORIO_PROMESA":   53,
    "MESSAGE":                 7,   # alias de VOLVER_A_LLAMAR
    "NO_ANSWER":               7,
    "HANGUP":                  8,
    "BUSY":                    7,
    "PAID":                   37,
}

TIPIF_MAP_ND = {
    "PROMESA_DE_PAGO":        12,
    "DIFICULTAD_DE_PAGO":     47,
    "NO_RECONOCE_DEUDA":      46,
    "SE_NIEGA_A_PAGAR":       45,
    "YA_PAGO":                37,
    "FALLECIDO":              44,
    "VOLVER_A_LLAMAR":         7,
    "LLAMADA_CORTADA":         8,
    "MENSAJE_OPERADOR":       11,
    "APP_NO_FUNCIONA":        62,
    "CONFIRMA_PROMESA":       63,
    "POSIBLE_FRAUDE":         64,
    "MESSAGE":                 7,
    "NO_ANSWER":               7,
    "HANGUP":                  8,
    "BUSY":                    7,
    "PAID":                   37,
}
```

**Tests requeridos** — actualizar `test_tipificaciones_mapping.py`:
- Cada key del mapa TC tiene un código numérico válido
- Cada key del mapa ND tiene un código numérico válido
- Resultado desconocido → warning + omisión de fila (comportamiento ya testeado)

---

## Orden de implementación recomendado

```
1. estado_persistente.py   → sin dependencias, máximo impacto en operación
2. update_estado.py        → agregar exclusión de RECUPERO=SI antes de guardar estado
3. ejecutar_dia.py         → sin dependencias, simplifica la operación inmediatamente
4. filtros.py              → esperar D2 del cliente (cajones válidos)
5. tipificaciones map      → completar con códigos reales, sin dependencias
6. schema final ROMAN      → esperar D3 del cliente
```

---

## Criterios de aceptación de la Fase 3

- [ ] El operador ejecuta `python ejecutar_dia.py` sin argumentos y el proceso corre completo
- [ ] Los archivos procesados se mueven automáticamente a `/diarios/procesados/YYYYMMDD/`
- [ ] El estado del mes se acumula día a día en `estados/estado_YYYYMM.csv`
- [ ] Existe un snapshot inmutable por día (`estados/estado_YYYYMMDD.csv`) que permite rollback manual
- [ ] Clientes con `RECUPERO=SI` no aparecen en el estado persistente ni en ningún ROMAN posterior
- [ ] El ROMAN generado no contiene clientes con cajón fuera de scope (M30, M60, SEV, etc.)
- [ ] El mapa de tipificaciones cubre todos los resultados posibles del agente IA
- [ ] Todos los tests pasan con `pytest back-base/tests/ back-resultados/tests/`
- [ ] El log diario registra: archivos detectados, filas procesadas, excluidos por motivo y path de salida

---

## Pendientes con el cliente que desbloquean esta fase

| ID | Pregunta | Bloqueante para | Estado |
|---|---|---|---|
| D1 | ¿`RECUPERO=SI` excluye del ROMAN o se incluye con flag? | Tarea 1 — filtro F2 | ✅ CERRADA: excluir del estado persistente |
| D2 | ¿El scope de mora avanzada es solo M90 o también M120 y M150? | Tarea 1 — filtro F1 | ⏳ PENDIENTE |
| D3 | ¿`recupero` y `tipo_pago` van en el CSV final o son solo internos? | Tarea 4 — schema | ⏳ PENDIENTE |
| D4 | ¿Los códigos de tipificación del mapa propuesto son correctos? | Tarea 5 | ⏳ PENDIENTE |
