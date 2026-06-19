# Plan de implementación — Back-resultados Naranja X M30

**Versión acelerada · ~10 horas de desarrollo**

> Objetivo: agregar al ETL existente la capacidad de procesar `LOGCALL` + `historial_llamadas` y generar el archivo `DEELO_NAR_USUOLOS` que espera Naranja X.

---

## Decisiones para acelerar

Para reducir el tiempo de ~24h a ~10h, este plan toma estos atajos respecto al plan original:

- **Módulo monolítico** en lugar de helpers separados. Toda la lógica vive en un solo archivo `back_resultados.py`.
- **Mapeo de RESULT codes hardcodeado** como diccionario al inicio del módulo. Si hay que cambiarlo, son 5 líneas. Cuando el cliente confirme el mapeo definitivo, se externaliza a JSON (1h extra a futuro).
- **Reutilización directa** de `_normalizar_telefono` desde `base_generator.py` por import. Nada de refactor.
- **Validaciones inline** durante la construcción de filas, no en un módulo separado.
- **Sin tests unitarios formales**. Validación manual con el dataset del 13/05.
- **Documentación mínima**: solo actualizar `CLAUDE.md` con una sección nueva.

Lo que **no se sacrifica**: trazabilidad de anomalías, validación estructural del output, e idempotencia del proceso.

---

## Bloqueantes (paralelos al desarrollo)

Estos puntos se pueden cerrar mientras el código avanza. El mapeo provisorio queda en el dict del módulo:

| Bloqueante | Estado |
|---|---|
| Mapeo RESULT codes 7, 8, 9, 1004, 16 del LogCall | Provisorio: `9→MESSAGE`, `1004→VOLVER A LLAMAR`, `7→BUSY`, `8→NO ANSWER`, `16→VOLVER A LLAMAR` |
| 167 casos `RESULT=10` sin match en HISTORIAL | Provisorio: `VOLVER A LLAMAR` |
| 4 casos "Dificultad de pago" con compromiso_logrado=true | Provisorio: ir como `PAYMENT DIFFICULTY` (sin monto/fecha) |
| 2 campañas mezcladas (MT + MA) en LogCall | Provisorio: filtrar solo MT (ACTIGROUP=M) |

> Las 4 decisiones provisorias están **señalizadas como TODO en el código** y son los únicos puntos a tocar cuando lleguen las definiciones finales.

---

## Arquitectura

Manteniendo las convenciones actuales del ETL (stdlib pura, auto-discovery por mtime):

```
soho-naranjaX-MT-etl/
├── main.py                          [MODIFICAR] flag --back
├── procesos/
│   ├── base_generator.py            [SIN CAMBIOS]
│   ├── phone_extractor.py           [SIN CAMBIOS]
│   └── back_resultados.py           [NUEVO] módulo monolítico
├── back_recibida/                   [NUEVO]
│   ├── historial/                   (drop manual de Roman)
│   └── logcall/                     (drop manual del dialer)
└── back_procesada/                  [NUEVO]
    ├── DEELO_NAR_USUOLOS_*.txt      (entregable final)
    └── _anomalias_*.txt             (reporte de excepciones)
```

**Flujo:**

```
historial + logcall + m30olos del día (de base_recibida/)
                          │
                          ▼
            1. Indexar tel → customer_id (M30OLOS)
            2. Indexar tel → fila historial (Roman)
            3. Recorrer LOGCALL fila por fila
            4. Mapear cada fila a las 40 cols del USUOLOS
            5. Validar estructura
            6. Escribir TXT pipe CRLF + reporte anomalías
```

---

## Plan por fases

### Fase 1 — Setup mínimo (1 hora)

- Crear directorios `back_recibida/{historial,logcall}` y `back_procesada/` con `.gitkeep`.
- Agregar entradas al `.gitignore`.
- Crear archivo vacío `procesos/back_resultados.py`.

**Criterio de aceptación:** la estructura existe y `git status` no muestra ruido.

---

### Fase 2 — Módulo `back_resultados.py` (6 horas)

Un solo archivo, ~400 líneas estimadas. Estructura interna:

