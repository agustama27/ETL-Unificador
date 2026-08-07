# Plan de corrección del ETL — Back-resultados Naranja X

**Objetivo**: que `procesos/back_resultados.py` genere directamente el USUOLOS final aprobado por el cliente, sin necesidad de pasos manuales de post-procesamiento.

**Estado actual**: el módulo existe (439 líneas, monolítico) pero produce un archivo que requiere 7 correcciones manuales para ser aceptado por el CRM del cliente.

**Esfuerzo total estimado**: 6 a 8 horas de un dev concentrado.

---

## Resumen ejecutivo

A lo largo de las iteraciones con el cliente del 13/05/2026 identificamos **7 correcciones** que el ETL actual no aplica correctamente. Este plan las traduce a cambios concretos en `procesos/back_resultados.py`, con snippets listos para pegar.

| # | Corrección | Estado actual ETL | Esfuerzo |
|---|---|---|---|
| 1 | Nombre output: `DEELO_NAR_USUEVOLTIS_*` | Genera `DEELO_NAR_USUOLOS_*` ❌ | 5 min |
| 2 | Col 8 = `USUEVOLTIS` | Hardcodeado a `USUOLOS` ❌ | 5 min |
| 3 | Col 36 = `EVOLTIS` | Hardcodeado a `DEELO` ❌ | 5 min |
| 4 | Col 7 = correlativo `1..N` | Usa `CALLREFID` (10 dígitos) ❌ | 30 min |
| 5 | Cols 15-16-17 = descomposición exacta del M30OLOS del día | Usa heurística sobre PHONE de LogCall ❌ | 2-3 horas |
| 6 | Col 4 = `id_extendido` con padding 13 chars | Usa `customer_id` sin padding ❌ | 15 min |
| 7 | Col 28 = monto con coma decimal | Reemplaza punto por coma pero a veces no aplica ⚠️ | 15 min |

Hay además **2 puntos de criterio** que el cliente todavía no confirmó:

- Mapeo de RESULT codes 7, 8, 9, 1004, 16 del LogCall
- Tratamiento de los 167 casos con RESULT=10 sin match en HISTORIAL

Estos se dejan **configurables vía constantes al tope del módulo** para que cambiarlos sea de 1 línea cuando el cliente responda.

---

## Bug #1 — Nombre del archivo de salida

### Cambio

`procesos/back_resultados.py` línea 403:

```python
# ANTES
usuolos_path = output_dir / f"DEELO_NAR_USUOLOS_{stamp:%Y%m%d_%H}.txt"

# DESPUÉS
usuolos_path = output_dir / f"DEELO_NAR_USUEVOLTIS_{stamp:%Y%m%d_%H}.txt"
```

### Sugerencia adicional

Extraer el prefijo a una constante al tope del módulo para futuros cambios:

```python
OUTPUT_FILENAME_PREFIX = "DEELO_NAR_USUEVOLTIS_"
...
usuolos_path = output_dir / f"{OUTPUT_FILENAME_PREFIX}{stamp:%Y%m%d_%H}.txt"
```

### Criterio de aceptación

El archivo generado se llama `DEELO_NAR_USUEVOLTIS_YYYYMMDD_HH.txt`.

---

## Bug #2 — Col 8: `USUOLOS` → `USUEVOLTIS`

### Cambio

Línea 333:

```python
# ANTES
fila[7] = "USUOLOS"

# DESPUÉS
fila[7] = "USUEVOLTIS"
```

### Sugerencia adicional

Extraer a constante:

```python
TIPO_REGISTRO = "USUEVOLTIS"
...
fila[7] = TIPO_REGISTRO
```

### Criterio de aceptación

Las 3.975 filas tienen `USUEVOLTIS` en la columna 8. Ninguna tiene `USUOLOS`.

---

## Bug #3 — Col 36: `DEELO` → `EVOLTIS`

### Cambio

