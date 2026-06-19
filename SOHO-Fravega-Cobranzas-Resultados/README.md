# SOHO Fravega Cobranzas - Generador de Resultados

Sistema para procesar bases de datos de Fravega y generar reportes de gestiones de cobranza a partir de llamadas de Retell.

## 📋 Estructura del Proyecto

```
fravega-generadorBase/
├── back-base/              # Procesamiento de bases de datos
│   ├── base_recibida/      # 📥 Carpeta para cargar archivos CSV recibidos
│   ├── base_procesada/     # 📤 Carpeta con archivos CSV procesados
│   ├── procesos/
│   │   └── clean_base.py   # Script de limpieza de datos
│   └── main.py             # Entrypoint principal
│
└── back-resultados/        # Generación de reportes de Retell
    ├── retell/             # 📥 Carpeta para cargar exports de Retell (obligatorio)
    ├── roman/              # 📥 Carpeta para cargar exports de ROMAN (opcional)
    ├── results/            # 📤 Carpeta con CSVs generados
    ├── procesos/
    │   ├── retell-manager.py      # Gestor de API de Retell + merge ROMAN
    │   └── tipif_generator.py     # Generador de tipificaciones
    └── main.py             # Entrypoint principal
```

## 🚀 Inicio Rápido

### Requisitos Previos

1. **Python 3.8+** instalado
2. **API Key de Retell** (solo para `back-resultados`)
3. Archivos CSV según el módulo que vayas a usar

### Configuración Inicial

1. Clonar el repositorio:
```bash
git clone https://rottino15-admin@bitbucket.org/evoltis/soho-fravega-cobranzas-resultados.git
cd soho-fravega-cobranzas-resultados
```

2. Configurar API Key de Retell (solo para `back-resultados`):
```powershell
# Opción 1: Variable de entorno
$env:RETELL_API_KEY="tu_api_key_aqui"

# Opción 2: Crear archivo .env en back-resultados/
# RETELL_API_KEY=tu_api_key_aqui
```

---

## 📊 Módulo: back-base

### ¿Qué hace?
Procesa y limpia archivos CSV de bases de datos de Fravega para prepararlos para su uso.

### Archivos a Cargar

1. **Ubicación**: Coloca tu archivo CSV en `back-base/base_recibida/`
   - Ejemplo: `Asignación Evoltis-Enero26(Evoltis).csv`

### Cómo Usar

```powershell
# Desde la raíz del proyecto
cd back-base
python main.py
```

### Resultados Generados

El script genera archivos procesados en `back-base/base_procesada/`:
- `fravega_base.csv` - Base principal limpia
- `fravega_cel_list.csv` - Lista de números de teléfono

---

## 📞 Módulo: back-resultados

### ¿Qué hace?
Obtiene datos de llamadas desde la API de Retell y genera reportes de gestiones de cobranza con tipificaciones.

### Archivos a Cargar

1. **Export de Retell**: Coloca tu archivo CSV exportado de Retell en `back-resultados/retell/`
   - El archivo debe tener una columna llamada `Call ID`
   - Ejemplo: `export_06dd954a91822e9d2f4668614.csv`
   - El script tomará automáticamente el archivo más reciente que coincida con el patrón `export_*.csv`

### Cómo Usar

#### Opción 1: Enriquecer CSV con todas las variables de Retell

```powershell
cd back-resultados
python main.py retell
```

**Resultado**: Genera `results/export_XXXXX_enriched.csv` con todas las variables dinámicas y postcall encontradas.

#### Opción 2: Generar CSV de Tipificaciones (Fravega Evoltis)

```powershell
cd back-resultados
python main.py tipif
```

**Resultado**: Genera `results/fravega_gestiones_evoltis_AAAAMMDD.csv` con las siguientes columnas:

**Variables Dinámicas:**
- `dni_cliente`
- `credito`
- `monto_exacto`
- `customer_name`
- `user_number`

**Variables Postcall:**
- `fecha_compromiso`
- `Tipificacion`

**⚠️ Importante**: Solo se incluyen filas donde `Tipificacion` no esté vacía.

### Configuración Avanzada

Puedes configurar variables de entorno opcionales:

