# soho-petersen-etl

ETL para procesamiento de datos de Grupo Petersen. Consolida información de clientes, productos y contactos de múltiples bancos del grupo en una tabla integradora única.

## 🚀 Quickstart

### 1. Instalación

```powershell
# Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Preparar archivos de entrada

Coloca los archivos en `inputs/petersen/incoming/` con el siguiente formato de nombre:
- `YYYYMMDD_AG002_BERC3BUC_INTEGRACION.csv` (datos de clientes)
- `YYYYMMDD_AG002_BERC3BUC_PRODCLI_DEELO.csv` (productos y deudas)
- `YYYYMMDD_AG002_BERC3BUC_MAILCLI.xls` (emails, opcional)

### 3. Ejecutar ETL

```powershell
# Ejecución básica (procesa todos los archivos encontrados)
python etl.py

# Con límite de clientes
python etl.py --max-clients 5000

# Con logging detallado
python etl.py --log-level INFO
```

### 4. Revisar archivos de salida

Los archivos se generan en `data/petersen/` con timestamp único:
- `tabla_integradora_YYYYMMDD_HHMMSS.csv` - Tabla principal consolidada
- `telefonos_YYYYMMDD_HHMMSS.csv` - Listado completo de teléfonos únicos
- `telefonos_petersen_YYYYMMDD_HHMMSS.txt` - Teléfonos únicos (formato simple)
- `telefonos_tel1_YYYYMMDD_HHMMSS.txt` - Solo teléfonos TEL1
- `telefonos_petersen_por_cliente_YYYYMMDD_HHMMSS.csv` - Teléfonos agrupados por cliente

---

## 📋 Dominio del ETL

### ¿Qué hace este ETL?

Este ETL procesa datos de **Grupo Petersen** (Banco Entre Ríos, Banco Santa Fe, Banco San Juan, Banco Santa Cruz) y genera una **tabla integradora** que consolida:

1. **Datos de clientes** (desde INTEGRACION.csv)
   - Información personal (nombre, documento, DAT3 como ID único)
   - Datos de contacto (teléfonos en TEL1, TEL2, TEL3, TEL4)
   - Segmentación y scoring
   - Cartera y nivel de riesgo

2. **Productos y deudas** (desde PRODCLI_DEELO.csv)
   - Tipos de productos (Préstamos, Tarjeta de Crédito, Cuenta Corriente)
   - Deuda vencida consolidada por cliente
   - Números de operación

3. **Emails** (desde MAILCLI.xls, opcional)
   - Email registrado por cliente

### Proceso de Transformación

El ETL realiza las siguientes transformaciones automáticas:

1. **Agrupación por banco y fecha**: Los archivos se agrupan por código de banco (BER, BSF, BSJ, BSC) y fecha (YYYYMMDD)

2. **Filtrado automático de carteras**: Solo procesa carteras permitidas (ver sección de configuración)

3. **Merge de datos**: 
   - Clientes (DAT3) ↔ Productos (NUMERO CLIENTE)
   - Consolidación de múltiples productos por cliente
   - Suma de deudas vencidas

4. **Enriquecimiento con emails**: Vinculación de emails desde MAILCLI usando DAT3

5. **Validaciones y limpieza**:
   - Deduplicación de teléfonos (prioridad TEL1 > TEL2 > TEL3 > TEL4)
   - Normalización de encoding (corrige "R¡os" → "Ríos" en DAT6)
   - Formateo de deudas (2 decimales)
   - Exclusión de columnas sensibles (DAT8, DAT9)

---

## 📥 Archivos de Entrada

### Ubicación

Todos los archivos de entrada deben estar en: `inputs/petersen/incoming/`

### Formato de nombres

Los archivos deben seguir este patrón para ser detectados automáticamente:

```
YYYYMMDD_AG002_BERC3BUC_INTEGRACION.csv
YYYYMMDD_AG002_BERC3BUC_PRODCLI_DEELO.csv
YYYYMMDD_AG002_BERC3BUC_MAILCLI.xls
```

Donde:
- `YYYYMMDD`: Fecha en formato año-mes-día (ej: 20251218)
- `BERC3BUC`: Código del banco (BER, BSF, BSJ, BSC)
- El tipo de archivo se identifica por palabras clave en el nombre

### Tipos de archivos

#### 1. INTEGRACION.csv (Requerido)

**Descripción**: Datos de clientes con información personal y de contacto.

**Columnas clave**:
- `DAT3`: ID único del cliente (usado para merge con productos)
- `NOMBRE Y APELLIDO`: Nombre completo
- `TEL1`, `TEL2`, `TEL3`, `TEL4`: Teléfonos de contacto
- `CARTERA - SEGMENTO`: Segmento de cartera (ej: "3 - 3_SA_RM_T1")
- `DEUDA VENCIDA`: Deuda vencida del cliente
- `DAT6`: Nombre del banco (ej: "Banco de Entre Ríos")

**Ejemplo de nombre**: `20251218_AG002_BERC3BUC_INTEGRACION.csv`

#### 2. PRODCLI_DEELO.csv (Requerido)

**Descripción**: Productos y deudas detalladas por cliente.

**Columnas clave**:
- `NUMERO CLIENTE`: ID del cliente (debe coincidir con DAT3 de INTEGRACION)
- `TIPO DE PRODUCTO`: Tipo de producto (Préstamos, Tarjeta de Crédito, etc.)
- `DEUDA VENCIDA`: Deuda vencida del producto
- `NUMERO DE OPERACION`: Número de operación del producto
- `SUCURSAL`: Código de sucursal

**Ejemplo de nombre**: `20251218_AG002_BERC3BUC_PRODCLI_DEELO.csv`

**Nota**: Un cliente puede tener múltiples productos. El ETL consolida todos los productos en una sola fila:
- `TIPO DE PRODUCTO`: Concatenación separada por coma (ej: "Préstamos, Tarjeta de Crédito")
- `DEUDA VENCIDA_PROD`: Suma de todas las deudas vencidas

#### 3. MAILCLI.xls (Opcional)

**Descripción**: Emails registrados por cliente.

**Columnas clave**:
- `DAT3` o columna equivalente: ID del cliente
- Columna con email: Se detecta automáticamente

**Ejemplo de nombre**: `20251218_AG002_BERC3BUC_MAILCLI.xls`

**Nota**: Si no se encuentra este archivo, el proceso continúa sin emails. La columna `email_registrado` quedará vacía.

---

## 📤 Archivos de Salida

Todos los archivos se generan en la carpeta especificada con `--output` (default: `data/petersen/`).

**Formato de encoding**: Todos los archivos se guardan en **UTF-8 con BOM** (`utf-8-sig`) para compatibilidad con Excel/Windows.

**Separador CSV**: Punto y coma (`;`)

### 1. tabla_integradora_YYYYMMDD_HHMMSS.csv ⭐ **ARCHIVO PRINCIPAL**

**Descripción**: Tabla consolidada con todos los datos de clientes, productos y contactos.

**Contenido**:
- **Datos de clientes**: Nombre, documento, DAT3, segmentación, scoring
- **Teléfonos**: TEL1, TEL2, TEL3, TEL4 (ya deduplicados globalmente)
- **Productos consolidados**: 
  - `TIPO DE PRODUCTO`: Lista de productos separados por coma
  - `DEUDA VENCIDA_PROD`: Suma total de deuda vencida (formateada a 2 decimales)
- **Email**: `email_registrado` (si está disponible desde MAILCLI)
- **Metadatos**: Banco, sucursal, número de operación, etc.

**Características especiales**:
- ✅ Teléfonos deduplicados: Si un número aparece en TEL1 de un cliente y TEL2 de otro, solo queda en TEL1 del primer cliente
- ✅ Deudas formateadas: `DEUDA VENCIDA_PROD` siempre tiene 2 decimales (ej: `777601.43`)
- ✅ Encoding corregido: `DAT6` con nombres de bancos correctos (ej: "Banco de Entre Ríos" en lugar de "Banco de Entre R¡os")
- ✅ Sin columnas sensibles: DAT8 y DAT9 son excluidas automáticamente

**Uso**: Este es el archivo principal para análisis, reporting y carga a sistemas downstream.

### 2. telefonos_YYYYMMDD_HHMMSS.csv

**Descripción**: Listado completo de teléfonos únicos con referencia al cliente.

**Formato**:
```csv
Telefono;DAT3
+5493456029665;20307838053
+5493447523431;20307836077
```

**Características**:
- Un teléfono por fila
- Incluye `DAT3` para vincular con la tabla integradora
- Teléfonos únicos (sin duplicados)
- Prioridad: Si un número aparece en TEL1 y TEL2, se asigna al cliente que lo tiene en TEL1

**Uso**: Para sistemas de llamadas que necesitan listado de teléfonos con referencia al cliente.

### 3. telefonos_petersen_YYYYMMDD_HHMMSS.txt

**Descripción**: Listado simple de teléfonos únicos, un teléfono por línea.

**Formato**:
```
+5493456029665
+5493447523431
+5493454019837
```

**Características**:
- Un teléfono por línea
- Sin metadatos ni headers
- Todos los teléfonos con prefijo `+549`
- Teléfonos únicos (sin duplicados)
- Incluye todos los teléfonos de TEL1, TEL2, TEL3, TEL4

**Uso**: Para sistemas de llamadas que solo necesitan el listado de números sin metadatos.

### 4. telefonos_tel1_YYYYMMDD_HHMMSS.txt

**Descripción**: Solo teléfonos de la columna TEL1 (teléfono principal).

**Formato**:
```
+5493456029665
+5493447523431
+5493454019837
```

**Características**:
- Un teléfono por línea
- Solo incluye TEL1 (teléfono principal de cada cliente)
- Todos con prefijo `+549`
- Teléfonos únicos

**Uso**: Para campañas que solo usan el teléfono principal de cada cliente.

### 5. telefonos_petersen_por_cliente_YYYYMMDD_HHMMSS.csv

**Descripción**: Teléfonos agrupados por cliente, todos los teléfonos de un cliente en una sola línea.

**Formato**:
```csv
3456029665,3454485586,3454339200,3455032984
3447523431,3454076901,3447590502,3454076901
3454019837,3454400185
```

**Características**:
- Una línea por cliente
- Teléfonos separados por coma
- Incluye TEL1, TEL2, TEL3, TEL4 (solo los que tienen valor)
- Teléfonos tal cual aparecen en la base (sin prefijo +549)
- Ordenados por cantidad de teléfonos (clientes con más teléfonos primero)

**Uso**: Para sistemas que necesitan todos los teléfonos de un cliente en un solo campo.

---

## ⚙️ Parámetros

### Parámetros disponibles

```powershell
python etl.py [opciones]
```

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--input` | Carpeta con archivos de entrada | `inputs/petersen/incoming` |
| `--output` | Carpeta de salida | `data/petersen` |
| `--max-clients` | Máximo de filas en tabla integradora final | `10000` |
| `--cartera` | Filtro adicional por cartera (ej: `"3 - 3_SA_RM_T2"`) | Ninguno |
| `--early-limit-per-bank` | Límite temprano por banco (solo performance) | `0` (desactivado) |
| `--log-level` | Nivel de logging: BASIC, INFO, DEBUG, WARNING, ERROR | `BASIC` |
| `--config` | Ruta al archivo de configuración YAML | `config/petersen.yaml` |

