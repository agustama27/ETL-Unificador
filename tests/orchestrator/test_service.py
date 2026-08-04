import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from adapters.naranjax.ma_chat import MaChatAdapter
from adapters.naranjax.ma_voice_pct import MaVoicePctAdapter
from orchestrator.catalog import Catalog
from orchestrator.models import (ETLDefinition, InputSpec, Readiness,
                                 RepositoryStatus, RunRequest, RunStatus)
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StatePromotionError
from tests.support.synthetic_naranjax import write_result


TODAY, ETL, SECRET = date(2026, 7, 21), "naranjax.ma.chat.daily", "host-secret"


class FakeRunner:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls = 0

    def run(self, command: tuple[str, ...], cwd: Path, env: dict[str, str],
            timeout: int, *, secret_values: tuple[str, ...]) -> ProcessEvidence:
        self.calls += 1
        run = next(path for path in map(Path, command) if path.name == "base.xlsx").parents[1]
        if self.mode in {"success", "missing", "ambiguous", "promotion"}:
            write_result(run, "success" if self.mode == "promotion" else self.mode)
        (run / "logs" / "legacy.log").write_text(f"legacy {SECRET}", encoding="utf-8")
        exit_code = {"nonzero": 7, "spawn": None}.get(self.mode, 0)
        timed_out = self.mode == "timeout"
        termination = Termination.SPAWN_FAILED if self.mode == "spawn" else Termination.COMPLETED
        return ProcessEvidence(command + (SECRET,), str(cwd), env,
            f'out {SECRET} /srv/private/data.csv "/srv/private dir/data.csv" relative logs/stdout.log',
            r'err D:\Agents\private\input.xlsx "D:\Agents Private\input.xlsx" \\server\share\private.csv https://example.test/a', exit_code, timed_out,
            termination, ("start", "finish"), f"failure {SECRET}" if exit_code is None else None)


class FakeState:
    def __init__(self, root: Path, error: StatePromotionError | OSError | None = None) -> None:
        self.root = root
        self.error = error
        self.promotions = 0

    def promote(self, etl_id: str, business_date: date, staged: Path, run_id: str,
                *, require_change: bool = False) -> object:
        self.promotions += 1
        assert require_change is False
        assert staged.read_text("utf-8") == "state"
        if self.error:
            raise self.error
        return object()


