---
name: petersen-tipificaciones-logica
description: Replicates the Petersen typification (gestiones) generation logic agnostic of source systems. Use when the user asks to "generate tipificaciones de Petersen", "armar gestiones de Petersen", "replicar tipificaciones Petersen", build AG002_45/46/47/48 files, apply Petersen bank gestiones rules from any data source (Retell, ROMAN, Excel, DB dumps, APIs, manual files, etc.), validate payment promises (promesas de pago) under Petersen rules, or port the Petersen ETL logic to a new input format. Covers field mapping, validations, sanitization, deduplication, date rules, money formatting, and output CSV structure without assuming a specific input source.
---

# Petersen — Lógica de Generación de Tipificaciones (source-agnostic)

Este skill describe la **lógica de negocio** para construir los archivos de tipificaciones (gestiones) de Petersen a partir de cualquier fuente que contenga información de gestiones de cobranza. No asume nombres de archivo, estructura de carpetas ni sistemas de origen concretos: solo define qué campos deben obtenerse, cómo transformarlos y cómo validarlos.

## Alcance

Dada una colección de registros de gestión (cada registro = una interacción con un cliente), el skill explica cómo producir los CSV finales para los 4 bancos de Petersen, aplicando sanitización, validación y deduplicación.

---

## 1. Información de entrada requerida

Cada registro de gestión debe aportar (o permitir derivar) los siguientes campos lógicos. Los nombres son internos del skill; adaptarlos a la fuente real.

| Campo lógico | Tipo | Uso | Obligatoriedad |
|--------------|------|-----|----------------|
| `banco_gestionado` | string | Clasifica en qué banco va la gestión | Obligatorio para ruteo |
| `efecto` | string | Tipificación (PROMESA DE PAGO, YA PAGO, etc.) | Obligatorio; si vacío → descartar |
| `nro_cliente` | string | Identificador único del cliente | Obligatorio; si vacío → descartar |
| `sucursal` | string | Sucursal del cliente | Obligatorio en tipif. válidas |
| `nro_producto` | string | Número de producto del cliente | Obligatorio solo en promesas |
| `producto` | string | Texto del producto (ej. "Tarjeta de Crédito") | Obligatorio solo en promesas |
| `monto_promesa` | numérico/string | Monto prometido | Solo promesas |
| `deuda_vencida` | numérico/string | Deuda actual del cliente | Fallback de `monto_promesa` |
| `fecha_promesa` | string `dd/mm/yyyy` | Fecha prometida de pago | Solo promesas |
| `fecha_llamada` | string `dd/mm/yyyy` o `dd/mm/yyyy, HH:MM` | Fecha original de la llamada | Opcional; usada para `FECHA_ALTA` original |
| `motivo_atraso` | string libre | Motivo declarado | Obligatorio en promesas |
| `observaciones_gestion` | string libre | Notas de la gestión | Obligatorio en tipif. simples |
| `observaciones_promesa` | string libre | Notas de la promesa | Solo promesas |
| `canal_de_pago` | string | Canal acordado | Solo promesas |
| `usuario_asignado` | string | Usuario responsable | Obligatorio |

**Nota**: si la fuente provee múltiples "capas" (ej. un sistema primario + correcciones manuales), aplicar la lógica de prioridad **antes** de entrar al pipeline. Este skill opera sobre un único stream consolidado.

---

## 2. Bancos soportados y mapeo de salida

Solo se emiten registros para estos 4 bancos (descartar todo `banco_gestionado` que no coincida):

| `banco_gestionado` (entrada) | Código archivo | Sigla |
|------------------------------|----------------|-------|
| `Santa Fe` | `AG002_45` | `BSF` |
| `Entre Ríos` | `AG002_46` | `BER` |
| `Santa Cruz` | `AG002_47` | `BSC` |
| `San Juan` | `AG002_48` | `BSJ` |

Normalizar `Entre Rios` → `Entre Ríos` si la fuente llega sin tilde.