### Ejemplos de uso

```powershell
# Ejecución básica
python etl.py

# Procesar máximo 5000 clientes
python etl.py --max-clients 5000

# Filtrar adicionalmente por cartera específica
python etl.py --cartera "3 - 3_SA_RM_T2"

# Activar logging detallado
python etl.py --log-level INFO

# Especificar carpetas personalizadas
python etl.py --input mi_carpeta/entrada --output mi_carpeta/salida

# Combinar múltiples parámetros
python etl.py --max-clients 3000 --log-level DEBUG --cartera "3 - 3_MONOTRIBUTO_RM_T1"
```

---

## 🔧 Configuración

### Filtro Automático de Carteras

El ETL aplica **automáticamente** un filtro por las siguientes carteras permitidas:

- `3_SA_RM_T2`
- `3_SA_RM_T1`
- `3_SA_RB_T2`
- `3_SA_RB_T1`
- `3_NA_RM_T1`
- `3_NA_RB_T1`
- `3_MONOTRIBUTO_RM_T1`
- `3_MONOTRIBUTO_RB_T1`

**Importante**: Este filtro se aplica **siempre**, independientemente de otros parámetros. Si especificas `--cartera`, se aplica como un filtro **adicional** sobre las carteras ya filtradas.

### Configuración de Logging

