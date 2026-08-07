import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from etls.naranjax.ma_chat import MaChatAdapter
from etls.naranjax.ma_voice import MaVoiceAdapter
from etl_core.contracts import SubprocessAdapter
from etls.naranjax.mt_voice import MtVoiceAdapter
from etls.naranjax.mt_voice_back import MtVoiceBackAdapter
from etls.petersen.adapter import PetersenGestionesAdapter
from orchestrator.catalog import CatalogError
from orchestrator.models import RunResult, RunStatus, StateEffect, StateStatus
from orchestrator.run import main
from orchestrator.run_store import RunStore
from orchestrator.runner import ProcessEvidence, Termination
from orchestrator.service import RunService
from orchestrator.state_store import StateStore
from tests.support.synthetic_naranjax import write_result


TODAY = date(2026, 7, 21)
VOICE = "naranjax.ma.voice.daily"


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
        run = next(Path(value) for value in command if Path(value).name == "base.xlsx").parents[1]
        if self.mode in {"success", "missing"}:
            write_result(run, self.mode, channel="voice")
        return ProcessEvidence(
            self.command, str(cwd), env, f"synthetic {run}", "",
            7 if self.mode == "nonzero" else (None if self.mode == "spawn" else 0),
            self.mode == "timeout",
            Termination.SPAWN_FAILED if self.mode == "spawn" else Termination.COMPLETED,
            ("start", "finish"), "spawn secret" if self.mode == "spawn" else None,
        )


def _base(tmp_path: Path) -> Path:
    path = tmp_path / "base.xlsx"
    path.write_bytes(b"synthetic")
    return path


def _adapters():
    return {
        "etls.naranjax.ma_chat:MaChatAdapter": MaChatAdapter(today=lambda: TODAY),
        "etls.naranjax.ma_voice:MaVoiceAdapter": MaVoiceAdapter(today=lambda: TODAY),
        "etls.naranjax.mt_voice:MtVoiceAdapter": MtVoiceAdapter(today=lambda: TODAY),
        "etls.naranjax.mt_voice_back:MtVoiceBackAdapter": MtVoiceBackAdapter(today=lambda: TODAY),
        "etl_core.contracts:SubprocessAdapter": SubprocessAdapter(today=lambda: TODAY),
        "etls.petersen.adapter:PetersenGestionesAdapter": PetersenGestionesAdapter(today=lambda: TODAY),
    }


@pytest.mark.parametrize(
    ("etl_id", "adapter_key"),
    [("naranjax.ma.chat.daily", "etls.naranjax.ma_chat:MaChatAdapter"),
     (VOICE, "etls.naranjax.ma_voice:MaVoiceAdapter")],
)
def test_cli_selects_catalog_adapter(tmp_path: Path, etl_id: str, adapter_key: str) -> None:
    adapters = _adapters()
    selected = []

    def factory(definition, adapter):
        selected.append((definition.id, adapter))
        return RecordingService()

    assert main(["--etl", etl_id, "--fecha", "20260721", "--base", str(_base(tmp_path)),
                 "--param", "no_planes_today"], adapters=adapters, service_factory=factory) == 0
    assert selected == [(etl_id, adapters[adapter_key])]


def test_cli_rejects_unregistered_executable_adapter_before_service(tmp_path: Path) -> None:
    called = []
    incomplete = {key: value for key, value in _adapters().items()
                  if key != "etls.naranjax.mt_voice:MtVoiceAdapter"}
    with pytest.raises(CatalogError, match="adapter"):
        main(["--etl", "naranjax.mt.voice.daily", "--fecha", "20260721",
              "--base", str(_base(tmp_path))], adapters=incomplete,
             service_factory=lambda definition, adapter: called.append(adapter))
    assert called == []


def test_cli_rejects_unknown_etl_before_service(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="unknown ETL"):
        main(["--etl", "unknown", "--fecha", "20260721", "--base", str(_base(tmp_path))],
             adapters=_adapters())


@pytest.mark.parametrize(
    ("mode", "day", "expected_exit", "status", "error", "ran"),
    [
        ("success", "20260721", 0, "succeeded", None, True),
        ("success", "20260720", 2, "blocked", "validation_error", False),
        ("nonzero", "20260721", 1, "failed", "nonzero_exit", True),
        ("timeout", "20260721", 1, "timed_out", "timeout", True),
        ("spawn", "20260721", 1, "failed", "spawn_failed", True),
        ("missing", "20260721", 1, "failed", "postcondition_failed", True),
    ],
)
def test_synthetic_voice_cli_writes_terminal_evidence_without_unsafe_promotion(
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

    exit_code = main(["--etl", VOICE, "--fecha", day, "--base", str(_base(tmp_path)),
                      "--param", "no_planes_today"], adapters=_adapters(), service_factory=factory)
    evidence = json.loads(next(runs.rglob("run.json")).read_text("utf-8"))

    assert exit_code == expected_exit
    assert capsys.readouterr().out.endswith(f"status={status}\n")
    assert evidence["status"] == status
    assert evidence["error"] == (None if error is None else {"code": error, "message": error.replace("_", " ")})
    assert bool(runner.command) is ran
    assert str(tmp_path) not in json.dumps(evidence)
    if ran:
        assert "[HOST_PATH]" in json.dumps(evidence)
    promoted = tuple(state_root.rglob("estado_*.csv"))
    if status == "succeeded":
        assert {item["role"] for item in evidence["artifacts"]} == {"roman", "e1kia"}
        assert len(promoted) == 2
        assert "--sin_planes_hoy" not in runner.command and "--chat" not in runner.command
    else:
        assert promoted == ()


def test_voice_rejects_unchanged_staged_state_before_promotion(tmp_path: Path) -> None:
    runs, state_root = tmp_path / "runs", tmp_path / "state"
    lineage = state_root / VOICE / "202607"
    lineage.mkdir(parents=True)
    current = lineage / "estado_202607.csv"
    original = b"state"
    current.write_bytes(original)

    def factory(definition, adapter):
        return RunService(
            definition, adapter, SyntheticRunner("success"), RunStore(runs, state_root),
            StateStore(state_root), workspace=Path.cwd(), now=lambda: "2026-07-21T15:00:00+00:00",
        )

    exit_code = main(
        ["--etl", VOICE, "--fecha", "20260721", "--base", str(_base(tmp_path)),
         "--param", "no_planes_today"], adapters=_adapters(), service_factory=factory,
    )
    evidence = json.loads(next(runs.rglob("run.json")).read_text("utf-8"))

    assert (exit_code, evidence["status"], evidence["error"]["code"]) == (1, "failed", "state_unchanged")
    assert evidence["postconditions"] == {"outputs": "passed", "state": "failed"}
    assert current.read_bytes() == original
    assert not (lineage / "estado_20260721.csv").exists()
