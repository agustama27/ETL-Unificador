# ADR-001 — Núcleo hexagonal con adapters descubribles

- **Estado:** aceptado e implementado (2026-08-07)
- **Fecha:** 2026-08-06
- **Ámbito:** `orchestrator/`, `etl_core/`, `etls/`, `platform_api/`, `platform_mcp/`
- **Implementación:** las cinco fases del plan están en `main` vía
  [PR #91](https://github.com/agustama27/ETL-Unificador/pull/91) (Fase 0) y
  [PR #99](https://github.com/agustama27/ETL-Unificador/pull/99) (Fases 1-5, historia
  lineal; las PRs por fase #92-#96 documentan la review de cada tramo). Verificación de
  fidelidad de la Fase 3 en `docs/verificacion-migracion-fase-3.md`. Quedan parciales dos
  ítems de la Fase 4, anotados en su checklist.

---

## Contexto

El proyecto arrancó como unificador de los ETLs de Naranja X y en pocos meses creció a ocho
clientes, dieciséis ETLs catalogados, una API REST y una consola web. El núcleo de ejecución
—sandbox, evidencia forense, locking, promoción durable de estado— está bien resuelto y no se
discute en este ADR.

Lo que sí se discute es **dónde están las fronteras**. El crecimiento fue por adición sin revisar
la forma, y el resultado es que el núcleo quedó acoplado al primer cliente. El objetivo declarado
en `01_objetivo_proyecto_etl_unificador.md` era explícito:

> *Debe ser fácil agregar nuevos ETLs sin modificar el core.*

Hoy agregar un cliente obliga a tocar al menos cuatro archivos del núcleo.

### Síntomas observados

1. `orchestrator/service.py` importa `ValidationError` y `PostconditionError` desde
   `adapters/naranjax/ma_chat.py`. La flecha de dependencia va del núcleo al cliente.
2. `MaVoicePctAdapter` está mapeado a nueve ETLs de seis clientes. Es un adapter genérico con
   nombre de cliente. `PetersenGestionesAdapter` instancia `MaChatAdapter` sólo para reusar
   `outputs()`.
3. `RunRequest` tiene campos `planes`, `pagos` y `no_planes_today`: vocabulario de cobranzas de
   Naranja X en el contrato universal. Petersen tiene que validar en negativo que no lleguen.
4. `ArtifactRole` es un enum cerrado en `orchestrator/models.py`, y `FILE_ROLES` una tupla en
   `platform_api/main.py`. Un rol nuevo obliga a editar el núcleo y la API.
5. El registro de adapters es un `dict` privado (`_adapters()`) dentro de `orchestrator/run.py`,
   que `platform_api` importa cruzando la frontera de privacidad.
6. `orchestrator/state_store.py` importa `ctypes.wintypes` a nivel de módulo, lo que falla en
   Linux. El proyecto no puede correr en contenedor, CI ni cloud.
7. El conocimiento de un cliente está repartido en cinco lugares: `registry/<cliente>.yaml`,
   `adapters/<cliente>/`, el proyecto legacy, `tests/e2e/test_<cliente>_*.py` y
   `openspec/changes/implement-<cliente>-*/`.

### Fuerzas en juego

- Van a seguir entrando clientes. El costo marginal de agregar uno tiene que bajar, no subir.
- La meta declarada incluye que **un agente de código** pueda crear ETLs nuevos. Un agente
  necesita un patrón repetible y local, no cinco lugares a editar y seis adapters entre los que
  adivinar cuál imitar.
- Hay trece tests e2e que cubren un ETL cada uno. Son una red de seguridad excelente para
  refactorizar, y hoy están infrautilizados porque no corren en CI.
- Los ETLs legacy están en producción. Nada de esto justifica tocarlos.

---

## Decisión

Adoptar **Ports & Adapters (hexagonal)** de forma explícita, con registro de adapters por
descubrimiento y contrato de entradas genérico.

No es una reescritura. El núcleo actual se conserva casi entero: lo que cambia es dónde viven las
fronteras y cómo se registran los clientes.

### Decisión 1 — `etl_core/contracts.py` como único punto de acoplamiento

Se crea un módulo de contratos que contiene:

- `ETLAdapter` como `typing.Protocol` con `validate`, `command`, `outputs`, `stateful` y
  `requires_state_change`.
- Las excepciones compartidas `ValidationError` y `PostconditionError`.
- `SubprocessAdapter`: la implementación genérica que hoy vive disfrazada de `MaVoicePctAdapter`.

El núcleo importa sólo de acá. **Ningún módulo de `orchestrator/` vuelve a importar de
`adapters/`.** Para mantener compatibilidad durante la transición, `adapters/naranjax/ma_chat.py`
reexporta las excepciones desde su nueva ubicación.

### Decisión 2 — `SubprocessAdapter` genérico, con nombre honesto

Los nueve ETLs que hoy apuntan a `MaVoicePctAdapter` pasan a apuntar a `SubprocessAdapter`.
El comportamiento no cambia; cambia el nombre y la ubicación. Con eso, tocar el PCT de Naranja X
deja de impactar a Bancor, EPEC, Frávega, Claro UY, Encuesta CX y Social Learning.

`PetersenGestionesAdapter` deja de instanciar `MaChatAdapter` y compone `SubprocessAdapter`.

### Decisión 3 — Contrato de entradas genérico

`RunRequest` pierde los campos específicos de Naranja X:

```python
@dataclass(frozen=True)
class RunRequest:
    etl_id: str
    business_date: date
    inputs: Mapping[str, Path]        # rol → archivo
    params: Mapping[str, str | bool]  # flags declarados en el manifiesto
    environment: Mapping[str, str]
```

`planes`, `pagos` y `no_planes_today` pasan a ser roles y parámetros declarados en
`registry/naranjax.yaml`. El núcleo deja de conocer vocabulario de cobranzas.

En el mismo movimiento: `ArtifactRole` deja de ser enum cerrado y pasa a ser un string validado
contra los roles que el manifiesto declara, y `FILE_ROLES` en la API se deriva del catálogo en vez
de estar hardcodeado. Las rutas fijas `input/diarios/planes.xlsx` y `input/diarios/pagos.csv` salen
de `RunService._stage_inputs()` y pasan al adapter de Naranja X, que es el único que las necesita.

### Decisión 4 — Registro por descubrimiento

`_adapters()` desaparece. Cada manifiesto declara la ruta de importación de su adapter y el
catálogo lo resuelve por import dinámico:

```yaml
adapter: etls.petersen.adapter:PetersenGestionesAdapter
```

El catálogo valida que la clase importada satisfaga el `Protocol` antes de aceptar el ETL como
ejecutable. Agregar un cliente pasa a ser: agregar una carpeta. Cero archivos del núcleo tocados.

### Decisión 5 — Cliente = paquete autocontenido

Se reagrupa por cliente, no por capa técnica:

```
etls/petersen/
├── manifest.yaml      (hoy registry/petersen.yaml)
├── adapter.py         (hoy adapters/petersen/gestiones.py)
├── job.py             (hoy adapters/petersen/gestiones_job.py)
├── legacy/            (hoy soho-petersen-cobranzas-resultados/)
├── tests/
├── fixtures/
└── README.md          entradas, salidas, deadline, reglas, contacto
```

Un dev o un agente que entra a tocar Petersen abre una carpeta y ahí está todo.

### Decisión 6 — Linux-first

El import de `ctypes.wintypes` se mueve dentro de la rama Windows de `_windows_directory_api()`.
La abstracción ya existe en el código; sólo el import quedó afuera. Se agrega Dockerfile y pipeline
de CI que corra los trece e2e en Linux.

---

## Alternativas consideradas

**Dejar todo como está y documentar.** Descartada: el costo marginal de cada cliente nuevo sube, y
el acoplamiento `MaVoicePctAdapter` → seis clientes es un riesgo activo de producción, no una deuda
cosmética.

**Reescribir los ETLs legacy dentro de un framework común.** Descartada por lo mismo que en el
documento original: reescribir reglas de negocio en producción, sin tests de referencia del lado
del legacy, tiene un blast radius inaceptable. Los legacy siguen siendo cajas negras invocables.

**Plugins como paquetes pip separados, un repo por cliente.** Descartada por ahora: el equipo es
chico y la sobrecarga de versionado y publicación no se justifica. La decisión 5 deja el camino
abierto si en algún momento hace falta.

**Motor de reglas / DSL declarativo para reemplazar los adapters.** Descartada: los adapters
existentes son de 30 a 90 líneas cada uno y su lógica es genuinamente idiosincrática. Un DSL sería
más código que el que reemplaza.

---

## Consecuencias

### Positivas

- Agregar un cliente no toca el núcleo.
- Un cambio en un cliente no puede romper a otro por herencia accidental.
- El código de un cliente es local y legible: el patrón se puede copiar, por una persona o por un agente.
- El proyecto pasa a correr en Linux, contenedor y CI.
- El contrato genérico habilita el MCP y el scheduling sin trabajo extra de diseño.

### Negativas y costos

- Migración de tres a cuatro semanas de trabajo repartido, con riesgo concentrado en la Fase 2
  (cambio de `RunRequest`), que toca todos los adapters a la vez.
- Los trece e2e podrían necesitar ajustes de setup en la Fase 3 (cambian rutas). El comportamiento
  verificado no debe cambiar: si un e2e falla por otra razón, el refactor está mal.
- Durante la transición conviven `adapters/` y `etls/`. Hay que sostener la reexportación de
  compatibilidad hasta terminar.
- Las decisiones 3 y 5 rompen compatibilidad de import para cualquier consumidor externo. No
  detectamos ninguno, pero conviene verificar antes.

---

## Plan de migración

Cinco fases. Cada una es entregable por sí sola y deja el repo funcionando.

### Fase 0 — Desbloquear (~1 semana)

Sin esto, ninguna otra fase se puede verificar en serio.

- [x] Mover `from ctypes import wintypes` dentro de `_windows_directory_api()`
- [x] `README.md` raíz, `docs/ARQUITECTURA.md`, este ADR, `docs/GUIA_NUEVO_CLIENTE.md`
- [x] `bitbucket-pipelines.yml` que corra `pytest` completo en Linux
- [x] Completar `pyproject.toml`: `fastapi`, `uvicorn`, `python-multipart`; renombrar el extra
      `naranjax` a `etl` porque lo usan todos los clientes
- [x] `Dockerfile` + `docker-compose.yml`
- [x] `openspec/project.md` y `AGENTS.md` raíz con las convenciones de la sección 8 de ARQUITECTURA

**Criterio de aceptación:** un dev nuevo clona, corre `docker compose up` y ejecuta los trece e2e
en verde, en Linux, sin leer nada más que el README.

### Fase 1 — Enderezar dependencias (~1–2 semanas)

- [x] Crear `etl_core/contracts.py` con `ETLAdapter`, excepciones y `SubprocessAdapter`
- [x] `orchestrator/service.py` importa de `etl_core`, no de `adapters`
- [x] Reapuntar los nueve mapeos de `MaVoicePctAdapter` a `SubprocessAdapter`
- [x] `PetersenGestionesAdapter` compone `SubprocessAdapter` en vez de `MaChatAdapter`
- [x] Registro por descubrimiento; eliminar `_adapters()` y el import cruzado desde `platform_api`
- [x] Reexportaciones de compatibilidad en las ubicaciones viejas

**Criterio de aceptación:** ningún módulo de `orchestrator/` importa de `adapters/`. Los trece e2e
pasan **sin modificarse**. `grep -r "from adapters" orchestrator/` no devuelve nada.

### Fase 2 — Generalizar el contrato (~2 semanas)

Es la fase de mayor riesgo: toca todos los adapters a la vez.

- [x] `RunRequest` con `inputs` y `params` genéricos
- [x] `ArtifactRole` abierto, validado contra el manifiesto
- [x] `FILE_ROLES` derivado del catálogo
- [x] Mover las rutas `input/diarios/*` del servicio al adapter de Naranja X
- [x] Declarar `no_planes_today` y `--chat` como parámetros en el YAML
- [x] Actualizar CLI, API y frontend

**Criterio de aceptación:** `grep -ri "planes\|pagos" orchestrator/ platform_api/` no devuelve nada.
Los trece e2e pasan con ajustes de setup únicamente.

### Fase 3 — Reagrupar por cliente (~2–3 semanas)

- [x] Crear `etls/` y migrar **un cliente por PR**, empezando por Petersen (el más chico y sin estado)
- [x] Cada carpeta con su `README.md`: entradas, salidas, deadline, reglas de negocio, contacto
- [x] Orden sugerido: Petersen → Encuesta CX → Frávega → Claro UY → EPEC → Social Learning → Bancor → Naranja X

**Criterio de aceptación:** `registry/` y `adapters/` quedan vacíos. Agregar un cliente = agregar
una carpeta bajo `etls/`.

### Fase 4 — Endurecer para producción

- [x] Índice de corridas en SQLite; `list_runs` deja de escanear el filesystem
- [x] *(parcial)* Pool no-daemon + recuperación de huérfanas al arrancar; la cola persistente con reintentos sigue pendiente
- [x] Autenticación en la API
- [x] Política de retención para `var/runs/` y `var/uploads/` (contienen datos personales)
- [x] *(parcial)* `GET /api/schedule` cruza deadlines estructurados con las corridas del día; el disparo automático sigue pendiente
- [x] Alertas efectivas: `notify_dev` escribe en un `.jsonl` que nadie lee
- [x] Extender el `Redactor` o documentar explícitamente que no cubre PII

### Fase 5 — Superficie agéntica

- [x] Servidor MCP sobre la misma API: `list_etls`, `describe_etl`, `run_etl`, `get_run`,
      `download_artifact`
- [x] Plantilla `etls/_template/` que un agente pueda copiar para crear un cliente nuevo
- [x] Skill o guía de agente que codifique el flujo de la Fase 3

> La Fase 5 depende de la 3, no al revés. El MCP es la parte fácil; lo que realmente habilita que
> un agente cree ETLs nuevos es que cada cliente sea una carpeta autocontenida con un patrón
> repetible. Hoy un agente tendría que adivinar cuál de los seis adapters imitar y editar cuatro
> archivos del núcleo.

---

## Preguntas abiertas

Hay que responderlas antes de la Fase 2, porque cambian el diseño.

1. **¿La regla `business_date == today` es una restricción real del negocio o una simplificación
   del MVP?** Si las bases sólo existen el día que llegan, se queda. Si es una simplificación, hay
   que diseñar reproceso y backfill, y eso afecta el contrato de `RunRequest`.
2. **Los ETLs bloqueados por credenciales de Retell.ai** (Bancor resultados, Claro UY encuestas,
   EPEC tipificaciones, Frávega resultados, Petersen Retell) son el bloqueante que afecta a más
   clientes a la vez. ¿Está trabado por acceso, presupuesto o decisión?
3. **Bancor cupones** figura como "plantilla VBA en desarrollo". ¿Hoy lo hace una persona a mano?
   ¿Hay fecha de migración?
4. **OpenSpec:** hay trece cambios abiertos y dos archivados, y sólo tres tienen el set completo de
   artefactos. ¿Se retoma el proceso o se reemplaza? A mitad de camino confunde más de lo que ayuda.
