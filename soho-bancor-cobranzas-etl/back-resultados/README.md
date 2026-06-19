# Procesamiento de Resultados de Llamadas Retell.ai - Bancor

Este módulo procesa los resultados de las llamadas obtenidas desde Retell.ai, extrayendo las variables dinámicas y datos postcall de cada llamada para generar un CSV consolidado con todas las gestiones.

## Estructura de Carpetas

```
back-resultados/
├── calls/              # Carpeta con archivos CSV que contienen los Call IDs
├── results/            # Carpeta donde se guardan los CSV generados
├── procesos/           # Módulos de procesamiento
│   ├── retell_manager.py      # Gestión de consultas a la API de Retell.ai
│   └── tipif_generator.py      # Generación del CSV de gestiones
└── main.py             # Script principal de ejecución
```

## Requisitos

### Dependencias Python

```bash
pip install pandas requests python-dotenv
```

### Variables de Entorno

Es necesario configurar la variable de entorno `RETELL_API_KEY` con tu clave de API de Retell.ai.

**Opción 1: Archivo `.env`** (recomendado)
```bash
# Crear archivo .env en la raíz del proyecto
RETELL_API_KEY=tu_api_key_aqui
```

**Opción 2: Variable de entorno del sistema**
```bash
# Windows (PowerShell)
$env:RETELL_API_KEY="tu_api_key_aqui"

# Linux/Mac
export RETELL_API_KEY="tu_api_key_aqui"
```

## Funcionamiento

El sistema ejecuta el siguiente flujo:

1. **Lectura del CSV de entrada**: Lee el archivo CSV de la carpeta `calls` que contiene los Call IDs
2. **Consulta a la API de Retell.ai**: Para cada Call ID, realiza una consulta GET a la API para obtener los datos completos de la llamada
3. **Extracción de datos**: Extrae las variables dinámicas (`retell_llm_dynamic_variables`) y datos postcall (`custom_analysis_data`) usando búsqueda recursiva
4. **Generación del CSV**: Crea un CSV donde cada fila es una llamada y las columnas son todas las variables extraídas

## Guía de Ejecución Paso a Paso

### Paso 1: Preparar el archivo CSV con Call IDs

1. Coloca un archivo CSV en la carpeta `calls/`
2. El CSV debe contener una columna con los Call IDs. La columna puede llamarse:
   - `Call ID`
   - `ID de Llamada`
   - `call_id`
   - `CallID`
   - `callId`

**Ejemplo de archivo CSV:**
```csv
Call ID,Fecha
call_d7a8655f20a25db3491d5cd4813,2026-01-15 10:00:00
call_abc123def456,2026-01-15 11:00:00
```

### Paso 2: Verificar la configuración

Asegúrate de que:
- ✅ La variable de entorno `RETELL_API_KEY` está configurada
- ✅ El archivo CSV está en la carpeta `calls/`
- ✅ Las dependencias están instaladas

### Paso 3: Ejecutar el script

```bash
python back-resultados/main.py
```

### Paso 4: Verificar el resultado

El CSV generado se guardará en la carpeta `results/` con el nombre:
```
gestiones_bancor_DDMMAAAA.csv
```

Donde `DDMMAAAA` es la fecha actual (ejemplo: `gestiones_bancor_15012026.csv`)

## Validaciones Realizadas

### 1. Validación de Estructura de Carpetas

- ✅ Verifica que la carpeta `calls/` existe
- ✅ Verifica que existe al menos un archivo CSV en `calls/`
- ✅ Si hay múltiples archivos CSV, procesa el primero y muestra una advertencia

### 2. Validación del Archivo CSV de Entrada

- ✅ **Detección automática de codificación**: Prueba múltiples codificaciones en orden:
  - `utf-8`
  - `latin-1`
  - `iso-8859-1`
  - `cp1252`
  - `utf-16`
- ✅ **Detección automática de separador**: Intenta primero con coma (`,`), luego con punto y coma (`;`)
- ✅ **Limpieza de nombres de columnas**: Elimina espacios en blanco al inicio y final
- ✅ **Validación de columna Call ID**: Verifica que existe una columna con los Call IDs
- ✅ **Filtrado de datos**: Elimina valores nulos y duplicados de los Call IDs

### 3. Validación de API Key

- ✅ Verifica que la variable de entorno `RETELL_API_KEY` esté configurada
- ✅ Lanza un error claro si no se encuentra la API key

### 4. Validación de Consultas a la API

- ✅ **Manejo de errores HTTP**: Captura y reporta errores de conexión o respuesta
- ✅ **Timeout**: Establece un timeout de 30 segundos por consulta
- ✅ **Validación de respuesta**: Verifica que la respuesta sea un diccionario válido
- ✅ **Manejo de llamadas fallidas**: Si una llamada falla, continúa con las siguientes y registra el error