Línea 344:

```python
# ANTES
fila[35] = "DEELO"

# DESPUÉS
fila[35] = "EVOLTIS"
```

### Sugerencia adicional

Extraer a constante:

```python
GRUPO_GESTION = "EVOLTIS"
...
fila[35] = GRUPO_GESTION
```

### Criterio de aceptación

Las 3.975 filas tienen `EVOLTIS` en la columna 36. Ninguna tiene `DEELO`.

### Detalle del feedback del cliente

> *"Grupo incorrecto: el dato que ingresa en la posición 36 del retorno es el grupo de gestión sobre el que se impactan las operaciones, solicitamos por favor se reemplace el valor DEELO por el valor EVOLTIS."*

---

## Bug #4 — Col 7: correlativo `1..N` en lugar de CALLREFID

### Contexto

Hoy el ETL copia el `CALLREFID` del LogCall a la col 7 (valores tipo `2685236001`). El cliente espera un **correlativo simple** del lote (valores `1` a `N`).

### Cambio

Línea 332:

```python
# ANTES
fila[6] = id_intento  # CALLREFID, 10 dígitos
```

Reemplazar por una asignación **post-loop**, después de construir todas las filas. En la función `procesar()`, después del filtro por campaña y antes de la validación de columnas (línea ~398):

```python
# Ordenar por timestamp para que el correlativo quede coherente
filas.sort(key=lambda r: r[0])

# Asignar correlativo 1..N a col 7
for i, fila in enumerate(filas, start=1):
    fila[6] = str(i)
```

### Decisión a confirmar con el cliente

Si después el cliente prefiere mantener el CALLREFID en la col 7 (porque el original del 27/01 muestra un patrón más complejo que un correlativo simple), revertir es trivial. Mientras tanto, el correlativo es la opción más segura para ser aceptada por el CRM.

### Criterio de aceptación

Col 7 contiene los valores `1, 2, 3, ..., N` (donde N = total de filas del lote), únicos, sin gaps.

---

## Bug #5 — Cols 15-16-17: descomposición telefónica desde M30OLOS

> **Este es el bug más complejo y el que más rechazos generó (257 de 295 en el feedback del cliente).**

### Causa raíz

El ETL actual descompone el `PHONE` de LogCall (E.164, ej. `5491123001415`) parseando "primeros 3 o 4 dígitos como código de área". Pero en Argentina las áreas son de longitud variable y muchos códigos válidos coexisten:

- `230` (Zárate, BA) ↔ `2302` (Mar de Ajó, BA)
- `387` (Salta) ↔ `3875` (no es área real)
- `294` (Bariloche) ↔ `2942` (no es área real)

La heurística falla: el ETL deja `2302` cuando el cliente envió `230`, arrastrando un dígito al área que pertenecía al número.

### Ejemplo del feedback del cliente (DU19098063)

| Origen | Área | Número | Tipo |
|---|---|---|---|
| Cliente envió (M30OLOS) | `230` | `152307331` | `CEL` |
| ETL actual devuelve | `2302` | `15307331` | `CEL` |
| Esperado | `230` | `152307331` | `CEL` |

### Solución correcta

**No descomponer el PHONE de LogCall. Tomar la descomposición exacta del M30OLOS del día.**

El M30OLOS tiene cada teléfono descompuesto correctamente:
- Cols 4-9: teléfono completo (`0230152307331`)
- Cols 12-29: descomposición `(área | número | tipo)` por slot

### Implementación

**Reemplazar la función `construir_indice_clientes()`** (líneas 158–210) por una versión que indexe la descomposición real:

