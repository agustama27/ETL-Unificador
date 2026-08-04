# Exploration: Naranja X MT Voice Back (USUEVOLTIS)

## Question

Can `naranjax.mt.voice.back` — the last legacy job outside the catalog — be
promoted, and what does its three-input contract require from the core?

## Contract Evidence

The job had no dedicated suite; PR #56 added an additive contract suite
driving `main.py --back` as a subprocess (MT back-resultados now 10 passed):
output structure, ACTIGROUP filter, RESULT mapping, anomalies file, non-txt
M30 rejection, and exit codes.

## Exact Legacy Contract

### Entry point

```text
python main.py --back
  [--logcall FILE.csv] [--historial FILE.csv] [--m30 FILE.txt]
  [--back-output-dir DIR]
  [--strict-phone-quality] [--max-phone-irrecoverable-ratio R]
```

All inputs autodiscover by mtime when omitted (LOGCALL under
`back_recibida/logcall/`, historial under `back_recibida/historial/`, M30
under `base_recibida/`) — the adapter MUST always pass all three explicitly
plus the sandbox output dir. `FileNotFoundError`/`ValueError` map to stderr +
exit 1; success exits 0.

### Inputs

| Input | Format | Used columns/shape |
|---|---|---|
| LOGCALL | CSV, sniffed delimiter | `ACTIGROUP` (rows kept only when `M`), `RESULT`, `PHONE`, `CALLREFID`, `LOGDATE`, `LOGTIME` |
| historial | CSV, comma | `[Entrada] user_number` key; optional customer/tipification/compromiso columns |
| M30OLOS | `.txt` pipe 33 columns (same file as the daily input); non-`.txt` rejected | customer/phone slots build the match index |

### Outputs (system date)

| Artefact | Pattern | Contract |
|---|---|---|
| USUEVOLTIS | `DEELO_NAR_USUEVOLTIS_%Y%m%d_%H.txt` | `\|`, UTF-8, **CRLF**, 40 columns; col 3 `NARANJA`, col 7 correlativo 1..N, col 8 `USUEVOLTIS`, col 10 `MAKE CALL`, col 36 `EVOLTIS`, col 39 `PENDING` |
| anomalías | `_anomalias_%Y%m%d_%H%M%S.txt` | Always written, grouped counters + detail lines |

Both filenames embed today's `%Y%m%d` followed by `_` — compatible with the
existing `YYYYMMDD` postcondition date check. State: none (stateless).

## The Core Gap: three inputs

`RunRequest` models exactly `base`/`planes`/`pagos`, and staging hardcodes
their destinations. The back job needs M30 (`base`, `.txt` — it IS the
monthly base file) plus two job-specific inputs (`logcall`, `historial`).

| Option | Verdict |
|---|---|
| Map logcall/historial onto planes/pagos | Rejected — stages lies (`planes.xlsx` holding a LOGCALL) into evidence |
| Job-specific CLI flags (`--logcall`) | Rejected — per-ETL flags erode the generic CLI |
| Generic `extras: Mapping[role, Path]` on `RunRequest` + repeatable CLI `--input ROLE=PATH`, staged as `input/<role><suffix>` | **Chosen** — roles are already free-form in catalog input specs; staging stays truthful |

## Second Output Role

The anomalies report is a mandatory artifact. Add `ArtifactRole.ANOMALIES`
(`anomalies`) and classify it like any role: exactly one new today-dated
`_anomalias_*.txt` per run.