### 5. Validación de Extracción de Datos

- ✅ **Búsqueda recursiva**: Busca los campos `retell_llm_dynamic_variables` y `custom_analysis_data` en cualquier nivel del payload
- ✅ **Manejo de estructuras anidadas**: Aplana diccionarios anidados correctamente
- ✅ **Conversión de tipos**: Convierte listas, None y otros tipos a formato adecuado
- ✅ **Validación de datos vacíos**: Maneja correctamente valores None, diccionarios vacíos y listas vacías

### 6. Validación del CSV Generado

- ✅ **Exclusión de columnas**: Elimina automáticamente las columnas:
  - `lk-call-info`
  - `lk-real-ip`
  - `lk-transport`
- ✅ **Limpieza de nombres**: Elimina prefijos `var_` y `postcall_` de los nombres de columnas
- ✅ **Manejo de columnas faltantes**: Si una llamada no tiene ciertas variables, se rellena con string vacío
- ✅ **Conversión de NaN**: Reemplaza valores NaN por strings vacíos
- ✅ **Ordenamiento de columnas**: Organiza las columnas con `call_id` primero, luego variables dinámicas, luego postcall

## Estructura del CSV Generado

### Columnas

El CSV generado contiene:

1. **`call_id`**: ID único de la llamada (siempre presente)
2. **Variables dinámicas**: Todas las variables encontradas en `retell_llm_dynamic_variables`
3. **Variables postcall**: Todos los datos encontrados en `custom_analysis_data`

### Formato

- **Separador**: Punto y coma (`;`) - formato europeo
- **Codificación**: UTF-8
- **Valores vacíos**: Representados como string vacío (`''`)
- **Valores nulos**: Convertidos a string vacío

### Ejemplo de Estructura

```csv
call_id;nombre;email;telefono;sentiment;summary
call_123;Juan Pérez;juan@email.com;1234567890;positive;Cliente interesado
call_456;María García;maria@email.com;0987654321;neutral;Consulta general
```

## Manejo de Errores

### Errores Comunes y Soluciones

#### Error: "No se encontró la variable de entorno RETELL_API_KEY"
**Solución**: Configura la variable de entorno o crea un archivo `.env` con tu API key.

#### Error: "No se encontraron archivos CSV en la carpeta calls"
**Solución**: Coloca un archivo CSV con los Call IDs en la carpeta `calls/`.

#### Error: "No se encontró ninguna columna de Call ID"
**Solución**: Asegúrate de que el CSV tenga una columna con uno de estos nombres:
- `Call ID`
- `ID de Llamada`
- `call_id`
- `CallID`
- `callId`

#### Error: "Error al obtener datos para Call ID..."
**Solución**: 
- Verifica que el Call ID sea válido
- Verifica tu conexión a internet
- Verifica que tu API key tenga permisos para acceder a ese Call ID

#### Error: "No se pudo leer el archivo con ninguna codificación"
**Solución**: El archivo CSV puede estar corrupto o usar una codificación no estándar. Intenta guardarlo nuevamente con codificación UTF-8.

## Información de Procesamiento

Durante la ejecución, el script muestra:

- ✅ Archivo CSV procesado
- ✅ Número de Call IDs encontrados
- ✅ Progreso de consultas a la API (X/Total)
- ✅ Estado de cada llamada procesada
- ✅ Columnas excluidas (si aplica)
- ✅ Resumen final con total de llamadas y columnas generadas

## Notas Importantes

1. **Múltiples archivos CSV**: Si hay múltiples archivos CSV en `calls/`, solo se procesa el primero. Se muestra una advertencia.

2. **Búsqueda recursiva**: El sistema busca los campos necesarios en cualquier nivel del payload de respuesta, por lo que funciona aunque Retell.ai cambie la estructura de su API.

3. **Columnas dinámicas**: Las columnas del CSV final dependen de las variables presentes en las llamadas. Si una llamada tiene variables que otra no tiene, se rellenan con valores vacíos.

4. **Rendimiento**: El proceso puede tardar varios minutos si hay muchas llamadas, ya que se consulta la API una por una.

5. **Archivos generados**: Cada ejecución genera un nuevo archivo con la fecha actual. Los archivos anteriores se mantienen en la carpeta `results/`.

## Ejemplo de Uso Completo

```bash
# 1. Configurar API key (una sola vez)
echo "RETELL_API_KEY=tu_api_key" > .env

# 2. Colocar archivo CSV en calls/
# calls/historial_llamadas.csv

# 3. Ejecutar
python back-resultados/main.py

# 4. Resultado en results/
# results/gestiones_bancor_15012026.csv
```

## Soporte

Para problemas o consultas, revisa:
- Los mensajes de error en la consola
- Los logs de ejecución
- La estructura del archivo CSV de entrada
- La configuración de la API key

