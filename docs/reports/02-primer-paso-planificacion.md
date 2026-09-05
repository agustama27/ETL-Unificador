# Primer paso del proyecto — Relevamiento y planificación técnica

## 1. Objetivo de este primer paso

Antes de implementar código funcional, el agente de IA de código debe realizar un **relevamiento técnico del repositorio** y entregar una **planificación detallada de implementación** para construir el primer MVP del ETL Unificador.

En esta etapa no se busca reescribir ETLs ni crear una UI. Se busca entender el estado real del repositorio, confirmar qué proyectos están disponibles y diseñar el primer incremento de manera segura.

## 2. Contexto del proyecto

El objetivo general es construir un sistema unificador de distintos ETLs hoy separados.

El primer dominio elegido es **Naranja X**, comenzando por estos proyectos:

```text
SOHO-Chat-NX_MA-ETL/
soho-naranjaX-MA-etl/
soho-naranjaX-MT-etl/
```

El primer piloto recomendado es:

```text
SOHO-Chat-NX_MA-ETL/
```

porque ya cuenta con ejecución diaria y una variante clara de generación de output chat mediante el flag `--chat`.

## 3. Regla principal de esta fase

No implementar todavía el runner final sin antes planificar.

El agente debe crear primero un documento de planificación dentro del repositorio, por ejemplo:

```text
docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md
```

Ese documento debe contener el diseño propuesto, decisiones, riesgos, estructura de archivos y pasos de implementación.

## 4. Tareas del agente de código

### 4.1 Crear rama de trabajo

Crear una rama específica para esta fase:

```bash
feature/plan-mvp-etl-unificador-naranjax
```

Si la rama ya existe, reutilizarla o indicar el estado actual.

### 4.2 Relevar estructura real del repo

Inspeccionar el árbol del repositorio y confirmar la existencia de:

```text
SOHO-Chat-NX_MA-ETL/
soho-naranjaX-MA-etl/
soho-naranjaX-MT-etl/
```

Para cada carpeta encontrada, documentar:

```text
- Si existe o no existe
- Archivos README / documentación disponibles
- Entry points principales
- Comandos de ejecución existentes
- Dependencias
- Tests disponibles
- Carpetas de entrada
- Carpetas de salida
- Carpetas de estado
- Carpeta de logs
```

Si `soho-naranjaX-MT-etl/` no existe en el repo, no asumir su estructura. Dejarlo explícitamente como pendiente.

### 4.3 Relevar el ETL piloto: SOHO-Chat-NX_MA-ETL

Analizar especialmente:

```text
SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py
SOHO-Chat-NX_MA-ETL/core/modelos.py
SOHO-Chat-NX_MA-ETL/core/procesar_dia.py
SOHO-Chat-NX_MA-ETL/back-base/back_base_etl/constants.py
SOHO-Chat-NX_MA-ETL/back-base/back_base_etl/transformers.py
```

Identificar con precisión:

```text
- Argumentos CLI requeridos y opcionales
- Cómo se pasa la fecha
- Cómo se pasa la base mensual
- Cómo se pasan PLANES y PAGOS
- Cómo se activa el modo chat
- Cómo se indica que no hay planes del día
- Qué outputs genera
- Dónde escribe logs
- Dónde guarda estado persistente
- Qué ocurre si falla
- Qué exit code devuelve
```

### 4.4 Relevar el ETL MA voz: soho-naranjaX-MA-etl

Analizar:

```text
soho-naranjaX-MA-etl/back-base/ejecutar_dia.py
soho-naranjaX-MA-etl/core/modelos.py
soho-naranjaX-MA-etl/core/procesar_dia.py
soho-naranjaX-MA-etl/back-resultados/
```

Identificar diferencias con Chat MA:

```text
- Outputs generados
- Presencia o ausencia de output chat
- Contrato ROMAN
- Contrato E1KIA
- Contrato PCT
- Argumentos CLI
- Uso de estado persistente
- Uso de PLANES/PAGOS
```

### 4.5 Definir catálogo inicial de ETLs

Proponer un archivo de catálogo inicial:

```text
registry/naranjax.yaml
```

El catálogo debe declarar al menos estos ETLs, aunque alguno quede pendiente:

```yaml
etls:
  - id: naranjax.ma.chat.daily
    name: Naranja X MA Chat - Proceso diario
    status: ready_for_adapter

  - id: naranjax.ma.voice.daily
    name: Naranja X MA Voz - Proceso diario
    status: ready_for_adapter

  - id: naranjax.ma.voice.pct
    name: Naranja X MA Voz - Tipificaciones PCT
    status: pending_review

  - id: naranjax.mt.voice.daily
    name: Naranja X MT Voz - Proceso diario
    status: pending_repository_check
```

El agente debe proponer el schema final del YAML, incluyendo:

