# Skill: Implementar App Desktop ROMAN + Logcall con Reporte Final (estilo `luz-exe`)

## Objetivo de la skill

Implementar en **un proyecto nuevo** una aplicación de escritorio ejecutable que:

1. ingeste uno o varios CSV de **ROMAN** y **Logcall**,
2. ejecute validaciones y normalizaciones robustas,
3. consolide la información siguiendo reglas de negocio reproducibles,
4. genere un **reporte final Excel** y un **log de corrida**,
5. preserve trazabilidad completa de entradas/salidas por ejecución.


---

## Cuándo usarla (triggers)

Usar esta skill cuando el usuario pida alguno de estos objetivos:

- "Crear app de escritorio para consolidar Roman + Logcall"
- "Generar ejecutable para usuarios de negocio (sin terminal)"
- "Procesar múltiples CSV y emitir reporte final Excel"
- "Necesito flujo con trazabilidad por corrida y logs"

No usarla si el pedido es solo un script ad-hoc de una sola corrida sin UI ni empaquetado.

---

## Precondiciones

Antes de implementar, verificar:

1. **Runtime**: Python 3.10+ (o versión definida por el nuevo proyecto).
2. **Dependencias mínimas**:
   - `pandas`
   - `openpyxl`
   - `pyinstaller` (si se builda EXE en esta etapa)
3. **Insumos esperados**:
   - CSV ROMAN (pueden venir múltiples archivos)
   - CSV Logcall (pueden venir múltiples archivos)
4. **Permisos de escritura** en el directorio de ejecución para crear `salidas/...`.
5. **Definición de columnas objetivo** del reporte final (canon funcional).
6. (Opcional pero recomendado) dataset de smoke con pocos registros para validación rápida.

---

## Flujo de trabajo paso a paso

### 1) Estructura base del proyecto

Crear módulos separados por responsabilidad:

- `main.py` (entrypoint UI + CLI/smoke)
- `app/processor.py` (orquestación de corrida)
- `app/consolidator.py` o módulo de dominio equivalente (reglas de negocio)
- `app/io.py` (lectura robusta CSV)
- `app/reporting.py` (export Excel)
- `app/logging.py` (logger por corrida)
- `*.spec` para empaquetado (PyInstaller)

> Patrón anclado en `luz-exe`: UI delgada + processor + consolidator de dominio.

### 2) UI desktop + modo CLI

Implementar dos modos:

- **UI (Tkinter o framework desktop elegido)**:
  - botón seleccionar múltiples CSV ROMAN
  - botón seleccionar múltiples CSV Logcall
  - botón `Procesar` habilitado solo cuando ambos conjuntos existan
  - mensajes de éxito/error al finalizar
- **CLI** (para smoke/automatización):
  - `--roman-files ...`
  - `--logcall-files ...`
  - `--smoke-ui` (abre/cierra UI rápido para verificar arranque)

### 3) Resolución de carpeta base de outputs

Regla clave:

- Si ejecuta como EXE (`frozen`), escribir junto al ejecutable.
- Si ejecuta como script, escribir junto al proyecto/script.

Nunca depender de carpeta temporal `_MEI` para outputs de negocio.

### 4) Validaciones de entrada

Para cada archivo seleccionado:

- existe y es archivo
- extensión `.csv`
- al menos un archivo por fuente (Roman y Logcall)

Error temprano con mensajes claros para el usuario final.

### 5) Creación de corrida trazable

Generar estructura por ejecucion:

- `salidas/DD-MM-YYYY/ejecucion_HH-MM-SS-ffffff/entradas/roman/*.csv`
- `salidas/DD-MM-YYYY/ejecucion_HH-MM-SS-ffffff/entradas/logcall/*.csv`
- `salidas/DD-MM-YYYY/ejecucion_HH-MM-SS-ffffff/resultados/output_luz_DD_MM_YY.xlsx`
- `salidas/DD-MM-YYYY/ejecucion_HH-MM-SS-ffffff/logs/luz_YYYYMMDD_HHMMSS.log`

Copiar los archivos originales a `entradas/...` (inmutabilidad y auditoría).

### 6) Ingesta robusta CSV

Aplicar lectura con fallback:

1. intentar `utf-8`,
2. fallback `latin-1`,
3. detectar caracteres de reemplazo (`�`) para evitar falsos positivos de encoding.

Soportar heterogeneidad de columnas con normalización de nombres (lower, sin acentos, alfanumérico).

### 7) Consolidación funcional (E2E)

Reglas recomendadas (ancladas en caso referencia):

