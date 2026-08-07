import json
import shutil
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_api.main import create_app


TODAY = date(2026, 7, 21)
WORKSPACE = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path) -> Path:
    shutil.copytree(WORKSPACE / "registry", tmp_path / "registry")
    return tmp_path


class FakeService:
    """Writes a terminal run.json into the reserved run dir."""

    def __init__(self, definition, adapter, store, workspace, *, status="succeeded"):
        self.store, self.status = store, status
        self.definition = definition

    def execute(self, request):
        run = self.store.create_run(request.etl_id)
        (run / "output").mkdir(parents=True, exist_ok=True)
        artifacts = []
        if self.status == "succeeded":
            artifact = run / "output" / "NARANJAX_PCT_20260721.csv"
            artifact.write_text("DNI|TIPIFICACION\n", encoding="utf-8")
            artifacts = [{"role": "pct", "path": "output/NARANJAX_PCT_20260721.csv",
                          "size": artifact.stat().st_size, "mtime_ns": 0, "sha256": "x"}]
        # json.dump directo: write_metadata usa un .tmp largo que rompe
        # MAX_PATH bajo el tmp_path de pytest en Windows.
        (run / "run.json").write_text(json.dumps({
            "run_id": run.name, "etl_id": request.etl_id,
            "business_date": request.business_date.isoformat(),
            "status": self.status,
            "lifecycle": [{"status": "preparing", "at": "t0"},
                          {"status": self.status, "at": "t1"}],
            "inputs": [{"role": "base", "path": "input/base.csv",
                        "size": 9, "mtime_ns": 0, "sha256": "abc"}],
            "process": {"command": ["python", "job.py"], "cwd": "x",
                        "environment": {}, "stdout": "linea1\nlinea2",
                        "stderr": "", "exit_code": 0, "timed_out": False,
                        "termination": "completed", "timestamps": ["a", "b"],
                        "error": None},
            "logs": [], "artifacts": artifacts,
            "postconditions": {"outputs": "passed", "state": "not_applicable"},
            "state": {"scope": "s", "status": "not_started"},
            "blocker": None,
            "error": None if self.status == "succeeded" else
                     {"code": "nonzero_exit", "message": "nonzero exit"},
        }), encoding="utf-8")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        _workspace(tmp_path),
        service_factory=FakeService, executor=lambda job: job(),
        today=lambda: TODAY,
    )
    return TestClient(app)


def test_catalog_exposes_all_entries_with_metadata(client: TestClient) -> None:
    entries = client.get("/api/catalog").json()

    assert len(entries) == 22
    by_id = {entry["id"]: entry for entry in entries}
    chat = by_id["naranjax.ma.chat.daily"]
    assert (chat["client"], chat["executable"], chat["stateful"],
            chat["params"]) == ("Naranja X", True, True, ["no_planes_today"])
    retell = by_id["petersen.retell"]
    assert retell["executable"] is False
    assert "Retell" in retell["reason"]
    assert by_id["bancor.base.daily"]["deadline_hint"].startswith("Entrega")
    assert sum(1 for entry in entries if entry["executable"]) == 15


def _launch(client: TestClient, **overrides):
    data = {"etl_id": "naranjax.ma.voice.pct",
            "business_date": "2026-07-21", "params": "{}"}
    data.update({k: v for k, v in overrides.items() if not k.startswith("_")})
    files = overrides.get("_files",
                          {"base": ("historial.csv", b"synthetic", "text/csv")})
    return client.post("/api/runs", data=data, files=files)


def test_run_lifecycle_history_and_artifacts(client: TestClient) -> None:
    launched = _launch(client)
    assert launched.status_code == 202
    run_id = launched.json()["run_id"]

    detail = client.get(f"/api/runs/{run_id}").json()
    assert (detail["status"], detail["client"]) == ("succeeded", "Naranja X")
    assert detail["artifacts"][0]["name"] == "NARANJAX_PCT_20260721.csv"
    assert detail["logs"]["stdout_tail"].endswith("linea2")

    history = client.get("/api/runs", params={"client": "Naranja X"}).json()
    assert history["total"] == 1
    assert history["items"][0]["run_id"] == run_id

    single = client.get(f"/api/runs/{run_id}/artifacts/pct")
    assert single.status_code == 200
    bundle = client.get(f"/api/runs/{run_id}/artifacts.zip")
    names = zipfile.ZipFile(BytesIO(bundle.content)).namelist()
    assert set(names) == {"run.json", "NARANJAX_PCT_20260721.csv"}


@pytest.mark.parametrize(
    ("overrides", "status", "fragment"),
    [
        ({"business_date": "2026-07-20"}, 422, "hoy"),
        ({"_files": {"base": ("historial.xlsx", b"x", "app/x")}}, 422, "Extensión"),
        ({"_files": {}}, 422, "requerido"),
        ({"etl_id": "petersen.retell"}, 409, "no es ejecutable"),
        ({"etl_id": "inexistente"}, 404, "desconocido"),
    ],
)
def test_post_run_validations(client: TestClient, overrides, status, fragment) -> None:
    response = _launch(client, **overrides)

    assert response.status_code == status
    assert fragment in response.json()["detail"]


def test_free_lock_action_removes_orphan_lock(client: TestClient, tmp_path: Path) -> None:
    run_id = _launch(client).json()["run_id"]
    lock = tmp_path / "var/state/naranjax.ma.voice.pct/202607/.lock"
    lock.mkdir(parents=True)

    freed = client.post(f"/api/runs/{run_id}/actions/free_lock").json()

    assert freed == {"ok": True, "action": "free_lock", "freed": True}
    assert not lock.exists()


def test_notify_dev_action_appends_notification(client: TestClient, tmp_path: Path) -> None:
    run_id = _launch(client).json()["run_id"]

    response = client.post(f"/api/runs/{run_id}/actions/notify_dev")

    assert response.json()["ok"] is True
    lines = (tmp_path / "var/notifications.jsonl").read_text("utf-8").splitlines()
    assert json.loads(lines[0])["run_id"] == run_id
