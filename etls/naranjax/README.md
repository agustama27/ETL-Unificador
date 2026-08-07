# Naranja X

El cliente más grande: siete ETLs sobre tres proyectos legacy.

## ETLs

| ID | Adapter | Legacy | Descripción |
|---|---|---|---|
| `naranjax.ma.chat.daily` | `MaChatAdapter` (stateful) | `legacy/chat` | Base diaria MA Chat → ROMAN + CHAT + E1KIA |
| `naranjax.ma.voice.daily` | `MaVoiceAdapter` (stateful, exige cambio de estado) | `legacy/ma` | Base diaria MA Voz → ROMAN + E1KIA |
| `naranjax.ma.voice.pct` | `SubprocessAdapter` | `legacy/ma` | Tipificaciones PCT voz |
| `naranjax.ma.chat.pct` | `SubprocessAdapter` | `legacy/chat` | Tipificaciones PCT chat |
| `naranjax.mt.voice.pct` | `SubprocessAdapter` | `legacy/mt` | PCT MT (DEELO USUEVOLTIS) |
| `naranjax.mt.voice.back` | `MtVoiceBackAdapter` | `legacy/mt` | Back USUEVOLTIS (base+logcall+historial) |
| `naranjax.mt.voice.daily` | `MtVoiceAdapter` | `legacy/mt` | Base diaria MT vía `mt_voice_job.py` |

## Particularidades

- **Estado mensual**: los daily MA leen/escriben `estado_YYYYMM.csv`; la promoción durable
  y el bloqueo por recovery viven en el núcleo (`orchestrator/state_store.py`).
- **PLANES/PAGOS**: entradas opcionales de los daily MA; el hook `input_destination` de
  `MaChatAdapter` las ancla en `input/diarios/`. `no_planes_today` es el único parámetro.
- `--chat` viaja como `fixed_arguments` del manifiesto, no está hardcodeado en el adapter.

## Estructura

`manifest.yaml` · `ma_chat.py` / `ma_voice.py` / `mt_voice.py` / `mt_voice_back.py`
(adapters) · `ma_voice_pct.py` (alias de compatibilidad de `SubprocessAdapter`) ·
`mt_voice_job.py` (CLI puente MT) · `legacy/{chat,ma,mt}` (no tocar) · `tests/` (6 e2e +
6 unit).

## Deadline y contacto

Corridas diarias con la base del día. Equipo de operaciones Evoltis (canal Naranja X).
