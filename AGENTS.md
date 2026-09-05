# AGENTS.md — Guía para agentes de código

Este repositorio es una **capa de ejecución controlada** sobre ETLs legacy de cobranza:
sandbox por corrida, evidencia forense, locking por período y promoción durable de estado.
Antes de tocar código leé `README.md` y `docs/reference/ARQUITECTURA.md`; la arquitectura objetivo
está en `docs/decisions/ADR-001-nucleo-hexagonal.md`.

## Mapa de documentación

- Índice: `docs/index.md` — catálogo con una línea por página y los huecos declarados.
- Bitácora: `docs/log.md` — append-only. Lo que pasó va acá, no dentro de un how-to.
- Comandos y estado esperado de la suite: `docs/reference/comandos.md`.
- Estructura: cuadrantes Diátaxis según ADR-ARC-022 (`decisions/`, `reference/`, `how-to/`,
  `explanation/`, `reports/`). No hay `tutorial/`: el hueco está declarado en el índice.

Desvíos respecto del layout canónico, y por qué:

| Desvío | Motivo |
|---|---|
| `openspec/` fuera del catálogo | Almacén de artefactos SDD y archivo histórico. ARC-022 excluye datos de proceso. Sus referencias a rutas previas al reordenamiento quedan sin actualizar: reescribir un registro lo invalida. |
| `etls/<cliente>/README.md` fuera del catálogo | Documentación por unidad desplegable, análoga a `apps/<servicio>/docs/` de ARC-002 §docs. Un cliente no aparece en el índice de otro. |
| `etls/` como carpeta de primer nivel | No es `apps/` (no son procesos desplegables: los ejecuta el orquestador como subprocesos) ni `apps/commons/` (no es código compartido nuestro). ARC-002 admite carpetas especializadas que no dupliquen un rol ya definido. Ver `docs/decisions/ADR-002-alineacion-evoltis.md`. |
| `tools/etl-platform-mcp/` | El servidor MCP es **stdio**: corre en la máquina del desarrollador, no en Kubernetes. `apps/` está reservado a procesos desplegables. |
| `tests/` junto a `test/` | `tests/` es el árbol unitario que descubre pytest; `test/integration/` es el de ARC-002. Renombrar `tests/` rompería imports (`tests.support.*`) a cambio de nada. |
| `explanation/DESPLIEGUE-CLOUD.md` mezcla cuadrantes | Tiene criterio (explanation) y procedimiento (how-to). Partirlo exige decidir qué procedimiento rige; ARC-022 §8 lo clasifica como "se propone, no se reescribe en silencio". |

Ruteo de contenido nuevo: un flag, default o contrato vigente va a `reference/`; el motivo de
algo o una trampa descubierta, a `explanation/`; una decisión con alternativa descartada, a
`decisions/`; qué pasó y cuándo, a `log.md`. **Preferí editar al dueño antes que crear un
archivo nuevo.**

## Reglas duras

1. **No modifiques los proyectos legacy** (`etls/*/legacy/`). Son cajas negras en
   producción, invocadas por subprocess. La lógica de negocio del cliente vive ahí, no en
   el núcleo. La única excepción hasta hoy (tolerancia del nombre de hoja en Naranja X MA,
   `docs/decisions/tolerancia-hoja-asignacion.md`) requirió OK explícito de operaciones y UAT byte a
   byte antes/después: ese es el estándar para cualquier otra.
2. **No modifiques los tests existentes.** Los 13 tests de `tests/e2e/` son la red de
   seguridad: si un refactor obliga a tocar uno, cambiaste comportamiento observable, no
   estructura. Corrélos antes y después de cualquier cambio al núcleo.
3. **No commitees datos reales:** `.csv`, `.xlsx`, `.xls`, `.env`, outputs generados ni
   nada bajo `var/`. Los artefactos y logs pueden contener PII.
4. **Mínimo blast radius:** ante la duda entre un cambio chico y uno prolijo, hacé el
   chico y anotá el prolijo como pendiente.
5. **`business_date == hoy` NO es deuda técnica.** Es regla de negocio confirmada por
   operaciones (ADR-001, decisión 7): no existe reproceso de días caídos. No propongas
   backfill ni "arregles" ese check.

## ⚠️ SubprocessAdapter es compartido por 10 ETLs de 6 clientes

`etl_core.contracts:SubprocessAdapter` está mapeado a las bases de Bancor, EPEC, Frávega,
Claro UY, Encuesta CX y Social Learning (AR/CL) y a los tres PCT de Naranja X. Si lo tocás
para arreglar algo de un cliente, estás tocando a los otros cinco. Cualquier cambio ahí
exige correr los 13 e2e completos (`pytest etls/`).

## Cómo agregar un cliente

Agregá una carpeta bajo `etls/<cliente>/` con `manifest.yaml` (con
`adapter: modulo:Clase`), el adapter si `SubprocessAdapter` no alcanza, un `job.py` si el
legacy no tiene CLI usable, `legacy/`, `tests/` y `README.md`. El catálogo la descubre
solo: **cero archivos del núcleo tocados.**

## Convenciones de código (docs/reference/ARQUITECTURA.md §8)

- **Python 3.12+.** Se usan `StrEnum`, `Self`, `X | None`, `is_relative_to`.
- **Inmutabilidad.** Modelos `@dataclass(frozen=True)`; los mapas se envuelven en
  `MappingProxyType` en `__post_init__`.
- **Inyección de dependencias por constructor con default.** `Runner(popen=..., clock=...)`,
  `StateStore(replace=..., file_fsync=...)`. Es lo que hace testeable el núcleo sin tocar
  disco. Mantenelo.
- **Excepciones con atributo `code`.** `RunBlockedError` y `StatePromotionError` llevan un
  `code` que termina en `run.json`. Los códigos nuevos se documentan en la sección 3 de
  `docs/reference/ARQUITECTURA.md`.
- **Errores acotados.** Nada de `except Exception` genérico en el núcleo; se capturan
  tipos concretos. Única excepción documentada: la frontera fail-fast de los `*_job.py`.
- **Sin comentarios decorativos.** Docstring de una línea cuando el nombre no alcanza.
- **Nombres del dominio en inglés en el código, mensajes de usuario en español.** La API
  responde en español porque la consume el equipo de operaciones.

## Cómo verificar

```bash
task check        # validate + lint + test
```

Las tareas, los requisitos y el estado esperado de la suite están en
`docs/reference/comandos.md`. **Un skip no es un pase**: el motivo, en
`docs/explanation/paridad-upstream.md`.
