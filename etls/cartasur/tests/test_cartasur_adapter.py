from datetime import date
from pathlib import Path
import sys

import pytest

from etl_core.contracts import PostconditionError, ValidationError
from etls.cartasur.adapter import CartaSurAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
ROMAN = "CARTA_SUR_ROMAN_260721.csv"
E1KIA = "CARTA_SUR_E1KIA_260721.csv"


def _adapter():
    return CartaSurAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("etls/cartasur/manifest.yaml"),
        Path.cwd(),
        adapters={"cartasur.base.daily": object()},
    )["cartasur.base.daily"]


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "cartasur.base.daily",
        "business_date": TODAY,
        "inputs": {"base": tmp_path / "base.xlsx"},
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_declares_stateless_contract() -> None:
    assert (CartaSurAdapter.stateful, CartaSurAdapter.requires_state_change) == (
        False, False)


@pytest.mark.parametrize("base_name", ("base.xlsx", "base.xlsm", "BBDD CARTA SUR.csv"))
def test_builds_exact_command_honoring_base_suffix(tmp_path: Path, base_name: str) -> None:
    run = _sandbox(tmp_path)
    suffix = Path(base_name).suffix.casefold()

    command = _adapter().command(
        _definition(), _request(tmp_path, inputs={"base": tmp_path / base_name}), run)

    assert command == (
        sys.executable,
        "../job.py",
        "--input", str(run / f"input/base{suffix}"),
        "--output_dir", str(run / "output"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"inputs": {"base": Path("b.xlsx"), "planes": Path("p.xlsx")}},
         "only the base input"),
        ({"params": {"strict": True}}, "no parameters"),
        ({"inputs": {"base": Path("base.txt")}}, "base must be"),
    ],
)
def test_rejects_invalid_requests(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _adapter().validate(_request(tmp_path, **changes))


def _inventories(tmp_path: Path, classification: str):
    run = _sandbox(tmp_path)
    output = run / "output"
    manager = FileManager(run)
    if classification == "unchanged":
        (output / ROMAN).write_text("same", encoding="utf-8")
        (output / E1KIA).write_text("same", encoding="utf-8")
    before = manager.inventory(Path("output"), "output")
    names = [ROMAN, E1KIA]
    if classification == "missing":
        names.remove(E1KIA)
    elif classification == "wrong-date":
        names = [ROMAN.replace("260721", "260720"), E1KIA]
    elif classification == "ambiguous":
        names.append("CARTA_SUR_ROMAN_copy_260721.csv")
    for name in names:
        path = output / name
        if not path.exists():
            path.write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_exactly_one_changed_pair_of_outputs(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == (
        (ArtifactRole.ROMAN, ROMAN),
        (ArtifactRole.E1KIA, E1KIA),
    )


@pytest.mark.parametrize(
    ("classification", "role"),
    [("missing", "e1kia"), ("unchanged", "roman"),
     ("wrong-date", "roman"), ("ambiguous", "roman")],
)
def test_rejects_each_invalid_output(tmp_path: Path, classification: str, role: str) -> None:
    before, after = _inventories(tmp_path, classification)

    with pytest.raises(PostconditionError, match=f"{role}: {classification}"):
        _adapter().outputs(_definition(), before, after)