---

## 3. Estructura del CSV de salida

- **Separador**: `;` (punto y coma)
- **Encoding**: `UTF-8 con BOM` (`utf-8-sig`)
- **19 columnas en este orden exacto**:

```
Usuario asignado;GESTION_RELACIONADA;TIPO_PROMESA;NRO_CLIENTE;SUCURSAL;ACCION;EFECTO;CONTACTO;MOTIVO_ATRASO;OBSERVACIONES_GESTION;NRO_PRODUCTO;SUC_PRODUCTO;TIPO_PROD;FECHA_ALTA;FECHA_PROMESA;MONTO_PROMESA;CANAL_DE_PAGO;PUNTAJE_PROMESA;OBSERVACIONES_PROMESA
```

El header se escribe siempre. Todas las filas deben tener exactamente estas 19 columnas en este orden.

---

## 4. Clasificación por EFECTO

Toda fila con `efecto` vacío → **descartar**.
Toda fila con `efecto = RELLAMAR` (case-insensitive) → **descartar** (salvo que el caller pida expresamente incluir todos los efectos).

### 4.1. Promesa de pago
- `efecto.upper().strip()` ∈ { `PROMESA DE PAGO`, `PROMESA_DE_PAGO` }
- Activa reglas estrictas de fechas, montos, producto.

### 4.2. Tipificaciones simples (lista cerrada)
- `YA PAGO`
- `NOTIFICADO TITULAR`
- `NOTIFICADO FLIAR`
- `TELEFONO EQUIVOCADO`
- `DESCONOCE DEUDA`
- `NO AFRONTA DEUDA`
- `FALLECIDO`

En tipificaciones simples los campos de promesa y producto quedan **vacíos**.

### 4.3. Otros efectos (ej. `NO RESPONDE OCUPADO`)
- Se generan automáticamente cuando un cliente debería haber sido gestionado pero no tiene registro.
- Comportamiento idéntico a tipificación simple.
- Para `NO RESPONDE OCUPADO`: `OBSERVACIONES_GESTION = "Cliente no responde."`

---

## 5. Reglas por campo (mapeo lógico → salida)

### `Usuario asignado`
- Valor de `usuario_asignado`. En implementación actual: `"scesano"` por defecto.
- Aplicar sanitización de texto (ver §7).

### `GESTION_RELACIONADA`
- Siempre vacío (`""`).

### `TIPO_PROMESA`
- Valor fijo: `"PRINCIPAL"` en todas las gestiones válidas (promesas y simples).

### `NRO_CLIENTE`
- Copiar tal cual de `nro_cliente`. Si vacío → descartar la fila.

### `SUCURSAL`
- Copiar tal cual de `sucursal`.

### `ACCION`
- Valor fijo: `"LLAMADA SALIENTE"`.

### `EFECTO`
- Copiar `efecto` tras sanitización (sin comillas, `;` → `,`).
- Conservar mayúsculas tal como vienen.

### `CONTACTO`
Determinado por `efecto.upper().strip()`:
| EFECTO | CONTACTO |
|--------|----------|
| `NOTIFICADO FLIAR` | `FAMILIAR` |
| `TELEFONO EQUIVOCADO` | `BLANK` |
| cualquier otro | `CLIENTE` |

### `MOTIVO_ATRASO`
- **Promesa de pago**: obligatorio.
  - **Importante**: en la generación actual se fuerza literalmente a `"Otros"` para toda promesa (override global del valor de entrada).
  - Si se quiere preservar el valor real: aplicar normalización (sin tildes vía NFKD, eliminar caracteres no permitidos — permitir solo `[a-zA-Z0-9 ,.:;()\-]` más espacios —, colapsar espacios), truncar a **100 caracteres** en la fase inicial.
  - En el export final de promesas válidas: truncar a **50 caracteres**, aplicar sanitización (§7).
  - Si viene vacío y no se usa el override: rellenar con `"No aclara motivo de atraso"`.
