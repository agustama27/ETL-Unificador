import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adapters.naranjax.ma_chat import MaChatAdapter
from adapters.naranjax.ma_voice import MaVoiceAdapter
from adapters.naranjax.ma_voice_pct import MaVoicePctAdapter
from adapters.naranjax.mt_voice import MtVoiceAdapter
from orchestrator.models import RunResult, RunStatus, StateEffect, StateStatus
from orchestrator.run import main
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StateStore
from tests.support.synthetic_naranjax import write_result


TODAY = date(2026, 7, 21)
ENTRIES = {
    "naranjax.ma.chat.pct": ("pct", "NARANJAX_PCT_20260721.csv"),
    "naranjax.mt.voice.pct": ("mt_pct", "DEELO_NAR_USUEVOLTIS_20260721.txt"),
}


class RecordingService:
    def execute(self, request):
        return RunResult("run-1", RunStatus.SUCCEEDED, None, (),
                         StateEffect("scope", StateStatus.NOT_STARTED))


class SyntheticRunner:
    def __init__(self, mode: str, channel: str) -> None:
        self.mode, self.channel = mode, channel
        self.command: tuple[str, ...] = ()

    def run(self, command, cwd, env, timeout, *, secret_values):
        self.command = tuple(command)
        run = next(Path(value) for value in command if Path(value).name == "base.csv").parents[1]
        if self.mode in {"success", "missing"}:
            write_result(run, self.mode, channel=self.channel)
        return ProcessEvidence(
            self.command, str(cwd), env, f"synthetic {run}", "",
            7 if self.mode == "nonzero" else 0, False, Termination.COMPLETED,
            ("start", "finish"), None,
        )


def _historial(tmp_path: Path) -> Path:
    path = tmp_path / "historial.csv"
    path.write_text("synthetic", encoding="utf-8")
    return path


def _adapters():
    return {
        "naranjax.ma.chat": MaChatAdapter(today=lambda: TODAY),
        "naranjax.ma.voice": MaVoiceAdapter(today=lambda: TODAY),
        "naranjax.ma.voice.pct": MaVoicePctAdapter(today=lambda: TODAY),
        "naranjax.mt.voice": MtVoiceAdapter(today=lambda: TODAY),
        "naranjax.ma.chat.pct": MaVoicePctAdapter(today=lambda: TODAY),
        "naranjax.mt.voice.pct": MaVoicePctAdapter(today=lambda: TODAY),
    }


@pytest.mark.parametrize("etl_id", tuple(ENTRIES))
def test_cli_selects_each_new_pct_adapter(tmp_path: Path, etl_id: str) -> None:
    adapters = _adapters()
    selected = []

    def factory(definition, adapter):
        selected.append((definition.id, adapter))
        return RecordingService()

    assert main(["--etl", etl_id, "--fecha", "20260721", "--base", str(_historial(tmp_path))],
                adapters=adapters, service_factory=factory) == 0
    assert selected == [(etl_id, adapters[etl_id])]


@pytest.mark.parametrize("etl_id", tuple(ENTRIES))
@pytest.mark.parametrize(
    ("mode", "day", "expected_exit", "status", "error", "ran"),
    [
        ("success", "20260721", 0, "succeeded", None, True),
        ("success", "20260720", 2, "blocked", "validation_error", False),
        ("nonzero", "20260721", 1, "failed", "nonzero_exit", True),
        ("missing", "20260721", 1, "failed", "postcondition_failed", True),
    ],
)
def test_synthetic_new_pct_cli_writes_terminal_evidence_without_state(
    tmp_path: Path, etl_id: str, mode: str, day: str,
    expected_exit: int, status: str, error: str | None, ran: bool,
) -> None:
    channel, artifact = ENTRIES[etl_id]
    runner = SyntheticRunner(mode, channel)
    runs, state_root = tmp_path / "runs", tmp_path / "state"

    def factory(definition, adapter):
        state = StateStore(state_root)
        store = RunStore(runs, state_root,
                         now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc))
        return RunService(definition, adapter, runner, store, state, workspace=Path.cwd(),
                          now=lambda: "2026-07-21T15:00:00+00:00")

    exit_code = main(["--etl", etl_id, "--fecha", day, "--base", str(_historial(tmp_path))],
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
            ("pct", f"output/{artifact}")
        ]
        assert evidence["postconditions"] == {"outputs": "passed", "state": "not_applicable"}
