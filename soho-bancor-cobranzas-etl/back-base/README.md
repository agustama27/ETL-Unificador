# Procesamiento de Base de Clientes Bancor

Este módulo procesa archivos CSV de base de clientes bancarios, aplicando validaciones y transformaciones específicas para generar archivos consolidados.

## Estructura de Carpetas

- **base-recibida/**: Contiene los archivos CSV originales a procesar
- **base-generada/**: Contiene los archivos CSV procesados y consolidados (una fila por cliente único) y el archivo de teléfonos
- **debug/**: Contiene los archivos CSV con una fila por producto (para depuración)
- **backup/**: Contiene los clientes descartados por deduplicación de teléfonos
- **procesos/**: Contiene el código de procesamiento (`base_generator.py` y `phone_extractor.py`)

## Ejecución

Para ejecutar el procesamiento completo, ejecutar:

```bash
python back-base/main.py
```

El script ejecutará cuatro pasos en secuencia:

1. **Procesamiento de base con filtros** (`con-filtros/`): Filtra por `OFERTA_Importe > 0` y `ModuloCodigo == "201"`
2. **Procesamiento de base completa** (`sin-filtros/`): Filtra por `MontoAdeudado > 0` y excluye acuerdos vigentes
3. **Extracción de teléfonos** (con filtros): Extrae y consolida los celulares de la base filtrada
4. **Extracción de teléfonos** (sin filtros): Extrae y consolida los celulares de la base completa

## Validaciones y Procesamientos Aplicados

### 1. Lectura del Archivo CSV

- **Manejo de codificaciones**: El sistema intenta leer el archivo con diferentes codificaciones en el siguiente orden:
  - `latin-1`
  - `iso-8859-1`
  - `cp1252`
  - `utf-8`
  - `utf-16`
- **Separador**: Los archivos CSV utilizan punto y coma (`;`) como separador

### 2. Filtros de Filas

Los filtros varían según el tipo de base generada.

#### Base con filtros (`con-filtros/`)

##### 2.1. Filtro por OFERTA_Importe
- Se mantienen **únicamente** las filas donde `OFERTA_Importe > 0`
- Los valores numéricos utilizan formato europeo (coma como separador decimal, ej: `647114,99`)
- Se convierten automáticamente a formato numérico para la comparación

##### 2.2. Filtro por ModuloCodigo
- Se mantienen **únicamente** las filas donde `ModuloCodigo == "201"`
- El filtro es robusto y maneja valores numéricos o de texto

#### Base completa (`sin-filtros/`)

##### 2.3. Filtro por MontoAdeudado
- Se mantienen **únicamente** las filas donde `MontoAdeudado > 0`
- Excluye clientes sin deuda o con monto nulo

##### 2.4. Exclusión de acuerdos vigentes
Se excluyen las filas (a nivel de producto/operación individual) que cumplen **ambas** condiciones simultáneamente:

1. La columna `Gestion_Estado` tiene exactamente uno de estos valores:
   - `07. Promesa de Pago Pactada`
   - `08. Gestión de Refinanciación`

2. La columna `Fecha_Gestion` tiene **7 días o menos** de antigüedad respecto de la fecha actual:
   - `(hoy - Fecha_Gestion) <= 7 días`

**Ejemplos:**

| Fecha_Gestion | Hoy | Diferencia | ¿Se excluye? |
|---|---|---|---|
| 01/03/2026 | 06/03/2026 | 5 días | Sí (≤ 7 días) |
| 27/02/2026 | 06/03/2026 | 7 días | Sí (≤ 7 días) |
| 26/02/2026 | 06/03/2026 | 8 días | No (> 7 días) |
| 01/01/2026 | 06/03/2026 | 64 días | No (> 7 días) |

**Casos especiales:**
- Si `Fecha_Gestion` está vacía o tiene formato inválido → la fila **no se excluye**
- Si el cliente tiene otros productos sin acuerdo vigente → el cliente sigue apareciendo en la base (solo se descarta esa fila/producto)
- Las columnas `Gestion_Estado` y `Fecha_Gestion` se usan exclusivamente para este filtro y **no aparecen** en el archivo de salida

### 3. Selección de Columnas

El archivo resultante contiene únicamente las siguientes columnas:

- `Cliente_BT`
- `CUIL`
- `NumeroDocumento`
- `ClienteNombre`
- `NumeroTelefono`
- `NumeroCelular`
- `Mail`
- `Nro Cuenta`
- `AgrupadorProducto`
- `ModuloCodigo`
- `NumeroOperacion`
- `Dias_Mora`
- `MontoAdeudado`
- `OFERTA_Importe`

### 4. Limpieza de Datos

#### 4.1. NumeroDocumento y Nro Cuenta
- Se eliminan los decimales `.0` de estos campos
- Los valores se convierten a enteros sin decimales
- Valores nulos/vacíos se mantienen como string vacío

#### 4.2. Números de Teléfono (NumeroTelefono y NumeroCelular)
- Se eliminan los guiones `-` de los números de teléfono
- Ejemplo: `351-2043044` → `3512043044`
- **Número hardcodeado**: El valor `3519999999` se reemplaza automáticamente por un campo vacío (no se elimina la fila, solo se limpia el campo)

### 5. Generación de Archivos

El proceso genera **tres archivos**:

#### 5.1. Archivo Debug (`debug/`)
- **Nombre**: `debug_[nombre_archivo_original].csv`
- **Contenido**: Una fila por cada producto/cliente
- **Propósito**: Archivo de depuración que muestra todas las filas procesadas antes de la consolidación

#### 5.2. Archivo Consolidado (`base-generada/`)
- **Nombre**: `base_bancor_DDMMAAAA.csv` (donde DDMMAAAA es la fecha actual)
- **Contenido**: Una fila por cliente (consolidado)
- **Propósito**: Archivo final para uso operativo con todos los datos de clientes consolidados
- **Formato**: Separador punto y coma (`;`), codificación UTF-8

#### 5.3. Archivo de Teléfonos (`base-generada/`)
- **Nombre**: `telefonos_x_cliente_DDMMAAAA.csv` (donde DDMMAAAA es la fecha actual)
- **Contenido**: Lista de números de celular únicos, uno por línea
- **Propósito**: Archivo para el sistema de llamadas con números únicos a contactar
- **Formato**:
  - Una línea por número de celular
  - Sin encabezado
  - Sin duplicados
  - Ordenado alfabéticamente
  - Solo campo `NumeroCelular` (no incluye NumeroTelefono ni NumeroTrabajo)
- **Estructura**:
  ```
  3515415555
  3541229129
  3548505300
  3516750929
  ```

#### 5.4. Archivo de Descartados (`backup/`)
- **Nombre**: `descartados_por_telefono_DDMMAAAA.csv` (donde DDMMAAAA es la fecha actual)
- **Contenido**: Clientes descartados por tener teléfonos duplicados con otros clientes
- **Propósito**: Archivo de backup para auditoría y recuperación
- **Formato**: Mismo formato que el archivo consolidado (separador `;`, codificación UTF-8)

### 6. Consolidación por Cliente

Cuando un cliente tiene múltiples productos (múltiples filas con el mismo `Cliente_BT`), se aplican las siguientes reglas de consolidación:

#### 6.1. Campos que se Suman
- **MontoAdeudado**: Suma de todos los montos adeudados de los productos del cliente
- **OFERTA_Importe**: Suma de todos los importes de oferta de los productos del cliente

#### 6.2. Campos que se Toman el Máximo
- **Dias_Mora**: Se toma el valor máximo de días de mora entre todos los productos

#### 6.3. Campos que se Concatenan
- **NumeroOperacion**: Se concatenan todos los números de operación separados por comas
  - Ejemplo: `1234,4567,7890`
- **AgrupadorProducto**: Se concatenan todos los agrupadores de producto separados por comas
  - Ejemplo: `Tarjeta de Crédito,Préstamos Personales`

#### 6.4. Campos que se Toman de la Primera Fila
Para el resto de las columnas, se toman los valores de la primera fila del grupo, ya que deberían ser iguales para el mismo cliente:
- `Cliente_BT`
- `CUIL`
- `NumeroDocumento`
- `ClienteNombre`
- `NumeroTelefono`
- `NumeroCelular`
- `Mail`
- `Nro Cuenta`
- `ModuloCodigo`

### 7. Deduplicación por Teléfonos

Después de la consolidación por cliente, se aplica un proceso de deduplicación para eliminar clientes que comparten el mismo número de teléfono:

#### 7.1. Criterio de Duplicados
Se considera que dos clientes son duplicados si comparten **al menos uno** de los siguientes campos:
- `NumeroTelefono`
- `NumeroTrabajo`
- `NumeroCelular`

#### 7.2. Criterio de Selección
Cuando hay múltiples clientes que comparten teléfonos, se mantiene el cliente con:
1. **Mayor `MontoAdeudado`** (prioridad principal)
2. **Mayor cantidad de productos** (`NumeroOperacion` concatenados) en caso de empate

#### 7.3. Manejo de Descartados
- Los clientes descartados se guardan en la carpeta `backup/` con el nombre `descartados_por_telefono_DDMMAAAA.csv`
- Esto permite auditoría y recuperación si es necesario

#### 7.4. Casos Especiales
- **Clientes sin teléfono**: Se mantienen sin aplicar deduplicación (no hay teléfono para comparar)
- **Empate total**: Si dos clientes tienen exactamente la misma deuda y cantidad de productos, se mantiene el primero encontrado

## Formato de Salida

- **Separador**: Punto y coma (`;`)
- **Codificación**: UTF-8
- **Formato numérico**: Los valores numéricos se guardan con formato europeo (coma como separador decimal)
  - Ejemplo: `647114,99`

## Información de Procesamiento

Durante la ejecución, el script muestra información de depuración:

### Procesamiento de Base con Filtros (`con-filtros/`):
- Total de filas originales
- Cantidad de valores no nulos en OFERTA_Importe
- Cantidad de valores > 0 en OFERTA_Importe
- Cantidad de filas con ModuloCodigo == '201'
- Filas filtradas después de aplicar todos los filtros
- Valores reemplazados (número hardcodeado)
- Total de filas en archivo debug
- Total de filas en el archivo consolidado
- Cantidad de clientes únicos

### Procesamiento de Base Completa (`sin-filtros/`):
- Total de filas originales
- Filas con MontoAdeudado > 0
- Filas excluidas por MontoAdeudado <= 0 o nulo
- Valores reemplazados (número hardcodeado)
- **Filtro de acuerdos vigentes**:
  - Filas con Gestion_Estado de acuerdo (total, sin importar la fecha)
  - Filas con acuerdo vigente (≤ 7 días) — las que se excluyen
  - Desglose por estado (`07. Promesa de Pago Pactada` / `08. Gestión de Refinanciación`)
  - Filas antes y después del filtro
- Total de filas en archivo debug
- Total de filas en el archivo consolidado
- Cantidad de clientes únicos

### Deduplicación por Teléfonos:
- Filas antes de deduplicación
- Filas después de deduplicación
- Clientes descartados (guardados en carpeta backup)

### Extracción de Teléfonos:
- Archivo base leído (`base_bancor_DDMMAAAA.csv`)
- Total de filas leídas
- Total de celulares antes de deduplicar
- Total de celulares únicos
- Duplicados eliminados

## Extracción de Teléfonos

El proceso de extracción de teléfonos se ejecuta automáticamente después del procesamiento de la base y realiza las siguientes operaciones:

### Fuente de Datos
- Lee el archivo `base_bancor_DDMMAAAA.csv` generado en el paso anterior
- Extrae **solo** la columna `NumeroCelular`

### Procesamiento de Teléfonos
- **Extracción de celulares**: Solo se extraen los números de la columna `NumeroCelular`
- **Limpieza de datos**:
  - Elimina valores vacíos, nulos o inválidos
  - Elimina el sufijo `.0` si existe (cuando pandas convierte números)
  - Filtra valores como 'nan', 'NaN', 'None', etc.
- **Eliminación de duplicados**: Cada número aparece solo una vez
- **Ordenamiento**: Los números se ordenan alfabéticamente

### Características del Archivo Generado
- **Sin encabezado**: El archivo no incluye fila de encabezado
- **Una línea por número**: Cada número de celular aparece en una línea separada
- **Sin duplicados**: Cada número único aparece solo una vez
- **Solo celulares**: No incluye `NumeroTelefono` ni `NumeroTrabajo`

### Ejemplo de Estructura

```
3515415555
3541229129
3548505300
3516750929
```

En este ejemplo:
- Cada línea representa un número de celular único
- Los números están ordenados alfabéticamente
- No hay duplicados

## Notas Importantes

1. **Manejo de Errores**: Si un archivo no puede ser procesado, se muestra un mensaje de error y se continúa con el siguiente archivo
2. **Valores Vacíos**: Los valores nulos/NaN se convierten a string vacío en los campos de texto
3. **Duplicados**: En la consolidación, los valores únicos se mantienen (ej: si hay dos productos iguales, solo aparece una vez en la concatenación)
4. **Preservación de Datos**: El archivo debug siempre se genera para mantener un registro completo de todos los productos procesados
5. **Dependencia de Archivos**: El proceso de extracción de teléfonos requiere que primero se haya generado el archivo `base_bancor_DDMMAAAA.csv`. Si este archivo no existe, se mostrará un error indicando que se debe ejecutar primero el procesamiento de la base
6. **Fecha Consistente**: Ambos archivos (`base_bancor_DDMMAAAA.csv` y `telefonos_x_cliente_DDMMAAAA.csv`) usan la misma fecha, garantizando que correspondan a la misma ejecución

