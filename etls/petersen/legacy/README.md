## Generación de resultados y tipificaciones Petersen

Este proyecto procesa exportes de ROMAN, approach y bases internas, y genera **tipificaciones finales por banco** listas para subir al FTP, aplicando reglas de negocio y validaciones estrictas.

Los bancos soportados son:
- **Santa Fe**
- **Entre Ríos**
- **Santa Cruz**
- **San Juan**

Toda la lógica de reglas de tipificación por campo está documentada en `docs/REGLAS_TIPIFICACIONES.md`.

---

## Flujo completo de punta a punta

El proceso completo para generar las tipificaciones válidas y los archivos finales se puede ver en **4 grandes etapas**:

1. **Carga de ROMAN y armado de gestiones totales**
2. **Validación y normalización de promesas / tipificaciones simples**
3. **Generación de archivos finales por banco (gestiones válidas)**
4. **Tipificación adicional por approach / excluidos y filtrado FTP (opcional)**

A continuación se detalla qué hace cada etapa, qué insumos necesita y qué archivos produce.

---

## Etapa 1: Carga de ROMAN y generación de gestiones totales

**Código principal**: `main.py` + `procesos/roman_merger.py` + `procesos/tipif_generator.py`

- **Entrada obligatoria**:
  - `roman/*.csv`
    - Export de ROMAN con columna `ID de Llamada` y columnas `[Entrada]` / `[Salida]`.

- **Pasos principales**:
  - Lee el CSV más reciente de `roman/`.
  - Mapea las columnas de ROMAN al esquema interno de gestiones:
    - `Usuario asignado`, `NRO_CLIENTE`, `SUCURSAL`, `ACCION`, `EFECTO`, `MOTIVO_ATRASO`, `NRO_PRODUCTO`, `TIPO_PROD`, etc.
  - Aplica primeras reglas de negocio:
    - Derivación de `CONTACTO` en base a `EFECTO`.
    - Uso de `deuda_vencida` como fallback de `MONTO_PROMESA` en promesas.
    - Normalización básica de textos y productos.
    - Obtención y preservación de `fecha_llamada` y `fecha_llamada_original`.
  - Filtra:
    - descarta filas con `EFECTO` vacío.
    - descarta filas con `EFECTO = RELLAMAR` (salvo que se fuerce incluir todo).
    - descarta filas sin `nro_cliente`.
  - **Separa por banco** (`BANCO_GESTIONADO`) en 4 archivos.

- **Salida principal** (por default del `main`):
  - Carpeta de resultados totales por día:
    - `debug/gestiones_totales_AAAAMMDD/`
      - `gestiones_Santa_Fe.csv`
      - `gestiones_Entre_Rios.csv`
      - `gestiones_Santa_Cruz.csv`
      - `gestiones_San_Juan.csv`

- **Reportes a revisar en esta etapa**:
  - Log en consola con cantidad de filas cargadas desde ROMAN.

---

## Etapa 2: Validación de promesas y tipificaciones

**Código principal**: `procesos/promesa_validator.py`

Sobre los archivos de `debug/gestiones_totales_AAAAMMDD/` se realiza una validación exhaustiva:

- **Validaciones para promesas de pago** (`EFECTO = PROMESA DE PAGO` / `PROMESA_DE_PAGO`):
  - Campos obligatorios (no vacíos y coherentes):
    - `FECHA_ALTA`
    - `FECHA_PROMESA` (formato válido, dentro de 10 días corridos, día hábil y ≥ `FECHA_ALTA`)
    - `MONTO_PROMESA` (> 0, formato monetario correcto)
    - `PUNTAJE_PROMESA`
    - `TIPO_PROMESA`
    - `MOTIVO_ATRASO`
    - `NRO_PRODUCTO`
    - `SUC_PRODUCTO`
    - `TIPO_PROD` ∈ {`27`, `4`, `1`}
  - Reglas especiales:
    - Fallback de `MONTO_PROMESA` con `deuda_vencida`.
    - `MOTIVO_ATRASO` por defecto `"No aclara motivo de atraso"` si viene vacío.
    - Ajuste automático de `FECHA_PROMESA` al último/primer día hábil válido dentro del rango.