- **Tipificaciones simples**: dejar **vacío**.

### `OBSERVACIONES_GESTION`
- Texto libre. Normalizar (sin tildes, sin caracteres especiales fuera del set permitido, espacios colapsados) y sanitizar (§7).
- **Obligatorio** en tipificaciones simples válidas.
- Para `NO RESPONDE OCUPADO` generado automáticamente: `"Cliente no responde."`

### `NRO_PRODUCTO`
- Copiar `nro_producto`.
- **Promesas**: obligatorio. Si vacío → promesa inválida.
- **Tipificaciones simples**: vacío.

### `SUC_PRODUCTO`
- Igual a `SUCURSAL` (misma sucursal del cliente).
- **Promesas**: obligatorio. **Simples**: vacío.

### `TIPO_PROD`
Mapear `producto` → código numérico:

1. Si `producto` contiene `,`, quedarse solo con el primer token (antes de la coma).
2. Normalizar: NFKD, quitar tildes, `.upper().strip()`.
3. Buscar substrings:

| Substring (ambas) | TIPO_PROD |
|-------------------|-----------|
| `TARJETA` y `CREDITO` | `"27"` |
| `PRESTAMO` | `"4"` |
| `CUENTA` y `CORRIENTE` | `"1"` |
| ninguno | `""` |

- **Promesas**: obligatorio (debe ser `"27"`, `"4"` o `"1"`). **Simples**: vacío.

### `FECHA_ALTA`
- Formato obligatorio: `dd/mm/yyyy`.
- **Tres modos** según la vista que se esté generando:
  1. **Vista "codificación" / "nombre"** (archivos principales): fijar a la **fecha de proceso (hoy)**.
  2. **Vista "fechas originales"** (archivo paralelo): usar la fecha extraída de `fecha_llamada` (tomar la parte antes de `,` si viene como `dd/mm/yyyy, HH:MM`). Si no se puede parsear, fallback a hoy.
  3. **Generación inicial (pre-export)**: usar `fecha_llamada` si existe, o un default inferido (ej. fecha del archivo/proceso).
- Obligatoria en promesas y tipificaciones simples.

### `FECHA_PROMESA`
Solo aplica a promesas. Formato: `dd/mm/yyyy`. **Validación y ajuste automático**:

1. Si vacío o no parseable → dejar vacío → promesa inválida.
2. Definir rango válido: `[hoy, hoy + 9 días]` (10 días corridos, incluyendo hoy).
3. Si `fecha_promesa < hoy`: buscar el **primer día hábil** (lunes–viernes) desde hoy avanzando hacia adelante dentro del rango. Si no se encuentra, fallback al último día hábil del rango.
4. Si `fecha_promesa > hoy + 9`: fijar al **último día hábil** dentro del rango (buscar desde el final hacia atrás).
5. Si `fecha_promesa` está dentro del rango pero cae en fin de semana: buscar el **último día hábil hacia atrás** desde esa fecha (sin bajar de hoy). Si no se encuentra, fallback al último día hábil del rango.
6. Si `fecha_promesa` está dentro del rango y es día hábil: mantener.

Regla adicional en validación final: `FECHA_PROMESA >= FECHA_ALTA` (mismo día permitido). Si menor → error.

En el export paralelo de "fechas originales": re-validar `FECHA_PROMESA` usando como ancla la `FECHA_ALTA` original (no hoy).

### `MONTO_PROMESA`
Solo promesas. Vacío en otras tipif.

1. Si `monto_promesa` vacío en una promesa → usar `deuda_vencida` como fallback.
2. Parsear: tolerar coma decimal (`"164906,64"` → `164906.64`), tolerar punto decimal.
3. Si es **cero** (`0`, `0.0`, `"0"`, `"0,00"`, `""`) → **dejar vacío** → promesa inválida.
4. Formato de salida **español** (en la fase de generación inicial): separador miles `.`, decimal `,`, 2 decimales.
   - `164906.64` → `"164.906,64"`
