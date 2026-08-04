from datetime import date
from pathlib import Path
import sys

import pytest

from adapters.naranjax.ma_chat import PostconditionError, ValidationError
from adapters.naranjax.ma_voice import MaVoiceAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
NAMES = {
    ArtifactRole.ROMAN: "NARANJAX_MA_ROMAN_20260721.csv",
    ArtifactRole.E1KIA: "NARANJAX_MA_E1KIA_260721_sinestrategia.csv",
}


def _adapter():
    return MaVoiceAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("registry/naranjax.yaml"),
        Path.cwd(),
        adapters={"naranjax.ma.chat": object(), "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object()},
    )["naranjax.ma.voice.daily"]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "naranjax.ma.voice.daily",
        "business_date": TODAY,
        "base": tmp_path / "base.xlsx",
        "no_planes_today": True,
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


@pytest.mark.parametrize("with_planes, with_pagos", [(False, False), (False, True), (True, False), (True, True)])
def test_builds_exact_voice_command_for_optional_inputs(
    tmp_path: Path, with_planes: bool, with_pagos: bool
) -> None:
    run = _sandbox(tmp_path)
    daily = run / "input/diarios"
    changes: dict[str, object] = {}
    optional: list[str] = []
    if with_planes:
        (daily / "planes.xlsx").write_text("synthetic", encoding="utf-8")
        changes.update(planes=tmp_path / "host-planes.xlsx", no_planes_today=False)
        optional.extend(("--planes", str(daily / "planes.xlsx")))
    if with_pagos:
        (daily / "pagos.csv").write_text("synthetic", encoding="utf-8")
        changes["pagos"] = tmp_path / "host-pagos.csv"
        optional.extend(("--pagos", str(daily / "pagos.csv")))

    command = _adapter().command(_definition(), _request(tmp_path, **changes), run)

    assert command == (
        sys.executable,
        "back-base/ejecutar_dia.py",
        "--fecha", "20260721",
        "--mes", "202607",
        "--input", str(run / "input/base.xlsx"),
        "--diarios_dir", str(daily),
        "--estado_dir", str(run / "state"),
        "--output_dir", str(run / "output"),
        "--logs_dir", str(run / "logs"),
        "--procesados_dir", str(run / "processed"),
        *optional,
    )
    assert "--chat" not in command
    assert "--sin_planes_hoy" not in command


def test_rejects_daily_directory_different_from_staged_inputs(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)
    (run / "input/diarios/residual.csv").write_text("synthetic", encoding="utf-8")

    with pytest.raises(ValidationError, match="exactly staged PLANES/PAGOS"):
        _adapter().command(_definition(), _request(tmp_path), run)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"no_planes_today": False}, "requires no_planes_today"),
        ({"planes": Path("planes.xlsx")}, "conflicts with no_planes_today"),
    ],
)
def test_rejects_date_or_planes_intent_conflict(
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
        names[names.index(target)] = target.replace("20260721", "20260720").replace("260721", "260720")
    elif classification == "ambiguous":
        names.append(target.replace("ROMAN_", "ROMAN_copy_") if role is ArtifactRole.ROMAN else target.replace("E1KIA_", "E1KIA_copy_"))
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_changed_today_output_per_voice_role(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, ArtifactRole.ROMAN, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == tuple(NAMES.items())


@pytest.mark.parametrize("role", tuple(NAMES))
@pytest.mark.parametrize("classification", ("missing", "unchanged", "wrong-date", "ambiguous"))
def test_rejects_each_invalid_voice_output(
    tmp_path: Path, role: ArtifactRole, classification: str
) -> None:
    before, after = _inventories(tmp_path, role, classification)

    with pytest.raises(PostconditionError, match=f"{role.value}: {classification}"):
        _adapter().outputs(_definition(), before, after)


def test_rejects_extra_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="extra"):
        _adapter().validate(_request(tmp_path, extras={"logcall": tmp_path / "x.csv"}))
