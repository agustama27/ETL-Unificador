# Índice de documentación

Catálogo de la documentación del repositorio. Una línea por página: link, y **de qué se
ocupa** — el alcance, no un resumen. Estructura según
[ADR-ARC-022](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/3160375300).

## How-to

- [how-to/GUIA_NUEVO_CLIENTE.md](how-to/GUIA_NUEVO_CLIENTE.md) — alta de un cliente nuevo:
  qué carpeta crear bajo `etls/`, qué campos lleva el manifiesto y cómo verificar el alta
- [how-to/desplegar-en-kubernetes.md](how-to/desplegar-en-kubernetes.md) — publicar imagen y
  chart, hacer el rollout y verificarlo; qué hacer si `/ready` devuelve 503

## Reference

- [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md) — estado actual del sistema: capas,
  flujo de una corrida, contrato de adapter, reglas de validación del manifiesto y
  convenciones de código
- [reference/comandos.md](reference/comandos.md) — tareas del `Taskfile`, requisitos, estado
  esperado de la suite y las dependencias pineadas a versión exacta

## Explanation

- [explanation/DESPLIEGUE-CLOUD.md](explanation/DESPLIEGUE-CLOUD.md) — restricciones de
  despliegue, opciones de nube evaluadas y bloqueantes, para decidir dónde y cómo desplegar
- [explanation/paridad-upstream.md](explanation/paridad-upstream.md) — qué cubre la paridad
  byte a byte, por qué no cubre el drift de dependencias, y qué red lo cubre en su lugar

## Decisions

- [decisions/ADR-001-nucleo-hexagonal.md](decisions/ADR-001-nucleo-hexagonal.md) — núcleo
  hexagonal con adapters descubribles, y las siete decisiones que lo acompañan
- [decisions/ADR-002-alineacion-evoltis.md](decisions/ADR-002-alineacion-evoltis.md) —
  adopción del scaffolding de Evoltis, dónde va cada cosa y por qué los ETLs siguen
  corriendo como subprocesos dentro del pod
- [decisions/tolerancia-hoja-asignacion.md](decisions/tolerancia-hoja-asignacion.md) — por qué
  se aceptó el único cambio a código legacy de toda la migración, y bajo qué autorización

## Reports

Registros fechados con valor propio. Envejecen a propósito: son constancia, no documentación
vigente.

- [reports/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md](reports/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md) —
  plan del MVP de Naranja X tal como se aprobó
- [reports/verificacion-migracion-fase-3.md](reports/verificacion-migracion-fase-3.md) —
  comparación campo por campo de los 22 ETLs entre `registry/` y `etls/`
- [reports/01-objetivo-proyecto.md](reports/01-objetivo-proyecto.md) — objetivo original del
  proyecto, previo a la primera línea de código
- [reports/02-primer-paso-planificacion.md](reports/02-primer-paso-planificacion.md) —
  relevamiento y planificación técnica inicial

## Huecos declarados

- **No hay tutorial.** El arranque está cubierto por el `README.md`; el primer camino guiado
  para alguien que llega de cero está pendiente de que haya un destinatario concreto.
- **`explanation/DESPLIEGUE-CLOUD.md` mezcla cuadrantes.** Tiene criterio de decisión
  (explanation) y procedimiento de despliegue (how-to) en el mismo archivo. Partirlo requiere
  decisión humana sobre qué procedimiento rige; ARC-022 §8 clasifica ese contenido como
  "se propone, no se reescribe en silencio".
- **`openspec/` no está catalogado.** Es el almacén de artefactos SDD (propuestas, specs,
  tasks, archivo histórico). ARC-022 lo excluye: son datos de proceso, no documentación
  mantenida a mano. Sus referencias a rutas previas al reordenamiento quedaron sin actualizar
  a propósito, porque reescribir un registro histórico lo invalida como registro.