5. En el **export final** de promesas válidas: **eliminar el separador de miles** (solo eliminar puntos). Mantener coma decimal.
   - `"164.906,64"` → `"164906,64"`
6. Validación final: valor parseado debe ser estrictamente `> 0`.

### `CANAL_DE_PAGO`
- Copiar `canal_de_pago` tras sanitización (§7). Solo promesas; vacío en otras.

### `PUNTAJE_PROMESA`
- Promesas generadas automáticamente: **`"9"`** (confianza máxima).
- No-promesas: vacío.
- Obligatorio en promesas válidas.

### `OBSERVACIONES_PROMESA`
- Promesas: `"Promesa de pago registrada"` (sanitizado).
- No-promesas: vacío.

---

## 6. Validación de promesas (resumen de aceptación)

Una fila con `EFECTO = PROMESA DE PAGO` es **válida** si y solo si todos estos campos están completos y coherentes:

| Campo | Condición |
|-------|-----------|
| `Usuario asignado` | no vacío |
| `NRO_CLIENTE` | no vacío |
| `SUCURSAL` | no vacío (vía `SUC_PRODUCTO`) |
| `ACCION` | no vacío |
| `EFECTO` | `PROMESA DE PAGO` / `PROMESA_DE_PAGO` |
| `CONTACTO` | no vacío (default `CLIENTE`) |
| `TIPO_PROMESA` | no vacío (= `PRINCIPAL`) |
| `FECHA_ALTA` | fecha válida `dd/mm/yyyy` |
| `FECHA_PROMESA` | válida, ajustada, día hábil, dentro del rango, `>= FECHA_ALTA` |
| `MONTO_PROMESA` | numérico `> 0` |
| `PUNTAJE_PROMESA` | no vacío (default `"9"`) |
| `MOTIVO_ATRASO` | no vacío |
| `NRO_PRODUCTO` | no vacío |
| `SUC_PRODUCTO` | no vacío |
| `TIPO_PROD` | ∈ { `"27"`, `"4"`, `"1"` } |

Cualquier falla → promesa descartada del export final (pero sí queda en el stream "total" pre-validación).

### Validación de tipificaciones simples

Una fila con `EFECTO` ∈ {lista simple de §4.2} es **válida** si todos estos campos tienen valor:

- `Usuario asignado`
- `TIPO_PROMESA`
- `NRO_CLIENTE`
- `SUCURSAL`
- `ACCION`
- `EFECTO`
- `CONTACTO`
- `OBSERVACIONES_GESTION`
- `FECHA_ALTA`

Todos los demás campos deben **forzarse a vacío** en el export final (limpieza explícita: sobrescribir con `""`).

---

## 7. Sanitización de texto (aplicar a TODOS los campos textuales)

Antes de escribir cualquier campo de texto al CSV:

1. **Eliminar comillas**: quitar `"` y `'`.
2. **Reemplazar `;` por `,`** (no romper el separador).
3. Para campos con normalización adicional (`MOTIVO_ATRASO`, `OBSERVACIONES_GESTION`):
   - Aplicar `unicodedata.normalize("NFKD", text)` y eliminar caracteres combinantes (quita tildes/acentos).
   - Filtrar con regex `[^\w\s,.:;()\-]` → eliminar caracteres especiales no permitidos.
   - Colapsar espacios múltiples con `\s+` → `" "`, y `.strip()`.
   - Truncar al límite (100 en generación inicial, 50 en export final).

Aplicar sanitización básica como **último paso** antes de escribir la fila.

---

## 8. Deduplicación por cliente (export final)

En los archivos finales, **una única gestión por `NRO_CLIENTE` y banco**:

1. Agrupar filas por `NRO_CLIENTE` dentro de cada banco.
2. Si hay múltiples filas para el mismo cliente:
   - Si al menos una es `PROMESA DE PAGO` → conservar la **primera promesa** encontrada, descartar el resto.
   - Si ninguna es promesa → conservar la **primera** fila, descartar las demás.
