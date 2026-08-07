from datetime import date
from pathlib import Path
import sys

import pytest

from adapters.naranjax.ma_chat import PostconditionError, ValidationError
from adapters.naranjax.mt_voice_back import MtVoiceBackAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
NAMES = {
    ArtifactRole.PCT: "DEELO_NAR_USUEVOLTIS_20260721_15.txt",
    ArtifactRole.ANOMALIES: "_anomalias_20260721_153000.txt",
}


def _adapter():
    return MtVoiceBackAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("registry/naranjax.yaml"),
        Path.cwd(),
        adapters={"naranjax.ma.chat": object(), "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()},
    )["naranjax.mt.voice.back"]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "naranjax.mt.voice.back",
        "business_date": TODAY,
        "inputs": {"base": tmp_path / "m30.txt",
                   "logcall": tmp_path / "LOGCALL.csv",
                   "historial": tmp_path / "historial.csv"},
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_declares_stateless_contract() -> None:
    assert (MtVoiceBackAdapter.stateful, MtVoiceBackAdapter.requires_state_change) == (
        False, False
    )


def test_builds_exact_back_command(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)

    command = _adapter().command(_definition(), _request(tmp_path), run)

    assert command == (
        sys.executable,
        "main.py",
        "--back",
        "--logcall", str(run / "input/logcall.csv"),
        "--historial", str(run / "input/historial.csv"),
        "--m30", str(run / "input/base.txt"),
        "--back-output-dir", str(run / "output"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"inputs": {"base": Path("m.txt"), "logcall": Path("a.csv"),
                     "historial": Path("b.csv"), "planes": Path("planes.xlsx")}},
         "exactly logcall and historial"),
        ({"params": {"no_planes_today": True}}, "no parameters"),
        ({"inputs": {"base": Path("m.txt")}}, "exactly logcall and historial"),
        ({"inputs": {"base": Path("m.txt"), "logcall": Path("LOGCALL.csv")}},
         "exactly logcall and historial"),
        ({"inputs": {"base": Path("m.txt"), "logcall": Path("a.csv"),
                     "historial": Path("b.csv"), "otro": Path("c.csv")}},
         "exactly logcall and historial"),
    ],
)
def test_rejects_invalid_intents_or_incomplete_extras(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _adapter().validate(_request(tmp_path, **changes))


def _inventories(tmp_path: Path, role: ArtifactRole, classification: str):
    run = _sandbox(tmp_path)
    output = run / "output"
    manager = FileManager(run)
    target = NAMES[role]
    if classification == "unchanged":
        (output / target).write_text("same", encoding="utf-8")
    before = manager.inventory(Path("output"), "output")
    names = list(NAMES.values())
    if classification == "missing":
        names.remove(target)
    elif classification == "wrong-date":
        names[names.index(target)] = target.replace("20260721", "20260720")
    elif classification == "ambiguous":
        names.append(target.replace("_2026", "_copy_2026"))
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_changed_today_output_per_back_role(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, ArtifactRole.PCT, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == tuple(NAMES.items())


@pytest.mark.parametrize("role", tuple(NAMES))
@pytest.mark.parametrize("classification", ("missing", "unchanged", "wrong-date", "ambiguous"))
def test_rejects_each_invalid_back_output(
    tmp_path: Path, role: ArtifactRole, classification: str
) -> None:
    before, after = _inventories(tmp_path, role, classification)

    with pytest.raises(PostconditionError, match=f"{role.value}: {classification}"):
        _adapter().outputs(_definition(), before, after)
