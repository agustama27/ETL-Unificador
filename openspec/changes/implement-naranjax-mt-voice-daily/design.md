# Design: Implement Naranja X MT Voice Daily

## Decisions

### D1 — The wrapper is the missing legacy CLI, owned by the unifier

`main.py` and the `procesos.*` module CLIs cannot redirect outputs (fixed
`__file__`-anchored dirs) and autodetect inputs by mtime. The core functions
already accept explicit `archivo_entrada`/`output_dir`. The unifier ships
`adapters/naranjax/mt_voice_job.py`, spawned as a subprocess with the MT repo
as cwd; it inserts cwd into `sys.path`, imports `procesos.*`, and runs the
exact `main.py` chain with explicit sandbox paths. The orchestrator process
never imports legacy code — the boundary holds at the process level, exactly
as it does when operations runs `main.py` by hand.

### D2 — Wrapper contract is a strict mirror of main.py

```text
<active python> ../adapters/naranjax/mt_voice_job.py
  --input <run>/input/base.txt
  --output_dir <run>/output
```

- `procesar_base(input, output_dir)` -> ROMAN path; then
  `extraer_telefonos(roman, output_dir)` — E1KIA derives from that exact
  ROMAN, never from directory discovery.
- `FileNotFoundError`/`ValueError` -> message on stderr, exit 1 (same mapping
  as `main.py`); any other exception propagates as a nonzero exit.
- The wrapper path in the catalog command is relative to the MT working dir
  (`../adapters/...`), keeping the command array fully declarative.

### D3 — Adapter mirrors the PCT stateless shape

`MtVoiceAdapter`: `stateful = False`, `requires_state_change = False`,
shared today-gate, rejects PLANES/PAGOS/no-PLANES intents, delegates output
classification to the shared role loop (`roman` + `e1kia`, `YYMMDD`,
`output_date_source: system_date`). Staging reuses suffix preservation:
`input/base.txt` via catalog extension `.txt`.

### D4 — Catalog keeps `roman`/`e1kia` roles for MT

MT outputs are the same conceptual artifacts as MA Voice (dialer base and
phone extract), so the existing roles are reused with MT-specific globs
(`NARANJAX_MT_ROMAN_*.csv`, `NARANJAX_MT_E1KIA_*.csv`). No new enum values.

### D5 — Two slices, mirroring the Voice/PCT chains

Slice 1: wrapper + adapter + complete-but-inert catalog metadata + unit tests.
Slice 2: promotion + CLI registration + synthetic E2E + docs + SDD close.
Each stays below 400 changed lines.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Edit legacy `main.py` to add `--input`/`--output_dir` | Legacy edits out of scope; needs its own regression suite |
| Run `main.py` with sandbox cwd | Paths are `__file__`-anchored; cwd changes nothing |
| Copy sandbox into legacy dirs and back | Mutates the legacy repo and races operations |
| Orchestrator imports `procesos` directly | Breaks the process boundary and dependency isolation |

## Test Strategy

- Wrapper: unit test against the real `procesos` modules with a synthetic
  33-column TXT (valid, wrong-column-count, empty) asserting outputs and exits.
- Adapter: exact command, today gate, daily-intent rejection, ROMAN/E1KIA
  classification (missing/unchanged/wrong-date/ambiguous per role).
- Catalog: all four entries executable; complete MT metadata.
- Synthetic CLI E2E: success (both artifacts, `state: not_applicable`, no
  lineage), non-today block, nonzero/timeout/spawn failures, missing output,
  redaction.
- Real fixture-driven platform run with a generated synthetic TXT (not
  committed) as final verification.
