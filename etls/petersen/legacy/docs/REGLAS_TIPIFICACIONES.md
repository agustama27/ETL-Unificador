### Reglas de tipificación – Vista orientada a campos

Este documento describe **la estructura final de una gestión** y las **reglas de negocio por campo**, independientemente de:
- De dónde viene la información (Retell, ROMAN, approach, excluidos, etc.).
- Cómo se ejecuta el flujo o en qué orden se corren los procesos.

La unidad básica es una **fila de gestión** (tipificación) con estos campos clave:

- `Usuario asignado`
- `GESTION_RELACIONADA`
- `TIPO_PROMESA`
- `NRO_CLIENTE`
- `SUCURSAL`
- `ACCION`
- `EFECTO`
- `CONTACTO`
- `MOTIVO_ATRASO`
- `OBSERVACIONES_GESTION`
- `NRO_PRODUCTO`
- `SUC_PRODUCTO`
- `TIPO_PROD`
- `FECHA_ALTA`
- `FECHA_PROMESA`
- `MONTO_PROMESA`
- `CANAL_DE_PAGO`
- `PUNTAJE_PROMESA`
- `OBSERVACIONES_PROMESA`

Todo lo que sigue explica **qué representa cada campo** y **cómo se valida según el tipo de tipificación**.


### 1. Tipos de tipificación (EFECTO) y su clasificación

- **Promesa de pago**:
  - `EFECTO` es `"PROMESA DE PAGO"` o `"PROMESA_DE_PAGO"` (insensible a mayúsculas/espacios).
  - Activa todas las reglas de negocio de **promesa** (fechas, montos, producto, puntaje, etc.).

- **Tipificaciones simples** (no financieras, de estado):
  - Valores considerados simples:
    - `"YA PAGO"`
    - `"NOTIFICADO TITULAR"`
    - `"NOTIFICADO FLIAR"`
    - `"TELEFONO EQUIVOCADO"`
    - `"DESCONOCE DEUDA"`
    - `"NO AFRONTA DEUDA"`
    - `"FALLECIDO"`
  - Tienen un conjunto reducido de campos obligatorios y el resto debe permanecer vacío.

- **Otras tipificaciones**:
  - Ejemplo: `"NO RESPONDE OCUPADO"` y otras que no entran en los grupos anteriores.
  - Suelen compartir estructura con las simples (no requieren campos de promesa).

En todos los casos, si `EFECTO` está vacío, la gestión **no es válida**.


### 2. Campos generales (aplican a casi todas las tipificaciones)

#### 2.1. `Usuario asignado`

- **Significado**: agente o usuario al que se le atribuye la gestión.
- **Reglas**:
  - Debe estar siempre informado en tipificaciones simples y promesas de pago válidas.
  - Se considera texto libre pero:
    - Se eliminan comillas (`"` y `'`).
    - Se reemplazan `;` por `,` para no romper el CSV.

#### 2.2. `NRO_CLIENTE`

- **Significado**: identificador único del cliente en el banco.
- **Reglas**:
  - Debe estar **siempre presente** en cualquier gestión que se conserve.
  - Es la clave primaria para:
    - Detectar duplicados y dejar **una sola gestión por cliente y banco** en los archivos “válidos”.
    - Evitar generar tipificaciones adicionales para clientes ya tipificados.
  - Si está vacío, la gestión se descarta.

#### 2.3. `SUCURSAL`

- **Significado**: sucursal donde está radicado el cliente o el producto principal.
- **Reglas**:
  - Obligatoria en tipificaciones simples y en promesas de pago válidas.
  - Se usa también para construir tipificaciones automáticas (ej. “NO RESPONDE OCUPADO”).

#### 2.4. `ACCION`

- **Significado**: tipo de acción realizada (por ejemplo, llamada saliente).
- **Reglas**:
  - En la práctica se estandariza a `"LLAMADA SALIENTE"` para las gestiones generadas por llamadas.
  - Obligatoria en tipificaciones simples y promesas.

#### 2.5. `EFECTO`

