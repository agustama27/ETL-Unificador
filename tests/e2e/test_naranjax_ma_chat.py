import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adapters.naranjax.ma_chat import MaChatAdapter
from orchestrator.models import RunRequest, RunResult, RunStatus, StateEffect, StateStatus
from orchestrator.run import main
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StateStore
from tests.support.synthetic_naranjax import write_result


TODAY = date(2026, 7, 21)
ETL = "naranjax.ma.chat.daily"


class RecordingService:
    def __init__(self, status: RunStatus) -> None:
        self.status = status
        self.request: RunRequest | None = None

    def execute(self, request):
        self.request = request
        return RunResult("run-1", self.status, None, (),
                         StateEffect("scope", StateStatus.NOT_STARTED))


class SyntheticRunner:
    def __init__(self) -> None:
        self.command: tuple[str, ...] = ()

    def run(self, command, cwd, env, timeout, *, secret_values):
        self.command = tuple(command)
        run = next(Path(value) for value in command if Path(value).name == "base.xlsx").parents[1]
        write_result(run)
        return ProcessEvidence(self.command, str(cwd), env, "synthetic", "", 0, False,
                               Termination.COMPLETED, ("start", "finish"))


def _base(tmp_path: Path) -> Path:
    base = tmp_path / "base.xlsx"
    base.write_bytes(b"synthetic")
    return base


def test_cli_help_and_required_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    help_text = capsys.readouterr().out
    assert all(flag in help_text for flag in (
        "--etl", "--fecha", "--base", "--input", "--param"
    ))

    with pytest.raises(SystemExit) as required_exit:
        main(["--etl", ETL])
    assert required_exit.value.code == 2


@pytest.mark.parametrize(
    ("status", "extras", "expected_exit", "no_planes"),
    [
        (RunStatus.SUCCEEDED, ["--input", "planes=planes.xlsx", "--input", "pagos=pagos.csv"], 0, False),
        (RunStatus.BLOCKED, ["--param", "no_planes_today"], 2, True),
        (RunStatus.FAILED, ["--param", "no_planes_today"], 1, True),
    ],
)
def test_cli_maps_arguments_and_terminal_statuses(
    tmp_path: Path, status: RunStatus, extras: list[str], expected_exit: int, no_planes: bool
) -> None:
    service = RecordingService(status)
    arguments = ["--etl", ETL, "--fecha", "20260721", "--base", str(_base(tmp_path)), *extras]

    assert main(arguments, service_factory=lambda definition, adapter: service) == expected_exit
    request = service.request
    assert request is not None
    assert request.business_date == TODAY
    assert bool(request.params.get("no_planes_today")) is no_planes
    assert request.inputs.get("planes") == (None if no_planes else Path("planes.xlsx"))
    assert request.inputs.get("pagos") == (None if no_planes else Path("pagos.csv"))


@pytest.mark.parametrize(
    ("requested_day", "expected_exit", "expected_status"),
    [("20260721", 0, "succeeded"), ("20260720", 2, "blocked")],
)
def test_synthetic_cli_run_always_writes_terminal_evidence(
    tmp_path: Path, requested_day: str, expected_exit: int, expected_status: str
) -> None:
    runner = SyntheticRunner()
    runs, state_root = tmp_path / "runs", tmp_path / "state"

    def factory(definition, adapter):
        state = StateStore(state_root)
        store = RunStore(runs, state_root,
                         now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc))
        return RunService(definition, MaChatAdapter(today=lambda: TODAY), runner, store, state,
                          workspace=Path.cwd(), now=lambda: "2026-07-21T15:00:00+00:00")

    exit_code = main([
        "--etl", ETL, "--fecha", requested_day, "--base", str(_base(tmp_path)),
        "--param", "no_planes_today",
    ], service_factory=factory)
    evidence = json.loads(next(runs.rglob("run.json")).read_text("utf-8"))

    assert exit_code == expected_exit
    assert evidence["status"] == expected_status
    assert evidence["lifecycle"][-1]["status"] == expected_status
    if expected_status == "succeeded":
        assert "--sin_planes_hoy" in runner.command and "--planes" not in runner.command
        assert {item["role"] for item in evidence["artifacts"]} == {"roman", "chat", "e1kia"}
        assert len(tuple(state_root.rglob("estado_*.csv"))) == 2
    else:
        assert runner.command == ()
        assert evidence["blocker"]["code"] == "validation_error"
        assert not state_root.exists()