- **Validaciones para tipificaciones simples**  
  (YA PAGO, NOTIFICADO TITULAR, NOTIFICADO FLIAR, TELEFONO EQUIVOCADO, DESCONOCE DEUDA, NO AFRONTA DEUDA, FALLECIDO):
  - Requieren:
    - `Usuario asignado`, `TIPO_PROMESA`, `NRO_CLIENTE`, `SUCURSAL`, `ACCION`,
      `EFECTO`, `CONTACTO`, `OBSERVACIONES_GESTION`, `FECHA_ALTA`.
  - Deben tener vacíos todos los campos de promesa/producto.

- **Salida lógica (no genera archivos nuevos)**:
  - Un objeto de resultado con:
    - Total de promesas.
    - Cantidad de promesas válidas.
    - Cantidad de promesas con errores.
    - Lista de errores por banco, fila y campo.

- **Reporte a revisar**:
  - **Reporte de validación en consola**, que se imprime desde `validate_results(...)`:
    - Resumen de totales.
    - Detalle de errores por banco, fila y campo.

---

## Etapa 3: Generación de gestiones válidas por banco

**Código principal**: `procesos/promesa_validator.py` → función `export_valid_promesas`

Partiendo de `debug/gestiones_totales_AAAAMMDD/`, se construye la carpeta final:

- `gestiones-validas/Gestiones_Petersen_AAAAMMDD/`
  - `archivos_codificacion/`
    - `AG002_45.csv` (Santa Fe)
    - `AG002_46.csv` (Entre Ríos)
    - `AG002_47.csv` (Santa Cruz)
    - `AG002_48.csv` (San Juan)
  - `archivos_nombre/`
    - `gestiones_validas_BSF.csv`
    - `gestiones_validas_BER.csv`
    - `gestiones_validas_BSC.csv`
    - `gestiones_validas_BSJ.csv`
  - `archivos_fechas_originales/`
    - `gestiones_originales_BSF.csv`
    - `gestiones_originales_BER.csv`
    - `gestiones_originales_BSC.csv`
    - `gestiones_originales_BSJ.csv`

Los contenidos de `archivos_codificacion` y `archivos_nombre` son idénticos (solo cambia el nombre del archivo).  
Los de `archivos_fechas_originales` preservan las fechas originales de las llamadas.

- **Qué filas se incluyen**:
  - **Promesas de pago válidas** según la validación de la etapa 2.
  - **Tipificaciones simples válidas y limpiadas** (YA PAGO, NOTIFICADO TITULAR, NOTIFICADO FLIAR, TELEFONO EQUIVOCADO, DESCONOCE DEUDA, NO AFRONTA DEUDA, FALLECIDO).

- **Normalizaciones y reglas adicionales aplicadas**:
  - Normalización de `MONTO_PROMESA` (eliminación de separador de miles donde aplica).
  - Truncamiento de `MOTIVO_ATRASO` a 50 caracteres y sanitización de texto.
  - Sanitización de `OBSERVACIONES_*` y campos de texto (comillas fuera, `;` → `,`).
  - **Eliminación de duplicados por `NRO_CLIENTE` y banco**:
    - Si hay múltiples gestiones para un mismo cliente:
      - Si al menos una es promesa de pago → se prioriza la promesa de pago.
      - Si ninguna es promesa → se conserva la primera gestión.
  - Ajuste de `FECHA_ALTA`:
    - En `archivos_codificacion/` y `archivos_nombre/` se fuerza a la **fecha de proceso (hoy)**.
    - En `archivos_fechas_originales/` se intenta preservar la fecha real de llamada.
  - Revalidación de `FECHA_PROMESA` cuando corresponde.

- **Reportes a revisar**:
  - Mensajes en consola al final de `export_valid_promesas`:
    - Detalle de archivos generados por banco y cantidad de filas.
    - Detalle de cuántas filas son promesas vs. tipificaciones simples.
  - **Reporte de normalización** en consola:
    - Totales de filas corregidas por monto, motivo, observaciones, fechas, etc.

Además, existe una función auxiliar `export_all_gestiones_fecha_original` para generar una vista de **todas las gestiones con fechas originales** en una carpeta alternativa (por ejemplo `gestiones-validas-fecha-original/`), sin filtrado por validez.