- **Significado**: resultado de la gestión (la tipificación propiamente dicha).
- **Reglas**:
  - No puede ser vacío.
  - Determina la **clase de tipificación**:
    - Promesa de pago (reglas estrictas de negocio).
    - Tipificación simple.
    - Otros efectos (ej. “NO RESPONDE OCUPADO”).
  - Se sanitiza texto (sin comillas, `;` → `,`).  

#### 2.6. `CONTACTO`

- **Significado**: quién fue contactado o con quién se interactuó.
- **Reglas de negocio principales**:
  - Si `EFECTO` es `"NOTIFICADO FLIAR"` → `CONTACTO = "FAMILIAR"`.
  - Si `EFECTO` es `"TELEFONO EQUIVOCADO"` → `CONTACTO = "BLANK"`
  - Para todos los demás efectos → `CONTACTO = "CLIENTE"` (valor por defecto).
  - Es obligatorio para tipificaciones simples.


### 3. Campos de contexto y observaciones

#### 3.1. `MOTIVO_ATRASO`

- **Significado**: explicación del motivo por el cual el cliente se encuentra en situación de atraso.
- **Reglas para promesa de pago**:
  - Es **obligatorio**.
  - Si viene vacío, se reemplaza por el texto fijo:
    - `"No aclara motivo de atraso"`.
  - En la generación inicial se normaliza:
    - Se eliminan acentos y caracteres especiales.
    - Se colapsan espacios múltiples.
    - Se trunca a un máximo de **100 caracteres**.
  - En los exports finales de promesas válidas:
    - Se trunca a máximo **50 caracteres**.
    - Se eliminan comillas.
    - Se reemplazan `;` por `,`.

- **Reglas para tipificaciones simples**:
  - En las tipificaciones simples “puras” seleccionadas, `MOTIVO_ATRASO` debe quedar vacío.

#### 3.2. `OBSERVACIONES_GESTION`

- **Significado**: texto libre con detalle de la gestión (lo que dijo el cliente, aclaraciones, etc.).
- **Reglas**:
  - Para tipificaciones simples utilizadas en los archivos válidos es **obligatorio**.
  - El contenido se normaliza:
    - Elimina acentos/tildes y caracteres especiales.
    - Elimina comillas.
    - Reemplaza `;` por `,`.
    - Se puede truncar (en práctica, se prioriza que no exceda límites razonables de longitud).

#### 3.3. `OBSERVACIONES_PROMESA`

- **Significado**: observaciones asociadas específicamente a la promesa de pago.
- **Reglas**:
  - Para promesas de pago generadas automáticamente se usa el texto fijo:
    - `"Promesa de pago registrada"`.
  - Se sanitiza igual que otros campos de texto (sin comillas, `;` → `,`).  
  - Para tipificaciones que no son promesa → debe quedar vacío.


### 4. Campos de producto

Estos campos describen el producto bancario asociado a la gestión.

#### 4.1. `NRO_PRODUCTO`

- **Significado**: identificador del producto (cuenta, préstamo, tarjeta, etc.).
- **Reglas**:
  - Es obligatorio en las **promesas de pago válidas**.
  - En tipificaciones simples exportadas como válidas, debe quedar vacío.

#### 4.2. `SUC_PRODUCTO`

- **Significado**: sucursal específica del producto.
- **Reglas**:
  - Obligatorio en las promesas de pago válidas.
  - En tipificaciones simples, debe quedar vacío.

#### 4.3. `TIPO_PROD`

- **Significado**: código numérico del tipo de producto.
- **Códigos de negocio válidos**:
  - `"27"` → Tarjeta de Crédito.
  - `"4"` → Préstamo.
  - `"1"` → Cuenta Corriente.
- **Reglas**:
  - Para promesas de pago válidas **debe** ser uno de esos códigos (si no, se considera error de validación).
  - En tipificaciones simples, debe estar vacío.


### 5. Campos de fechas

#### 5.1. `FECHA_ALTA`