3. Filas sin `NRO_CLIENTE` → no entran al dedup, pero también deberían haber sido descartadas antes por la validación.

Registrar los descartes para auditoría (nro_cliente, efectos descartados).

---

## 9. Flujo de procesamiento (end-to-end)

```
Entrada: colección de gestiones normalizadas (fuente-agnóstica)
   │
   ▼
[1] Filtrar:
    - descartar si efecto vacío
    - descartar si efecto == RELLAMAR (salvo override)
    - descartar si nro_cliente vacío
    - descartar si banco_gestionado no es uno de los 4
   │
   ▼
[2] Mapear cada fila al esquema de 19 columnas (reglas §5)
    - aplicar sanitización básica por campo
    - para promesas: aplicar override MOTIVO_ATRASO="Otros", fallback monto, validar fecha_promesa
   │
   ▼
[3] Separar por banco → 4 streams (uno por banco)
   │
   ▼
[4] Validar:
    - promesas → reglas §6 (descartar inválidas)
    - tipif. simples → campos obligatorios + limpiar campos no aplicables
   │
   ▼
[5] Deduplicar por NRO_CLIENTE (§8)
   │
   ▼
[6] Normalización final de salida:
    - MONTO_PROMESA: eliminar separador de miles
    - MOTIVO_ATRASO: truncar a 50, sanitizar
    - OBSERVACIONES_*: sanitizar
    - FECHA_ALTA: fijar a HOY (para vista principal) / preservar original (para vista paralela)
    - FECHA_PROMESA: re-validar contra la FECHA_ALTA aplicada
   │
   ▼
[7] Escribir CSV por banco con header + 19 columnas + separador ";" + UTF-8-BOM
    - nombre archivo codificación: AG002_45.csv / AG002_46.csv / AG002_47.csv / AG002_48.csv
    - nombre archivo descriptivo: gestiones_validas_BSF.csv / BER.csv / BSC.csv / BSJ.csv
```

Vistas que se generan típicamente (todas con los mismos datos, diferentes `FECHA_ALTA`):
1. **Codificación** (nombre AG002_XX): `FECHA_ALTA = hoy`.
2. **Nombre descriptivo** (gestiones_validas_BXX): `FECHA_ALTA = hoy`.
3. **Fechas originales** (gestiones_originales_BXX): `FECHA_ALTA = fecha de la llamada original`.

---

## 10. Fila "NO RESPONDE OCUPADO" (relleno automático)

Cuando la fuente indica clientes que debían ser gestionados pero no tienen gestión registrada (ej. de un reporte de llamadas no contestadas), generar una fila sintética:

```
Usuario asignado = scesano
GESTION_RELACIONADA = ""
TIPO_PROMESA = PRINCIPAL
NRO_CLIENTE = <del cliente>
SUCURSAL = <del cliente>
ACCION = LLAMADA SALIENTE
EFECTO = NO RESPONDE OCUPADO
CONTACTO = CLIENTE
MOTIVO_ATRASO = ""
OBSERVACIONES_GESTION = Cliente no responde.
NRO_PRODUCTO = ""
SUC_PRODUCTO = ""
TIPO_PROD = ""
FECHA_ALTA = hoy (dd/mm/yyyy)
FECHA_PROMESA = ""
MONTO_PROMESA = ""
CANAL_DE_PAGO = ""
PUNTAJE_PROMESA = ""
OBSERVACIONES_PROMESA = ""
```

Esta fila **no** entra al dedup por promesa (no es promesa), pero sí al dedup general por `NRO_CLIENTE`: solo agregar si el cliente **no tiene ya** otra gestión registrada para ese banco.

---

## 11. Ejemplo de fila final

