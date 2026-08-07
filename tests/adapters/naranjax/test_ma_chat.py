from datetime import date
from pathlib import Path
import sys

import pytest

from adapters.naranjax.ma_chat import MaChatAdapter, PostconditionError, ValidationError
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
NAMES = {
    ArtifactRole.ROMAN: "NARANJAX_MA_ROMAN_20260721.csv",
    ArtifactRole.CHAT: "NARANJAX_MA_CHAT_ROMAN_260721.csv",
    ArtifactRole.E1KIA: "NARANJAX_MA_E1KIA_260721_sinestrategia.csv",
}


def _definition():
    return Catalog.load(Path("registry/naranjax.yaml"), Path.cwd(),
                        adapters={"naranjax.ma.chat": object(), "naranjax.ma.voice": object(),
                  "naranjax.ma.voice.pct": object(), "naranjax.mt.voice": object(),
                  "naranjax.ma.chat.pct": object(), "naranjax.mt.voice.pct": object(),
                  "naranjax.mt.voice.back": object()})[
        "naranjax.ma.chat.daily"
    ]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "naranjax.ma.chat.daily",
        "business_date": TODAY,
        "inputs": {"base": tmp_path / "base.xlsx"},
        "params": {"no_planes_today": True},
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_builds_exact_daily_command_with_optional_inputs(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)
    request = _request(
        tmp_path,
        inputs={"base": tmp_path / "base.xlsx",
                "planes": tmp_path / "host-planes.xlsx",
                "pagos": tmp_path / "host-pagos.csv"},
        params={},
    )

    command = MaChatAdapter(today=lambda: TODAY).command(_definition(), request, run)

    assert command == (
        sys.executable,
        "back-base/ejecutar_dia.py",
        "--fecha", "20260721",
        "--mes", "202607",
        "--input", str(run / "input/base.xlsx"),
        "--diarios_dir", str(run / "input/diarios"),
        "--estado_dir", str(run / "state"),
        "--output_dir", str(run / "output"),
        "--logs_dir", str(run / "logs"),
        "--procesados_dir", str(run / "processed"),
        "--planes", str(run / "input/diarios/planes.xlsx"),
        "--pagos", str(run / "input/diarios/pagos.csv"),
        "--chat",
    )


def test_omitted_planes_uses_only_empty_isolated_daily_directory(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)
    host_planes = tmp_path / "host/planes.xlsx"
    host_planes.parent.mkdir()
    host_planes.write_text("must remain inaccessible", encoding="utf-8")

    command = MaChatAdapter(today=lambda: TODAY).command(
        _definition(), _request(tmp_path), run
    )

    assert command[-2:] == ("--sin_planes_hoy", "--chat")
    assert "--planes" not in command
    assert str(host_planes) not in command
    assert tuple((run / "input/diarios").iterdir()) == ()


def test_omitted_planes_rejects_nonempty_isolated_directory(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)
    (run / "input/diarios/residual.xlsx").write_text("synthetic", encoding="utf-8")

    with pytest.raises(ValidationError, match="daily directory must be empty"):
        MaChatAdapter(today=lambda: TODAY).command(
            _definition(), _request(tmp_path), run
        )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"params": {}}, "requires no_planes_today"),
    ],
)
def test_rejects_date_or_implicit_planes_omission(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        MaChatAdapter(today=lambda: TODAY).validate(_request(tmp_path, **changes))


def _inventories(
    tmp_path: Path, role: ArtifactRole, classification: str
):
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
        names[names.index(target)] = target.replace("20260721", "20260720").replace(
            "260721", "260720"
        )
    elif classification == "ambiguous":
        names.append(target.replace("ROMAN_", "ROMAN_copy_") if role is not ArtifactRole.E1KIA
                     else target.replace("E1KIA_", "E1KIA_copy_"))
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_new_today_dated_output_per_class(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, ArtifactRole.ROMAN, "success")

    artifacts = MaChatAdapter(today=lambda: TODAY).outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == tuple(NAMES.items())


@pytest.mark.parametrize("role", tuple(ArtifactRole)[:3])
@pytest.mark.parametrize("classification", ("missing", "unchanged", "wrong-date", "ambiguous"))
def test_rejects_each_invalid_output_classification(
    tmp_path: Path, role: ArtifactRole, classification: str
) -> None:
    before, after = _inventories(tmp_path, role, classification)

    with pytest.raises(PostconditionError, match=f"{role.value}: {classification}"):
        MaChatAdapter(today=lambda: TODAY).outputs(_definition(), before, after)


def test_rejects_extra_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="extra"):
        MaChatAdapter(today=lambda: TODAY).validate(
            _request(tmp_path, inputs={"base": tmp_path / "base.xlsx",
                                       "logcall": tmp_path / "x.csv"})
        )