- **Significado**: fecha de alta o registro de la gestión en el sistema destino.
- **Reglas generales**:
  - Siempre debe ser una fecha con formato `dd/mm/yyyy`.
  - Para archivos “válidos” que se entregan al banco:
    - Se fija a la **fecha de proceso** (hoy) en los archivos de “codificación” y “nombre”.
  - Para versiones con fecha original:
    - Se intenta preservar la fecha real de la llamada o del registro original.

- **Reglas de validación**:
  - Obligatoria en promesas de pago y tipificaciones simples válidas.
  - Se utiliza como referencia para comparar con `FECHA_PROMESA`.

#### 5.2. `FECHA_PROMESA`

- **Significado**: fecha en la que el cliente se compromete a realizar el pago.
- **Aplica solo a**: tipificaciones de **promesa de pago**.

- **Reglas de negocio (validación)**:
  - Debe existir para que la promesa sea considerada válida.
  - Debe ser una fecha válida en formato `dd/mm/yyyy`.
  - Debe ser **posterior a `FECHA_ALTA`** (si no, se considera error).
  - Además, se ajusta a un rango de **10 días corridos** a partir de la fecha de referencia (típicamente hoy):
    - Rango permitido: desde hoy (incluido) hasta hoy + 9 días.
    - Si la fecha propuesta es anterior a hoy → se mueve al primer día hábil dentro del rango.
    - Si es posterior al rango → se fija al **último día hábil** disponible dentro de los 10 días.
    - Si cae en fin de semana → se busca el **último día hábil** dentro del rango (hacia atrás).
  - Si no se puede interpretar como fecha válida → se deja vacía y la promesa se considera con error.


### 6. Campos monetarios y de canal

#### 6.1. `MONTO_PROMESA`

- **Significado**: importe comprometido a pagar en la promesa.
- **Reglas para promesa de pago**:
  - Debe ser **mayor a 0** (tras parseo en formato español).
  - Si viene vacío pero la gestión es promesa de pago:
    - Se usa como respaldo el valor de la deuda vencida (si está disponible).
  - Formato final en los archivos de salida:
    - Español: separador de miles `.` y separador decimal `,`, con 2 decimales.
    - Ejemplo: `164906.64` → `"164.906,64"`.
  - En algunos exports se normaliza quitando puntos de miles para mantener consistencia.
  - Si el valor numérico es 0 (`0`, `0.0`, `"0"`, `"0,00"`, etc.) → se deja vacío (no se considera promesa válida).

- **Reglas para otras tipificaciones**:
  - Debe estar vacío (no corresponde indicar monto).

#### 6.2. `CANAL_DE_PAGO`

- **Significado**: canal por el cual el cliente manifiesta que realizará el pago (caja, débito, web, etc.).
- **Reglas**:
  - Solo aplica a promesas de pago.
  - Para gestiones que no son promesa, el campo se deja vacío.
  - Se sanitiza texto (sin comillas, `;` → `,`).  

#### 6.3. `PUNTAJE_PROMESA`

- **Significado**: score o calificación de la promesa de pago.
- **Reglas**:
  - Para promesas de pago generadas automáticamente se fija en `"9"` (máxima confianza).
  - Para gestiones que no son promesa se deja vacío.
  - En la validación de negocio es un campo **obligatorio** para considerar la promesa como válida.


### 7. Campos de relación y metadatos

#### 7.1. `GESTION_RELACIONADA`

- **Significado**: identificador de una gestión anterior con la que esta tipificación se relaciona (encadenamiento).
- **Reglas**:
  - En la implementación actual se deja vacío (`""`) en la mayoría de los casos.
  - No interviene en las reglas de validación de negocio.

#### 7.2. `TIPO_PROMESA`

- **Significado**: tipo de promesa o indicador de prioridad.
- **Reglas**:
  - En la práctica se fija como `"PRINCIPAL"` para gestiones generadas automáticamente (incluyendo promesas y algunas tipificaciones adicionales).
  - Es considerado **obligatorio** tanto en promesas de pago válidas como en tipificaciones simples “válidas”.


### 8. Reglas específicas por tipo de tipificación

Esta sección resume, de forma compacta, qué campos deben estar completos o vacíos según el tipo de `EFECTO`.

