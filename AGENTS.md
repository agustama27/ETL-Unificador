# AGENTS.md — Guía para agentes de código

Este repositorio es una **capa de ejecución controlada** sobre ETLs legacy de cobranza:
sandbox por corrida, evidencia forense, locking por período y promoción durable de estado.
Antes de tocar código leé `README.md` y `docs/ARQUITECTURA.md`; la arquitectura objetivo
está en `docs/ADR-001-nucleo-hexagonal.md`.

## Reglas duras

1. **No modifiques los proyectos legacy** (`SOHO-*`, `soho-*`). Son cajas negras en
   producción, invocadas por subprocess. La lógica de negocio del cliente vive ahí, no en
   el núcleo.
2. **No modifiques los tests existentes.** Los 13 tests de `tests/e2e/` son la red de
   seguridad: si un refactor obliga a tocar uno, cambiaste comportamiento observable, no
   estructura. Corrélos antes y después de cualquier cambio al núcleo.
3. **No commitees datos reales:** `.csv`, `.xlsx`, `.xls`, `.env`, outputs generados ni
   nada bajo `var/`. Los artefactos y logs pueden contener PII.
4. **Mínimo blast radius:** ante la duda entre un cambio chico y uno prolijo, hacé el
   chico y anotá el prolijo como pendiente.

## ⚠️ MaVoicePctAdapter es el adapter genérico de facto

`MaVoicePctAdapter` está mapeado a **nueve ETLs de seis clientes**: `bancor.base`,
`epec.base`, `fravega.base`, `clarouy.base`, `encuestacx.base`, `social.argentina`,
`social.chile`, `naranjax.ma.chat.pct` y `naranjax.mt.voice.pct`. Si lo tocás para
arreglar algo de Naranja X, estás tocando seis clientes. Cualquier cambio ahí exige
correr los 13 e2e completos. La salida de fondo es la decisión 2 del ADR-001
(`SubprocessAdapter` con nombre honesto).

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
