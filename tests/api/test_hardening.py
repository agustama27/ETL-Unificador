import json
import os
import shutil
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from platform_api.main import create_app


TODAY = date(2026, 7, 22)  # miércoles: hay deadline de Bancor
WORKSPACE = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path) -> Path:
    for manifest in WORKSPACE.glob("etls/*/manifest.yaml"):
        target = tmp_path / manifest.relative_to(WORKSPACE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, target)
    return tmp_path


def _write_run(workspace: Path, etl_id: str, run_id: str, status: str,
               business_date: str = "2026-07-22") -> Path:
    run_dir = workspace / "var/runs" / etl_id / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "schema": 1, "run_id": run_id, "etl_id": etl_id,
        "business_date": business_date, "status": status,
        "lifecycle": [{"status": "preparing", "at": "t0"}, {"status": status, "at": "t1"}],
        "inputs": [], "artifacts": [], "logs": [], "process": None,
        "postconditions": {"outputs": "not_run", "state": "not_started"},
        "state": {"scope": "s", "status": "not_started"},
        "blocker": None, "error": None,
    }), encoding="utf-8")
    return run_dir


def _client(tmp_path: Path, **overrides) -> TestClient:
    overrides.setdefault("token", "")
    app = create_app(
        _workspace(tmp_path), executor=lambda job: job(),
        today=lambda: TODAY, **overrides,
    )
    return TestClient(app)


def test_token_guards_every_api_route(tmp_path: Path) -> None:
    client = _client(tmp_path, token="secreto")

    assert client.get("/api/catalog").status_code == 401
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs/x/artifacts.zip").status_code == 401
    assert client.get("/api/runs/x/artifacts/pct").status_code == 401
    allowed = client.get("/api/catalog", headers={"Authorization": "Bearer secreto"})
    assert allowed.status_code == 200
    header_variant = client.get("/api/runs", headers={"X-Api-Token": "secreto"})
    assert header_variant.status_code == 200


def test_unconfigured_auth_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ETL_CONSOLE_TOKEN", raising=False)
    monkeypatch.delenv("ETL_AUTH_DISABLED", raising=False)

    closed = TestClient(create_app(_workspace(tmp_path), today=lambda: TODAY))
    response = closed.get("/api/catalog")
    assert response.status_code == 503
    assert "ETL_CONSOLE_TOKEN" in response.json()["detail"]

    monkeypatch.setenv("ETL_AUTH_DISABLED", "1")
    dev = TestClient(create_app(_workspace(tmp_path / "dev"), today=lambda: TODAY))
    assert dev.get("/api/catalog").status_code == 200


def test_orphaned_live_runs_are_failed_at_startup(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_run(workspace, "bancor.base.daily", "run-huerfana", "running")

    client = TestClient(create_app(workspace, token="", today=lambda: TODAY))
    detail = client.get("/api/runs/run-huerfana").json()

    assert detail["status"] == "failed"
    assert detail["error_code"] == "orphaned"
    assert client.get("/api/schedule").json()["orphaned_runs"] == ["run-huerfana"]


def test_retention_purges_only_old_terminal_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    old = _write_run(workspace, "bancor.base.daily", "run-vieja", "succeeded")
    fresh = _write_run(workspace, "bancor.base.daily", "run-nueva", "succeeded")
    upload = workspace / "var/uploads" / "carga-vieja"
    upload.mkdir(parents=True)
    stale = time.time() - 40 * 24 * 3600
    for path in (old, upload):
        os.utime(path, (stale, stale))

    _client(tmp_path, retention_days=30)

    assert not old.exists()
    assert not upload.exists()
    assert fresh.exists()


def test_list_runs_serves_preexisting_evidence_from_index(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_run(workspace, "bancor.base.daily", "run-1", "succeeded")

    listing = _client(tmp_path).get("/api/runs").json()

    assert listing["total"] == 1
    item = listing["items"][0]
    assert (item["run_id"], item["client"], item["status"]) == (
        "run-1", "Bancor", "succeeded")


def test_schedule_reports_pending_deadline_until_success(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = client.get("/api/schedule").json()
    assert first["deadlines"] == [{
        "etl_id": "bancor.base.daily", "client": "Bancor", "before": "12:30",
        "hint": "Entrega miércoles y viernes antes de 12:30", "ran_today": False,
    }]

    _write_run(_workspace(tmp_path), "bancor.base.daily", "run-ok", "succeeded")


def test_notify_dev_delivers_to_webhook_and_appends_jsonl(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_run(workspace, "bancor.base.daily", "run-err", "failed")
    received = []

    client = TestClient(create_app(workspace, token="", today=lambda: TODAY,
                                   notifier=received.append))
    response = client.post("/api/runs/run-err/actions/notify_dev").json()

    assert response == {"ok": True, "action": "notify_dev", "delivered": True}
    assert received[0]["run_id"] == "run-err"
    log = (workspace / "var/notifications.jsonl").read_text("utf-8").strip()
    assert json.loads(log)["etl_id"] == "bancor.base.daily"