```python
# back_resultados.py

# ─────────────────────────────────────────────────────────────────
# CONFIG — modificar acá cuando se cierren los bloqueantes
# ─────────────────────────────────────────────────────────────────

MAPEO_TIPIFICACION = {
    'Promesa de pago':       'PROMISE',
    'Dificultad de pago':    'PAYMENT DIFFICULTY',
    'Manifiesta pago':       'PAID',
    'Contestador':           'MESSAGE',
    'No responde':           'HANGUP',
    'Notificado titular':    'MENSAJE OPERADOR',
    'Notificado familiar':   'MENSAJE OPERADOR',
    'No es titular':         'MENSAJE OPERADOR',
    'No reconoce deuda':     'MENSAJE OPERADOR',
    'Conoce titular':        'MENSAJE OPERADOR',
    'Sin voluntad de pago':  'VOLVER A LLAMAR',
}

MAPEO_RESULT_LOGCALL = {  # TODO: confirmar con cliente
    '9':    'MESSAGE',
    '1004': 'VOLVER A LLAMAR',
    '7':    'BUSY',
    '8':    'NO ANSWER',
    '16':   'VOLVER A LLAMAR',
}

CAMPANA_FILTRO = 'IA_NARANJAXMT'  # TODO: confirmar si va MT, MA o ambas
RESULT_BOT = '10'

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def normalizar_fecha(fecha_str):
    """'15/05/26' o '15/05/2026' → '20260515235858'."""
    ...

def descomponer_telefono(tel_normalizado):
    """'5491123001415' → ('1123001415', '11', 'CEL')."""
    ...

def construir_indice_clientes(m30olos_path):
    """Lee M30OLOS, devuelve {tel_normalizado: customer_id}."""
    ...

def construir_indice_historial(historial_path):
    """Lee historial Roman, devuelve {user_number: fila_dict}."""
    ...

# ─────────────────────────────────────────────────────────────────
# Núcleo
# ─────────────────────────────────────────────────────────────────

def mapear_col_11(logcall_row, fila_historial):
    """Determina el resultado USUOLOS según las reglas."""
    if logcall_row['RESULT'] == RESULT_BOT:
        if fila_historial:
            tip = fila_historial['[Salida] Tipificaciones']
            return MAPEO_TIPIFICACION.get(tip, 'VOLVER A LLAMAR')
        else:
            return 'VOLVER A LLAMAR'  # TODO: confirmar
    return MAPEO_RESULT_LOGCALL.get(logcall_row['RESULT'], 'VOLVER A LLAMAR')

def construir_fila_usuolos(logcall_row, idx_historial, idx_clientes, anomalias):
    """Devuelve lista de 40 strings o None si hay que descartar la fila."""
    # ...lógica de las 40 columnas
    # Registra anomalías en el dict que recibe

def procesar(logcall_path, historial_path, m30olos_path, output_dir):
    """Orquestador. Lee fuentes, construye filas, valida, escribe."""
    idx_clientes = construir_indice_clientes(m30olos_path)
    idx_historial = construir_indice_historial(historial_path)
    
    anomalias = {
        'sin_customer_id': [],
        'monto_mayor_deuda': [],
        'fecha_formato_raro': [],
        'compromiso_sin_monto': [],
    }
    
    filas = []
    for row in leer_logcall(logcall_path):
        if row['CAMPAIGN'] != CAMPANA_FILTRO + '_' + fecha:
            continue
        fila = construir_fila_usuolos(row, idx_historial, idx_clientes, anomalias)
        if fila:
            filas.append(fila)
    
    validar(filas)  # raise si algo está mal
    escribir_usuolos(filas, output_dir)
    escribir_reporte(anomalias, output_dir)

# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Auto-discovery del archivo más nuevo en cada carpeta
    procesar(...)
```

**Sub-checkpoints dentro de la fase:**

1. (1h) Lectores: `leer_logcall`, `leer_historial`, índices de clientes y historial.
2. (1h) Helpers: `normalizar_fecha`, `descomponer_telefono`.
3. (2h) `construir_fila_usuolos`: las 40 columnas con su lógica condicional.
4. (1h) `mapear_col_11` con sus 3 casos (RESULT=10 con match, RESULT=10 sin match, RESULT≠10).
5. (1h) Validador inline + escritor del TXT pipe CRLF + reporte de anomalías.