```python
def construir_indice_clientes(m30olos_path: Path) -> dict:
    """
    Devuelve dict {customer_id: [(tel_full, area, num, tipo), ...]}
    a partir de las 6 ranuras de teléfono descompuestas del M30OLOS.

    Esta versión SOLO soporta el formato pipe del M30OLOS original
    (33 columnas). El formato CSV/punto y coma queda deprecado para
    el back-resultados.
    """
    from collections import defaultdict
    idx = defaultdict(list)

    with open(m30olos_path, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\r\n").split("|")
            if len(cols) < 33:
                continue
            cust = cols[0].strip()
            extended = cols[30].strip() if len(cols) > 30 else cust
            # 6 ranuras: (tel_full, area, num, tipo)
            for tel_i, area_i, num_i, tipo_i in [
                (3, 11, 12, 13),
                (4, 14, 15, 16),
                (5, 17, 18, 19),
                (6, 20, 21, 22),
                (7, 23, 24, 25),
                (8, 26, 27, 28),
            ]:
                tel_full = cols[tel_i].strip()
                area = cols[area_i].strip()
                num = cols[num_i].strip()
                tipo = cols[tipo_i].strip()
                if tel_full and area and num and tipo:
                    idx[cust].append({
                        "tel_full": tel_full,
                        "area": area,
                        "numero": num,
                        "tipo": tipo,
                        "extended_id": extended,
                    })
    return dict(idx)
```

**Agregar función de matcheo PHONE → descomposición**:

```python
def matchear_telefono(phone_logcall: str, tels_cliente: list[dict]) -> dict | None:
    """
    Recibe el PHONE del LogCall en E.164 (549... o 54...) y la lista
    de teléfonos del cliente desde el M30OLOS. Devuelve el primero
    cuya reconstrucción en E.164 coincida con phone_logcall.
    """
    if not phone_logcall or not phone_logcall.isdigit():
        return None

    for tel in tels_cliente:
        area = tel["area"]
        numero = tel["numero"]
        tipo = tel["tipo"]

        if tipo == "CEL":
            num_sin_15 = numero[2:] if numero.startswith("15") else numero
            e164 = "549" + area + num_sin_15
        else:  # TEL
            e164 = "54" + area + numero

        if phone_logcall == e164:
            return tel

    # Fallback: comparar últimos 8 dígitos
    last8 = phone_logcall[-8:]
    for tel in tels_cliente:
        if tel["tipo"] == "CEL":
            num_sin_15 = tel["numero"][2:] if tel["numero"].startswith("15") else tel["numero"]
            e164 = "549" + tel["area"] + num_sin_15
        else:
            e164 = "54" + tel["area"] + tel["numero"]
        if e164[-8:] == last8:
            return tel

    return None
```

**Modificar `construir_fila_usuolos()`** (líneas 257–348) para usar el matcheo nuevo:

```python
def construir_fila_usuolos(logcall_row, idx_historial, idx_clientes, anomalias):
    phone_raw = (logcall_row.get("PHONE") or "").strip()
    phone_clean = _clean_phone(phone_raw)
    if not phone_clean:
        anomalias["telefono_vacio"].append(logcall_row.get("CALLREFID", ""))
        return None

    # ... resto sin cambios hasta el bloque de teléfono ...

    # NUEVO: resolver customer_id + descomposición vía M30OLOS
    customer_id = ""
    extended_id = ""
    nacional = phone_clean
    area_code = ""
    tel_type = ""

    # Buscar el cliente cuyo PHONE de LogCall coincida con alguno de sus tels
    for cust_id, tels in idx_clientes.items():
        match = matchear_telefono(phone_raw, tels)
        if match:
            customer_id = cust_id
            extended_id = match["extended_id"]
            nacional = match["numero"]
            area_code = match["area"]
            tel_type = match["tipo"]
            break

    if not customer_id:
        anomalias["sin_customer_id"].append(
            f"CALLREFID={logcall_row.get('CALLREFID','')} PHONE={phone_clean}"
        )
    # ... resto sin cambios ...
```

### Optimización (importante)

