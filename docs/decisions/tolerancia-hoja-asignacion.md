# Tolerancia del nombre de hoja en la base mensual de Naranja X MA

**Único cambio a código legacy de toda la migración** (issue #101, autorizado
explícitamente por operaciones). Afecta `back_base_etl/io.py::_resolve_input_sheet_name`
en sus **dos copias**: `etls/naranjax/legacy/chat` y `etls/naranjax/legacy/ma`.

## Por qué

Los archivos de asignación de Naranja X llegan con la hoja llamada `Hoja1` y el legacy
exigía `Asignacion` (o alias/patrón M90). El "procedimiento" era que alguien renombrara
la hoja a mano antes de cada corrida — un paso manual, mensual y silencioso que la
plataforma no podía absorber avisando: había que eliminarlo.

## Comportamiento (idéntico en ambas copias, verificado por test de paridad)

1. Si existe una hoja `Asignacion`/`Asignación`/`ASIGNACION` o que matchee
   `Asignacion M90 - *` → se usa. **Comportamiento histórico, cero regresión.**
2. Si no existe y el libro tiene **exactamente una hoja**: se validan los encabezados
   obligatorios (`INPUT_COLUMNS` menos opcionales, vía `INPUT_COLUMN_ALIASES`) contra la
   primera fila. Si están → se usa esa hoja y queda **constancia en el log**
   (`WARNING etl_naranjax: ... using the workbook's single sheet 'Hoja1' ...`).
3. Hoja única **sin** los encabezados obligatorios → falla listando qué columnas faltan.
4. **Más de una hoja** sin match → falla como siempre, listando esperadas y encontradas.

Nunca se toma "la primera hoja" a ciegas: procesar la hoja equivocada en silencio es
peor que fallar.

## Verificación (UAT 2026-08-07, legacy standalone, datos reales)

| Caso | Resultado |
|---|---|
| chat · base mayo (`ASIGNACION`) antes vs después | 5/5 sha256 idénticos (regresión cero) |
| ma · base mayo antes vs después | 4/4 idénticos |
| ma · base julio (`Hoja1`, fallback preexistente) antes vs después | 4/4 idénticos |
| chat · base julio original (`Hoja1`) vs renombrada quirúrgicamente a `Asignacion` | **5/5 idénticos** (3 artefactos + snapshot + estado del mes) |
| chat · base julio, antes del cambio | fallaba con el error de hoja |

Nota metodológica: renombrar la hoja re-guardando el `.xlsx` con openpyxl re-serializa
los floats del XML (`108741.48999999999` → `108741.49`) y hace divergir el estado (que
preserva valores crudos) aunque los artefactos coincidan. Para comparar de verdad hay
que renombrar editando sólo `xl/workbook.xml` dentro del zip.

## Guardas

- Tests en `etls/naranjax/tests/test_asignacion_sheet_resolution.py`: las cuatro ramas
  sobre **ambas copias**, más un test que exige que el bloque de código de resolución sea
  **textualmente idéntico** entre chat y ma (las copias ya habían divergido una vez: ma
  tenía un fallback ciego que este cambio elevó al estándar con guarda y log).
- La regla general sigue vigente: `etls/*/legacy/` no se toca. Este cambio fue una
  excepción con OK explícito de operaciones y UAT byte a byte; cualquier otra requiere
  el mismo proceso.