**Criterio de aceptación:** ejecutando con los archivos del 13/05 se genera un TXT con la cantidad de filas esperadas, 40 columnas por fila, y un reporte de anomalías legible.

---

### Fase 3 — Integración y testing manual (2 horas)

#### 3.1 Modificar `main.py` (30 min)

Agregar flag o subcomando:

```python
parser.add_argument('--back', action='store_true', 
                    help='Modo back-resultados (procesar logcall + historial)')

if args.back:
    from procesos.back_resultados import procesar
    procesar(...)
else:
    # pipeline existente sin cambios
```

#### 3.2 Testing manual con lote 13/05 (1h30)

- Copiar los archivos a `back_recibida/`.
- Ejecutar `python main.py --back`.
- Verificar:
  - Cantidad de filas en el output (debe coincidir con LOGCALL filtrado por campaña).
  - Las filas con tipificación Promesa tienen cols 4, 5, 6, 28, 29, 31 llenas.
  - El formato byte-a-byte coincide con el USUOLOS del 27/01 (mismas cols vacías, mismo CRLF, mismas constantes).
  - El reporte de anomalías lista los casos esperados (3 montos > deuda, 4 compromisos sin monto).

**Criterio de aceptación:** `diff` estructural cero contra el formato del USUOLOS de referencia.

---

### Fase 4 — Documentación mínima (1 hora)

Agregar una sección al `CLAUDE.md` existente:

```markdown
## Back-resultados (NUEVO)

Procesa LOGCALL + historial_llamadas → DEELO_NAR_USUOLOS pipe CRLF 40 cols.

### Ejecutar
\`\`\`bash
python main.py --back
\`\`\`

### Inputs esperados (auto-discovery por mtime)
- back_recibida/logcall/LOGCALL_*.csv  (dialer)
- back_recibida/historial/historial_llamadas_*.csv  (Roman)
- base_recibida/DEELO_NAR_M30OLOS_*.txt  (lookup tel → customer_id)

### Output
- back_procesada/DEELO_NAR_USUOLOS_YYYYMMDD_HH.txt
- back_procesada/_anomalias_YYYYMMDD_HHMMSS.txt
```

**Criterio de aceptación:** otra persona del equipo puede operar el ETL leyendo solo el `CLAUDE.md`.

---

## Cronograma total

| Fase | Esfuerzo | Acumulado |
|---|---|---|
| 1 — Setup | 1 h | 1 h |
| 2 — Módulo back_resultados.py | 6 h | 7 h |
| 3 — Integración + testing manual | 2 h | 9 h |
| 4 — Documentación mínima | 1 h | 10 h |

**Total: ~10 horas** (~1.5 días útiles de un dev concentrado).

---

## Lo que se deja fuera del MVP

Para sumarlo en una segunda iteración cuando el flujo esté en producción:

- Externalización del mapeo de RESULT codes a JSON (~1h).
- Refactor de helpers a módulos separados con tests unitarios (~6h).
- Manejo de la campaña MA en paralelo a MT, generando 2 archivos (~2h).
- Detección automática de encoding del input (~2h).
- Métricas de performance y monitoring (~3h).

---

## Riesgos del plan acelerado

| Riesgo | Mitigación |
|---|---|
| Hardcodear el mapeo de RESULT codes hace difícil cambiarlo en producción | El dict está al tope del archivo, comentado. Cambio = 5 líneas + redeploy. |
| Sin tests unitarios formales, una regresión puede pasar desapercibida | El validador inline atrapa errores estructurales. Para errores semánticos: diff manual contra USUOLOS de referencia antes de cada release. |
| Reutilizar `_normalizar_telefono` por import acopla los dos módulos | Aceptable. Si en el futuro cambia la lógica de normalización, ambos flujos se actualizan a la vez (es lo deseable). |
| Filtrar solo campaña MT puede omitir datos válidos de MA | Provisorio. Cuando el cliente confirme alcance, cambiar el filtro o quitar el filter. |

---

## Próximo paso recomendado

Arrancar **Fase 1 y los lectores de Fase 2** en paralelo a cerrar los bloqueantes con el cliente. Las primeras 2-3 horas no dependen de las definiciones pendientes.