```powershell
# Número de llamadas paralelas (default: 10)
$env:RETELL_MAX_WORKERS="10"

# Delay entre llamadas en segundos (default: 0.0)
$env:RETELL_SLEEP_SECONDS="0.5"

# URL base de Retell (default: https://api.retellai.com)
$env:RETELL_BASE_URL="https://api.retellai.com"

# Modo debug (muestra qué variables se extraen)
$env:RETELL_DEBUG="1"
```

### Integración con ROMAN (Opcional)

ROMAN es un sistema donde se pueden editar/corregir manualmente los datos de las llamadas después de procesadas. El sistema soporta **merge inteligente** con datos de ROMAN.

#### ¿Por qué usar ROMAN?

- **Retell** es completo (tiene todas las llamadas) pero puede tener datos desactualizados
- **ROMAN** puede tener datos corregidos manualmente pero puede ser incompleto
- El sistema **prioriza ROMAN cuando existe** pero usa Retell como fallback

#### Flujo de Datos

```
┌─────────────────────┐
│ retell/export_*.csv │ ← Export de Retell (base completa)
└─────────┬───────────┘
          │
          ↓
┌─────────────────────┐
│   API de Retell     │ ← Enriquecimiento con variables dinámicas/postcall
└─────────┬───────────┘
          │
          ↓
┌─────────────────────┐
│ roman/export_roman_ │ ← Export de ROMAN (si existe, OPCIONAL)
│    *.csv (PRIORIDAD)│
└─────────┬───────────┘
          │
          ↓
┌─────────────────────────────────────────┐
│          MERGE INTELIGENTE              │
│  • Si Call ID existe en ROMAN → ROMAN   │
│  • Si NO existe en ROMAN → Retell       │
└─────────┬───────────────────────────────┘
          │
          ↓
┌─────────────────────┐
│   Archivos finales  │
└─────────────────────┘
```

#### Cómo Usar ROMAN

1. **Exportar datos de ROMAN**
   - Exporta el CSV desde el sistema ROMAN con las correcciones manuales
   - Asegúrate de que incluya la columna `Call ID`

2. **Colocar el archivo**
   ```powershell
   # Copia el archivo a la carpeta roman
   copy "ruta\a\tu\export_roman_20260119.csv" "back-resultados\roman\"
   ```
   
   > **Nota**: El nombre debe seguir el patrón `export_roman_*.csv`

3. **Ejecutar normalmente**
   ```powershell
   cd back-resultados
   python main.py retell  # o python main.py tipif
   ```

4. **Verificar en la consola**
   ```
   📋 Encontrado export de ROMAN: export_roman_20260119.csv
      Llamadas en ROMAN: 150
   ✅ Actualizadas 45 llamadas con datos de ROMAN
   ```

#### Estructura del CSV de ROMAN

El CSV de ROMAN debe tener la misma estructura que el export de Retell:

| Columna | Descripción |
|---------|-------------|
| `Call ID` | **(Obligatorio)** Identificador único de la llamada |
| `[Entrada] Dni Cliente` | Variable dinámica de entrada |
| `[Salida] Tipificacion` | Variable postcall de salida |
| ... | Otras columnas según necesidad |

#### Configuración

```powershell
# Opcional: cambiar patrón de archivos ROMAN (default: export_roman_*.csv)
$env:ROMAN_GLOB_PATTERN="export_roman_*.csv"
```

#### Comportamiento del Merge

- **Solo sobrescribe columnas con valores**: Si ROMAN tiene un valor vacío o "-", se mantiene el valor de Retell
- **Normaliza nombres de columnas**: `[Entrada] Dni Cliente` → `dni_cliente`
- **Retrocompatible**: Si no hay archivo ROMAN, funciona exactamente igual que antes
- **Logs claros**: La consola indica cuántas llamadas fueron actualizadas

---

## 📁 Estructura de Carpetas

### Carpetas de Entrada (📥)

- `back-base/base_recibida/` - Coloca aquí los CSV a procesar
- `back-resultados/retell/` - Coloca aquí los exports de Retell (obligatorio)
- `back-resultados/roman/` - Coloca aquí los exports de ROMAN (opcional, para correcciones)

### Carpetas de Salida (📤)