La búsqueda lineal `for cust_id, tels in idx_clientes.items()` es O(N×M). Con 3.000 clientes y 6.000 filas de LogCall son 18 millones de comparaciones. Aceptable pero mejorable. **Alternativa**: agregar un índice inverso E.164 → customer_id:

```python
def construir_indice_clientes(m30olos_path):
    idx = defaultdict(list)
    e164_to_cust = {}  # NUEVO: lookup directo

    # ... mismo loop ...
    for tel in idx[cust]:
        if tel["tipo"] == "CEL":
            num_sin_15 = tel["numero"][2:] if tel["numero"].startswith("15") else tel["numero"]
            e164 = "549" + tel["area"] + num_sin_15
        else:
            e164 = "54" + tel["area"] + tel["numero"]
        e164_to_cust[e164] = (cust, tel)

    return dict(idx), e164_to_cust
```

Y en `construir_fila_usuolos`:

```python
match = e164_to_cust.get(phone_raw)
if match:
    customer_id, tel_info = match
    ...
```

Pasa de O(N×M) a O(N). En este lote: 18M operaciones → 6K. Diferencia notable en producción cuando la cartera escale.

### Criterio de aceptación

- Para cada fila del USUOLOS, las cols 15, 16, 17 son **idénticas** a las cols 13, 12, 14 del slot correspondiente del M30OLOS del cliente (área, número, tipo).
- Validación específica del caso del feedback: `DU19098063` debe tener `(número=152307331, área=230, tipo=CEL)`.
- Cobertura esperada en el lote 13/05: 3.785 de 3.975 filas (95%). Las 190 sin match permanecen con col 2 vacía (anomalía heredada).

---

## Bug #6 — Col 4: id_extendido con padding

### Cambio

Línea 329:

```python
# ANTES
fila[3] = extended_id if resultado == "PROMISE" else ""
```

Reemplazar por:

```python
# Padding a DU + 11 dígitos (13 chars total)
def id_extendido_con_padding(customer_id: str) -> str:
    if not customer_id or not customer_id.startswith("DU"):
        return ""
    numero = customer_id[2:]
    if not numero.isdigit():
        return ""
    return "DU" + numero.zfill(11)

...

fila[3] = id_extendido_con_padding(customer_id) if resultado == "PROMISE" else ""
```

### Criterio de aceptación

Para las 49 filas PROMISE: col 4 tiene siempre 13 caracteres y empieza con `DU`. Ejemplo: `DU4490406` → `DU00004490406`.

---

## Bug #7 — Col 28: punto → coma decimal

### Estado actual

El ETL **ya hace el replace** en la línea 302:

```python
monto_compromiso = monto_compromiso.replace(".", ",")
```

Pero en la **validación del archivo entregado** detectamos que algunos casos siguen con punto. Probablemente porque el monto viene con separador de miles (ej. `139.000.33`) y el replace global rompe esos casos.

### Cambio

Reemplazar el replace global por uno más robusto que detecte el separador decimal:

```python
def normalizar_monto(raw: str) -> str:
    """
    Convierte cualquier formato de monto al estándar del cliente:
    coma decimal, sin separadores de miles.
    Ej: '139000.33' -> '139000,33'
        '139,000.33' -> '139000,33'
        '139.000,33' -> '139000,33'
    """
    s = (raw or "").strip()
    if not s:
        return ""
    # Detectar separador decimal: el ÚLTIMO punto o coma es decimal
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    if last_dot > last_comma:
        # Punto es decimal, coma es separador de miles
        s = s.replace(",", "")
        s = s.replace(".", ",", 1)  # Solo el último
        # Pero pueden haber varios puntos: dejar solo el último
        parts = s.rsplit(",", 1)
        if "." in parts[0]:
            parts[0] = parts[0].replace(".", "")
        s = ",".join(parts)
    elif last_comma > last_dot:
        # Coma ya es decimal, punto es miles
        s = s.replace(".", "")
    else:
        # Solo hay un separador. Si está cerca del final (≤ 3 chars), es decimal
        if last_dot >= 0 and len(s) - last_dot - 1 <= 2:
            s = s[:last_dot] + "," + s[last_dot+1:]
        elif last_dot >= 0:
            # Es separador de miles
            s = s.replace(".", "")
    return s
```

