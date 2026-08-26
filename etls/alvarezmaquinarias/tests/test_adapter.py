from datetime import date
from pathlib import Path
import sys

import pytest

from etl_core.contracts import PostconditionError, ValidationError
from etls.alvarezmaquinarias.adapter import AlvarezMaquinariasAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import ArtifactRole, RunRequest


TODAY = date(2026, 7, 21)
ROMAN = "ALVAREZ_MAQUINARIAS_ROMAN_260721.csv"
E1KIA = "ALVAREZ_MAQUINARIAS_E1KIA_260721.csv"


def _adapter():
    return AlvarezMaquinariasAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("etls/alvarezmaquinarias/manifest.yaml"),
        Path.cwd(),
        adapters={"alvarez.cobranzas.daily": object()},
    )["alvarez.cobranzas.daily"]


def _inputs(tmp_path: Path, base_name: str = "saldos.xls") -> dict[str, Path]:
    return {
        "base": tmp_path / base_name,
        "maquinarias": tmp_path / "maquinarias.xlsx",
        "servicios": tmp_path / "servicios.xlsx",
        "repuestos": tmp_path / "repuestos.pdf",
    }


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "alvarez.cobranzas.daily",
        "business_date": TODAY,
        "inputs": _inputs(tmp_path),
    }
    values.update(changes)
    return RunRequest(**values)  # type: ignore[arg-type]


def _sandbox(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    FileManager(run).create_sandbox()
    return run


def test_declares_stateless_contract() -> None:
    assert (AlvarezMaquinariasAdapter.stateful,
            AlvarezMaquinariasAdapter.requires_state_change) == (False, False)


@pytest.mark.parametrize(
    ("base_name", "staged_suffix"), [("saldos.xls", ".xls"), ("sal +20.csv", ".csv")]
)
def test_builds_exact_command_honoring_base_suffix(
    tmp_path: Path, base_name: str, staged_suffix: str
) -> None:
    run = _sandbox(tmp_path)

    command = _adapter().command(_definition(), _request(tmp_path, inputs=_inputs(tmp_path, base_name)), run)

    assert command == (
        sys.executable,
        "../job.py",
        "--input", str(run / f"input/base{staged_suffix}"),
        "--output_dir", str(run / "output"),
        "--maquinarias", str(run / "input/maquinarias.xlsx"),
        "--repuestos", str(run / "input/repuestos.pdf"),
        "--servicios", str(run / "input/servicios.xlsx"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"params": {"overwrite": True}}, "no parameters"),
        ({"inputs": {"base": Path("saldos.xls")}}, "missing cobranzas inputs"),
    ],
)
def test_rejects_non_today_or_incomplete_requests(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _adapter().validate(_request(tmp_path, **changes))


def test_rejects_unknown_extra_input(tmp_path: Path) -> None:
    inputs = dict(_inputs(tmp_path))
    inputs["planes"] = tmp_path / "planes.xlsx"
    with pytest.raises(ValidationError, match="unknown cobranzas inputs"):
        _adapter().validate(_request(tmp_path, inputs=inputs))


def test_rejects_unsupported_saldos_extension(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="saldos must be"):
        _adapter().validate(_request(tmp_path, inputs=_inputs(tmp_path, "saldos.xlsx")))


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
        names.append("ALVAREZ_MAQUINARIAS_ROMAN_copy_260721.csv")
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