---

## Etapa 4: Tipificación adicional vía approach / excluidos y filtrado FTP

### 4.1. Tipificación automática con approach

**Código principal**: `procesos/approach_merge.py`

Una vez generada la carpeta `gestiones-validas/Gestiones_Petersen_AAAAMMDD/`, se puede:

1. **Cruzar el reporte de approach con la base** (`base/`) para identificar teléfonos:
   - Entrada:
     - `approach/LOGCALL_*.csv` (u otro CSV con columnas `PHONE` y `RESULT`).
     - `base/tabla_integradora_*.csv` (con `TEL1–TEL4`, `DAT3` = NRO_CLIENTE, `DAT6` = banco, `SUCURSAL`).
   - Salida:
     - `debug/approach_merge_YYYYMMDD_HHMMSS.csv`  
       (con columnas `PHONE`, `RESULT`, `DAT3`, `DAT6`, `SUCURSAL`).

2. **Generar tipificaciones "NO RESPONDE OCUPADO" para clientes sin tipificación previa**:
   - Se usa `run_approach_merge_and_tipify(gestiones_dir=Gestiones_Petersen_AAAAMMDD)`.
   - Para cada cliente (`DAT3`) que:
     - aparece en el cruce approach+base.
     - **no tiene aún gestión** en `archivos_codificacion/`.
   - Se agrega una fila con:
     - `ACCION = LLAMADA SALIENTE`
     - `EFECTO = NO RESPONDE OCUPADO`
     - `OBSERVACIONES_GESTION = Cliente no responde.`
   - La línea se agrega a:
     - `archivos_codificacion/AG002_XX.csv`
     - `archivos_nombre/gestiones_validas_BXX.csv`
     - `archivos_fechas_originales/gestiones_originales_BXX.csv`

- **Reportes a revisar**:
  - CSV de debug: `debug/approach_merge_YYYYMMDD_HHMMSS.csv`.
  - Estadísticas que imprime `run_approach_merge_and_tipify`:
    - `total_matcheados`
    - `ya_tipificados`
    - `banco_desconocido`
    - `tipificaciones_agregadas`

### 4.2. Tipificación de datos excluidos

**Código principal**: `procesos/approach_merge.py` → `run_tipify_excluded`

- **Entrada**:
  - `datos-excluidos/*.csv` con columnas `DAT3`, `DAT6`, `SUCURSAL`.
- **Lógica**:
  - Para cada cliente excluido:
    - Si ya tiene gestión en `Gestiones_Petersen_AAAAMMDD` → se omite.
    - Si no, se genera también una tipificación `"NO RESPONDE OCUPADO"` similar a la del punto anterior.
- **Salida / reportes**:
  - No genera nuevos CSV de debug, pero:
    - Imprime en consola:
      - `total_excluidos`
      - `excluidos_ya_tipificados`
      - `excluidos_banco_desconocido`
      - `tipificaciones_excluidos_agregadas`

### 4.3. Filtrado para FTP (opcional)

**Script independiente**: `procesos/filtrar_ftp.py`

Este script se usa cuando ya existen archivos **de FTP** (por ejemplo, desde `archivos_codificacion/ftp`) y se desean dejar solo las gestiones con efectos relevantes.

- **Entrada**:
  - Carpeta tipo:
    - `gestiones-validas/Gestiones_Petersen_AAAAMMDD/archivos_codificacion/ftp`
  - Archivos dentro:
    - `AG002_45.csv`, `AG002_46.csv`, `AG002_47.csv`, `AG002_48.csv`, etc.
- **Filtros aplicados**:
  - Se conservan solo registros con `EFECTO` en:
    - `PROMESA DE PAGO`
    - `NOTIFICADO TITULAR`
    - `NOTIFICADO FLIAR`
    - `YA PAGO`
- **Salida**:
  - Carpeta hermana `sub_ftp/`:
    - Mismos nombres de archivo pero filtrados.
  - Adicionalmente, para `AG002_48.csv` (San Juan):
    - `promesas_bco_SJ.csv` con registros de promesa y efectos válidos.