```text
- id
- name
- project_path
- working_dir
- command
- arguments
- required_inputs
- optional_inputs
- output_patterns
- stateful
- date_format
- timeout_seconds
- environment_variables
```

### 4.6 Diseñar el runner común

Proponer la estructura del runner, sin implementarlo todavía o implementando solo stubs si fuera necesario.

Diseño esperado:

```text
orchestrator/
├── models.py
├── runner.py
├── run_store.py
├── file_manager.py
└── logging_utils.py
```

El plan debe explicar responsabilidades:

```text
models.py
  Define RunRequest, RunResult, ETLDefinition, InputFileSpec, OutputFileSpec.

runner.py
  Ejecuta subprocess con cwd controlado, timeout, stdout/stderr y exit_code.

run_store.py
  Crea carpetas runs/, escribe run.json y permite consultar metadata histórica.

file_manager.py
  Copia inputs al sandbox, prepara output_dir/state_dir/logs_dir/processed_dir.

logging_utils.py
  Normaliza captura de logs y archivos .log.
```

### 4.7 Diseñar sandbox de ejecución

Proponer estructura por corrida:

```text
runs/
└── <etl_id>/
    └── <fecha_hora>/
        ├── input/
        ├── output/
        ├── logs/
        ├── state/
        ├── processed/
        └── run.json
```

Definir qué archivos se copian, cuáles se generan y cómo se detectan outputs.

### 4.8 Definir primer comando objetivo

El primer comando del unificador debería verse conceptualmente así:

```bash
python -m orchestrator.run \
  --etl naranjax.ma.chat.daily \
  --fecha 20260619 \
  --base ./inputs/base.xlsx \
  --planes ./inputs/planes.xlsx \
  --pagos ./inputs/pagos.csv
```

El agente debe validar si este diseño es compatible con el CLI real del ETL piloto y, si no lo es, proponer una alternativa.

### 4.9 Definir criterios de aceptación del MVP

El plan debe incluir criterios de aceptación claros:

```text
- Se puede ejecutar Naranja X MA Chat desde el unificador.
- La corrida queda aislada bajo runs/.
- Se genera run.json.
- Se capturan stdout y stderr.
- Se guarda exit_code.
- Se detectan outputs esperados.
- Si el proceso falla, el error queda registrado.
- No se modifican reglas de negocio del ETL legacy.
- No se suben datos reales ni outputs al repo.
```

### 4.10 Identificar riesgos

El agente debe documentar riesgos, por ejemplo:

```text
- El ETL legacy puede depender de rutas relativas internas.
- Los outputs pueden usar distintos formatos de fecha.
- Algunos outputs se generan con YYYYMMDD y otros con YYMMDD.
- La persistencia de estado puede necesitar sobrevivir entre corridas.
- Los inputs reales no deben commitearse.
- Puede haber diferencias entre MA Chat, MA Voz y MT.
- El repo puede no contener todavía MT.
```

## 5. Entregable esperado

El entregable de esta fase es un documento de planificación, no el producto terminado.

Crear:

```text
docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md
```

Debe incluir:

```text
1. Inventario real del repositorio.
2. Diagnóstico de los ETLs Naranja X disponibles.
3. Propuesta de arquitectura del MVP.
4. Schema propuesto para registry/naranjax.yaml.
5. Diseño del runner común.
6. Diseño de sandbox por ejecución.
7. Primer ETL piloto recomendado.
8. Plan de implementación por fases.
9. Criterios de aceptación.
10. Riesgos y dudas abiertas.
```

## 6. Qué no hacer todavía

En este primer paso, evitar:

```text
- No crear API FastAPI todavía.
- No crear UI todavía.
- No refactorizar lógica interna de los ETLs.
- No cambiar reglas de negocio de Naranja X.
- No modificar outputs existentes.
- No eliminar archivos legacy.
- No mover carpetas de proyectos sin plan aprobado.
- No hardcodear rutas absolutas.
```

## 7. Forma de trabajo esperada

El agente debe trabajar de forma conservadora:

```text
1. Leer antes de modificar.
2. Confirmar estructura real.
3. Documentar supuestos.
4. Mantener bajo impacto.
5. Proponer antes de implementar.
6. Separar claramente planificación de ejecución.
```

## 8. Resultado final de esta fase

Al finalizar, debe quedar claro:

```text
- Qué ETL se va a integrar primero.
- Qué comando real se va a envolver.
- Qué inputs necesita.
- Qué outputs genera.
- Cómo se va a registrar cada corrida.
- Qué estructura de carpetas se va a crear.
- Qué archivos se modificarán en la siguiente fase.
```

El siguiente paso, después de aprobar esta planificación, será implementar el MVP del runner para ejecutar `naranjax.ma.chat.daily` desde el unificador.