- Cargar todos los ROMAN y unirlos.
- Cargar todos los Logcall y unirlos.
- **Deduplicar ROMAN** por `ID de Llamada` (keep last).
- **Deduplicar Logcall** por `CALLREFID` (keep last).
- Remover cabeceras incrustadas en Logcall cuando aparezcan como filas.
- Construir filas sintéticas de "no conectados" para `RESULT != 10`.
- Unir: `roman_conectados + logcall_no_conectados`.
- Ordenar por fecha/hora descendente.
- Aplicar shape final fijo (columnas objetivo exactas).
- Normalizar valores canónicos (booleans Sí/No, categorías, acentos).
- Completar faltantes con `-` (o convención definida por negocio).

#### Diccionario fijo de tipificaciones Logcall

| RESULT | TIPI |
| --- | --- |
| 1004 | CONTESTADOR |
| 10 | CONECTADO |
| 7 | OCUPADO |
| 9 | NO LLAMA |
| 8 | NO RESPONDE |
| 18 | FAX |

#### Ajuste a tipificaciones ROMAN por cliente

- El diccionario de Logcall es fijo de origen y debe tratarse como fuente canónica inicial.
- La tipificación final de salida debe ajustarse (mapearse) a las tipificaciones de ROMAN, que cambian según cliente.
- Implementar una configuración de mapeo por cliente (por ejemplo YAML, JSON o tabla), con fallback controlado y validaciones de consistencia.
- Toda tipificación sin mapeo debe quedar logueada explícitamente para revisión operativa.

### 8) Exportación y logging

- Exportar a Excel (`openpyxl`) con hoja principal y orden de columnas estable.
- Tratar campos sensibles como texto (`Desde`, contrato, suministro) para no perder formato.
- Escribir log por corrida con:
  - cantidad archivos Roman/Logcall
  - totales de filas
  - distribución de `RESULT`
  - ruta de output final

### 9) Resultado final al usuario

Retornar (UI y CLI) objeto resumen con:

- ruta de corrida
- rutas de archivos copiados
- ruta Excel
- ruta log
- cantidad total de filas salida
- métricas de consolidación

---

## Contrato de entradas/salidas

### Entradas

- `roman_files: list[str|Path]` (>= 1)
- `logcall_files: list[str|Path]` (>= 1)
- `output_root: str|Path`
- `client_typification_map: dict|str|Path` (mapeo por cliente de tipificaciones Logcall -> ROMAN)

### Salidas (objeto de proceso)

Ejemplo de contrato:

- `run_root: Path`
- `roman_copied_files: list[Path]`
- `logcall_copied_files: list[Path]`
- `output_excel_path: Path`
- `log_file_path: Path`
- `total_output_rows: int`
- `summary: dict`
  - `roman_rows`
  - `logcall_rows`
  - `logcall_connected_result_10`
  - `logcall_non_connected_rows`
  - `logcall_result_distribution`

### Errores esperados (controlados)

- `ValueError`: faltan archivos de una fuente, extensión inválida, argumentos incompletos CLI
- `FileNotFoundError`: rutas inexistentes
- `UnicodeDecodeError` (si fallan todos los encodings y no se pudo leer)
- excepciones de export Excel (I/O, permisos)

---

## Reglas de calidad y validación

1. **Determinismo de salida**: mismo input -> mismo contenido de output (excepto timestamp/ruta).
2. **Trazabilidad**: toda corrida debe guardar copia de insumos y log.
3. **Robustez de encoding**: no romper con CSV Latin-1 habituales.
4. **Compatibilidad semántica**: normalizar variaciones de texto a un canon.
5. **No pérdida silenciosa**: loguear descartes (cabeceras incrustadas, filas inválidas).
6. **Cobertura de mapeo de tipificaciones**: no permitir pérdida silenciosa en el pasaje Logcall -> ROMAN; todo no mapeado debe quedar en log y entrar en fallback controlado.
7. **UX clara**: errores comprensibles para usuario no técnico.
8. **Separación de capas**: UI no contiene reglas de negocio.

---

## Estrategia de tests

### A) Unitarios

Cobertura mínima:

- validación de archivos (exists/extensión)
- normalización de headers
- deduplicación (Roman/Logcall)
- mapeo `RESULT -> motivo/tipo`
- mapeo fijo Logcall (`RESULT -> TIPI`) y mapeo final por cliente a tipificaciones ROMAN
- normalización booleanos a Sí/No
- construcción de fecha/hora desde Logcall
- fallback de encoding

### B) Integración

Casos recomendados:

1. **Happy path multi-archivo**:
   - 2 ROMAN + 2 Logcall
   - dedupe correcto
   - output con columnas esperadas y conteo consistente
2. **Sin no conectados** (`RESULT=10` todo):
   - no se agregan filas sintéticas
3. **Con no conectados mixtos**:
   - validar motivos y tipo contacto
4. **CSV con header incrustado**:
   - fila removida y warning en log
5. **Encodings mixtos**:
   - archivo UTF-8 + archivo Latin-1 en misma corrida
6. **Mapeo por cliente con cobertura completa**:
   - validar Logcall fijo -> ROMAN cliente sin diferencias en resultados esperados