- **Reportes a revisar**:
  - Mensajes en consola:
    - Cantidad de registros originales vs. filtrados por archivo.
    - Totales generales.
    - Detalle de `promesas_bco_SJ.csv` si se genera.

---

## Quickstart (ejecución estándar)

### 1. Colocar los insumos

- **ROMAN (obligatorio)**:

  ```text
  roman/*.csv
  ```

  El sistema usa el archivo más reciente del directorio.

- **Approach (opcional, para NO RESPONDE OCUPADO automáticas)**:

  ```text
  approach/LOGCALL_*.csv
  ```

- **Base de clientes (para approach)**:

  ```text
  base/tabla_integradora_*.csv
  ```

- **Datos excluidos (opcional)**:

  ```text
  datos-excluidos/*.csv
  ```

### 2. Ejecutar el flujo principal

Desde la raíz del proyecto:

```powershell
python .\main.py
```

Esto ejecuta en orden:
1. Carga de ROMAN y generación de `debug/gestiones_totales_AAAAMMDD/`.
2. Validación de promesas y tipificaciones.
3. Export de gestiones válidas a `gestiones-validas/Gestiones_Petersen_AAAAMMDD/`.
4. (Si hay insumos) tipificación adicional por approach y excluidos.

### 2.b Modo ejecutable distribuible (salida única ZIP)

Este proyecto también puede empaquetarse como ejecutable para compartir con el equipo.

#### Generar el ejecutable

```powershell
pip install -r .\requirements.txt
python .\build.py
```

El ejecutable queda en:

```text
dist/petersen_resultados.exe
```

#### Uso para tus compañeros

1. Copiar `petersen_resultados.exe` a una carpeta de trabajo que tenga:
   - `roman/` (obligatorio)
   - `approach/` (opcional)
   - `base/` (opcional, para approach)
   - `datos-excluidos/` (opcional)
2. Ejecutar con doble clic `petersen_resultados.exe`.
3. La salida final será un único ZIP en esa misma carpeta:
   - `Gestiones_Petersen_AAAAMMDD.zip`
   - Contenido exacto: `AG002_45.csv`, `AG002_46.csv`, `AG002_47.csv`, `AG002_48.csv`

Nota: en modo ejecutable los archivos intermedios se generan en una carpeta temporal y se eliminan automáticamente al finalizar.

### 3. Pasos opcionales posteriores

- **Filtrar para FTP** (si se usan subcarpetas `ftp/`):

```powershell
python .\procesos\filtrar_ftp.py gestiones-validas\Gestiones_Petersen_AAAAMMDD\archivos_codificacion\ftp
```

Revisa la carpeta `sub_ftp/` generada y el archivo `promesas_bco_SJ.csv` si corresponde.

---

## Estructura actual de carpetas (resumen)

```text
soho-petersen-cobranzas-resultados/
├── roman/                          # Exports de ROMAN (obligatorio)
│   └── *.csv
├── approach/                       # Reportes de approach (opcional)
│   └── LOGCALL_*.csv
├── base/                           # Base integradora para cruzar teléfonos
│   └── tabla_integradora_*.csv
├── datos-excluidos/                # Base de clientes excluidos (opcional)
├── debug/
│   ├── gestiones_totales_AAAAMMDD/ # Gestiones totales por banco
│   └── approach_merge_*.csv        # Debug de merge approach + base
├── gestiones-validas/
│   └── Gestiones_Petersen_AAAAMMDD/
│       ├── archivos_codificacion/  # AG002_45–48.csv (fecha alta = hoy)
│       ├── archivos_nombre/        # gestiones_validas_BSF/BER/BSC/BSJ.csv
│       └── archivos_fechas_originales/
│           └── gestiones_originales_BSF/BER/BSC/BSJ.csv
├── docs/
│   └── REGLAS_TIPIFICACIONES.md    # Reglas de tipificación por campo
├── procesos/                       # Módulos de procesamiento
│   ├── tipif_generator.py
│   ├── promesa_validator.py
│   ├── roman_merger.py
│   ├── approach_merge.py
│   └── filtrar_ftp.py
├── main.py                         # Punto de entrada del flujo completo
├── requirements.txt
└── README.md
```
