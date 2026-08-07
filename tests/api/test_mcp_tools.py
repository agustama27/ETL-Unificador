from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_mcp import tools
from tests.api.test_console_api import TODAY, FakeService, _workspace

from platform_api.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        _workspace(tmp_path),
        service_factory=FakeService, executor=lambda job: job(),
        today=lambda: TODAY,
    )
    return TestClient(app)


def test_list_and_describe_expose_catalog_contract(client: TestClient) -> None:
    entries = tools.list_etls(client)

    assert len(entries) == 22
    assert {"id", "name", "client", "executable", "reason"} == set(entries[0])

    detail = tools.describe_etl(client, "naranjax.ma.chat.daily")
    assert detail["params"] == ["no_planes_today"]
    assert detail["inputs"][0]["role"] == "base"

    with pytest.raises(RuntimeError, match="desconocido"):
        tools.describe_etl(client, "no.existe")


def test_run_get_and_download_roundtrip(client: TestClient, tmp_path: Path) -> None:
    base = tmp_path / "historial.csv"
    base.write_text("synthetic", encoding="utf-8")

    launched = tools.run_etl(client, "naranjax.ma.voice.pct", TODAY.isoformat(),
                             {"base": str(base)})
    run_id = launched["run_id"]

    detail = tools.get_run(client, run_id)
    assert detail["status"] == "succeeded"
    assert detail["artifacts"][0]["role"] == "pct"

    saved = tools.download_artifact(client, run_id, "pct", str(tmp_path / "descargas"))
    assert Path(saved).name == "NARANJAX_PCT_20260721.csv"
    assert Path(saved).read_text("utf-8").startswith("DNI|")


def test_run_etl_surfaces_api_validation_errors(client: TestClient, tmp_path: Path) -> None:
    base = tmp_path / "historial.csv"
    base.write_text("synthetic", encoding="utf-8")

    with pytest.raises(RuntimeError, match="fecha de negocio"):
        tools.run_etl(client, "naranjax.ma.voice.pct", "2026-07-20", {"base": str(base)})