- `back-base/base_procesada/` - Archivos procesados
- `back-resultados/results/` - Reportes generados

**Nota**: Estas carpetas están configuradas en `.gitignore` para no subir los archivos de datos al repositorio, pero las carpetas se mantienen gracias a los archivos `.gitkeep`.

---

## 🔄 Flujo de Trabajo Completo

### Ejemplo: Generar Reporte de Tipificaciones

1. **Obtener export de Retell**
   - Desde el dashboard de Retell, exporta las llamadas que necesitas
   - Guarda el CSV con nombre `export_*.csv`

2. **Cargar el archivo**
   ```powershell
   # Copia el archivo a la carpeta retell
   copy "ruta\a\tu\export_XXXXX.csv" "back-resultados\retell\"
   ```

3. **Configurar API Key**
   ```powershell
   $env:RETELL_API_KEY="tu_api_key"
   ```

4. **Ejecutar el generador**
   ```powershell
   cd back-resultados
   python main.py tipif
   ```

5. **Obtener resultados**
   - El archivo se genera en `back-resultados/results/`
   - Nombre: `fravega_gestiones_evoltis_AAAAMMDD.csv` (fecha actual)

---

## 📝 Ejemplos de Uso

### Ejemplo 1: Procesar Base de Datos

```powershell
# 1. Colocar archivo en base_recibida/
# 2. Ejecutar
cd back-base
python main.py

# 3. Resultados en base_procesada/
```

### Ejemplo 2: Enriquecer Export de Retell

```powershell
# 1. Colocar export en retell/
# 2. Configurar API key
$env:RETELL_API_KEY="tu_key"

# 3. Ejecutar
cd back-resultados
python main.py retell

# 4. Resultado en results/export_XXXXX_enriched.csv
```

### Ejemplo 3: Generar Reporte de Tipificaciones

```powershell
# 1. Colocar export en retell/
# 2. Configurar API key
$env:RETELL_API_KEY="tu_key"

# 3. Ejecutar con procesamiento paralelo
$env:RETELL_MAX_WORKERS="15"
cd back-resultados
python main.py tipif

# 4. Resultado en results/fravega_gestiones_evoltis_20260109.csv
```

---

## ⚙️ Optimización de Rendimiento

El módulo `back-resultados` procesa las llamadas en paralelo para mejorar el rendimiento:

- **Default**: 10 llamadas simultáneas
- **Configurable**: Ajusta `RETELL_MAX_WORKERS` según los límites de tu API
- **Progreso**: Muestra el progreso y tiempo estimado durante el procesamiento

**Ejemplo con 100 llamadas:**
- Sin paralelización: ~50 segundos
- Con paralelización (10 workers): ~5-7 segundos

---

## 🐛 Solución de Problemas

### Error: "Missing RETELL_API_KEY"
**Solución**: Configura la variable de entorno o crea un archivo `.env`:
```powershell
$env:RETELL_API_KEY="tu_api_key"
```

### Error: "No CSV found in retell matching export_*.csv"
**Solución**: Verifica que:
- El archivo esté en `back-resultados/retell/`
- El nombre comience con `export_`
- Tenga extensión `.csv`

### Error: "Column 'Call ID' not found"
**Solución**: Verifica que el CSV de Retell tenga una columna llamada exactamente `Call ID`

### Las variables dinámicas no aparecen
**Solución**: 
- Verifica que las llamadas tengan `retell_llm_dynamic_variables` en el payload
- Ejecuta con `$env:RETELL_DEBUG="1"` para ver qué se está extrayendo

---

## 📚 Archivos Importantes

- `back-base/.gitignore` - Ignora archivos de datos en base_recibida/ y base_procesada/
- `back-resultados/.gitignore` - Ignora archivos de datos en results/ y retell/
- `.gitkeep` - Mantiene las carpetas vacías en el repositorio

---

## 🔐 Seguridad

- **Nunca subas** archivos `.env` con API keys al repositorio
- Los archivos CSV con datos sensibles están en `.gitignore`
- Las API keys deben manejarse mediante variables de entorno

---

## 📞 Soporte

Para problemas o consultas, contactar al equipo de desarrollo.

---

## 📄 Licencia

Proyecto interno de Evoltis para gestión de cobranzas Fravega.

