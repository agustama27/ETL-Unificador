"""Production hardening for the console API (ADR-001, Fase 4).

SQLite run index, orphan recovery at startup, retention policy for PII-bearing
run evidence, and an outbound webhook notifier. Everything here layers over the
orchestrator's on-disk evidence — ``run.json`` remains the source of truth.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

LIVE_STATUSES = {"preparing", "running"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    etl_id TEXT NOT NULL,
    business_date TEXT,
    status TEXT NOT NULL,
    error_code TEXT,
    started_at TEXT,
    finished_at TEXT,
    artifacts_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS runs_etl_status ON runs (etl_id, status);
"""


def read_run(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text("utf-8"))


def summarize(run_dir: Path, document: dict[str, Any]) -> dict[str, Any]:
    lifecycle = document.get("lifecycle") or []
    started = lifecycle[0]["at"] if lifecycle else None
    finished = (lifecycle[-1]["at"]
                if document.get("status") not in LIVE_STATUSES and lifecycle else None)
    return {
        "run_id": run_dir.name,
        "etl_id": document.get("etl_id"),
        "business_date": document.get("business_date"),
        "status": document.get("status"),
        "error_code": (document.get("error") or {}).get("code"),
        "started_at": started,
        "finished_at": finished,
        "artifacts_count": len(document.get("artifacts") or []),
    }


class RunIndex:
    """SQLite summary index over ``var/runs``; run.json stays authoritative."""

    def __init__(self, database: Path, runs_root: Path) -> None:
        self._database = database
        self._runs_root = runs_root
        self._lock = threading.Lock()
        database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database)
        connection.row_factory = sqlite3.Row
        return connection

    def _run_dir(self, etl_id: str, run_id: str) -> Path:
        return self._runs_root / etl_id / run_id

    def upsert(self, run_dir: Path) -> None:
        if not (run_dir / "run.json").exists():
            return
        summary = summarize(run_dir, read_run(run_dir))
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (summary["run_id"], summary["etl_id"], summary["business_date"],
                 summary["status"], summary["error_code"], summary["started_at"],
                 summary["finished_at"], summary["artifacts_count"]),
            )

    def refresh_full(self) -> None:
        if not self._runs_root.exists():
            return
        for etl_dir in self._runs_root.iterdir():
            if etl_dir.is_dir():
                for run_dir in etl_dir.iterdir():
                    self.upsert(run_dir)

    def _refresh_live(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, etl_id FROM runs WHERE status IN ('preparing', 'running')"
            ).fetchall()
        for row in rows:
            run_dir = self._run_dir(row["etl_id"], row["run_id"])
            if (run_dir / "run.json").exists():
                self.upsert(run_dir)
            else:
                with self._lock, self._connect() as connection:
                    connection.execute("DELETE FROM runs WHERE run_id = ?", (row["run_id"],))

    def query(self, *, etl_id: str | None = None, status: str | None = None,
              business_date: str | None = None) -> list[dict[str, Any]]:
        self._refresh_live()
        clauses, values = [], []
        for column, value in (("etl_id", etl_id), ("status", status),
                              ("business_date", business_date)):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM runs{where} ORDER BY run_id DESC", values
            ).fetchall()
        return [dict(row) for row in rows]

    def ran_today(self, etl_id: str, business_date: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM runs WHERE etl_id = ? AND business_date = ?"
                " AND status = 'succeeded' LIMIT 1",
                (etl_id, business_date),
            ).fetchone()
        return row is not None


def recover_orphans(runs_root: Path, write_metadata: Callable[[Path, dict[str, Any]], None],
                    now: Callable[[], str]) -> list[str]:
    """Mark live runs from a previous process as failed with code ``orphaned``."""
    recovered = []
    if not runs_root.exists():
        return recovered
    for etl_dir in runs_root.iterdir():
        if not etl_dir.is_dir():
            continue
        for run_dir in etl_dir.iterdir():
            if not (run_dir / "run.json").exists():
                continue
            document = read_run(run_dir)
            if document.get("status") not in LIVE_STATUSES:
                continue
            detail = {"code": "orphaned",
                      "message": "corrida interrumpida por reinicio del servicio"}
            document["status"] = "failed"
            document["error"] = detail
            document.setdefault("lifecycle", []).append({"status": "failed", "at": now()})
            document.pop("schema", None)
            write_metadata(run_dir, document)
            recovered.append(run_dir.name)
    return recovered


def purge_expired(roots: tuple[Path, ...], retention_days: int,
                  now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> int:
    """Delete run/upload directories older than the retention window (they hold PII)."""
    if retention_days <= 0:
        return 0
    cutoff = (now() - timedelta(days=retention_days)).timestamp()
    removed = 0
    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            candidates = tuple(child.iterdir()) if (root.name == "runs") else (child,)
            for candidate in candidates:
                marker = candidate / "run.json"
                if marker.exists():
                    document = read_run(candidate)
                    if document.get("status") in LIVE_STATUSES:
                        continue
                if candidate.stat().st_mtime < cutoff:
                    shutil.rmtree(candidate, ignore_errors=True)
                    removed += 1
    return removed


def webhook_notifier(url: str, *, timeout: float = 5.0) -> Callable[[dict[str, Any]], None]:
    """POST the notification JSON to a webhook (Slack/Teams/n8n compatible)."""

    def notify(payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout):
            pass

    return notify
