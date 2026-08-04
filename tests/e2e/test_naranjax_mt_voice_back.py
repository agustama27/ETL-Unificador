import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adapters.naranjax.ma_chat import MaChatAdapter
from adapters.naranjax.ma_voice import MaVoiceAdapter
from adapters.naranjax.ma_voice_pct import MaVoicePctAdapter
from adapters.naranjax.mt_voice import MtVoiceAdapter
from adapters.naranjax.mt_voice_back import MtVoiceBackAdapter
from orchestrator.models import RunResult, RunStatus, StateEffect, StateStatus
from orchestrator.run import main
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StateStore
from tests.support.synthetic_naranjax import write_result


TODAY = date(2026, 7, 21)
BACK = "naranjax.mt.voice.back"


class RecordingService:
    def __init__(self) -> None:
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return RunResult("run-1", RunStatus.SUCCEEDED, None, (),
                         StateEffect("scope", StateStatus.NOT_STARTED))


class SyntheticRunner:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.command: tuple[str, ...] = ()

    def run(self, command, cwd, env, timeout, *, secret_values):
        self.command = tuple(command)
        run = next(Path(value) for value in command if Path(value).name == "base.txt").parents[1]
        if self.mode in {"success", "missing"}:
            write_result(run, self.mode, channel="back")
        return ProcessEvidence(
            self.command, str(cwd), env, f"synthetic {run}", "",
            7 if self.mode == "nonzero" else 0, False, Termination.COMPLETED,
            ("start", "finish"), None,
        )


def _inputs(tmp_path: Path) -> list[str]:
    for name in ("m30.txt", "LOGCALL.csv", "historial.csv"):
        (tmp_path / name).write_text("synthetic", encoding="utf-8")
    return ["--base", str(tmp_path / "m30.txt"),
            "--input", f"logcall={tmp_path / 'LOGCALL.csv'}",
            "--input", f"historial={tmp_path / 'historial.csv'}"]


def _adapters():
    return {
        "naranjax.ma.chat": MaChatAdapter(today=lambda: TODAY),
        "naranjax.ma.voice": MaVoiceAdapter(today=lambda: TODAY),
        "naranjax.ma.voice.pct": MaVoicePctAdapter(today=lambda: TODAY),
        "naranjax.mt.voice": MtVoiceAdapter(today=lambda: TODAY),
        "naranjax.ma.chat.pct": MaVoicePctAdapter(today=lambda: TODAY),
        "naranjax.mt.voice.pct": MaVoicePctAdapter(today=lambda: TODAY),
        "naranjax.mt.voice.back": MtVoiceBackAdapter(today=lambda: TODAY),
        "encuestacx.base": MaVoicePctAdapter(today=lambda: TODAY),
        "bancor.base": MaVoicePctAdapter(today=lambda: TODAY),
        "epec.base": MaVoicePctAdapter(today=lambda: TODAY),
    }


def test_cli_selects_back_adapter_and_forwards_extras(tmp_path: Path) -> None:
    adapters = _adapters()
    service = RecordingService()
    selected = []

    def factory(definition, adapter):
        selected.append((definition.id, adapter))
        return service

    assert main(["--etl", BACK, "--fecha", "20260721", *_inputs(tmp_path)],
                adapters=adapters, service_factory=factory) == 0
    assert selected == [(BACK, adapters[BACK])]
    assert dict(service.requests[0].extras) == {
        "logcall": tmp_path / "LOGCALL.csv", "historial": tmp_path / "historial.csv"
    }


@pytest.mark.parametrize(
    ("mode", "day", "with_extras", "expected_exit", "status", "error", "ran"),
    [
        ("success", "20260721", True, 0, "succeeded", None, True),
        ("success", "20260720", True, 2, "blocked", "validation_error", False),
        ("success", "20260721", False, 2, "blocked", "validation_error", False),
        ("nonzero", "20260721", True, 1, "failed", "nonzero_exit", True),
        ("missing", "20260721", True, 1, "failed", "postcondition_failed", True),
    ],
)
def test_synthetic_back_cli_writes_terminal_evidence_without_state(
    tmp_path: Path, mode: str, day: str, with_extras: bool,
    expected_exit: int, status: str, error: str | None, ran: bool,
) -> None:
    runner = SyntheticRunner(mode)
    runs, state_root = tmp_path / "runs", tmp_path / "state"

    def factory(definition, adapter):
        state = StateStore(state_root)
        store = RunStore(runs, state_root,
                         now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc))
        return RunService(definition, adapter, runner, store, state, workspace=Path.cwd(),
                          now=lambda: "2026-07-21T15:00:00+00:00")

    arguments = _inputs(tmp_path)
    if not with_extras:
        arguments = arguments[:2]
    exit_code = main(["--etl", BACK, "--fecha", day, *arguments],
                     adapters=_adapters(), service_factory=factory)
    evidence = json.loads(next(runs.rglob("run.json")).read_text("utf-8"))

    assert exit_code == expected_exit
    assert evidence["status"] == status
    assert evidence["error"] == (None if error is None else {"code": error, "message": error.replace("_", " ")})
    assert bool(runner.command) is ran
    assert str(tmp_path) not in json.dumps(evidence)
    assert tuple(state_root.rglob("estado_*.csv")) == ()
    if status == "succeeded":
        assert [(item["role"], item["path"]) for item in evidence["artifacts"]] == [
            ("pct", "output/DEELO_NAR_USUEVOLTIS_20260721_15.txt"),
            ("anomalies", "output/_anomalias_20260721_153000.txt"),
        ]
        assert evidence["postconditions"] == {"outputs": "passed", "state": "not_applicable"}
        staged = {item["role"] for item in evidence["inputs"]}
        assert staged == {"base", "logcall", "historial"}
        assert "--back" in runner.command and "--m30" in runner.command
