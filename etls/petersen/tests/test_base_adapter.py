from datetime import date
from pathlib import Path
import sys

import pytest

from etl_core.contracts import PostconditionError, ValidationError
from etls.petersen.adapter_base import PetersenBaseAdapter
from orchestrator.catalog import Catalog
from orchestrator.file_manager import FileManager
from orchestrator.models import RunRequest


TODAY = date(2026, 7, 21)
NAMES = {
    "base": "20260721_AG002_BSFC3BUC_INTEGRACION.csv",
    "deelo_1": "20260721_AG002_BSFC3BUC_PRODCLI_DEELO.csv",
    "mailcli_1": "20260721_AG002_BSFC3BUC_MAILCLI.xls",
}
OUTPUTS = ("tabla_integradora_20260721_153000.csv",
           "telefonos_20260721_153000.csv",
           "telefonos_petersen_20260721_153000.txt",
           "telefonos_tel1_20260721_153000.txt",
           "telefonos_petersen_por_cliente_20260721_153000.csv")


def _adapter():
    return PetersenBaseAdapter(today=lambda: TODAY)


def _definition():
    return Catalog.load(
        Path("etls/petersen/manifest.yaml"),
        Path.cwd(),
        adapters={"petersen.gestiones.daily": object(),
                  "petersen.base.daily": object()},
    )["petersen.base.daily"]


def _inputs(tmp_path: Path) -> dict[str, Path]:
    return {role: tmp_path / name for role, name in NAMES.items()}


def _request(tmp_path: Path, **changes: object) -> RunRequest:
    values = {
        "etl_id": "petersen.base.daily",
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
    assert (PetersenBaseAdapter.stateful,
            PetersenBaseAdapter.requires_state_change) == (False, False)


def test_staging_preserves_original_filenames(tmp_path: Path) -> None:
    destination = _adapter().input_destination("base", tmp_path / NAMES["base"])
    assert destination == Path("input/incoming") / NAMES["base"]


def test_builds_directory_command(tmp_path: Path) -> None:
    run = _sandbox(tmp_path)

    command = _adapter().command(_definition(), _request(tmp_path), run)

    assert command == (
        sys.executable,
        "../job_base.py",
        "--input", str(run / "input/incoming"),
        "--output_dir", str(run / "output"),
    )


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"business_date": date(2026, 7, 20)}, "host-local today"),
        ({"params": {"max_clients": "5"}}, "no parameters"),
        ({"inputs": {"base": Path(NAMES["base"])}}, "missing base inputs"),
        ({"inputs": {"base": Path(NAMES["base"]), "deelo_1": Path(NAMES["deelo_1"]),
                     "planes": Path("planes.csv")}}, "unknown base inputs"),
        ({"inputs": {"base": Path("INTEGRACION_sin_fecha.csv"),
                     "deelo_1": Path(NAMES["deelo_1"])}}, "debe empezar con YYYYMMDD"),
        ({"inputs": {"base": Path("20260721_XXX_INTEGRACION.csv"),
                     "deelo_1": Path(NAMES["deelo_1"])}}, "debe empezar con YYYYMMDD"),
        ({"inputs": {"base": Path(NAMES["base"]),
                     "deelo_1": Path("20260720_AG002_BSFC3BUC_PRODCLI_DEELO.csv")}},
         "misma fecha"),
        ({"inputs": {"base": Path(NAMES["base"]),
                     "deelo_1": Path("20260721_AG002_BSCC3BUC_PRODCLI_DEELO.csv")}},
         "sin su"),
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
    before = manager.inventory(Path("output"), "output")
    names = list(OUTPUTS)
    if classification == "missing":
        names.pop()
    elif classification == "ambiguous":
        names.append("telefonos_petersen_por_cliente_20260721_153001.csv")
    for name in names:
        (output / name).write_text("new", encoding="utf-8")
    return before, manager.inventory(Path("output"), "output")


def test_accepts_the_five_timestamped_outputs(tmp_path: Path) -> None:
    before, after = _inventories(tmp_path, "success")

    artifacts = _adapter().outputs(_definition(), before, after)

    assert tuple((item.role, item.path.name) for item in artifacts) == (
        ("tabla_integradora", OUTPUTS[0]),
        ("telefonos", OUTPUTS[1]),
        ("telefonos_txt", OUTPUTS[2]),
        ("telefonos_tel1", OUTPUTS[3]),
        ("telefonos_cliente", OUTPUTS[4]),
    )


@pytest.mark.parametrize(
    ("classification", "role"),
    [("missing", "telefonos_cliente"), ("ambiguous", "telefonos_cliente")],
)
def test_rejects_missing_or_duplicated_output(
    tmp_path: Path, classification: str, role: str
) -> None:
    before, after = _inventories(tmp_path, classification)

    with pytest.raises(PostconditionError, match=f"{role}: {classification}"):
        _adapter().outputs(_definition(), before, after)


def test_telefonos_glob_does_not_swallow_por_cliente(tmp_path: Path) -> None:
    """El glob 'telefonos_[0-9]*.csv' no debe matchear el por_cliente."""
    before, after = _inventories(tmp_path, "success")
    artifacts = _adapter().outputs(_definition(), before, after)
    by_role = {item.role: item.path.name for item in artifacts}
    assert by_role["telefonos"] == OUTPUTS[1]
    assert by_role["telefonos_cliente"] == OUTPUTS[4]
