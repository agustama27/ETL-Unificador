from datetime import date
from pathlib import Path
import sys

import pytest

from etls.naranjax.ma_chat import PostconditionError, ValidationError
from etls.naranjax.ma_voice_pct import MaVoicePctAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
NAME = "NARANJAX_PCT_20260721.csv"


def _adapter():
    return MaVoicePctAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("etls/naranjax/manifest.yaml"),
        Path.cwd(),
        adapters={"naranjax.ma.chat": object(), "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()},
    )["naranjax.ma.voice.pct"]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "naranjax.ma.voice.pct",
        "business_date": TODAY,
        "inputs": {"base": tmp_path / "historial.csv"},
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_declares_stateless_contract() -> None:
    assert (MaVoicePctAdapter.stateful, MaVoicePctAdapter.requires_state_change) == (
        False, False
    )


def test_builds_exact_pct_command(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)

    command = _adapter().command(_definition(), _request(tmp_path), run)

    assert command == (
        sys.executable,
        "back-resultados/etl_tipificaciones_ia_voz_pct.py",
        "--input", str(run / "input/base.csv"),
        "--output_dir", str(run / "output"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"inputs": {"base": Path("b.csv"), "planes": Path("planes.xlsx")}},
         "only the base input"),
        ({"inputs": {"base": Path("b.csv"), "pagos": Path("pagos.csv")}},
         "only the base input"),
        ({"params": {"no_planes_today": True}}, "no parameters"),
    ],
)
def test_rejects_non_today_or_daily_intents(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _adapter().validate(_request(tmp_path, **changes))


def _inventories(tmp_path: Path, classification: str):
    run = _sandbox(tmp_path)
    output = run / "output"
    manager = FileManager(run)
    if classification == "unchanged":
        (output / NAME).write_text("same", encoding="utf-8")
    before = manager.inventory(Path("output"), "output")
    names = [NAME]
    if classification == "missing":
        names.clear()
    elif classification == "wrong-date":
        names = [NAME.replace("20260721", "20260720")]
    elif classification == "ambiguous":
        names.append("NARANJAX_PCT_copy_20260721.csv")
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_changed_today_pct_output(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == (
        (ArtifactRole.PCT, NAME),
    )


@pytest.mark.parametrize("classification", ("missing", "unchanged", "wrong-date", "ambiguous"))
def test_rejects_each_invalid_pct_output(tmp_path: Path, classification: str) -> None:
    before, after = _inventories(tmp_path, classification)

    with pytest.raises(PostconditionError, match=f"pct: {classification}"):
        _adapter().outputs(_definition(), before, after)


def test_rejects_extra_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="base input"):
        _adapter().validate(_request(tmp_path, inputs={
            "base": tmp_path / "historial.csv", "logcall": tmp_path / "x.csv"}))