7. **Tipificaciones no mapeadas**:
   - aplicar fallback controlado y registrar eventos en log para revisión operativa

### C) Smoke

- `python main.py --smoke-ui` (arranque/cierre UI sin crash)
- CLI mínima con fixtures:
  - `python main.py --roman-files ... --logcall-files ...`
  - verificar que existe Excel y log en `salidas/...`
- Smoke post-build:
  - ejecutar EXE y confirmar generación de salida junto al ejecutable

---

## Criterios de aceptación

Se considera completada si:

1. La app desktop permite seleccionar múltiples ROMAN y Logcall y procesar.
2. La corrida crea estructura trazable de carpetas/archivos.
3. El Excel final se genera con columnas canon y datos consolidados.
4. Se aplican reglas de dedupe y no conectados (`RESULT != 10`).
5. Existe log por corrida con métricas resumidas.
6. El modo CLI funciona para smoke automatizable.
7. El EXE buildado corre sin depender del entorno de desarrollo.
8. Tests unitarios + integración + smoke pasan.

---

## Checklist de implementación

- [ ] Crear arquitectura de módulos (UI, processor, consolidator, io, reporting).
- [ ] Definir columnas objetivo y normalizaciones canónicas.
- [ ] Implementar selector múltiple UI para Roman y Logcall.
- [ ] Implementar argumentos CLI y `--smoke-ui`.
- [ ] Implementar validación fuerte de entradas.
- [ ] Implementar creación de corrida y copia de insumos.
- [ ] Implementar lectura CSV con fallback de encoding.
- [ ] Implementar consolidación (merge, dedupe, no conectados, orden).
- [ ] Implementar export Excel y logger por corrida.
- [ ] Implementar pruebas unitarias.
- [ ] Implementar pruebas de integración con fixtures.
- [ ] Implementar smoke tests (script + UI + exe si aplica).
- [ ] Configurar `pyinstaller` spec y verificar output ejecutable.
- [ ] Documentar uso rápido para usuarios finales.

---

## Riesgos comunes y mitigaciones

1. **Cambios de naming en columnas fuente**
   - Mitigación: normalizador de headers por clave canónica, no por texto exacto.
2. **CSV corruptos o encoding raro**
   - Mitigación: fallback + detección de `�` + errores explícitos por archivo.
3. **Colisión de nombres de archivos copiados**
   - Mitigación: estrategia de renombre incremental (`_2`, `_3`, ...).
4. **Inflado de filas por dedupe incorrecto**
   - Mitigación: tests de regresión con claves `ID de Llamada` y `CALLREFID`.
5. **Output inaccesible en EXE**
   - Mitigación: resolver base dir con `sys.executable` cuando frozen.
6. **Reglas de negocio implícitas no documentadas**
   - Mitigación: declarar mapping de `RESULT` y normalizaciones en constantes versionadas.

---

## Plantillas de prompts para el agente que use esta skill

### Prompt 1: implementación completa en repo nuevo

> Implementá en este repo una app desktop ejecutable para consolidar CSV de ROMAN y Logcall, siguiendo la skill "Implementar App Desktop ROMAN + Logcall con Reporte Final".  
> Requisitos: UI con selección múltiple, modo CLI con smoke, corrida trazable `salidas/...`, dedupe Roman/Logcall, filas sintéticas para `RESULT != 10`, export Excel final y log por corrida.  
> Entregá: estructura de código, tests unitarios/integración/smoke, spec de PyInstaller y documentación de uso.

### Prompt 2: primero núcleo de negocio, luego UI

> Aplicá la skill de ROMAN+Logcall, pero en dos fases:  
> Fase A: implementar motor de consolidación y tests (sin UI).  
> Fase B: montar UI desktop y empaquetado EXE.  
> Mantené contrato de salida trazable y compatible con criterios de aceptación.

### Prompt 3: hardening de calidad

> Tomá la implementación actual y alineala con la skill ROMAN+Logcall: reforzá validaciones, normalización de encodings, dedupe por claves canónicas, logging estructurado por corrida y cobertura de tests de integración.

### Prompt 4: auditoría técnica contra la skill

> Auditá este repo contra la skill ROMAN+Logcall y devolvé un gap report: qué cumple, qué falta, riesgos y plan de cierre priorizado en pasos concretos.

---

## Notas de anclaje al caso `luz-exe` (para mantener fidelidad funcional)

- Arquitectura simple y mantenible: `main.py` (UI/CLI) + `processor` + consolidador.
- Persistencia de corrida junto al ejecutable/script, no temporal.
- Soporte de múltiples archivos por fuente.
- Consolidación con dedupe + enriquecimiento de no conectados (`RESULT != 10`).
- Export Excel con columnas de negocio estables.
- Logs de corrida para soporte y trazabilidad operacional.