Reemplazar la línea 302:

```python
# ANTES
monto_compromiso = monto_compromiso.replace(".", ",")

# DESPUÉS
monto_compromiso = normalizar_monto(monto_compromiso)
```

### Criterio de aceptación

Todas las filas PROMISE tienen col 28 con coma decimal y sin separadores de miles. Ejemplo aceptado: `139000,33`. Rechazado: `139.000,33`, `139.000.33`.

---

## Cambios de configuración (sin código, solo constantes)

Al tope del módulo, **agrupar todas las constantes editables**:

```python
# ===================================================================
# Configuración del formato de salida (alineado con feedback cliente)
# ===================================================================
OUTPUT_FILENAME_PREFIX = "DEELO_NAR_USUEVOLTIS_"
TIPO_REGISTRO = "USUEVOLTIS"        # col 8
GRUPO_GESTION = "EVOLTIS"           # col 36
SISTEMA_ORIGEN = "NARANJA"          # col 3
ACCION = "MAKE CALL"                # col 10
CANAL_BOT = "VOICEBOT"              # col 12 (cuando aplica)
ESTADO_PENDIENTE = "PENDING"        # col 39

USUOLOS_COLS = 40
CAMPANA_ACTIGROUP = "M"             # filtro Mora Temprana
RESULT_BOT = "10"                   # match con HISTORIAL

# ===================================================================
# Mapeo RESULT codes LogCall (pendiente confirmación cliente)
# ===================================================================
MAPEO_RESULT_LOGCALL = {
    "9": "MESSAGE",
    "1004": "VOLVER A LLAMAR",
    "7": "BUSY",
    "8": "NO ANSWER",
    "16": "VOLVER A LLAMAR",
}

# Resultado para RESULT=10 SIN match en HISTORIAL (pendiente confirmar)
RESULT_BOT_SIN_HISTORIAL = "VOLVER A LLAMAR"
```

Esto deja **6 puntos de configuración cliente** en un solo bloque del código. Cualquier cambio futuro se hace acá sin tocar la lógica.

---

## Plan de ejecución sugerido

### Fase 1 — Fixes rápidos (1 hora)

Aplicar bugs #1, #2, #3, #6, #7. Son cambios de 1 a 5 líneas cada uno. Después correr el ETL contra el lote 13/05 y validar:

- Nombre archivo correcto
- Col 8 = USUEVOLTIS
- Col 36 = EVOLTIS
- Col 4 con padding
- Col 28 con coma decimal

### Fase 2 — Fix de correlativo (30 min)

Aplicar bug #4 (col 7 correlativo). Validar:

- Col 7 = 1..N estricto
- Sin duplicados
- Sin gaps

### Fase 3 — Fix de descomposición telefónica (3 a 4 horas)

Aplicar bug #5 (el más complejo):

1. Reescribir `construir_indice_clientes` para soportar M30OLOS pipe-delimited con descomposición completa.
2. Agregar función `matchear_telefono`.
3. Modificar `construir_fila_usuolos` para usar el matcheo nuevo en lugar de la heurística actual.
4. Opcionalmente: índice inverso E.164 → customer_id para performance.

Validar:

- DU19098063: `(número=152307331, área=230, tipo=CEL)` exacto
- Los 257 rechazos del feedback corregidos
- Cobertura del 95% (3.785 / 3.975)

### Fase 4 — Validación contra USUOLOS aprobado (1 hora)

Diff byte-a-byte (o casi) contra `DEELO_NAR_USUEVOLTIS_20260513_16.txt` que ya validamos manualmente con el cliente. Si diff = 0, el ETL está alineado.