**Promesa válida (Santa Fe)**:
```
scesano;;PRINCIPAL;300012345678;4;LLAMADA SALIENTE;PROMESA DE PAGO;CLIENTE;Otros;El cliente se compromete a abonar.;4567890;4;27;21/04/2026;28/04/2026;164906,64;TRANSFERENCIA;9;Promesa de pago registrada
```

**Tipificación simple (NOTIFICADO FLIAR, Entre Ríos)**:
```
scesano;;PRINCIPAL;300011108292;566;LLAMADA SALIENTE;NOTIFICADO FLIAR;FAMILIAR;;No se logra compromiso, atiende familiar y no esta el titular.;;;;13/04/2026;;;;;
```

---

## 12. Checklist para portar la lógica a una nueva fuente

1. [ ] Identificar en la fuente los 14 campos lógicos de §1 y mapear sus nombres reales.
2. [ ] Si hay varias capas de datos (primario + correcciones): aplicar prioridad **antes** de entrar al pipeline; producir un stream único.
3. [ ] Aplicar filtros de §9 paso [1].
4. [ ] Implementar mapeo §5 campo por campo (no saltar ninguno).
5. [ ] Implementar helpers:
    - `is_promesa_de_pago(efecto)` (case-insensitive, acepta ambas variantes).
    - `get_contacto(efecto)` con la tabla de §5.
    - `get_tipo_prod(producto)` con la lógica de substrings de §5.
    - `is_dia_habil(fecha)` (weekday < 5).
    - `validate_fecha_promesa(fecha_str, hoy)` con los 6 casos de §5.
    - `format_money_spanish(val)` → `"164.906,64"`.
    - `sanitize_text(s)` → quita comillas y `;`.
    - `normalize_and_truncate(s, max)` → NFKD + filtro regex + colapsar espacios + truncar.
6. [ ] Implementar validador de promesas (§6) que retorne errores por fila.
7. [ ] Implementar limpieza de tipif. simples (forzar campos no aplicables a `""`).
8. [ ] Implementar deduplicación por `NRO_CLIENTE` con prioridad de promesa (§8).
9. [ ] Escribir CSV con header, 19 columnas en orden, `;` como separador, encoding `utf-8-sig`.
10. [ ] Nombrar archivos según el mapeo de §2 (ambas variantes: codificación y descriptiva).
11. [ ] Si se requieren las 3 vistas (hoy / hoy / original): duplicar el paso de escritura ajustando `FECHA_ALTA` y re-validando `FECHA_PROMESA` en cada una.
12. [ ] (Opcional) Generar filas sintéticas `NO RESPONDE OCUPADO` para clientes no gestionados (§10).

---

## 13. Errores típicos a evitar

- **Separador**: usar `;`, no `,`. Si un campo contiene `;`, reemplazarlo por `,` (sanitización §7).
- **Encoding**: `utf-8-sig` (con BOM), no `utf-8` pelado — algunos consumidores lo requieren.
- **Fecha en fin de semana**: no aceptar nunca sábado/domingo en `FECHA_PROMESA`; siempre ajustar.
- **Monto cero**: `0`, `"0,00"`, etc. → promesa **inválida**, no enviar como `"0"`.
- **`TIPO_PROD`**: solo `"27"`, `"4"`, `"1"`. Cualquier otro valor invalida la promesa.
- **Mezcla de formatos de monto**: en fase inicial usar formato español con separador de miles; en export final quitarlo. Nunca mezclar.
- **Tildes en nombres de banco**: `Entre Ríos` con tilde. Normalizar si viene sin tilde.
- **`RELLAMAR`**: descartar por defecto; incluirlo solo si hay override explícito.
- **Duplicados**: si un cliente tiene una promesa + una tipif. simple, siempre gana la promesa.
- **Orden de columnas**: respetar exactamente las 19 en el orden dado. El consumidor lo valida posicionalmente.
- **`FECHA_PROMESA` < `FECHA_ALTA`**: inválido (aunque el mismo día sí se permite).
