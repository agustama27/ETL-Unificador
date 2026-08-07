import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from etls.naranjax.ma_chat import MaChatAdapter
from etls.naranjax.ma_voice import MaVoiceAdapter
from etls.naranjax.ma_voice_pct import MaVoicePctAdapter
from etls.naranjax.mt_voice import MtVoiceAdapter
from etls.naranjax.mt_voice_back import MtVoiceBackAdapter
from etls.petersen.adapter import PetersenGestionesAdapter
from orchestrator.models import RunResult, RunStatus, StateEffect, StateStatus
from orchestrator.run import main
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StateStore
from tests.support.synthetic_naranjax import write_result


TODAY = date(2026, 7, 21)
MT = "naranjax.mt.voice.daily"


class RecordingService:
    def execute(self, request):
        return RunResult("run-1", RunStatus.SUCCEEDED, None, (),
                         StateEffect("scope", StateStatus.NOT_STARTED))


class SyntheticRunner:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.command: tuple[str, ...] = ()

    def run(self, command, cwd, env, timeout, *, secret_values):
        self.command = tuple(command)
        run = next(Path(value) for value in command if Path(value).name == "base.txt").parents[1]
        if self.mode in {"success", "missing", "ambiguous"}:
            write_result(run, self.mode, channel="mt")
        return ProcessEvidence(
            self.command, str(cwd), env, f"synthetic {run}", "",
            7 if self.mode == "nonzero" else (None if self.mode == "spawn" else 0),
            self.mode == "timeout",
            Termination.SPAWN_FAILED if self.mode == "spawn" else Termination.COMPLETED,
            ("start", "finish"), "spawn secret" if self.mode == "spawn" else None,
        )


def _base(tmp_path: Path) -> Path:
    path = tmp_path / "base.txt"
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
        "naranjax.mt.voice.back": MtVoiceBackAdapter(today=lambda: TODAY),
        "encuestacx.base": MaVoicePctAdapter(today=lambda: TODAY),
        "bancor.base": MaVoicePctAdapter(today=lambda: TODAY),
        "epec.base": MaVoicePctAdapter(today=lambda: TODAY),
        "fravega.base": MaVoicePctAdapter(today=lambda: TODAY),
        "clarouy.base": MaVoicePctAdapter(today=lambda: TODAY),
        "social.argentina": MaVoicePctAdapter(today=lambda: TODAY),
        "social.chile": MaVoicePctAdapter(today=lambda: TODAY),
        "petersen.gestiones": PetersenGestionesAdapter(today=lambda: TODAY),
    }


def test_cli_selects_mt_adapter(tmp_path: Path) -> None:
    adapters = _adapters()
    selected = []

    def factory(definition, adapter):
        selected.append((definition.id, adapter))
        return RecordingService()

    assert main(["--etl", MT, "--fecha", "20260721", "--base", str(_base(tmp_path))],
                adapters=adapters, service_factory=factory) == 0
    assert selected == [(MT, adapters["naranjax.mt.voice"])]


@pytest.mark.parametrize(
    ("mode", "day", "expected_exit", "status", "error", "ran"),
    [
        ("success", "20260721", 0, "succeeded", None, True),
        ("success", "20260720", 2, "blocked", "validation_error", False),
        ("nonzero", "20260721", 1, "failed", "nonzero_exit", True),
        ("timeout", "20260721", 1, "timed_out", "timeout", True),
        ("spawn", "20260721", 1, "failed", "spawn_failed", True),
        ("missing", "20260721", 1, "failed", "postcondition_failed", True),
        ("ambiguous", "20260721", 1, "failed", "postcondition_failed", True),
    ],
)
def test_synthetic_mt_cli_writes_terminal_evidence_without_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str, day: str,
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

    exit_code = main(["--etl", MT, "--fecha", day, "--base", str(_base(tmp_path))],
                     adapters=_adapters(), service_factory=factory)
    evidence = json.loads(next(runs.rglob("run.json")).read_text("utf-8"))

    assert exit_code == expected_exit
    assert capsys.readouterr().out.endswith(f"status={status}\n")
    assert evidence["status"] == status
    assert evidence["error"] == (None if error is None else {"code": error, "message": error.replace("_", " ")})
    assert bool(runner.command) is ran
    assert str(tmp_path) not in json.dumps(evidence)
    assert tuple(state_root.rglob("estado_*.csv")) == ()
    if status == "succeeded":
        assert {item["role"] for item in evidence["artifacts"]} == {"roman", "e1kia"}
        assert evidence["postconditions"] == {"outputs": "passed", "state": "not_applicable"}
        assert "--input" in runner.command and "--output_dir" in runner.command
        assert "--planes" not in runner.command and "--pagos" not in runner.command