El nivel de logging puede configurarse de tres formas (en orden de prioridad):

1. **Parámetro `--log-level`** en línea de comandos (máxima prioridad)
2. **Variable de entorno** `LOG_LEVEL`
3. **Archivo de configuración** `config/petersen.yaml`:

```yaml
logging:
  level: BASIC  # BASIC, INFO, DEBUG, WARNING, ERROR
```

---

## ✅ Validaciones Automáticas

El ETL realiza las siguientes validaciones y transformaciones automáticas:

### 1. Deduplicación de Teléfonos

**Problema**: Un mismo número puede aparecer en diferentes clientes y/o columnas.

**Solución**: 
- Prioridad: TEL1 > TEL2 > TEL3 > TEL4
- Si un número está en TEL1 de un cliente y TEL2 de otro, se mantiene solo en TEL1 del primer cliente
- Si hay empate (mismo número en la misma columna de dos clientes), se mantiene en el primero que aparece

**Resultado**: Cada número de teléfono aparece solo una vez en toda la base.

### 2. Normalización de Encoding

**Problema**: Nombres de bancos con caracteres mal codificados (ej: "Banco de Entre R¡os").

**Solución**: Corrección automática de problemas de encoding Windows-1252 → UTF-8.

**Resultado**: `DAT6` siempre tiene nombres correctos (ej: "Banco de Entre Ríos").