def service(tmp_path: Path, mode: str = "success", state_error: Any = None):
    runner = FakeRunner(mode)
    state = FakeState(tmp_path / "state", state_error)
    store = RunStore(
        tmp_path / "runs", state.root,
        now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        uuid_factory=iter((f"id-{n}" for n in range(30))).__next__,
    )
    definition = Catalog.load(Path("registry/naranjax.yaml"), Path.cwd(),
                              adapters={"naranjax.ma.chat": object(),
                                        "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()})[ETL]
    subject = RunService(definition, MaChatAdapter(today=lambda: TODAY), runner, store, state,
                         workspace=Path.cwd(), now=lambda: "2026-07-21T15:00:00+00:00")
    return subject, runner, state, store


def request(tmp_path: Path, day: date = TODAY) -> RunRequest:
    base = tmp_path / "outside" / "base.xlsx"
    base.parent.mkdir(exist_ok=True)
    base.write_bytes(b"synthetic base")
    return RunRequest(ETL, day, base, no_planes_today=True,
                      environment={"NARANJAX_PLANES_MIN_COVERAGE": SECRET})


def record(store: RunStore) -> dict[str, Any]:
    return json.loads(next(store.runs_root.rglob("run.json")).read_text("utf-8"))


def test_success_persists_complete_relative_redacted_evidence(tmp_path: Path) -> None:
    subject, runner, state, store = service(tmp_path)
    result, evidence = subject.execute(request(tmp_path)), record(store)

    assert result.status is RunStatus.SUCCEEDED
    assert [event["status"] for event in evidence["lifecycle"]] == ["preparing", "running", "succeeded"]
    assert evidence["inputs"][0]["sha256"] == "68828f0b413235f5c2d7d6803a3570a7e3ebd0fd4481be30f82aa490082d788b"
    assert evidence["postconditions"] == {"outputs": "passed", "state": "promoted"}
    assert {item["role"] for item in evidence["artifacts"]} == {"roman", "chat", "e1kia"}
    assert evidence["logs"] == ["logs/stdout.log", "logs/stderr.log", "logs/legacy-legacy.log"]
    serialized = json.dumps(evidence)
    forbidden = (SECRET, str(tmp_path), "/srv/private/data.csv", r"D:\Agents\private\input.xlsx", r"\\server\share\private.csv", " dir/data.csv", r" Private\input.xlsx")
    logs = "".join(path.read_text("utf-8") for path in next(store.runs_root.iterdir()).rglob("*.log"))
    assert not any(value in serialized + logs for value in forbidden)
    assert "relative logs/stdout.log" in serialized and "https://example.test/a" in serialized
    assert (runner.calls, state.promotions) == (1, 1)


def test_historical_date_is_terminal_before_lock_or_process(tmp_path: Path) -> None:
    subject, runner, state, store = service(tmp_path)
    result = subject.execute(request(tmp_path, date(2026, 7, 20)))
    evidence = record(store)

    assert (result.status, result.error_code) == (RunStatus.BLOCKED, "validation_error")
    assert evidence["lifecycle"][-1]["status"] == "blocked"
    assert evidence["blocker"]["code"] == "validation_error"
    assert (runner.calls, state.promotions) == (0, 0)


@pytest.mark.parametrize("blocker", ("snapshot", "recovery", "lock"))
def test_state_and_lock_preflight_blockers_are_terminal(tmp_path: Path, blocker: str) -> None:
    subject, runner, state, store = service(tmp_path)
    lineage = state.root / ETL / "202607"
    lineage.mkdir(parents=True)
    code = {"snapshot": "snapshot_exists", "recovery": "recovery_required", "lock": "lock_exists"}[blocker]
    if blocker == "snapshot":
        (lineage / "estado_20260721.csv").write_text("old", encoding="utf-8")
    elif blocker == "recovery":
        (lineage / "recovery.json").write_text("{}", encoding="utf-8")
    else:
        store.acquire_lock(ETL, "202607", "other")

    result = subject.execute(request(tmp_path))
    assert (result.status, result.error_code) == (RunStatus.BLOCKED, code)
    assert record(store)["blocker"]["code"] == code
    assert (runner.calls, state.promotions) == (0, 0)


@pytest.mark.parametrize(
    "mode,status,code",
    (("spawn", RunStatus.FAILED, "spawn_failed"),
     ("nonzero", RunStatus.FAILED, "nonzero_exit"),
     ("timeout", RunStatus.TIMED_OUT, "timeout")),
)
def test_process_failures_preserve_terminal_evidence(
    tmp_path: Path, mode: str, status: RunStatus, code: str
) -> None:
    subject, _, state, store = service(tmp_path, mode)
    result = subject.execute(request(tmp_path))

    assert (result.status, result.error_code) == (status, code)
    assert record(store)["process"]["termination"] in {"completed", "spawn_failed"}
    assert state.promotions == 0


@pytest.mark.parametrize("mode", ("missing", "ambiguous"))
def test_invalid_outputs_fail_without_promotion(tmp_path: Path, mode: str) -> None:
    subject, _, state, store = service(tmp_path, mode)
    result = subject.execute(request(tmp_path))

    assert (result.status, result.error_code) == (RunStatus.FAILED, "postcondition_failed")
    assert record(store)["postconditions"]["outputs"] == "failed"
    assert state.promotions == 0


@pytest.mark.parametrize(
    "error,status,code",
    ((OSError("disk unavailable"), RunStatus.FAILED, "promotion_failed"),
     (StatePromotionError("recovery_required", "manual recovery"),
      RunStatus.BLOCKED, "recovery_required")),
)
def test_state_failures_are_terminal(
    tmp_path: Path, error: Exception, status: RunStatus, code: str
) -> None:
    subject, _, state, store = service(tmp_path, "promotion", error)
    result = subject.execute(request(tmp_path))

    assert (result.status, result.error_code) == (status, code)
    assert record(store)["state"]["status"] == (
        "recovery_required" if code == "recovery_required" else "staged"
    )
    assert state.promotions == 1


PCT = "naranjax.ma.voice.pct"


class PctRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, command: tuple[str, ...], cwd: Path, env: dict[str, str],
            timeout: int, *, secret_values: tuple[str, ...]) -> ProcessEvidence:
        self.calls += 1
        run = next(path for path in map(Path, command) if path.name == "base.csv").parents[1]
        write_result(run, channel="pct")
        return ProcessEvidence(command, str(cwd), env, "out", "err", 0, False,
                               Termination.COMPLETED, ("start", "finish"), None)


def test_stateless_pct_run_skips_preflight_staging_and_promotion(tmp_path: Path) -> None:
    runner = PctRunner()
    state = FakeState(tmp_path / "state")
    store = RunStore(
        tmp_path / "runs", state.root,
        now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        uuid_factory=iter((f"id-{n}" for n in range(30))).__next__,
    )
    definition = Catalog.load(Path("registry/naranjax.yaml"), Path.cwd(),
                              adapters={"naranjax.ma.chat": object(),
                                        "naranjax.ma.voice": object(),
                                        "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()})[PCT]
    subject = RunService(definition, MaVoicePctAdapter(today=lambda: TODAY), runner, store,
                         state, workspace=Path.cwd(), now=lambda: "2026-07-21T15:00:00+00:00")
    lineage = state.root / PCT / "202607"
    lineage.mkdir(parents=True)
    (lineage / "estado_20260721.csv").write_text("old", encoding="utf-8")
    base = tmp_path / "outside" / "historial.csv"
    base.parent.mkdir(exist_ok=True)
    base.write_text("synthetic", encoding="utf-8")

    result = subject.execute(RunRequest(PCT, TODAY, base))
    evidence = record(store)

    assert result.status is RunStatus.SUCCEEDED
    assert (runner.calls, state.promotions) == (1, 0)
    assert evidence["postconditions"] == {"outputs": "passed", "state": "not_applicable"}
    assert evidence["state"]["status"] == "not_started"
    assert evidence["inputs"][0]["path"].endswith("base.csv")
    assert {item["role"] for item in evidence["artifacts"]} == {"pct"}


def _extras_fixture(tmp_path: Path):
    definition = ETLDefinition(
        id="synthetic.back", name="Synthetic back",
        repository_status=RepositoryStatus.PRESENT, readiness=Readiness.READY,
        executable=True, project_path=Path("p"),
        command=("python", "job.py"), adapter="synthetic.back",
        inputs=(InputSpec("base", (".txt",), True),
                InputSpec("logcall", (".csv",), True),
                InputSpec("historial", (".csv",), True)),
        outputs=(), allowed_exits=(0,), timeout_seconds=900,
    )

    class ExtrasAdapter:
        stateful = False
        requires_state_change = False

        def validate(self, request):
            return None

        def command(self, definition, request, run):
            return ("noop", str(run / "input/base.txt"))

        def outputs(self, definition, before, after):
            return ()

    class ExtrasRunner:
        def run(self, command, cwd, env, timeout, *, secret_values):
            return ProcessEvidence(command, str(cwd), env, "out", "err", 0, False,
                                   Termination.COMPLETED, ("start", "finish"), None)

    state = FakeState(tmp_path / "state")
    store = RunStore(
        tmp_path / "runs", state.root,
        now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        uuid_factory=iter((f"id-{n}" for n in range(30))).__next__,
    )
    subject = RunService(definition, ExtrasAdapter(), ExtrasRunner(), store, state,
                         workspace=Path.cwd(), now=lambda: "2026-07-21T15:00:00+00:00")
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    for name in ("base.txt", "LOGCALL_x.csv", "historial_x.csv"):
        (outside / name).write_text("synthetic", encoding="utf-8")
    return subject, store, state, outside


def test_extras_stage_truthfully_with_validated_suffixes(tmp_path: Path) -> None:
    subject, store, state, outside = _extras_fixture(tmp_path)

    result = subject.execute(RunRequest(
        "synthetic.back", TODAY, outside / "base.txt",
        extras={"logcall": outside / "LOGCALL_x.csv",
                "historial": outside / "historial_x.csv"},
    ))
    evidence = record(store)

    assert result.status is RunStatus.SUCCEEDED
    staged = {item["role"]: item["path"] for item in evidence["inputs"]}
    assert staged["base"].endswith("base.txt")
    assert staged["logcall"].endswith("logcall.csv")
    assert staged["historial"].endswith("historial.csv")
    run_dir = next(store.runs_root.glob("synthetic.back/*"))
    assert (run_dir / "input/logcall.csv").exists()
    assert (run_dir / "input/historial.csv").exists()
    assert state.promotions == 0


def test_extra_with_undeclared_extension_is_terminal(tmp_path: Path) -> None:
    subject, store, _, outside = _extras_fixture(tmp_path)
    (outside / "logcall.xlsx").write_text("synthetic", encoding="utf-8")

    result = subject.execute(RunRequest(
        "synthetic.back", TODAY, outside / "base.txt",
        extras={"logcall": outside / "logcall.xlsx",
                "historial": outside / "historial_x.csv"},
    ))

    assert (result.status, result.error_code) == (RunStatus.FAILED, "validation_error")
    assert record(store)["error"]["code"] == "validation_error"
