from datetime import date
from pathlib import Path
import sys

import pytest

from etls.naranjax.ma_chat import PostconditionError, ValidationError
from etls.naranjax.mt_voice import MtVoiceAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
NAMES = {
    ArtifactRole.ROMAN: "NARANJAX_MT_ROMAN_260721.csv",
    ArtifactRole.E1KIA: "NARANJAX_MT_E1KIA_260721.csv",
}


def _adapter():
    return MtVoiceAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("etls/naranjax/manifest.yaml"),
        Path.cwd(),
        adapters={"naranjax.ma.chat": object(), "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()},
    )["naranjax.mt.voice.daily"]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "naranjax.mt.voice.daily",
        "business_date": TODAY,
        "inputs": {"base": tmp_path / "base.txt"},
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_declares_stateless_contract() -> None:
    assert (MtVoiceAdapter.stateful, MtVoiceAdapter.requires_state_change) == (
        False, False
    )


def test_builds_exact_mt_command(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)

    command = _adapter().command(_definition(), _request(tmp_path), run)

    assert command == (
        sys.executable,
        "../../mt_voice_job.py",
        "--input", str(run / "input/base.txt"),
        "--output_dir", str(run / "output"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"inputs": {"base": Path("b.txt"), "planes": Path("planes.xlsx")}},
         "no extra inputs"),
        ({"inputs": {"base": Path("b.txt"), "pagos": Path("pagos.csv")}},
         "no extra inputs"),
        ({"params": {"no_planes_today": True}}, "no parameters"),
    ],
)
def test_rejects_non_today_or_daily_intents(
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
        names[names.index(target)] = target.replace("260721", "260720")
    elif classification == "ambiguous":
        names.append(target.replace("_260721", "_copy_260721"))
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_changed_today_output_per_mt_role(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, ArtifactRole.ROMAN, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == tuple(NAMES.items())


@pytest.mark.parametrize("role", tuple(NAMES))
@pytest.mark.parametrize("classification", ("missing", "unchanged", "wrong-date", "ambiguous"))
def test_rejects_each_invalid_mt_output(
    tmp_path: Path, role: ArtifactRole, classification: str
) -> None:
    before, after = _inventories(tmp_path, role, classification)

    with pytest.raises(PostconditionError, match=f"{role.value}: {classification}"):
        _adapter().outputs(_definition(), before, after)


def test_rejects_extra_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="extra"):
        _adapter().validate(_request(tmp_path, inputs={
            "base": tmp_path / "base.txt", "logcall": tmp_path / "x.csv"}))