### 3. Formateo de Deudas

**Problema**: Valores con muchos decimales por errores de punto flotante (ej: `777601.4299999999`).

**Solución**: Redondeo a 2 decimales con formato fijo.

**Resultado**: `DEUDA VENCIDA_PROD` siempre tiene formato `XXXXXX.XX`.

### 4. Validación de Columnas

- **SUCURSAL**: Verifica existencia en PRODCLI_DEELO (advertencia si no existe)
- **NUMERO DE OPERACION**: Valida correspondencia con tipo de producto

**Nota**: Las validaciones no abortan el proceso, solo generan advertencias en el log.

### 5. Exclusión de Columnas Sensibles

Las columnas `DAT8` y `DAT9` son excluidas automáticamente de la tabla integradora final.

---

## 📊 Estructura del Proyecto

```
soho-petersen-etl/
├── adapters/petersen/    # Módulos de ingestión de datos
│   ├── simple_ingest.py  # Carga INTEGRACION, PRODCLI_DEELO, MAILCLI
│   └── ...
├── procesos/             # Lógica de transformación
│   ├── simple_merge.py   # Merge de clientes y productos
│   └── mail_merge.py     # Enriquecimiento con emails
├── lib/common/           # Utilidades comunes
│   ├── validations.py    # Validaciones y deduplicación
│   ├── phone_normalize.py # Normalización de teléfonos
│   └── ...
├── config/               # Archivos de configuración
│   └── petersen.yaml     # Configuración del ETL
├── data/                 # Datos procesados (generados)
│   └── petersen/         # Archivos de salida
├── inputs/               # Archivos de entrada
│   └── petersen/
│       └── incoming/     # Colocar archivos aquí
├── tools/                # Herramientas auxiliares
│   └── dedupe_phones_csv.py  # Script para deduplicar CSV existente
├── etl.py                # Script principal del ETL
└── README.md             # Esta documentación
```

---

## 🧪 Tests

```powershell
# Ejecutar tests básicos
python test_etl.py
python test_simple_etl.py
```

---

## 🔍 Troubleshooting

### Problema: No se detectan los archivos

**Solución**: Verifica que:
1. Los archivos estén en `inputs/petersen/incoming/`
2. Los nombres sigan el formato: `YYYYMMDD_AG002_BERC3BUC_INTEGRACION.csv`
3. Los archivos tengan extensión `.csv` o `.xls`/`.xlsx`

### Problema: "No se encontraron archivos INTEGRACION.csv o PRODCLI_DEELO.csv"

**Solución**: 
- Verifica que los archivos tengan las palabras clave `INTEGRACION` y `PRODCLI_DEELO` en el nombre
- Verifica que tengan código de banco válido (BER, BSF, BSJ, BSC) y fecha en formato YYYYMMDD

### Problema: Teléfonos duplicados en la salida

**Solución**: La deduplicación se aplica automáticamente. Si ves duplicados, verifica:
- Que estés usando la versión más reciente del ETL
- Que los teléfonos estén en las columnas TEL1, TEL2, TEL3, TEL4

### Problema: "Banco de Entre R¡os" en lugar de "Banco de Entre Ríos"

**Solución**: Esta corrección se aplica automáticamente desde la versión actual. Si persiste, verifica que estés usando la última versión del código.

---

## 📝 Notas Adicionales

- **Encoding**: Todos los archivos se procesan y generan en UTF-8 con BOM para compatibilidad con Excel
- **Separador CSV**: Se usa punto y coma (`;`) como separador estándar
- **Performance**: Para grandes volúmenes, considera usar `--early-limit-per-bank` (solo si es necesario)
- **Límite de clientes**: `--max-clients` se aplica **al final** sobre el número de filas, no sobre clientes únicos

---

## 📞 Soporte

Para problemas o consultas, revisa los logs con `--log-level DEBUG` para información detallada del proceso.
