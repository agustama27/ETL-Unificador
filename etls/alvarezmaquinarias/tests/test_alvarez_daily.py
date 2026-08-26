import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from etl_core.contracts import SubprocessAdapter
from etls.alvarezmaquinarias.adapter import AlvarezMaquinariasAdapter
from etls.naranjax.ma_chat import MaChatAdapter
from etls.naranjax.ma_voice import MaVoiceAdapter
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
ALVAREZ = "alvarez.cobranzas.daily"


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
        run = next(Path(value) for value in command if Path(value).name == "base.csv").parents[1]
        if self.mode == "success":
            write_result(run, self.mode, channel="alvarez")
        return ProcessEvidence(
            self.command, str(cwd), env, f"synthetic {run}", "",
            7 if self.mode == "nonzero" else 0, False, Termination.COMPLETED,
            ("start", "finish"), None,
        )


def _inputs(tmp_path: Path) -> list[str]:
    for name in ("base.csv", "maquinarias.xlsx", "servicios.xlsx", "repuestos.pdf"):
        (tmp_path / name).write_text("synthetic", encoding="utf-8")
    return ["--base", str(tmp_path / "base.csv"),
            "--input", f"maquinarias={tmp_path / 'maquinarias.xlsx'}",
            "--input", f"servicios={tmp_path / 'servicios.xlsx'}",
            "--input", f"repuestos={tmp_path / 'repuestos.pdf'}"]


def _adapters():
    return {
        "etls.naranjax.ma_chat:MaChatAdapter": MaChatAdapter(today=lambda: TODAY),
        "etls.naranjax.ma_voice:MaVoiceAdapter": MaVoiceAdapter(today=lambda: TODAY),
        "etls.naranjax.mt_voice:MtVoiceAdapter": MtVoiceAdapter(today=lambda: TODAY),
        "etls.naranjax.mt_voice_back:MtVoiceBackAdapter": MtVoiceBackAdapter(today=lambda: TODAY),
        "etl_core.contracts:SubprocessAdapter": SubprocessAdapter(today=lambda: TODAY),
        "etls.petersen.adapter:PetersenGestionesAdapter": PetersenGestionesAdapter(today=lambda: TODAY),
        "etls.alvarezmaquinarias.adapter:AlvarezMaquinariasAdapter":
            AlvarezMaquinariasAdapter(today=lambda: TODAY),
    }


def test_cli_selects_alvarez_adapter_and_forwards_required_extras(tmp_path: Path) -> None:
    service = RecordingService()

    def factory(definition, adapter):
        return service

    assert main(["--etl", ALVAREZ, "--fecha", "20260721", *_inputs(tmp_path)],
                adapters=_adapters(), service_factory=factory) == 0
    staged = dict(service.requests[0].inputs)
    assert set(staged) == {"base", "maquinarias", "servicios", "repuestos"}


@pytest.mark.parametrize(
    ("mode", "day", "expected_exit", "status", "error", "ran"),
    [
        ("success", "20260721", 0, "succeeded", None, True),
        ("success", "20260720", 2, "blocked", "validation_error", False),
        ("nonzero", "20260721", 1, "failed", "nonzero_exit", True),
        ("missing", "20260721", 1, "failed", "postcondition_failed", True),
    ],
)
def test_alvarez_cli_lifecycle(
    tmp_path: Path, mode: str, day: str,
    expected_exit: int, status: str, error: str | None, ran: bool,
) -> None:
    runner = SyntheticRunner(mode)
    runs, state_root = tmp_path / "r", tmp_path / "s"

    def factory(definition, adapter):
        state = StateStore(state_root)
        store = RunStore(runs, state_root,
                         now=lambda: datetime(2026, 7, 21, 15, tzinfo=timezone.utc))
        return RunService(definition, adapter, runner, store, state, workspace=Path.cwd(),
                          now=lambda: "2026-07-21T15:00:00+00:00")

    exit_code = main(["--etl", ALVAREZ, "--fecha", day, *_inputs(tmp_path)],
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
            ("roman", "output/ALVAREZ_MAQUINARIAS_ROMAN_260721.csv"),
            ("e1kia", "output/ALVAREZ_MAQUINARIAS_E1KIA_260721.csv"),
        ]
        assert evidence["postconditions"] == {"outputs": "passed", "state": "not_applicable"}
        assert "--maquinarias" in runner.command
        assert "--servicios" in runner.command
        assert "--repuestos" in runner.command
