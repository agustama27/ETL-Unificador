# AGENTS.md — Guía para agentes de código

Este repositorio es una **capa de ejecución controlada** sobre ETLs legacy de cobranza:
sandbox por corrida, evidencia forense, locking por período y promoción durable de estado.
Antes de tocar código leé `README.md` y `docs/ARQUITECTURA.md`; la arquitectura objetivo
está en `docs/ADR-001-nucleo-hexagonal.md`.

## Reglas duras

1. **No modifiques los proyectos legacy** (`etls/*/legacy/`). Son cajas negras en
   producción, invocadas por subprocess. La lógica de negocio del cliente vive ahí, no en
   el núcleo.
2. **No modifiques los tests existentes.** Los 13 tests de `tests/e2e/` son la red de
   seguridad: si un refactor obliga a tocar uno, cambiaste comportamiento observable, no
   estructura. Corrélos antes y después de cualquier cambio al núcleo.
3. **No commitees datos reales:** `.csv`, `.xlsx`, `.xls`, `.env`, outputs generados ni
   nada bajo `var/`. Los artefactos y logs pueden contener PII.
4. **Mínimo blast radius:** ante la duda entre un cambio chico y uno prolijo, hacé el
   chico y anotá el prolijo como pendiente.

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

## Convenciones de código (docs/ARQUITECTURA.md §8)

- **Python 3.12+.** Se usan `StrEnum`, `Self`, `X | None`, `is_relative_to`.
- **Inmutabilidad.** Modelos `@dataclass(frozen=True)`; los mapas se envuelven en
  `MappingProxyType` en `__post_init__`.
- **Inyección de dependencias por constructor con default.** `Runner(popen=..., clock=...)`,
  `StateStore(replace=..., file_fsync=...)`. Es lo que hace testeable el núcleo sin tocar
  disco. Mantenelo.
- **Excepciones con atributo `code`.** `RunBlockedError` y `StatePromotionError` llevan un
  `code` que termina en `run.json`. Los códigos nuevos se documentan en la sección 3 de
  `docs/ARQUITECTURA.md`.
- **Errores acotados.** Nada de `except Exception` genérico en el núcleo; se capturan
  tipos concretos. Única excepción documentada: la frontera fail-fast de los `*_job.py`.
- **Sin comentarios decorativos.** Docstring de una línea cuando el nombre no alcanza.
- **Nombres del dominio en inglés en el código, mensajes de usuario en español.** La API
  responde en español porque la consume el equipo de operaciones.

## Cómo verificar

```bash
pip install -e ".[test,etl,api]"
pytest            # 284 tests; testpaths apunta a tests/, no toca los legacy
```