#### 8.1. Promesa de pago (`EFECTO = PROMESA DE PAGO` / `PROMESA_DE_PAGO`)

- **Campos obligatorios** (no vacíos y coherentes):
  - `Usuario asignado`
  - `NRO_CLIENTE`
  - `SUCURSAL`
  - `ACCION`
  - `EFECTO` (específico de promesa)
  - `CONTACTO` (normalmente `"CLIENTE"`)
  - `TIPO_PROMESA`
  - `FECHA_ALTA` (fecha válida)
  - `FECHA_PROMESA` (fecha válida, dentro del rango permitido y **mayor** a `FECHA_ALTA`)
  - `MONTO_PROMESA` (monto > 0)
  - `PUNTAJE_PROMESA` (ej. `"9"`)
  - `MOTIVO_ATRASO` (texto no vacío, eventualmente normalizado)
  - `NRO_PRODUCTO`
  - `SUC_PRODUCTO`
  - `TIPO_PROD` ∈ {`"27"`, `"4"`, `"1"`}

- **Campos opcionales / derivados**:
  - `OBSERVACIONES_GESTION` (texto normalizado).
  - `OBSERVACIONES_PROMESA` (ej. `"Promesa de pago registrada"`).
  - `CANAL_DE_PAGO` (cuando se conoce el canal).

Si cualquiera de estos campos obligatorios no cumple las reglas, la promesa se marca como **con error** y no se incluye en el set de promesas válidas.

#### 8.2. Tipificaciones simples

Ejemplos: `YA PAGO`, `NOTIFICADO TITULAR`, `NOTIFICADO FLIAR`, `TELEFONO EQUIVOCADO`, `DESCONOCE DEUDA`, `NO AFRONTA DEUDA`, `FALLECIDO`.

- **Campos requeridos**:
  - `Usuario asignado`
  - `TIPO_PROMESA` (ej. `"PRINCIPAL"`)
  - `NRO_CLIENTE`
  - `SUCURSAL`
  - `ACCION`
  - `EFECTO`
  - `CONTACTO` (según la lógica de negocio, ej. `"FAMILIAR"` para NOTIFICADO FLIAR)
  - `OBSERVACIONES_GESTION`
  - `FECHA_ALTA`

- **Campos que deben estar vacíos**:
  - Todos los campos de promesa y producto:
    - `NRO_PRODUCTO`, `SUC_PRODUCTO`, `TIPO_PROD`,
    - `FECHA_PROMESA`, `MONTO_PROMESA`, `CANAL_DE_PAGO`,
    - `PUNTAJE_PROMESA`, `OBSERVACIONES_PROMESA`,
    - `MOTIVO_ATRASO` (para que queden “limpias” como tipificación simple).

Si falta alguno de los campos requeridos o hay información no vacía donde debe estar vacía, la fila se excluye de los archivos de “gestiones válidas”.

#### 8.3. Otras tipificaciones (ej. `NO RESPONDE OCUPADO`)

- Se comportan conceptualmente como tipificaciones simples:
  - Requieren los campos de identificación básicos (`Usuario asignado`, `NRO_CLIENTE`, `SUCURSAL`, `ACCION`, `EFECTO`, `CONTACTO`, `FECHA_ALTA`).
  - No deben tener campos de promesa ni de producto completados, salvo que se trate explícitamente de una promesa de pago.
  - El `MOTIVO_ATRASO` suele quedar vacío y se utiliza `OBSERVACIONES_GESTION` para describir la situación (ej. `"Cliente no responde."`).


### 9. Criterio de unicidad por cliente

En los archivos finales de **gestiones válidas por banco**:

- Se busca tener **una sola gestión por cliente** (`NRO_CLIENTE`) y banco.
- Cuando hay varias gestiones para el mismo cliente:
  - Si al menos una es promesa de pago → se prioriza la promesa de pago (se conserva una y se descartan las demás).
  - Si ninguna es promesa → se conserva la primera gestión y se descartan las otras.

Este criterio asegura que la vista “válida” sea compacta y priorice la información más relevante (la promesa).