### Fase 5 — Actualizar documentación (30 min)

- `CLAUDE.md`: nueva sección "Cambios del feedback 13/05/2026" con resumen.
- Renombrar la sección "Back-resultados (NUEVO)" — sacar el "(NUEVO)" porque ya está en producción.
- Actualizar el ejemplo de output filename.

### Fase 6 — Tests automáticos (opcional, 1 hora)

Agregar tests a `back-resultados/tests/` que cubran:

1. Que el output empieza con `DEELO_NAR_USUEVOLTIS_`.
2. Que col 36 nunca sea `DEELO`.
3. Que las cols 15, 16, 17 de PROMISE sean idénticas a las del M30OLOS del cliente.
4. Caso DU19098063 (regression test del feedback).

---

## Cronograma total

| Fase | Esfuerzo |
|---|---|
| 1 — Fixes rápidos (#1, #2, #3, #6, #7) | 1 h |
| 2 — Correlativo (#4) | 30 min |
| 3 — Descomposición telefónica (#5) | 3-4 h |
| 4 — Validación contra USUOLOS aprobado | 1 h |
| 5 — Documentación | 30 min |
| 6 — Tests automáticos (opcional) | 1 h |
| **Total** | **6 a 8 horas** |

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El cliente cambia el nombre de archivo otra vez | `OUTPUT_FILENAME_PREFIX` está como constante al tope del módulo. Cambio = 1 línea. |
| El cliente confirma un mapeo distinto de RESULT codes | `MAPEO_RESULT_LOGCALL` también es constante. Cambio = editar el dict. |
| El M30OLOS del día llega tarde o no llega | Mantener fallback al método heurístico anterior con `try/except` y reportar la fila en anomalías. **Recomendación**: que el job aborte si no encuentra el M30OLOS del mismo día (mejor fallar fuerte que entregar archivo con teléfonos rotos). |
| Performance se degrada cuando la cartera escale a 50k+ clientes | Implementar el índice inverso E.164 → customer_id sugerido en Fase 3. Es O(N) vs el O(N×M) actual. |
| Hay otras anomalías del cliente que no se detectaron en este lote | Mantener el sistema de anomalías y revisar cada lote nuevo manualmente durante 2-3 semanas antes de automatizar al 100%. |

---

## Definiciones pendientes con el cliente

Estas decisiones no bloquean la implementación pero conviene cerrarlas antes de producción estable:

1. **Mapeo RESULT codes LogCall (7, 8, 9, 1004, 16)** — confirmar con documentación oficial del Logcall.
2. **Tratamiento de RESULT=10 sin match HISTORIAL** (167 casos en el lote) — `VOLVER A LLAMAR`, `HANGUP`, u otro.
3. **Col 7 (dato de secuencia)** — confirmar si el correlativo 1..N es lo que esperan o si necesitan otra regla. Tienen el USUOLOS del 27/01 con valores 1..21266 sin gaps pero desordenados temporalmente.
4. **Casos "Dificultad de pago" con compromiso_logrado=true sin monto** (4 casos) — definir si van como `PROMISE` o `PAYMENT DIFFICULTY` en col 11.
5. **Manejo de las 190 filas sin customer_id** — confirmar si el cliente está de acuerdo con que vayan con col 2 vacía o prefiere excluirlas.

---

## Estado del entregable final del lote 13/05

El archivo `DEELO_NAR_USUEVOLTIS_20260513_16.txt` que ya validamos manualmente con el cliente queda como **archivo de referencia / regression test**. El objetivo de este plan es que el ETL lo genere por sí mismo sin necesidad de scripts de post-procesamiento.

Una vez aplicados los 7 fixes, ejecutar:

```bash
python main.py --back
```

debería producir un archivo **byte-a-byte equivalente** al de referencia (salvo el timestamp del nombre, que dependerá de cuándo se corre).
